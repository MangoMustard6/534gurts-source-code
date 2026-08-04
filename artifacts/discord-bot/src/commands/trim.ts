import { Message } from 'discord.js';
import path from 'node:path';
import fs from 'node:fs';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import { spawnAsync } from '../utils/spawn.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { resolveAttachment, SUPPORTED_VIDEO_EXTS } from './gradientmap.js';

const AUDIO_EXTS = new Set(['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac']);
const USAGE =
  '**Usage:** `th/trim [start] [end]` — attach or reply-to media\n' +
  'Defaults to `0` → the media length. One value means `start` → the media length.\n' +
  '**Examples:** `th/trim` · `th/trim 5` · `th/trim 5 15`';

function parseTimestamp(value: string): number {
  const parts = value.trim().split(':');
  const numbers = parts.map(Number);
  if (numbers.some((n) => !Number.isFinite(n)) || parts.length > 3) {
    throw new Error('invalid timestamp format');
  }
  if (parts.length === 1) return numbers[0]!;
  if (parts.length === 2) return numbers[0]! * 60 + numbers[1]!;
  return numbers[0]! * 3600 + numbers[1]! * 60 + numbers[2]!;
}

async function probeDuration(file: string): Promise<number> {
  const result = await spawnAsync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration',
    '-of', 'default=nw=1:nk=1', file,
  ], { timeout: 10_000 });
  const duration = Number(result.stdout.trim());
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('could not read media duration');
  return duration;
}

export async function handleTrim(message: Message, rest: string): Promise<void> {
  const args = rest.trim().split(/\s+/).filter(Boolean);
  if (args.length > 2) {
    await message.reply(USAGE);
    return;
  }
  let start = 0;
  let end: number | undefined;
  try {
    if (args[0]) start = parseTimestamp(args[0]);
    if (args[1]) end = parseTimestamp(args[1]);
  } catch {
    await message.reply(`❌ Invalid timestamp format.\n${USAGE}`);
    return;
  }
  if (start < 0 || (end !== undefined && end < 0)) {
    await message.reply(`❌ Timestamps cannot be negative.\n${USAGE}`);
    return;
  }

  const source = await resolveAttachment(message);
  if (!source) {
    await message.reply(`❌ Attach or reply to a video, GIF, or audio file.\n${USAGE}`);
    return;
  }
  const isAudio = AUDIO_EXTS.has(source.ext);
  const isVideo = SUPPORTED_VIDEO_EXTS.has(source.ext);
  if (!isAudio && !isVideo) {
    await message.reply(`❌ Unsupported file type \`.${source.ext}\`.\n${USAGE}`);
    return;
  }

  const status = await message.reply('🔧 Executing FFmpeg trim-filter code…');
  const tmpDir = makeTempDir('trim');
  try {
    const input = path.join(tmpDir, `input.${source.ext}`);
    await downloadUrl(source.url, input);
    const duration = await probeDuration(input);
    end ??= duration;
    if (start >= end) throw new Error('start time must be less than end time');
    if (end > duration + 0.001) throw new Error(`end time exceeds media duration (${duration.toFixed(3)}s)`);

    const outputExt = isAudio ? source.ext : 'mp4';
    const output = path.join(tmpDir, `trimmed.${outputExt}`);
    const trimDuration = end - start;
    const ffmpegArgs = isAudio
      ? ['-y', '-ss', String(start), '-i', input, '-t', String(trimDuration), '-c', 'copy', output]
      : [
        '-y', '-ss', String(start), '-i', input, '-t', String(trimDuration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', output,
      ];
    await spawnAsync('ffmpeg', ffmpegArgs, { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });
    if (!fs.existsSync(output) || fs.statSync(output).size === 0) throw new Error('trim produced no output');

    const size = fs.statSync(output).size;
    const limit = getUploadLimitBytes(message.guild ?? null);
    if (size > limit) {
      const url = await _upload_to_catbox(output);
      if (!url) throw new Error(`output is too large (${formatBytes(size)}) and Catbox upload failed`);
      await status.edit(`✅ Trimmed \`${start}s\` → \`${end}s\`.\n${url}`);
      return;
    }
    await status.edit({
      content: `✅ Trimmed \`${start}s\` → \`${end}s\``,
      files: [{ attachment: output, name: `trimmed_${start}-${end}.${outputExt}` }],
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    await status.edit(`❌ ${detail.slice(0, 500)}`);
  } finally {
    cleanupDir(tmpDir);
  }
}