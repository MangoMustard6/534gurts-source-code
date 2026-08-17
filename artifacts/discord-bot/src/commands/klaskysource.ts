import { Message } from 'discord.js';
import path from 'path';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const KLASKY_URL =
  'https://cdn.discordapp.com/attachments/1124758906376302632/1531987508928446505/convert.33ff0215.mp4?ex=6a6b360d&is=6a69e48d&hm=3b36ef2ce3b5f06e6895c0e127efdeba5cd0d36855cb38a9e344847825898329&';

export async function handleKlaskysource(message: Message): Promise<void> {
  const tmpDir = makeTempDir('klaskysource');
  try {
    const outputPath = path.join(tmpDir, 'klaskysource.mp4');
    await downloadUrl(KLASKY_URL, outputPath);

    const { size } = await import('node:fs').then((fs) => fs.promises.stat(outputPath));
    const limit = getUploadLimitBytes(message.guild ?? null);

    if (size > limit) {
      const catboxUrl = await _upload_to_catbox(outputPath);
      if (catboxUrl) {
        await message.reply(catboxUrl);
      } else {
        await message.reply(`❌ File too large for Discord (${formatBytes(size)}) and Catbox upload failed.`);
      }
      return;
    }

    await message.reply({ files: [{ attachment: outputPath, name: 'klaskysource.mp4' }] });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await message.reply(`❌ Failed to fetch klaskysource: \`${msg.slice(0, 200)}\``);
  } finally {
    cleanupDir(tmpDir);
  }
}
