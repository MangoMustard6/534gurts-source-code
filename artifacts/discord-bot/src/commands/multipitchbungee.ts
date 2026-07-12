/**
 * multipitchbungee.ts — th/multipitch_bungee (mpb)
 *
 * Port of the standalone bungee pitch-shifter pipeline:
 *   1. Transcode input to FFV1/PCM_S16LE temp video
 *   2. Extract audio shifted down one octave via asetrate=sr/2
 *   3. Run the cached `multipitch` binary with --bungee --no-normalize
 *   4. Mux processed audio back onto the original video stream
 *
 * Prefix: th/multipitch_bungee [pitch]  (alias: mpb)
 * Default pitch: 1.5
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
const SAMPLE_RATE = 44100;

const IMAGE_EXTENSIONS = new Set([
  'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'svg', 'ico', 'avif', 'heic',
]);

const ACCEPTED_EXTENSIONS = new Set([
  'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'opus', 'wma', 'aiff', 'aif',
  'mp4', 'mov', 'mkv', 'webm', 'avi', 'mts', 'm2ts',
]);

export const PREFIX_USAGE = [
  '**Usage:** `th/multipitch_bungee [pitch]`  — alias: `mpb`',
  '',
  '  `pitch` — pitch factor passed to the bungee processor (default: `1.5`)',
  '',
  '**Example:** `th/multipitch_bungee 2.0`',
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
  pitch: string,
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

  // 2. Transcode to FFV1/PCM_S16LE temp video (mirrors the original script)
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

  // 3. Extract audio with sample rate halved (asetrate=sr/2)
  await setStatus('⏳ Extracting audio with octave-down sample rate…');
  const halfWav = path.join(tmpDir, 'half.wav');
  const extract = await spawnAsync('ffmpeg', [
    '-y', '-i', tempVideo,
    '-af', `asetrate=${SAMPLE_RATE / 2}`,
    '-c:a', 'pcm_s16le',
    halfWav,
  ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
  if (extract.code !== 0) {
    await setStatus(`❌ Audio extraction failed.\n\`\`\`\n${extract.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 4. Run the bungee pitch processor
  await setStatus(`⏳ Running bungee pitch processor (pitch ${pitch})…`);
  const outWav = path.join(tmpDir, 'out.wav');
  const bungee = await spawnAsync(MULTIPITCH_BIN, [
    halfWav, outWav, pitch, '--bungee', '--no-normalize',
  ], { timeout: PROCESS_TIMEOUTS.RUBBERBAND_MS });
  if (bungee.code !== 0) {
    await setStatus(`❌ Bungee processor failed.\n\`\`\`\n${bungee.stderr.slice(-400)}\n\`\`\``);
    return null;
  }

  // 5. Mux processed audio back onto the original video stream, encode to MP4
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

  const pitch = body ? body.split(/\s+/)[0].trim() : '1.5';
  if (body && isNaN(Number(pitch))) {
    await message.reply(`❌ Pitch must be a number.\n\n${PREFIX_USAGE}`);
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

  const status = await message.reply(
    `⏳ Multipitch Bungee — pitch **${pitch}**`,
  );

  let last = '';
  const setStatus = async (s: string) => {
    if (s === last) return; last = s;
    try { await status.edit(s); } catch { /* ignore */ }
  };

  const tmpDir = makeTempDir('mpb');
  try {
    const result = await runBungee(pitch, att.url, ext, tmpDir, setStatus, message.guild);
    if (!result) return;

    if (!fs.existsSync(result)) { await setStatus('❌ Output file was not created.'); return; }
    const size = fs.statSync(result).size;
    const limit = getUploadLimitBytes(message.guild);
    if (size > limit) {
      await setStatus(`❌ Output (${formatBytes(size)}) exceeds upload limit (${formatBytes(limit)}).`);
      return;
    }

    await status.edit({
      content: `✅ Multipitch Bungee done! pitch **${pitch}**`,
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
  const pitch = String(slash.options.getNumber('pitch') ?? 1.5);

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

  await setStatus(`⏳ Multipitch Bungee — pitch **${pitch}**`);

  const tmpDir = makeTempDir('mpb');
  try {
    const result = await runBungee(pitch, attachment.url, ext, tmpDir, setStatus, slash.guild);
    if (!result) return;

    if (!fs.existsSync(result)) { await setStatus('❌ Output file was not created.'); return; }
    const size = fs.statSync(result).size;
    const limit = getUploadLimitBytes(slash.guild);
    if (size > limit) {
      await setStatus(`❌ Output (${formatBytes(size)}) exceeds upload limit (${formatBytes(limit)}).`);
      return;
    }

    await slash.editReply({
      content: `✅ Multipitch Bungee done! pitch **${pitch}**`,
      files: [{ attachment: result, name: 'multipitch_bungee.mp4' }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await setStatus(msg.includes('timed out') ? '❌ Processing timed out.' : `❌ Error: ${msg.slice(0, 300)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}
