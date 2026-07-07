import { Guild, GuildPremiumTier } from 'discord.js';
import { LIMITS } from '../config.js';

export function getMaxRepetitions(userId: string, ownerId: string, guild: Guild | null): number {
  const isOwner = ownerId !== '' && userId === ownerId;
  let max = isOwner ? LIMITS.OWNER_MAX_REPS : LIMITS.NON_OWNER_MAX_REPS;

  if (guild && guild.premiumTier >= GuildPremiumTier.Tier1) {
    max += LIMITS.BOOST_BONUS;
  }

  return max;
}

export function getUploadLimitBytes(guild: Guild | null): number {
  if (!guild) return 8 * 1024 * 1024;
  if (guild.premiumTier >= GuildPremiumTier.Tier3) return 100 * 1024 * 1024;
  if (guild.premiumTier >= GuildPremiumTier.Tier2) return 50 * 1024 * 1024;
  return 8 * 1024 * 1024;
}

export function formatBytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}
