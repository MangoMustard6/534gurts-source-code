/**
 * ihtxsap.ts — IHTX-Sap: Pure audio pitch-layer processor.
 *
 * Accepts any video or audio input, strips all video tracks, applies N
 * parallel pitch-shifted layers using the selected style engine, mixes them
 * with amix, repeats the mix `repetitions` times, and outputs a pure .mp3.
 *
 * Slash:  /ihtxsap file=<att> duration=<n> [repetitions=<n>] pitches=<s> [style=<s>]
 * Prefix: th/ihtxsap <repetitions> <duration> <pitch1;pitch2;...> ["Style Name"]
 *
 * Style engines:
 *   Rubberband R2  — rubberband -2 --time-ratio --pitch per layer
 *   Rubberband R3  — rubberband -3 --time-ratio --pitch per layer
 *   Soundtouch     — FFmpeg asetrate + atempo (no external binary)
 *   Bungee         — bungee binary if available; else high-quality FFmpeg fallback
 */

import fs from 'fs';
import path from 'path';
import { Message, ChatInputCommandInteraction, Guild } from 'discord.js';
import { spawnAsync } from '../utils/spawn.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { PROCESS_TIMEOUTS } from '../config.js';

// ── Constants ────────────────────────────────────────────────────────────────

const IMAGE_EXTENSIONS = new Set([
  'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'svg', 'ico', 'avif', 'heic',
]);

const ACCEPTED_EXTENSIONS = new Set([
  'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'opus', 'wma', 'aiff', 'aif',
  'mp4', 'mov', 'mkv', 'webm', 'avi', 'mts', 'm2ts',
]);

export const IHTXSAP_STYLE_CHOICES = [
  { name: 'Rubberband R2', value: 'rubberband_r2' },
  { name: 'Rubberband R3', value: 'rubberband_r3' },
  { name: 'Soundtouch',    value: 'soundtouch'    },
  { name: 'Bungee',        value: 'bungee'        },
] as const;

type StyleValue = typeof IHTXSAP_STYLE_CHOICES[number]['value'];

interface SapOpts {
  duration:    number;     // snip end in seconds — only the first N seconds of audio are used
  repetitions: number;     // concat repeats (default 5)
  pitches:     number[];   // semitone shifts per parallel layer
  style:       StyleValue;
  volume:      number;     // output volume multiplier applied after mix (default 1)
}

const PREFIX_USAGE = [
  '**Usage:** `th/ihtxsap <repetitions> <duration> <pitches> [style] [volume=<n>]`',
  '',
  '  `repetitions` — integer 1–100, how many times the mix is looped (default: `5`)',
  '  `duration`    — seconds to snip from the start of the audio (e.g. `5` = first 5 s)',
  '  `pitches`     — semicolon-separated semitone shifts: `-7;5;6`',
  '  `style`       — optional, in quotes: `"Rubberband R2"` (default), `"Rubberband R3"`, `"Soundtouch"`, `"Bungee"`',
  '  `volume=<n>`  — optional float, output volume multiplier after mix (e.g. `volume=8`)',
  '',
  '**Example:** `th/ihtxsap 5 3 -7;5;6 "Rubberband R3" volume=8`',
  'Attach a video or audio file, reply to one, or have one in recent channel history.',
].join('\n');

// ── Pure helpers ─────────────────────────────────────────────────────────────

function stToRatio(semitones: number): number {
  return Math.pow(2, semitones / 12);
}

/**
 * Build an atempo filter chain that handles values outside FFmpeg's [0.5, 2.0]
 * constraint by chaining multiple atempo filters.
 */
function atempoChain(factor: number): string {
  const filters: string[] = [];
  let f = factor;
  while (f > 2.0 + 1e-9)  { filters.push('atempo=2.0'); f /= 2.0; }
  while (f < 0.5 - 1e-9)  { filters.push('atempo=0.5'); f *= 2.0; }
  filters.push(`atempo=${f.toFixed(9)}`);
  return filters.join(',');
}

function styleLabel(style: StyleValue): string {
  return IHTXSAP_STYLE_CHOICES.find((s) => s.value === style)?.name ?? style;
}

// ── Attachment resolution ────────────────────────────────────────────────────

async function resolveAttachment(
  message: Message,
): Promise<{ url: string; name: string } | null> {
  const direct = message.attachments.first();
  if (direct) return { url: direct.url, name: direct.name };

  if (message.reference?.messageId) {
    try {
      const ref = await message.fetchReference();
      const a = ref.attachments.first();
      if (a) return { url: a.url, name: a.name };
    } catch { /* ignore */ }
  }

  // Scan channel history for the last non-image attachment
  try {
    if (message.channel.isTextBased()) {
      const history = await message.channel.messages.fetch({ limit: 30, before: message.id });
      for (const [, msg] of history) {
        const a = msg.attachments.first();
        if (!a) continue;
        const ext = (a.name?.split('.').pop() ?? '').toLowerCase();
        if (!IMAGE_EXTENSIONS.has(ext)) return { url: a.url, name: a.name };
      }
    }
  } catch { /* ignore */ }

  return null;
}

// ── Prefix argument parser ───────────────────────────────────────────────────

function parsePrefixArgs(raw: string): SapOpts | string {
  // Tokenise respecting quoted groups (handles "Rubberband R2" etc.)
  const tokens: string[] = [];
  let cur = '';
  let inQuote = false;
  let qChar = '';
  for (const ch of raw.trim()) {
    if (inQuote) {
      if (ch === qChar) { inQuote = false; tokens.push(cur); cur = ''; }
      else cur += ch;
    } else if (ch === '"' || ch === "'") {
      inQuote = true; qChar = ch;
    } else if (ch === ' ' || ch === '\t') {
      if (cur) { tokens.push(cur); cur = ''; }
    } else {
      cur += ch;
    }
  }
  if (cur) tokens.push(cur);

  if (tokens.length < 3) return `❌ Not enough arguments.\n\n${PREFIX_USAGE}`;

  const reps = parseInt(tokens[0], 10);
  if (isNaN(reps) || reps < 1 || reps > 100)
    return `❌ \`repetitions\` must be an integer 1–100 (got \`${tokens[0]}\`).`;

  const dur = parseFloat(tokens[1]);
  if (isNaN(dur) || dur <= 0 || dur > 3600)
    return `❌ \`duration\` must be a positive number of seconds (max 3600, got \`${tokens[1]}\`).`;

  const pitches = tokens[2].split(';').map((p) => parseFloat(p.trim()));
  if (pitches.some(isNaN) || pitches.length < 1)
    return `❌ \`pitches\` must be semicolon-separated numbers, e.g. \`-7;5;6\`.`;
  if (pitches.some((p) => Math.abs(p) > 120))
    return `❌ Pitch shifts must be within ±120 semitones.`;

  // Remaining tokens (index ≥ 3): pull out volume=N first, rest is style
  let style: StyleValue = 'rubberband_r2';
  let volume = 1;
  const extraTokens = tokens.slice(3);
  const styleTokens: string[] = [];

  for (const tok of extraTokens) {
    const lower = tok.toLowerCase();
    if (lower.startsWith('volume=')) {
      const v = parseFloat(tok.slice(7));
      if (isNaN(v) || v <= 0 || v > 100)
        return `❌ \`volume\` must be a positive float ≤ 100 (got \`${tok.slice(7)}\`).`;
      volume = v;
    } else {
      styleTokens.push(tok);
    }
  }

  if (styleTokens.length > 0) {
    const s = styleTokens.join(' ').toLowerCase().trim();
    if      (s.includes('r3'))         style = 'rubberband_r3';
    else if (s.includes('soundtouch')) style = 'soundtouch';
    else if (s.includes('bungee'))     style = 'bungee';
    else if (s.includes('r2'))         style = 'rubberband_r2';
    else return `❌ Unknown style "${styleTokens.join(' ')}". Options: Rubberband R2, Rubberband R3, Soundtouch, Bungee.`;
  }

  return { duration: dur, repetitions: reps, pitches, style, volume };
}

// ── Per-layer processors ─────────────────────────────────────────────────────

async function layerRubberband(
  inputWav: string, out: string,
  semitones: number,
  flag: '-2' | '-3',
): Promise<{ code: number; stderr: string }> {
  return spawnAsync('rubberband', [
    flag,
    `--pitch`, String(semitones),
    inputWav, out,
  ], { timeout: PROCESS_TIMEOUTS.RUBBERBAND_MS });
}

async function isSoundtouchAvailable(): Promise<boolean> {
  try {
    const r = await spawnAsync('soundstretch', [], { timeout: 3_000 });
    // soundstretch prints usage and exits non-zero when called with no args — that's fine
    return r.code === 0 || r.stderr.length > 0 || r.stdout.length > 0;
  } catch { return false; }
}

/**
 * SoundTouch style: uses the real `soundstretch` binary (same as th/ssmp).
 * -pitch=<semitones>  — semitone pitch shift
 * -tempo=<percent>    — tempo change: (duration_ratio - 1) * 100
 *   e.g. duration=0.7 → -tempo=-30  (30% slower)
 *        duration=1.5 → -tempo=50   (50% faster)
 */
async function layerSoundtouch(
  inputWav: string, out: string,
  semitones: number,
): Promise<{ code: number; stderr: string }> {
  return spawnAsync('soundstretch', [
    inputWav,
    out,
    `-pitch=${semitones.toFixed(4)}`,
  ], { timeout: PROCESS_TIMEOUTS.RUBBERBAND_MS });
}

async function layerBungeeFallback(
  inputWav: string, out: string,
  semitones: number,
): Promise<{ code: number; stderr: string }> {
  // Pitch-only FFmpeg fallback: asetrate shifts pitch (compensated by aresample) + aphaser
  const ratio = stToRatio(semitones);
  const af = [
    `asetrate=44100*${ratio.toFixed(9)}`,
    `aresample=44100`,
    `aphaser=type=t:speed=0.5:decay=0.4`,
  ].join(',');
  return spawnAsync('ffmpeg', [
    '-y', '-i', inputWav,
    '-af', af,
    '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
    out,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
}

async function layerBungee(
  inputWav: string, out: string,
  semitones: number,
): Promise<{ code: number; stderr: string }> {
  return spawnAsync('bungee', [
    '--pitch', String(semitones),
    inputWav, out,
  ], { timeout: PROCESS_TIMEOUTS.RUBBERBAND_MS });
}

async function isBungeeAvailable(): Promise<boolean> {
  try {
    const r = await spawnAsync('bungee', ['--version'], { timeout: 3_000 });
    return r.code === 0;
  } catch { return false; }
}

// ── Core pipeline ────────────────────────────────────────────────────────────

async function runSap(
  opts:       SapOpts,
  fileUrl:    string,
  fileExt:    string,
  tmpDir:     string,
  setStatus:  (s: string) => Promise<void>,
  guild:      Guild | null,
): Promise<string | null> {

  // 1. Download
  await setStatus('⏳ Downloading input file…');
  const inputRaw = path.join(tmpDir, `input.${fileExt}`);
  await downloadUrl(fileUrl, inputRaw);

  // 2. Extract audio → WAV, snipping at duration seconds (drop all video tracks)
  await setStatus(`⏳ Extracting first ${opts.duration}s of audio…`);
  const inputWav = path.join(tmpDir, 'input.wav');
  const extract = await spawnAsync('ffmpeg', [
    '-y', '-i', inputRaw,
    '-t', String(opts.duration),
    '-vn',
    '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
    inputWav,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (extract.code !== 0) {
    await setStatus(`❌ Audio extraction failed.\n\`\`\`\n${extract.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 3. Binary availability checks
  let bungeeOk = false;
  if (opts.style === 'bungee') {
    bungeeOk = await isBungeeAvailable();
    if (!bungeeOk) {
      await setStatus('⚠️ `bungee` binary not found — using high-quality FFmpeg fallback…');
      await new Promise((r) => setTimeout(r, 800));
    }
  }
  if (opts.style === 'soundtouch') {
    const ssOk = await isSoundtouchAvailable();
    if (!ssOk) {
      await setStatus('❌ `soundstretch` binary not found — install the SoundTouch package.');
      return null;
    }
  }

  // 4. Render each pitch layer
  const layerPaths: string[] = [];
  for (let i = 0; i < opts.pitches.length; i++) {
    const st  = opts.pitches[i];
    const out = path.join(tmpDir, `layer_${i}.wav`);
    await setStatus(
      `⏳ Layer ${i + 1}/${opts.pitches.length} — pitch ${st >= 0 ? '+' : ''}${st} st (${styleLabel(opts.style)})…`,
    );

    let result: { code: number; stderr: string };
    switch (opts.style) {
      case 'rubberband_r2': result = await layerRubberband(inputWav, out, st, '-2'); break;
      case 'rubberband_r3': result = await layerRubberband(inputWav, out, st, '-3'); break;
      case 'soundtouch':    result = await layerSoundtouch(inputWav, out, st);       break;
      case 'bungee':
        result = bungeeOk
          ? await layerBungee(inputWav, out, st)
          : await layerBungeeFallback(inputWav, out, st);
        break;
    }

    if (result!.code !== 0) {
      await setStatus(
        `❌ Layer ${i + 1} failed.\n\`\`\`\n${result!.stderr.slice(-400)}\n\`\`\``,
      );
      return null;
    }
    layerPaths.push(out);
  }

  // 5. Mix all layers → mixed.wav
  await setStatus(`⏳ Mixing ${layerPaths.length} layer${layerPaths.length > 1 ? 's' : ''}…`);
  const mixedWav = path.join(tmpDir, 'mixed.wav');
  const mixArgs: string[] = ['-y'];
  for (const lp of layerPaths) mixArgs.push('-i', lp);
  const volFilter = opts.volume !== 1 ? `,volume=${opts.volume.toFixed(6)}` : '';
  const mixFilter = layerPaths.length === 1
    ? `alimiter=limit=0.99:level=false${volFilter}`
    : `amix=inputs=${layerPaths.length}:duration=longest:normalize=0,alimiter=limit=0.99:level=false${volFilter}`;
  mixArgs.push(
    '-filter_complex', mixFilter,
    '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
    mixedWav,
  );
  const mix = await spawnAsync('ffmpeg', mixArgs, { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (mix.code !== 0) {
    await setStatus(`❌ Mix failed.\n\`\`\`\n${mix.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 6. Repeat (concat) N times
  let finalWav = mixedWav;
  if (opts.repetitions > 1) {
    await setStatus(`⏳ Repeating mix ${opts.repetitions}× end-to-end…`);
    finalWav = path.join(tmpDir, 'repeated.wav');
    const listFile = path.join(tmpDir, 'concat.txt');
    fs.writeFileSync(
      listFile,
      Array.from({ length: opts.repetitions }, () => `file '${mixedWav}'`).join('\n'),
    );
    const cat = await spawnAsync('ffmpeg', [
      '-y', '-f', 'concat', '-safe', '0', '-i', listFile,
      '-c', 'copy', finalWav,
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
    if (cat.code !== 0) {
      await setStatus(`❌ Concat failed.\n\`\`\`\n${cat.stderr.slice(-400)}\n\`\`\``);
      return null;
    }
  }

  // 7. Encode to MP3
  await setStatus('⏳ Encoding to MP3…');
  const outputMp3 = path.join(tmpDir, 'ihtxsap.mp3');
  const enc = await spawnAsync('ffmpeg', [
    '-y', '-i', finalWav,
    '-acodec', 'libmp3lame', '-q:a', '2',
    outputMp3,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (enc.code !== 0) {
    await setStatus(`❌ MP3 encoding failed.\n\`\`\`\n${enc.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  return outputMp3;
}

function summaryLine(opts: SapOpts, bungeeOk = false): string {
  const pitchStr = opts.pitches.map((p) => (p >= 0 ? '+' : '') + p).join(', ');
  const engine   = opts.style === 'bungee' && !bungeeOk
    ? 'Bungee (FFmpeg fallback)'
    : styleLabel(opts.style);
  const volPart  = opts.volume !== 1 ? ` · vol ×${opts.volume}` : '';
  return `Pitches: **${pitchStr}** · snip **${opts.duration}s** · ${opts.repetitions}× · ${engine}${volPart}`;
}

// ── Prefix entry point ───────────────────────────────────────────────────────

export async function handleIhtxSap(message: Message): Promise<void> {
  const body = message.content.slice(message.content.toLowerCase().indexOf('ihtxsap') + 7).trim();

  if (!body) {
    await message.reply(PREFIX_USAGE);
    return;
  }

  const parsed = parsePrefixArgs(body);
  if (typeof parsed === 'string') { await message.reply(parsed); return; }

  const att = await resolveAttachment(message);
  if (!att) {
    await message.reply(
      `❌ No audio/video file found. Attach one, reply to one, or have one in recent channel history.\n\n${PREFIX_USAGE}`,
    );
    return;
  }

  const ext = (att.name?.split('.').pop() ?? '').toLowerCase();
  if (IMAGE_EXTENSIONS.has(ext)) {
    await message.reply('❌ Image files are not accepted — attach an audio or video file.');
    return;
  }
  if (!ACCEPTED_EXTENSIONS.has(ext)) {
    await message.reply(`❌ Unsupported file type \`.${ext}\`. Accepted: \`${[...ACCEPTED_EXTENSIONS].join(', ')}\`.`);
    return;
  }

  const volDesc = parsed.volume !== 1 ? `, vol ×${parsed.volume}` : '';
  const status = await message.reply(
    `⏳ IHTX-Sap — **${parsed.pitches.length}** layer${parsed.pitches.length > 1 ? 's' : ''}, ` +
    `**${parsed.repetitions}×** loop, ratio **×${parsed.duration}**, **${styleLabel(parsed.style)}**${volDesc}`,
  );

  let last = '';
  const setStatus = async (s: string) => {
    if (s === last) return; last = s;
    try { await status.edit(s); } catch { /* ignore */ }
  };

  const tmpDir = makeTempDir('ihtxsap');
  try {
    const result = await runSap(parsed, att.url, ext, tmpDir, setStatus, message.guild);
    if (!result) return;

    if (!fs.existsSync(result)) { await setStatus('❌ Output file was not created.'); return; }
    const size  = fs.statSync(result).size;
    const limit = getUploadLimitBytes(message.guild);
    if (size > limit) {
      await setStatus(`❌ Output (${formatBytes(size)}) exceeds upload limit (${formatBytes(limit)}).`);
      return;
    }

    await status.edit({
      content:  `✅ IHTX-Sap done! ${summaryLine(parsed)}`,
      files:    [{ attachment: result, name: 'ihtxsap.mp3' }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await setStatus(msg.includes('timed out') ? '❌ Processing timed out.' : `❌ Error: ${msg.slice(0, 300)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}

// ── Slash entry point ────────────────────────────────────────────────────────

export async function handleIhtxSapInteraction(slash: ChatInputCommandInteraction): Promise<void> {
  await slash.deferReply();

  const attachment = slash.options.getAttachment('file', true);
  const duration   = slash.options.getNumber('duration', true);
  const reps       = slash.options.getInteger('repetitions') ?? 5;
  const pitchStr   = slash.options.getString('pitches', true);
  const styleRaw   = (slash.options.getString('style') ?? 'rubberband_r2') as StyleValue;

  const ext = (attachment.name?.split('.').pop() ?? '').toLowerCase();
  if (IMAGE_EXTENSIONS.has(ext)) {
    await slash.editReply('❌ Image files are not accepted — attach an audio or video file.');
    return;
  }
  if (!ACCEPTED_EXTENSIONS.has(ext)) {
    await slash.editReply(
      `❌ Unsupported file type \`.${ext}\`. Accepted: \`${[...ACCEPTED_EXTENSIONS].join(', ')}\`.`,
    );
    return;
  }

  // Slash mode: pitches are space-separated
  const pitches = pitchStr.trim().split(/\s+/).map(Number);
  if (pitches.some(isNaN) || pitches.length < 1) {
    await slash.editReply('❌ `pitches` must be space-separated numbers, e.g. `1 2 3` or `-7 5 6`.');
    return;
  }
  if (pitches.some((p) => Math.abs(p) > 120)) {
    await slash.editReply('❌ Pitch shifts must be within ±120 semitones.');
    return;
  }
  if (duration < 0.01 || duration > 3600) {
    await slash.editReply('❌ `duration` must be between 0.01 and 3600 seconds.');
    return;
  }
  if (reps < 1 || reps > 100) {
    await slash.editReply('❌ `repetitions` must be between 1 and 100.');
    return;
  }

  const volumeRaw = slash.options.getNumber('volume') ?? 1;
  if (volumeRaw <= 0 || volumeRaw > 100) {
    await slash.editReply('❌ `volume` must be a positive number ≤ 100.');
    return;
  }

  const opts: SapOpts = { duration, repetitions: reps, pitches, style: styleRaw, volume: volumeRaw };

  const setStatus = async (s: string) => {
    try { await slash.editReply(s); } catch { /* ignore */ }
  };

  const volDesc = volumeRaw !== 1 ? `, vol ×${volumeRaw}` : '';
  await setStatus(
    `⏳ IHTX-Sap — **${pitches.length}** layer${pitches.length > 1 ? 's' : ''}, ` +
    `**${reps}×** loop, ratio **×${duration}**, **${styleLabel(styleRaw)}**${volDesc}`,
  );

  const tmpDir = makeTempDir('ihtxsap');
  try {
    const result = await runSap(opts, attachment.url, ext, tmpDir, setStatus, slash.guild);
    if (!result) return;

    if (!fs.existsSync(result)) { await setStatus('❌ Output file was not created.'); return; }
    const size  = fs.statSync(result).size;
    const limit = getUploadLimitBytes(slash.guild);
    if (size > limit) {
      await setStatus(`❌ Output (${formatBytes(size)}) exceeds upload limit (${formatBytes(limit)}).`);
      return;
    }

    await slash.editReply({
      content: `✅ IHTX-Sap done! ${summaryLine(opts)}`,
      files:   [{ attachment: result, name: 'ihtxsap.mp3' }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await setStatus(msg.includes('timed out') ? '❌ Processing timed out.' : `❌ Error: ${msg.slice(0, 300)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}
