import { Message } from 'discord.js';
import { gameEmbed } from '../../utils/embed.js';

function rollDice(expr: string): { rolls: number[]; modifier: number; sides: number; count: number } | null {
  const match = expr.toLowerCase().match(/^(\d+)?d(\d+)([+-]\d+)?$/);
  if (!match) {
    const plain = Number(expr);
    if (!Number.isNaN(plain) && plain >= 2 && plain <= 10000) {
      return { rolls: [Math.floor(Math.random() * plain) + 1], modifier: 0, sides: plain, count: 1 };
    }
    return null;
  }

  const count = Math.min(parseInt(match[1] ?? '1', 10), 100);
  const sides = parseInt(match[2], 10);
  const modifier = match[3] ? parseInt(match[3], 10) : 0;

  if (sides < 2 || sides > 10000 || count < 1) return null;

  const rolls = Array.from({ length: count }, () => Math.floor(Math.random() * sides) + 1);
  return { rolls, modifier, sides, count };
}

export async function handleDice(message: Message, args: string[], ownerId: string): Promise<void> {
  const expr = args[0] ?? 'd6';
  const result = rollDice(expr.trim());

  if (!result) {
    await message.reply(
      '❌ Invalid dice expression. Examples: `d6`, `2d8`, `3d6+5`, `d20`, `100`',
    );
    return;
  }

  const { rolls, modifier, sides, count } = result;
  const subtotal = rolls.reduce((a, b) => a + b, 0);
  const total = subtotal + modifier;

  const rollStr = count > 1 ? `[${rolls.join(', ')}]` : `${rolls[0]}`;
  const modStr = modifier !== 0 ? ` ${modifier > 0 ? '+' : ''}${modifier}` : '';
  const isNat20 = sides === 20 && count === 1 && rolls[0] === 20;
  const isNat1 = sides === 20 && count === 1 && rolls[0] === 1;

  let desc = `**${rollStr}${modStr}**`;
  if (modifier !== 0) desc += ` = **${total}**`;
  if (isNat20) desc += '\n\n🎉 **NATURAL 20!**';
  if (isNat1) desc += '\n\n💀 **CRITICAL FAIL!**';

  const embed = gameEmbed(message, ownerId, {
    title: `🎲 Rolling \`${expr.trim()}\``,
    description: desc,
    color: isNat20 ? 0x57f287 : isNat1 ? 0xed4245 : 0x5865f2,
    fields: count > 1
      ? [
          { name: 'Total', value: `**${total}**`, inline: true },
          { name: 'Dice', value: `${count}d${sides}`, inline: true },
          { name: 'Modifier', value: modifier !== 0 ? `${modifier > 0 ? '+' : ''}${modifier}` : 'None', inline: true },
        ]
      : [],
    footer: 'IHTX Games • Dice',
  });

  await message.reply({ embeds: [embed] });
}
