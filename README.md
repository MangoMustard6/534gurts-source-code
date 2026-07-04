OLD README.md
# IHTX Bot — I Hate The X FFmpeg Discord Bot

A Discord bot that applies destructive FFmpeg visual effects to videos and images. Upload a file, pick a preset, chain custom effects, or generate a TV-simulator montage.

## Quick Start

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) (required)
- [ImageMagick](https://imagemagick.org/) (required for preview1280 and huehsv effect)
- [sox](http://sox.sourceforge.net/) (optional, for advanced audio effects)
- FFmpeg with rubberband filter support (required for preview1280 pitch shifting)

### Install

```bash
pip install -r requirements.txt
```

### Run

Set your Discord bot token as an environment variable, then start the bot:

```bash
export DISCORD_TOKEN="your-bot-token-here"
python3 bot/ihtx_bot.py
```

Or use the entry point:

```bash
python3 main.py
```

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/ihtx [preset]` | `th/effect`, `th/destroy` | Apply a preset effect to an attached video/image |
| `th/ihtx effect=value,... [rep] [dur]` | | Chain custom effects with repetitions and duration |
| `th/preview1280 [start] [dur]` | `th/p1280` | 12-segment TV-simulator montage |
| `th/multipitch <pitches>` | `th/mp`, `th/multi` | Multi-voice pitch shift (semicolon-separated semitones) |
| `th/ihtxsap <reps> [dur] [pitches]` | `th/sap` | Audio-only th/ihtx: strip video, repeat N times, optional multipitch |
| `th/presets` | `th/effects`, `th/list` | List all available effect presets |
| `th/ihtxhelp` | `th/bothelp` | Show help embed with full effect reference |

### Owner-Only Commands

| Command | Description |
|---------|-------------|
| `th/blockuser <id\|mention>` | Block a user from using the bot |
| `th/unblockuser <id\|mention>` | Unblock a user |
| `th/blockchannel [id\|mention]` | Block a channel (current channel if omitted) |
| `th/unblockchannel [id\|mention]` | Unblock a channel |
| `th/say <message>` | Send a plain message as the bot |
| `th/sayembed <title> \| <description>` | Send an embed as the bot |

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

## Custom Effect Chains

Use `th/ihtx` with comma-separated `effect=value` pairs. Sub-parameters use semicolons (including multipitch pitch values).

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
| ffmpeg | `ffmpeg(<args>)` | Raw ffmpeg flags |

## Preview1280

The `th/preview1280` command creates a 12-segment TV-simulator montage with:

- Hue shifts using Hald CLUTs (54°, 180°, 22°, 108°+saturation boost)
- Horizontal flips and mirror compositions
- TV-simulator displacement mapping with contrast and hue adjustments
- Pitch variations per segment via rubberband filter (+1, -2, +2, +3 semitones)
- Final upscale to original video resolution

**Requirements:** ImageMagick (`magick` command), FFmpeg with `rubberband` filter support, and the `tvsimulator.mov` displacement map at `bot/displacemaps/tvsimulator.mov`.

**Usage:** `th/preview1280 [start_offset] [segment_duration]`

Defaults: start=1.85s, duration=0.85s per segment.

## Multipitch

The `th/multipitch` command (aliases: `th/mp`, `th/multi`) applies multi-voice pitch shifting using FFmpeg\'s `rubberband` audio filter with `filter_complex` + `amix`. Each semicolon-separated semitone value creates a separate pitch-shifted copy of the audio, and all copies are mixed together simultaneously.

**Pipeline:**
```
[0:a]rubberband=pitch=2^(1/12):window=standard:transients=crisp:detector=2.14748e+09/4.9:phase=independent:channels=together[a0];
[0:a]rubberband=pitch=2^(4/12):...[a1];
[0:a]rubberband=pitch=2^(7/12):...[a2];
[a0][a1][a2]amix=3,volume=3,bass=g=2.5[outa]
-map 0:v -map "[outa]" -c:v ffv1 -c:a pcm_s16le
```

**Usage:** `th/multipitch <semitones;separated;by;semicolon>`

**Example:** `th/multipitch 1;4;7` — all three pitches play simultaneously, mixed together.

Negative values are supported: `th/multipitch -3;0;5`

**In effect chains:** `multipitch=1;4;7` uses rubberband with summed pitch values for a single-pass shift (full amix requires `filter_complex` which is only in the standalone command).

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Discord bot token |

### Data Files (auto-created in `bot/`)

| File | Purpose |
|------|---------|
| `owner_ids.json` | List of owner user IDs (full access) |
| `limits.json` | Per-user heavy command limits |
| `blocklist.json` | Blocked user IDs |
| `channel_blocks.json` | Blocked channel IDs |
| `tags.json` | Custom tag/preset definitions |
| `autoreply.json` | Auto-reply configuration |

### Assets

| Path | Purpose |
|------|---------|
| `bot/displacemaps/tvsimulator.mov` | TV simulator displacement map for preview1280 |

### Constants (edit in source)

- `MAX_FILE_SIZE` — 25 MB (Discord upload limit)
- `MAX_DURATION` — 600 seconds
- `MAX_REPETITIONS` — 100
- `HEAVY_LIMIT_DEFAULT` — 10 heavy commands per 24h for non-owners
- Command prefix: `th/`

## Docker

```bash
docker build -t ihtx-bot .
docker run -e DISCORD_TOKEN="your-token" ihtx-bot
```

## Project Structure

```
├── bot/
│   ├── ihtx_bot.py          # Main Discord bot (presets, effect chains, preview1280)
│   ├── displacemaps/         # FFmpeg displacement assets
│   │   └── tvsimulator.mov   # TV simulator displacement map
│   ├── owner_ids.json
│   ├── limits.json
│   ├── tags.json
│   ├── autoreply.json
│   ├── blocklist.json
│   └── channel_blocks.json
├── main.py                   # Entry point
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build
├── .replit                   # Replit configuration
├── replit.nix                # Nix system deps (ffmpeg, sox)
├── artifacts/                # TypeScript API server & mockup sandbox
├── lib/                      # Shared TypeScript libraries (API spec, DB, Zod)
└── scripts/                 # Build & maintenance scripts
```

## License

Private project — all rights reserved.
