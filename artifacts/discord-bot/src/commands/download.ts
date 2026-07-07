import { Message } from 'discord.js';
import fs from 'fs';
import path from 'path';
import { spawnAsync } from '../utils/spawn.js';
import { getUploadLimitBytes, formatBytes } from '../utils/limits.js';
import { makeTempDir, cleanupDir, listDir } from '../utils/temp.js';
import { PROCESS_TIMEOUTS } from '../config.js';
import { _upload_to_catbox } from '../utils/catbox.js';

const USAGE = '**Usage:** `t!download <url>`  *(aliases: dl, dv, dlv)*';

function validateUrl(raw: string): URL | null {
  try {
    const u = new URL(raw);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u;
  } catch {
    return null;
  }
}

export async function handleDownload(message: Message, args: string[]): Promise<void> {
  const rawUrl = args[0];

  if (!rawUrl) {
    await message.reply(`❌ No URL provided.\n${USAGE}`);
    return;
  }

  const url = validateUrl(rawUrl);
  if (!url) {
    await message.reply('idk bro 😭');
    return;
  }

  const username = message.member?.displayName ?? message.author.username;
  const status = await message.reply(
    `son im crine... fetching this clip for ${username.toLowerCase()} 🥀\ndownloading parameters rn 🫩`,
  );

  const tmpDir = makeTempDir('dl');

  try {
    const outputTemplate = path.join(tmpDir, '%(id)s.%(ext)s');

    const result = await spawnAsync(
      'yt-dlp',
      [
        url.toString(),
        '-f', 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '-o', outputTemplate,
        '--no-playlist',
        '--no-part',
        '--age-limit', '99',
      ],
      { timeout: PROCESS_TIMEOUTS.DOWNLOAD_MS },
    );

    if (result.code !== 0) {
      const excerpt = result.stderr.slice(-800).trim().toLowerCase();
      const rawExcerpt = result.stderr.slice(-800).trim();
      // Classify common yt-dlp errors into user-friendly messages
      if (excerpt.includes('not available') || excerpt.includes('not found')) {
        await status.edit(`❌ This video is not available. It may have been removed or made private.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('private')) {
        await status.edit(`❌ This video is private and cannot be downloaded.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('age') || excerpt.includes('sign in') || excerpt.includes('inappropriate')) {
        await status.edit(`❌ This video is age-restricted and cannot be downloaded without authentication.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('geo') || excerpt.includes('country') || excerpt.includes('region')) {
        await status.edit(`❌ This video is geo-blocked and not available in this region.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('copyright') || excerpt.includes('takedown')) {
        await status.edit(`❌ This video has been removed due to a copyright claim.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('live') && (excerpt.includes('stream') || excerpt.includes('broadcast'))) {
        await status.edit(`❌ Live streams cannot be downloaded while in progress.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('premium') || excerpt.includes('members') || excerpt.includes('subscriber')) {
        await status.edit(`❌ This video requires a premium/membership and cannot be downloaded.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else if (excerpt.includes('playlist')) {
        await status.edit(`❌ Playlists are not supported. Please provide a single video URL.\n-# \`${rawExcerpt.slice(0, 200)}\``);
      } else {
        await status.edit(`idk bro 😭\n\`\`\`\n${rawExcerpt}\n\`\`\``);
      }
      return;
    }

    const files = listDir(tmpDir);
    if (files.length === 0) {
      await status.edit('idk bro 😭');
      return;
    }

    const filePath = files.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
    const uploadLimit = getUploadLimitBytes(message.guild ?? null);
    const size = fs.statSync(filePath).size;

    if (size > uploadLimit) {
      await status.edit(`file too heavy tbh... uploading to catbox instead 🥀`);
      const catboxUrl = await _upload_to_catbox(filePath);
      if (catboxUrl) {
        await status.edit(
          `here ✌️ (too heavy for discord so catbox it is)\n${catboxUrl}\n-# ${formatBytes(size)}`,
        );
      } else {
        await status.edit(`file too heavy tbh... cant upload 💀\n-# ${formatBytes(size)} — too big for Discord and Catbox upload failed`);
      }
      return;
    }

    await status.edit({ content: `here ✌️`, files: [filePath] });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes('timed out')) {
      await status.edit('idk bro 😭 (timed out)');
    } else if (msg.includes('spawn error') || msg.includes('Failed to spawn')) {
      await status.edit('idk bro 😭 (`yt-dlp` not found)');
    } else {
      await status.edit(`idk bro 😭\n\`\`\`\n${msg.slice(0, 300)}\n\`\`\``);
    }
  } finally {
    cleanupDir(tmpDir);
  }
}
