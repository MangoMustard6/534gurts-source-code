/**
 * multipitch2.ts — External-binary pitch shifter (signalsmith backend)
 *
 * Downloads the `multipitch` binary from file.garden, runs it against the
 * attached video/audio file, and remuxes the result with an optional
 * Wave Hammer limiter filter.
 *
 * Command syntax (prefix):
 *   th/multipitch2 <pitch1>|<pitch2>|...[||<wave-hammer-type>] [sr=<rate>]
 *
 * Wave hammer types: G-Major_17 | Evil_Rampaging_Sorcerer
 *
 * Examples:
 *   th/multipitch2 7|8|9
 *   th/multipitch2 7|8|9||G-Major_17
 *   th/multipitch2 -3|0|4||Evil_Rampaging_Sorcerer sr=48000
 */

import { Message, AttachmentBuilder } from 'discord.js';
import fs from 'fs';
import path from 'path';
import { spawnAsync } from '../utils/spawn.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { VIDEO_EXTENSIONS, PROCESS_TIMEOUTS } from '../config.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';

// ── Constants ────────────────────────────────────────────────────────────────

const BINARY_URL = 'https://file.garden/aTXso15ukD3mnuPI/multipitch';
const DEFAULT_SR  = 44100;
const MAX_PITCH_VALUES = 100;

type WaveHammer = 'G-Major_17' | 'Evil_Rampaging_Sorcerer';
const WAVE_HAMMERS: ReadonlySet<string> = new Set<WaveHammer>(['G-Major_17', 'Evil_Rampaging_Sorcerer']);

// ── Usage string ─────────────────────────────────────────────────────────────

const USAGE = [
  '**Usage:** `th/multipitch2 <pitches> [||<wave-hammer>] [sr=<rate>]` — attach a video/audio file',
  '',
  '**Pitches** (pipe-separated integers, e.g. `7|8|9` or `-3|0|4`)',
  '',
  '**Wave hammer types (optional):**',
  '`G-Major_17` — light limiting (alimiter=15)',
  '`Evil_Rampaging_Sorcerer` — heavy limiting (alimiter=30)',
  '',
  '**Sample rate (optional):**',
  '`sr=44100` — processing sample rate (default: 44100)',
  '',
  '**Examples:**',
  '`th/multipitch2 7|8|9`',
  '`th/multipitch2 7|8|9||G-Major_17`',
  '`th/multipitch2 -3|0|4||Evil_Rampaging_Sorcerer sr=48000`',
].join('\n');

// ── Argument parser ───────────────────────────────────────────────────────────

interface Opts {
  pitches: string;      // comma-separated for binary, e.g. "7,8,9"
  waveHammer: WaveHammer | null;
  sr: number;
}

function parseArgs(raw: string): Opts | string {
  // Split on || to separate pitches from optional wave hammer
  const [pitchPart, hammerPart] = raw.split('||').map((s) => s.trim());

  if (!pitchPart) return `❌ No pitches provided.\n${USAGE}`;

  // Extract sr=N from pitchPart tokens (anything that looks like sr=N)
  const tokens = pitchPart.split(/\s+/);
  let pitchToken = '';
  let sr = DEFAULT_SR;

  for (const tok of tokens) {
    if (/^sr=\d+$/i.test(tok)) {
      const n = parseInt(tok.slice(3), 10);
      if (isNaN(n) || n < 8000 || n > 384000)
        return `❌ \`sr\` must be between 8000 and 384000.`;
      sr = n;
    } else if (!pitchToken) {
      pitchToken = tok;
    } else {
      return `❌ Unexpected token \`${tok}\`.\n${USAGE}`;
    }
  }

  if (!pitchToken) return `❌ No pitches provided.\n${USAGE}`;

  // Validate each pitch value is a number
  const pitchValues = pitchToken.split('|');
  if (pitchValues.length === 0 || pitchValues.some((p) => p.trim() === ''))
    return `❌ Empty pitch value in \`${pitchToken}\`.`;
  if (pitchValues.length > MAX_PITCH_VALUES)
    return `❌ Too many pitch values (maximum: ${MAX_PITCH_VALUES}). Got ${pitchValues.length}.`;
  if (pitchValues.some((p) => isNaN(Number(p.trim()))))
    return `❌ All pitches must be numbers. Got: \`${pitchToken}\``;

  // Convert pipes to commas for the binary
  const pitches = pitchValues.map((p) => p.trim()).join(',');

  // Validate wave hammer
  let waveHammer: WaveHammer | null = null;
  if (hammerPart) {
    if (!WAVE_HAMMERS.has(hammerPart))
      return `❌ Unknown wave hammer \`${hammerPart}\`. Valid options: \`G-Major_17\`, \`Evil_Rampaging_Sorcerer\`.`;
    waveHammer = hammerPart as WaveHammer;
  }

  return { pitches, waveHammer, sr };
}

// ── Attachment resolver ───────────────────────────────────────────────────────

async function resolveAttachment(message: Message): Promise<{ url: string; name: string; ext: string } | null> {
  const direct = message.attachments.first();
  if (direct) return { url: direct.url, name: direct.name, ext: (direct.name?.split('.').pop() ?? '').toLowerCase() };
  if (message.reference?.messageId) {
    try {
      const ref = await message.fetchReference();
      const a = ref.attachments.first();
      if (a) return { url: a.url, name: a.name, ext: (a.name?.split('.').pop() ?? '').toLowerCase() };
    } catch { /* ignored */ }
  }
  return null;
}

// ── Build the FFmpeg audio filter ─────────────────────────────────────────────

function buildAudioFilter(sr: number, waveHammer: WaveHammer | null): string {
  let filter = `asetrate=${sr}`;
  if (waveHammer === 'Evil_Rampaging_Sorcerer') filter += ',alimiter=30:latency=1';
  else if (waveHammer === 'G-Major_17')          filter += ',alimiter=15:latency=1';
  return filter;
}

// ── Main handler ──────────────────────────────────────────────────────────────

export async function handleMultipitch2(message: Message, rawArgs: string): Promise<void> {
  if (!rawArgs.trim()) {
    await message.reply(USAGE);
    return;
  }

  const parsed = parseArgs(rawArgs.trim());
  if (typeof parsed === 'string') {
    await message.reply(parsed);
    return;
  }

  const attachmentInfo = await resolveAttachment(message);
  if (!attachmentInfo) {
    await message.reply(`❌ No video/audio attachment found. Attach a file or reply to a message with one.\n${USAGE}`);
    return;
  }

  const { url: attachmentUrl, ext } = attachmentInfo;
  if (!VIDEO_EXTENSIONS.has(ext)) {
    await message.reply(`❌ Unsupported file type \`.${ext}\`. Supported: \`${[...VIDEO_EXTENSIONS].join(', ')}\`.`);
    return;
  }

  const { pitches, waveHammer, sr } = parsed;
  const hammerLabel = waveHammer ? ` + ${waveHammer}` : '';
  const status = await message.reply(`🔧 Executing multipitch2 pitch-processing code — pitches: \`${pitches}\`${hammerLabel} (sr=${sr})…`);

  const edit = async (msg: string) => { try { await status.edit(msg); } catch { /* ignored */ } };

  const tmpDir = makeTempDir('mp2');

  try {
    // ── 1. Download attachment ────────────────────────────────────────────────
    await edit('⏳ Downloading attachment…');
    const inputPath = path.join(tmpDir, `input.${ext}`);
    await downloadUrl(attachmentUrl, inputPath);

    // ── 2. Convert input to lossless intermediate ─────────────────────────────
    await edit('⏳ Converting to lossless intermediate…');
    const intermediatePath = path.join(tmpDir, 'intermediate.mp4');

    const convertResult = await spawnAsync('ffmpeg', [
      '-y', '-i', inputPath,
      '-c:v', 'copy',
      '-c:a', 'pcm_s16le',
      intermediatePath,
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    if (convertResult.code !== 0) {
      await edit(`❌ Conversion failed.\n\`\`\`\n${convertResult.stderr.slice(-400)}\n\`\`\``);
      return;
    }

    // ── 3. Download the multipitch binary ─────────────────────────────────────
    await edit('⏳ Fetching pitch-shifter binary…');
    const binaryPath = path.join(tmpDir, 'multipitch');
    await downloadUrl(BINARY_URL, binaryPath);
    fs.chmodSync(binaryPath, 0o755);

    // ── 4. Downsample audio for binary input ──────────────────────────────────
    await edit('⏳ Preparing audio (downsample)…');
    const halfRateWav = path.join(tmpDir, 'halfrate.wav');

    const downsampleResult = await spawnAsync('ffmpeg', [
      '-y', '-i', intermediatePath,
      '-af', `asetrate=${sr / 2}`,
      '-c:a', 'pcm_s16le',
      halfRateWav,
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    if (downsampleResult.code !== 0) {
      await edit(`❌ Downsample failed.\n\`\`\`\n${downsampleResult.stderr.slice(-400)}\n\`\`\``);
      return;
    }

    // ── 5. Run multipitch binary ──────────────────────────────────────────────
    await edit(`⏳ Running pitch shifter — \`${pitches}\`…`);
    const shiftedWav = path.join(tmpDir, 'shifted.wav');

    const shiftResult = await spawnAsync(binaryPath, [
      halfRateWav, shiftedWav, pitches,
      '--backend', 'signalsmith',
      '--no-normalize',
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    if (shiftResult.code !== 0) {
      await edit(`❌ Pitch shift failed.\n\`\`\`\n${shiftResult.stderr.slice(-400)}\n\`\`\``);
      return;
    }

    if (!fs.existsSync(shiftedWav)) {
      await edit('❌ Pitch shifter produced no output.');
      return;
    }

    // ── 6. Remux: original video + shifted audio ──────────────────────────────
    await edit('⏳ Remuxing video + shifted audio…');
    const outputPath = path.join(tmpDir, 'output.mp4');
    const audioFilter = buildAudioFilter(sr, waveHammer);

    const remuxArgs = [
      '-y',
      '-i', intermediatePath,
      '-i', shiftedWav,
      '-map', '0:v?',          // video track if present (optional)
      '-map', '1:a',
      '-af', audioFilter,
      '-c:v', 'copy',
      '-c:a', 'aac', '-b:a', '192k',
      outputPath,
    ];

    const remuxResult = await spawnAsync('ffmpeg', remuxArgs, { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    if (remuxResult.code !== 0) {
      await edit(`❌ Remux failed.\n\`\`\`\n${remuxResult.stderr.slice(-400)}\n\`\`\``);
      return;
    }

    if (!fs.existsSync(outputPath)) {
      await edit('❌ Output file was not created.');
      return;
    }

    // ── 7. Upload ─────────────────────────────────────────────────────────────
    const outputSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    if (outputSize > uploadLimit) {
      await edit(`❌ Output (${formatBytes(outputSize)}) exceeds upload limit (${formatBytes(uploadLimit)}).`);
      return;
    }

    const pitchDisplay = pitches.replace(/,/g, '|');
    await status.edit({
      content: `✅ Done! pitches: \`${pitchDisplay}\`${hammerLabel}`,
      files: [new AttachmentBuilder(outputPath, { name: 'multipitch2.mp4' })],
    });

  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await edit(msg.includes('timed out') ? '❌ Processing timed out.' : `❌ Error: ${msg.slice(0, 300)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}
