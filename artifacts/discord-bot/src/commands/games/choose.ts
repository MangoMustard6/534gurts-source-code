import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

export async function handleChoose(message: Message, args: string[], ownerId: string): Promise<void> {
  const input = args.join(' ');
  const options = input.split('|').map((o) => o.trim()).filter(Boolean);

  if (options.length < 2) {
    await message.reply(
      '❌ Provide at least 2 options separated by `|`.\nExample: `t!choose pizza | tacos | sushi`',
    );
    return;
  }

  if (options.length > 20) {
    await message.reply('❌ Maximum 20 options allowed.');
    return;
  }

  const winner = options[Math.floor(Math.random() * options.length)];

  const embed = gameEmbed(message, ownerId, {
    title: '🎯 I Choose…',
    description: `## ${winner}`,
    color: 0x57f287,
    fields: [
      {
        name: `All ${options.length} options`,
        value: options.map((o, i) => `${o === winner ? '➡️' : `${i + 1}.`} ${o}`).join('\n'),
      },
    ],
    footer: 'IHTX Games • Choose',
  });

  await message.reply({ embeds: [embed] });
}
