/**
 * wave.ts — th/wave <preset> command.
 * Applies a named wave preset from WAVE_PRESETS directly via FFmpeg -vf.
 */
import { Message } from 'discord.js';
import path from 'path';
import fs from 'fs';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import { spawnAsync } from '../utils/spawn.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { WAVE_PRESETS, WavePresetKey } from '../wavePresets.js';
import { resolveAttachment, SUPPORTED_VIDEO_EXTS, SUPPORTED_IMAGE_EXTS } from './gradientmap.js';

const PRESET_NAMES = Object.keys(WAVE_PRESETS) as WavePresetKey[];

const USAGE =
  '**Usage:** `th/wave <preset>` — attach or reply-to a video/image\n' +
  '**Presets:** ' + PRESET_NAMES.map((p) => `\`${p}\``).join(', ') + '\n' +
  '**Examples:**\n' +
  '`th/wave largeWave`\n' +
  '`th/wave horizontalOnly`';

export async function handleWave(message: Message, rest: string): Promise<void> {
  const presetName = rest.trim();

  if (!presetName) {
    await message.reply(USAGE);
    return;
  }

  if (!(presetName in WAVE_PRESETS)) {
    await message.reply(
      `❌ Unknown wave preset \`${presetName}\`.\n${USAGE}`,
    );
    return;
  }

  const attachmentInfo = await resolveAttachment(message);
  if (!attachmentInfo) {
    await message.reply(`❌ Attach a video or image to use \`th/wave\`.\n${USAGE}`);
    return;
  }

  const { url, name, ext } = attachmentInfo;
  const isVideo = SUPPORTED_VIDEO_EXTS.has(ext);
  const isImage = SUPPORTED_IMAGE_EXTS.has(ext);
  if (!isVideo && !isImage) {
    await message.reply(
      `❌ Unsupported file type \`.${ext}\`. Attach a video or image.\n${USAGE}`,
    );
    return;
  }

  const status = await message.reply(`⏳ Applying wave preset \`${presetName}\`…`);
  const tmpDir = makeTempDir('wave');
  const startTime = Date.now();

  try {
    const inputPath = path.join(tmpDir, `input.${ext}`);
    const baseName = path.parse(name).name.replace(/\.[^.]+$/, '');
    const outSuffix = isImage ? `.${ext}` : '.mp4';
    const outputPath = path.join(tmpDir, `wave_${baseName}${outSuffix}`);

    await downloadUrl(url, inputPath);

    const filterChain = WAVE_PRESETS[presetName as WavePresetKey];

    await spawnAsync('ffmpeg', [
      '-y', '-i', inputPath,
      '-vf', filterChain,
      '-c:a', 'copy',
      outputPath,
    ], { timeout: PROCESS_TIMEOUTS.FFMPEG_MS });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(3);

    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit('❌ Wave effect produced no output.');
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    if (outSize > uploadLimit) {
      await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await status.edit(
          `✅ Wave preset \`${presetName}\` done! (${elapsed}s)\n-# Output exceeded Discord limit — uploaded to Catbox.\n${catboxUrl}`,
        );
      } else {
        await status.edit(`❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`);
      }
      return;
    }

    await status.edit({
      content: `✅ Wave preset \`${presetName}\` applied!\n-# Took ${elapsed} seconds.`,
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
