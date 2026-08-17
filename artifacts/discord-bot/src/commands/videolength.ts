import { Message } from 'discord.js';
import { spawnAsync } from '../utils/spawn.js';

const USAGE = '**Usage:** `th/videolength <url>`  *(aliases: vidlen, videolen)*';

function validateUrl(raw: string): URL | null {
  try {
    const u = new URL(raw);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u;
  } catch {
    return null;
  }
}

/**
 * Formats a duration in seconds to H:MM:SS.ss
 * e.g. 3661.5 → "1:01:01.50"
 */
function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const sFixed = s.toFixed(2).padStart(5, '0'); // e.g. "01.50", "59.99"
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${sFixed}`;
  }
  return `${m}:${sFixed}`;
}

export async function handleVideolength(message: Message, args: string[]): Promise<void> {
  const rawUrl = args[0];

  if (!rawUrl) {
    await message.reply(`❌ No URL provided.\n${USAGE}`);
    return;
  }

  const url = validateUrl(rawUrl);
  if (!url) {
    await message.reply('❌ Invalid URL.');
    return;
  }

  const status = await message.reply('🔍 checking duration...');

  const result = await spawnAsync('ffprobe', [
    '-i', url.toString(),
    '-show_entries', 'format=duration',
    '-v', 'quiet',
    '-of', 'csv=p=0',
  ], { timeout: 30_000 });

  const raw = result.stdout.trim();
  const seconds = parseFloat(raw);

  if (!raw || isNaN(seconds)) {
    const excerpt = result.stderr.slice(-400).trim();
    await status.edit(`❌ Couldn't read duration.\n\`\`\`\n${excerpt || 'no output'}\n\`\`\``);
    return;
  }

  const formatted = formatDuration(seconds);
  await status.edit(`⏱️ **${formatted}** *(${seconds.toFixed(3)}s)*`);
}
