export const BOT_TOKEN = process.env.DISCORD_TOKEN ?? process.env.DISCORD_TOKEN_TS ?? '';
export const BOT_OWNER_ID = process.env.BOT_OWNER_ID ?? '';
export const PREFIX = 'th/';

export const LIMITS = {
  NON_OWNER_MAX_REPS: 30,
  OWNER_MAX_REPS: 1000,
  BOOST_BONUS: 15,
  MIN_REPS: 1,
} as const;

export const VIDEO_EXTENSIONS = new Set(['mp4', 'mov', 'mkv', 'webm', 'avi']);

export const PROCESS_TIMEOUTS = {
  DOWNLOAD_MS: 180_000,
  FFMPEG_MS: 120_000,
  RUBBERBAND_MS: 120_000,
  REALGM4_MS: 180_000,
} as const;
