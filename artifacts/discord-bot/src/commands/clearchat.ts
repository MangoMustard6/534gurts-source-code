import { Message } from 'discord.js';
import { clearChannelHistory } from './chat.js';

export async function handleClearchat(message: Message): Promise<void> {
  const cleared = clearChannelHistory(message.channel.id);
  if (cleared) {
    await message.reply('alr chat wiped 🥀 history for this channel is gone');
  } else {
    await message.reply('bradar there was nothing to clear 😭');
  }
}
