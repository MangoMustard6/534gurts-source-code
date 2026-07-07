import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { VIDEO_EXTENSIONS, PROCESS_TIMEOUTS } from '../config.js';
import { applyRealGMajor4 } from '../effects.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const USAGE =
  '**Usage:** `th/realgmajor4` *(aliases: realgm4, rgm4)* — attach or reply-to a video file\n' +
  'Applies a solarization curve (`curves=all=0/0 0.5/1 1/0`), mixes original audio with a pitch-shifted copy (×1.335 ≈ +5 st), and doubles the volume.';

const SUPPORTED_VIDEO_EXTS = new Set(['mp4', 'mov', 'mkv', 'webm', 'avi']);

async function resolveAttachment(
  message: Message,
): Promise<{ url: string; name: string; ext: string } | null> {
  const direct = message.attachments.first();
  if (direct) {
    const ext = (direct.name?.split('.').pop() ?? '').toLowerCase();
    return { url: direct.url, name: direct.name ?? 'input.mp4', ext };
  }

  if (message.reference?.messageId) {
    try {
      const ref = await message.fetchReference();
      const a = ref.attachments.first();
      if (a) {
        const ext = (a.name?.split('.').pop() ?? '').toLowerCase();
        return { url: a.url, name: a.name ?? 'input.mp4', ext };
      }
    } catch { /* reference may be deleted or in another channel */ }
  }

  return null;
}

export async function handleRealGMajor4(message: Message): Promise<void> {
  const attachmentInfo = await resolveAttachment(message);

  if (!attachmentInfo) {
    await message.reply(USAGE);
    return;
  }

  const { url: attachmentUrl, name: attachmentName, ext } = attachmentInfo;

  if (!SUPPORTED_VIDEO_EXTS.has(ext)) {
    await message.reply(
      `❌ Unsupported file type \`.${ext}\`. Real G-Major 4 requires a video file.\n` +
      `Supported: \`${[...SUPPORTED_VIDEO_EXTS].join(', ')}\`.`,
    );
    return;
  }

  const status = await message.reply('⏳ Generating G-Major 4 filter stream graphs…');

  const tmpDir = makeTempDir('gm4');
  const startTime = Date.now();

  try {
    const inputPath = path.join(tmpDir, `input.${ext}`);
    const baseName = path.parse(attachmentName).name.replace(/\.[^.]+$/, '');
    const outputPath = path.join(tmpDir, `rgm4_${baseName}.mp4`);

    await downloadUrl(attachmentUrl, inputPath);

    await applyRealGMajor4(inputPath, outputPath, PROCESS_TIMEOUTS.REALGM4_MS);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);

    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit('❌ Real G-Major 4 synthesis produced no output.');
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);

    if (outSize > uploadLimit) {
      await status.edit(
        `Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`,
      );
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(
          `✅ Done! (${elapsed}s)\n` +
          `-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`,
        );
      } else {
        await status.edit(
          `❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`,
        );
      }
      return;
    }

    await status.edit({
      content: `✅ Real G-Major 4 — Solarization curve · pitch mix ×1.335 · Volume doubled\n-# Took ${elapsed} seconds.`,
      files: [{ attachment: outputPath, name: path.basename(outputPath) }],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);

    if (msg.includes('timed out')) {
      await status.edit(`❌ Processing timed out after ${elapsed}s.`);
    } else if (msg.includes('rubberband') || msg.includes('Could not read')) {
      await status.edit(`❌ Synthesis broken. Confirm that rubberband dependencies are available.\n-# \`${msg.slice(0, 300)}\`\n-# Took ${elapsed}s.`);
    } else {
      await status.edit(`❌ \`${msg.slice(0, 300)}\`\n-# Took ${elapsed}s.`);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}
