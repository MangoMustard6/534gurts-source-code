import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

const RESPONSES = [
  { text: 'It is certain.', type: 'positive' },
  { text: 'It is decidedly so.', type: 'positive' },
  { text: 'Without a doubt.', type: 'positive' },
  { text: 'Yes, definitely.', type: 'positive' },
  { text: 'You may rely on it.', type: 'positive' },
  { text: 'As I see it, yes.', type: 'positive' },
  { text: 'Most likely.', type: 'positive' },
  { text: 'Outlook good.', type: 'positive' },
  { text: 'Yes.', type: 'positive' },
  { text: 'Signs point to yes.', type: 'positive' },
  { text: 'Reply hazy, try again.', type: 'neutral' },
  { text: 'Ask again later.', type: 'neutral' },
  { text: 'Better not tell you now.', type: 'neutral' },
  { text: 'Cannot predict now.', type: 'neutral' },
  { text: 'Concentrate and ask again.', type: 'neutral' },
  { text: "Don't count on it.", type: 'negative' },
  { text: 'My reply is no.', type: 'negative' },
  { text: 'My sources say no.', type: 'negative' },
  { text: 'Outlook not so good.', type: 'negative' },
  { text: 'Very doubtful.', type: 'negative' },
] as const;

export async function handleEightBall(message: Message, args: string[], ownerId: string): Promise<void> {
  const question = args.join(' ').trim();

  if (!question) {
    await message.reply('❌ Ask a question!\nExample: `t!8ball Will I win today?`');
    return;
  }

  const response = RESPONSES[Math.floor(Math.random() * RESPONSES.length)];
  const color =
    response.type === 'positive' ? 0x57f287 :
    response.type === 'negative' ? 0xed4245 :
    0xfee75c;

  const embed = gameEmbed(message, ownerId, {
    title: '🎱 Magic 8-Ball',
    color,
    fields: [
      { name: 'Question', value: question.length > 256 ? question.slice(0, 253) + '…' : question },
      { name: 'Answer', value: `> ${response.text}` },
    ],
    footer: 'IHTX Games • 8-Ball',
  });

  await message.reply({ embeds: [embed] });
}
