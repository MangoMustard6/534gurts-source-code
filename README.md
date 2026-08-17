# IHTX Bot — I Hate The X FFmpeg Discord Bot

A Discord bot that applies destructive FFmpeg visual effects to videos and images. Upload a file, pick a preset, chain custom pipe effects, generate a TV-simulator montage, chat with AI, farm a garden, and more.

---

## Quick Start

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) (required)
- [ImageMagick](https://imagemagick.org/) (`magick` CLI — required for `huehsv`, `preview1280`, `freakzinga`)
- FFmpeg with `rubberband` filter support (required for `preview1280` pitch shifting)
- FFmpeg with `vidstab` filter support (required for `earthquake`/`nbfx`)
- [sox](http://sox.sourceforge.net/) (optional, for `soundstretch`)

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
export DISCORD_TOKEN="your-bot-token-here"
export GROQ_API_KEY="your-groq-key-here"        # optional — enables AI chat
export CATBOX_USERHASH="your-userhash-here"     # optional — links uploads to your catbox account
python3 main.py
```

On **Replit**, set these via the Secrets panel and run the `IHTX Discord Bot` workflow.

---

## Core Interface — ihtxgen / th/ihtx

The main effect command. Available as a slash command (`/ihtxgen`) and as a prefix command (`th/ihtx`, `th/effect`, `th/destroy`).

### Slash command: `/ihtxgen`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `effect` | string | `chaos` | Preset name, a bare comma-separated pipe effects string (e.g. `negate,huehsv=0.5`), or the full custom syntax string |
| `url` | string | — | Direct URL to a media file (alternative to attaching) |
| `attachment` | file | — | Attach a video or image (slash only) |
| `pipe_effects` | string | — | Comma-separated pipe effects (see [Pipe Effects](#pipe-effects)) |
| `repetitions` | int | `1` | How many times to repeat in pipe mode (max 100) |
| `duration` | string | `vidlen` | Seconds or awk expression, e.g. `5` or `vidlen/2` |
| `no_trim` | bool | `false` | Skip trimming in pipe mode |
| `export_fmt` | string | `mp4` | Output container: `mp4`, `mkv`, `mov`, `avi` |

### Prefix command: `th/ihtx [args]`

Two modes:

**Preset mode:**
```
th/ihtx <preset>
th/ihtx chaos
```

**Custom syntax (pipe effects):**
```
th/ihtx <reps> <duration> <no_trim> <fmt> <pipe_effects>
th/ihtx 1 5 - mp4 negate,huehsv=0.5
th/ihtx 3 vidlen - mp4 multipitch=1;6;7,hue=90
```

**Shorthand pipe mode** (no leading digits, no preset name → 1 rep, full duration, mp4):
```
th/ihtx negate,hue=90
th/ihtx ffmpeg(-vf huesaturation=saturation=1:strength=100)
```

---

## Presets

Apply with `th/ihtx <preset>` or `/ihtxgen effect:<preset>`.

| Preset | Description | Filters Applied |
|--------|-------------|-----------------|
| `chaos` | Shake + noise + hue spin + high contrast | `shake`, noise, `hue=h=t*180:s=2`, `eq=contrast=1.5:brightness=0.05:saturation=3` |
| `glitch` | RGB channel shift + noise + grayscale crush | `rgbashift=rh=8:rv=-8:gh=-4:gv=4:bh=6:bv=-6`, noise, `eq=contrast=1.8:saturation=0` |
| `shake` | Shake + noise + boosted contrast/saturation | `shake`, noise, `eq=contrast=1.3:saturation=1.5` |
| `rainbow` | RGB channel split → additive blend | `split=3`, `lutrgb` per channel, `blend=all_mode=addition` (filter_complex) |
| `static` | Noise + vintage curve + mild contrast | noise, `curves=vintage`, `eq=contrast=1.2` |
| `melt` | Perspective warp + noise | `perspective` with `sin(t*3)`, noise |
| `corrupt` | Grid overlay + noise + high gamma | `drawgrid`, noise, `eq=gamma=1.5:saturation=0.3:contrast=2` |
| `sierpinskiransomware` | 2×2 Sierpinski grid: negate + rubberband speed warp | `hstack`/`vstack` of `negate` + `rubberband=pitch&tempo`, `amix=4` |

---

## Pipe Effects

Use in `th/ihtx` or `/ihtxgen pipe_effects:`. Effects are **comma-separated**; parameters within each effect are **semicolon-, space-, or pipe-separated**.

```
th/ihtx 1 5 - mp4 hflip,negate,multipitch=1;6;7
th/ihtx 2 3 - mp4 swirl=180;0.4,huehsv=0.3,multipitch=-4;0;4
```

You can also use the raw filter passthrough syntax to mix hand-written FFmpeg filters:
```
VIDEO: hue=h=t*90:s=2,negate AUDIO: volume=2,acontrast=50
```

### Video / Visual Effects

| Effect | Syntax | Description | FFmpeg filter |
|--------|--------|-------------|---------------|
| `hflip` | `hflip` | Flip horizontally | `hflip` |
| `vflip` | `vflip` | Flip vertically | `vflip` |
| `invert` / `negate` | `invert` | Invert all colours | `negate` |
| `grayscale` | `grayscale` | Desaturate | `colorchannelmixer=.299:.587:.114:0:…` |
| `sepia` | `sepia` | Sepia tone | `colorchannelmixer=.393:.769:.189:0:…` |
| `rotate` | `rotate=<deg>[;expand]` | Rotate by degrees. `expand=1` expands canvas to fit | `rotate=<deg>/180*PI[:ow='rotw(a)':oh='roth(a)']` |
| `brightness` | `brightness=<b>[;c][;s][;g]` | Brightness, contrast, saturation, gamma (all via `eq`) | `eq=brightness=b:contrast=c:saturation=s:gamma=g` |
| `contrast` | `contrast=<c>[;b][;s][;g]` | Contrast first, then brightness, saturation, gamma | `eq=contrast=c:brightness=b:saturation=s:gamma=g` |
| `saturation` | `saturation=<s>[;h]` | Saturation + optional hue angle | `hue=s=s:h=h` |
| `hue` / `ccshue` | `hue=<deg>` | Hue shift via ImageMagick Hald CLUT preprocessing | Hald CLUT → FFmpeg overlay |
| `ffmpeghue` | `ffmpeghue=<deg>` | Hue shift directly via FFmpeg hue filter | `hue=h=deg` |
| `swapuv` | `swapuv` | Swap U and V chroma channels | `swapuv` |
| `invertrgb` | `invertrgb=<r>[;g][;b]` | Invert specific channels (1=invert, 0=keep) | `curves` with per-channel `0/1 1/0` |
| `invlum` | `invlum` | Invert luminosity only (built-in LUT) | `lut3d=InvertLuminosity.cube` or `curves=all='0/1 1/0'` |
| `gm4` | `gm4` | Selective colour boost | `selectivecolor=blacks='0 0 0 0':whites='1 1 1 1'` |
| `realgm4` | `realgm4` | Solarise via curves inversion | `curves=all='0/0 0.5/1 1/0'` |
| `channelblend` | `channelblend=<r>[;g][;b]` | Swap/mix RGB channels | `colorchannelmixer` with custom mapping |
| `zoom` | `zoom=<scale>` | Zoom and crop back to original size | `scale=iw*s:ih*s,crop=iw/s:ih/s:…` |
| `mirror` | `mirror=<left\|right\|top\|bottom>` | Fold left/right/top/bottom half to fill frame | `split`, `crop`, `hflip`/`vflip`, `hstack`/`vstack` |
| `mirror` | `mirror=<angle>[;cx][;cy]` | Parametric fold along any angle through centre point | `geq` with rotation/reflection math |
| `pan` | `pan=<px>[;py]` | Shift image by pixel offset (wraps at boundaries) | `format=yuv444p,geq='p(clip(X+px,…))'` |
| `tile` | `tile=<tx>[;ty]` | Tile image N×M times | `format=yuv444p,geq='p(mod(X*tx,W),…)'` |
| `ripple` | `ripple=[speed][;freq][;amp][;phase]` | Radial sinusoidal distortion from centre | `format=yuv444p,geq` with `hypot`/`sin` radial formula |
| `wave` | `wave=[hs][;hf][;ha][;hp][;vs][;vf][;va][;vp][;sep][;noclip]` | Sinusoidal pixel displacement (8 params + sep/noclip flags) | `format=yuv444p,geq` with `sin(T+…)` x/y formulas |
| `swirl` | `swirl=<strength>[;radius][;xc][;yc][;fallout][;is1to1]` | Vortex distortion. fallout: `linear` or `quad`. is1to1: square before swirl | Complex `geq` with polar coordinate math |
| `pinch&punch` / `p&p` | `pinch&punch=[strength][;radius][;cx][;cy]` | Radial pinch/punch barrel warp | `format=yuv444p,geq` with `gauss`/`hypot` formula |
| `gm91deform` | `gm91deform` | Perspective + barrel warp | `scale=360:360,rotate,geq` with `lerp`/`asin`/`pow` formula |
| `scroll` | `scroll=<h>[;v]` | Continuous scroll (0.0–1.0 per axis) | `scroll=hpos=h:vpos=v` |
| `scroll` | `scroll=hpos=<n>[;ypos=<n>]` | Named scroll params | `scroll=hpos=n:vpos=n` |
| `scroll` | `scroll=<x1>[;y1][;x2][;y2][;dur]` | Animated pan from (x1,y1) to (x2,y2) over dur seconds | `geq` with time-interpolated pixel expressions |
| `orb` | `orb` | Fisheye orb effect | `v360=fisheye:hammer:7` chain |
| `deorb` | `deorb` | Reverse orb | `v360=hammer:fisheye:7` chain |
| `vebfisheye2` | `vebfisheye2[=count]` | Double fisheye chain (repeated up to count times) | `v360=22:fisheye:7` × count |
| `vebdefisheye2` | `vebdefisheye2[=count]` | Inverse double fisheye | `v360=fisheye:22:7` × count |
| `vebfisheye3` | `vebfisheye3[=count]` | Triple fisheye chain | `v360=22:fisheye:7` × count, scaled ×2 |
| `vebdefisheye3` | `vebdefisheye3[=count]` | Inverse triple fisheye | `v360=fisheye:22:7` × count, scaled ×2 |
| `chromashift` | `chromashift` | Chroma shift using green/blue channel cross-displacement | `format=rgb24,geq=r='p(mod(…))':g=…:b=…,hue=s=0` |
| `shake` | `shake=[h_amt][;v_amt]` | Per-frame sinusoidal pixel displacement shake (default h=3) | `rotate=0:iw*1.1:ih*1.1,geq='p(X+h*sin(N*…))'` |
| `jitter` | `jitter=[strength]` | Crop-based per-frame jitter (deterministic) | `pad=iw+margin:ih+margin,crop=iw-margin:ih-margin:expr` |
| `randomjitter` | `randomjitter=[strength]` | Per-frame geq pixel jitter (pseudorandom, strength default 10) | `rotate:geq='p(X+expr_x,Y+expr_y)':crop` |
| `leftsplit` | `leftsplit=<inner_effects>` | Apply inner pipe effects to left half, mirror to right | crop left → apply effects → hstack + hflip |
| `rightsplit` | `rightsplit=<inner_effects>` | Apply inner pipe effects to right half, mirror to left | crop right → apply effects → hstack + hflip |
| `earthquake` / `nbfx` | `earthquake` | 2-pass vidstab destabilize shake (extreme camera shake) | `vidstabdetect` on shake sample → `vidstabtransform=invert=1` |
| `sierpinskiransomware` | `sierpinskiransomware` | Full 2×2 Sierpinski preset as a pipe step | See preset table |
| `preview1280` | `preview1280[=start][;dur]` | Full 12-segment TV-simulator montage as a pipe step | See `th/preview1280` |
| `oppositep1280` / `op1280` | `oppositep1280[=start][;dur]` | Opposite-polarity TV-simulator as a pipe step | See `th/oppositep1280` |
| `folkvalley` / `fv` | `folkvalley` | Folk Valley music + brightness boost + overlay as a pipe step | See `th/folkvalley` |
| `tvsim` / `tv` | `tvsim=<line_sync>[;zoom][;vsync][;phosphor][;interlace][;scan][;aperture][;static]` | CRT simulator as a pipe step | See `th/tvsim` |
| `speed` | `speed=<multiplier>` | Change playback speed (0.01–100×). Chains `atempo` for audio | `setpts=1/s*PTS` + chained `atempo` |
| `trim` | `trim=<start>[;end]` | Trim to time range (`hh:mm:ss` or seconds) | `ffmpeg -ss start -to end` |
| `vreverse` | `vreverse` | Reverse video frames | `reverse` |
| `avflip` | `avflip` | Extreme audio warp: rubberband tempo crush → afftfilt → expand | `rubberband=tempo=0.05…,afftfilt=…,rubberband=tempo=20…` |
| `nepeta` | `nepeta[=url]` | Overlay cat face PNG (downloads default or custom URL) | `overlay=0:0:repeatlast=1` |
| `watermark` | `watermark=<url>` | Overlay transparent PNG from URL | `overlay=0:0:repeatlast=1` |
| `ring` | `ring[=url]` | Frame overlay (default frame or custom URL) | `overlay` |
| `miui` | `miui` | MIUI-style watermark overlay | `overlay` |
| `reddit` | `reddit` | Reddit-style watermark overlay | `overlay` |
| `caption` | `caption=<text>` | Text at top-centre | `drawtext` |
| `frei0r` | `frei0r=<plugin>[;p1][;p2]…` | Any frei0r plugin with colon-separated params | `frei0r=plugin:p1:p2` |
| `ffmpeg(…)` | `ffmpeg(-vf hue=h=90)` | Raw FFmpeg args injected into the pipeline | Passed verbatim via `shlex.split` |
| `🥸🥸` | `🥸🥸` | Hue shift by π radians | `hue=h=3.14159265` |
| `﷽` | `﷽` | Equirectangular → ball → fisheye chain | `v360=e:ball,v360=fisheye:22:7` |
| `𒐫` | `𒐫` | Ball → hammer projection chain | `v360=ball:hammer` |

### Audio Effects

| Effect | Syntax | Description | FFmpeg filter |
|--------|--------|-------------|---------------|
| `multipitch` | `multipitch=<semitones>` | Multi-voice pitch shift. Semicolon-separated: `multipitch=1;6;7` | Signalsmith multi-pitch binary (x86-64) or `rubberband` fallback |
| `multipitch2` / `mp2` | `multipitch2=<semitones>` | Alternate multipitch path | `rubberband` pitch chain |
| `ssmp` / `soundstretchmultipitch` | `ssmp=<semitones>` | SoundTouch pitch shift (soundstretch binary) | `soundstretch` |
| `volume` | `volume=<val>` | Adjust volume multiplier | `volume=val` |
| `vibrato` | `vibrato=<freq>[;depth]` | Vibrato effect | `vibrato=f=freq:d=depth` |
| `areverse` | `areverse` | Reverse audio | `areverse,asetpts=PTS-STARTPTS` |
| `alimiter` | `alimiter=[li][;limit][;attack][;release][;latency]` | Audio limiter | `alimiter=level_in=li:limit=l:attack=a:release=r:latency=lat` |
| `acontrast` | `acontrast=[val]` | Audio contrast (default 33) | `acontrast=val` |
| `adestroy` | `adestroy` | Extreme audio contrast (5× stacked acontrast=100) | `acontrast=100` × 5 |
| `audioequalizer` | `audioequalizer=[40hz][;150hz][;375hz][;1000hz][;3000hz]` | 5-band parametric EQ (gain in dB) | `equalizer=f=40:…,equalizer=f=150:…` × 5 |
| `4ormulator` | `4ormulator=[dial]` | Formant shift via rubberband | `rubberband=tempo=1:formant=dial:pitch=1` |
| `vocoder` | `vocoder=<url>` | Vocoder (ilvocodex profile) | FFT phase vocoder pipeline |
| `vocoder` | `vocoder=<mode>[;bw][;url]` | Vocoder with explicit mode and bandwidth | FFT phase vocoder pipeline |
| `ilvocodex` | `ilvocodex=<url>` | Vocoder — ILVocodex profile (bw=256, window=1024, phases=6) | FFT phase vocoder |
| `orangevocoder` | `orangevocoder=<url>` | Vocoder — Orange Vocoder profile (bw=256, window=1024) | FFT phase vocoder |
| `audacity` | `audacity=<url>` | Vocoder — Audacity profile (bw=64, window=512, post_phases=12) | FFT phase vocoder |
| `freakzinga` / `fzgm156` / `fgm156` | `freakzinga[=samplerate]` | Palindrome video + dual-voice G major pitch shift + bass | Hald CLUT + multipitch binary + `amix` |
| `syncaudio` | `syncaudio[=mode]` | Sync audio track to video | See `th/syncaudio` |

### Raw Filter Passthrough

Skip the parser entirely and write raw FFmpeg filter strings:

```
VIDEO: hue=h=t*180:s=2,negate AUDIO: volume=2,acontrast=50
```

Both `VIDEO:` and `AUDIO:` blocks are optional — use either or both.

---

## Standalone Effect Commands

### `th/preview1280` / `th/p1280`

12-segment TV-simulator montage. Runs the full pipeline: Hald CLUTs, horizontal flips, mirror compositions, TV displacement mapping, rubberband pitch shifts per segment, final upscale.

```
th/preview1280 [start_offset] [segment_duration]
```

Defaults: start=1.85s, duration=0.85s.

**Requirements:** ImageMagick (`magick`), FFmpeg with `rubberband`, `bot/displacemaps/tvsimulator.mov`.

---

### `th/oppositep1280` / `th/op1280`

Same as `preview1280` but with inverse colour polarity. Aliases: `th/opposite`, `th/opposite1280`.

---

### `th/preview1280with640x360resize` / `th/p1280ff!3`

`preview1280` with 640×360 output resize. Alias: `th/p1280w16:9r`.

---

### `th/multipitch` / `th/mp`

Multi-voice pitch shift. Each semicolon-separated semitone value creates a separate pitch copy, all mixed together via `amix`.

```
th/multipitch <semitones;separated;by;semicolons>
th/multipitch 1;4;7
th/multipitch -3;0;5
```

**Pipeline:**
```
Its basically Rubberband R3 :/
```

---

### `th/soundstretchmultipitch` / `th/ssmp`

Multi-voice pitch shift via the SoundTouch `soundstretch` binary. Same semicolon syntax as `th/multipitch`.

---

### `th/ihtxsap` / `th/sap`

Audio-only effect: strip video, repeat N times, optional multipitch.

```
th/ihtxsap <reps> [duration] [pitches]
```

---

### `th/swirl` / `th/vortex`

Swirl/vortex distortion.

```
th/swirl <strength> [radius] [xc] [yc] [fallout] [is1to1]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `strength` | — | Swirl angle in degrees (required; negative = counter-swirl) |
| `radius` | `0.5` | Normalised radius 0–1 relative to `min(W,H)` |
| `xc` | `0.5` | Horizontal centre 0–1 |
| `yc` | `0.5` | Vertical centre 0–1 |
| `fallout` | `quad` | Attenuation curve: `linear` or `quad` |
| `is1to1` | `true` | Scale to square before swirl |

**Examples:**
```
th/swirl 180
th/swirl 360 0.5 0.5 0.5 quad false
th/swirl -90 0.3 0.25 0.75 linear
```

---

### `th/tvsim` / `th/tv`

CRT/TV simulator displacement effect. Requires a video attachment.

```
th/tvsim <line_sync> [detail_zoom] [vertical_sync] [phosphorescence] [interlacing] [scan_phasing] [aperture_grill] [static]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `line_sync` | — | 0–1 displacement strength (0=max CRT warp, 1=no warp). Required. |
| `detail_zoom` | `1` | Crop zoom on displacement map |
| `vertical_sync` | `1` | Vertical scroll speed (1=none) |
| `phosphorescence` | `0` | CRT phosphor colour tint (0=off) |
| `interlacing` | `0` | Scanline darkening (0=off) |
| `scan_phasing` | `0` | Scanline ripple/phase shift (0=off) |
| `aperture_grill` | `0` | Vertical phosphor stripe mask 0–1 (0=off) |
| `static` | `0` | TV static noise strength 0–1 (0=off) |

**Examples:**
```
th/tvsim 0.5
th/tvsim 0.3 1 1 0.4 0.5 0 0.6 0
th/tvsim 0.5 1 1 0 0 0 0 1
```

---

### `th/huehsv` / `th/hhsv`

Hue, saturation, and lightness shift via ImageMagick Hald CLUT.

```
th/huehsv [hue] [saturation] [lightness] [colorspace] [betterfully]
```

Defaults: hue=0.5, sat=1.0, lightness=1.0, colorspace=hsl.

---

### `th/mirror`

Mirror-fold effect with presets or parametric angle.

```
th/mirror [left|right|top|bottom]   — fold along axis
th/mirror [angle] [cx] [cy]         — fold along any angle through centre
```

Preset filters:
- `left` — crop left half, mirror to right
- `right` — crop right half, mirror to left
- `top` — crop top half, mirror to bottom
- `bottom` — crop bottom half, mirror to top

---

### `th/vocoder` / `th/vocode`

FFT phase vocoder: shape a carrier signal with the envelope of the attached audio.

```
th/vocoder <carrier_url>
th/vocoder <mode> <carrier_url>
th/vocoder <mode> <bandwidth> <carrier_url>
```

Modes: `ilvocodex` (default), `orangevocoder`, `4ormulator`, `audacity`

---

### `th/folkvalley` / `th/fv`

Folk Valley aesthetic: replaces audio with the folk valley music track, boosts brightness (HSV value shift), overlays a decorative image.

---

### `th/trim`

Trim media to a time range.

```
th/trim <start> <end>
th/trim 0:05 0:30
th/trim 10 45
```

---

### `th/syncaudio` / `th/sa`

Sync audio track to video.

```
th/syncaudio [mode: alt or leave it blank]
```

---

### `th/ffmpeg`

Run raw FFmpeg arguments directly on an attached file.

```
th/ffmpeg -vf hue=h=31.415926 -c:v libx264
```

---

### `th/ffmpegprocess` / `th/fmp`

FFmpeg with additional processing options and complex filter support.

---

### `th/png2lut` / `th/lut2cube`

Convert a PNG Hald CLUT image to a `.cube` LUT file.

---

### `th/lut2png` / `th/applylut`

Apply a `.cube` LUT file (provided as a URL) to an attached video or image.

```
th/lut2png <cube_url>
```

---

### `th/addsource`

Add an overlay source layer to a composition.

```
th/addsource <name> [url]
```

---

### `th/lexg` / `th/lec` (doesn't really work but ill fix it)

Grab the last N seconds of a video export.

```
th/lexg [duration]
th/lexg 5.0
```

---

### `th/multipitch2` / `th/mp2`

Alternate multipitch path using the rubberband chain directly.

---

### `th/catbox` / `th/cb` / `th/upload`

Upload an attached file to [catbox.moe](https://catbox.moe). If `CATBOX_USERHASH` is set, the upload is linked to your account; otherwise it's anonymous.

---

### `th/undo`

Delete the bot's last message in the current channel. (reply to it)

---

### `th/guesseffect` / `th/ge`

Guess which effect was applied to a randomly selected clip. Shows a scrambled name and pipeline clue.

---

## AI Chat

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/chat <question>` | `th/ask`, `th/ai` | Chat with the AI (Groq — Llama 3.3 70B Versatile). Text only. |
| `th/clearchat` | `th/resetai`, `th/chatclear` | Clear your personal AI chat history |

AI auto-reply can be enabled per-channel via `th/autoreply2`. Requires `GROQ_API_KEY`.

> **Heavy command:** `th/chat` counts toward the daily heavy-command limit.

---

## Fun & Games

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/8ball <question>` | `th/eightball` | Ask the magic 8-ball |
| `th/coinflip` | `th/flip`, `th/coin` | Flip a coin |
| `th/roll [sides]` | `th/dice`, `th/d` | Roll a die (default 6 sides) |
| `th/rps <choice>` | `th/rockpaperscissors` | Rock, paper, scissors |
| `th/choose <opt1\|opt2\|…>` | `th/pick` | Pick randomly from options |
| `th/rate <thing>` | | Rate something out of 10 |
| `th/slots` | `th/slot` | Spin the slot machine |
| `th/hangman` | `th/hm` | Play hangman |
| `th/blackjack` | `th/bj`, `th/21` | Play blackjack |
| `th/tictactoe` | `th/ttt` | Play tic-tac-toe |
| `th/trivia` | | Answer a trivia question |
| `th/random [subcommand]` | `th/rand` | Random pool: `add`, `remove`/`rm`/`del`, `list`, `clear` |

---

## XP & Levels

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/level [member]` | `th/rank`, `th/xp` | Check your (or another member's) XP and level |
| `th/leaderboard` | `th/lb`, `th/top` | Server XP leaderboard |

---

## Economy & Slash Commands (Economy Cog)

These are hybrid commands (available as both slash `/` and prefix `th/`):

| Command | Aliases | Description |
|---------|---------|-------------|
| `/ihtxgen` | — | Full slash interface to the IHTX pipeline (see [Core Interface](#core-interface--ihtxgen--thihtx)) |
| `th/ihtx` | `th/effect`, `th/destroy` | Prefix alias for `/ihtxgen` |
| `/profile [user]` | — | View a user's profile, wallet, bank, XP level, and inventory |
| `/ping` | — | Check WebSocket latency and message round-trip time |
| `/status` | — | Bot status: latency, uptime, server/user counts |
| `/jackpot` | — | Spin the slot machine for 200 XP jackpot (1-hour cooldown) |

---

## Garden (Garden Cog)

A farming mini-game. All commands are hybrid (slash + `th/` prefix):

| Command | Aliases | Description |
|---------|---------|-------------|
| `/garden` | — | View your garden plots and crop status |
| `/shop` | — | Browse seeds, saplings, boosters, and pet eggs |
| `/buy <item> [amount]` | — | Purchase seeds, saplings, boosters, or pet eggs |
| `/inventory` | `inv` | Show full inventory |
| `/plant <crop> <plot>` | — | Plant a seed or sapling in a specific plot (1-indexed) |
| `/water <plot>` | — | Water a crop to keep it alive |
| `/use <booster> [plot]` | — | Apply a booster item (e.g. `speed_fertilizer`) to a plot |
| `/pet <action> [pet_name]` | — | Manage pets: `equip` or `list` |
| `/harvest <plot>` | — | Harvest a fully grown crop or fruit |
| `/sell <item> [amount]` | — | Sell harvested crops or fruits for coins |
| `/wait <minutes>` | — | Simulate time passing so crops can grow |
| `/scare` | — | Scare off pests from your garden |
| `/gardenclear [plot]` | `gclear` | Clear dead plots (omit to clear all dead at once) |
| `/gardenboard` | `glb`, `gardenleaderboard` | Top garden coin earners |

---

## Utility Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/presets` | `th/effects`, `th/list` | List all available effect presets |
| `th/ihtxhelp [query]` | `th/bothelp` | Show help embed with full effect reference |
| `th/invite` | | Get the bot's invite link |
| `th/usage` | `th/heavyusage`, `th/limit`, `th/checklimit` | Check your heavy-command usage and reset time |

---

## Auto-Reply Management

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/autoreply <trigger> [channel] <response>` | `th/ar` | Add an auto-reply trigger |
| `th/removeautoreply <trigger>` | `th/rar`, `th/deautoreply` | Remove a trigger |
| `th/removearmentions <trigger>` | `th/rarm`, `th/noarping` | Disable @mention pings for a trigger |
| `th/blockarchannel <trigger> [channel]` | `th/bac`, `th/silencear` | Block a trigger in a specific channel |
| `th/autoreplies` | `th/listautoreplies`, `th/arlist` | List all auto-reply triggers |
| `th/autoreply2` | `th/ar2` | Toggle AI auto-reply in the current channel |
| `th/autoreply2list` | `th/ar2list` | List channels with AI auto-reply enabled |
| `th/removear2mentions <user>` | `th/rarm2`, `th/noar2ping` | Disable AI auto-reply pings for a specific user |

---

## Owner-Only Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `th/blockuser <id\|mention>` | | Block a user from using the bot |
| `th/unblockuser <id\|mention>` | | Unblock a user |
| `th/blockchannel [id\|mention]` | | Block a channel (current if omitted) |
| `th/unblockchannel [id\|mention]` | | Unblock a channel |
| `th/keywordblock <keyword> [channel]` | `th/blockkeyword`, `th/kb` | Block messages containing a keyword |
| `th/keywordblockremove <keyword> [channel]` | `th/unblockkeyword`, `th/kbr` | Remove a keyword block |
| `th/keywordblockmsg <keyword> <message>` | `th/kbmsg`, `th/blockmsg` | Set the auto-delete response message for a keyword |
| `th/say <message>` | | Send a plain message as the bot |
| `th/sayembed <title> \| <description>` | | Send an embed as the bot |
| `th/sendmsg <channel_id> <text>` | `th/msgsend` | Send a message to any channel by ID |
| `th/setactivity <type> <text>` | `th/activity`, `th/presence` | Set the bot's Discord activity/presence |
| `th/setlimit <user> <limit>` | `th/sl` | Set a custom heavy-command daily limit for a user |
| `th/resetlimit <user>` | `th/rl`, `th/resetusage` | Reset a user's heavy-command usage counter |
| `th/listservers` | `th/servers`, `th/guilds` | List all servers the bot is in |
| `th/listchannels <guild_id>` | `th/channels` | List channels in a server |
| `th/syncslash` | `th/synccmds`, `th/synctree`, `th/slashsync` | Register slash commands globally (bulk upsert) |

---

## Configuration

### Environment Variables / Secrets

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | **Yes** | Discord bot token |
| `GROQ_API_KEY` | **Yes** | Groq API key — enables `th/chat` and AI auto-reply (Llama 3.3 70B) |
| `CATBOX_USERHASH` | No | Catbox user hash — links uploads to your account; omit for anonymous uploads |

### Data Files (auto-created in `bot/`)

| File | Purpose |
|------|---------|
| `owner_ids.json` | Owner user IDs (full bot access) |
| `limits.json` | Per-user heavy-command daily limits |
| `blocklist.json` | Blocked user IDs |
| `channel_blocks.json` | Blocked channel IDs |
| `tags.json` / `tag_store.json` | Custom tag/preset definitions |
| `autoreply.json` | Auto-reply trigger configuration |
| `autoreply2.json` | Channels with AI auto-reply enabled |
| `autoreply2_no_mention.json` | Users with AI auto-reply pings disabled |
| `xp_data.json` | XP and level data |
| `economy_data.json` | Economy (wallet, bank, inventory) data |
| `garden_data.json` | Garden plot and crop data |
| `chat_profiles.json` | AI chat personalisation profiles |
| `usage.json` | Heavy-command usage tracking |
| `warnings.json` | User warning records |
| `random_pool.json` | Media pool for `th/random` |
| `keyword_blocks.json` | Blocked keywords per channel |
| `keyword_block_messages.json` | Custom responses for keyword blocks |

### Assets

| Path | Purpose |
|------|---------|
| `bot/displacemaps/tvsimulator.mov` | TV simulator displacement map (`preview1280`, `tvsim`) |
| `bot/InvertLuminosity.cube` | Built-in LUT for `invlum` |
| `bot/fileaa` | Signalsmith multi-pitch binary (x86-64, auto-downloaded at startup) |

### Constants (edit in source)

- `MAX_FILE_SIZE` — 25 MB (Discord upload limit)
- `MAX_DURATION` — 600 seconds
- `MAX_REPETITIONS` — 100
- `HEAVY_LIMIT_DEFAULT` — 20 heavy commands per 24h for non-owners
- Command prefix: `th/` (configurable via `bot/config.json` → `bot_prefix`)

### `bot/config.json`

```json
{
  "DISCORD_TOKEN": "",
  "GROQ_API_KEY": "",
  "bot_prefix": "th/",
  "SYSTEM_PROMPT": "You are a charismatic, witty, and multilingual AI assistant…"
}
```

Token and key values in `config.json` are overridden by environment variables / Replit Secrets.

---

## Heavy Commands

The following commands count toward the per-user daily limit (default 20/day for non-owners):

`ihtxgen`, `ihtx`/`effect`/`destroy`, `preview1280`, `oppositep1280`, `preview1280with640x360resize`, `multipitch`, `lexg`, `chat`/`ask`/`ai`, `ihtxsap`

---

## Project Structure

```
├── bot/
│   ├── ihtx_bot.py               # Main bot: effects, AI, games, moderation
│   ├── economy_cog.py            # Economy cog: /ihtxgen, /profile, /ping, /status, /jackpot
│   ├── garden_cog.py             # Garden mini-game cog
│   ├── catbox_upload.py          # CLI catbox upload wrapper
│   ├── displacemaps/             # FFmpeg displacement assets
│   │   └── tvsimulator.mov
│   ├── InvertLuminosity.cube     # Luma-inversion LUT
│   ├── fileaa                    # Signalsmith multi-pitch binary (x86-64)
│   ├── config.json               # Bot config (prefix, system prompt)
│   ├── config.json.template      # Config template
│   ├── owner_ids.json
│   ├── limits.json
│   ├── tags.json / tag_store.json
│   ├── autoreply.json
│   ├── autoreply2.json
│   ├── blocklist.json
│   ├── channel_blocks.json
│   ├── xp_data.json
│   ├── economy_data.json
│   ├── garden_data.json
│   └── random_pool.json
├── main.py                       # Entry point
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container build
├── .replit                       # Replit configuration
├── replit.nix                    # Nix system deps (ffmpeg, sox, imagemagick)
└── AutotuneBot/                  # Standalone autotune bot (separate module)
```

---

## License

Private project — all rights reserved.
# end.
