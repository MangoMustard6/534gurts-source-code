# IHTX Bot — I Hate The X FFmpeg Discord Bot

A Discord bot that applies destructive visual and audio effects to videos and images using FFmpeg, ImageMagick, and Sox. Supports presets (chaos, glitch, melt), custom effect chaining, TV-simulator montages, and multi-voice pitch shifting.

## Run & Operate

- Run button starts the bot via `python3 main.py`
- Required secret: `DISCORD_TOKEN` — your Discord bot token (set via Replit Secrets)
- Required secret: `CATBOX_USERHASH` — Catbox.moe userhash for uploads (bot exits at startup if missing)
- Optional secrets: `GROQ_API_KEY` (AI chat via Llama), `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `FAL_KEY`, `REPLICATE_API_TOKEN`

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
- All AI integrations (Gemini, Anthropic, fal, replicate) are optional — gracefully degrade if keys not set
- System tools (ffmpeg, sox, imagemagick, rubberband) provided via Nix `stable-25_05` channel

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- `DISCORD_TOKEN` must be set in Replit Secrets before the bot will start
- yt-dlp version must be recent (>=2026.3.17) to avoid YouTube API breakage
