import { Message } from 'discord.js';
import path from 'path';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const KLASKY_URL =
  'https://cdn.discordapp.com/attachments/1522748365509754970/1526836867860008990/snip.5d8ea87e.mp4?ex=6a587924&is=6a5727a4&hm=f22e312730d0018586fa93b7d33585214e929c5d06074129ec1ccc34bec3ffd5&';

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
