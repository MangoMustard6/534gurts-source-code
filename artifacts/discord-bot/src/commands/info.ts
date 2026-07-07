import { Message, EmbedBuilder } from 'discord.js';
import { spawnAsync } from '../utils/spawn.js';
import { BOT_OWNER_ID } from '../config.js';

const startTime = Date.now();

function formatUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h ${m % 60}m`;
  if (h > 0) return `${h}h ${m % 60}m ${s % 60}s`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

async function getVersion(cmd: string, args: string[]): Promise<string> {
  try {
    const r = await spawnAsync(cmd, args, { timeout: 8000 });
    const out = (r.stdout + r.stderr).trim();
    const first = out.split('\n')[0] ?? '';
    return first.slice(0, 60) || '(unknown)';
  } catch {
    return '(not found)';
  }
}

export async function handleInfo(message: Message): Promise<void> {
  const ownerId = BOT_OWNER_ID;
  const isOwner = ownerId !== '' && message.author.id === ownerId;
  const uptime = formatUptime(Date.now() - startTime);

  const [ffmpegVer, rbVer, ytdlpVer] = await Promise.all([
    getVersion('ffmpeg', ['-version']),
    getVersion('rubberband', ['--version']),
    getVersion('yt-dlp', ['--version']),
  ]);

  const embed = new EmbedBuilder()
    .setColor(0x5865f2)
    .setAuthor({
      name: isOwner ? `👑 ${message.author.displayName}` : message.author.displayName,
      iconURL: message.author.displayAvatarURL(),
    })
    .setTitle('ℹ️ IHTX Bot — Info')
    .addFields(
      {
        name: '🤖 Bot',
        value: [
          `Uptime: **${uptime}**`,
          `Node.js: **${process.version}**`,
          `Your role: **${isOwner ? '👑 Owner' : 'User'}**`,
        ].join('\n'),
        inline: true,
      },
      {
        name: '🛠️ System Tools',
        value: [
          `FFmpeg: \`${ffmpegVer}\``,
          `Rubberband: \`${rbVer}\``,
          `yt-dlp: \`${ytdlpVer}\``,
        ].join('\n'),
        inline: true,
      },
    )
    .setFooter({ text: 'IHTX Bot (TypeScript)' })
    .setTimestamp();

  await message.reply({ embeds: [embed] });
}
