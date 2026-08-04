import { Message } from 'discord.js';
import path from 'node:path';
import fs from 'node:fs';
import { applySidechainGateVocoder } from '../effects.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import {
  resolveAttachment,
  SUPPORTED_VIDEO_EXTS,
  SUPPORTED_IMAGE_EXTS,
} from './gradientmap.js';

const USAGE =
  '**Usage:** `th/scgv <carrier_url> [bandwidth] [ratio] [threshold] [release] [attack] [makeup] [knee] [detection] [range] [volume] [pitch]>`\n' +
  '**Alias:** `th/sidechaingate_vocoder`\n' +
  '**Defaults:** 64 bands, peak detection, release 50, attack 0.01, ratio 2, threshold 1, makeup 1, knee 8, pitch 0, range 0, volume 1.\n' +
  'Attach or reply to the modulator video/audio.';

export async function handleScgv(message: Message, rest: string): Promise<void> {
  const params = rest.trim().split(/\s+/).filter(Boolean);
  if (!params.length) {
    await message.reply(USAGE);
    return;
  }

  const attachment = await resolveAttachment(message);
  if (!attachment) {
    await message.reply(`❌ Attach or reply to a video/audio file.\n${USAGE}`);
    return;
  }

  if (!SUPPORTED_VIDEO_EXTS.has(attachment.ext) && !SUPPORTED_IMAGE_EXTS.has(attachment.ext)) {
    await message.reply(`❌ Unsupported file type \`.${attachment.ext}\`.\n${USAGE}`);
    return;
  }

  const tmpDir = makeTempDir('scgv');
  const inputPath = path.join(tmpDir, `input.${attachment.ext}`);
  const outputPath = path.join(tmpDir, 'sidechaingate_vocoder.mp4');
  const status = await message.reply(`🔧 Executing SCGV vocoder/filtergraph code (${params[0].slice(0, 80)})…`);

  try {
    await downloadUrl(attachment.url, inputPath);
    await applySidechainGateVocoder(
      { inputFile: inputPath, outputFile: outputPath },
      params,
    );

    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      await status.edit('❌ SCGV produced no output.');
      return;
    }

    const outSize = fs.statSync(outputPath).size;
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    if (outSize > uploadLimit) {
      await status.edit(`Output too large for Discord (${formatBytes(outSize)}). Uploading to Catbox…`);
      const catboxUrl = await _upload_to_catbox(outputPath);
      await status.edit(
        catboxUrl
          ? `✅ SCGV done! Output uploaded to Catbox.\n${catboxUrl}`
          : `❌ Too large for Discord and Catbox upload failed. (${formatBytes(outSize)})`,
      );
      return;
    }

    await status.edit({
      content: '✅ SCGV vocoder applied.',
      files: [{ attachment: outputPath, name: 'sidechaingate_vocoder.mp4' }],
    });
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    await status.edit(`❌ SCGV failed:\n\`\`\`\n${messageText.slice(-1500)}\n\`\`\``);
  } finally {
    cleanupDir(tmpDir);
  }
}