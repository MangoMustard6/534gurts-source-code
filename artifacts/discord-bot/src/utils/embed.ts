import { EmbedBuilder, Message, ColorResolvable } from 'discord.js';

export function gameEmbed(
  message: Message,
  ownerId: string,
  options: {
    title: string;
    description?: string;
    color?: ColorResolvable;
    fields?: { name: string; value: string; inline?: boolean }[];
    thumbnail?: string;
    footer?: string;
  },
): EmbedBuilder {
  const isOwner = ownerId !== '' && message.author.id === ownerId;
  const authorName = isOwner
    ? `👑 ${message.author.displayName}`
    : message.author.displayName;

  const embed = new EmbedBuilder()
    .setAuthor({
      name: authorName,
      iconURL: message.author.displayAvatarURL(),
    })
    .setTitle(options.title)
    .setColor(options.color ?? 0x5865f2)
    .setTimestamp();

  if (options.description) embed.setDescription(options.description);
  if (options.fields?.length) embed.addFields(options.fields);
  if (options.thumbnail) embed.setThumbnail(options.thumbnail);

  embed.setFooter({
    text: options.footer ?? 'IHTX Games',
    iconURL: message.client.user?.displayAvatarURL(),
  });

  return embed;
}
