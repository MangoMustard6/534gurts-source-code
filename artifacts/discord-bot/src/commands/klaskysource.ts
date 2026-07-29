import { Message } from 'discord.js';
import path from 'path';
import { makeTempDir, cleanupDir, downloadUrl } from '../utils/temp.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const KLASKY_URL =
  'https://cdn.discordapp.com/attachments/1124758906376302632/1531978800936784003/Project_Name_9.36268c57.mov?ex=6a6b2df0&is=6a69dc70&hm=22e44ff512fc2151cf2c05933f4b9672a0c0bb6503323f22166c8be1797682de&';

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
