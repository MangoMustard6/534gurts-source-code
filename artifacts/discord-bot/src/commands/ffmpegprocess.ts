import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { spawnAsync } from '../utils/spawn.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const USAGE =
  '**Usage:** `t!ffmpegprocess <ffmpeg args>` *(alias: fmp)*  — attach or reply-to a file\n' +
  '**Example:** `t!ffmpegprocess -vf scale=1280:-1 -c:v libx264 -crf 23`\n' +
  'Args are placed between `-i <input>` and `<output>`. Input metadata is probed and shown in the footer.';

async function probeValue(args: string[]): Promise<string> {
  try {
    const result = await spawnAsync('ffprobe', args, { timeout: 10_000 });
    return result.stdout.trim() || 'N/A';
  } catch {
    return 'N/A';
  }
}

async function gatherMetadata(filePath: string): Promise<{
  sampleRate: string;
  frameRate: string;
  duration: string;
  width: string;
  height: string;
  frameCount: string;
}> {
  const [sampleRate, frameRate, duration, width, height, frameCount] = await Promise.all([
    probeValue(['-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate',
      '-of', 'default=nokey=1:noprint_wrappers=1', filePath]),
    probeValue(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
      '-of', 'default=nokey=1:noprint_wrappers=1', filePath]),
    probeValue(['-i', filePath, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=p=0']),
    probeValue(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width',
      '-of', 'default=nw=1:nk=1', filePath]),
    probeValue(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=height',
      '-of', 'default=nw=1:nk=1', filePath]),
    probeValue(['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=nb_frames',
      '-of', 'default=nokey=1:noprint_wrappers=1', filePath]),
  ]);
  return { sampleRate, frameRate, duration, width, height, frameCount };
}

export async function handleFfmpegProcess(message: Message, rawArgs: string): Promise<void> {
  if (!rawArgs.trim()) {
    await message.reply(`❌ No FFmpeg args provided.\n${USAGE}`);
    return;
  }

  let attachmentUrl: string | null = null;
  let attachmentFilename = 'output.mp4';

  if (message.attachments.size > 0) {
    const att = message.attachments.first()!;
    attachmentUrl = att.url;
    attachmentFilename = att.name;
  } else if (message.reference?.messageId) {
    try {
      const ref = await message.channel.messages.fetch(message.reference.messageId);
      if (ref.attachments.size > 0) {
        const att = ref.attachments.first()!;
        attachmentUrl = att.url;
        attachmentFilename = att.name;
      }
    } catch { }
  }

  if (!attachmentUrl) {
    await message.reply(`❌ Attach a file or reply to a message with a file.\n${USAGE}`);
    return;
  }

  const argsDisplay = rawArgs.length <= 80 ? rawArgs : rawArgs.slice(0, 79) + '…';
  const status = await message.reply(`⏳ Probing + processing \`${argsDisplay}\`…`);

  const tmpDir = makeTempDir('fmp');
  const startTime = Date.now();

  try {
    const ext = path.extname(attachmentFilename) || '.mp4';
    const inputPath = path.join(tmpDir, `input${ext}`);
    const outputPath = path.join(tmpDir, attachmentFilename);

    await downloadUrl(attachmentUrl, inputPath);

    const meta = await gatherMetadata(inputPath);

    const userArgList = rawArgs.trim().split(/\s+/);

    const ffResult = await spawnAsync(
      'ffmpeg',
      ['-loglevel', 'error', '-hide_banner', '-y', '-i', inputPath, ...userArgList, outputPath],
      { timeout: PROCESS_TIMEOUTS.FFMPEG_MS },
    );

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);

    const metaParts: string[] = [];
    if (meta.width !== 'N/A' && meta.height !== 'N/A') metaParts.push(`${meta.width}×${meta.height}`);
    if (meta.frameRate !== 'N/A') metaParts.push(`${meta.frameRate} fps`);
    if (meta.duration !== 'N/A') metaParts.push(`${parseFloat(meta.duration).toFixed(2)}s`);
    if (meta.sampleRate !== 'N/A') metaParts.push(`${meta.sampleRate} Hz`);
    if (meta.frameCount !== 'N/A') metaParts.push(`${meta.frameCount} frames`);
    const metaLine = metaParts.length > 0 ? `-# Input: ${metaParts.join(' · ')}` : '';

    const errorLog = ffResult.stderr.trim();
    const errorBlock = errorLog ? `\n-# Error Log:\n\`\`\`\n${errorLog.slice(-800)}\n\`\`\`` : '';

    const footer = [metaLine, errorBlock, `-# Took ${elapsed} seconds.`]
      .filter(Boolean)
      .join('\n');

    if (ffResult.code !== 0 && !fs.existsSync(outputPath)) {
      await status.edit(`❌ FFmpeg failed.${errorBlock}\n-# Took ${elapsed} seconds.`);
      return;
    }

    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit(`❌ FFmpeg produced no output.${errorBlock}`);
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);

    if (outSize > uploadLimit) {
      await status.edit(`${footer}\nFile too big for Discord — uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(`${footer}\n${catboxUrl}`);
      } else {
        await status.edit(`${footer}\n❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
      }
      return;
    }

    await status.edit({ content: footer, files: [outputPath] });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);
    if (msg.includes('timed out')) {
      await status.edit(`❌ Timed out after ${elapsed}s.`);
    } else {
      await status.edit(`❌ \`${msg.slice(0, 300)}\`\n-# Took ${elapsed}s.`);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}
