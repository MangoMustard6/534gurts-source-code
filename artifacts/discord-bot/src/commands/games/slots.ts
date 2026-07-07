import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

const SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '⭐', '💎', '7️⃣'];
const WEIGHTS =   [30,   25,   20,   15,   6,    3,    1];

function weightedPick(): string {
  const total = WEIGHTS.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < SYMBOLS.length; i++) {
    r -= WEIGHTS[i];
    if (r <= 0) return SYMBOLS[i];
  }
  return SYMBOLS[0];
}

function payoutLabel(s1: string, s2: string, s3: string): { label: string; color: number } {
  if (s1 === s2 && s2 === s3) {
    if (s1 === '7️⃣') return { label: '🎰 **JACKPOT! TRIPLE SEVENS!** 🎰', color: 0xffd700 };
    if (s1 === '💎') return { label: '💎 **TRIPLE DIAMONDS!**', color: 0x00d4ff };
    return { label: `🎉 **THREE OF A KIND!** ${s1}${s1}${s1}`, color: 0x57f287 };
  }
  if (s1 === s2 || s2 === s3 || s1 === s3) {
    return { label: '✨ **Pair!**', color: 0xfee75c };
  }
  return { label: '😔 No match. Try again!', color: 0xed4245 };
}

export async function handleSlots(message: Message, ownerId: string): Promise<void> {
  const s1 = weightedPick();
  const s2 = weightedPick();
  const s3 = weightedPick();
  const { label, color } = payoutLabel(s1, s2, s3);

  const embed = gameEmbed(message, ownerId, {
    title: '🎰 Slot Machine',
    description: `# ${s1}  ${s2}  ${s3}\n\n${label}`,
    color,
    footer: 'IHTX Games • Slots',
  });

  await message.reply({ embeds: [embed] });
}
