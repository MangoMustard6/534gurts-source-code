# IHTX Bot — I Hate The X FFmpeg Discord Bot

A Discord bot that applies destructive FFmpeg visual effects to videos and images. Upload a file, pick a preset, chain custom effects, generate a TV-simulator montage, chat with an AI, and more.

## Quick Start

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) (required)
- [ImageMagick](https://imagemagick.org/) (required for `huehsv`, `preview1280`)
- [sox](http://sox.sourceforge.net/) (optional, for advanced audio effects)
- FFmpeg with `rubberband` filter support (required for `preview1280` pitch shifting)

### Install

```bash
pip install -r requirements.txt
```

### Run

Set your secrets as environment variables, then start the bot:

```bash
export DISCORD_TOKEN="your-bot-token-here"
export GROQ_API_KEY="your-groq-key-here"        # optional — enables AI chat
export CATBOX_USERHASH="your-userhash-here"     # optional — links uploads to your account
python3 main.py
```

On **Replit**, set these via the Secrets panel and run the `IHTX Discord Bot` workflow.

---

## Commands

### Effect Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/ihtx [preset]` | `th/effect`, `th/destroy` | Apply a preset effect to an attached video/image |
| `th/ihtx effect=value,... [rep] [dur]` | | Chain custom effects with repetitions and duration |
| `th/preview1280 [start] [dur]` | `th/p1280`, `th/preview`, `th/pv1280` | 12-segment TV-simulator montage |
| `th/oppositep1280 [start] [dur]` | `th/op1280`, `th/opposite` | Opposite-polarity variant of preview1280 |
| `th/preview1280with640x360resize [start] [dur]` | `th/p1280ff!3`, `th/p1280w16:9r` | preview1280 with 640×360 output resize |
| `th/multipitch <pitches>` | `th/mp`, `th/multi` | Multi-voice pitch shift (semicolon-separated semitones) |
| `th/soundstretchmultipitch <pitches>` | `th/ssmp` | Soundstretch-based multi-pitch shift |
| `th/ihtxsap <reps> [dur] [pitches]` | `th/sap` | Audio-only ihtx: strip video, repeat N times, optional multipitch |
| `th/invlum [reps]` | `th/il` | Apply luminosity-inversion LUT |
| `th/mirror [preset]` | | Mirror-fold effect with optional preset |
| `th/huehsv <val>` | `th/hhsv` | Hue shift via ImageMagick HSV |
| `th/swirl [args]` | `th/vortex` | Swirl/vortex distortion |
| `th/tvsim [args]` | `th/tv`, `th/tvsimulator` | TV-simulator displacement effect |
| `th/folkvalley` | `th/fv`, `th/folk` | Folk Valley preset |
| `th/vocoder [args]` | `th/vocode` | Vocoder audio effect |
| `th/autotune [args]` | `th/autotoon` | Autotune pitch correction |
| `th/trim [args]` | | Trim video/audio to a time range |
| `th/syncaudio [mode]` | `th/sa`, `th/sync` | Sync audio to video |
| `th/ffmpeg <args>` | | Run raw FFmpeg flags on an attached file |
| `th/ffmpegprocess <args>` | `th/fmp` | FFmpeg processing with additional options |
| `th/lexg [dur]` | `th/lastexportgrab`, `th/lec` | Grab the last N seconds of an export |
| `th/png2lut [args]` | `th/lut2cube` | Convert PNG to .cube LUT |
| `th/lut2png [cube_url]` | `th/applylut`, `th/applycube` | Apply a .cube LUT to an attached file |
| `th/addsource [args]` | | Add a source layer to a composition |
| `th/undo` | | Undo the last effect applied |
| `th/guesseffect` | `th/ge` | Guess the effect applied to a random clip |
| `th/presets` | `th/effects`, `th/list` | List all available effect presets |
| `th/ihtxhelp [query]` | `th/bothelp` | Show help embed with full effect reference |

### AI Chat

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/chat <question>` | `th/ask`, `th/ai` | Chat with the AI assistant (Groq / Llama 3.3 70B) |
| `th/clearchat` | `th/resetai`, `th/chatclear` | Clear your AI chat history |

> **Note:** Attachments are not supported in `th/chat` — text only. AI replies are also enabled per-channel via `th/autoreply2`.

### Catbox Upload

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/catbox` | `th/cb`, `th/upload` | Upload an attached file to catbox.moe |

### Fun & Games

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/8ball <question>` | `th/eightball` | Ask the magic 8-ball |
| `th/coinflip` | `th/flip`, `th/coin` | Flip a coin |
| `th/roll [sides]` | `th/dice`, `th/d` | Roll a die (default: 6 sides) |
| `th/rps <choice>` | `th/rockpaperscissors` | Rock, paper, scissors |
| `th/choose <opt1\|opt2\|...>` | `th/pick` | Pick randomly from options |
| `th/rate <thing>` | | Rate something out of 10 |
| `th/slots` | `th/slot` | Spin the slot machine |
| `th/hangman` | `th/hm` | Play hangman |
| `th/blackjack` | `th/bj`, `th/21` | Play blackjack |
| `th/tictactoe` | `th/ttt` | Play tic-tac-toe |
| `th/trivia` | | Answer a trivia question |
| `th/random [subcommand]` | `th/rand` | Random media/content from the pool |

### XP & Levels

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/level [member]` | `th/rank`, `th/xp` | Check your (or another member's) XP and level |
| `th/leaderboard` | `th/lb`, `th/top` | Server XP leaderboard |

### Auto-Reply Management

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/autoreply <trigger> [channel] <response>` | `th/ar` | Add an auto-reply trigger |
| `th/removeautoreply <trigger>` | `th/rar`, `th/deautoreply` | Remove an auto-reply trigger |
| `th/removearmentions <trigger>` | `th/rarm`, `th/noarping` | Disable mention pings for a trigger |
| `th/blockarchannel <trigger> [channel]` | `th/bac`, `th/silencear` | Block a trigger in a channel |
| `th/autoreplies` | `th/listautoreplies`, `th/arlist` | List all auto-reply triggers |
| `th/autoreply2` | `th/ar2` | Toggle AI auto-reply in the current channel |
| `th/autoreply2list` | `th/ar2list` | List channels with AI auto-reply enabled |
| `th/removear2mentions <user>` | `th/rarm2`, `th/noar2ping` | Disable AI auto-reply pings for a user |

### Owner-Only Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/blockuser <id\|mention>` | | Block a user from using the bot |
| `th/unblockuser <id\|mention>` | | Unblock a user |
| `th/blockchannel [id\|mention]` | | Block a channel (current if omitted) |
| `th/unblockchannel [id\|mention]` | | Unblock a channel |
| `th/keywordblock <keyword> [channel]` | `th/blockkeyword`, `th/kb` | Block messages containing a keyword |
| `th/keywordblockremove <keyword> [channel]` | `th/unblockkeyword`, `th/kbr` | Remove a keyword block |
| `th/keywordblockmsg <keyword> <message>` | `th/kbmsg`, `th/blockmsg` | Set the response message for a keyword block |
| `th/say <message>` | | Send a plain message as the bot |
| `th/sayembed <title> \| <description>` | | Send an embed as the bot |
| `th/sendmsg <channel_id> <text>` | `th/msgsend` | Send a message to a specific channel |
| `th/setactivity <type> <text>` | `th/activity`, `th/presence` | Set the bot's activity status |
| `th/setlimit <user> <limit>` | `th/sl` | Set a custom heavy-command limit for a user |
| `th/resetlimit <user>` | `th/rl`, `th/resetusage` | Reset a user's heavy-command usage |
| `th/listservers` | `th/servers`, `th/guilds` | List all servers the bot is in |
| `th/listchannels <guild_id>` | `th/channels` | List channels in a server |
| `th/syncslash` | `th/synccmds`, `th/synctree`, `th/slashsync` | Register slash commands globally |
| `th/invite` | | Get the bot's invite link |
| `th/usage` | `th/heavyusage`, `th/limit`, `th/checklimit` | Check heavy-command usage |

---

## Presets

| Preset | Description |
|--------|-------------|
| `chaos` | Shake + noise + hue rotation + high contrast (default) |
| `glitch` | RGB shift + noise + high contrast grayscale |
| `shake` | Shake + noise + boosted contrast/saturation |
| `rainbow` | RGB channel split and additive blend |
| `static` | Noise + vintage curve + mild contrast |
| `melt` | Perspective warp + noise |
| `corrupt` | Grid overlay + noise + high gamma/contrast |

---

## Custom Effect Chains

Use `th/ihtx` with comma-separated `effect=value` pairs. Sub-parameters use semicolons.

**Usage:** `th/ihtx effect=value,effect=value,... [rep] [dur]`

**Example:** `th/ihtx mirror=45,hue=90,multipitch=5 3 10`

### Video Effects

| Effect | Syntax | Description |
|--------|--------|-------------|
| hflip | `hflip` | Flip horizontally |
| vflip | `vflip` | Flip vertically |
| invert | `invert` | Invert all colours |
| invlum | `invlum` | Invert luminosity only |
| invertrgb | `invertrgb=r;g;b` | Invert specific channels (1=invert, 0=keep) |
| grayscale | `grayscale` | Remove colour (desaturate) |
| sepia | `sepia` | Sepia tone |
| rotate | `rotate=<deg>` | Rotate by degrees |
| hue | `hue=<deg>` | Shift hue (0–360) |
| huehsv | `huehsv=<val>` | Shift hue (magick-style, -100 to 100) |
| ffmpeghue | `ffmpeghue=<deg>` | Hue shift via FFmpeg hue filter |
| brightness | `brightness=<val>` | Adjust brightness (e.g. 0.1) |
| contrast | `contrast=<val>` | Adjust contrast (e.g. 1.5) |
| saturation | `saturation=<val>` | Adjust saturation (e.g. 1.5) |
| channelblend | `channelblend=r;g;b` | Swap/mix RGB channels (r/g/b) |
| swapuv | `swapuv` | Swap U and V chroma channels |
| gm4 | `gm4` | Selective colour boost |
| realgm4 | `realgm4` | Solarise via curves inversion |

### Distortion Effects

| Effect | Syntax | Description |
|--------|--------|-------------|
| fisheye | `fisheye=strength;radius;cx;cy` | Fisheye lens warp |
| swirl | `swirl=angle;radius;cx;cy;fallout;lock` | Swirl distortion (fallout: linear/quad) |
| wave | `wave=hs;hf;ha;hp;vs;vf;va;vp` | Wave distortion (8 params + optional separate/noclip) |
| zoom | `zoom=<scale>` | Zoom in (e.g. 2) |
| mirror | `mirror=<angle>` | Mirror fold at angle |
| tile | `tile=x;y` | Tile the image N×M times |
| polar | `polar` | Unroll circular image to strip |
| depolar | `depolar` | Wrap strip into disk |
| orb | `orb` | Fisheye orb effect |
| deorb | `deorb` | Reverse orb |
| gm91deform | `gm91deform` | Perspective/barrel warp |

### Transform / Overlay Effects

| Effect | Syntax | Description |
|--------|--------|-------------|
| scroll | `scroll=h;v` | Continuous scroll (0.0–1.0) |
| pan | `pan=x;y` | Shift image by pixels |
| vreverse | `vreverse` | Reverse video frames |
| watermark | `watermark=<url>` | Overlay transparent PNG |
| ring | `ring` or `ring=<url>` | Frame overlay (default or custom URL) |
| miui | `miui` | MIUI-style watermark |
| reddit | `reddit` | Reddit-style watermark |
| caption | `caption=<text>` | Text at top-centre |

### Audio Effects

| Effect | Syntax | Description |
|--------|--------|-------------|
| multipitch | `multipitch=<semitones>` | Multi-voice pitch shift. Semicolon-separated: `multipitch=1;4;7` |
| volume | `volume=<val>` | Adjust volume multiplier |
| vibrato | `vibrato=freq;depth` | Vibrato effect |
| areverse | `areverse` | Reverse audio |

### LUT / Raw Effects

| Effect | Syntax | Description |
|--------|--------|-------------|
| lut | `lut=<url>` | Apply external .cube LUT from URL |
| invlum | `invlum` | Built-in luminosity-inversion LUT |
| ffmpeg | `ffmpeg(<args>)` | Raw FFmpeg flags |

---

## Preview1280

The `th/preview1280` command creates a 12-segment TV-simulator montage with:

- Hue shifts using Hald CLUTs (54°, 180°, 22°, 108°+saturation boost)
- Horizontal flips and mirror compositions
- TV-simulator displacement mapping with contrast and hue adjustments
- Pitch variations per segment via rubberband filter (+1, -2, +2, +3 semitones)
- Final upscale to original video resolution

**Requirements:** ImageMagick (`magick` command), FFmpeg with `rubberband` filter support, and `bot/displacemaps/tvsimulator.mov`.

**Usage:** `th/preview1280 [start_offset] [segment_duration]`

Defaults: start=1.85s, duration=0.85s per segment.

---

## Multipitch

The `th/multipitch` command applies multi-voice pitch shifting using FFmpeg's `rubberband` audio filter with `filter_complex` + `amix`. Each semicolon-separated semitone value creates a separate pitch-shifted copy mixed together simultaneously.

**Pipeline:**
```
[0:a]rubberband=pitch=2^(1/12)...[a0];
[0:a]rubberband=pitch=2^(4/12)...[a1];
[0:a]rubberband=pitch=2^(7/12)...[a2];
[a0][a1][a2]amix=3,volume=3,bass=g=2.5[outa]
-map 0:v -map "[outa]" -c:v ffv1 -c:a pcm_s16le
```

**Usage:** `th/multipitch <semitones;separated;by;semicolon>`

**Example:** `th/multipitch 1;4;7` — all three pitches play simultaneously.

Negative values are supported: `th/multipitch -3;0;5`

**In effect chains:** `multipitch=1;4;7` uses rubberband with summed pitch values for a single-pass shift.

---

## Configuration

### Environment Variables / Secrets

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | **Yes** | Discord bot token |
| `GROQ_API_KEY` | No | Groq API key — enables `th/chat` and AI auto-reply |
| `CATBOX_USERHASH` | No | Catbox user hash — links uploads to your account; omit for anonymous uploads |

### Data Files (auto-created in `bot/`)

| File | Purpose |
|------|---------|
| `owner_ids.json` | List of owner user IDs (full access) |
| `limits.json` | Per-user heavy command limits |
| `blocklist.json` | Blocked user IDs |
| `channel_blocks.json` | Blocked channel IDs |
| `tags.json` | Custom tag/preset definitions |
| `autoreply.json` | Auto-reply trigger configuration |
| `autoreply2.json` | Channels with AI auto-reply enabled |
| `xp_data.json` | XP and level data |
| `economy_data.json` | Economy/game data |

### Assets

| Path | Purpose |
|------|---------|
| `bot/displacemaps/tvsimulator.mov` | TV simulator displacement map for preview1280 |
| `bot/InvertLuminosity.cube` | Built-in LUT for `invlum` effect |

### Constants (edit in source)

- `MAX_FILE_SIZE` — 25 MB (Discord upload limit)
- `MAX_DURATION` — 600 seconds
- `MAX_REPETITIONS` — 100
- `HEAVY_LIMIT_DEFAULT` — 20 heavy commands per 24h for non-owners
- Command prefix: `th/` (configurable via `bot/config.json`)

---

## Project Structure

```
├── bot/
│   ├── ihtx_bot.py          # Main Discord bot
│   ├── economy_cog.py       # Economy and game commands
│   ├── garden_cog.py        # Garden mini-game
│   ├── catbox_upload.py     # CLI catbox upload helper
│   ├── displacemaps/        # FFmpeg displacement assets
│   │   └── tvsimulator.mov
│   ├── config.json          # Bot config (prefix, system prompt)
│   ├── owner_ids.json
│   ├── limits.json
│   ├── tags.json
│   ├── autoreply.json
│   ├── blocklist.json
│   └── channel_blocks.json
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container build
├── .replit                  # Replit configuration
└── replit.nix               # Nix system deps (ffmpeg, sox)
```

---

## License

Private project — all rights reserved.
