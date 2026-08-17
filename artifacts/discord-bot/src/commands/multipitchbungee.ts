/**
 * multipitchbungee.ts — th/multipitch_bungee (mpb)
 *
 * Port of the standalone bungee pitch-shifter pipeline:
 *   1. Transcode input to FFV1/PCM_S16LE temp video
 *   2. Probe actual audio sample rate; extract audio at sr/2 via asetrate
 *   3. Run the cached `multipitch` binary with <pitches> --bungee --no-normalize
 *   4. Mux processed audio back onto the original video stream
 *
 * Prefix: th/multipitch_bungee [-7|7]  (alias: mpb)
 * Pitches: pipe/semicolon/comma/space separated semitone values (default: 1.5)
 */

import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { Message, ChatInputCommandInteraction, Guild } from 'discord.js';
import { spawnAsync } from '../utils/spawn.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { PROCESS_TIMEOUTS } from '../config.js';

// ── Constants ──────────────────────────────────────────────────────────────────

const MULTIPITCH_BIN = path.resolve(process.cwd(), '../../bot/multipitch');
const MULTIPITCH_URL = 'https://file.garden/aTXso15ukD3mnuPI/multipitch';
const FALLBACK_SAMPLE_RATE = 44100;

const IMAGE_EXTENSIONS = new Set([
  'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'svg', 'ico', 'avif', 'heic',
]);

const ACCEPTED_EXTENSIONS = new Set([
  'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'opus', 'wma', 'aiff', 'aif',
  'mp4', 'mov', 'mkv', 'webm', 'avi', 'mts', 'm2ts',
]);

export const PREFIX_USAGE = [
  '**Usage:** `th/multipitch_bungee [pitches]`  — alias: `mpb`',
  '',
  '  `pitches` — pipe/semicolon/comma-separated semitone values (default: `1.5`)',
  '',
  '**Examples:**',
  '  `th/mpb -7|7` — two-voice bungee at −7 and +7 semitones',
  '  `th/mpb 1.5` — single voice at +1.5 semitones',
  'Attach a video or audio file, reply to one, or have one in recent channel history.',
].join('\n');

// ── Binary setup ─────────────────────────────────────────────────────────────

async function ensureMultipitchBinary(): Promise<boolean> {
  if (fs.existsSync(MULTIPITCH_BIN)) return true;
  try {
    const binDir = path.dirname(MULTIPITCH_BIN);
    fs.mkdirSync(binDir, { recursive: true });
    await downloadUrl(MULTIPITCH_URL, MULTIPITCH_BIN);
    try { execFileSync('chmod', ['+x', MULTIPITCH_BIN]); } catch { /* ignore */ }
    return fs.existsSync(MULTIPITCH_BIN);
  } catch (err) {
    console.error('[mpb] failed to download multipitch binary:', err);
    return false;
  }
}

// ── Sample rate probe ────────────────────────────────────────────────────────

async function getAudioSampleRate(filePath: string): Promise<number> {
  const probe = await spawnAsync('ffprobe', [
    '-v', 'quiet',
    '-print_format', 'json',
    '-show_streams',
    filePath,
  ], { timeout: 30_000 });
  if (probe.code !== 0) return FALLBACK_SAMPLE_RATE;
  try {
    const data = JSON.parse(probe.stdout) as { streams?: Array<{ codec_type?: string; sample_rate?: string }> };
    const audio = data.streams?.find((s) => s.codec_type === 'audio');
    const sr = audio?.sample_rate ? parseInt(audio.sample_rate, 10) : NaN;
    return isNaN(sr) || sr <= 0 ? FALLBACK_SAMPLE_RATE : sr;
  } catch {
    return FALLBACK_SAMPLE_RATE;
  }
}

// ── Pitch parsing ─────────────────────────────────────────────────────────────

function parsePitches(raw: string): string | null {
  const values = raw.trim().split(/[|;,\s]+/).map((v) => v.trim()).filter(Boolean);
  if (!values.length) return null;
  for (const v of values) {
    if (isNaN(Number(v))) return null;
  }
  return values.join(',');
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

// ── Core pipeline ────────────────────────────────────────────────────────────

async function runBungee(
  pitchArg: string,
  fileUrl: string,
  fileExt: string,
  tmpDir: string,
  setStatus: (s: string) => Promise<void>,
  guild: Guild | null,
): Promise<string | null> {
  const binaryOk = await ensureMultipitchBinary();
  if (!binaryOk) {
    await setStatus('❌ Could not download the `multipitch` bungee binary. Try again later.');
    return null;
  }

  // 1. Download input
  await setStatus('⏳ Downloading input file…');
  const inputRaw = path.join(tmpDir, `input.${fileExt}`);
  await downloadUrl(fileUrl, inputRaw);

  // 2. Transcode to FFV1/PCM_S16LE temp video
  await setStatus('⏳ Transcoding to FFV1/PCM temp…');
  const tempVideo = path.join(tmpDir, 'temp.mp4');
  const transcode = await spawnAsync('ffmpeg', [
    '-y', '-i', inputRaw,
    '-f', 'mp4', '-preset', 'ultrafast',
    '-c:v', 'ffv1', '-c:a', 'pcm_s16le',
    tempVideo,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (transcode.code !== 0) {
    await setStatus(`❌ Transcode failed.\n\`\`\`\n${transcode.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 3. Probe actual audio sample rate, then extract at sr/2
  await setStatus('⏳ Probing sample rate and extracting audio…');
  const sr = await getAudioSampleRate(tempVideo);
  const halfRate = Math.floor(sr / 2);
  const halfWav = path.join(tmpDir, 'half.wav');
  const extract = await spawnAsync('ffmpeg', [
    '-y', '-i', tempVideo,
    '-af', `asetrate=${halfRate}`,
    '-c:a', 'pcm_s16le',
    halfWav,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (extract.code !== 0) {
    await setStatus(`❌ Audio extraction failed.\n\`\`\`\n${extract.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 4. Run the bungee pitch processor
  await setStatus(`⏳ Running bungee pitch processor (pitches: ${pitchArg})…`);
  const outWav = path.join(tmpDir, 'out.wav');
  const bungee = await spawnAsync(MULTIPITCH_BIN, [
    halfWav, outWav, pitchArg, '--bungee', '--no-normalize',
  ], { timeout: PROCESS_TIMEOUTS.RUBBERBAND_MS });
  if (bungee.code !== 0) {
    await setStatus(`❌ Bungee processor failed.\n\`\`\`\n${bungee.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 5. Mux processed audio back onto the original video stream
  await setStatus('⏳ Muxing final output…');
  const outputMp4 = path.join(tmpDir, 'multipitch_bungee.mp4');
  const mux = await spawnAsync('ffmpeg', [
    '-y', '-i', tempVideo, '-i', outWav,
    '-map', '0:v', '-map', '1:a',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-c:a', 'aac', '-b:a', '192k',
    '-pix_fmt', 'yuv420p',
    outputMp4,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (mux.code !== 0) {
    await setStatus(`❌ Mux failed.\n\`\`\`\n${mux.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  return outputMp4;
}

// ── Prefix entry point ───────────────────────────────────────────────────────

export async function handleMultipitchBungee(message: Message): Promise<void> {
  const content = message.content;
  const lower = content.toLowerCase();
  let cmdEnd = lower.indexOf('multipitch_bungee');
  if (cmdEnd === -1) cmdEnd = lower.indexOf('mpb');
  const body = content.slice(cmdEnd + (lower.indexOf('multipitch_bungee') === cmdEnd ? 'multipitch_bungee'.length : 'mpb'.length)).trim();

  const rawPitches = body.split(/\s+/)[0]?.trim() || '1.5';
  const pitchArg = parsePitches(rawPitches);
  if (!pitchArg) {
    await message.reply(`❌ Invalid pitch values — use pipe/semicolon/comma separated numbers, e.g. \`-7|7\`.\n\n${PREFIX_USAGE}`);
    return;
  }

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

  const status = await message.reply(`🔧 Executing Bungee multipitch-processing code — pitches: **${pitchArg.replace(/,/g, ' | ')}**`);

  let last = '';
  const setStatus = async (s: string) => {
    if (s === last) return; last = s;
    try { await status.edit(s); } catch { /* ignore */ }
  };

  const tmpDir = makeTempDir('mpb');
  try {
    const result = await runBungee(pitchArg, att.url, ext, tmpDir, setStatus, message.guild);
    if (!result) return;

    if (!fs.existsSync(result)) { await setStatus('❌ Output file was not created.'); return; }
    const size = fs.statSync(result).size;
    const limit = getUploadLimitBytes(message.guild);
    if (size > limit) {
      await setStatus(`❌ Output (${formatBytes(size)}) exceeds upload limit (${formatBytes(limit)}).`);
      return;
    }

    await status.edit({
      content: `✅ Multipitch Bungee done! pitches: **${pitchArg.replace(/,/g, ' | ')}**`,
      files: [{ attachment: result, name: 'multipitch_bungee.mp4' }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await setStatus(msg.includes('timed out') ? '❌ Processing timed out.' : `❌ Error: ${msg.slice(0, 300)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}

// ── Slash entry point ────────────────────────────────────────────────────────

export async function handleMultipitchBungeeInteraction(slash: ChatInputCommandInteraction): Promise<void> {
  await slash.deferReply();

  const attachment = slash.options.getAttachment('file', true);
  const rawPitches = slash.options.getString('pitches') ?? '1.5';
  const pitchArg = parsePitches(rawPitches);
  if (!pitchArg) {
    await slash.editReply(`❌ Invalid pitch values — use pipe/semicolon/comma separated numbers, e.g. \`-7|7\`.`);
    return;
  }

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

  const setStatus = async (s: string) => {
    try { await slash.editReply(s); } catch { /* ignore */ }
  };

  await setStatus(`🔧 Executing Bungee multipitch-processing code — pitches: **${pitchArg.replace(/,/g, ' | ')}**`);

  const tmpDir = makeTempDir('mpb');
  try {
    const result = await runBungee(pitchArg, attachment.url, ext, tmpDir, setStatus, slash.guild);
    if (!result) return;

    if (!fs.existsSync(result)) { await setStatus('❌ Output file was not created.'); return; }
    const size = fs.statSync(result).size;
    const limit = getUploadLimitBytes(slash.guild);
    if (size > limit) {
      await setStatus(`❌ Output (${formatBytes(size)}) exceeds upload limit (${formatBytes(limit)}).`);
      return;
    }

    await slash.editReply({
      content: `✅ Multipitch Bungee done! pitches: **${pitchArg.replace(/,/g, ' | ')}**`,
      files: [{ attachment: result, name: 'multipitch_bungee.mp4' }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await setStatus(msg.includes('timed out') ? '❌ Processing timed out.' : `❌ Error: ${msg.slice(0, 300)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}
