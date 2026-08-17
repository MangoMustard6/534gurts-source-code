# IHTX Bot — I Hate The X FFmpeg Discord Bot

A Discord bot that applies destructive visual and audio effects to videos and images using FFmpeg, ImageMagick, and Sox. Supports presets (chaos, glitch, melt), custom effect chaining, TV-simulator montages, and multi-voice pitch shifting.

## Run & Operate

- Start both bots via the **Run** button (or individually from the Workflows panel):
  - `IHTX Discord Bot` — Python bot (`python3 main.py`)
  - `IHTX Discord Bot (TypeScript)` — TypeScript bot (`pnpm --filter @workspace/discord-bot run dev`)
- Required secrets (set via Replit Secrets):
  - `DISCORD_TOKEN` — Python bot token
  - `DISCORD_TOKEN_TS` — TypeScript bot token (separate Discord app so both can run simultaneously)
  - `BOT_OWNER_ID` — your Discord user ID (both bots exit at startup if missing)
- Optional secrets: `GROQ_API_KEY` (AI chat on Python bot), `GEMINI_API_KEY` (AI chat on TS bot), `CATBOX_USERHASH` (links Catbox uploads to your account)

## Stack

- Python 3.11
- discord.py 2.7+
- FFmpeg, ImageMagick, Sox, Rubberband (system tools via Nix)
- aiohttp, yt-dlp, anthropic, google-genai, fal-client, replicate

## Where things live

- `main.py` — entry point
- `bot/ihtx_bot.py` — full bot implementation (commands, effects, presets)
- `bot/*.json` — config files (owner IDs, blocklists, autoreplies, limits, tags)
- `bot/displacemaps/` — FFmpeg displacement map assets

## Architecture decisions

- Bot token read from `DISCORD_TOKEN` env var at startup; exits cleanly if missing
- Discord login HTTP 429 responses stop the Python launcher without retries; restart it manually after Discord clears the temporary block
- All AI integrations (Gemini, Anthropic, fal, replicate) are optional — gracefully degrade if keys not set
- System tools (ffmpeg, sox, imagemagick, rubberband) provided via Nix `stable-25_05` channel

## User preferences

- `BOT_OWNER_ID` is always required — never use a hardcoded default Discord user ID. Both bots must exit at startup if this secret is missing.

## Gotchas

- `DISCORD_TOKEN` must be set in Replit Secrets before the bot will start
- yt-dlp version must be recent (>=2026.3.17) to avoid YouTube API breakage
