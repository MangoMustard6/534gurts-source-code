import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

const CHOICES = ['rock', 'paper', 'scissors'] as const;
type Choice = typeof CHOICES[number];

const EMOJI: Record<Choice, string> = { rock: '🪨', paper: '📄', scissors: '✂️' };

function getOutcome(player: Choice, bot: Choice): 'win' | 'lose' | 'tie' {
  if (player === bot) return 'tie';
  if (
    (player === 'rock' && bot === 'scissors') ||
    (player === 'paper' && bot === 'rock') ||
    (player === 'scissors' && bot === 'paper')
  ) return 'win';
  return 'lose';
}

export async function handleRPS(message: Message, args: string[], ownerId: string): Promise<void> {
  const input = args[0]?.toLowerCase().trim();

  if (!input || !CHOICES.includes(input as Choice)) {
    await message.reply('❌ Choose `rock`, `paper`, or `scissors`.\nExample: `t!rps rock`');
    return;
  }

  const player = input as Choice;
  const bot = CHOICES[Math.floor(Math.random() * 3)];
  const outcome = getOutcome(player, bot);

  const resultLine = outcome === 'win'
    ? '🎉 **You win!**'
    : outcome === 'lose'
    ? '😔 **You lose!**'
    : '🤝 **It\'s a tie!**';

  const color = outcome === 'win' ? 0x57f287 : outcome === 'lose' ? 0xed4245 : 0xfee75c;

  const embed = gameEmbed(message, ownerId, {
    title: '✂️ Rock Paper Scissors',
    description: resultLine,
    color,
    fields: [
      { name: 'You', value: `${EMOJI[player]} ${player}`, inline: true },
      { name: 'Bot', value: `${EMOJI[bot]} ${bot}`, inline: true },
    ],
    footer: 'IHTX Games • Rock Paper Scissors',
  });

  await message.reply({ embeds: [embed] });
}
