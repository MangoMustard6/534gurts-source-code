import { Message } from 'discord.js';
import fs from 'node:fs';
import path from 'node:path';
import { applyPipeEffects, parsePipeEffects, PIPE_EFFECT_NAMES } from '../effects.js';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';
import {
  resolveAttachment,
  SUPPORTED_IMAGE_EXTS,
  SUPPORTED_VIDEO_EXTS,
} from './gradientmap.js';

const USAGE =
  '**Usage:** `th/ihtx <effect>[=<params>],<effect>[=<params>]` — attach or reply to a video/image\n' +
  '**Examples:** `th/ihtx negate,mirror=45;0.5;0.5,zoom=1.4` · `th/ihtx grayscale,volume=1.2`';

export async function handleIhtx(message: Message, rest: string): Promise<void> {
  const effects = parsePipeEffects(rest);
  if (!effects.length) {
    await message.reply(`**Available TypeScript pipe effects:**\n\`${[...PIPE_EFFECT_NAMES].join('`, `')}\`\n\n${USAGE}`);
    return;
  }
  const unknown = effects.filter((effect) => !PIPE_EFFECT_NAMES.has(effect.name));
  if (unknown.length) {
    await message.reply(`❌ Unknown pipe effect(s): ${unknown.map((effect) => `\`${effect.name}\``).join(', ')}\n${USAGE}`);
    return;
  }

  const attachment = await resolveAttachment(message);
  if (!attachment) {
    await message.reply(`❌ Attach or reply to a video/image.\n${USAGE}`);
    return;
  }
  if (!SUPPORTED_VIDEO_EXTS.has(attachment.ext) && !SUPPORTED_IMAGE_EXTS.has(attachment.ext)) {
    await message.reply(`❌ Unsupported file type \`.${attachment.ext}\`.\n${USAGE}`);
    return;
  }

  const dir = makeTempDir('ihtx');
  const input = path.join(dir, `input.${attachment.ext || 'mp4'}`);
  const output = path.join(dir, `ihtx_${path.parse(attachment.name).name}.mp4`);
  const started = Date.now();
  const status = await message.reply(`🔧 Applying ${effects.map((effect) => effect.name).join(' → ')}…`);
  try {
    await downloadUrl(attachment.url, input);
    await applyPipeEffects({ inputFile: input, outputFile: output }, effects);
    if (!fs.existsSync(output) || fs.statSync(output).size === 0) {
      throw new Error('The pipe produced no output');
    }
    const elapsed = ((Date.now() - started) / 1000).toFixed(2);
    const size = fs.statSync(output).size;
    const limit = getUploadLimitBytes(message.guild ?? null);
    if (size > limit) {
      const catbox = await _upload_to_catbox(output);
      await status.edit(catbox
        ? `✅ Pipe complete in ${elapsed}s — output was ${formatBytes(size)} and was uploaded to Catbox.\n${catbox}`
        : `❌ Output is ${formatBytes(size)} and exceeds Discord's upload limit; Catbox upload failed.`);
      return;
    }
    await status.edit({
      content: `✅ Pipe complete in ${elapsed}s.`,
      files: [{ attachment: output, name: path.basename(output) }],
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    await status.edit(`❌ Pipe failed: ${detail.slice(-1400)}`).catch(() => null);
  } finally {
    cleanupDir(dir);
  }
}