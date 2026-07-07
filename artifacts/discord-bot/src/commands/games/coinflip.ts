import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

export async function handleCoinflip(message: Message, ownerId: string): Promise<void> {
  const result = Math.random() < 0.5 ? 'Heads' : 'Tails';
  const emoji = result === 'Heads' ? '🟡' : '⚪';

  const embed = gameEmbed(message, ownerId, {
    title: `${emoji} Coin Flip`,
    description: `## ${result}!`,
    color: result === 'Heads' ? 0xffd700 : 0xaaaaaa,
    footer: 'IHTX Games • Coinflip',
  });

  await message.reply({ embeds: [embed] });
}
