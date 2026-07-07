import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

const RED_NUMBERS = new Set([1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]);

function spin(): { num: number; color: 'red' | 'black' | 'green' } {
  const num = Math.floor(Math.random() * 37);
  const color = num === 0 ? 'green' : RED_NUMBERS.has(num) ? 'red' : 'black';
  return { num, color };
}

function colorEmoji(c: 'red' | 'black' | 'green'): string {
  return c === 'red' ? '🔴' : c === 'black' ? '⚫' : '🟢';
}

export async function handleRoulette(message: Message, args: string[], ownerId: string): Promise<void> {
  const bet = args[0]?.toLowerCase().trim();

  if (!bet) {
    await message.reply(
      '❌ Place a bet!\n**Options:** `red`, `black`, `green`, or a number `0`–`36`\nExample: `t!roulette red`',
    );
    return;
  }

  const { num, color } = spin();
  const landed = `${colorEmoji(color)} **${num}** (${color})`;

  let won = false;
  let betLabel = bet;

  if (bet === 'red' || bet === 'black' || bet === 'green') {
    won = bet === color;
    betLabel = `${colorEmoji(bet as 'red' | 'black' | 'green')} ${bet}`;
  } else {
    const n = parseInt(bet, 10);
    if (isNaN(n) || n < 0 || n > 36) {
      await message.reply('❌ Invalid bet. Use `red`, `black`, `green`, or a number `0`–`36`.');
      return;
    }
    won = n === num;
    betLabel = `🔢 ${n}`;
  }

  const resultLine = won
    ? bet === 'green' || bet === String(num)
      ? '🎰 **JACKPOT WIN!**'
      : '🎉 **You win!**'
    : '😔 **You lose!**';

  const embed = gameEmbed(message, ownerId, {
    title: '🎡 Roulette',
    description: resultLine,
    color: won ? 0x57f287 : 0xed4245,
    fields: [
      { name: 'Your bet', value: betLabel, inline: true },
      { name: 'Landed on', value: landed, inline: true },
    ],
    footer: 'IHTX Games • Roulette',
  });

  await message.reply({ embeds: [embed] });
}
