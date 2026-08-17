import { Message, AttachmentBuilder } from 'discord.js';
import fs from 'node:fs';
import path from 'node:path';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { resolveAttachment } from './gradientmap.js';
import { applyPitchTransition } from '../effects.js';
import { VIDEO_EXTENSIONS, PROCESS_TIMEOUTS } from '../config.js';

const AUDIO_EXTENSIONS = new Set(['mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a', 'opus']);
const USAGE = [
  '**Usage:** `th/pitchtransition <start,end[;start,end...]>` — attach or reply to audio/video',
  '**Also accepts:** `th/pitchtransition --pitch "-5,9;5,-9"`',
  '**Example:** `th/pitchtransition -5,9`',
].join('\n');

export async function handlePitchTransition(message: Message, rawArgs: string): Promise<void> {
  if (!rawArgs.trim()) {
    await message.reply(USAGE);
    return;
  }
  const raw = rawArgs.trim().replace(/^--pitch(?:=|\s*)/i, '').replace(/^["']|["']$/g, '');
  const attachment = await resolveAttachment(message);
  if (!attachment) {
    await message.reply(`❌ No audio/video attachment found. Attach a file or reply to one.\n${USAGE}`);
    return;
  }
  if (!VIDEO_EXTENSIONS.has(attachment.ext) && !AUDIO_EXTENSIONS.has(attachment.ext)) {
    await message.reply(`❌ Unsupported file type \`.${attachment.ext}\`.\n${USAGE}`);
    return;
  }

  const tmpDir = makeTempDir('pitchtransition');
  const status = await message.reply('🔧 Executing native Rubber Band R3 pitch-transition code…');
  try {
    const input = path.join(tmpDir, `input.${attachment.ext}`);
    const outputExt = VIDEO_EXTENSIONS.has(attachment.ext) ? 'mov' : 'm4a';
    const output = path.join(tmpDir, `pitchtransition.${outputExt}`);
    await downloadUrl(attachment.url, input);
    await applyPitchTransition({ inputFile: input, outputFile: output, timeout: PROCESS_TIMEOUTS.FFMPEG_MS }, [raw]);
    const size = fs.statSync(output).size;
    const limit = getUploadLimitBytes(message.guild ?? null);
    if (size > limit) {
      await status.edit(`❌ Output is ${formatBytes(size)}, exceeding Discord's ${formatBytes(limit)} upload limit.`);
      return;
    }
    await status.edit({
      content: `✅ Pitch transition applied: \`${raw}\``,
      files: [new AttachmentBuilder(output, { name: path.basename(output) })],
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    await status.edit(`❌ Pitch transition failed:\n\`\`\`\n${detail.slice(-1200)}\n\`\`\``);
  } finally {
    cleanupDir(tmpDir);
  }
}