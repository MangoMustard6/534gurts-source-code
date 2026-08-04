/**
 * repeat.ts — th/repeat [n]
 * Repeats a video, GIF, or audio file N times using FFmpeg concat demuxer.
 */
import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import { spawnAsync } from '../utils/spawn.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { resolveAttachment, SUPPORTED_VIDEO_EXTS } from './gradientmap.js';

const MAX_REPEATS = 10;
const SUPPORTED_AUDIO_EXTS = new Set(['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac']);

const USAGE =
  `**Usage:** \`th/repeat [n]\` — attach or reply-to a video, GIF, or audio file\n` +
  `Repeats the media **n** times (default: 2, max: ${MAX_REPEATS}).\n` +
  `**Examples:** \`th/repeat\`  \`th/repeat 3\`  \`th/repeat 5\``;

export async function handleRepeat(message: Message, rest: string): Promise<void> {
  const n = Math.max(1, Math.min(MAX_REPEATS, parseInt(rest.trim()) || 2));

  const attachmentInfo = await resolveAttachment(message);
  if (!attachmentInfo) {
    await message.reply(`❌ Attach a video, GIF, or audio file to use \`th/repeat\`.\n${USAGE}`);
    return;
  }

  const { url, name, ext } = attachmentInfo;
  const isVideo = SUPPORTED_VIDEO_EXTS.has(ext);
  const isAudio = SUPPORTED_AUDIO_EXTS.has(ext);

  if (!isVideo && !isAudio) {
    await message.reply(
      `❌ Unsupported file type \`.${ext}\`. Attach a video, GIF, or audio file.\n${USAGE}`,
    );
    return;
  }

  const status = await message.reply(`🔧 Executing FFmpeg repeat/concat code (${n}×)…`);
  const tmpDir = makeTempDir('repeat');
  const startTime = Date.now();

  try {
    const inputPath = path.join(tmpDir, `input.${ext}`);
    const baseName = path.parse(name).name.replace(/\.[^.]+$/, '');
    const outExt = isAudio ? ext : 'mp4';
    const outputPath = path.join(tmpDir, `repeat_${baseName}.${outExt}`);

    await downloadUrl(url, inputPath);

    // Build concat list — escape single quotes in the path
    const safePath = inputPath.replace(/\\/g, '/').replace(/'/g, "'\\''");
    const concatLines = Array.from({ length: n }, () => `file '${safePath}'`).join('\n');
    const concatListPath = path.join(tmpDir, 'concat.txt');
    fs.writeFileSync(concatListPath, concatLines + '\n');

    await spawnAsync('ffmpeg', [
      '-y',
      '-f', 'concat', '-safe', '0',
      '-i', concatListPath,
      '-c', 'copy',
      outputPath,
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);

    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit('❌ Repeat produced no output.');
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    if (outSize > uploadLimit) {
      await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(
          `✅ Repeated ${n}× done! (${elapsed}s)\n-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`,
        );
      } else {
        await status.edit(`❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
      }
      return;
    }

    await status.edit({
      content: `✅ Repeated ${n}×!\n-# Took ${elapsed} seconds.`,
      files: [{ attachment: outputPath, name: path.basename(outputPath) }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
    if (msg.includes('timed out')) {
      await status.edit(`❌ Processing timed out after ${elapsed}s.`);
    } else {
      await status.edit(`❌ \`${msg.slice(0, 300)}\`\n-# Took ${elapsed}s.`);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}
