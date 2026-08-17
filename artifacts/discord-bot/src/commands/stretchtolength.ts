import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { spawnAsync } from '../utils/spawn.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const USAGE =
  '**Usage:** `th/stretch_to_length <target_seconds>` *(alias: stl)* — attach, reply-to, or pass a media URL\n' +
  '**Example:** `th/stl 10`\n' +
  'Video is re-timed with `setpts` + a locked framerate; audio tempo is changed with `rubberband` (pitch preserved).';

const VIDEO_EXTS = new Set(['.mp4', '.mov', '.mkv', '.webm', '.avi', '.gif']);
const AUDIO_EXTS = new Set(['.mp3', '.wav', '.flac', '.ogg', '.m4a']);

async function probeDuration(filePath: string): Promise<number> {
  const result = await spawnAsync(
    'ffprobe',
    ['-i', filePath, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=p=0'],
    { timeout: 10_000 },
  );
  const val = parseFloat(result.stdout.trim());
  return Number.isFinite(val) ? val : 0;
}

async function probeFramerate(filePath: string): Promise<string> {
  const result = await spawnAsync(
    'ffprobe',
    ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
      '-of', 'default=nokey=1:noprint_wrappers=1', filePath],
    { timeout: 10_000 },
  );
  return result.stdout.trim() || '30';
}

export async function handleStretchToLength(message: Message, rawArgs: string): Promise<void> {
  const tokens = rawArgs.trim() ? rawArgs.trim().split(/\s+/) : [];

  let mediaUrl: string | null = null;
  let targetToken: string | null = null;
  for (const tok of tokens) {
    if (tok.startsWith('http://') || tok.startsWith('https://')) {
      if (!mediaUrl) mediaUrl = tok;
    } else if (!targetToken) {
      targetToken = tok;
    }
  }

  if (!targetToken) {
    await message.reply(`❌ Missing target duration.\n${USAGE}`);
    return;
  }
  const targetDuration = parseFloat(targetToken);
  if (!Number.isFinite(targetDuration) || targetDuration <= 0) {
    await message.reply(`❌ Target duration must be a positive number of seconds.\n${USAGE}`);
    return;
  }

  let attachmentUrl: string | null = mediaUrl;
  let attachmentFilename = 'input.mp4';

  if (!attachmentUrl && message.attachments.size > 0) {
    const att = message.attachments.first()!;
    attachmentUrl = att.url;
    attachmentFilename = att.name;
  } else if (!attachmentUrl && message.reference?.messageId) {
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
    await message.reply(`❌ No media found. Attach, reply to, or provide a media URL.\n${USAGE}`);
    return;
  }

  const status = await message.reply(`⏱️ Stretching to \`${targetDuration}s\`…`);
  const tmpDir = makeTempDir('stl');

  try {
    const ext = path.extname(attachmentFilename).toLowerCase() || '.mp4';
    if (!VIDEO_EXTS.has(ext) && !AUDIO_EXTS.has(ext)) {
      await status.edit(`❌ Unsupported format \`${ext}\`.\nSupported: ${[...VIDEO_EXTS, ...AUDIO_EXTS].sort().join(', ')}`);
      return;
    }

    const inputPath = path.join(tmpDir, `input${ext}`);
    const outputPath = path.join(tmpDir, `stretched${ext}`);

    await downloadUrl(attachmentUrl, inputPath);

    const vidlen = await probeDuration(inputPath);
    if (vidlen <= 0) {
      await status.edit('❌ Could not read media duration.');
      return;
    }

    const ratio = vidlen / targetDuration;

    let cmd: string[];
    if (AUDIO_EXTS.has(ext)) {
      cmd = ['-y', '-i', inputPath, '-af', `rubberband=tempo=${ratio.toFixed(10)}`, outputPath];
    } else {
      const framerate = await probeFramerate(inputPath);
      cmd = [
        '-y', '-i', inputPath,
        '-vf', `setpts=1/${ratio.toFixed(10)}*PTS,fps=${framerate}`,
        '-af', `rubberband=tempo=${ratio.toFixed(10)}`,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        outputPath,
      ];
    }

    const ffResult = await spawnAsync('ffmpeg', cmd, { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    if (ffResult.code !== 0 || !fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      const errorLog = ffResult.stderr.trim();
      const errorBlock = errorLog ? `\n\`\`\`\n${errorLog.slice(-1200)}\n\`\`\`` : '';
      await status.edit(`❌ FFmpeg failed.${errorBlock}`);
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    const summary = `✅ Stretched \`${vidlen.toFixed(4)}s\` → \`${targetDuration.toFixed(4)}s\` (ratio \`${ratio.toFixed(4)}\`)`;

    if (outSize > uploadLimit) {
      await status.edit(`${summary}\nFile too big for Discord — uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(`${summary}\n${catboxUrl}`);
      } else {
        await status.edit(`${summary}\n❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
      }
      return;
    }

    const outName = `stl_${targetDuration.toFixed(4)}s_${path.basename(attachmentFilename, ext)}${ext}`;
    await status.edit({ content: summary, files: [{ attachment: outputPath, name: outName }] });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes('timed out')) {
      await status.edit('❌ Timed out.');
    } else {
      await status.edit(`❌ \`${msg.slice(0, 300)}\``);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}
