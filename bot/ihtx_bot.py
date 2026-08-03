"""
IHTX Bot — I Hate The X FFmpeg Discord Bot

Full implementation with preset effects, custom effect chaining (th/ihtx),
and the preview1280 TV-simulator montage command.

Dependencies required at runtime: ffmpeg, aiohttp, discord.py, optionally yt-dlp,
ImageMagick/sox/etc. depending on advanced effects.

_UPDATELOG (newest first):
- 2026-08-03: [Python/TypeScript] Switched pitchtransition from FFmpeg's `rubberband=phase=712923000` filter to native Rubber Band R3 (`rubberband-r3 -3 --pitchmap`) for dynamic pitch sweeps; finite padding and MOV PCM output remain intact.
- 2026-08-03: [Python/TypeScript] Final MOV pitchtransition outputs now encode audio with `-c:a pcm_s16le`; MP4 remains AAC for container compatibility.
- 2026-08-03: [Python/TypeScript] Fixed pitchtransition start truncation by removing the post-Rubber-Band front trim; timestamp normalization now preserves the source beginning while retaining the finite tail.
- 2026-08-03: [Python/TypeScript] Fixed pitchtransition endpoint truncation by retaining a finite latency tail through the audio render, mux, IHTX base render, and trim passes; bounded padding prevents runaway WAV output.
- 2026-08-03: [Python/TypeScript] Preserved the final pitchtransition endpoint by padding audio before Rubber Band processing, then compensating latency and trimming only after the tail is emitted.
- 2026-08-03: [Python/TypeScript] Fixed pitchtransition export delay by compensating Rubber Band look-ahead and resetting audio/video PTS during per-export trim and final concat; full IHTX output now starts both streams at t=0.
- 2026-08-03: [Python] Added a dedicated pitchtransition parser branch so custom IHTX exports preserve the full decimal `start,end[;start,end]` parameter as one raw value.
- 2026-08-03: [Python] Preserved raw pitchtransition pair parameters through the IHTX export preprocessor so decimal values such as `-4.5,5` reach the Rubber Band automation unchanged.
- 2026-08-03: [Python] Fixed standalone `pitchtransition -4.5,5` parsing so its comma remains part of the start/end pair instead of being treated as an effect delimiter.
- 2026-08-03: [Python/TypeScript] Pitchtransition now accepts decimal and exponent pitch values and normalizes multi-voice mixing; solo transitions bypass amix to preserve the reference behavior.
- 2026-08-02: [Python/TypeScript] Added `pitchtransition` / `pitchtrans` as a standalone and pipe-effect time-varying Rubber Band pitch sweep with optional multi-voice mixing.
- 2026-08-02: [Python/TypeScript] Fixed adjacent pipe assignments such as `mp=-7|7 volume=2`: the parser now keeps each effect separate instead of attaching the next effect as a parameter.
- 2026-08-02: [Python] Pipe chains now automatically skip unknown effect names while preserving valid effects; an all-unknown chain returns the original media unchanged.
- 2026-08-02: [Python] Added Uguu upload fallback when Catbox fails, plus th/uguu (alias ugupload) for direct file/video uploads.
- 2026-08-02: [Python] Added th/funfact (aliases: fact, ihtxfact) with rotating facts about the IHTX bot and listed it in the th/bothelp Fun category.
- 2026-08-02: [Python] Fixed autoreply2 silently not responding during Groq 429 quota exhaustion; it now sends a local status reply and temporarily skips repeated failed API calls.
- 2026-08-02: [Python] Added brother-bot awareness to chatbot prompts: 534gurts recognizes its brotherly bot by BOT ID 1523928952693981274.
- 2026-08-02: [Python] Updated the volume pipe effect to explicitly encode processed audio with `-c:a aac` instead of the shared PCM intermediate codec.
- 2026-08-02: [Python] Made autoreply2 dramatically more excited when the primary BOT_OWNER_ID owner speaks, with celebratory greetings, high-energy enthusiasm, and affectionate appreciation.
- 2026-08-02: [Python] Added explicit 534gurts identity to the chatbot and autoreply2 prompts so AI replies identify the bot correctly.
- 2026-08-02: [Python] Updated autoreply2 context so it knows the bot command reference in every reply path and recognizes the primary BOT_OWNER_ID with a joyful owner-specific tone.
- 2026-08-02: [Python/TypeScript] Added utility th/effectconfig (alias th/ec) to normalize pipe-effect parameters separated by =, ;, commas, or spaces into canonical effect=param;param configuration.
- 2026-08-02: [TypeScript] Fixed scgv pipe filtergraph labels and added FFmpeg sidechain-gate parameter validation; invalid detection/threshold values now fail clearly before processing.
- 2026-08-02: [Python/TypeScript] Restarted both bot workflows after adding TypeScript scgv as a pipe effect and standalone command.
- 2026-08-02: [Python] Fixed th/pipetest error reporting to clip oversized FFmpeg diagnostics before Discord replies/edits, preventing the 2,000-character Invalid Form Body error.
- 2026-08-02: [Python] Added Easy, Normal, and Hard difficulty modes to th/nightshift; Easy slows battery drain and monster movement, Hard increases both, and Normal remains the default.
- 2026-08-02: [Python] Converted th/nightshift into a hybrid command; it now starts the same interactive game from either `th/nightshift` or `/nightshift`.
- 2026-08-02: [Python] Added /nightshift, a Pillow-rendered interactive horror game with in-memory office/camera/jumpscare frames, power drain, moving threats, and owner-locked controls.
- 2026-08-02: [Python] Removed VEB's automatic bot-mention reply-to-video random pipe-effect trigger; normal `th/veb` and media reply handling remain available.
- 2026-08-02: [Python/TypeScript] Raised the maximum pitch-value count to 100 for ihtxsap, multipitch, multipitch2, multipitch3, and multipitchsox.
- 2026-08-02: [Python] Added a th/bothelp guide for newer IHTX filters, including scgv, gradientmap, labadjust, wave, and frei0r plugin syntax.
- 2026-08-01: [Python] Implemented th/ihtx no_trim argument after duration: true/yes/+ preserves full-length source and exports; false/no/- loops and trims each step to duration.
- 2026-08-01: [Python] Added optional overlay start offset to th/addsource; the fifth positional value snips the overlay from its beginning, e.g. `th/addsource URL 3x3 5 0.5 0.4`.
- 2026-08-01: [Python] Added a startup notification in the configured Discord channel after each bot process restart, reporting the newest update-log change or restart reason.
- 2026-08-01: [Python] Preserved Bash `${...}` parameter expansions while resolving nested TagScript placeholders, preventing generated filenames such as `$.mov`.
- 2026-08-01: [Python] Fixed Bash tags so nested TagScript variables and argument blocks resolve before execution; FFmpeg wrappers now emit errors only instead of leaking input metadata.
- 2026-08-01: [Python] Increased owner Bash tag execution to a 300-second media-safe timeout and suppressed FFmpeg build banners so long Bash/FFmpeg tags return useful output instead of a truncated banner.
- 2026-08-01: [Python] Made Bash tag execution translate legacy `load {iv}` media directives into a downloaded `FILE_1` input instead of passing `load` to Bash.
- 2026-08-01: [Python] Fixed th/tag Bash blocks to execute through `bash -lc` instead of Python's `/bin/sh` shell path, preserving Bash syntax for multiline owner-only tags.
- 2026-08-01: [Python] Updated the custom th/ihtx completion footer to “th/ihtx is ready!” and added a one-time author mention when generation reaches its halfway stage.
- 2026-07-29: [Python/TypeScript] Updated th/klaskycsupo to the new Discord CDN youtube-Jv5OyY_GJDY.mp4 clip and th/klaskysource to the new convert.mp4 clip in both bot implementations.
- 2026-07-29: [Python/TypeScript] Added a Utility category to th/bothelp with klaskycsupo, klaskysource, presets, and bothelp entries. Added Python th/klaskysource (alias klasky) and updated both bots to use the new Discord CDN Project_Name .mov URL.
- 2026-07-29: [Python] Fixed th/bothelp category and pagination interaction failures by deferring Discord component interactions immediately before preparing local preview attachments, then editing the original response; errors now use follow-up messages after defer.
- 2026-07-29: [Python] Restored a clearly visible th/bothelp home embed after removing the broken smiley: added separate Heavy, Fun, Games, and Owner category fields with counts and descriptions; kept the smiley fully removed.
- 2026-07-29: [Python] Removed the broken Python smiley reference from th/bothelp completely: no home image, no smiley attachment on Home navigation, and no smiley fallback for effects without dedicated previews. Dedicated local effect PNG/GIF previews remain enabled.
- 2026-07-29: [Python] th/bothelp effect previews now use the generated local PNG/GIF files in bot/help_previews and attach the selected preview directly to Discord, replacing unreliable zero-byte Catbox URLs. Category selection and Prev/Next navigation replace the attachment and embed image together.
- 2026-07-29: [Python] Fixed the missing th/bothelp smiley preview by attaching the local bot/help_previews/smiley_reference.png directly to the Discord help message and using attachment://smiley_reference.png instead of the zero-byte Catbox URL.
- 2026-07-29: [Python] Removed the remaining bothelp thumbnail image so the help embed uses only its configured main image/preview.
- 2026-07-29: [Python] Added th/set <user_id> owner|mod|remove — owner-only command to grant/revoke owner or moderator status. Mods (is_mod=True in xp_data) can now use th/say, th/sayembed, th/sendmsg (all three switched from _is_owner to _is_bot_mod). _is_bot_mod now reads from in-memory _xp_data instead of re-reading file on every check. Removed th/ban, th/unban, th/kick, th/timeout, th/untimeout, th/purge, th/slowmode from help entries. Fixed th/bothelp home embed: moved bot icon to footer icon_url so set_image(smiley_ref) is the sole embed image and renders correctly in Discord.
- 2026-07-28: [Python] th/bothelp: home embed now shows smiley-face reference image (Python-art PNG on Catbox); category browsing switched to 1 entry per page so each effect shows its Catbox preview image (GIF for animated, PNG for static) via set_image(). Added _SMILEY_REF_URL and _HELP_ENTRY_PREVIEWS dict. economy_cog.py: video outputs no longer use set_image(attachment://…) — only image outputs (.png/.jpg/.gif/.webp etc.) set the embed image; video files attach without set_image so Discord renders a native video player in the same message.
- 2026-07-27: [Python] Fixed `_preprocess_math_expr` collapsing colon-separated FFmpeg values (e.g. `scale=$w:$h` → `640:640` → incorrectly collapsed to `640640`): `_MathParser` is now only called when the expression is pure math (matches `_PURE_MATH_RE = ^[\d\s+\-*/^%().]+$`); strings containing `:`, `=`, letters, etc. are returned as-is after variable substitution.
- 2026-07-27: [Python] All output filenames now include bot-prefix: `534gurts_` → `534gurts_th` (e.g. `534gurts_thpipetest.mp4`, `534gurts_thffmpeg.mp4`). Added `*T` as alias for `$T` (normalized time 0→1) in pipe-effect math expressions and in th/ffmpeg raw arg substitution — use `*T` anywhere `$T` works (e.g. `frei0r=distort0r:*T`).
- 2026-07-26: [Python] ffmpeg() pipe effect: apply _preprocess_math_expr to raw args before shlex.split so $fc/$vd/$d/$sr/$fr/$f/$w/$h are substituted (effect is in _RAW_ARG_EFFECTS so _preprocess_param was skipped).
- 2026-07-26: [Python] th/ffmpeg: substitute $sr/$fr/$f/$d/$vd/$w/$h/$fc with ffprobe values before shlex.split (uses _gather_media_metadata; skipped if no $ vars present).
- 2026-07-26: [Python] mpsox: pad audio back to original duration (apad=whole_dur + -t) to prevent sox bend trim from shortening the video by a few milliseconds.
- 2026-07-26: [Python] Added multipitchsox/mpsox pipe effect — sox bend multi-voice pitch shift; single pitch: bend→highpass=5 remux; multi-pitch: bend per voice→amix+highpass=17.5 remux. Ports TypeScript renderPitchBentVideo() pipeline.
- 2026-07-25: [Python] Added bot/fileaa_seg standalone binary — segmented fileaa video pipeline; splits video into --seg N second chunks (default 0.4s), per segment: extract ultrafast/qp1/pcm_s16le, extract WAV, run fileaa with any pitch engine flag (--bungee/--backend/--soundtouch/--basic/--rubberband-args/--preserve-formants/--no-normalize), remux, then concatenate all segments. Removed th/fileaa Discord command (same pipeline now lives in the binary).
- 2026-07-25: [Python] Added th/sidechaingate_vocoder (alias: th/scgv) and scgv pipe effect — ports TypeScript generateVocoderCommand() filtergraph to Python FFmpeg: firequalizer band-split (mod+carrier), sidechaingate per-band, amix+crystalizer+alimiter output; params: carrier_url, bw=64, ratio=2, threshold=1, release=50, attack=0.01, makeup=1, knee=8, detection=peak, range=0, volume=1, pitch=0. Fixed th/convert to use slash-separated format string (th/convert mov/png/flac) instead of three separate args. Replaced all .mov output generators with .mp4: bytebeat_cog.py (waveform render + discord.File filename), ihtx_bot.py get_output_ext(), pipe engine temp files, invlum, p1280, op1280, p1280r, preview1280what, multipitch, ssmp, mpb, repeat, concatenate, join. Added th/convert (alias: conv) — converts an attached video into video fmt + audio fmt + image fmt simultaneously (defaults: mp4/mp3/png); runs all three FFmpeg jobs in parallel; falls back to Catbox for oversized video output.
- 2026-07-24: [Python] Added th/preview1280what (aliases: p1280what, p1280fev8v2plus) — 28-segment TV-simulator extended montage (preview1280 FFmpeg Extended v8 v2+). 4 full segs + 23 half segs + 1 looping long seg; optional use_tempo param for rubberband time-stretch. Output is .mov (pwhatextended). Added to th/ihtxhelp Fun section. Removed set_thumbnail from all command result embeds (p1280, op1280, p1280r, swirl, fzte, tvsim, folkvalley). Added gif thumbnail (_IHTX_SAP_FOOTER_ICON) to th/ihtxhelp overview and all section pages.
- 2026-07-23: [Python] Removed preview1280/p1280, oppositep1280/op1280, preview1280with640x360resize/p1280ff!3/p1280w16:9r, and multipitch/mp/multi from HEAVY_COMMANDS (no longer rate-limited). Moved their _HELP_ENTRIES category from "heavy" to "fun". Updated th/help (TypeScript): moved preview1280/multipitch out of Heavy Effects into Video Tools section; added missing commands (tvsim, swirl, folkvalley, vocoder, download, videolength, bytebeat, wave, submiteffect, listeffects, invite); split Games into TS-only and Python-only subsections; added numguess, scramble, typerace, mathquiz to Python games; merged Info+Limits into one field.
- 2026-07-23: [Python] Fixed `labadjust` output unplayable: switched to `-c:a copy` with no explicit video codec (matches huehsv/ccshue pattern exactly), so the output container/codec follows output_path extension. Updated `_concat_codec_args` formats (mkv/mxf/mov/mp4/avi) to use `-bufsize 16M -threads 0 -crf 25 -preset veryfast`; wired `export_format` through to final concat output in tagscript workflow (no longer hardcoded to mp4). Fixed `labadjust` haldclut "Failed to configure input pad" error: switched from `-filter_complex "[1:v][0:v]haldclut"` to `-vf "movie={lut_path},[in]haldclut,format=yuv420p"`. Added pipe-effect variables `$d` (duration alias for `$vd`), `$fr` (frame rate alias for `$f`), `$w` (video width px), `$h` (video height px).
- 2026-07-22: [Python] `th/effectlist` now paginates with ◀/▶ buttons (10 per page). Added `games` tab to `th/ihtxhelp` covering all game commands (8ball, coinflip, roll, rps, choose, rate, slots, numguess, scramble, typerace, mathquiz, trivia). Updated tvsim help entry to match renamed params (curvature→line_sync→detail_zoom order). Added `labadjust=l;a;b` to the pipe effects summary entry in ihtxhelp.
- 2026-07-21: [Python] Removed peak normalization from `_run_vocoder` (the `result / peak * 0.88` step before writing vocoded.wav); the alimiter post-filter still applies per-profile.
- 2026-07-21: [Python] Re-matched `_run_tvsim` to latest TypeScript runTvSimulator: param 0 renamed `curvature` (was `line_sync`); new param 1 `line_sync` = zoom factor for interlace/scanphase filters and displacement map Y-stretch; param 2 `detail_zoom` now controls scroll speed (was crop zoom); param 3 `vertical_sync` now controls phosphor lutrgb (was scroll); param 4 `phosphorescence` now interlacing scanlines (centered sin, line_sync-aware); param 5 `interlacing` now scan phasing (cos when curved / -sin when flat, line_sync-aware); scan phasing formula branches on `is_curved`; grill/static inputs now processed with `syncFilter` (center-zoom geq when line_sync!=1); disp map gets Y-stretch geq when line_sync!=1; base gray background changed to `#808080`; trivial case (flat+no grill+no static) uses simple -vf or copy. Standalone `th/tvsim` command updated to match new param order and defaults. Added `labadjust`/`labadj` pipe effect: negates selected Lab color channels (l/a/b params 0 or 1) via ImageMagick hald:8 HALD CLUT and FFmpeg haldclut filter.
- 2026-07-21: [Python] Updated `_run_tvsim` (standalone command + pipe effect) to match TypeScript runTVSimulator: interlacing formula now centered sin with detail_zoom-aware frequency (`sin(0.5+(Y/H-0.5)*(300/dz))`); scan_phasing now uses `-sin` with detail_zoom-aware frequency and period 4.833333 (was `cos(...period=5)`); aperture_grill now uses external PNG (`tv_simulator_aperture_grill.png`) + `blend=multiply` + `huesaturation` instead of geq mask; static now uses external MP4 (`tv_simulator_static.mp4`) + `blend=overlay` instead of FFmpeg noise filter; optional filters now applied *after* displacement (not before); added `_TVSIM_APERTURE_GRILL_URL` and `_TVSIM_STATIC_URL` constants.
- 2026-07-21: [Python] Raised Catbox upload threshold from 8 MB to 10 MB (CATBOX_THRESHOLD constant + hardcoded site in th/repeat); updated all user-facing messages accordingly. Fixed Catbox video playback: `_upload_to_catbox` now transcodes video files to web-compatible MP4 (H.264/AAC, +faststart) via `_transcode_to_web_mp4` before uploading, so videos play correctly in browsers and Discord embeds. Catbox upload timeout increased from 60 s to 120 s.
- 2026-07-20: [Python] Fixed `swirl` pipe effect to accept FFmpeg expression strings for `strength` (e.g. `swirl=0.05*T/$vd`): changed call site from `_pfloat` (silently fell back to 180.0) to `_expr_param` which preserves non-numeric strings; updated `_run_swirl` signature to `strength: float | str`.
- 2026-07-20: [Python] Fixed `_split_pipe_segments` to use universal paren-depth tracking (any `(` increments depth, any `)` decrements) instead of the `_FUNC_NAMES` whitelist. Previously, functions not in the whitelist (e.g. `lerp`, `gauss`, `hypot`) had their internal commas treated as pipe-segment delimiters, causing `lerp(0,1,N/$fc)` to split into three bogus segments and land unexpanded inside geq expressions.
- 2026-07-20: [Web] Added expression variable system to public/serve.mjs pipe engine: `$vd` (duration s), `$fc` (frame count), `$f` (FPS), `$sr` (sample rate) are substituted with literal numbers before FFmpeg; `lerp(a,b,t)` expands to `((a)+((b)-(a))*(t))`; `T`/`t` (time) and `N`/`n` (frame#) pass through as native FFmpeg expression variables. Pipe segment splitter is now parenthesis/quote-aware so `lerp(0,1,N/$fc)` commas are never treated as effect separators. Added `pinch&punch`/`p&p`/`pinchpunch` effect (geq-based Gaussian pinch distortion; params: strength;radius;cx;cy, all accept expressions). Fixed `swirl` to accept expression strings for strength (e.g. `swirl=0.05*T/$vd`). Usage examples: `swirl=0.05*T/$vd`, `p&p=1;0.5;lerp(0,1,N/$fc)`.
- 2026-07-18: [TS] Removed `th/multipitchihtx` command and its source file (it was already unwired from the dispatcher).
- 2026-07-18: [TS] Added `th/videolength` (aliases: vidlen, videolen) — runs ffprobe on a URL and returns the duration formatted as H:MM:SS.ss plus raw seconds.
- 2026-07-18: Added `magix` vocoder mode (window_size=2048, bandwidth=256, alimiter=0.5) — mirrors the exe's `-w 2048 -v 10 -N` flags; available as `th/vocoder magix <url>`, `magix=url` pipe shortcut, and `vocoder=magix;url`.
- 2026-07-18: Added `geq` as a direct pipe effect (`geq='expr'`, auto-wraps in `format=yuv444p/scale=iw:ih/format=yuv420p`); fixed `_split_pipe_segments` to track quote context so commas/parens inside `'...'`/`"..."` are never treated as delimiters (fixes `ffmpeg(-vf geq='p(X,Y)')` depth miscounting and `geq='expr'` direct pipe step); fixed `th/ffmpeg` (`ffmpegprocess.ts`) to use shell-style arg tokenization that strips surrounding quotes so `geq='p(X,Y)'` reaches FFmpeg correctly.
- 2026-07-18: Added `reverse=true` option to `th/ihtxsap` (Python) and `/ihtxsap` + `th/ihtxsap` (TypeScript) — reverses the extracted audio clip via `areverse` before pitch processing; keyword arg in both prefix and slash modes.
- 2026-07-17: `swirl` `is1to1` default restored to `true`. Expanded AI chatbot system prompt (`_CHAT_SYSTEM_PROMPT`) and autoreply2 command ref (`_AR2_COMMAND_REF`) with full `th/ihtx` usage: both preset mode and pipe mode args (`exports`, `duration`, `no_trim`, `format`, `effects`), all pipe effect names, and math variable reference ($fc/$vd/$f/$sr).
- 2026-07-17: Updated `swirl`/`vortex` pipe effect and standalone command — angle formula now matches TypeScript: `amount*(PI²)*(-255/180)` (replaces old `strength/180*PI`); default `is1to1` was temporarily set to `false` then restored to `true`; standalone default `amount` changed from 180 → 1; pipe-effect default `is1to1` updated to match.
- 2026-07-17: Added `(=)` pipe effect: `v360=ball:e → hue=h=450*t/$vd → v360=e:9` (ball-projection with time-varying hue spin). Added `(<>)` pipe effect: `v360=e:9 → earthquake → hue=s=2*t/$vd → v360=9:e` (equirect→ball projection, vidstab destabilize shake, saturation spin, deproject back).
- 2026-07-17: Fixed `ffmpeg()` pipe step crashing with "unconnected output" when user provides `-filter_complex` with a named video output (e.g. `[out]`) alongside `-map 0:a` — bot now auto-detects final unconnected filter labels (appear exactly once, are not stream specifiers) and injects `-map [label]` before the user's audio map.
- 2026-07-17: Added `th/uptime` (alias `up`) — shows bot uptime, render count, and servers. Added 4 new games: `th/numguess`/`ng` (number guessing 1–100, 7 tries), `th/scramble`/`ws` (word scramble, 30s), `th/typerace`/`tr` (WPM typing race), `th/mathquiz`/`mq` (5 math questions, 10s each). Bot custom status now tracks render completions — `_renders_completed` increments on each successful Catbox upload and the Playing status updates to "Made N renders in X servers!" (respects activity.json override). `on_guild_join`/`on_guild_remove` updated to use the same presence helper.
- 2026-07-17: Fixed `gradientmap`/`gmap` pipe effect dropping audio — added `-map 0:a?` alongside `-map [v]` so the input audio stream is passed through. Fixed `th/addsource` trim mode overlay being longer than N seconds — added `trim=0:{t},setpts=PTS-STARTPTS` to the overlay `[1:v]` filter chain.
- 2026-07-16: Tag system made global — tags are now shared across all servers. Existing per-guild tags in tag_store.json are auto-migrated to a single "global" namespace on first load. Storage layer rewritten; cog UI updated (list/stats/info/random show global counts and guild_origin).
- 2026-07-16: Both bots: raised `th/ihtxsap` max repetitions from 100 → 1000.
- 2026-07-16: Both bots: added `th/repeat [n]` (aliases: rep, loop) — repeats a video/GIF/audio N times (default 2, max 10) via FFmpeg concat demuxer. Removed `trim`, `chat`, `ask`, `ai`, `lexg` from HEAVY_COMMANDS (not computationally heavy). Added wave preset support to pipe effects: `wave=largeWave`, `wave=mediumWave`, `wave=smallWave`, `wave=horizontalOnly`, `wave=verticalOnly`, and `wave=custom:<params>`. Fixed `th/pipetest` to route both `wave` and `gradientmap` effects.
- 2026-07-15: Both bots: wave phase reverted to `(Y/H)*PI` / `(X/W)*PI` (restores half-sine widening shape); added `scale=iw:ih` after geq in both bots to preserve output aspect ratio; removed `setsar=1:1` from TS bot. The `-0.5` centered variant turned the bulge into an S-curve shear and is incompatible with the expected widening look.
- 2026-07-15: Both bots: wave formula now uses `W/640` amplitude scaling (same visual strength at any resolution). Previously the Python bot used flat `-15*amp` pixels with no size compensation, so bigger videos got a proportionally weaker effect.
- 2026-07-15: TS bot: fixed `applyWave` vertical offset — spatial phase now uses `(Y/H-0.5)` and `(X/W-0.5)` so the sine sweeps symmetrically around 0; the old `(Y/H)*PI` formula swept only a half-cycle whose mean is 2/π ≈ 0.64, adding a constant pixel shift to the whole image.
- 2026-07-15: TS bot: fixed `applyWave` amplitude scaling — displacement is now multiplied by `W/640` so the visual effect is proportional to native resolution (matches old scale-to-640/scale-back behaviour without a dimension probe). Added `th/klaskysource` (alias `th/klasky`) command to TS bot — downloads and re-attaches the Klasky source clip; falls back to Catbox if the file exceeds the guild upload limit.
- 2026-07-14: Added `gradientmap` as a TypeScript pipe effect in `artifacts/discord-bot/src/effects.ts` and exposed a `th/pipetest` (alias `th/pt`) one-shot runner that validates the `ProcessorContext` integration.
- 2026-07-14: Added standalone ESM gradientmap script at `scripts/src/gradient_map.ts` and updated the TypeScript `th/gradientmap` / `th/gm` command to expose the same `ColorStop`/`GradientMapOptions` API and synchronous `applyGradientMap` helper.
- 2026-07-16: Added `$vd` (duration s), `$sr` (sample rate Hz), `$f` (FPS) as th/ihtx pipe-effect math variables alongside the existing `$fc` (frame count). All four are substituted before lerp/math evaluation.
- 2026-07-16: Updated `th/addsource`: new optional `trim_duration` arg applies reverse→trim→reverse (end-trim) to base video and areverse→atrim→areverse to audio via named filter labels `[out_v]`/`[out_a]`; audio always from base track when trim is used. `--base-audio` flag retained for no-trim mode.
- 2026-07-16: Updated `imagemagick`/`im` pipe effect: switched frame format to PPM (faster magick I/O), frames now processed in parallel via ThreadPoolExecutor (in-place), `-r fps` passed to both extraction and reassembly, vf filter changed to `scale=-1:floor(ih/2)*2,setsar=1:1` (only force-even height).
- 2026-07-16: Added `imagemagick`/`im` pipe effect: applies arbitrary ImageMagick args to a video (frame-by-frame extract→magick→reassemble with audio) or directly to a static image. Usage: `imagemagick=-monochrome`, `im=-blur 0x8|-edge|1`.
- 2026-07-15: Fixed `th/download` for YouTube/TikTok-style URLs: removed the direct-download fallback that produced HTML `.bin` files when yt-dlp failed; matched the yt-dlp format selector to the TypeScript bot; filtered `.part`/`.ytdl` leftovers; added magic-bytes sniffing and `.bin` renaming for any generic download.
- 2026-07-14: Re-added Python `gradientmap`/`gmap` pipe effect to the Python bot with the same ColorStop/GradientMapOptions logic as the TypeScript bot, so `th/ihtx gradientmap=...` works on both bots.
- 2026-07-14: Hardened `gradientmap`/`gmap` parsing: now accepts double-bracket `[[...]]`, single-bracket `[...]`, colon/space-separated values, bare number groups, and JSON/flat-list gradient files from URLs or attachments. Error messages now report how many points were actually parsed.
- 2026-07-14: `gradientmap`/`gmap` now supports unlimited color points via external sources: a `url:https://...` point list (works in both standalone `th/gradientmap` and the `th/ihtx` pipe effect) or a `.txt`/`.csv`/`.json` gradient file attached alongside the media for the standalone command.
- 2026-07-14: Added `spherize` pipe effect (aliases `sphere`, `bulge`) — Vegas-style bulge/spherize distortion via FFmpeg geq. Params: `amount|radius|center_x|center_y` (default `0.8|0.5|0.5|0.5`). Added to the pipe effects list in `th/ihtxhelp`. Also added `th/download` (alias `th/dl`) — generic media downloader for any URL including Discord CDN links. Also reordered `th/ihtxsap` pitch styles and added `Rubberband Custom` with `rubberbandcustom=...` arbitrary flag support.
- 2026-07-13: User-submitted effects (`th/submiteffect`) are now global across all guilds and record the guild name/id. Added `th/randomlist` embed showing every random-pool entry and who/guild added it. Random pool entries now store author/guild metadata. Blocked users and blocked channels are now also enforced for slash (/) commands via `bot.tree.interaction_check`. Added `th/effectlist` alias to `th/listeffects`. Fixed th/unblockuser — owners are now exempt from the user-blocklist check in _global_checks, so a blocked owner can still run unblockuser (and can never be silently blocked from owner commands). Added BOT_OWNER_ID env var support to set the primary owner without editing code.
- 2026-07-13: Added th/submiteffect (aliases: se, addeffect), th/listeffects (le), th/deleteeffect — user-submitted named pipe effects stored in bot/user_effects.json and auto-expanded in _parse_pipe_effects. Removed effect label from th/ihtx queue header, live ticker, and result embed Effect: fields.
- 2026-07-12: Switched bot presence to `Playing "Making Effects in {N} servers!"` — updates live on guild join/leave via `on_guild_join`/`on_guild_remove` handlers. Only applies when no saved `activity.json` overrides it.
- 2026-07-12: Replaced `zoom` pipe effect with geq pixel-remap (ports TS logic): `zoom=2` zooms in, `zoom=0.5` zooms out with black bars, default `1.5`. Fixed crash when s < 1.
- 2026-07-12: Added per-voice volume boost to multipitch pipe effect (bungee + normal): volume = number of voices during remux (2 voices → volume=2, 3 voices → volume=3).
- 2026-07-12: Scaled th/ihtx tagscript timeout per-rep: base 180s + 6s per export so high-rep runs (up to 1000) don't get killed mid-process. Full codebase scan confirmed no remaining `source is not defined` bugs outside the five commands already fixed.
- 2026-07-12: Raised MAX_REPETITIONS from 100 → 1000 for th/ihtx.
- 2026-07-12: Fixed NameError `source is not defined` in th/stl, th/trim, th/addsource, th/mirror, th/autotune — all five commands used `attachment`/`media_url`/`base_url` to resolve media but then accidentally referenced the undefined `source` variable when building the filename and calling download helpers.
- 2026-07-12: Updated `mpb`/`bungee`: pipe effect now probes actual audio sample rate and uses sr/2 (was hardcoded 22050). Added standalone `th/mpb` / `th/multipitch_bungee` command to Python bot. Both pipe effect and standalone accept multi-pitch values (pipe/semicolon/comma separated, e.g. `-7|7`). Removed `th/multipitchihtx` from TS bot. Added `mpb`/`bungee` as Bungee pitch type in `th/ihtxsap`.
- 2026-07-12: Added th/join, th/pipetest, th/freakzingatesteffect (th/fzte), and th/youtubedownload (th/ytdl) to `th/ihtxhelp` / `th/bothelp` browse entries so the new commands appear in the Python bot's embed help.
- 2026-07-12: Disabled the default discord.py `th/help` command so the Python bot no longer sends a non-embed text help; the TypeScript bot's live embed `th/help` is now the only `th/help` response.
- 2026-07-12: Updated th/gradientmap and gradientmap/gmap pipe effect to build the gradient map from a grayscale source: both branches now use `format=gray` so the FFmpeg curves correctly map input luminance to the target RGBA gradient stops.
- 2026-07-11: Updated th/fzte / th/freakzingatesteffect pipeline to: invlum,huehsv=0.62,ccshue=110,channelblend=b|g|r,invlum,rotate=-0.78539815,tvsim=0.9;4,wave=0|15.000|0.8000|0.3466666667|0|0|0|0|0,rotate=0.78539815,mirror=90|0.840,mirror=right,mirror=bottom,ffmpeg(scale/drawtext/negate),mp3. Fixed th/join — the video join FFmpeg command was built but never executed, causing empty output. Also forced video output to .mp4 and fixed the uploaded filename extension. Added th/join — join 2 videos side-by-side (default) or stacked (use `-vertical`). Also added to `th/ihtxhelp` / `th/help` embeds. Added th/ytdl (alias th/youtubedownload) — yt-dlp download command; sends file directly if ≤8 MB, uploads to Catbox otherwise. Added stretch pipe effect (geq centre-zoom, params: zoom|offset). Added th/pipetest (alias th/pt) — one-shot pipe effect runner.
- 2026-07-11: Added replied-to plain HTTP(S) URL support for media commands that previously only accepted attachments.
- 2026-07-10: Refactored _apply_pipe_effects: extracted _ff_vf/_ff_af/_geq/_dl_file helpers and _VF_CODEC/_FF_BASE constants to eliminate repeated FFmpeg command boilerplate across ~15 effects (shake, wave, wave2, wmm3dripple, timecode, radar, jitter, randomjitter, watermark, nepeta, avflip, lut, __rawvf__, __rawaf__).
- 2026-07-10: th/chat now auto-sends long replies (>1800 chars) as a .txt file attachment; -debug flag still works for explicit file mode. th/ihtx pipe effects: added short aliases srw (sierpinskiransomware), wmm (wmm3dripple), p1280 (preview1280), rj (randomjitter).
- 2026-07-10: Fixed attachment downloads across all bot code — switched from `source.url` to `attachment.proxy_url or source.url`. Discord CDN now requires auth; direct URLs often return 404 for fresh uploads.
- 2026-07-10: Added Catbox.moe fallback to all video commands. Files >8 MB now auto-upload to Catbox instead of erroring out. Lowered threshold from 25 MB to 8 MB for commands that already had Catbox fallback.
- 2026-07-10: th/chat now supports -debug flag — adds the full AI response as a .txt file attachment, bypassing Discord's 2000-char message limit.
- 2026-07-09: Rewrote _split_pipe_segments to only track parens inside known function blocks (ffmpeg, leftsplit, rightsplit), fixing "No closing quotation" errors caused by expressions like 7*(text_h) corrupting the naive depth counter.
- 2026-07-09: Replaced chatbot personality (Clankered lore) with a concise technical assistant prompt that knows all core IHTX commands, effects, and presets.
- 2026-07-09: fzte pipeline: replaced volume,mp,volume trio with single mp3= (rubberband CLI multi-pitch, FLAC) for cleaner audio. Updated docstrings and embed description to show full pipeline.
- 2026-07-09: Fixed pipe effects' intermediate audio codec from pcm_s24le to pcm_s16le to prevent "Invalid PCM packet" FFmpeg errors on odd-byte audio streams. Also updated invlum pipe effect separately.
- 2026-07-09: Added th/crop and th/resize commands: crop <width> <height> center-crops a video; resize <width> <height> scales a video to the exact dimensions. Both preserve audio and support attachment/reply input.
- 2026-07-09: Updated th/lexg to use the last th/ihtx export per user (persisted to output/lastexport_<user_id>.mp4) with reverse→trim→reverse. Still supports attachment/reply override.
- 2026-07-08: Removed alimiter post-processing from multipitch2/mp2 (Evil_Rampaging_Sorcerer/G-Major_17 presets) to avoid clipping/static.
- 2026-07-08: Added multipitch3/mp3 pipe effect — old-style Rubber Band CLI multi-voice pitch shift with FLAC audio (no static fallback).
- 2026-07-08: Fixed th/veb to call ihtxgen.callback directly, avoiding the hybrid-command invocation path that was dropping pipe_effects and showing the ihtx preset help.
- 2026-07-08: Added math/animation support for pipe effects: $fc (frame count), lerp(a,b,t), and FFmpeg-native T/N/PI expressions. Affects wave, wave2, shake, jitter, randomjitter, scroll, ripple, pan, tile, brightness, contrast, saturation, rotate.
- 2026-07-08: Added th/math command (EconomyCog) to evaluate math expressions safely.
- 2026-07-08: huehsv: preserve audio stream with -c:a copy.
- 2026-07-08: multipitch2/mp2: probe for audio stream before processing; removed apad padding; restored pcm_s16le intermediate codec.
- 2026-07-08: Added VebCog (bot/veb_cog.py): th/veb <effects> command with veb-shorthand mapping + mention-triggered random effects.
- 2026-07-07: fzte: rewrite to use ihtx pipe engine (lut→rotate→tvsim→wave→rotate→ffmpeg/mirror/drawtext→volume→mp→volume); no more custom filter_complex.
- 2026-07-07: rotate pipe effect: angle now passed verbatim as FFmpeg radian expression (supports any math e.g. -45/180*PI, 50*7).
- 2026-07-07: fzte: switch to user's requested ihtx pipeline with mirror=right/bottom instead of frei0r=mirr0r (unavailable on Nix).
- 2026-07-07: fzte: LUT source reverted to file.garden URL (valid .cube file, 7 MB, 64³ LUT).
- 2026-07-07: fzte: replaced LUT download with on-the-fly color chain: invlum,huehsv=0.62,ccshue=110,channelblend=b|g|r,invlum.
- 2026-07-07: invlum: make InvertLuminosity.cube path relative to the bot module so it resolves regardless of cwd.
- 2026-07-06: fzte: move haldclut from displacement map [0] to user video [1] to fix displacement glitch.
- 2026-07-06: multipitch2/mp2: replaced fileaa binary + asetrate trick with rubberband filter_complex (TS "find pitch" port); added inharmonic mode and auto-scale.
- 2026-07-06: fzte/freakzingatesteffect: replaced remote lut3d cube with on-the-fly ImageMagick hald:8 haldclut generation.
- 2026-07-05: Added freakzingatesteffect as a th/ihtx pipe effect and a th/freakzingatesteffect (alias th/fzte) standalone command.
- 2026-07-05: Wired gradientmap/gmap as a th/ihtx pipe effect and added th/gradientmap (alias th/gm) standalone command.
- 2026-07-05: Added radar, timecode, wmm3dripple, and wave2 pipe effects.
"""

import discord
from discord.ext import commands, tasks
from bot.tags.cog import TagCog
import asyncio
import json
import math
import os
import random
import re
from collections import deque
import shlex
import tempfile
import shutil
import subprocess
import aiohttp
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import urllib.parse
import base64
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from bot.tags.parser import _MathParser, _safe_math

try:
    from PIL import Image as _PIL_Image
except ImportError:
    _PIL_Image = None

try:
    from bot.smiley_preview import (
        generate_smiley as _smiley_generate,
        ensure_previews as _smiley_ensure_previews,
        load_cache as _smiley_load_cache,
    )
    _smiley_preview_available = True
except Exception:
    _smiley_preview_available = False

_preview_cache: dict[str, str] = {}

try:
    import groq as _groq_lib
    _groq_api_key = os.environ.get("GROQ_API_KEY")
    if _groq_api_key:
        _groq_client = _groq_lib.Groq(api_key=_groq_api_key)
        print("[groq] Groq client initialized ✓")
    else:
        _groq_client = None
        print("[groq] GROQ_API_KEY not set — Groq disabled")
except Exception as _groq_init_err:
    _groq_client = None
    print(f"[groq] Failed to initialize Groq client: {_groq_init_err}")



# ---------- Configuration & constants ----------

TOKEN = os.environ.get("DISCORD_TOKEN")
CATBOX_USERHASH = os.environ.get("CATBOX_USERHASH", "")

# Owner ID — required, no default (set BOT_OWNER_ID in Replit Secrets)
_owner_id_raw = os.environ.get("BOT_OWNER_ID")
if not _owner_id_raw:
    import sys as _sys
    print("ERROR: BOT_OWNER_ID environment variable not set.", file=_sys.stderr)
    _sys.exit(1)
OWNER_ID = int(_owner_id_raw)

OWNER_IDS_FILE = Path("bot/owner_ids.json")
owner_ids: set[int] = {OWNER_ID}


def _load_owner_ids():
    global owner_ids
    try:
        if OWNER_IDS_FILE.exists():
            with OWNER_IDS_FILE.open() as f:
                owner_ids = set(int(x) for x in json.load(f))
        else:
            owner_ids = {OWNER_ID}
    except Exception:
        owner_ids = {OWNER_ID}


def _save_owner_ids():
    OWNER_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OWNER_IDS_FILE.open("w") as f:
        json.dump(list(owner_ids), f)


def _is_owner(ctx: commands.Context) -> bool:
    return ctx.author.id in owner_ids


def _is_owner_by_id(user_id: int) -> bool:
    return user_id in owner_ids


def _is_bot_mod(ctx: commands.Context) -> bool:
    """True if the user is an owner OR has been set as bot moderator via th/set."""
    if ctx.author.id in owner_ids:
        return True
    # _xp_data is loaded at module level later; safe to reference at call time.
    try:
        return bool(_xp_data.get(str(ctx.author.id), {}).get("is_mod", False))
    except Exception:
        return False

_load_owner_ids()

# ---------- Math / animation helpers ----------

_FFMPEG_EXPR_SYMBOLS = {
    "T", "N", "X", "Y", "W", "H", "PI", "E",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "abs", "clip", "mod", "hypot", "sqrt", "pow", "exp", "log",
    "min", "max", "if", "gt", "lt", "eq", "gte", "lte", "not", "and", "or",
    "between", "bitand", "bitor", "bitxor", "ceil", "floor", "round", "trunc",
    "isnan", "isinf", "gauss", "lerp",
    "w", "h", "t", "n", "x", "y", "p", "dx", "dy",
}

_FFMPEG_EXPR_RE = re.compile(
    r'(?<![A-Za-z0-9_])(' + '|'.join(re.escape(s) for s in _FFMPEG_EXPR_SYMBOLS) + r')(?![A-Za-z0-9_])'
)
# Matches expressions that contain ONLY characters valid in a math expression.
# Used to guard _MathParser: strings with ':', '=', letters etc. must not be
# collapsed because _MathParser._TOK silently strips those chars, causing e.g.
# "640:640" to be tokenised as the single number 640640.
_PURE_MATH_RE = re.compile(r'^[\d\s+\-*/^%().]+$')


def _split_top_level(s: str, delim: str) -> list[str]:
    """Split *s* at *delim*, but only at top-level parentheses depth."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in s:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == delim and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current).strip())
    return parts


def _expand_lerp(expr: str) -> str:
    """Expand lerp(a,b,t) -> (a)+((b)-(a))*(t)."""
    while True:
        m = re.search(r'\blerp\s*\(', expr, re.IGNORECASE)
        if not m:
            break
        start = m.start()
        depth = 1
        end = m.end()
        for i in range(m.end(), len(expr)):
            if expr[i] == '(':
                depth += 1
            elif expr[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end <= m.end():
            break
        inner = expr[m.end():end]
        args = _split_top_level(inner, ',')
        if len(args) != 3:
            break
        a, b, t = args
        replacement = f"({a})+(({b})-({a}))*({t})"
        expr = expr[:start] + f"({replacement})" + expr[end + 1:]
    return expr


def _preprocess_math_expr(
    expr: str,
    frame_count: int | None = None,
    media_vars: dict | None = None,
) -> str:
    """Replace $fc/$vd/$d/$sr/$fr/$f/$w/$h, expand lerp, collapse constant subexpressions.

    media_vars may contain: vd/d (duration s), sr (sample rate Hz),
    fps/fr (frame rate), w (width px), h (height px).
    Preserves key=value forms (e.g. scroll=hpos=0.5) by only preprocessing
    the value half.
    """
    if frame_count is not None:
        expr = expr.replace('$fc', str(frame_count))
    if media_vars:
        if 'vd' in media_vars:
            expr = expr.replace('$vd', f"{media_vars['vd']:.10g}")
            expr = expr.replace('$d', f"{media_vars['vd']:.10g}")
            # $T / *T — normalized time 0→1 over the video (expands to FFmpeg expression t/<vd>)
            _vd = media_vars['vd']
            _T_expr = f"(t/{_vd:.10g})" if _vd and _vd > 0 else "t"
            expr = re.sub(r'\$T(?![a-zA-Z0-9_])', _T_expr, expr)
            expr = re.sub(r'\*T(?![a-zA-Z0-9_])', _T_expr, expr)
        if 'sr' in media_vars:
            expr = expr.replace('$sr', str(media_vars['sr']))
        if 'fps' in media_vars:
            expr = expr.replace('$fr', f"{media_vars['fps']:.10g}")
            expr = expr.replace('$f', f"{media_vars['fps']:.10g}")
        if 'w' in media_vars:
            expr = expr.replace('$w', str(media_vars['w']))
        if 'h' in media_vars:
            expr = expr.replace('$h', str(media_vars['h']))
    expr = _expand_lerp(expr)
    if not _FFMPEG_EXPR_RE.search(expr) and _PURE_MATH_RE.match(expr):
        try:
            val = _MathParser(expr).parse()
            if val == int(val) and abs(val) < 1e15:
                return str(int(val))
            return f"{val:.10g}"
        except Exception:
            pass
    return expr


def _preprocess_param(
    param: str,
    frame_count: int | None = None,
    media_vars: dict | None = None,
) -> str:
    """Preprocess a single effect parameter, preserving key=value syntax."""
    if not param or not param.strip():
        return param
    if "=" in param:
        k, v = param.split("=", 1)
        return f"{k}={_preprocess_math_expr(v.strip(), frame_count, media_vars)}"
    return _preprocess_math_expr(param.strip(), frame_count, media_vars)


def _expr_param(param: str | None, default: float) -> str:
    """Return a string suitable for FFmpeg expressions."""
    if param is None:
        return str(default)
    param = param.strip()
    if param == "":
        return str(default)
    try:
        return str(float(param))
    except (ValueError, TypeError):
        return param


# Heavy command rate limiting
HEAVY_COMMANDS = {"ihtxgen", "ihtx", "effect", "destroy", "ihtxcustom", "icustom", "ihtxsap", "sap", "concatenate", "concat", "join", "multipitch_bungee", "mpb", "bmp", "multipitchbungee", "bungeemultipitch"}
HEAVY_LIMIT_DEFAULT = 20
HEAVY_LIMIT_OWNER = 5340
LIMITS_FILE = Path("bot/limits.json")
USAGE_FILE = Path("bot/usage.json")
PENDING_RESETS_FILE = Path("bot/pending_resets.json")
INVLUM_LUT_FILE = Path(__file__).with_name("InvertLuminosity.cube")
heavy_limits: dict[int, int] = {}
heavy_usage: dict[int, list[float]] = {}


def _load_limits():
    global heavy_limits
    try:
        if LIMITS_FILE.exists():
            with LIMITS_FILE.open() as f:
                heavy_limits = {int(k): int(v) for k, v in json.load(f).items()}
        else:
            heavy_limits = {}
    except Exception:
        heavy_limits = {}


def _save_limits():
    LIMITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LIMITS_FILE.open("w") as f:
        json.dump(heavy_limits, f)


def _load_usage():
    global heavy_usage
    try:
        if USAGE_FILE.exists():
            with USAGE_FILE.open() as f:
                data = json.load(f)
                heavy_usage = {int(k): [float(t) for t in v] for k, v in data.items()}
        else:
            heavy_usage = {}
    except Exception:
        heavy_usage = {}


def _save_usage():
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_FILE.open("w") as f:
        json.dump({str(k): v for k, v in heavy_usage.items()}, f)


def _check_heavy_limit(user_id: int) -> tuple[bool, str]:
    if _is_owner_by_id(user_id):
        return True, ""
    limit = heavy_limits.get(user_id, HEAVY_LIMIT_DEFAULT)
    now = time.time()
    day_ago = now - 86400
    usage = [t for t in heavy_usage.get(user_id, []) if t > day_ago]
    heavy_usage[user_id] = usage
    if len(usage) >= limit:
        return False, f"Heavy command limit reached ({limit}/{limit} per 24h). Contact an owner."
    usage.append(now)
    heavy_usage[user_id] = usage
    _save_usage()
    return True, ""

_load_limits()
_load_usage()

# Blocklist (users)
BLOCKLIST_FILE = Path("bot/blocklist.json")
blocklist: set[int] = set()


def _load_blocklist():
    global blocklist
    try:
        if BLOCKLIST_FILE.exists():
            with BLOCKLIST_FILE.open() as f:
                blocklist = set(int(x) for x in json.load(f))
        else:
            blocklist = set()
    except Exception:
        blocklist = set()


def _save_blocklist():
    BLOCKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BLOCKLIST_FILE.open("w") as f:
        json.dump(list(blocklist), f)

_load_blocklist()

# Channel blocklist
CHANNEL_BLOCK_FILE = Path("bot/channel_blocks.json")
channel_blocks: set[int] = set()


def _load_channel_blocks():
    global channel_blocks
    try:
        if CHANNEL_BLOCK_FILE.exists():
            with CHANNEL_BLOCK_FILE.open() as f:
                channel_blocks = set(int(x) for x in json.load(f))
        else:
            channel_blocks = set()
    except Exception:
        channel_blocks = set()


def _save_channel_blocks():
    CHANNEL_BLOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHANNEL_BLOCK_FILE.open("w") as f:
        json.dump(list(channel_blocks), f)

_load_channel_blocks()

# Per-channel keyword blocklist
KEYWORD_BLOCK_FILE = Path("bot/keyword_blocks.json")
KEYWORD_BLOCK_MSG_FILE = Path("bot/keyword_block_messages.json")
keyword_blocks: dict[int, set[str]] = {}
keyword_block_messages: dict[int, dict[str, str]] = {}


def _normalize_keyword(keyword: str) -> str:
    return re.sub(r"\s+", " ", keyword.strip().lower())


def _load_keyword_blocks():
    global keyword_blocks, keyword_block_messages
    try:
        if KEYWORD_BLOCK_FILE.exists():
            with KEYWORD_BLOCK_FILE.open() as f:
                raw = json.load(f)
            keyword_blocks = {
                int(channel_id): {
                    _normalize_keyword(keyword)
                    for keyword in keywords
                    if _normalize_keyword(str(keyword))
                }
                for channel_id, keywords in raw.items()
            }
        else:
            keyword_blocks = {}
    except Exception:
        keyword_blocks = {}

    try:
        if KEYWORD_BLOCK_MSG_FILE.exists():
            with KEYWORD_BLOCK_MSG_FILE.open() as f:
                raw = json.load(f)
            keyword_block_messages = {
                int(channel_id): {
                    _normalize_keyword(keyword): msg
                    for keyword, msg in msgs.items()
                }
                for channel_id, msgs in raw.items()
            }
        else:
            keyword_block_messages = {}
    except Exception:
        keyword_block_messages = {}


def _save_keyword_blocks():
    KEYWORD_BLOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        str(channel_id): sorted(keywords)
        for channel_id, keywords in keyword_blocks.items()
        if keywords
    }
    with KEYWORD_BLOCK_FILE.open("w") as f:
        json.dump(serializable, f, indent=2)
    # Also save messages
    msg_serializable = {
        str(channel_id): {
            keyword: msg
            for keyword, msg in msgs.items()
        }
        for channel_id, msgs in keyword_block_messages.items()
    }
    with KEYWORD_BLOCK_MSG_FILE.open("w") as f:
        json.dump(msg_serializable, f, indent=2)


def _blocked_keyword_for_message(channel_id: int, content: str) -> str | None:
    keywords = keyword_blocks.get(channel_id, set())
    if not keywords:
        return None
    normalized_content = content.lower()
    for keyword in sorted(keywords, key=len, reverse=True):
        if keyword and keyword in normalized_content:
            return keyword
    return None

def _blocked_keyword_message(channel_id: int, keyword: str, author_mention: str) -> str:
    msgs = keyword_block_messages.get(channel_id, {})
    msg = msgs.get(keyword)
    if msg:
        return msg.replace("{mention}", author_mention).replace("{user}", author_mention)
    return f"{author_mention}, that keyword is blocked in this channel."

_load_keyword_blocks()

# Autoreplies
AUTOREPLY_FILE = Path("bot/autoreplies.json")
autoreplies: dict[str, str] = {}


def _load_autoreplies():
    global autoreplies
    try:
        if AUTOREPLY_FILE.exists():
            with AUTOREPLY_FILE.open() as f:
                raw = json.load(f)
            # Migrate old flat format {"trigger": "response"} → new format
            migrated = {}
            for k, v in raw.items():
                if isinstance(v, dict):
                    migrated[k] = v
                else:
                    migrated[k] = {"response": v, "channel_id": None}
            autoreplies = migrated
        else:
            autoreplies = {}
    except Exception:
        autoreplies = {}


def _save_autoreplies():
    AUTOREPLY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUTOREPLY_FILE.open("w") as f:
        json.dump(autoreplies, f, indent=2)


_load_autoreplies()

# Autoreply2 (per-channel AI auto-reply toggle)
AUTOREPLY2_FILE = Path("bot/autoreply2.json")
autoreply2: set[int] = set()  # stores channel IDs


def _load_autoreply2():
    global autoreply2
    try:
        if AUTOREPLY2_FILE.exists():
            with AUTOREPLY2_FILE.open() as f:
                raw = json.load(f)
            autoreply2 = set(int(x) for x in raw)
        else:
            autoreply2 = set()
    except Exception:
        autoreply2 = set()


def _save_autoreply2():
    AUTOREPLY2_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUTOREPLY2_FILE.open("w") as f:
        json.dump(list(autoreply2), f, indent=2)


_load_autoreply2()

# Autoreply2 no-mention set (users whose ar2 replies skip the ping)
AUTOREPLY2_NO_MENTION_FILE = Path("bot/autoreply2_no_mention.json")
autoreply2_no_mention: set[int] = set()


def _load_autoreply2_no_mention():
    global autoreply2_no_mention
    try:
        if AUTOREPLY2_NO_MENTION_FILE.exists():
            with AUTOREPLY2_NO_MENTION_FILE.open() as f:
                autoreply2_no_mention = set(int(x) for x in json.load(f))
        else:
            autoreply2_no_mention = set()
    except Exception:
        autoreply2_no_mention = set()


def _save_autoreply2_no_mention():
    AUTOREPLY2_NO_MENTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUTOREPLY2_NO_MENTION_FILE.open("w") as f:
        json.dump(list(autoreply2_no_mention), f, indent=2)


_load_autoreply2_no_mention()




# Tags (custom presets)
TAGS_FILE = Path("bot/tags.json")
tags: dict[str, dict] = {}


def _load_tags():
    global tags
    try:
        if TAGS_FILE.exists():
            with TAGS_FILE.open() as f:
                tags = json.load(f)
        else:
            tags = {}
    except Exception:
        tags = {}


def _save_tags():
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TAGS_FILE.open("w") as f:
        json.dump(tags, f, indent=2)

_load_tags()

# Load bot config
_BOT_CONFIG_PATH = Path(__file__).parent / "config.json"
_bot_config = {}
if _BOT_CONFIG_PATH.exists():
    try:
        with open(_BOT_CONFIG_PATH, "r", encoding="utf-8") as f:
            _bot_config = json.load(f)
    except Exception as e:
        print(f"Warning: could not load config.json: {e}")

_BOT_PREFIX = _bot_config.get("bot_prefix") or _bot_config.get("BOT_PREFIX") or "th/"
if not isinstance(_BOT_PREFIX, str) or not _BOT_PREFIX:
    print(f"Warning: invalid bot_prefix ({_BOT_PREFIX!r}), falling back to 'th/'")
    _BOT_PREFIX = "th/"

# Intents and bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=_BOT_PREFIX, intents=intents, help_command=None)


@bot.tree.interaction_check
async def _slash_global_check(interaction: discord.Interaction) -> bool:
    """Mirror the prefix command global checks for slash (/) commands."""
    # Blocked users — owners are exempt so they can always unblock themselves
    if interaction.user.id in blocklist and interaction.user.id not in owner_ids:
        try:
            await interaction.response.send_message("❌ You are blocked from using this bot.", ephemeral=True)
        except Exception:
            pass
        return False
    # Blocked channels
    if interaction.channel and interaction.channel.id in channel_blocks:
        return False
    return True


# Maps user message id → list of bot reply message ids.
# Used to delete old responses when the user edits their command.
_response_map: dict[int, list[int]] = {}
_RESPONSE_MAP_MAX = 2000  # cap to prevent unbounded growth

# th/undo tracking: channel_id → last bot message id
_last_bot_msg: dict[int, int] = {}
_LAST_BOT_MSG_MAX = 500

# Stores the last th/ihtx export per user for th/lexg re-use.
_last_exports: dict[int, dict] = {}

# Runtime stats
_bot_start_time: float = time.time()
_renders_completed: int = 0
_renders_in_progress: int = 0

# File handling constants
SUPPORTED_EXTENSIONS  = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif", ".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS      = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"}
AUDIO_VIDEO_EXTS      = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_FILE_SIZE         = 25 * 1024 * 1024
CATBOX_THRESHOLD      = 10 * 1024 * 1024   # upload to catbox above this, Discord limit is 25 MB
MAX_REPETITIONS       = 1000
MAX_DURATION          = 600

# Effect filter definitions
_BASE_NOISE = "noise=alls=40:allf=t+u"
_SHAKE      = "crop=iw-20:ih-20:10+5*sin(t*30):10+5*cos(t*17),scale=iw+20:ih+20"
_CHROMAB = (
    "[IN]split=3[r][g][b];"
    "[r]lutrgb=r=val:g=0:b=0,pad=iw+6:ih:3:0[ro];"
    "[g]lutrgb=r=0:g=val:b=0[go];"
    "[b]lutrgb=r=0:g=0:b=val,pad=iw+6:ih:0:0[bo];"
    "[ro][go]blend=all_mode=addition[rg];"
    "[rg][bo]blend=all_mode=addition[OUT]"
)

PRESET_FILTERS: dict[str, dict] = {
    "chaos": {
        "vf": f"{_SHAKE},{_BASE_NOISE},hue=h=t*180:s=2,eq=contrast=1.5:brightness=0.05:saturation=3",
        "complex": None,
    },
    "glitch": {
        "vf": f"rgbashift=rh=8:rv=-8:gh=-4:gv=4:bh=6:bv=-6,{_BASE_NOISE},eq=contrast=1.8:saturation=0",
        "complex": None,
    },
    "shake": {
        "vf": f"{_SHAKE},{_BASE_NOISE},eq=contrast=1.3:saturation=1.5",
        "complex": None,
    },
    "rainbow": {
        "vf": None,
        "complex": (
            "[0:v]split=3[r][g][b];"
            "[r]lutrgb=r=val:g=0:b=0,pad=iw+6:ih:3:0[ro];"
            "[g]lutrgb=r=0:g=val:b=0[go];"
            "[b]lutrgb=r=0:g=0:b=val,pad=iw+6:ih:0:0[bo];"
            "[ro][go]blend=all_mode=addition[rg];"
            "[rg][bo]blend=all_mode=addition"
        ),
    },
    "static": {
        "vf": f"{_BASE_NOISE},curves=vintage,eq=contrast=1.2",
        "complex": None,
    },
    "melt": {
        "vf": (
            "perspective=x0=0:y0=0:x1=iw:y1=20*sin(t*3)"
            ":x2=0:y2=ih:x3=iw:y3=ih-20*sin(t*3),"
            + _BASE_NOISE
        ),
        "complex": None,
    },
    "corrupt": {
        "vf": f"drawgrid=x=0:y=0:w=iw:h=5:t=1:color=white@0.1,{_BASE_NOISE},eq=gamma=1.5:saturation=0.3:contrast=2",
        "complex": None,
    },
    "sierpinskiransomware": {
        "vf": None,
        "complex": None,
        "complex_template": (
            "[0:v]null,trim=0:{d}[outv1];"
            "[0:a]atrim=0:{d}[outa1];"
            "[0:v]trim=0:{d}[v1];"
            "[0:v]negate,trim=0:{d}[v2];"
            "[v1][v2]concat=2:1:0,setpts=1/2*PTS,fps={fr},trim=0:{d}[outv2];"
            "[0:a]rubberband=pitch=2:tempo=2,atrim=0:{d}[a1];"
            "[0:a]rubberband=pitch=2:tempo=2,atrim=0:{d}[a2];"
            "[a1][a2]concat=2:0:1,atrim=0:{d}[outa2];"
            "[0:v]null,trim=0:{d}[v3];"
            "[0:v]negate,trim=0:{d}[v4];"
            "[v3][v4]concat=2:1:0,setpts=1/1.333*PTS,fps={fr},trim=0:{d}[outv3];"
            "[0:a]rubberband=pitch=1.333:tempo=1.333,atrim=0:{d}[a3];"
            "[0:a]rubberband=pitch=1.333:tempo=1.333,atrim=0:{d}[a4];"
            "[a3][a4]concat=2:0:1,atrim=0:{d}[outa3];"
            "[0:v]setpts=1/0.5*PTS,fps={fr},trim=0:{d}[outv4];"
            "[0:a]rubberband=pitch=0.5:tempo=0.5,atrim=0:{d}[outa4];"
            "[outv1][outv2]hstack[tmp1];"
            "[outv3][outv4]hstack[tmp2];"
            "[tmp1][tmp2]vstack,scale=iw/2:ih/2[outv];"
            "[outa1][outa2][outa3][outa4]amix=inputs=4,alimiter=level_in=2:latency=1,highpass=f=40[outa]"
        ),
        "maps": ["[outv]", "[outa]"],
        "audio_codec": "flac",
        "extra_codec_args": ["-preset", "ultrafast"],
        "output_ext": ".mp4",
    },
}

VISUAL_PRESETS = set(PRESET_FILTERS.keys())

HELP_TEXT = """\
**I Hate The X — IHTX Bot**
One command, pipe-style syntax:

`th/ihtx effect=value,effect=value,...`

(Full help included in repository's README/help text.)
"""

# ---------- Global checks ----------

@bot.check
async def _global_checks(ctx: commands.Context) -> bool:
    # Channel blocked
    if ctx.channel.id in channel_blocks:
        return False
    # User blocked — owners are always exempt so they can unblock themselves
    if ctx.author.id in blocklist and ctx.author.id not in owner_ids:
        return False
    # Heavy command rate limiting
    if ctx.command and ctx.command.name in HEAVY_COMMANDS:
        ok, reason = _check_heavy_limit(ctx.author.id)
        if not ok:
            await ctx.reply(f"❌ {reason}")
            return False
    return True

# ---------- Helpers: download and ffmpeg ----------

async def download_attachment(attachment: discord.Attachment, dest: str):
    """Download a discord.Attachment to path `dest`.

    Uses ``proxy_url`` (Discord's authenticated CDN proxy) when available,
    falling back to ``url``. Discord CDN now requires auth; direct ``url``
    often returns 404 for fresh uploads.
    """
    url = attachment.proxy_url or attachment.url
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError(f"Failed to download attachment (HTTP {resp.status})")
            data = await resp.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)




async def _resolve_media_source(ctx: commands.Context) -> discord.Attachment | str | None:
    """Resolve a media source from the current message or a reply."""
    if ctx.message and ctx.message.attachments:
        return ctx.message.attachments[0]
    if ctx.message and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                return ref.attachments[0]
            for tok in ref.content.split():
                if tok.startswith(("http://", "https://")):
                    return tok
        except Exception:
            pass
    return None
async def download_url(url: str, dest: str):
    """Download an arbitrary URL to path `dest`.

    Streams the response in chunks to avoid loading large files into memory,
    sets a browser-like User-Agent to prevent server disconnects, and applies
    a generous timeout so large video files complete reliably.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    timeout = aiohttp.ClientTimeout(total=300, connect=15)
    tmp = dest + ".part"
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                raise ValueError(f"Failed to download URL (HTTP {resp.status})")
            with open(tmp, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    f.write(chunk)
    os.replace(tmp, dest)


async def _update_bot_presence() -> None:
    """Refresh the bot's Playing status with the current render count.

    Skipped if the owner has set a custom activity via ``th/setactivity``
    (i.e. bot/activity.json exists) so their custom text is not clobbered.
    """
    if Path("bot/activity.json").exists():
        return
    gc = len(bot.guilds)
    if _renders_completed > 0:
        name = f"Made {_renders_completed:,} renders in {gc} servers!"
    else:
        name = f"Making Effects in {gc} servers!"
    try:
        await bot.change_presence(status=discord.Status.online, activity=discord.Game(name=name))
    except Exception:
        pass


def _transcode_to_web_mp4(file_path: str) -> str | None:
    """
    Re-encode a video file to a web-compatible MP4 (H.264 + AAC) so it plays
    in browsers and Discord embeds after being hosted on Catbox.moe.

    Returns the path to the transcoded file (a .mp4 in the same directory),
    or None if the file is not a video or transcoding fails.
    The caller is responsible for deleting the returned temp file.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in AUDIO_VIDEO_EXTS:
        return None
    out_path = file_path + "_catbox_web.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", file_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        pass
    # Clean up partial output on failure
    try:
        os.remove(out_path)
    except OSError:
        pass
    return None


async def _upload_to_catbox(file_path: str) -> str | None:
    """Upload a file to catbox.moe and return the URL, or None on failure.

    Video files are transcoded to web-compatible MP4 (H.264/AAC) before
    uploading so they play correctly in browsers and Discord embeds.
    """
    global _renders_completed
    transcoded: str | None = None
    upload_path = file_path
    try:
        # Re-encode videos so they play in browser after catbox serves them
        ext = Path(file_path).suffix.lower()
        if ext in AUDIO_VIDEO_EXTS:
            transcoded = await asyncio.get_event_loop().run_in_executor(
                None, _transcode_to_web_mp4, file_path
            )
            if transcoded:
                upload_path = transcoded

        with open(upload_path, "rb") as fh:
            file_bytes = fh.read()
        filename = Path(upload_path).name
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        if CATBOX_USERHASH:
            form.add_field("userhash", CATBOX_USERHASH)
        form.add_field("fileToUpload", file_bytes, filename=filename)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://catbox.moe/user/api.php", data=form, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                text = await resp.text()
                if resp.status == 200 and text.startswith("https://"):
                    _renders_completed += 1
                    asyncio.ensure_future(_update_bot_presence())
                    return text.strip()
                return await _upload_to_uguu(file_path)
    except Exception:
        return await _upload_to_uguu(file_path)
    finally:
        if transcoded:
            try:
                os.remove(transcoded)
            except OSError:
                pass


async def _upload_to_uguu(file_path: str) -> str | None:
    """Upload a file to uguu.se and return its direct URL, or None on failure."""
    try:
        with open(file_path, "rb") as fh:
            form = aiohttp.FormData()
            form.add_field(
                "files[]",
                fh,
                filename=Path(file_path).name,
                content_type="application/octet-stream",
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://uguu.se/upload.php",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        return None
                    payload = await resp.json(content_type=None)
                    files = payload.get("files", []) if isinstance(payload, dict) else []
                    url = files[0].get("url") if files and isinstance(files[0], dict) else None
                    return url.strip() if isinstance(url, str) and url.startswith("https://") else None
    except Exception:
        return None


def _ffprobe(input_path: str, *args: str) -> str:
    """Run ffprobe and return stripped stdout."""
    cmd = ["ffprobe", "-v", "error"] + list(args) + [input_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def _ffprobe_duration(input_path: str) -> float:
    """Get duration in seconds."""
    out = _ffprobe(input_path, "-show_entries", "format=duration",
                   "-of", "csv=p=0")
    try:
        return float(out)
    except (ValueError, TypeError):
        return 0.0


def _ffprobe_video_info(input_path: str) -> dict:
    """Return width, height, duration, nb_frames, r_frame_rate."""
    info = {"width": 0, "height": 0, "duration": 0.0,
            "nb_frames": 0, "r_frame_rate": "30"}
    w = _ffprobe(input_path, "-select_streams", "v:0",
                 "-show_entries", "stream=width",
                 "-of", "default=nw=1:nk=1")
    h = _ffprobe(input_path, "-select_streams", "v:0",
                 "-show_entries", "stream=height",
                 "-of", "default=nw=1:nk=1")
    fc = _ffprobe(input_path, "-select_streams", "v:0",
                  "-show_entries", "stream=nb_frames",
                  "-of", "default=nokey=1:noprint_wrappers=1")
    fr = _ffprobe(input_path, "-select_streams", "v:0",
                  "-show_entries", "stream=r_frame_rate",
                  "-of", "default=nokey=1:noprint_wrappers=1")
    dur = _ffprobe_duration(input_path)
    try:
        info["width"] = int(w)
    except (ValueError, TypeError):
        pass
    try:
        info["height"] = int(h)
    except (ValueError, TypeError):
        pass
    try:
        info["nb_frames"] = int(fc)
    except (ValueError, TypeError):
        pass
    if fr:
        info["r_frame_rate"] = fr
    info["duration"] = dur
    return info


def _ffprobe_sample_rate(input_path: str) -> int:
    """Return the audio sample rate of the input file, defaulting to 44100."""
    sr = _ffprobe(input_path, "-select_streams", "a:0",
                  "-show_entries", "stream=sample_rate",
                  "-of", "default=nw=1:nk=1")
    try:
        return int(sr)
    except (ValueError, TypeError):
        return 44100


def _run_ffmpeg_raw(cmd: list[str], timeout: int = 180) -> tuple[bool, str]:
    """Run an arbitrary ffmpeg command. Returns (ok, stderr-or-empty)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr[-2000:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"FFmpeg timed out (>{timeout}s)"
    except Exception as e:
        return False, str(e)


def _frei0r_mirr0r_available() -> bool:
    """Return True if FFmpeg can load the frei0r mirr0r plugin."""
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "nullsrc",
            "-vf", "frei0r=mirr0r:0.5", "-frames:v", "1", "-f", "null", "-",
        ],
        capture_output=True, timeout=10,
    )
    return result.returncode == 0


def _run_freakzinga_test_effect(
    input_path: str,
    output_path: str,
    params: list[str] | None = None,
) -> tuple[bool, str]:
    """Freakzinga test effect — runs the standard fzte ihtx pipe pipeline.

    Pipeline:
      1. invlum — luma inversion
      2. huehsv=0.62 — hue shift
      3. ccshue=110 — CCS hue
      4. channelblend=b|g|r — channel blend
      5. invlum — second luma inversion
      6. rotate=-0.78539815 — rotate -45°
      7. tvsim=0.9;4 — TV simulator
      8. wave=0|15.000|0.8000|0.3466666667|0|0|0|0|0 — wave distortion
      9. rotate=0.78539815 — rotate +45°
     10. mirror=90|0.840 — parametric fold
     11. mirror=right — mirror right half
     12. mirror=bottom — mirror bottom half
     13. ffmpeg(...) — scale, negate, frame-numbered drawtext, negate, scale to 640x360
     14. mp3=-20|-17|-13|-8|-5|-1|4|7|11|16|19|23 — multi-pitch (rubberband CLI, FLAC)

    Aliases in pipe syntax: fzte, freaktest.
    """
    params = params or []

    # Probe video dimensions; allow override via params
    try:
        vinfo = _ffprobe_video_info(input_path)
        w = int(vinfo["width"])
        h = int(vinfo["height"])
    except Exception:
        w, h = 1920, 1080

    if params:
        try:
            joined = " ".join(params)
            parts = [p.strip() for p in re.split(r"[;|,_\s]+", joined) if p.strip()]
            if len(parts) >= 2:
                w = int(parts[0])
                h = int(parts[1])
        except Exception:
            pass

    font = "/usr/share/fonts/truetype/arial/ArialSans.ttf"

    pipe = (
        "invlum,huehsv=0.62,ccshue=110,channelblend=b|g|r,invlum,"
        "rotate=-0.78539815,"
        "tvsim=0.9;4,"
        "wave=0|15.000|0.8000|0.3466666667|0|0|0|0|0,"
        "rotate=0.78539815,"
        + "mirror=90|0.840,"
        + "mirror=right,"
        + "mirror=bottom,"
        + "ffmpeg("
        + "-vf scale=640*1.1:360*1.05,negate,"
        + f"drawtext=fontfile={font}:text='%{{n}}.000':text_align=R:fontcolor=white:fontsize=w/27:box=1:boxcolor=black:boxborderw=7*(text_h):x=(w/2)-(text_w/2):y=(h-text_h)/1.12,"
        + "negate,scale=640:360"
        + "),"
        + "mp3=-20|-17|-13|-8|-5|-1|4|7|11|16|19|23"
    )

    effects = _parse_pipe_effects(pipe)
    return _apply_pipe_effects(input_path, output_path, effects)


def _run_nparisonffmpeg(
    input_path: str,
    output_path: str,
    gridx: int,
    gridy: int,
    user_args: list[str],
) -> tuple[bool, str]:
    """Iterative xstack grid: apply *user_args* once per cell, stack results.

    Each cell receives one additional application of the FFmpeg args (chained
    from the previous cell).  The final grid is scaled back to per-tile size.
    Returns (ok, error_message).
    """
    powers = gridx * gridy
    if powers > 16:
        return False, f"Grid too large ({powers} cells) — max 16 (e.g. 4×4)."

    with tempfile.TemporaryDirectory() as tmpdir:
        # Detect audio
        _probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, timeout=10,
        )
        has_audio = "audio" in _probe.stdout

        # Step 0: lossless encode — use .mkv (ffv1 is not valid in .mp4)
        step0 = os.path.join(tmpdir, "np_0.mkv")
        s0_cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                  "-i", input_path, "-c:v", "ffv1"]
        s0_cmd += ["-c:a", "flac"] if has_audio else ["-an"]
        s0_cmd.append(step0)
        ok, err = _run_ffmpeg_raw(s0_cmd, timeout=180)
        if not ok:
            return False, f"lossless encode failed: {err}"

        # Steps 1..powers+1 — collect 1..powers as grid inputs.
        # Use .mkv (not .ts) so any audio/video codec combination works.
        mkv_files: list[str] = []
        prev = step0
        for step in range(1, powers + 2):
            mkv_out = os.path.join(tmpdir, f"np_{step}.mkv")
            ok, err = _run_ffmpeg_raw(
                ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                 "-i", prev] + user_args + [mkv_out],
                timeout=180,
            )
            if not ok:
                return False, f"iteration {step} failed: {err}"
            if step <= powers:
                mkv_files.append(mkv_out)
            prev = mkv_out

        # Probe the shortest video duration across all iteration outputs so we
        # can hard-trim every stream to the same length before xstack.
        # This is the only reliable fix for the "best_input >= 0" assertion,
        # which fires whenever streams have even slightly different durations
        # (e.g. when -af effects like rubberband change audio length).
        min_dur: float | None = None
        for mf in mkv_files:
            try:
                _dp = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", mf],
                    capture_output=True, text=True, timeout=10,
                )
                _d = float(_dp.stdout.strip())
                if min_dur is None or _d < min_dur:
                    min_dur = _d
            except Exception:
                pass

        # Build filter_complex: trim every video stream to min_dur, reset PTS,
        # then xstack.  Audio uses aresample+atrim to match the same window.
        inp_flags: list[str] = []
        for tf in mkv_files:
            inp_flags += ["-i", tf]

        trim_v = f"trim=duration={min_dur:.4f}," if min_dur is not None else ""
        fc_segments: list[str] = []
        for k in range(powers):
            fc_segments.append(f"[{k}:v]{trim_v}setpts=PTS-STARTPTS[pv{k}]")
        stacked_v = "".join(f"[pv{k}]" for k in range(powers))
        fc_segments.append(
            f"{stacked_v}xstack=inputs={powers}:grid={gridx}x{gridy},"
            f"scale=iw/{gridx}:ih/{gridy}:flags=lanczos[v]"
        )

        map_extra: list[str] = []
        acodec_args: list[str] = []
        if has_audio:
            trim_a = f"atrim=duration={min_dur:.4f},asetpts=PTS-STARTPTS," if min_dur is not None else ""
            for k in range(powers):
                fc_segments.append(f"[{k}:a]{trim_a}aresample=async=1[pa{k}]")
            pa_joined = "".join(f"[pa{k}]" for k in range(powers))
            fc_segments.append(f"{pa_joined}amix={powers}:normalize=0[a]")
            map_extra = ["-map", "[a]"]
            acodec_args = ["-c:a", "aac", "-b:a", "192k"]

        fc = ";".join(fc_segments)
        timeout = 120 + powers * 60
        cmd = (
            ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y"]
            + inp_flags
            + ["-filter_complex", fc, "-map", "[v]"] + map_extra
            + ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
               "-pix_fmt", "yuv420p"]
            + acodec_args
            + [output_path]
        )
        ok, err = _run_ffmpeg_raw(cmd, timeout=timeout)
        if not ok:
            return False, f"xstack failed: {err}"

    return True, ""


def _probe_video_info(input_path: str) -> tuple[float, float]:
    """Return (duration_seconds, fps) for a video file via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", input_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout) if result.stdout else {}
    duration = float(data.get("format", {}).get("duration", 30))
    fps = 30.0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            r = stream.get("r_frame_rate", "30/1")
            try:
                num, den = r.split("/")
                fps = float(num) / float(den)
            except Exception:
                pass
            break
    return duration, fps


def run_ffmpeg(input_path: str, output_path: str, preset: str, is_video: bool) -> tuple[bool, str]:
    """Run ffmpeg using PRESET_FILTERS. Returns (ok, stderr-or-empty)."""
    cfg = PRESET_FILTERS.get(preset)
    if cfg is None:
        cfg = PRESET_FILTERS["chaos"]

    # Presets with a dynamic filter_complex template (e.g. sierpinskiransomware)
    if cfg.get("complex_template") and is_video:
        duration, fps = _probe_video_info(input_path)
        d = min(duration, 30.0)
        fr = round(fps)
        fc = cfg["complex_template"].format(d=d, fr=fr)
        maps = cfg.get("maps", [])
        audio_codec = cfg.get("audio_codec", "aac")
        extra_codec_args = cfg.get("extra_codec_args", ["-preset", "fast", "-crf", "23"])
        map_flags: list[str] = []
        for m in maps:
            map_flags += ["-map", m]
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", fc,
            *map_flags,
            "-c:v", "libx264", *extra_codec_args,
            "-strict", "experimental",
            "-c:a", audio_codec,
            "-t", str(d),
            "-f", "mov",
            output_path,
        ]
        return _run_ffmpeg_raw(cmd)

    if is_video:
        if cfg["complex"]:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex", cfg["complex"],
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac",
                "-t", "30",
                output_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", cfg["vf"],
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac",
                "-t", "30",
                output_path
            ]
    else:
        # Image → animated GIF
        if cfg["complex"]:
            fc = cfg["complex"] + ",split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", input_path,
                "-filter_complex", fc,
                "-t", "3",
                output_path
            ]
        else:
            vf = cfg["vf"] + ",split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", input_path,
                "-vf", vf,
                "-t", "3",
                output_path
            ]

    return _run_ffmpeg_raw(cmd)


def get_output_ext(input_ext: str, is_video: bool) -> str:
    return ".mp4" if is_video else ".gif"

# ---------- HueHSV (ImageMagick haldclut) ----------

def _run_huehsv(
    input_path: str,
    output_path: str,
    hue: float = 0.5,
    sat: float = 1.0,
    lightness: float = 1.0,
    colorspace: str = "hsl",
    betterfully: bool = False,
) -> tuple[bool, str]:
    """Apply huehsv using ImageMagick haldclut + FFmpeg haldclut filter.

    ImageMagick -modulate takes brightness%,saturation%,hue% (100 = unchanged).
      hue:        user float → hue*200+100   (0.0=unchanged, 0.5=full rotation)
      sat:        multiplier  → sat*100 (or sat*125 in betterfully mode)
      lightness:  multiplier  → lightness*100 (1.0=unchanged)
      colorspace: ImageMagick modulate colorspace (default hsl)
      betterfully: if True, boosts saturation headroom to 125% and posterizes
                   the hue channel (round to nearest 1/6 step) for a richer look.

    Pipe usage: huehsv=<hue>|<sat>|<lightness>|<colorspace>|<betterfully>
    e.g. huehsv=0.65|0.8|1.2|hsl|1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        hald_path = os.path.join(tmpdir, "hsv.ppm")
        hue_pct      = hue * 200 + 100
        sat_pct      = sat * (125 if betterfully else 100)
        lightness_pct = lightness * 100
        modulate_arg = f"{lightness_pct:.6g},{sat_pct:.6g},{hue_pct:.6g}"

        cmd = [
            "magick", "hald:8",
            "-define", f"modulate:colorspace={colorspace}",
            "-modulate", modulate_arg,
        ]
        if betterfully:
            cmd += [
                "-colorspace", "hsl",
                "-channel", "r",
                "-fx", "round(u*6)/6",
                "+channel",
                "-colorspace", "srgb",
            ]
        cmd.append(hald_path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, f"huehsv: ImageMagick failed: {result.stderr}"

        # Apply via FFmpeg haldclut filter; preserve audio by copying it.
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"movie={hald_path},[in]haldclut,format=yuv420p",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            output_path,
        ], timeout=180)
        if not ok:
            return False, f"huehsv: FFmpeg haldclut failed: {err}"

        return True, ""


# ---------- TV Simulator ----------

_TVSIM_DISPLACE_MAP = Path(__file__).parent / "displacemaps" / "tvsimulator.mov"
_TVSIM_DISPLACE_MAP_URL  = "https://file.garden/aTXso15ukD3mnuPI/tv_sim_displacement_map.mov"
_TVSIM_APERTURE_GRILL_URL = "https://file.garden/aTXso15ukD3mnuPI/tv_simulator_aperture_grill.png"
_TVSIM_STATIC_URL        = "https://file.garden/aTXso15ukD3mnuPI/tv_simulator_static.mp4"


def _run_tvsim(
    input_path: str,
    output_path: str,
    curvature: float = 0.0,       # arg 0: displacement strength (1=flat, 0=max curve)
    line_sync: float = 1.0,       # arg 1: zoom factor for filters + disp map Y-stretch
    detail_zoom: float = 1.0,     # arg 2: scroll speed (detail_zoom != 1 activates scroll)
    vertical_sync: float = 0.0,   # arg 3: phosphor lutrgb tint strength
    phosphorescence: float = 0.0, # arg 4: interlacing scanline darkening strength
    interlacing: float = 0.0,     # arg 5: scan phasing ripple strength
    aperture_grill: float = 0.0,  # arg 6: grill PNG blend (0=off, 1=full)
    static_noise: float = 0.0,    # arg 7: static MP4 blend (0=off, 1=full)
    _in_split: bool = False,
) -> tuple[bool, str]:
    """Apply TV-simulator CRT effect via FFmpeg displacement map.

    Matches TypeScript runTvSimulator:
      curvature    — displacement strength (1=flat, 0=max CRT curve)
      line_sync    — zoom factor for interlace/scanphase filters and disp map Y-stretch
      detail_zoom  — scroll speed; != 1 activates vertical scroll
      vertical_sync — phosphor lutrgb tint strength
      phosphorescence — interlacing scanline darkening (centered sin, line_sync-aware)
      interlacing  — scan phasing ripple (cos when curved, -sin when flat; line_sync-aware)
      aperture_grill — external PNG blended multiply + huesaturation intensity
      static_noise   — external MP4 blended overlay
    """
    curvature = max(0.0, min(1.0, curvature))

    vinfo = _ffprobe_video_info(input_path)
    w = vinfo["width"] or 854
    h = vinfo["height"] or 480
    r_frame_rate = vinfo.get("r_frame_rate", "30")
    try:
        fn, fd = r_frame_rate.split("/")
        fr = float(fn) / float(fd)
    except Exception:
        fr = 30.0

    is_curved  = curvature != 1.0
    has_grill  = aperture_grill != 0.0
    has_static = static_noise   != 0.0
    ls = line_sync

    # --- Inline optional filters (applied after displacement or base format step) ---
    fx: list[str] = []

    # Scroll — detail_zoom != 1 activates it; uses probed frame rate
    if detail_zoom != 1.0:
        fx.append(f"scroll=v='lerp(8/{fr},0,({detail_zoom})^(1/3))'")

    # Phosphor lutrgb tint — vertical_sync != 0
    if vertical_sync != 0.0:
        vs = vertical_sync
        fx.append(
            f"lutrgb='lerp(val,val*1.15,{vs})':'lerp(val,val*1.15+48,{vs})':'lerp(val,val*1.15+64,{vs})'"
        )

    # Interlacing scanlines (phosphorescence != 0) — centered sin, line_sync-aware frequency
    if phosphorescence != 0.0:
        ph = phosphorescence
        fx.append(
            f"geq=r='p(X,Y)*lerp(1,(sin(0.5+(Y/H-0.5)*(300/{ls}))+1)/2,{ph})':"
            f"g='p(X,Y)*lerp(1,(sin(0.5+(Y/H-0.5)*(300/{ls}))+1)/2,{ph})':"
            f"b='p(X,Y)*lerp(1,(sin(0.5+(Y/H-0.5)*(300/{ls}))+1)/2,{ph})'"
        )

    # Scan phasing / ripple (interlacing != 0) — cos when curved, -sin when flat
    if interlacing != 0.0:
        il = interlacing
        if is_curved:
            fx.append(
                f"geq=r='min(p(X,Y)+max(cos(Y/H*(5/{ls})-mod(T*16.666666*{il},5))*128-64,0),255)':"
                f"g='min(p(X,Y)+max(cos(Y/H*(5/{ls})-mod(T*16.666666*{il},5))*128-64,0),255)':"
                f"b='min(p(X,Y)+max(cos(Y/H*(5/{ls})-mod(T*16.666666*{il},5))*128-64,0),255)'"
            )
        else:
            fx.append(
                f"geq=r='min(p(X,Y)+max(-sin(0.5+(Y/H-0.5)*(5/{ls})-mod(T*16.666666*{il},4.833333))*128-64,0),255)':"
                f"g='min(p(X,Y)+max(-sin(0.5+(Y/H-0.5)*(5/{ls})-mod(T*16.666666*{il},4.833333))*128-64,0),255)':"
                f"b='min(p(X,Y)+max(-sin(0.5+(Y/H-0.5)*(5/{ls})-mod(T*16.666666*{il},4.833333))*128-64,0),255)'"
            )

    fx_chain = ("," + ",".join(fx)) if fx else ""

    # syncFilter applied to grill/static inputs when line_sync != 1 (center-zoom)
    if line_sync != 1.0:
        sync_filter = (
            f"format=yuv444p,"
            f"geq='p(mod((W/2)+(X-(W/2))/{ls},W),mod((H/2)+(Y-(H/2))/{ls},H))',"
        )
    else:
        sync_filter = ""

    # --- Trivial case: flat + no grill + no static ---
    if not is_curved and not has_grill and not has_static:
        if fx:
            vf = ",".join(fx) + ",format=yuv420p"
            cmd = [
                "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                "-i", input_path,
                "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", output_path,
            ]
        else:
            cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                   "-i", input_path, "-c", "copy", output_path]
        return _run_ffmpeg_raw(cmd, timeout=600)

    # --- Build input list with stream indices ---
    extra_inputs: list[str] = []
    cur_idx = 1

    if is_curved:
        disp_idx = cur_idx
        extra_inputs += ["-stream_loop", "-1", "-i", _TVSIM_DISPLACE_MAP_URL]
        cur_idx += 1
    else:
        disp_idx = None

    if has_grill:
        ag_idx = cur_idx
        extra_inputs += ["-i", _TVSIM_APERTURE_GRILL_URL]
        cur_idx += 1
    else:
        ag_idx = None

    if has_static:
        st_idx = cur_idx
        extra_inputs += ["-stream_loop", "-1", "-i", _TVSIM_STATIC_URL]
        cur_idx += 1
    else:
        st_idx = None

    # --- Build filter_complex ---
    segs: list[str] = []
    out_fmt = "gbrp" if (has_grill or has_static) else "yuv444p"
    current = "_v1"  # tracks current labeled output through the chain

    # Step 1: base → [_v1]
    if is_curved:
        contrast = (1.0 - curvature) * 2.366666
        # Y-stretch on displacement map when line_sync != 1
        disp_pre = (
            f"format=yuv444p,geq='p(mod(X,W),mod(Y/{ls},H))',"
            if line_sync != 1.0 else ""
        )
        segs.append(f"[0:v]scale=854:854,format=bgr32[_tv00]")
        segs.append(
            f"[{disp_idx}:v]{disp_pre}scale=854:854,"
            f"eq=contrast={contrast:.6f}:eval=frame,format=bgr32,hue=b=-0.033[_tvx]"
        )
        segs.append("color=s=854x854:c=#808080,format=bgr32[_tvy]")
        segs.append(
            f"[_tv00][_tvx][_tvy]displace=edge=wrap,scale={w}:{h},setsar=1,"
            f"format={out_fmt}{fx_chain}[_v1]"
        )
    else:
        segs.append(f"[0:v]format=gbrp{fx_chain}[_v1]")

    # Step 2: aperture grill — PNG + blend multiply + huesaturation → [_vag]
    if has_grill:
        ag = aperture_grill
        segs.append(f"[{ag_idx}:v]{sync_filter}scale={w}:{h},format=gbrp[_ag]")
        segs.append(
            f"[{current}][_ag]blend=all_mode=multiply:all_opacity={ag},"
            f"huesaturation=hue=0:saturation=0:intensity={ag / 2.0}:strength=100[_vag]"
        )
        current = "_vag"

    # Step 3: static — MP4 + blend overlay → [_vst]
    if has_static:
        segs.append(f"[{st_idx}:v]{sync_filter}scale={w}:{h},format=gbrp[_st]")
        segs.append(f"[{current}][_st]blend=all_mode=overlay:all_opacity=1:shortest=1[_vst]")
        current = "_vst"

    # Ensure final output is always labeled [_vout] for -map
    if current != "_vout":
        segs.append(f"[{current}]format=yuv420p[_vout]")

    fc = ";".join(segs)

    cmd = [
        "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
        "-i", input_path,
    ] + extra_inputs + [
        "-filter_complex", fc,
        "-map", "[_vout]",
        "-map", "0:a?",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        output_path,
    ]

    return _run_ffmpeg_raw(cmd, timeout=600)


# ---------- Folk Valley ----------

_FOLKVALLEY_MUSIC_URL = "https://files.catbox.moe/4d3mdi.mp3"
_FOLKVALLEY_OVERLAY_URL = "https://files.catbox.moe/53c100.png"


def _run_folkvalley(input_path: str, output_path: str) -> tuple[bool, str]:
    """Apply the folkvalley aesthetic effect:
    - Replace audio with the folkvalley music track (catbox mp3)
    - Brightness boost via HSV value shift (hueshifthsv H=0 S=0 V+100 ≈ eq brightness +0.39)
    - Overlay a decorative image (catbox PNG) scaled to fit the frame
    """
    import urllib.request
    import ssl

    _ua = {"User-Agent": "Mozilla/5.0 (compatible; IHTX-Bot/1.0)"}
    ssl_ctx = ssl.create_default_context()

    with tempfile.TemporaryDirectory() as tmpdir:
        music_path = os.path.join(tmpdir, "music.mp3")
        overlay_path = os.path.join(tmpdir, "overlay.png")

        for url, dest in [(_FOLKVALLEY_MUSIC_URL, music_path), (_FOLKVALLEY_OVERLAY_URL, overlay_path)]:
            try:
                req = urllib.request.Request(url, headers=_ua)
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=60) as resp:
                    with open(dest, "wb") as fh:
                        fh.write(resp.read())
            except Exception as exc:
                return False, f"folkvalley: failed to download {url}: {exc}"

        filter_complex = (
            "[0:v]eq=brightness=0.39[vbright];"
            "[2:v][vbright]scale2ref=w=iw:h=ih:force_original_aspect_ratio=decrease[pscale][vref];"
            "[vref][pscale]overlay=(W-w)/2:(H-h)/2[vout]"
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
            "-i", input_path,
            "-stream_loop", "-1", "-i", music_path,
            "-i", overlay_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
        return _run_ffmpeg_raw(cmd, timeout=300)


# ---------- Lab Adjust ----------

def _run_labadjust(
    input_path: str,
    output_path: str,
    l: int = 0,
    a: int = 0,
    b: int = 0,
) -> tuple[bool, str]:
    """Negate selected Lab color channels using an ImageMagick HALD CLUT.

    Generates a hald:8 LUT in Lab color space, negates the requested channels
    (l=L*, a=a*, b=b* — mapped to r/g/b in ImageMagick's Lab representation),
    converts back to sRGB, then applies the LUT via FFmpeg's haldclut filter.

    Args:
        l — negate the L* (luminance) channel (0 or 1)
        a — negate the a* (green–red) channel (0 or 1)
        b — negate the b* (blue–yellow) channel (0 or 1)
    """
    channels = ""
    if int(l) == 1:
        channels += "r"
    if int(a) == 1:
        channels += "g"
    if int(b) == 1:
        channels += "b"

    # If no channels selected, just copy
    if not channels:
        cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
               "-i", input_path, "-c", "copy", output_path]
        return _run_ffmpeg_raw(cmd, timeout=60)

    with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as tf:
        lut_path = tf.name

    try:
        # Generate HALD CLUT: Lab colorspace, negate selected channels, back to sRGB
        magick_cmd = [
            "magick", "hald:8",
            "-colorspace", "lab",
            "-channel", channels,
            "-negate", "+channel",
            "-colorspace", "srgb",
            lut_path,
        ]
        result = subprocess.run(magick_cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            return False, result.stderr.decode(errors="replace")

        # Apply HALD CLUT via movie= source — identical pattern to huehsv/ccshue.
        # Use -c:a copy (not aac) so the output container/codec is determined
        # by output_path's extension, matching how other haldclut effects work.
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"movie={lut_path},[in]haldclut,format=yuv420p",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        return _run_ffmpeg_raw(cmd, timeout=300)
    finally:
        try:
            os.remove(lut_path)
        except OSError:
            pass


# ---------- Autotune ----------

def _detect_dominant_pitch_hz(wav_path: str) -> float | None:
    """Detect the dominant fundamental frequency of a WAV file using HPS + numpy FFT."""
    try:
        import numpy as np
        import wave as _wave
    except ImportError:
        return None
    try:
        with _wave.open(wav_path, "rb") as wf:
            sr = wf.getframerate()
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
        if sampwidth == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 1:
            samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        elif sampwidth == 4:
            samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            return None
        if nchannels > 1:
            samples = samples.reshape(-1, nchannels).mean(axis=1)
        # Analyse the middle half to skip silence at start/end
        total = len(samples)
        segment = samples[total // 4: total * 3 // 4] if total > 4096 else samples
        frame_size = 4096
        hop = frame_size // 2
        freqs_detected: list[float] = []
        for i in range(0, max(1, len(segment) - frame_size), hop):
            frame = segment[i: i + frame_size]
            if len(frame) < frame_size:
                break
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms < 0.008:
                continue
            windowed = frame * np.hanning(frame_size)
            spectrum = np.abs(np.fft.rfft(windowed))
            freq_bins = np.fft.rfftfreq(frame_size, 1.0 / sr)
            # Harmonic Product Spectrum (down-sample × 2,3,4)
            hps = spectrum.copy()
            for h in range(2, 5):
                dec = spectrum[::h]
                hps[: len(dec)] *= dec
            lo = int(np.searchsorted(freq_bins, 80))
            hi = int(np.searchsorted(freq_bins, 1200))
            if hi <= lo:
                continue
            peak_idx = int(np.argmax(hps[lo:hi])) + lo
            if freq_bins[peak_idx] > 0:
                freqs_detected.append(float(freq_bins[peak_idx]))
        if not freqs_detected:
            return None
        return float(np.median(freqs_detected))
    except Exception:
        return None


def _hz_to_semitone_correction(hz: float, scale: list[int]) -> float:
    """Return semitones to shift so that hz lands on the nearest note in scale."""
    import math
    midi = 69.0 + 12.0 * math.log2(hz / 440.0)
    note_in_octave = midi % 12.0
    best_diff = 99.0
    for n in scale:
        d = (note_in_octave - n) % 12.0
        if d > 6.0:
            d -= 12.0
        if abs(d) < abs(best_diff):
            best_diff = d
    return -best_diff  # positive = shift up


def _run_autotune(
    input_path: str,
    output_path: str,
    key: str = "chromatic",
    strength: float = 1.0,
) -> tuple[bool, str]:
    """Pitch-correct audio to the nearest notes in a musical key.

    Uses numpy FFT (HPS method) for dominant pitch detection and FFmpeg's
    rubberband audio filter for pitch shifting with formant preservation.

    Args:
        key:      chromatic | major | minor | pentatonic  (default: chromatic)
        strength: 0.0–1.0 correction amount (default: 1.0 = full snap)
    """
    SCALES: dict[str, list[int]] = {
        "chromatic":   list(range(12)),
        "major":       [0, 2, 4, 5, 7, 9, 11],
        "minor":       [0, 2, 3, 5, 7, 8, 10],
        "pentatonic":  [0, 2, 4, 7, 9],
    }
    scale = SCALES.get(key.lower(), SCALES["chromatic"])

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = os.path.join(tmpdir, "audio.wav")
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path, "-vn", "-ac", "1", "-ar", "22050", "-f", "wav", wav_path,
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=60)
        if not ok:
            return False, f"autotune: audio extraction failed: {err}"

        dominant_hz = _detect_dominant_pitch_hz(wav_path)
        if dominant_hz is None or dominant_hz <= 0:
            # No pitched content detected — pass through unchanged
            return _run_ffmpeg_raw(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-i", input_path, "-c", "copy", output_path], timeout=60
            )

        correction_st = _hz_to_semitone_correction(dominant_hz, scale) * strength
        if abs(correction_st) < 0.05:
            return _run_ffmpeg_raw(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-i", input_path, "-c", "copy", output_path], timeout=60
            )

        import math
        pitch_ratio = 2.0 ** (correction_st / 12.0)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-af", f"rubberband=pitch={pitch_ratio:.6f}:formant=1",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=180)
        if not ok:
            return False, f"autotune: rubberband failed: {err}"
        return True, f"autotune: {dominant_hz:.1f} Hz → {correction_st:+.2f} st correction"


# ---------- Reference-based autotune (th/autotune / th/autotoon) ----------

def _pitch_detect_wav_stdlib(wav_path: str, min_hz: float = 80.0, max_hz: float = 1200.0) -> float | None:
    """Autocorrelation pitch detector — pure Python stdlib, no numpy required."""
    import wave, struct, math
    try:
        with wave.open(wav_path, "rb") as wf:
            sr = wf.getframerate()
            nch = wf.getnchannels()
            sw = wf.getsampwidth()
            total = wf.getnframes()
            skip = total // 4
            use = min(sr, max(0, total - skip))  # ≤ 1 second
            if use <= 0:
                return None
            wf.setpos(skip)
            raw = wf.readframes(use)
        fmt = {1: "b", 2: "h", 4: "i"}.get(sw)
        if not fmt:
            return None
        n_raw = (len(raw) // (sw * nch)) * (sw * nch)
        raw = raw[:n_raw]
        all_s = struct.unpack(f"{len(raw) // sw}{fmt}", raw)
        if nch > 1:
            samples = [sum(all_s[i:i + nch]) / nch for i in range(0, len(all_s) - nch + 1, nch)]
        else:
            samples = list(all_s)
        peak = max((abs(s) for s in samples), default=1) or 1
        samples = [s / peak for s in samples]
        frame_sz = 512
        hop = frame_sz // 2
        min_lag = max(1, int(sr / max_hz))
        max_lag = int(sr / min_hz)
        found: list[float] = []
        for start in range(0, max(1, len(samples) - frame_sz), hop):
            f = samples[start:start + frame_sz]
            if len(f) < frame_sz:
                break
            rms = math.sqrt(sum(x * x for x in f) / frame_sz)
            if rms < 0.01:
                continue
            best, best_lag = -1e18, min_lag
            for lag in range(min_lag, min(max_lag, frame_sz // 2)):
                c = sum(f[i] * f[i + lag] for i in range(frame_sz - lag))
                if c > best:
                    best, best_lag = c, lag
            if best > 0:
                found.append(sr / best_lag)
        if not found:
            return None
        found.sort()
        return found[len(found) // 2]
    except Exception:
        return None


def _ytdlp_download_audio_wav(query_or_url: str, output_wav: str, max_dur: int = 600) -> tuple[bool, str]:
    """Download audio as mono 44 100 Hz WAV using yt-dlp.

    query_or_url may be a full URL or a plain search query (searched on YouTube).
    """
    import subprocess as _sp, tempfile as _tf, os as _os
    is_url = query_or_url.startswith(("http://", "https://"))
    source = query_or_url if is_url else f"ytsearch1:{query_or_url}"
    with _tf.TemporaryDirectory() as dl_dir:
        tmpl = _os.path.join(dl_dir, "ref.%(ext)s")
        cmd = [
            "yt-dlp", "--no-playlist", "-x",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "--no-warnings",
            "-o", tmpl,
            source,
        ]
        r = _sp.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, f"yt-dlp error: {r.stderr[-600:]}"
        # Locate downloaded WAV (yt-dlp may produce any ext before conversion)
        dl_path = None
        for fn in _os.listdir(dl_dir):
            dl_path = _os.path.join(dl_dir, fn)
            break
        if not dl_path or not _os.path.exists(dl_path):
            return False, "yt-dlp: no output file found."
        conv = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", dl_path,
            "-ac", "1", "-ar", "44100",
            "-t", str(max_dur),
            output_wav,
        ]
        rc = _sp.run(conv, capture_output=True, timeout=120)
        if rc.returncode != 0:
            return False, f"ffmpeg convert: {rc.stderr.decode()[-400:]}"
        return True, ""


def _run_autotune_reference(
    base_path: str,
    ref_wav: str,
    output_path: str,
    strength: float = 1.0,
) -> tuple[bool, str]:
    """Pitch-correct base media to match dominant pitch of reference WAV.

    Detects average pitch of both signals via autocorrelation, computes the
    semitone offset, and applies it with FFmpeg's rubberband filter (formant-
    preserved).  Falls back to passthrough if pitch detection fails.
    """
    import math
    with tempfile.TemporaryDirectory() as tmpdir:
        base_wav = os.path.join(tmpdir, "base.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", base_path, "-vn", "-ac", "1", "-ar", "44100", base_wav,
        ], timeout=90)
        if not ok:
            return False, f"Audio extraction failed: {err}"

        base_hz = _pitch_detect_wav_stdlib(base_wav)
        ref_hz = _pitch_detect_wav_stdlib(ref_wav)

        if not base_hz or not ref_hz or base_hz <= 0 or ref_hz <= 0:
            return _run_ffmpeg_raw([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", base_path, "-c", "copy", output_path,
            ], timeout=60)

        shift_st = 12.0 * math.log2(ref_hz / base_hz) * strength
        shift_st = max(-24.0, min(24.0, shift_st))
        pitch_ratio = 2.0 ** (shift_st / 12.0)

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", base_path,
            "-af", f"rubberband=pitch={pitch_ratio:.6f}:formant=1",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=180)
        if not ok:
            return False, f"rubberband failed: {err}"
        return True, f"{base_hz:.1f} Hz → {ref_hz:.1f} Hz ({shift_st:+.2f} st)"


# ---------- Grid overlay (th/addsource) ----------

def _run_grid_overlay(
    base_path: str,
    overlay_path: str,
    rows: int,
    cols: int,
    pos: int,          # 1-indexed
    output_path: str,
    use_base_audio: bool = False,
    trim_duration: float | None = None,
    overlay_start: float | None = None,
) -> tuple[bool, str]:
    """Overlay overlay_path into a specific grid cell of base_path.

    The base frame is divided into a rows×cols grid.  pos is 1-indexed,
    counted left-to-right then top-to-bottom.  The overlay is scaled to
    exactly fill the cell.

    When trim_duration is given the base video is end-trimmed to that many
    seconds using the reverse→trim→reverse pattern, and base audio is
    end-trimmed with areverse→atrim→areverse.  Audio always comes from the
    base track when trim_duration is supplied (matching the TS reference).
    Without trim_duration, audio source is controlled by use_base_audio.
    overlay_start optionally skips that many seconds from the beginning of
    the overlay video before compositing it.
    """
    import subprocess as _sp

    # ── 1. Probe base dimensions ───────────────────────────────────────────────
    r = _sp.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", base_path],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return False, f"ffprobe (dimensions) failed: {r.stderr}"
    try:
        base_w, base_h = map(int, r.stdout.strip().split(","))
    except Exception:
        return False, f"Could not parse base dimensions: {r.stdout}"

    # ── 2. Probe base duration (used when trim_duration is not supplied) ────────
    r2 = _sp.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", base_path],
        capture_output=True, text=True, timeout=30,
    )
    base_dur: float | None = None
    if r2.returncode == 0:
        try:
            base_dur = float(r2.stdout.strip())
        except Exception:
            pass

    # ── 3. Calculate cell geometry ─────────────────────────────────────────────
    idx    = pos - 1
    row    = idx // cols
    col    = idx % cols
    cell_w = base_w // cols
    cell_h = base_h // rows
    x_pos  = col * cell_w
    y_pos  = row * cell_h

    # ── 4. Build FFmpeg filter_complex ─────────────────────────────────────────
    if trim_duration is not None:
        # End-trim pattern: reverse→trim→reverse selects the last N seconds.
        # Audio is dropped (silent output) — base track is muted.
        # Overlay is scaled to 2× cell size (clamped to frame bounds) so it
        # sits prominently over the grid rather than being confined to one cell.
        t = trim_duration
        filter_parts = [
            f"[0:v]reverse,trim=0:{t},setpts=PTS-STARTPTS,reverse,setpts=PTS-STARTPTS[trimmed_base]",
            f"[trimmed_base]scale={base_w}:{base_h}[scaled_base]",
            (
                f"[1:v]trim=start={overlay_start or 0}:duration={t},"
                f"setpts=PTS-STARTPTS,format=rgb24,scale={cell_w}:{cell_h}[ov]"
            ),
            f"[scaled_base][ov]overlay={x_pos}:{y_pos}[out_v]",
        ]
        filter_complex = ";".join(filter_parts)
        map_args = ["-map", "[out_v]", "-map", "1:a?"]
        dur_args: list[str] = []
    else:
        overlay_filter = (
            f"[1:v]trim=start={overlay_start},setpts=PTS-STARTPTS,"
            f"format=rgb24,scale={cell_w}:{cell_h}[ov]"
            if overlay_start is not None
            else f"[1:v]format=rgb24,scale={cell_w}:{cell_h}[ov]"
        )
        filter_complex = (
            f"[0:v]scale={base_w}:{base_h}[base];"
            f"{overlay_filter};"
            f"[base][ov]overlay={x_pos}:{y_pos}"
        )
        map_args = ["-map", "0:a?"] if use_base_audio else ["-map", "1:a?"]
        dur_args = ["-t", str(base_dur)] if base_dur else []

    cmd = [
        "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
        "-i", base_path,
        "-i", overlay_path,
        "-filter_complex", filter_complex,
    ] + map_args + [
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-shortest",
    ] + dur_args + [output_path]

    return _run_ffmpeg_raw(cmd, timeout=300)


# ---------- Vocoder ----------

_VOCODER_PROFILES: dict[str, dict] = {
    "ilvocodex":     {"bandwidth": 256, "window_size": 1024, "mod_phases": 6,  "post_highpass": 200, "bass_g": -10, "alimiter": 0.2, "post_phases": 0},
    "orangevocoder": {"bandwidth": 256, "window_size": 1024, "mod_phases": 0,  "post_highpass": 200, "bass_g": -10, "alimiter": 0.2, "post_phases": 0},
    "4ormulator":    {"bandwidth": 128, "window_size": 256,  "mod_phases": 0,  "post_highpass": 100, "bass_g": -10, "alimiter": 0.2, "post_phases": 0},
    "audacity":      {"bandwidth": 64,  "window_size": 512,  "mod_phases": 0,  "post_highpass": 200, "bass_g": -10, "alimiter": 0.5, "post_phases": 12},
    # magix: large 2048-point window → higher frequency resolution; default 256 bands.
    # Mirrors the -w 2048 -v 10 -N exe flags; alimiter 0.5 keeps output at a safe level.
    "magix":         {"bandwidth": 256, "window_size": 2048, "mod_phases": 0,  "post_highpass": 200, "bass_g": -10, "alimiter": 0.5, "post_phases": 0},
}


def _run_vocoder(
    input_path: str,
    output_path: str,
    carrier_url: str,
    mode: str = "ilvocodex",
    bandwidth: int | None = None,
) -> tuple[bool, str]:
    """FFT phase vocoder: shape carrier audio with voice (modulator) frequency envelope.

    Pure Python/numpy port of the vocoder.ts pipeline — no Wine or exe required.
    Modes: ilvocodex | orangevocoder | 4ormulator | audacity

    Args:
        carrier_url: URL to a carrier audio file (synth pad, drone, instrument…)
        mode:        vocoder profile (default: ilvocodex)
        bandwidth:   number of frequency bands; None = use profile default
    """
    try:
        import numpy as np
        import wave as _wave
    except ImportError:
        return False, "numpy not installed — run: pip install numpy"

    m = mode.lower()
    if m not in _VOCODER_PROFILES:
        return False, f"Unknown vocoder mode '{mode}'. Valid: {', '.join(_VOCODER_PROFILES)}"

    p = _VOCODER_PROFILES[m]
    n_bands = bandwidth if (bandwidth and bandwidth > 0) else p["bandwidth"]
    win_size = p["window_size"]

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── 1. Download carrier ─────────────────────────────────────────────
        carrier_dl = os.path.join(tmpdir, "carrier_dl")
        try:
            import urllib.request, ssl as _ssl
            _ctx = _ssl.create_default_context()
            _req = urllib.request.Request(carrier_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(_req, context=_ctx, timeout=60) as _resp:
                with open(carrier_dl, "wb") as _fh:
                    _fh.write(_resp.read())
        except Exception as exc:
            return False, f"vocoder: failed to download carrier from {carrier_url}: {exc}"

        carrier_wav = os.path.join(tmpdir, "carrier.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", carrier_dl, "-ac", "1", "-ar", "48000", "-f", "wav", carrier_wav,
        ], timeout=60)
        if not ok:
            return False, f"vocoder: carrier conversion failed: {err}"

        # ── 2. Get video duration ──────────────────────────────────────────
        dur_res = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True,
        )
        try:
            duration = float(dur_res.stdout.strip())
        except Exception:
            duration = 30.0

        # ── 3. Extract modulator (voice from video) ───────────────────────
        mod_wav = os.path.join(tmpdir, "mod.wav")
        mod_cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                   "-i", input_path, "-ac", "1", "-ar", "48000", "-vn"]
        if p["mod_phases"] > 0:
            mod_af = ",".join(["aphaseshift=order=16:shift=1"] * p["mod_phases"])
            mod_cmd += ["-af", mod_af]
        mod_cmd += ["-f", "wav", mod_wav]
        ok, err = _run_ffmpeg_raw(mod_cmd, timeout=60)
        if not ok:
            return False, f"vocoder: modulator extraction failed: {err}"

        # ── 4. Loop carrier to match duration ─────────────────────────────
        carr_wav = os.path.join(tmpdir, "carr.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", carrier_wav,
            "-ac", "1", "-ar", "48000", "-t", str(duration), "-f", "wav", carr_wav,
        ], timeout=60)
        if not ok:
            return False, f"vocoder: carrier loop failed: {err}"

        # ── 5. Python FFT phase vocoder ────────────────────────────────────
        def _read_mono(path: str):
            with _wave.open(path, "rb") as wf:
                sr = wf.getframerate()
                sw = wf.getsampwidth()
                nc = wf.getnchannels()
                raw = wf.readframes(wf.getnframes())
            if sw == 2:
                s = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sw == 1:
                s = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
            elif sw == 4:
                s = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                s = np.zeros(wf.getnframes(), dtype=np.float32)
            if nc > 1:
                s = s.reshape(-1, nc).mean(axis=1)
            return s, sr

        mod_samples, sr = _read_mono(mod_wav)
        car_samples, _  = _read_mono(carr_wav)

        n = min(len(mod_samples), len(car_samples))
        mod_samples = mod_samples[:n]
        car_samples = car_samples[:n]

        hop = win_size // 4
        window = np.hanning(win_size).astype(np.float32)
        output = np.zeros(n + win_size, dtype=np.float32)
        n_fft = win_size // 2 + 1
        bins_per_band = max(1, n_fft // n_bands)

        for start in range(0, n - win_size, hop):
            mod_frame = mod_samples[start: start + win_size] * window
            car_frame = car_samples[start: start + win_size] * window
            mod_fft = np.fft.rfft(mod_frame)
            car_fft = np.fft.rfft(car_frame)
            mod_mag = np.abs(mod_fft)
            car_phase = np.angle(car_fft)
            out_fft = np.zeros(n_fft, dtype=np.complex64)
            for band in range(n_bands):
                bs = band * bins_per_band
                be = min(bs + bins_per_band, n_fft)
                env = float(np.mean(mod_mag[bs:be]))
                out_fft[bs:be] = env * np.exp(1j * car_phase[bs:be])
            out_frame = np.fft.irfft(out_fft)[:win_size] * window
            output[start: start + win_size] += out_frame

        result = output[:n]

        voc_wav = os.path.join(tmpdir, "vocoded.wav")
        with _wave.open(voc_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes((result * 32767).astype(np.int16).tobytes())

        # ── 6. Post-filters (per profile) ─────────────────────────────────
        post_af_parts = [
            f"highpass=f={p['post_highpass']}",
            f"bass=g={p['bass_g']}",
            f"alimiter=limit={p['alimiter']}:latency=1",
        ]
        if p["post_phases"] > 0:
            post_af_parts += ["aphaseshift=order=16:shift=1"] * p["post_phases"]
        post_af = ",".join(post_af_parts)

        # ── 7. Mux vocoded audio back with original video ─────────────────
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path, "-i", voc_wav,
            "-af", post_af,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=180)
        if not ok:
            # Audio-only fallback (no video stream)
            cmd2 = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", voc_wav, "-af", post_af,
                "-c:a", "aac", "-b:a", "192k", output_path,
            ]
            ok, err = _run_ffmpeg_raw(cmd2, timeout=180)

        return ok, err if not ok else f"vocoder: {m} mode, {n_bands} bands, {duration:.1f}s"


# ---------- Sidechaingate Vocoder (FFmpeg firequalizer + sidechaingate) ----------

def _run_scgv(
    input_path: str,
    output_path: str,
    carrier_url: str,
    bandwidth: int = 64,
    detection: str = "peak",
    release: float = 50.0,
    attack: float = 0.01,
    ratio: float = 2.0,
    threshold: float = 1.0,
    makeup: float = 1.0,
    knee: float = 8.0,
    pitch: float = 0.0,
    range_val: float = 0.0,
    volume: float = 1.0,
) -> tuple[bool, str]:
    """Sidechaingate vocoder: shape a carrier with the frequency envelope of the modulator.

    Ports the TypeScript generateVocoderCommand() filtergraph to Python FFmpeg.
    - Input 0 (input_path): modulator (your video/audio)
    - Input 1 (carrier_url, stream-looped): carrier (synth/pad)
    - Output: video from input 0 + sidechaingate-vocoded audio
    """
    import urllib.request, ssl as _ssl

    bw = max(1, min(int(bandwidth), 256))

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download carrier
        carrier_ext = os.path.splitext(carrier_url.split("?")[0])[-1] or ".mp3"
        carrier_dl = os.path.join(tmpdir, f"carrier{carrier_ext}")
        try:
            _ctx = _ssl.create_default_context()
            _req = urllib.request.Request(carrier_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(_req, context=_ctx, timeout=60) as _resp:
                with open(carrier_dl, "wb") as _fh:
                    _fh.write(_resp.read())
        except Exception as exc:
            return False, f"scgv: failed to download carrier from {carrier_url}: {exc}"

        # Build filtergraph
        rubberband = (
            f"rubberband=pitch=2^({pitch}/12):phase=2.14748e+09/3:window=short,"
            if pitch != 0 else ""
        )

        mod_labels  = "".join(f"[mod{i}]" for i in range(1, bw + 1))
        carr_labels = "".join(f"[carr{i}]" for i in range(1, bw + 1))

        fg_parts: list[str] = []
        fg_parts.append(f"[0:a]aformat=cl=mono,{rubberband}asplit={bw}{mod_labels}")
        fg_parts.append(f"[1:a]aformat=cl=mono,asplit={bw}{carr_labels}")

        for i in range(1, bw + 1):
            lo = (i - 1) * 20000 / bw
            hi = i * 20000 / bw
            gain = f"if(between(f,{lo},{hi}),0,-INF)"
            fg_parts.append(
                f"[mod{i}]firequalizer=gain='{gain}':accuracy=100:fft2=1,atrim=0.01[m{i}]"
            )

        for i in range(1, bw + 1):
            lo = (i - 1) * 20000 / bw
            hi = i * 20000 / bw
            gain = f"if(between(f,{lo},{hi}),0,-INF)"
            fg_parts.append(
                f"[carr{i}]firequalizer=gain='{gain}':accuracy=100:fft2=1,atrim=0.01[c{i}]"
            )

        for i in range(1, bw + 1):
            fg_parts.append(
                f"[c{i}][m{i}]sidechaingate="
                f"ratio={ratio}:threshold={threshold}:range={range_val}:"
                f"attack={attack}:release={release}:makeup={makeup}:"
                f"knee={knee}:detection={detection}:level_sc=sqrt({bw})[v{i}]"
            )

        mix_inputs = "".join(f"[v{i}]" for i in range(1, bw + 1))
        fg_parts.append(
            f"{mix_inputs}amix={bw}:normalize=0,crystalizer,alimiter={volume}:latency=1[a]"
        )

        filtergraph = ";".join(fg_parts)

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-stream_loop", "-1", "-i", carrier_dl,
            "-filter_complex", filtergraph,
            "-map", "0:v?",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=600)
        return ok, err if not ok else f"scgv: {bw} bands, {detection} detection"


# ---------- Swirl ----------

def _run_swirl(
    input_path: str,
    output_path: str,
    strength: float | str = 180.0,  # accepts numeric or FFmpeg expression string
    radius: float = 0.5,
    xc: float = 0.5,
    yc: float = 0.5,
    fallout: str = "quad",
    is1to1: bool = True,
) -> tuple[bool, str]:
    """Apply a swirl/vortex distortion via FFmpeg geq.

    Args:
        strength  — twist amount multiplier (scaled by PI²×255/180 internally)
        radius    — normalized radius 0–1 of min(W,H) (default 0.5)
        xc / yc  — normalized center 0–1 (default 0.5 = center)
        fallout   — attenuation curve: 'linear' or 'quad' (default quad)
        is1to1    — scale to square before swirl then restore aspect ratio (default True)
    """
    fallout = fallout.lower()
    if fallout not in ("linear", "quad"):
        fallout = "quad"

    vinfo = _ffprobe_video_info(input_path)
    w = vinfo["width"] or 854
    h = vinfo["height"] or 480
    has_audio = vinfo.get("duration", 0) > 0 and Path(input_path).suffix.lower() in VIDEO_EXTENSIONS

    power = "^2" if fallout == "quad" else ""

    # Attenuation: 1→0 within min(W,H)*radius of centre, 0 outside
    atten = (
        f"(if(lt(hypot(X-W*{xc},Y-H*{yc})+1e-6,min(W,H)*{radius}),"
        f"1-(hypot(X-W*{xc},Y-H*{yc})+1e-6)/(min(W,H)*{radius}),0){power})"
    )
    # Angle formula matches TypeScript: amount * PI² * (-255/180)
    angle = f"(({strength})*(PI^2)*(-255/180))"
    calc_cos = f"cos((atan2(Y-H*{yc},X-W*{xc}))+{angle}*{atten})"
    calc_sin = f"sin((atan2(Y-H*{yc},X-W*{xc}))+{angle}*{atten})"
    geq_core = (
        f"geq='p(W*{xc}+(hypot(X-W*{xc},Y-H*{yc})+1e-6)*{calc_cos},"
        f"H*{yc}+(hypot(X-W*{xc},Y-H*{yc})+1e-6)*{calc_sin})'"
    )

    if is1to1:
        vf = f"format=yuv444p,scale={h}:{h},{geq_core},scale={w}:{h},setsar=1:1,format=yuv420p"
    else:
        vf = f"format=yuv444p,{geq_core},scale=iw:ih,format=yuv420p"

    if has_audio:
        cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
            "-vf", vf,
            output_path,
        ]

    return _run_ffmpeg_raw(cmd, timeout=300)


# ---------- ccshue (ImageMagick haldclut — hue/sat/gamma/gain/offset) ----------

def _run_ccshue(
    input_path: str,
    output_path: str,
    hue: float = 0.0,
    sat: float = 1.0,
    gamma: float = 1.0,
    gain: float = 1.0,
    offset: float = 0.0,
) -> tuple[bool, str]:
    """Apply color-correction via ImageMagick haldclut + FFmpeg haldclut filter.

    Parameters (all optional, pass only what you want to change):
        hue    — rotation in degrees (-180…180, default 0)
        sat    — saturation multiplier (default 1.0)
        gamma  — gamma correction (default 1.0)
        gain   — RGB gain / multiply (default 1.0)
        offset — add to every channel (-1…1, default 0)

    Generates ccs.ppm via:
        magick hald:8 [hue] [sat] [gamma] [gain] [offset] ccs.ppm
    Then applies:
        ffmpeg -i input -vf "movie=ccs.ppm,[in]haldclut" output
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        hald_path = os.path.join(tmpdir, "ccs.ppm")

        cmd = ["magick", "hald:8"]

        # Hue rotation (YUV-space rotation matrix via -fx)
        if abs(hue) > 0.001:
            angle_fx = (
                f"angle={hue}*pi/180; "
                "channel(u,"
                ".5+(u.g-.5)*cos(angle)-(u.b-.5)*sin(angle),"
                ".5+(u.g-.5)*sin(angle)+(u.b-.5)*cos(angle))"
            )
            cmd += ["-colorspace", "yuv", "-fx", angle_fx, "-colorspace", "srgb"]

        # Saturation (YUV-space scaling)
        if abs(sat - 1.0) > 0.001:
            sat_fx = (
                f"sat={sat}; "
                "channel(u,(u-.5)*sat+.5,(u-.5)*sat+.5)"
            )
            cmd += ["-colorspace", "yuv", "-fx", sat_fx, "-colorspace", "srgb"]

        # Gamma
        if abs(gamma - 1.0) > 0.001:
            cmd += ["-gamma", f"{gamma:.6g}"]

        # Gain (multiply all channels)
        if abs(gain - 1.0) > 0.001:
            cmd += ["-evaluate", "multiply", f"{gain:.6g}"]

        # Offset (add; 127.5 is half of 8-bit full range)
        if abs(offset) > 0.001:
            cmd += ["-evaluate", "add", f"{offset * 127.5:.4f}"]

        cmd.append(hald_path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, f"ccshue: ImageMagick failed: {result.stderr.strip()}"

        # Apply haldclut via FFmpeg
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
            "-vf", f"movie={hald_path},[in]haldclut",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            output_path,
        ], timeout=180)
        if not ok:
            return False, f"ccshue: FFmpeg haldclut failed: {err}"

        return True, ""


# ---------- ImageMagick pipe effect ----------

def _run_imagemagick(
    input_path: str,
    output_path: str,
    params: list[str],
) -> tuple[bool, str]:
    """Apply arbitrary ImageMagick arguments to a video (frame-by-frame) or image.

    Pipe usage: imagemagick=<magick args>  or  im=<magick args>
    e.g. imagemagick=-negate
         imagemagick=-colorspace Gray
         imagemagick=-blur 0x8|-edge|1   (params split by pipe/space both work)

    For videos:
      1. Probe framerate with ffprobe.
      2. Extract frames as PPM (lossless, fast for ImageMagick I/O).
      3. Extract audio stream to WAV.
      4. Apply magick to every frame **in parallel** (in-place: same file in/out).
      5. Reassemble frames + audio into the output container.
    For images: runs magick directly on the file.
    """
    import concurrent.futures

    # Normalize params: join and shlex-split so both paren-syntax (single raw
    # string, e.g. imagemagick(-blur 0x8 -edge 1)) and equals-syntax
    # (pre-split list, e.g. imagemagick=-blur|0x8) yield the same arg list.
    try:
        magick_args = shlex.split(" ".join(params))
    except ValueError as e:
        return False, f"imagemagick: could not parse args ({e}). Use: imagemagick(-option value …)"

    ext = Path(input_path).suffix.lower()
    is_video = ext in VIDEO_EXTENSIONS

    with tempfile.TemporaryDirectory() as tmpdir:
        if is_video:
            # --- 1. Probe framerate ---
            vinfo = _ffprobe_video_info(input_path)
            fps_str = vinfo.get("r_frame_rate", "30")  # raw fraction e.g. "30000/1001"
            has_audio = vinfo.get("duration", 0) > 0 and ext in AUDIO_VIDEO_EXTS

            # --- 2. Extract frames as PPM ---
            # -r before -i sets the input/decode framerate for the image sequence.
            frames_tmpl = os.path.join(tmpdir, "frame_%04d.ppm")
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                "-r", fps_str,
                "-i", input_path,
                frames_tmpl,
            ], timeout=120)
            if not ok:
                return False, f"imagemagick: frame extraction failed: {err}"

            # --- 3. Extract audio (best-effort) ---
            audio_path = os.path.join(tmpdir, "audio.wav")
            if has_audio:
                _run_ffmpeg_raw([
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", input_path,
                    audio_path,
                ], timeout=60)

            # --- 4. Apply ImageMagick to each frame in parallel (in-place) ---
            frame_files = sorted(
                os.path.join(tmpdir, f)
                for f in os.listdir(tmpdir)
                if f.startswith("frame_") and f.endswith(".ppm")
            )
            if not frame_files:
                return False, "imagemagick: no frames extracted"

            def _process_frame(fp: str) -> str | None:
                result = subprocess.run(
                    ["magick", fp] + magick_args + [fp],
                    capture_output=True, text=True, timeout=60,
                )
                return result.stderr.strip() if result.returncode != 0 else None

            with concurrent.futures.ThreadPoolExecutor() as pool:
                frame_errors = list(pool.map(_process_frame, frame_files))

            failed = [(i, e) for i, e in enumerate(frame_errors) if e]
            if failed:
                i, e = failed[0]
                return False, f"imagemagick: frame {i} failed: {e}"

            # --- 5. Reassemble processed frames + audio ---
            if has_audio and os.path.exists(audio_path):
                reassemble_cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-r", fps_str,
                    "-i", frames_tmpl,
                    "-i", audio_path,
                    "-vf", "scale=-1:floor(ih/2)*2,setsar=1:1",
                    "-map", "0:v", "-map", "1:a",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path,
                ]
            else:
                reassemble_cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-r", fps_str,
                    "-i", frames_tmpl,
                    "-vf", "scale=-1:floor(ih/2)*2,setsar=1:1",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path,
                ]

            ok, err = _run_ffmpeg_raw(reassemble_cmd, timeout=300)
            if not ok:
                return False, f"imagemagick: reassemble failed: {err}"

            return True, ""

        else:
            # --- Static image: run magick directly ---
            result = subprocess.run(
                ["magick", input_path] + magick_args + [output_path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return False, f"imagemagick: magick failed: {result.stderr.strip()}"
            return True, ""


# ---------- Wave presets ----------

WAVE_PRESETS = {
    "largeWave":
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*5.4)))*(-15*2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*5.4)))*(-15*2)))',setsar=1:1,format=yuv420p",
    "mediumWave":
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*14)))*(-15*2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*14)))*(-15*2)))',setsar=1:1,format=yuv420p",
    "smallWave":
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*20)))*(-15*1.2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*20)))*(-15*1.2)))',setsar=1:1,format=yuv420p",
    "horizontalOnly":
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0.053*15))+(Y/H)*(PI*10)))*(-15*1.5)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*0)))*(-15*0)))',setsar=1:1,format=yuv420p",
    "verticalOnly":
        "format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*0)))*(-15*0)),Y-((sin((T*5*0+(0.053*15))+(X/W)*(PI*10)))*(-15*1.6)))',setsar=1:1,format=yuv420p",
}

# ---------- Pipe effects engine ----------

PIPE_EFFECT_NAMES = {
    "hflip", "vflip", "invert", "negate", "grayscale", "sepia", "rotate",
    "ccshue", "brightness", "contrast", "saturation", "swapuv", "mirror",
    "zoom", "pinch&punch", "p&p", "pinchpunch", "gm91deform",
    "invertrgb", "invlum", "volume", "vibrato", "areverse", "vreverse",
    "channelblend", "huehsv", "multipitch", "mp", "multi", "lut",
    "syncaudio", "speed", "ffmpeg", "frei0r",
    "wave",
    "tvsim", "tv",
    "swirl",
    "sierpinskiransomware", "srw",
    "preview1280", "p1280", "scale1280",
    "oppositep1280", "op1280",
    "earthquake", "nbfx",
    "ssmp", "soundstretchmultipitch",
    "multipitchsox", "mpsox",
    "pitchtransition", "pitchtrans",
    "folkvalley", "fv",
    "labadjust", "labadj",
    "vocoder", "ilvocodex", "orangevocoder", "4ormulator", "audacity", "magix",
    "alimiter",
    "freakzinga", "fzgm156", "freakzingagm156", "fgm156",
    "multipitch2", "mp2",
    "multipitch3", "mp3",
    "jitter",
    "randomjitter", "rj",
    "trim",
    "leftsplit",
    "rightsplit",
    "ripple",
    "scroll",
    "pan",
    "tile",
    "watermark", "ring", "miui", "reddit",
    "caption",
    "orb", "deorb",
    "vebfisheye2", "vebdefisheye2", "vebfisheye3", "vebdefisheye3",
    "chromashift",
    "🥸🥸", "﷽", "𒐫",
    "gm4", "realgm4",
    "acontrast", "adestroy", "audioequalizer",
    "avflip",
    "nepeta",
    "nparisonffmpeg", "nineparisonffmpeg",
    "wave2",
    "wmm3dripple", "wmm",
    "timecode",
    "radar",
    "freakzingatesteffect", "fzte", "freaktest",
    "stretch",
    "gradientmap", "gmap",
    "spherize", "sphere", "bulge",
    "imagemagick", "im",
    "(=)",
    "(<>)",
    "geq",
    "scgv", "sidechaingate_vocoder",
}

# ---------- User-submitted named pipe effects ----------

_USER_EFFECTS_FILE = Path("bot/user_effects.json")
_USER_EFFECTS: dict[str, dict] = {}


def _load_user_effects() -> None:
    global _USER_EFFECTS
    try:
        if _USER_EFFECTS_FILE.exists():
            with _USER_EFFECTS_FILE.open() as f:
                _USER_EFFECTS = json.load(f)
    except Exception as e:
        print(f"[user_effects] Failed to load: {e}")
        _USER_EFFECTS = {}


def _save_user_effects() -> None:
    try:
        _USER_EFFECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _USER_EFFECTS_FILE.open("w") as f:
            json.dump(_USER_EFFECTS, f, indent=2)
    except Exception as e:
        print(f"[user_effects] Failed to save: {e}")


def _effect_guild_name(ctx: commands.Context) -> str:
    """Return the guild name to store for a user effect or random-media entry."""
    if ctx.guild:
        return ctx.guild.name or f"Guild {ctx.guild.id}"
    return "Direct Messages"


_load_user_effects()


def _split_effect_params(value: str) -> list[str]:
    """Split effect parameters using the separators users commonly type.

    Commas are intentionally excluded — commas are now the top-level effect
    delimiter, so param values are separated by spaces, pipes, or semicolons.
    """
    return [p.strip() for p in re.split(r"[;|\s]+", value.strip()) if p.strip()]


def _split_pipe_segments(pipe_str: str) -> list[str]:
    """Split pipe_str on ',' (or '>') while respecting parentheses and quotes.

    Any comma or '>' that sits inside unmatched parentheses or brackets, or
    inside a single/double-quoted string, is treated as part of the current
    segment rather than as a delimiter.  This lets expressions like
    ``lerp(0,1,N/$fc)``, ``ffmpeg(...)``, and ``geq='p(X,Y)'`` pass through
    without being incorrectly split.

    Universal paren-depth tracking replaces the earlier _FUNC_NAMES whitelist
    approach, which failed for any function not in the list (e.g. ``lerp``).
    Balanced arithmetic sub-expressions like ``7*(text_h)`` are handled
    correctly because their parens open and close within the same segment.
    """
    segments: list[str] = []
    paren_depth = 0
    array_depth = 0
    in_quote: str | None = None   # current open quote char: "'" or '"'
    current: list[str] = []
    i = 0
    while i < len(pipe_str):
        ch = pipe_str[i]
        # ── Quote context: inside '...' or "...", nothing is a delimiter ──
        if in_quote is not None:
            if ch == in_quote:
                in_quote = None
            current.append(ch)
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            current.append(ch)
            i += 1
            continue
        # ── Normal (unquoted) character processing ─────────────────────────
        if ch == "(":
            paren_depth += 1
            current.append(ch)
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
            current.append(ch)
        elif ch == "[":
            array_depth += 1
            current.append(ch)
        elif ch == "]":
            array_depth = max(0, array_depth - 1)
            current.append(ch)
        elif ch in (",", ">") and paren_depth == 0 and array_depth == 0:
            # pitchtransition voice definitions intentionally contain a comma:
            # pitchtransition=-5,9;5,-9
            current_name = "".join(current).lstrip().lower()
            if ch == "," and re.match(r"^(?:pitchtransition|pitchtrans)(?:=|\s)", current_name):
                # Keep commas inside `start,end` voice pairs, but recognize a
                # following `effect=` assignment as the next effect.
                remainder = pipe_str[i + 1:]
                if not re.match(r"\s*[a-z0-9_&()﷽𒐫🥸]+\s*=", remainder, re.IGNORECASE):
                    current.append(ch)
                    i += 1
                    continue
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
        else:
            current.append(ch)
        i += 1
    seg = "".join(current).strip()
    if seg:
        segments.append(seg)
    return segments


def _expand_user_effects(pipe_str: str) -> str:
    """Expand user-submitted named effects within a pipe string.

    Each top-level comma-delimited segment is checked: if its base name
    (the part before ``=`` or whitespace) matches a key in ``_USER_EFFECTS``,
    the segment is replaced with the stored expansion inline.
    """
    if not _USER_EFFECTS:
        return pipe_str
    segments = _split_pipe_segments(pipe_str)
    expanded = []
    for seg in segments:
        base = re.split(r"[=\s]", seg.strip(), 1)[0].lower()
        if base in _USER_EFFECTS:
            expanded.append(_USER_EFFECTS[base]["effects"])
        else:
            expanded.append(seg)
    return ",".join(expanded)


def _parse_pipe_effects(pipe_str: str) -> list[tuple[str, list[str]]]:
    """Parse pipe effects from IHTX custom syntax.

    Effects are separated with semicolons. Each effect can be written as
    ``name=value`` or ``name value``. Parameters can be separated with spaces,
    commas, semicolons, or pipes, so forms like ``swirl=1`` or
    ``lut=https://example.com/lut.cube`` both work.

    ``ffmpeg(...)`` is a special effect whose content is passed verbatim as raw
    FFmpeg args; semicolons inside the parens do *not* act as delimiters.
    """
    pipe_str = _expand_user_effects(pipe_str)
    # VIDEO: <vf_filter> AUDIO: <af_filter> raw format — pass directly to FFmpeg
    if re.search(r'\b(VIDEO|AUDIO):', pipe_str, re.IGNORECASE):
        effects: list[tuple[str, list[str]]] = []
        vf_m = re.search(r'VIDEO:\s*(.*?)(?=\bAUDIO:|$)', pipe_str, re.IGNORECASE | re.DOTALL)
        af_m = re.search(r'AUDIO:\s*(.*?)(?=\bVIDEO:|$)', pipe_str, re.IGNORECASE | re.DOTALL)
        if vf_m:
            vf = vf_m.group(1).strip()
            if vf:
                effects.append(("__rawvf__", [vf]))
        if af_m:
            af = af_m.group(1).strip()
            if af:
                effects.append(("__rawaf__", [af]))
        return effects

    effects = []
    current_name = None
    current_params: list[str] = []

    # A comma is the canonical effect delimiter, but users commonly write
    # adjacent assignments with whitespace:
    #   mp=-7|7 volume=2
    # Do not let the second assignment become another multipitch parameter.
    # This split is deliberately limited to a whitespace followed by a
    # `name=` shape, so ordinary positional parameters (`brightness=1 2 3`)
    # and pipe-separated values (`mp=-7|7`) remain intact.
    raw_parts: list[str] = []
    for segment in _split_pipe_segments(pipe_str):
        assignment_parts = re.split(
            r"\s+(?=[^\s=]+\s*=)",
            segment.strip(),
        )
        raw_parts.extend(part for part in assignment_parts if part.strip())

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        # Strip optional annotations like (magick)
        part = re.sub(r"\s*\(magick\)\s*", "", part, flags=re.IGNORECASE)

        # ffmpeg(...) — raw FFmpeg args, captured verbatim
        ffmpeg_m = re.match(r'^ffmpeg\s*\((.+)\)\s*$', part, re.IGNORECASE | re.DOTALL)
        if ffmpeg_m:
            if current_name is not None:
                effects.append((current_name, current_params))
                current_name = None
                current_params = []
            effects.append(("ffmpeg", [ffmpeg_m.group(1).strip()]))
            continue

        # imagemagick(...) / im(...) — raw ImageMagick args, captured verbatim
        im_m = re.match(r'^(imagemagick|im)\s*\((.+)\)\s*$', part, re.IGNORECASE | re.DOTALL)
        if im_m:
            if current_name is not None:
                effects.append((current_name, current_params))
                current_name = None
                current_params = []
            effects.append(("imagemagick", [im_m.group(2).strip()]))
            continue

        # leftsplit(...) / rightsplit(...) — inner effects in parens
        split_m = re.match(r'^(leftsplit|rightsplit)\s*\((.+)\)\s*$', part, re.IGNORECASE | re.DOTALL)
        if split_m:
            if current_name is not None:
                effects.append((current_name, current_params))
                current_name = None
                current_params = []
            effects.append((split_m.group(1).lower(), [split_m.group(2).strip()]))
            continue

        if "=" in part:
            if current_name is not None:
                effects.append((current_name, current_params))
            name, value = part.split("=", 1)
            current_name = name.strip().lower()
            vstrip = value.strip()
            if current_name in ("pitchtransition", "pitchtrans"):
                # Preserve the complete decimal pair text verbatim. The
                # generic parameter splitter/math normalizer is not suitable
                # for `start,end;start,end` syntax.
                current_params = [vstrip] if vstrip else []
            elif "::" in value:
                # :: is an explicit param separator — each segment is kept verbatim
                # as one param (no further splitting on | or spaces).
                # Allows: mp2=-4.5|5::G-Major_17  →  params=["-4.5|5", "G-Major_17"]
                current_params = [p.strip() for p in value.split("::") if p.strip()]
            elif current_name == "scroll" and "=" not in value and ":" in value:
                # scroll supports colon-delimited positional syntax:
                #   scroll=x1:y1:x2:y2[:dur]
                current_params = [p.strip() for p in value.split(":") if p.strip()]
            else:
                current_params = _split_effect_params(value)
            continue

        tokens = part.split(None, 1)
        possible_name = tokens[0].strip().lower()
        if possible_name in PIPE_EFFECT_NAMES:
            if current_name is not None:
                effects.append((current_name, current_params))
            current_name = possible_name
            current_params = _split_effect_params(tokens[1]) if len(tokens) > 1 else []
        elif current_name is not None:
            # Treat semicolon fragments after an effect as additional params,
            # e.g. lut=https://example.com/lut.cube
            current_params.extend(_split_effect_params(part))
        else:
            current_name = possible_name
            current_params = _split_effect_params(tokens[1]) if len(tokens) > 1 else []

    if current_name is not None:
        effects.append((current_name, current_params))
    return effects


def _build_ffmpeg_pipe_vf(name: str, params: list[str]) -> str | None:
    """Build a single FFmpeg -vf filter string for a pipe effect."""
    if name == "hflip":
        return "hflip"
    if name == "vflip":
        return "vflip"
    if name in ("invert", "negate"):
        return "negate"
    if name == "grayscale":
        return "colorchannelmixer=.299:.587:.114:0:.299:.587:.114:0:.299:.587:.114"
    if name == "sepia":
        return "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"
    if name == "rotate":
        # Angle is a raw FFmpeg expression in radians — supports any math e.g. -45/180*PI or T*6
        angle = params[0] if params else "0"
        return f"rotate={angle}"
    if name == "ccshue":
        # Handled as a special case in _apply_pipe_effects (needs ImageMagick preprocessing)
        return None
    if name in ("nepeta", "watermark", "ring", "miui", "reddit"):
        # Overlay effects — handled in _apply_pipe_effects (need second input via -i)
        return None
    if name == "frei0r":
        # frei0r=plugin:p1:p2:…  (colon-separated params)
        plugin = params[0] if params else ""
        if not plugin:
            return None
        rest = ":".join(params[1:]) if len(params) > 1 else ""
        return f"frei0r={plugin}:{rest}" if rest else f"frei0r={plugin}"
    if name == "brightness":
        # params: brightness|contrast|saturation|gamma  (all via eq filter, 100=unchanged)
        b = _expr_param(params[0] if params else None, 0.0)
        c = _expr_param(params[1] if len(params) > 1 else None, 1.0)
        s = _expr_param(params[2] if len(params) > 2 else None, 1.0)
        g = _expr_param(params[3] if len(params) > 3 else None, 1.0)
        return f"eq=brightness={b}:contrast={c}:saturation={s}:gamma={g}"
    if name == "contrast":
        # params: contrast|brightness|saturation|gamma
        c = _expr_param(params[0] if params else None, 1.0)
        b = _expr_param(params[1] if len(params) > 1 else None, 0.0)
        s = _expr_param(params[2] if len(params) > 2 else None, 1.0)
        g = _expr_param(params[3] if len(params) > 3 else None, 1.0)
        return f"eq=contrast={c}:brightness={b}:saturation={s}:gamma={g}"
    if name == "saturation":
        # params: saturation|hue_angle_degrees
        s = _expr_param(params[0] if params else None, 1.0)
        h = _expr_param(params[1] if len(params) > 1 else None, 0.0)
        return f"hue=s={s}:h={h}"
    if name == "swapuv":
        return "swapuv"
    if name == "mirror":
        first = (params[0] if params else "").lower().strip()
        _mirror_aliases = {"l": "left", "r": "right", "t": "top", "b": "bottom"}
        first_resolved = _mirror_aliases.get(first, first)
        _preset_names = {"left", "right", "top", "bottom"}
        if first_resolved in _preset_names:
            # Legacy preset mode: left / right / top / bottom
            _mirror_vf = {
                "left":   "split[_ma][_mb];[_ma]crop=iw/2:ih:0:0[_mL];[_mb]crop=iw/2:ih:0:0,hflip[_mR];[_mL][_mR]hstack",
                "right":  "split[_ma][_mb];[_ma]crop=iw/2:ih:iw/2:0,hflip[_mL];[_mb]crop=iw/2:ih:iw/2:0[_mR];[_mL][_mR]hstack",
                "top":    "split[_ma][_mb];[_ma]crop=iw:ih/2:0:0[_mT];[_mb]crop=iw:ih/2:0:0,vflip[_mB];[_mT][_mB]vstack",
                "bottom": "split[_ma][_mb];[_ma]crop=iw:ih/2:0:ih/2,vflip[_mT];[_mb]crop=iw:ih/2:0:ih/2[_mB];[_mT][_mB]vstack",
            }
            return _mirror_vf.get(first_resolved, _mirror_vf["left"])
        else:
            # Parametric mode: mirror=angle[,cx,cy]
            # Folds the image along a line through (cx,cy) at `angle` degrees.
            # angle=90  → horizontal fold (default)
            # angle=0   → vertical fold
            # angle=45  → diagonal fold
            try:
                A = float(first) if first else 90.0
            except ValueError:
                A = 90.0
            cx = float(params[1]) if len(params) > 1 else 0.5
            cy = float(params[2]) if len(params) > 2 else 0.5
            # In the 2x canvas (W=2·OW, H=2·OH) the fold line's Y position is:
            #   fold_y = H/2 + (cx-0.5)*(W/2)*sin(A°) + (cy-0.5)*(H/2)*cos(A°)
            a_rad = f"{A}/180*PI"
            cx_off = cx - 0.5
            cy_off = cy - 0.5
            cx_term = (
                f"+{cx_off:.6f}*(W/2)*sin({a_rad})" if cx_off >= 0
                else f"{cx_off:.6f}*(W/2)*sin({a_rad})"
            )
            cy_term = (
                f"+{cy_off:.6f}*(H/2)*cos({a_rad})" if cy_off >= 0
                else f"{cy_off:.6f}*(H/2)*cos({a_rad})"
            )
            fold_y = f"H/2{cx_term}{cy_term}"
            return (
                f"rotate={A}/180*PI:iw*2:ih*2,"
                f"geq='if(gte(Y,{fold_y}),p(X,2*({fold_y})-Y),p(X,Y))',"
                f"format=yuv420p,"
                f"rotate={A}/-180*PI,"
                f"crop=iw/2:ih/2,"
                f"format=yuv420p"
            )
    if name == "scale1280":
        # params: width|height  (height defaults to -2 = preserve aspect ratio)
        width = params[0] if params else "1280"
        try:
            int(width)
        except (ValueError, TypeError):
            width = "1280"
        height = params[1] if len(params) > 1 else "-2"
        try:
            int(height)
        except (ValueError, TypeError):
            height = "-2"
        return f"scale={width}:{height}"
    if name == "zoom":
        # Pixel-remap zoom via geq (ports TS zoom logic):
        #   s > 1 zooms in, s < 1 zooms out.  Works via reverse-sampling:
        #   each output pixel is pulled from a position scaled around centre.
        try:
            s = float(params[0]) if params else 1.5
        except (ValueError, TypeError):
            s = 1.5
        s = max(0.01, s)
        return (
            f"format=yuv444p,rotate=0:iw*1.1:ih*1.1,"
            f"geq='p((W/2)+(X-(W/2))/{s},(H/2)+(Y-(H/2))/{s})',"
            f"scale=iw:ih,crop=iw/1.1:ih/1.1:(iw-iw/1.1)/2:(ih-ih/1.1)/2,format=yuv420p"
        )
    if name == "ripple":
        # Radial displacement using geq with hypot/sin/cos formulas.
        # params: speed|frequency|amplitude|phase  (all optional, may be expressions)
        speed     = _expr_param(params[0] if len(params) > 0 else None, 1.0)
        frequency = _expr_param(params[1] if len(params) > 1 else None, 30.0)
        amplitude = _expr_param(params[2] if len(params) > 2 else None, 10.0)
        phase     = _expr_param(params[3] if len(params) > 3 else None, 0.0)
        r_expr = "hypot(X-W*0.5,Y-H*0.5)"
        disp = f"({r_expr}+({amplitude})*sin(2*PI*({speed})*T-({phase})+(-({r_expr})/({frequency}))))"
        angle = "atan2(Y-H*0.5,X-W*0.5)"
        return (
            f"format=yuv444p,"
            f"geq='p(W*0.5+({disp})*cos({angle}),H*0.5+({disp})*sin({angle}))',"
            f"scale=iw:ih,format=yuv420p"
        )
    if name == "pan":
        # Simple pixel offset via geq with clip for boundary safety.
        # params: px|py  (pixel offset amounts, default 0, may be expressions)
        px = _expr_param(params[0] if len(params) > 0 else None, 0.0)
        py = _expr_param(params[1] if len(params) > 1 else None, 0.0)
        return (
            f"format=yuv444p,"
            f"geq='p(clip(X+({px}),0,W-1),clip(Y+({py}),0,H-1))"
            f":cb(clip(X+({px}),0,W-1),clip(Y+({py}),0,H-1))"
            f":cr(clip(X+({px}),0,W-1),clip(Y+({py}),0,H-1))',"
            f"scale=iw:ih,format=yuv420p"
        )
    if name == "tile":
        # Repetitive tiling via geq mod expressions.
        # params: tx|ty  (tile repeat counts, default 2x2, may be expressions)
        tx = _expr_param(params[0] if len(params) > 0 else None, 2.0)
        ty = _expr_param(params[1] if len(params) > 1 else None, 2.0)
        return (
            f"format=yuv444p,"
            f"geq='p(mod(X*({tx}),W),mod(Y*({ty}),H))"
            f":cb(mod(X*({tx}),W),mod(Y*({ty}),H))"
            f":cr(mod(X*({tx}),W),mod(Y*({ty}),H))',"
            f"scale=iw:ih,format=yuv420p"
        )
    if name in ("pinch&punch", "p&p", "pinchpunch"):
        strength = params[0] if len(params) > 0 else "1"
        radius = params[1] if len(params) > 1 else "0.5"
        cx = params[2] if len(params) > 2 else "0.5"
        cy = params[3] if len(params) > 3 else "0.5"
        geq_expr = (
            f"p(W*{cx}+(X-W*{cx})*max(1-({strength})*gauss(-3.3333*pow(hypot((X-W*{cx})/(W*{radius}),(Y-H*{cy})/(H*{radius})),2)),0),"
            f"H*{cy}+(Y-H*{cy})*max(1-({strength})*gauss(-3.3333*pow(hypot((X-W*{cx})/(W*{radius}),(Y-H*{cy})/(H*{radius})),2)),0))"
        )
        return f"format=yuv444p,geq='{geq_expr}',scale=iw:ih,format=yuv420p"
    if name == "vreverse":
        return "reverse"
    if name == "gm91deform":
        deform_geq = (
            "p((W/2)+((X-W/2)/lerp(1,asin(sin(-Y/H)),0.164))/1.22"
            "+((Y-H/2)*(-0.136))+((0.047*W)*pow((Y-H/2)/(H/2),2))+(-W/40)"
            ",(H/2)+((Y-H/2)/1.27)/lerp(1,sin((X/W)*PI),0.12)"
            "-(((0.014)*H)*pow((X-W/2)/(W/2),2))+((X-W/2)*(0.12))-(1.2))"
        )
        return (
            f"format=yuv444p,scale=360:360,setsar=1:1,rotate=0:iw*1.05:ih*1.05,"
            f"geq='{deform_geq}',"
            f"scale=640*1.05:360*1.05,crop=640:360:(in_w-in_h)/2+8,scale=iw:ih,setsar=1,format=yuv420p"
        )
    if name == "invertrgb":
        r_inv = params[0] if len(params) > 0 else "1"
        g_inv = params[1] if len(params) > 1 else "0"
        b_inv = params[2] if len(params) > 2 else "0"
        r_curve = "0/1 1/0" if r_inv == "1" else "0/0 1/1"
        g_curve = "0/1 1/0" if g_inv == "1" else "0/0 1/1"
        b_curve = "0/1 1/0" if b_inv == "1" else "0/0 1/1"
        return f"curves=r='{r_curve}':g='{g_curve}':b='{b_curve}'"
    if name in ("invlum", "il"):
        return f"lut3d=file={INVLUM_LUT_FILE}"
    if name == "volume":
        val = params[0] if params else "1"
        return f"volume={val}"
    if name == "vibrato":
        freq = params[0] if len(params) > 0 else "5"
        depth = params[1] if len(params) > 1 else "0.5"
        return f"vibrato=f={freq}:d={depth}"
    if name == "areverse":
        return "areverse,asetpts=PTS-STARTPTS"
    if name == "alimiter":
        level_in = params[0] if len(params) > 0 else "1"
        limit    = params[1] if len(params) > 1 else "1"
        attack   = params[2] if len(params) > 2 else "5"
        release  = params[3] if len(params) > 3 else "50"
        try:
            latency = int(float(params[4])) if len(params) > 4 else 1
        except (ValueError, TypeError):
            latency = 1
        latency = max(0, min(latency, 1))
        return f"alimiter=level_in={level_in}:limit={limit}:attack={attack}:release={release}:latency={latency}"
    if name == "channelblend":
        r = params[0] if len(params) > 0 else "r"
        g = params[1] if len(params) > 1 else "g"
        b = params[2] if len(params) > 2 else "b"
        ch_map = {"r": "1:0:0", "g": "0:1:0", "b": "0:0:1"}
        rr = ch_map.get(r, "1:0:0")
        gg = ch_map.get(g, "0:1:0")
        bb = ch_map.get(b, "0:0:1")
        return (
            f"colorchannelmixer=rr={rr.split(':')[0]}:rg={rr.split(':')[1]}:rb={rr.split(':')[2]}"
            f":gr={gg.split(':')[0]}:gg={gg.split(':')[1]}:gb={gg.split(':')[2]}"
            f":br={bb.split(':')[0]}:bg={bb.split(':')[1]}:bb={bb.split(':')[2]}"
        )
    # ── Video effects (TS port) ─────────────────────────────────────────────
    if name == "caption":
        raw_text = " ".join(params) if params else ""
        escaped = raw_text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
        return (
            f"drawtext=text='{escaped}':fontsize=h/15:fontcolor=white"
            f":borderw=3:bordercolor=black:x=(w-text_w)/2:y=20"
        )
    if name == "orb":
        return (
            "scroll=0.05,v360=e:hammer,v360=fisheye:22:7,"
            "scale=iw/2:ih/2,format=yuv444p,"
            "geq='p((W/2)+(X-(W/2))/1,(H/2)+(Y-(H/2))/1)',"
            "scale=iw:ih,format=yuv420p"
        )
    if name == "deorb":
        return (
            "scroll=-0.05,v360=hammer:e,v360=22:fisheye:7,"
            "scale=iw*2:ih*2,format=yuv444p,"
            "geq='p((W/2)+(X-(W/2))/1,(H/2)+(Y-(H/2))/1)',"
            "scale=iw:ih,format=yuv420p"
        )
    if name == "vebfisheye2":
        try:
            count = max(1, min(int(params[0]), 10)) if params else 1
        except (ValueError, TypeError):
            count = 1
        parts = []
        for _ in range(count):
            parts += ["v360=e:hammer", "scale=iw:ih", "setsar=1:1"]
        return ",".join(parts)
    if name == "vebdefisheye2":
        try:
            count = max(1, min(int(params[0]), 10)) if params else 1
        except (ValueError, TypeError):
            count = 1
        parts = []
        for _ in range(count):
            parts += ["v360=hammer:e", "scale=iw:ih", "setsar=1:1"]
        return ",".join(parts)
    if name == "vebfisheye3":
        try:
            count = max(1, min(int(params[0]), 10)) if params else 1
        except (ValueError, TypeError):
            count = 1
        parts = []
        for _ in range(count):
            parts += ["v360=fisheye:22:7", "scale=iw:ih", "setsar=1:1"]
        return ",".join(parts)
    if name == "vebdefisheye3":
        try:
            count = max(1, min(int(params[0]), 10)) if params else 1
        except (ValueError, TypeError):
            count = 1
        parts = []
        for _ in range(count):
            parts += ["v360=22:fisheye:7", "scale=iw*2:ih*2", "setsar=1:1"]
        return ",".join(parts)
    if name == "chromashift":
        return (
            "format=rgb24,"
            "geq="
            "r='p(mod((255-g(X,Y)*0.593*3)+X,W),mod((255-b(X,Y)*0.926*3)+Y,H))'"
            ":g='p(mod((255-g(X,Y)*0.593*3)+X,W),mod((255-b(X,Y)*0.926*3)+Y,H))'"
            ":b='p(mod((255-g(X,Y)*0.593*3)+X,W),mod((255-b(X,Y)*0.926*3)+Y,H))',"
            "format=yuv420p,hue=s=0"
        )
    if name == "🥸🥸":
        return "hue=h=3.14159265"
    if name == "﷽":
        return "v360=e:ball,v360=fisheye:22:7"
    if name == "𒐫":
        return "v360=ball:hammer"
    if name == "gm4":
        return "selectivecolor=blacks='0 0 0 0':whites='1 1 1 1',format=yuv420p"
    if name == "realgm4":
        return "curves=all='0/0 0.5/1 1/0'"
    # ── Audio effects (TS port — used via -af path in _apply_pipe_effects) ──
    if name == "acontrast":
        val = params[0] if params else "33"
        return f"acontrast={val}"
    if name == "adestroy":
        return "acontrast=100,acontrast=100,acontrast=100,acontrast=100,acontrast=100"
    if name == "audioequalizer":
        bands = [
            ("40",   params[0] if len(params) > 0 else "0"),
            ("150",  params[1] if len(params) > 1 else "0"),
            ("375",  params[2] if len(params) > 2 else "0"),
            ("1000", params[3] if len(params) > 3 else "0"),
            ("3000", params[4] if len(params) > 4 else "0"),
        ]
        return ",".join(f"equalizer=f={f}:width_type=q:width=1:g={g}" for f, g in bands)
    if name == "4ormulator":
        dial = params[0] if params else "712923000"
        return f"rubberband=tempo=1:formant={dial}:pitch=1"
    return None




# ── Pipe-effect inline helpers ───────────────────────────────────────────────

_VF_CODEC = ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
             "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le"]
_FF_BASE   = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y"]

def _ff_vf(inp: str, vf: str, out: str, timeout: int = 180) -> tuple[bool, str]:
    """Run a -vf filter with standard x264/pcm_s16le settings."""
    return _run_ffmpeg_raw(_FF_BASE + ["-i", inp, "-vf", vf, *_VF_CODEC, out], timeout=timeout)

def _ff_af(inp: str, af: str, out: str, timeout: int = 180) -> tuple[bool, str]:
    """Run a -af filter keeping video stream unchanged."""
    return _run_ffmpeg_raw(_FF_BASE + ["-i", inp, "-af", af, "-c:v", "copy", "-c:a", "pcm_s16le", out], timeout=timeout)


def _run_pitch_transition(
    input_path: str,
    output_path: str,
    pitch_params: list[str],
) -> tuple[bool, str]:
    """Sweep one or more voices linearly from start to end semitones.

    Pipe syntax: ``pitchtransition=-5,9;5,-9``.
    Each voice is rendered with Rubber Band R3's native pitchmap mode and
    multiple voices are mixed with amix before being muxed back to the source.
    """
    raw = " ".join(pitch_params).strip()
    if raw.lower().startswith("--pitch"):
        raw = raw.split("=", 1)[1].strip() if "=" in raw else raw[len("--pitch"):].strip()
    # Custom export parsing can normalize semicolons to spaces, so accept
    # both `-7,7;7,-7` and the equivalent `-7,7 7,-7`.
    number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
    pair_re = re.compile(rf"({number})\s*,\s*({number})")
    matches = list(pair_re.finditer(raw))
    compact_raw = re.sub(r"[\s;]+", "", raw)
    compact_matches = "".join(
        f"{match.group(1)},{match.group(2)}" for match in matches
    )
    if not matches or compact_matches != compact_raw:
        return False, f"pitchtransition: invalid voice {raw!r}; expected start,end;start,end."

    voices: list[tuple[float, float]] = []
    for match in matches:
        start, end = float(match.group(1)), float(match.group(2))
        if not math.isfinite(start) or not math.isfinite(end):
            return False, "pitchtransition: start/end must be finite numbers."
        voices.append((start, end))
    if not voices:
        return False, "pitchtransition: provide start,end[;start,end;...]."
    if len(voices) > 100:
        return False, "pitchtransition: maximum 100 voices."

    duration = _ffprobe_duration(input_path)
    if duration <= 0:
        return False, "pitchtransition: could not determine input duration."

    has_video = bool(_ffprobe(
        input_path, "-select_streams", "v:0",
        "-show_entries", "stream=codec_type", "-of", "default=nw=1:nk=1",
    ).strip())
    with tempfile.TemporaryDirectory(prefix="pitchtransition_") as tmpdir:
        transition_latency = 0.08
        voice_wavs: list[str] = []
        for index, (start, end) in enumerate(voices):
            padded = os.path.join(tmpdir, f"padded_{index}.wav")
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y", "-i", input_path, "-vn",
                "-af", f"apad=pad_dur={transition_latency:.6f},"
                       f"atrim=duration={duration + transition_latency:.6f}",
                "-c:a", "pcm_s16le", padded,
            ], timeout=300)
            if not ok:
                return False, f"pitchtransition padding failed: {err}"
            sample_rate_raw = _ffprobe(
                padded, "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate",
                "-of", "default=nw=1:nk=1",
            ).strip()
            try:
                sample_rate = int(sample_rate_raw)
            except ValueError:
                return False, "pitchtransition: could not determine audio sample rate."
            pitch_map = os.path.join(tmpdir, f"transition_{index}.map")
            map_lines = []
            for step in range(int((duration + transition_latency) / 0.01) + 1):
                t = min(step * 0.01, duration + transition_latency)
                progress = min(t, duration) / duration
                pitch = start + (end - start) * progress
                map_lines.append(f"{round(t * sample_rate)} {pitch:.10f}")
            Path(pitch_map).write_text("\n".join(map_lines) + "\n")
            wav = os.path.join(tmpdir, f"voice_{index}.wav")
            try:
                result = subprocess.run(
                    ["rubberband-r3", "-3", "--pitchmap", pitch_map,
                     "-t", "1", padded, wav],
                    capture_output=True, text=True, timeout=300,
                )
                ok = result.returncode == 0
                err = result.stderr[-2000:] if not ok else ""
            except subprocess.TimeoutExpired:
                ok, err = False, "Rubber Band R3 timed out (>300s)"
            except Exception as exc:
                ok, err = False, str(exc)
            if not ok:
                return False, f"pitchtransition voice {index + 1} failed: {err}"
            voice_wavs.append(wav)

        if len(voice_wavs) == 1:
            # Match the reference CLI: a solo transition is not passed through
            # an unnecessary mixer, preserving its original level and tone.
            mixed = voice_wavs[0]
        else:
            mixed = os.path.join(tmpdir, "mixed.wav")
            mix_cmd = ["ffmpeg", "-y"]
            for wav in voice_wavs:
                mix_cmd += ["-i", wav]
            mix_cmd += [
                "-filter_complex",
                f"amix=inputs={len(voice_wavs)}:duration=longest:"
                "dropout_transition=0:normalize=1",
                "-c:a", "pcm_s16le", mixed,
            ]
            ok, err = _run_ffmpeg_raw(mix_cmd, timeout=300)
            if not ok:
                return False, f"pitchtransition mix failed: {err}"

        if has_video:
            return _run_ffmpeg_raw([
                "ffmpeg", "-y", "-i", input_path, "-i", mixed,
                "-map", "0:v:0", "-map", "1:a:0",
                "-map_metadata", "-1", "-avoid_negative_ts", "make_zero",
                # Re-encode the video timeline so source encoder delay cannot
                # remain offset from the freshly rendered Rubber Band audio.
                "-vf", "setpts=PTS-STARTPTS",
                "-t", f"{duration + transition_latency:.6f}",
                "-c:v", "libx264", "-preset", "fast", "-tune", "zerolatency",
                "-bf", "0", "-crf", "18",
                "-pix_fmt", "yuv420p",
                *(
                    ["-c:a", "pcm_s16le"]
                    if Path(output_path).suffix.lower() == ".mov"
                    else ["-c:a", "aac", "-b:a", "192k"]
                ),
                output_path,
            ], timeout=180)
        return _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", mixed,
            "-t", f"{duration + transition_latency:.6f}",
            "-c:a", "aac", output_path,
        ], timeout=180)

def _geq(expr: str) -> str:
    """Wrap a geq pixel expression in the yuv444p → geq → yuv420p boilerplate."""
    return f"format=yuv444p,geq='{expr}',format=yuv420p"

def _dl_file(url: str, path: str, timeout: int = 30) -> tuple[bool, str]:
    """Download *url* to *path*. Returns (ok, error_message)."""
    import urllib.request as _ur, ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; IHTX-Bot)"})
        with _ur.urlopen(req, context=ctx, timeout=timeout) as r:
            with open(path, "wb") as f:
                f.write(r.read())
        return True, ""
    except Exception as e:
        return False, str(e)

def _pfloat(params: list, idx: int, default: float) -> float:
    """Safe float-from-params; used by pipe-effect parameter blocks."""
    try:
        return float(params[idx]) if idx < len(params) else default
    except (ValueError, TypeError):
        return default


def _mux_audio_onto(out: str, audio_src: str) -> tuple[bool, str]:
    """Mux audio from *audio_src* onto a video-only file at *out* (replaces in-place)."""
    with tempfile.TemporaryDirectory() as _mux_tmp:
        _muted = os.path.join(_mux_tmp, "muted.mp4")
        os.replace(out, _muted)
        return _run_ffmpeg_raw(
            _FF_BASE + ["-i", _muted, "-i", audio_src,
                        "-map", "0:v", "-map", "1:a?",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", out],
            timeout=120,
        )

# ─────────────────────────────────────────────────────────────────────────────

def _parse_gradientmap_stops(params: list[str]) -> tuple[list[tuple[int, int, int, int, float]] | None, str]:
    """Parse color-stop parameters for the gradientmap pipe effect.

    Accepts multiple forms:
      - `gradientmap=0,0,0 255,255,255`
      - `gradientmap=0:0:0:255:0.0;255:0:0:255:0.5`
      - `gradientmap=[[0,0,0,255,0],[255,0,0,255,0.5]]`
      - `gradientmap=url:https://example.com/gradient.txt`

    Each point has R,G,B [A] [pos] where A defaults to 255 and pos defaults to
    even spacing across the provided points. At least two points are required.
    """
    import json as _json
    import urllib.request as _ur
    import ssl as _ssl
    import re as _re

    def _split_points(raw: str) -> list[str]:
        raw = raw.strip()
        if not raw:
            return []
        # Try JSON array first (flat or nested).
        try:
            data = _json.loads(raw)
            if isinstance(data, list) and len(data) >= 2:
                out: list[str] = []
                for item in data:
                    if isinstance(item, list):
                        out.append(",".join(str(x) for x in item))
                    elif isinstance(item, str):
                        out.append(item)
                if out:
                    return out
        except Exception:
            pass
        # Flat list of 5-tuples or 3-tuples?
        flat = [s.strip() for s in raw.replace(";", ",").split(",") if s.strip()]
        if len(flat) >= 6 and len(flat) % 5 == 0:
            return [",".join(flat[i:i + 5]) for i in range(0, len(flat), 5)]
        if len(flat) >= 6 and len(flat) % 3 == 0:
            return [",".join(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        # Semicolon/line-based with comment support.
        points: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            hash_idx = line.find("#")
            if hash_idx != -1:
                line = line[:hash_idx].strip()
            for segment in line.split(";"):
                segment = segment.strip()
                segment = _re.sub(r"^[\[\]\s]+|[\[\]\s]+$", "", segment)
                if segment and not segment.startswith("#"):
                    points.append(segment)
        return points

    if not params:
        return None, "gradientmap needs at least 2 color stops: `gradientmap=R,G,B [R,G,B ...]`"

    first = params[0].strip()
    raw_points: list[str] = []

    if first.startswith("url:") or first.startswith("http://") or first.startswith("https://"):
        url = first[4:] if first.startswith("url:") else first
        try:
            ctx = _ssl.create_default_context()
            req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; IHTX-Bot)"})
            with _ur.urlopen(req, context=ctx, timeout=30) as r:
                text = r.read().decode("utf-8", errors="replace")
            raw_points = _split_points(text)
        except Exception as e:
            return None, f"gradientmap: failed to fetch URL points: {e}"
    elif len(params) == 1 and first.startswith("[[") and first.endswith("]]"):
        inner = first[2:-2].strip()
        raw_points = [p.strip() for p in inner.split("]")]
        raw_points = [_re.sub(r"^[\[,\s]+|[\],\s]+$", "", p) for p in raw_points if p.strip()]
    elif len(params) == 1 and first.startswith("[") and first.endswith("]"):
        bracketed = [m.group(1).strip() for m in _re.finditer(r"\[([^\]]+)\]", first)]
        if len(bracketed) >= 2:
            raw_points = bracketed
        else:
            raw_points = _split_points(first[1:-1])
    else:
        raw_points = [p.strip() for p in params]
        raw_points = [_re.sub(r"^[\[\]\s]+|[\[\]\s]+$", "", p) for p in raw_points if p.strip()]
        # If every token is a bare number and they collectively form a flat list, group them.
        if raw_points and all(_re.match(r"^-?\d+(\.\d+)?$", p) for p in raw_points):
            if len(raw_points) % 5 == 0:
                raw_points = [",".join(raw_points[i:i + 5]) for i in range(0, len(raw_points), 5)]
            elif len(raw_points) % 3 == 0:
                raw_points = [",".join(raw_points[i:i + 3]) for i in range(0, len(raw_points), 3)]

    if len(raw_points) < 2:
        preview = ", ".join(f"'{p}'" for p in raw_points[:5]) if raw_points else "(none)"
        return None, f"gradientmap needs >=2 points; got {len(raw_points)}: {preview}"

    stops: list[tuple[int, int, int, int, float]] = []
    for i, p in enumerate(raw_points):
        parts = [s.strip() for s in _re.split(r"[,;:_\s]+", p) if s.strip()]
        if len(parts) < 3:
            return None, f"gradientmap: invalid point '{p}' -- need at least R,G,B"
        try:
            nums = [float(s) for s in parts]
        except ValueError:
            return None, f"gradientmap: invalid point '{p}' -- values must be numbers"
        r, g, b = int(round(nums[0])), int(round(nums[1])), int(round(nums[2]))
        a = int(round(nums[3])) if len(nums) > 3 else 255
        pos = nums[4] if len(nums) > 4 else i / max(len(raw_points) - 1, 1)
        if any(v < 0 or v > 255 for v in (r, g, b, a)):
            return None, f"gradientmap: color values in '{p}' must be 0-255"
        if pos < 0.0 or pos > 1.0:
            return None, f"gradientmap: position in '{p}' must be 0.0-1.0"
        stops.append((r, g, b, a, pos))

    return stops, ""


def _build_gradientmap_filter(stops: list[tuple[int, int, int, int, float]]) -> str:
    r_curve = " ".join(f"{pos}/{r/255.0:.6f}" for r, g, b, a, pos in stops)
    g_curve = " ".join(f"{pos}/{g/255.0:.6f}" for r, g, b, a, pos in stops)
    b_curve = " ".join(f"{pos}/{b/255.0:.6f}" for r, g, b, a, pos in stops)
    a_curve = " ".join(f"{pos}/{a/255.0:.6f}" for r, g, b, a, pos in stops)
    return (
        f"split=3[_gm_a][_gm_b][_gm_t];"
        f"[_gm_a]format=gray,curves=r='{r_curve}':g='{g_curve}':b='{b_curve}'[_gm_aa];"
        f"[_gm_b]format=gray,curves=all='{a_curve}'[_gm_bb];"
        f"[_gm_aa][_gm_bb]alphamerge[_gm_c];"
        f"[_gm_t][_gm_c]overlay,format=yuv420p[v]"
    )



def _apply_pipe_effects(
    input_path: str,
    output_path: str,
    effects: list[tuple[str, list[str]]],
    _in_split: bool = False,
    step_timeout: int = 180,
) -> tuple[bool, str]:
    """Apply pipe effects sequentially — each effect is rendered individually
    before the next begins (no filter batching).
    """
    if not effects:
        ok, err = _run_ffmpeg_raw(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], timeout=60)
        return ok, err

    # Unknown names should not abort an otherwise valid chain. Keep parser-only
    # raw filter names here because they are intentionally not public effects.
    _PIPE_INTERNAL_EFFECTS = {"__rawvf__", "__rawaf__"}
    unknown_effects = sorted({
        name for name, _params in effects
        if name not in PIPE_EFFECT_NAMES and name not in _PIPE_INTERNAL_EFFECTS
    })
    if unknown_effects:
        print(f"[pipe] Skipping unknown effect(s): {', '.join(unknown_effects)}")
        effects = [
            (name, params)
            for name, params in effects
            if name in PIPE_EFFECT_NAMES or name in _PIPE_INTERNAL_EFFECTS
        ]
        if not effects:
            ok, err = _run_ffmpeg_raw(
                ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path],
                timeout=60,
            )
            return ok, err

    # Probe media properties for $fc/$vd/$sr/$f variable substitution.
    frame_count: int | None = None
    media_vars: dict = {}
    try:
        vinfo = _ffprobe_video_info(input_path)
        dur = vinfo.get("duration", 0.0)
        fps_str = vinfo.get("r_frame_rate", "30")
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(fps_str)
        if dur > 0 and fps > 0:
            frame_count = max(1, int(round(dur * fps)))
        media_vars['vd'] = dur
        media_vars['fps'] = fps
        media_vars['w'] = vinfo.get("width", 0)
        media_vars['h'] = vinfo.get("height", 0)
    except Exception:
        pass
    try:
        media_vars['sr'] = _ffprobe_sample_rate(input_path)
    except Exception:
        pass

    # Preprocess effect parameters: expand lerp, replace $fc/$vd/$sr/$f, collapse constants.
    # Skip for effects whose params are raw FFmpeg/shell command strings
    # (they may contain '=' that is NOT a key=value separator).
    _RAW_ARG_EFFECTS = {
        "ffmpeg", "leftsplit", "rightsplit", "gradientmap", "gmap",
        "imagemagick", "im", "geq",
        # pitchtransition owns its comma/semicolon numeric syntax. Do not
        # send its pair text through generic math/key=value preprocessing.
        "pitchtransition", "pitchtrans",
    }
    effects = [
        (
            name,
            (params if name in _RAW_ARG_EFFECTS else [_preprocess_param(p, frame_count, media_vars) for p in params]),
        )
        for name, params in effects
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        current = input_path

        for i, (name, params) in enumerate(effects):
            is_last = (i == len(effects) - 1)
            out = output_path if is_last else os.path.join(tmpdir, f"pipe_{i}.mp4")

            # ccshue — ImageMagick haldclut with hue/sat/gamma/gain/offset
            if name == "ccshue":
                ok, err = _run_ccshue(
                    current, out,
                    hue=_pfloat(params, 0, 0.0),
                    sat=_pfloat(params, 1, 1.0),
                    gamma=_pfloat(params, 2, 1.0),
                    gain=_pfloat(params, 3, 1.0),
                    offset=_pfloat(params, 4, 0.0),
                )
                if not ok:
                    return False, err
                current = out
                continue

            # ImageMagick huehsv — params: hue|sat|lightness|colorspace|betterfully
            if name == "huehsv":
                _TRUE_VALS = {"1", "true", "t", "y", "yes", "+", "on"}
                _bf_raw = params[4].strip().lower() if len(params) > 4 else ""
                ok, err = _run_huehsv(
                    current, out,
                    hue=_pfloat(params, 0, 0.5),
                    sat=_pfloat(params, 1, 1.0),
                    lightness=_pfloat(params, 2, 1.0),
                    colorspace=params[3].strip() if len(params) > 3 and params[3].strip() else "hsl",
                    betterfully=_bf_raw in _TRUE_VALS,
                )
                if not ok:
                    return False, err
                current = out
                continue

            # ImageMagick pipe effect — apply arbitrary magick args frame-by-frame (video) or directly (image)
            if name in ("imagemagick", "im"):
                ok, err = _run_imagemagick(current, out, params)
                if not ok:
                    return False, err
                current = out
                continue

            # Rubber Band R3 multipitch (add `bungee` or `--bungee` flag for bungee mode)
            # Append `:true` to params to add alimiter=0.99 after processing.
            # e.g. mp=-6|9:true  →  pitch shift then hard limit
            if name in ("multipitch", "mp", "multi"):
                _mp_use_lim = params and params[-1].strip().lower() == "true"
                _mp_params = params[:-1] if _mp_use_lim else params
                ok, err = _run_multipitch_rb3(current, out, _mp_params)
                if not ok:
                    return False, err
                if _mp_use_lim:
                    _lim_out = out + "_lim.mp4"
                    _lim_ok, _lim_err = _ff_af(out, "alimiter=limit=0.99:level=false:latency=1", _lim_out)
                    if _lim_ok:
                        os.replace(_lim_out, out)
                current = out
                continue

            if name in ("pitchtransition", "pitchtrans"):
                ok, err = _run_pitch_transition(current, out, params)
                if not ok:
                    return False, err
                current = out
                continue

            # Old multipitch fallback — rubberband CLI + FLAC (no static)
            if name in ("multipitch3", "mp3"):
                ok, err = _run_multipitch_old(current, out, params)
                if not ok:
                    return False, f"multipitch3: {err}"
                current = out
                continue

            # SoundTouch soundstretch multipitch
            if name in ("ssmp", "soundstretchmultipitch"):
                ok, err = _run_soundstretch_multipitch(current, out, params)
                if not ok:
                    return False, err
                current = out
                continue

            # sox bend multipitch
            if name in ("multipitchsox", "mpsox"):
                ok, err = _run_multipitch_sox(current, out, params)
                if not ok:
                    return False, err
                current = out
                continue

            # LUT / 3D LUT via lut3d filter
            if name == "lut":
                lut_url = params[0] if len(params) > 0 else ""
                if not lut_url:
                    return False, "lut effect requires a URL parameter."
                lut_path = os.path.join(tmpdir, f"lut_{i}.cube")
                try:
                    import urllib.request
                    import ssl
                    ssl_ctx = ssl.create_default_context()
                    req = urllib.request.Request(
                        lut_url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; IHTX-Bot)"}
                    )
                    with urllib.request.urlopen(req, context=ssl_ctx, timeout=60) as resp:
                        with open(lut_path, "wb") as f:
                            f.write(resp.read())
                except Exception as e:
                    return False, f"Failed to download LUT from {lut_url}: {e}"
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-vf", f"lut3d={lut_path},format=yuv420p",
                                *_VF_CODEC, "-movflags", "+faststart", out],
                    timeout=step_timeout,
                )
                if not ok:
                    return False, f"lut3d failed: {err}"
                current = out
                continue

            # Raw VIDEO:/AUDIO: filters — each rendered immediately
            if name == "__rawvf__":
                vf_str = params[0] if params else ""
                if vf_str:
                    ok, err = _ff_vf(current, vf_str, out)
                    if not ok:
                        return False, f"Video filter failed: {err}"
                    current = out
                continue

            if name == "__rawaf__":
                af_str = params[0] if params else ""
                if af_str:
                    ok, err = _ff_af(current, af_str, out)
                    if not ok:
                        return False, f"Audio filter failed: {err}"
                    current = out
                continue

            # trim — cut from start to end: trim=5|15 or trim=1:30|2:45
            if name == "trim":
                if len(params) < 2:
                    return False, "trim effect requires two params: trim=<start>|<end>  e.g. trim=5|15 or trim=1:30|2:45"
                try:
                    t_start = float(_parse_trim_timestamp(params[0]))
                    t_end   = float(_parse_trim_timestamp(params[1]))
                except ValueError as exc:
                    return False, f"trim: invalid timestamp — {exc}"
                if t_start < 0 or t_end < 0:
                    return False, "trim: timestamps cannot be negative."
                if t_start >= t_end:
                    return False, "trim: start must be less than end."
                t_dur = t_end - t_start
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-ss", str(t_start), "-i", current,
                                "-t", str(t_dur),
                                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                                "-c:a", "aac", "-b:a", "192k",
                                "-movflags", "+faststart", "-pix_fmt", "yuv420p", out],
                    timeout=step_timeout,
                )
                if not ok:
                    return False, f"trim failed: {err}"
                current = out
                continue

            # Speed: change playback rate (video setpts + audio atempo chain)
            if name == "speed":
                try:
                    spd = float(params[0]) if params else 1.0
                except (ValueError, IndexError):
                    spd = 1.0
                spd = max(0.01, min(spd, 100.0))
                # video: setpts = 1/speed * PTS
                vf_speed = f"setpts={1.0/spd:.6f}*PTS"
                # audio: chain atempo filters to stay in FFmpeg's 0.5-100 range
                af_speed = _build_atempo_chain(spd)
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-vf", vf_speed, "-af", af_speed,
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out],
                    timeout=step_timeout,
                )
                if not ok:
                    return False, f"speed failed: {err}"
                current = out
                continue

            # geq — raw FFmpeg geq filter expression applied directly in the vf chain
            # Syntax: geq='p(X,Y)'  or  geq=lum='expr':cb=128:cr=128
            # Quotes around the expression (e.g. geq='p(X,Y)') are passed through
            # verbatim — FFmpeg's filter option parser strips them automatically.
            # Prepends format=yuv444p so geq can read per-component values, then
            # restores yuv420p and preserves original dimensions via scale=iw:ih.
            if name == "geq":
                expr = params[0] if params else ""
                if not expr:
                    return False, "geq pipe step requires an expression (e.g. geq='p(X,Y)*0.5')."
                vf = f"format=yuv444p,geq={expr},scale=iw:ih,format=yuv420p"
                ok, err = _ff_vf(current, vf, out, timeout=step_timeout)
                if not ok:
                    return False, f"geq failed: {err}"
                current = out
                continue

            # ffmpeg(...) — raw FFmpeg args pipe step
            if name == "ffmpeg":
                raw_args = params[0] if params else ""
                if not raw_args:
                    return False, "ffmpeg() pipe step requires args inside the parentheses."
                # Substitute $fc/$vd/$d/$sr/$fr/$f/$w/$h before tokenising.
                raw_args = _preprocess_math_expr(raw_args, frame_count, media_vars)
                try:
                    user_args = shlex.split(raw_args)
                except ValueError as e:
                    return False, f"ffmpeg() pipe step — invalid args: {e}"
                # Preserve audio unless the user explicitly opted out with -map or -an
                has_map = any(a in ("-map", "-an") for a in user_args)
                # When -filter_complex is used, the user may supply -map 0:a (audio only)
                # without mapping the named video output label (e.g. [out]).  Detect that
                # case and auto-inject -map [label] so FFmpeg sees a connected output.
                auto_video_map: list[str] = []
                if has_map:
                    map_values = [
                        user_args[i + 1]
                        for i, a in enumerate(user_args)
                        if a == "-map" and i + 1 < len(user_args)
                    ]
                    has_labeled_map = any(re.match(r'^\[.+\]', v) for v in map_values)
                    if not has_labeled_map:
                        fc_idx = next(
                            (i for i, a in enumerate(user_args)
                             if a in ("-filter_complex", "-filter_complex:v")
                             and i + 1 < len(user_args)),
                            None,
                        )
                        if fc_idx is not None:
                            fc_str = user_args[fc_idx + 1]
                            label_counts: dict[str, int] = {}
                            for lbl in re.findall(r'\[([^\[\]]+)\]', fc_str):
                                label_counts[lbl] = label_counts.get(lbl, 0) + 1
                            # Labels that appear exactly once and are not stream specifiers
                            # (pure digits or containing ':') are unconnected final outputs.
                            for lbl, cnt in label_counts.items():
                                if cnt == 1 and not lbl.isdigit() and ':' not in lbl:
                                    auto_video_map += ["-map", f"[{lbl}]"]
                audio_map = [] if has_map else ["-map", "0:v:0", "-map", "0:a?", "-c:a", "copy"]
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current,
                ] + user_args + auto_video_map + audio_map + [out]
                ok, err = _run_ffmpeg_raw(cmd, timeout=step_timeout)
                if not ok:
                    return False, f"ffmpeg() pipe step failed: {err}"
                current = out
                continue

            # Named audio filters — rendered immediately
            if name in ("volume", "vibrato", "areverse", "alimiter",
                        "acontrast", "adestroy", "audioequalizer", "4ormulator"):
                af = _build_ffmpeg_pipe_vf(name, params)
                if af:
                    # pcm_s16le is lossless but requires a container that supports it.
                    # Use .mkv for intermediates; for the final output honour the extension.
                    _pcm_exts = {".mkv", ".wav", ".avi", ".mka"}
                    if name == "volume":
                        # Volume pipe output is intentionally AAC-encoded, including
                        # intermediate stages, to avoid carrying raw PCM through
                        # the rest of a volume-heavy chain.
                        audio_out = out if is_last else os.path.join(tmpdir, f"pipe_{i}.mkv")
                        audio_codec_args = ["-c:a", "aac"]
                    elif is_last:
                        audio_out = out
                        _out_ext = os.path.splitext(out)[1].lower()
                        audio_codec_args = ["-c:a", "pcm_s16le"] if _out_ext in _pcm_exts else ["-c:a", "aac", "-b:a", "192k"]
                    else:
                        audio_out = os.path.join(tmpdir, f"pipe_{i}.mkv")
                        audio_codec_args = ["-c:a", "pcm_s16le"]
                    ok, err = _run_ffmpeg_raw(
                        _FF_BASE + ["-i", current, "-af", af,
                                    "-c:v", "copy", *audio_codec_args, audio_out],
                        timeout=step_timeout,
                    )
                    if not ok:
                        return False, f"Audio filter '{name}' failed: {err}"
                    current = audio_out
                    continue

            # shake — pixel-displacement shake using geq, crops back to original dims
            if name == "shake":
                h_amt = _expr_param(params[0] if len(params) > 0 else None, 3.0)
                v_amt = _expr_param(params[1] if len(params) > 1 else None, 0.0)
                try:
                    vinfo = _ffprobe_video_info(current)
                    vid_w = int(vinfo["width"])
                    vid_h = int(vinfo["height"])
                except Exception:
                    vid_w, vid_h = 0, 0
                if vid_w <= 0 or vid_h <= 0:
                    return False, "shake: could not probe video dimensions."
                shake_vf = (
                    f"rotate=0:iw*1.1:ih*1.1,format=yuv444p,"
                    f"geq='p(X+({h_amt})*(2*mod(1000*sin(N*12.9898),1)-1),"
                    f"Y+({v_amt})*(2*mod(1000*sin(N+1000)*78.233,1)-1))',"
                    f"crop={vid_w}:{vid_h},format=yuv420p"
                )
                ok, err = _ff_vf(current, shake_vf, out, timeout=step_timeout)
                if not ok:
                    return False, f"shake failed: {err}"
                current = out
                continue

            # stretch — centre-zoom pixel remap via geq (ports the TS applyZoomGeq logic)
            # params: zoom|offset  (default 1.5|<same as zoom>)
            # zoom > 1 pulls pixels toward centre (zoom in); < 1 pushes out.
            # offset controls the vertical zoom independently of horizontal.
            if name == "stretch":
                zoom   = _pfloat(params, 0, 1.5)
                offset = _pfloat(params, 1, zoom)
                try:
                    vinfo = _ffprobe_video_info(current)
                    vid_w = int(vinfo["width"])
                    vid_h = int(vinfo["height"])
                except Exception:
                    vid_w, vid_h = 0, 0
                if vid_w <= 0 or vid_h <= 0:
                    return False, "stretch: could not probe video dimensions."
                stretch_vf = (
                    f"rotate=0:iw*1.1:ih*1.1,format=yuv444p,"
                    f"geq='p((W/2)+(X-(W/2))/{zoom},(H/2)+(Y-(H/2))/{offset})',"
                    f"scale=iw:ih,crop={vid_w}:{vid_h},format=yuv420p"
                )
                ok, err = _ff_vf(current, stretch_vf, out, timeout=step_timeout)
                if not ok:
                    return False, f"stretch failed: {err}"
                current = out
                continue

            # spherize — bulge/spherize distortion via geq (Vegas-style)
            # params: amount|radius|center_x|center_y  (default 0.8|0.5|0.5|0.5)
            if name in ("spherize", "sphere", "bulge"):
                amount = _pfloat(params, 0, 0.8)
                radius = _pfloat(params, 1, 0.5)
                cx     = _pfloat(params, 2, 0.5)
                cy     = _pfloat(params, 3, 0.5)
                try:
                    vinfo = _ffprobe_video_info(current)
                    vid_w = int(vinfo["width"])
                    vid_h = int(vinfo["height"])
                except Exception:
                    vid_w, vid_h = 0, 0
                if vid_w <= 0 or vid_h <= 0:
                    return False, "spherize: could not probe video dimensions."
                geq_expr = (
                    f"if(lte(hypot(X-W*{cx},Y-H*{cy}),min(W,H)*{radius}),"
                    f"p(W*{cx}+(X-W*{cx})*max(1-({amount})*(1-pow(hypot(X-W*{cx},Y-H*{cy})/(min(W,H)*{radius}),1)),0),"
                    f"H*{cy}+(Y-H*{cy})*max(1-({amount})*(1-pow(hypot(X-W*{cx},Y-H*{cy})/(min(W,H)*{radius}),1)),0)),"
                    f"p(X,Y))"
                )
                spherize_vf = (
                    f"format=yuv444p,"
                    f"scale={vid_h}:{vid_h},"
                    f"geq='{geq_expr}',"
                    f"scale={vid_w}:{vid_h},"
                    f"setsar=1:1,"
                    f"format=yuv420p"
                )
                ok, err = _ff_vf(current, spherize_vf, out, timeout=step_timeout)
                if not ok:
                    return False, f"spherize failed: {err}"
                current = out
                continue

            # wave — sinusoidal pixel-displacement distortion
            # Syntax:
            #   wave=largeWave            (named preset)
            #   wave=custom:hSpd|hFreq|…  (custom numeric params)
            #   wave=hSpd|hFreq|…          (legacy positional)
            if name == "wave":
                first_p = params[0].strip() if params else ""

                # ── Named preset ──────────────────────────────────────
                if first_p in WAVE_PRESETS:
                    ok, err = _ff_vf(current, WAVE_PRESETS[first_p], out)
                    if not ok:
                        return False, f"wave preset '{first_p}' failed: {err}"
                    current = out
                    continue

                # ── Custom / legacy numeric ───────────────────────────
                num_params = params
                if first_p.lower().startswith("custom:"):
                    num_params = [first_p[len("custom:"):]] + params[1:]

                def _wp(idx, default):
                    return _expr_param(num_params[idx] if idx < len(num_params) else None, default)
                h_speed   = _wp(0, 1.0)
                h_freq    = _wp(1, 1.0)
                h_amp     = _wp(2, 1.0)
                h_phase   = _wp(3, 0.0)
                v_speed   = _wp(4, 1.0)
                v_freq    = _wp(5, 1.0)
                v_amp     = _wp(6, 1.0)
                v_phase   = _wp(7, 0.0)
                sep       = len(num_params) > 8 and num_params[8].strip() in ("1", "true", "sep", "yes")
                noclip    = len(num_params) > 9 and num_params[9].strip() in ("1", "true", "noclip", "yes")

                drawbox = "drawbox=t=1," if noclip else ""
                h_wave = (
                    f"sin((T*5*({v_speed})+(({v_phase})*15))+(Y/H)*(PI*({v_freq})))*(-15*({v_amp})*(W/640))"
                )
                v_wave = (
                    f"sin((T*5*({h_speed})+(({h_phase})*15))+(X/W)*(PI*({h_freq})))*(-15*({h_amp})*(W/640))"
                )

                def _wave_cmd(inp, op, x_expr, y_expr):
                    vf = f"{drawbox}format=yuv444p,geq='p({x_expr},{y_expr})',scale=iw:ih,format=yuv420p"
                    return _ff_vf(inp, vf, op)

                if sep:
                    mid = os.path.join(tmpdir, f"wave_mid_{i}.mp4")
                    ok, err = _wave_cmd(current, mid, f"X-({h_wave})", "Y")
                    if not ok:
                        return False, f"wave (h pass) failed: {err}"
                    ok, err = _wave_cmd(mid, out, "X", f"Y-({v_wave})")
                    if not ok:
                        return False, f"wave (v pass) failed: {err}"
                else:
                    ok, err = _wave_cmd(current, out, f"X-({h_wave})", f"Y-({v_wave})")
                    if not ok:
                        return False, f"wave failed: {err}"
                current = out
                continue

            # wave2 — sinusoidal pixel-warp (buildWaveFilter port from TS)
            if name == "wave2":
                def _w2p(idx, default):
                    return _expr_param(params[idx] if idx < len(params) else None, default)
                xw     = _w2p(0, 3.0)
                yw     = _w2p(1, 3.0)
                xa     = _w2p(2, 20.0)
                ya     = _w2p(3, 20.0)
                xphase = _w2p(4, 0.0)
                yphase = _w2p(5, 0.0)
                speed  = _w2p(6, 0.0)
                ph_x = f"2*PI*Y*({xw})/2/H+2*PI*({speed})*T+({xphase})*PI/180"
                ph_y = f"2*PI*X*({yw})/2/W+2*PI*({speed})*T+({yphase})*PI/180"
                dx = f"({xa})*10*sin({ph_x})" if xa != "0" else "0"
                dy = f"({ya})*10*sin({ph_y})" if ya != "0" else "0"
                cx = f"clip(X+{dx},0,W-1)"
                cy = f"clip(Y+{dy},0,H-1)"
                vf_str = (
                    f"format=yuv444p,"
                    f"geq='p({cx},{cy}):cb({cx},{cy}):cr({cx},{cy})',"
                    f"scale=iw:ih,format=yuv420p"
                )
                ok, err = _ff_vf(current, vf_str, out, timeout=step_timeout)
                if not ok:
                    return False, f"wave2 failed: {err}"
                current = out
                continue

            # wmm3dripple (wmm) — radial ripple distortion (probes dims + frame count)
            if name in ("wmm3dripple", "wmm"):
                vinfo = _ffprobe_video_info(current)
                rW  = vinfo["width"]  or 640
                rH  = vinfo["height"] or 640
                rFc = vinfo["nb_frames"]
                if not rFc:
                    _wmm_dur, _wmm_fps = _probe_video_info(current)
                    rFc = max(1, round(_wmm_dur * _wmm_fps))
                geq_str = (
                    f"geq='p("
                    f"mod(W*0.5+(hypot(X-W*0.5,Y-H*0.5)+sin(N/{rFc}*PI)*25*sin(2*PI*N/{rFc}*2-(0)+(-(hypot(X-W*0.5,Y-H*0.5))/90)))*cos(atan2(Y-H*0.5,X-W*0.5)),W),"
                    f"mod(H*0.5+(hypot(X-W*0.5,Y-H*0.5)-sin(N/{rFc}*PI)*25*sin(2*PI*N/{rFc}*2-(0)+(-(hypot(X-W*0.5,Y-H*0.5))/90)))*sin(atan2(Y-H*0.5,X-W*0.5)),H)"
                    f")'"
                )
                vf_str = f"scale=640:640,format=yuv444p,{geq_str},scale={rW}:{rH},setsar=1,format=yuv420p"
                ok, err = _ff_vf(current, vf_str, out, timeout=300)
                if not ok:
                    return False, f"wmm3dripple failed: {err}"
                current = out
                continue

            # timecode — burnt-in SMPTE timecode overlay (probes fps for rate=)
            if name == "timecode":
                _tc_dur, _tc_fps = _probe_video_info(current)
                _tc_font = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
                _tc_rate = str(max(1, round(_tc_fps)))
                vf_str = (
                    f"drawtext=fontfile='{_tc_font}'"
                    f":timecode='00\\:00\\:00\\:00'"
                    f":rate={_tc_rate}"
                    f":text_align=R"
                    f":fontcolor=white"
                    f":fontsize=w/24"
                    f":box=1"
                    f":boxcolor=black"
                    f":boxborderw=7"
                    f":x=(w-text_w)/1.1"
                    f":y=(h-text_h)/1.12"
                )
                ok, err = _ff_vf(current, vf_str, out, timeout=step_timeout)
                if not ok:
                    return False, f"timecode failed: {err}"
                current = out
                continue

            # radar — 2×2 video analysis meter wall (waveform / histogram / vectorscope)
            if name == "radar":
                vinfo = _ffprobe_video_info(current)
                rW = vinfo["width"]
                rH = vinfo["height"]
                if not rW or not rH:
                    return False, "radar: could not probe video dimensions"
                fc = (
                    f"[0:v]format=yuv444p,split=4[ra][rb][rc][rd];"
                    f"[ra]waveform,hue=b=1.455,scale={rW}:{rH},setsar=1:1[raa];"
                    f"[rb]scale={rW}:{rH},setsar=1:1[rbn];"  # extra scale vs. TS: guarantees every stacked branch has identical dimensions
                    f"[rbn][raa]vstack[rV];"
                    f"[rc]format=rgb24,histogram=colors_mode=coloronblack,hue=b=1.25,scale={rW}:{rH},setsar=1:1[rcc];"
                    f"[rd]vectorscope=color4,hue=b=1.9,scale={rW}:{rH},setsar=1:1[rdd];"
                    f"[rcc][rdd]vstack[rV2];"
                    f"[rV][rV2]hstack,scale={rW}:{rH},setsar=1:1,format=yuv420p[vout]"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-filter_complex", fc,
                                "-map", "[vout]", "-map", "0:a?",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-pix_fmt", "yuv420p", "-c:a", "copy", out],
                    timeout=step_timeout,
                )
                if not ok:
                    return False, f"radar failed: {err}"
                current = out
                continue

            # preview1280 (p1280) — full TV-simulator montage pipeline as a pipe step
            if name in ("preview1280", "p1280"):
                ok, err = _run_preview1280(
                    current, out,
                    start_offset=_pfloat(params, 0, 1.85),
                    segment_dur=_pfloat(params, 1, 0.85),
                )
                if not ok:
                    return False, f"preview1280 pipe failed: {err}"
                current = out
                continue

            # oppositep1280 / op1280 — inverse TV-simulator montage pipeline as a pipe step
            if name in ("oppositep1280", "op1280"):
                ok, err = _run_oppositep1280(
                    current, out,
                    start_offset=_pfloat(params, 0, 1.85),
                    segment_dur=_pfloat(params, 1, 0.85),
                )
                if not ok:
                    return False, f"oppositep1280 pipe failed: {err}"
                current = out
                continue


            # Inside a split, mirror=left/right → hflip; top/bottom → vflip
            # (avoids the split-within-split crop+stack which breaks on half-width video)
            if _in_split and name == "mirror":
                _m_dir = (params[0] if params else "").lower().strip()
                _m_dir = {"l": "left", "r": "right", "t": "top", "b": "bottom"}.get(_m_dir, _m_dir)
                _m_vf = "vflip" if _m_dir in ("top", "bottom") else "hflip"
                ok, err = _ff_vf(current, _m_vf, out)
                if not ok:
                    return False, f"mirror (split-inner) failed: {err}"
                current = out
                continue

            # (=) — ball-projection hue-spin (v360=ball:e → hue → v360=e:9)
            if name == "(=)":
                _dur = media_vars.get('vd', 1.0) or 1.0
                vf = f"v360=ball:e,hue=h=450*t/{_dur:.10g},v360=e:9"
                ok, err = _ff_vf(current, vf, out, timeout=step_timeout)
                if not ok:
                    return False, f"(=) failed: {err}"
                current = out
                continue

            # (<>) — equirect → earthquake → hue-sat-spin → deproject
            if name == "(<>)":
                _dur = media_vars.get('vd', 1.0) or 1.0
                # Step 1: v360=e:9
                _s1 = os.path.join(tmpdir, f"diamond_s1_{i}.mp4")
                ok, err = _ff_vf(current, "v360=e:9", _s1, timeout=step_timeout)
                if not ok:
                    return False, f"(<>) step 1 (v360=e:9) failed: {err}"
                # Step 2: earthquake (2-pass vidstab destabilize)
                _EARTHQUAKE_SAMPLE_DIA = "https://file.garden/aTXso15ukD3mnuPI/nbfx_earthquake.mp4"
                _eq_dur, _eq_fps = _probe_video_info(_s1)
                _eq_dur = min(_eq_dur, 30.0)
                _eq_fr = str(round(_eq_fps)) if _eq_fps else "30"
                try:
                    _dim_r2 = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height",
                         "-of", "csv=s=x:p=0", _s1],
                        capture_output=True, text=True, timeout=30,
                    )
                    _dims2 = _dim_r2.stdout.strip().split("x")
                    _eq_w2, _eq_h2 = int(_dims2[0]), int(_dims2[1])
                except Exception:
                    _eq_w2, _eq_h2 = 1920, 1080
                _trf2 = os.path.join(tmpdir, f"diamond_eq_{i}.trf")
                ok, err = _run_ffmpeg_raw([
                    "ffmpeg", "-y", "-stream_loop", "-1",
                    "-i", _EARTHQUAKE_SAMPLE_DIA,
                    "-vf", (
                        f"fps={_eq_fr},scale={_eq_w2}:{_eq_h2},setsar=1:1,"
                        f"vidstabdetect=shakiness=10:accuracy=1:mincontrast=0:show=0:result={_trf2}"
                    ),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-t", str(_eq_dur), "-f", "null", "-",
                ], timeout=180)
                if not ok:
                    return False, f"(<>) earthquake pass 1 failed: {err}"
                _s2 = os.path.join(tmpdir, f"diamond_s2_{i}.mp4")
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", _s1, "-vf",
                                f"format=yuv444p,"
                                f"vidstabtransform=input={_trf2}:optalgo=avg:optzoom=0:zoom=15:invert=1,"
                                f"scale=iw:ih,format=yuv420p",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-c:a", "copy", _s2],
                    timeout=180,
                )
                if not ok:
                    return False, f"(<>) earthquake pass 2 failed: {err}"
                # Step 3: hue=s=2*t/$vd
                _s3 = os.path.join(tmpdir, f"diamond_s3_{i}.mp4")
                ok, err = _ff_vf(_s2, f"hue=s=2*t/{_dur:.10g}", _s3, timeout=step_timeout)
                if not ok:
                    return False, f"(<>) step 3 (hue=s) failed: {err}"
                # Step 4: v360=9:e
                ok, err = _ff_vf(_s3, "v360=9:e", out, timeout=step_timeout)
                if not ok:
                    return False, f"(<>) step 4 (v360=9:e) failed: {err}"
                current = out
                continue

            # Named video filters — rendered immediately
            vf = _build_ffmpeg_pipe_vf(name, params)
            if vf:
                ok, err = _ff_vf(current, vf, out, timeout=step_timeout)
                if not ok:
                    return False, f"Filter '{name}' failed: {err}"
                current = out
                continue

            # swirl — vortex/swirl distortion via geq
            if name == "swirl":
                _sp = lambda idx, d: params[idx] if idx < len(params) else d
                is1to1_val = str(_sp(5, "true")).lower() in ("1", "true", "t", "y", "yes", "+", "on")
                ok, err = _run_swirl(
                    current, out,
                    strength=_expr_param(params[0] if params else None, 180.0),
                    radius=_pfloat(params, 1, 0.5),
                    xc=_pfloat(params, 2, 0.5),
                    yc=_pfloat(params, 3, 0.5),
                    fallout=_sp(4, "quad"),
                    is1to1=is1to1_val,
                )
                if not ok:
                    return False, f"swirl failed: {err}"
                current = out
                continue

            # tvsim — TV simulator CRT displacement effect
            if name in ("tvsim", "tv"):
                ok, err = _run_tvsim(
                    current, out,
                    curvature=_pfloat(params, 0, 0.5),
                    line_sync=_pfloat(params, 1, 1.0),
                    detail_zoom=_pfloat(params, 2, 1.0),
                    vertical_sync=_pfloat(params, 3, 0.0),
                    phosphorescence=_pfloat(params, 4, 0.0),
                    interlacing=_pfloat(params, 5, 0.0),
                    aperture_grill=_pfloat(params, 6, 0.0),
                    static_noise=_pfloat(params, 7, 0.0),
                    _in_split=_in_split,
                )
                if not ok:
                    return False, f"tvsim failed: {err}"
                current = out
                continue

            # sierpinskiransomware (srw) — 2×2 Sierpinski-style grid via preset
            if name in ("sierpinskiransomware", "srw"):
                ok, err = run_ffmpeg(current, out, "sierpinskiransomware", True)
                if not ok:
                    return False, f"sierpinskiransomware failed: {err}"
                current = out
                continue

            # earthquake (nbfx) — 2-pass vidstab destabilize shake effect
            if name in ("earthquake", "nbfx"):
                _EARTHQUAKE_SAMPLE = "https://file.garden/aTXso15ukD3mnuPI/nbfx_earthquake.mp4"

                # Probe dimensions (duration/fps via existing helper)
                _eq_dur, _eq_fps = _probe_video_info(current)
                _eq_dur = min(_eq_dur, 30.0)
                _eq_fr = str(round(_eq_fps)) if _eq_fps else "30"
                try:
                    _dim_r = subprocess.run(
                        [
                            "ffprobe", "-v", "quiet", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height",
                            "-of", "csv=s=x:p=0", current,
                        ],
                        capture_output=True, text=True, timeout=30,
                    )
                    _dims = _dim_r.stdout.strip().split("x")
                    _eq_w, _eq_h = int(_dims[0]), int(_dims[1])
                except Exception:
                    _eq_w, _eq_h = 1920, 1080

                _trf_path = os.path.join(tmpdir, f"eq_{i}.trf")

                # Pass 1: vidstabdetect on the shake sample, matched to input specs
                _eq_pass1 = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1",
                    "-i", _EARTHQUAKE_SAMPLE,
                    "-vf", (
                        f"fps={_eq_fr},scale={_eq_w}:{_eq_h},setsar=1:1,"
                        f"vidstabdetect=shakiness=10:accuracy=1:mincontrast=0:show=0:result={_trf_path}"
                    ),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-t", str(_eq_dur),
                    "-f", "null", "-",
                ]
                ok, err = _run_ffmpeg_raw(_eq_pass1, timeout=180)
                if not ok:
                    return False, f"earthquake (pass 1 — vidstabdetect) failed: {err}"

                # Pass 2: apply inverted stabilization (destabilize = shake)
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-vf",
                                f"format=yuv444p,"
                                f"vidstabtransform=input={_trf_path}:optalgo=avg:optzoom=0:zoom=15:invert=1,"
                                f"scale=iw:ih,format=yuv420p",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-c:a", "copy", out],
                    timeout=180,
                )
                if not ok:
                    return False, f"earthquake (pass 2 — vidstabtransform) failed: {err}"
                current = out
                continue

            # folkvalley — music replacement + brightness boost + decorative overlay
            if name in ("folkvalley", "fv"):
                ok, err = _run_folkvalley(current, out)
                if not ok:
                    return False, f"folkvalley failed: {err}"
                current = out
                continue

            # labadjust (labadj) — negate selected Lab channels via ImageMagick HALD CLUT
            # Params: l;a;b — each 0 or 1 (1 = negate that channel)
            # Example: labadjust=1;0;1  →  negate L and b channels
            if name in ("labadjust", "labadj"):
                _lab_l = int(_pfloat(params, 0, 0.0))
                _lab_a = int(_pfloat(params, 1, 0.0))
                _lab_b = int(_pfloat(params, 2, 0.0))
                ok, err = _run_labadjust(current, out, _lab_l, _lab_a, _lab_b)
                if not ok:
                    return False, f"labadjust failed: {err}"
                current = out
                continue

            # vocoder — FFT phase vocoder (shape carrier with voice envelope)
            if name in ("vocoder", "ilvocodex", "orangevocoder", "4ormulator", "audacity", "magix"):
                # If the effect name IS a mode, use it as the default mode
                _default_mode = name if name != "vocoder" else "ilvocodex"
                # Syntax variants:
                #   vocoder=mode;bw;carrier_url
                #   vocoder=mode;carrier_url
                #   vocoder=carrier_url
                #   ilvocodex=carrier_url
                _p0 = params[0] if len(params) > 0 else ""
                _p1 = params[1] if len(params) > 1 else ""
                _p2 = params[2] if len(params) > 2 else ""
                if _p0.lower() in _VOCODER_PROFILES:
                    _vc_mode = _p0.lower()
                    try:
                        _vc_bw = int(_p1)
                        _vc_url = _p2
                    except (ValueError, TypeError):
                        _vc_bw = None
                        _vc_url = _p1
                else:
                    _vc_mode = _default_mode
                    _vc_url = _p0
                    _vc_bw = None
                if not _vc_url:
                    return False, "vocoder pipe effect requires a carrier URL: `vocoder=mode;https://…`"
                ok, err = _run_vocoder(current, out, carrier_url=_vc_url, mode=_vc_mode, bandwidth=_vc_bw)
                if not ok:
                    return False, f"vocoder failed: {err}"
                current = out
                continue

            # scgv — sidechaingate vocoder (FFmpeg firequalizer + sidechaingate)
            if name in ("scgv", "sidechaingate_vocoder"):
                # Syntax: scgv=carrier_url[;bw[;ratio[;threshold[;release[;attack[;makeup[;knee[;detection[;range[;volume[;pitch]]]]]]]]]]]]
                _scgv_url = params[0] if params else ""
                if not _scgv_url:
                    return False, "scgv pipe effect requires a carrier URL: `scgv=https://…`"
                _scgv_bw        = int(_pfloat(params, 1, 64))
                _scgv_ratio     = _pfloat(params, 2, 2.0)
                _scgv_threshold = _pfloat(params, 3, 1.0)
                _scgv_release   = _pfloat(params, 4, 50.0)
                _scgv_attack    = _pfloat(params, 5, 0.01)
                _scgv_makeup    = _pfloat(params, 6, 1.0)
                _scgv_knee      = _pfloat(params, 7, 8.0)
                _scgv_detection = params[8] if len(params) > 8 and params[8] else "peak"
                _scgv_range     = _pfloat(params, 9, 0.0)
                _scgv_volume    = _pfloat(params, 10, 1.0)
                _scgv_pitch     = _pfloat(params, 11, 0.0)
                ok, err = _run_scgv(
                    current, out, carrier_url=_scgv_url,
                    bandwidth=_scgv_bw, detection=_scgv_detection,
                    release=_scgv_release, attack=_scgv_attack,
                    ratio=_scgv_ratio, threshold=_scgv_threshold,
                    makeup=_scgv_makeup, knee=_scgv_knee,
                    pitch=_scgv_pitch, range_val=_scgv_range, volume=_scgv_volume,
                )
                if not ok:
                    return False, f"scgv failed: {err}"
                current = out
                continue

            # freakzinga g major 156 — palindrome video + dual-voice pitch shift + bass mix
            if name in ("freakzinga", "fzgm156", "freakzingagm156", "fgm156"):
                if not _ensure_multipitch_bin():
                    return False, "fzgm156: multipitch binary unavailable — download failed."

                sr_val = int(_pfloat(params, 0, 44100))

                # Probe input duration
                try:
                    _fz_dur, _ = _probe_video_info(current)
                except Exception:
                    _fz_dur = 0.0
                if _fz_dur <= 0.0:
                    return False, "fzgm156: could not probe input duration."

                trim_s = _fz_dur * 0.5

                # Step 1: generate Hald CLUT with ImageMagick
                hald_ppm = os.path.join(tmpdir, f"fzgm156_hsv_{i}.ppm")
                try:
                    subprocess.run(
                        [
                            "magick", "hald:6",
                            "-define", "modulate:colorspace=hsl",
                            "-modulate", "100,100,200",
                            hald_ppm,
                        ],
                        check=True, capture_output=True, timeout=30,
                    )
                except Exception as _hald_err:
                    return False, f"fzgm156: Hald CLUT generation failed: {_hald_err}"

                # Step 2: palindrome video — forward half + reversed half concatenated,
                # with haldclut and slight hue/blue-channel boost
                vid_step = os.path.join(tmpdir, f"fzgm156_vid_{i}.mkv")
                fz_vf = (
                    f"movie={hald_ppm},[in]haldclut,hue=b=.045,format=yuv444p[bruh];"
                    f"[bruh]split=2[invcol][invcol2];"
                    f"[invcol]trim=0:{trim_s:.6f},format=rgb24,shuffleplanes=0:2:1,format=yuv420p[first_s];"
                    f"[invcol2]reverse,trim=0:{trim_s:.6f},format=yuv420p[second_s];"
                    f"[first_s][second_s]concat=2:1:0,format=yuv420p"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-filter_complex", fz_vf,
                                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "1",
                                "-c:a", "pcm_s16le", vid_step],
                    timeout=300,
                )
                if not ok:
                    return False, f"fzgm156: palindrome video step failed: {err}"

                # Step 3: extract downsampled audio (halved sample rate)
                audio_down = os.path.join(tmpdir, f"fzgm156_h_{i}.wav")
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", vid_step, "-af", f"asetrate={sr_val // 2}", audio_down],
                    timeout=120,
                )
                if not ok:
                    return False, f"fzgm156: audio downsample step failed: {err}"

                # Step 4: dual pitch-shift passes with multipitch binary (+ rubberband fallback)
                out_pos = os.path.join(tmpdir, f"fzgm156_pos_{i}.wav")
                out_neg = os.path.join(tmpdir, f"fzgm156_neg_{i}.wav")
                ok_pos, err_pos = _run_fileaa_with_fallback(
                    audio_down, out_pos, "0.5,4.5", tmpdir, f"fzpos{i}", timeout=120)
                if not ok_pos:
                    return False, f"fzgm156: pitch shift (pos) failed: {err_pos}"
                ok_neg, err_neg = _run_fileaa_with_fallback(
                    audio_down, out_neg, "-0.5,-4.5", tmpdir, f"fzneg{i}", timeout=120)
                if not ok_neg:
                    return False, f"fzgm156: pitch shift (neg) failed: {err_neg}"

                # Step 5: mix — pos forward + neg reversed, both with bass boost, trimmed to half
                audio_mixed = os.path.join(tmpdir, f"fzgm156_mix_{i}.wav")
                fz_af = (
                    f"[0]asetrate={sr_val},bass=g=2.5,atrim=end={trim_s:.6f}[a];"
                    f"[1]asetrate={sr_val},bass=g=2.5,areverse,atrim=end={trim_s:.6f}[b];"
                    f"[a][b]concat=n=2:v=0:a=1"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", out_pos, "-i", out_neg,
                                "-filter_complex", fz_af, audio_mixed],
                    timeout=120,
                )
                if not ok:
                    return False, f"fzgm156: audio mix step failed: {err}"

                # Step 6: remux palindrome video + mixed audio
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", vid_step, "-i", audio_mixed,
                                "-map", "0:v", "-map", "1:a",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", out],
                    timeout=300,
                )
                if not ok:
                    return False, f"fzgm156: remux step failed: {err}"
                current = out
                continue

            # multipitch2 / mp2 — rubberband multi-voice pitch shift (TS "find pitch" update)
            #
            # Params (use :: to separate pitch group from preset, or plain | per pitch):
            #   mp2=1|7|8                       three voices at +1, +7, +8 st
            #   mp2=i|1|7|8                     inharmonic: each voice gets a +0.12 st companion
            #   mp2=1|7|8::G-Major_17           pitches + surround preset
            #   mp2=i|1|7|8::Evil_Rampaging_Sorcerer
            #
            # Auto-scale: if |semitone| >= 120 it is assumed to be in tenths → divide by 10.
            # Surround presets: G-Major_17 → alimiter=15, Evil_Rampaging_Sorcerer → alimiter=30.
            if name in ("multipitch2", "mp2"):
                # Guard: multipitch2 needs an audio stream to process.
                audio_streams = _ffprobe(
                    current,
                    "-select_streams", "a",
                    "-show_entries", "stream=index",
                    "-of", "default=nw=1:nk=1",
                ).strip()
                if not audio_streams:
                    return False, "multipitch2: input has no audio stream — attach or reply to a video with audio."

                all_params = list(params)

                # Inharmonic mode — 'i' as standalone first token
                inharmonic_mode = False
                if all_params and all_params[0].strip().lower() == "i":
                    inharmonic_mode = True
                    all_params = all_params[1:]

                if not all_params:
                    return False, "multipitch2: requires at least one pitch value (e.g. `mp2=1|7|8`)."

                # Collect semitones; each param may itself be pipe-separated (:: style).
                # Stop at the first non-numeric token and treat the whole param as surround_type.
                surround_type = ""
                raw_semitones: list[float] = []
                for p in all_params:
                    sub_tokens = re.split(r"[|,\s]+", p.strip())
                    hit_non_numeric = False
                    for tok in sub_tokens:
                        if not tok:
                            continue
                        try:
                            n = float(tok)
                            if abs(n) >= 120:   # tenths notation auto-scale
                                n /= 10
                            raw_semitones.append(n)
                        except ValueError:
                            surround_type = p.strip()
                            hit_non_numeric = True
                            break
                    if hit_non_numeric:
                        break

                if not raw_semitones:
                    return False, "multipitch2: no valid pitch values found."

                # Inharmonic: pair each semitone with a +0.12 st companion for chorus texture
                semitones: list[float] = []
                if inharmonic_mode:
                    for st in raw_semitones:
                        semitones.extend([st, st + 0.12])
                else:
                    semitones = raw_semitones

                n_voices = len(semitones)
                pcm      = "aformat=sample_fmts=s16:sample_rates=44100,"
                rb_args  = "rubberband=tempo=1:formant=6942000/634"

                post_mix = ""

                if n_voices == 1:
                    pitch_ratio = 2 ** (semitones[0] / 12)
                    fc_chain = (
                        f"[0:a]{pcm}"
                        f"{rb_args}:pitch={pitch_ratio:.6f},"
                        f"asetpts=PTS-STARTPTS{post_mix}[mp2aout]"
                    )
                else:
                    labels_ps  = "".join(f"[mp2ps{j}]" for j in range(n_voices))
                    split_part = f"[0:a]{pcm}asplit={n_voices}{labels_ps}"
                    chain_parts = []
                    for j, st in enumerate(semitones):
                        pitch_ratio = 2 ** (st / 12)
                        chain_parts.append(
                            f"[mp2ps{j}]"
                            f"{rb_args}:pitch={pitch_ratio:.6f},"
                            f"asetpts=PTS-STARTPTS,dynaudnorm[mp2rb{j}]"
                        )
                    rb_inputs = "".join(f"[mp2rb{j}]" for j in range(n_voices))
                    mix_part  = (
                        f"{rb_inputs}amix=inputs={n_voices}:normalize=0"
                        f"{post_mix}[mp2aout]"
                    )
                    fc_chain = ";".join([split_part] + chain_parts + [mix_part])

                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-filter_complex", fc_chain,
                                "-map", "0:v?", "-map", "[mp2aout]",
                                "-c:v", "copy", "-c:a", "pcm_s16le", out],
                    timeout=300,
                )
                if not ok:
                    return False, f"multipitch2: rubberband pitch shift failed: {err}"
                current = out
                continue

            # jitter — sinusoidal per-frame pixel displacement (camera shake)
            # Param: <strength> (default 15). Translates the TypeScript geq shake
            # into a pad→crop approach: expands the canvas by `margin` px, then
            # crops back with a sin(n*seed)-driven x/y offset each frame.
            if name == "jitter":
                strength = _expr_param(params[0] if params else None, 15.0)
                try:
                    strength_num = float(strength)
                    margin = max(4, (int(strength_num * 2) + 4) // 2 * 2)  # even, ≥4
                except (ValueError, TypeError):
                    margin = 64  # expression: use a safe default margin
                half = margin // 2
                sin_x = i + 68   # TypeScript: sinSeedX = i + 67 (with i defaulting to 1)
                sin_y = i + 671  # TypeScript: sinSeedY = i + 670
                x_expr = f"max(0,{half}+({strength})*sin(n*{sin_x}))"
                y_expr = f"max(0,{half}+({strength})*sin(n*{sin_y}))"
                vf = (
                    f"pad=iw+{margin}:ih+{margin}:{half}:{half},"
                    f"crop=iw-{margin}:ih-{margin}:'{x_expr}':'{y_expr}'"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-vf", vf, "-c:a", "copy", out],
                    timeout=300,
                )
                if not ok:
                    return False, f"jitter: ffmpeg failed: {err}"
                current = out
                continue

            # randomjitter — sinusoidal per-frame pixel displacement via geq
            # (exact formula from the TypeScript effects.ts reference).
            # Param: <strength> (default 10). Uses rotate→geq→crop with
            # dynamic pixel matrix expressions:
            #   indexX = i+67, indexY = i+670, divisor = 2.6666666666666665
            #   exprX = ((strength/(25/3))/divisor)*(2*mod(1000*sin(N*indexX),1)-1)
            #   exprY = (strength/divisor)*(2*mod(1000*sin(N+1000)*indexY,1)-1)
            if name in ("randomjitter", "rj"):
                strength = _expr_param(params[0] if params else None, 10.0)

                info = _ffprobe_video_info(current)
                w, h = info["width"], info["height"]
                if w == 0 or h == 0:
                    return False, "randomjitter: could not read video dimensions"

                idx_i = 1
                index_x = idx_i + 67
                index_y = idx_i + 670
                divisor = 2.6666666666666665

                expr_x = f"(({strength})/(25/3)/{divisor})*(2*mod(1000*sin(N*{index_x}),1)-1)"
                expr_y = f"({strength}/{divisor})*(2*mod(1000*sin(N+1000)*{index_y},1)-1)"

                vf = (
                    f"rotate=0:iw*1.1:ih*1.1,format=yuv444p,"
                    f"geq='p(X+{expr_x},Y+{expr_y})',"
                    f"crop={w}:{h},format=yuv420p"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-vf", vf, "-c:a", "copy", out],
                    timeout=300,
                )
                if not ok:
                    return False, f"randomjitter: ffmpeg failed: {err}"
                current = out
                continue

            # scroll — multi-mode scroll/pan effect
            # Mode 1: scroll=hpos=0.5 or scroll=hpos=0.5;ypos=0.3
            #   → uses FFmpeg's native scroll filter with named params
            # Mode 2: scroll=h;v (0.0–1.0 per axis continuous scroll)
            #   → uses FFmpeg's native scroll filter
            # Mode 3: scroll=x1:y1:x2:y2[:dur] (4+ numeric params → animated pan via geq)
            #   → animated pan using geq with time-dependent expressions
            if name == "scroll":
                has_named = any(p.startswith(("hpos", "vpos", "ypos")) for p in params)
                if has_named:
                    # Mode 1: Named params (hpos=, ypos=) → native scroll filter
                    scroll_parts = []
                    for p in params:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            k = k.strip().lower()
                            if k == "hpos":
                                scroll_parts.append(f"hpos={v.strip()}")
                            elif k in ("vpos", "ypos"):
                                scroll_parts.append(f"vpos={v.strip()}")
                    vf_filter = f"scroll={','.join(scroll_parts) or 'hpos=0.5'}"
                elif len(params) >= 4:
                    # Mode 3: Animated pan via geq — x1:y1:x2:y2[:dur]
                    x1 = _expr_param(params[0] if 0 < len(params) else None, 0.0)
                    y1 = _expr_param(params[1] if 1 < len(params) else None, 0.0)
                    x2 = _expr_param(params[2] if 2 < len(params) else None, 0.0)
                    y2 = _expr_param(params[3] if 3 < len(params) else None, 0.0)
                    dur = _expr_param(params[4] if 4 < len(params) else None, 0.0)
                    try:
                        t_expr = f"T/{float(dur)}" if float(dur) > 0 else "T"
                    except (ValueError, TypeError):
                        t_expr = f"T/({dur})"
                    pan_x = f"({x1})+(({x2})-({x1}))*{t_expr}"
                    pan_y = f"({y1})+(({y2})-({y1}))*{t_expr}"
                    vf_filter = (
                        f"format=yuv444p,"
                        f"geq='p(clip(X+({pan_x}),0,W-1),clip(Y+({pan_y}),0,H-1))"
                        f":cb(clip(X+({pan_x}),0,W-1),clip(Y+({pan_y}),0,H-1))"
                        f":cr(clip(X+({pan_x}),0,W-1),clip(Y+({pan_y}),0,H-1))',"
                        f"scale=iw:ih,format=yuv420p"
                    )
                else:
                    # Mode 2: Continuous scroll — h;v (0.0–1.0 per axis)
                    h_speed = _expr_param(params[0] if 0 < len(params) else None, 0.0)
                    v_speed = _expr_param(params[1] if 1 < len(params) else None, 0.0)
                    scroll_args = []
                    if h_speed not in ("0.0", "0"):
                        scroll_args.append(f"hpos={h_speed}")
                    if v_speed not in ("0.0", "0"):
                        scroll_args.append(f"vpos={v_speed}")
                    vf_filter = f"scroll={','.join(scroll_args) or 'hpos=0.5'}"
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-vf", vf_filter, "-c:a", "copy", out],
                    timeout=300,
                )
                if not ok:
                    return False, f"scroll: ffmpeg failed: {err}"
                current = out
                continue

            # leftsplit — split video, apply inner effects to left half, hflip+hstack
            # Syntax: leftsplit=<inner_effects>
            #   e.g. leftsplit=grayscale  →  left half gets grayscale, right half is mirrored
            # Process: split → crop left half → apply inner effects to left half →
            #          crop right half → hstack (with hflip for mirror effect)
            if name == "leftsplit":
                inner_str = params[0] if params else ""
                if not inner_str:
                    if current != out:
                        shutil.copyfile(current, out)
                    current = out
                    continue
                inner_effects = _parse_pipe_effects(inner_str)
                if not inner_effects:
                    if current != out:
                        shutil.copyfile(current, out)
                    current = out
                    continue
                info = _ffprobe_video_info(current)
                w, h = info["width"], info["height"]
                if w == 0 or h == 0:
                    return False, "leftsplit: could not read video dimensions"
                half_w = w // 2
                with tempfile.TemporaryDirectory() as split_tmp:
                    left_raw = os.path.join(split_tmp, "left_raw.mp4")
                    left_fx = os.path.join(split_tmp, "left_fx.mp4")
                    # Step 1: Extract left half
                    ok, err = _run_ffmpeg_raw(
                        _FF_BASE + ["-i", current, "-vf", f"crop={half_w}:{h}:0:0",
                                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                    "-pix_fmt", "yuv420p", "-c:a", "copy", left_raw],
                        timeout=300,
                    )
                    if not ok:
                        return False, f"leftsplit: crop left failed: {err}"
                    # Step 2: Apply inner effects to left half
                    ok, err = _apply_pipe_effects(left_raw, left_fx, inner_effects, _in_split=True)
                    if not ok:
                        return False, f"leftsplit: inner effects failed: {err}"
                    # Step 3: hstack left_fx (unchanged) + hflip(left_fx) to create mirror.
                    ok, err = _run_ffmpeg_raw(
                        _FF_BASE + ["-i", left_fx, "-filter_complex",
                                    "[0:v]split[l][r];[r]hflip[rflipped];[l][rflipped]hstack=inputs=2[vout]",
                                    "-map", "[vout]",
                                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                    "-pix_fmt", "yuv420p", "-an", out],
                        timeout=300,
                    )
                    if not ok:
                        return False, f"leftsplit: hstack failed: {err}"
                # Always mux audio from the original input; -map 1:a? is a no-op if no audio stream.
                # Do NOT use -shortest: it causes compounding duration truncation across iterations,
                # eventually producing a 0-duration/unreadable file. Let the video drive duration.
                ok, err = _mux_audio_onto(out, current)
                if not ok:
                    return False, f"leftsplit: audio mux failed: {err}"
                current = out
                continue

            # rightsplit — split video, apply inner effects to right half, hstack
            # Syntax: rightsplit=<inner_effects>
            #   e.g. rightsplit=grayscale  →  right half gets grayscale, left half stays
            # Process: split → crop right half → apply inner effects to right half →
            #          crop left half → hstack left+right(affected)
            if name == "rightsplit":
                inner_str = params[0] if params else ""
                if not inner_str:
                    if current != out:
                        shutil.copyfile(current, out)
                    current = out
                    continue
                inner_effects = _parse_pipe_effects(inner_str)
                if not inner_effects:
                    if current != out:
                        shutil.copyfile(current, out)
                    current = out
                    continue
                info = _ffprobe_video_info(current)
                w, h = info["width"], info["height"]
                if w == 0 or h == 0:
                    return False, "rightsplit: could not read video dimensions"
                half_w = w // 2
                with tempfile.TemporaryDirectory() as split_tmp:
                    left_raw = os.path.join(split_tmp, "left_raw.mp4")
                    right_raw = os.path.join(split_tmp, "right_raw.mp4")
                    right_fx = os.path.join(split_tmp, "right_fx.mp4")
                    # Step 1: Extract left half (no effects)
                    ok, err = _run_ffmpeg_raw(
                        _FF_BASE + ["-i", current, "-vf", f"crop={half_w}:{h}:0:0",
                                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                    "-pix_fmt", "yuv420p", "-c:a", "copy", left_raw],
                        timeout=300,
                    )
                    if not ok:
                        return False, f"rightsplit: crop left failed: {err}"
                    # Step 2: Extract right half
                    ok, err = _run_ffmpeg_raw(
                        _FF_BASE + ["-i", current, "-vf", f"crop={half_w}:{h}:{half_w}:0",
                                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                    "-pix_fmt", "yuv420p", "-c:a", "copy", right_raw],
                        timeout=300,
                    )
                    if not ok:
                        return False, f"rightsplit: crop right failed: {err}"
                    # Step 3: Apply inner effects to right half
                    ok, err = _apply_pipe_effects(right_raw, right_fx, inner_effects, _in_split=True)
                    if not ok:
                        return False, f"rightsplit: inner effects failed: {err}"
                    # Step 4: hstack left + right(affected)
                    ok, err = _run_ffmpeg_raw(
                        _FF_BASE + ["-i", left_raw, "-i", right_fx,
                                    "-filter_complex", "[0:v][1:v]hstack=inputs=2[vout]",
                                    "-map", "[vout]",
                                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                    "-pix_fmt", "yuv420p", "-an", out],
                        timeout=300,
                    )
                    if not ok:
                        return False, f"rightsplit: hstack failed: {err}"
                # Always mux audio from the original input; -map 1:a? is a no-op if no audio stream.
                # Do NOT use -shortest: it causes compounding duration truncation across iterations,
                # eventually producing a 0-duration/unreadable file. Let the video drive duration.
                ok, err = _mux_audio_onto(out, current)
                if not ok:
                    return False, f"rightsplit: audio mux failed: {err}"
                current = out
                continue

            # watermark / ring / miui / reddit — overlay a transparent PNG as a watermark
            if name in ("watermark", "ring", "miui", "reddit"):
                _WM_DEFAULTS = {
                    "ring":   "https://files.catbox.moe/r8l5ay.png",
                    "miui":   "https://files.catbox.moe/z0gkil.png",
                    "reddit": "https://files.catbox.moe/3ce714.png",
                }
                if name == "watermark":
                    wm_url = params[0] if params else ""
                    if not wm_url:
                        return False, "watermark: provide a URL as the parameter"
                else:
                    wm_url = params[0] if params else _WM_DEFAULTS[name]
                wm_path = os.path.join(tmpdir, f"wm_{i}.png")
                ok, err = _dl_file(wm_url, wm_path)
                if not ok:
                    return False, f"{name}: failed to download watermark from {wm_url}: {err}"
                fc = (
                    "[1:v]format=rgba,loop=loop=-1:size=1[_wmraw];"
                    "[_wmraw][0:v]scale2ref=w=ref_w:h=ref_h:flags=lanczos[_wm][_vid];"
                    "[_vid][_wm]overlay=0:0:eof_action=repeat[vout]"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-i", wm_path,
                                "-filter_complex", fc,
                                "-map", "[vout]", "-map", "0:a?",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-pix_fmt", "yuv420p", "-c:a", "copy", out],
                    timeout=120,
                )
                if not ok:
                    return False, f"{name}: ffmpeg overlay failed: {err}"
                current = out
                continue

            # nepeta — overlay the Nepeta cat-ear PNG (or custom URL) scaled to video dims
            if name == "nepeta":
                _NEPETA_DEFAULT_URL = "https://files.catbox.moe/i4d60t.png"
                nepeta_url = params[0] if params else _NEPETA_DEFAULT_URL
                nepeta_path = os.path.join(tmpdir, f"nepeta_{i}.png")
                ok, err = _dl_file(nepeta_url, nepeta_path)
                if not ok:
                    return False, f"nepeta: failed to download overlay from {nepeta_url}: {err}"
                # Probe video dimensions so we can scale the PNG exactly to them.
                # (scale2ref + loop crashes on this FFmpeg build; probing then hardcoding is stable.)
                _probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height",
                     "-of", "csv=p=0", current],
                    capture_output=True, text=True, timeout=15,
                )
                try:
                    _vw, _vh = map(int, _probe.stdout.strip().split(","))
                except Exception:
                    _vw, _vh = 1280, 720  # safe fallback
                fc = (
                    f"[1:v]format=rgba,scale={_vw}:{_vh}:flags=lanczos[_nimg];"
                    "[0:v][_nimg]overlay=0:0:repeatlast=1[vout]"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-i", nepeta_path,
                                "-filter_complex", fc,
                                "-map", "[vout]", "-map", "0:a?",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                                "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", out],
                    timeout=120,
                )
                if not ok:
                    return False, f"nepeta: ffmpeg overlay failed: {err}"
                current = out
                continue

            # avflip — extreme audio warp: rubberband tempo crush + afftfilt + rubberband expand
            if name == "avflip":
                _avflip_fc = (
                    "[0:a]aresample=44100,"
                    "rubberband=tempo=0.05:smoothing=712923000:window=long,"
                    "afftfilt=real='real((1216000/b),ch)':imag='imag((1216000/b),ch)'"
                    ":overlap=1:win_size=65536:win_func=bharris,"
                    "rubberband=tempo=20:smoothing=712923000:window=long,"
                    "volume=8,aformat=channel_layouts=mono[aout]"
                )
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + ["-i", current, "-filter_complex", _avflip_fc,
                                "-map", "0:v?", "-map", "[aout]",
                                "-c:v", "copy", "-c:a", "pcm_s16le", out],
                    timeout=180,
                )
                if not ok:
                    return False, f"avflip: ffmpeg failed: {err}"
                current = out
                continue

            # nparisonffmpeg / nineparisonffmpeg — iterative xstack grid filter
            # Syntax: nparisonffmpeg(NxM <ffmpeg args>)
            # e.g.   nparisonffmpeg(2x2 -vf negate)
            # Applies <ffmpeg args> once per grid cell (each step chains from the
            # previous), then stacks all `N*M` intermediate outputs in a grid.
            if name in ("nparisonffmpeg", "nineparisonffmpeg"):
                if not params:
                    return False, (
                        "nparisonffmpeg requires a grid and FFmpeg args, "
                        "e.g. nparisonffmpeg(2x2 -vf negate)."
                    )
                grid_str = params[0]
                try:
                    _gp = grid_str.lower().split("x")
                    _gridx = int(_gp[0])
                    _gridy = int(_gp[1])
                except (IndexError, ValueError):
                    return False, (
                        f"nparisonffmpeg: invalid grid '{grid_str}' — "
                        "use NxM format, e.g. 2x2."
                    )
                if _gridx < 1 or _gridy < 1 or _gridx * _gridy < 2:
                    return False, (
                        "nparisonffmpeg: grid must have at least 2 cells, "
                        "e.g. 1x2 or 2x2."
                    )
                _powers = _gridx * _gridy
                if _powers > 16:
                    return False, (
                        f"nparisonffmpeg: grid too large ({_powers} cells) — "
                        "max 16 cells (e.g. 4x4)."
                    )
                _user_args_str = " ".join(params[1:]) if len(params) > 1 else ""
                if not _user_args_str:
                    return False, (
                        "nparisonffmpeg: no FFmpeg args provided after the grid — "
                        "e.g. nparisonffmpeg(2x2 -vf negate)."
                    )
                try:
                    _user_args = shlex.split(_user_args_str)
                except ValueError as _e:
                    return False, f"nparisonffmpeg: invalid FFmpeg args: {_e}"

                # Detect whether input has an audio stream
                _np_probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=codec_type",
                     "-of", "default=noprint_wrappers=1:nokey=1", current],
                    capture_output=True, text=True, timeout=10,
                )
                _np_has_audio = "audio" in _np_probe.stdout

                # Step 0: lossless-encode the input so iterative re-encodes are clean
                _step0 = os.path.join(tmpdir, f"np_{i}_0.mp4")
                _s0_cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                           "-i", current, "-c:v", "ffv1"]
                _s0_cmd += ["-c:a", "flac"] if _np_has_audio else ["-an"]
                _s0_cmd.append(_step0)
                ok, err = _run_ffmpeg_raw(_s0_cmd, timeout=180)
                if not ok:
                    return False, f"nparisonffmpeg: lossless encode failed: {err}"

                # Steps 1..powers+1: each step applies user args to the previous .ts.
                # Collect steps 1..powers as grid inputs (powers+1 is discarded).
                _ts_files: list[str] = []
                _prev = _step0
                for _step in range(1, _powers + 2):
                    _ts_out = os.path.join(tmpdir, f"np_{i}_{_step}.ts")
                    ok, err = _run_ffmpeg_raw(
                        ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                         "-i", _prev] + _user_args +
                        ["-movflags", "+faststart", _ts_out],
                        timeout=180,
                    )
                    if not ok:
                        return False, f"nparisonffmpeg: iteration {_step} failed: {err}"
                    if _step <= _powers:
                        _ts_files.append(_ts_out)
                    _prev = _ts_out

                # Build xstack (+ optional amix) filter_complex.
                # After xstack the frame is gridx*W x gridy*H; divide both dims to
                # restore per-tile size.  -2 on height keeps even-pixel alignment.
                _inp_flags: list[str] = []
                for _tf in _ts_files:
                    _inp_flags += ["-i", _tf]
                _fv = "".join(f"[{_k}:v]" for _k in range(_powers))
                _fc_parts = [
                    f"{_fv}xstack=inputs={_powers}:grid={grid_str},"
                    f"scale=iw/{_gridx}:ih/{_gridy}:flags=lanczos[v]"
                ]
                _map_extra: list[str] = []
                _acodec_args: list[str] = []
                if _np_has_audio:
                    _fa = "".join(f"[{_k}:a]" for _k in range(_powers))
                    _fc_parts.append(f"{_fa}amix={_powers}:normalize=0[a]")
                    _map_extra = ["-map", "[a]"]
                    _acodec_args = ["-c:a", "aac", "-b:a", "192k"]
                _fc = ";".join(_fc_parts)
                # Scale timeout with grid size (120 s base + 60 s per cell)
                _np_timeout = 120 + _powers * 60
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE + _inp_flags
                    + ["-filter_complex", _fc, "-map", "[v]"] + _map_extra
                    + ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                       "-pix_fmt", "yuv420p"]
                    + _acodec_args + [out],
                    timeout=_np_timeout,
                )
                if not ok:
                    return False, f"nparisonffmpeg: xstack failed: {err}"
                current = out
                continue

            # Freakzinga test effect — complex LUT/displace/native-mirror + multi-pitch audio
            if name in ("freakzingatesteffect", "fzte", "freaktest"):
                ok, err = _run_freakzinga_test_effect(current, out, params)
                if not ok:
                    return False, err
                current = out
                continue


            # gradientmap -- map grayscale luminance to an RGBA gradient
            if name in ("gradientmap", "gmap"):
                gm_stops, gm_err = _parse_gradientmap_stops(params)
                if gm_stops is None:
                    return False, gm_err
                gm_fc = _build_gradientmap_filter(gm_stops)
                ok, err = _run_ffmpeg_raw(
                    _FF_BASE
                    + ["-i", current, "-filter_complex", gm_fc,
                       "-map", "[v]", "-map", "0:a?"]
                    + ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                       "-pix_fmt", "yuv420p"]
                    + ["-c:a", "copy", out],
                    timeout=step_timeout,
                )
                if not ok:
                    return False, f"gradientmap failed: {err}"
                current = out
                continue
            return False, f"Unknown pipe effect: {name}"

        if current != output_path:
            shutil.copyfile(current, output_path)

    return True, ""


# ---------- IHTX TagScript workflow ----------

def _raw_tail_after_n_tokens(s: str, n: int) -> str:
    """Return the raw substring of *s* after skipping the first *n* tokens.

    Tokens are whitespace-delimited but double- and single-quoted strings
    count as one token (quotes and their contents are skipped as a unit).
    The returned tail preserves the original characters verbatim — including
    any quotes — so callers can shlex.split it later without information loss.
    """
    _TOK = re.compile(r'''"[^"]*"|'[^']*'|\S+''')
    pos = 0
    for _ in range(n):
        m = _TOK.search(s, pos)
        if not m:
            return ""
        pos = m.end()
    return s[pos:].strip()


def _parse_ihtx_custom_args(args: str) -> tuple[int, str, str, str, str] | None:
    """Parse TagScript-style IHTX custom syntax.

    Syntax:
      <exports> <duration_expr> <no_trim> <export_file_format> <pipe effects>

    Example:
      10 0.483 - mp4 huehsv 0.5;negate;multipitch=1|6|7
    """
    parts = shlex.split(args)
    if len(parts) <= 4:
        return None
    try:
        exports = int(parts[0])
    except ValueError:
        return None
    if exports == 0:
        return None
    duration_expr = parts[1]
    no_trim = parts[2].lower()
    if no_trim not in {"true", "yes", "+", "false", "no", "-"}:
        return None
    export_format = parts[3].lstrip(".") or "mp4"
    # Extract pipe_effects from the ORIGINAL raw string so quoted groups
    # (e.g. "-color-matrix \"0 1 0 1 0 0 0 0 1\"") are preserved verbatim.
    # " ".join(parts[4:]) would strip the quotes and lose grouping.
    pipe_effects = _raw_tail_after_n_tokens(args, 4)
    if not pipe_effects:
        return None
    return exports, duration_expr, no_trim, export_format, pipe_effects


def _pipe_effects_label(pipe_str: str) -> str:
    """Extract just the effect names from a pipe effects string for display."""
    names = []
    for part in pipe_str.split(";"):
        part = part.strip()
        if not part:
            continue
        name = part.split("=")[0].split()[0].lower()
        if name:
            names.append(name)
    return ",".join(names) or pipe_str[:40]


def _safe_awk_duration(duration_expr: str, vidlen: float) -> tuple[bool, str]:
    """Evaluate the tag duration expression using awk like the original TagScript."""
    if not duration_expr or len(duration_expr) > 200:
        return False, "Invalid duration expression."
    if any(ch in duration_expr for ch in "\n\r\0"):
        return False, "Duration expression cannot contain newlines."
    try:
        result = subprocess.run(
            ["awk", "-v", f"vidlen={vidlen}", f"BEGIN{{ printf {duration_expr} }}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        return False, f"Duration expression failed: {e}"
    if result.returncode != 0:
        return False, result.stderr[-1000:] or "Duration expression failed."
    value = result.stdout.strip()
    try:
        dur = float(value)
    except ValueError:
        return False, f"Duration expression did not produce a number: {value!r}"
    if not math.isfinite(dur) or dur <= 0:
        return False, "Duration must be a positive finite number."
    return True, str(min(dur, MAX_DURATION))


def _concat_codec_args(output_format: str) -> list[str]:
    """Return final concat codec args for each supported output format."""
    fmt = output_format.lower().lstrip(".")
    if fmt == "mkv":
        return ["-c:v", "mpeg2video", "-q:v", "1", "-c:a", "flac",
                "-pix_fmt", "yuv420p", "-bufsize", "16M", "-threads", "0"]
    if fmt == "mxf":
        return ["-c:v", "mpeg2video", "-qscale", "1", "-qmin", "1",
                "-c:a", "pcm_s16le", "-ar", "48000",
                "-pix_fmt", "yuv420p", "-bufsize", "16M", "-threads", "0"]
    if fmt == "mov":
        return ["-c:v", "libx264", "-profile:v", "high422", "-level:v", "5",
                "-tune", "zerolatency", "-q:v", "1", "-crf", "25", "-preset", "veryfast",
                 "-c:a", "pcm_s16le",
                "-pix_fmt", "yuv420p", "-bufsize", "16M", "-threads", "0"]
    if fmt == "mp4":
        return ["-c:v", "libx264", "-profile:v", "high422", "-level:v", "5",
                "-tune", "zerolatency", "-q:v", "1", "-crf", "25", "-preset", "veryfast",
                "-c:a", "flac", "-pix_fmt", "yuv420p", "-bufsize", "16M", "-threads", "0"]
    if fmt == "avi":
        return ["-c:v", "mpeg2video", "-c:a", "flac", "-pix_fmt", "yuv420p", "-threads", "0"]
    # fallback: copy streams, let FFmpeg choose container defaults
    return ["-pix_fmt", "yuv420p", "-bufsize", "16M", "-threads", "0"]


def _run_ihtx_tagscript_workflow(
    input_path: str,
    output_path: str,
    exports: int,
    duration_expr: str,
    no_trim: str,
    export_format: str,
    pipe_effects_str: str,
    progress_callback=None,
) -> tuple[bool, str]:
    """Run custom IHTX using the TagScript-style shell workflow with pipe effects.

    Pipe effects are applied sequentially to each export.
    Output is always mp4.
    """
    if abs(exports) > MAX_REPETITIONS:
        exports = MAX_REPETITIONS if exports > 0 else -MAX_REPETITIONS

    if not re.fullmatch(r"[A-Za-z0-9]+", export_format):
        return False, "Export file format must be alphanumeric (example: mp4)."

    effects = _parse_pipe_effects(pipe_effects_str)
    if not effects:
        return False, "No pipe effects provided."

    vidlen = _ffprobe_duration(input_path)
    if vidlen <= 0:
        return False, "Could not read input duration."
    dur_ok, dur_or_error = _safe_awk_duration(duration_expr, vidlen)
    if not dur_ok:
        return False, dur_or_error
    dur = dur_or_error
    # A pitchtransition filter needs its Rubber Band tail to finish emitting
    # the final automation command. Keep that tail through every export pass.
    pitchtransition_tail = 0.08 if any(
        name in ("pitchtransition", "pitchtrans") for name, _ in effects
    ) else 0.0
    try:
        effective_duration = f"{float(dur) + pitchtransition_tail:.6f}"
    except (TypeError, ValueError):
        return False, "Export duration must be numeric when pitchtransition is used."

    _SUPPORTED_FINAL_FORMATS = {"mp4", "mkv", "mxf", "mov", "avi"}
    _fmt_lower = export_format.lower()
    extension = _fmt_lower if _fmt_lower in _SUPPORTED_FINAL_FORMATS else "mp4"
    dual_render = _fmt_lower in {"mkv", "mxf"}
    total_exports = abs(exports)

    with tempfile.TemporaryDirectory() as tmpdir:
        base = os.path.join(tmpdir, "0.mp4")
        final_output = os.path.join(tmpdir, f"icfplus.{extension}")

        warmup = os.path.join(tmpdir, "a.mp4")
        _run_ffmpeg_raw([
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", "https://file.garden/aTXso15ukD3mnuPI/resized.mp4",
            "-vf", "scale=4:4,setsar=1:1,geq=r=128:g=128:b=128",
            "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-an", "-t", "0.03", warmup,
        ], timeout=60)

        no_trim_enabled = no_trim.lower() in {"true", "yes", "+"}
        if no_trim.lower() not in {"true", "yes", "+", "false", "no", "-"}:
            return False, "no_trim must be one of: true, yes, +, false, no, -."

        base_cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y"]
        base_cmd += ["-i", input_path] if no_trim_enabled else ["-stream_loop", "-1", "-i", input_path]
        base_cmd += [
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "16M",
            "-c:a", "flac",
        ]
        if not no_trim_enabled:
            base_cmd += ["-t", effective_duration]
        base_cmd += ["-movflags", "+faststart", base]
        ok, err = _run_ffmpeg_raw(base_cmd, timeout=180)
        if not ok:
            return False, f"Base render failed: {err}"
        if progress_callback:
            progress_callback(1, total_exports + 2)

        # Per-rep timeout scaling: base 180s + 6s per rep (so 1000 reps gets ~6180s)
        _per_rep_timeout = 180 + (total_exports * 6)
        previous = base
        for i in range(1, total_exports + 2):
            current = os.path.join(tmpdir, f"{i}.{export_format}")
            ok, err = _apply_pipe_effects(previous, current, effects, step_timeout=_per_rep_timeout)
            if not ok:
                return False, f"Export {i} failed: {err}"
            if not no_trim_enabled:
                # The trim-enabled branch mirrors the original shell loop:
                # loop each processed export and cap it at the requested duration.
                trimmed = os.path.join(tmpdir, f"{i}.trimmed.{extension}")
                trim_cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-stream_loop", "-1", "-i", current,
                    "-t", effective_duration,
                    "-map", "0:v?", "-map", "0:a?",
                    # Each export pass must begin both streams at t=0.
                    # Without this, AAC priming/previous filter PTS becomes
                    # cumulative delay in the final IHTX export.
                    "-vf", "setpts=PTS-STARTPTS",
                    "-af", "asetpts=PTS-STARTPTS",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", trimmed,
                ]
                ok, err = _run_ffmpeg_raw(trim_cmd, timeout=_per_rep_timeout)
                if not ok:
                    return False, f"Export {i} trim failed: {err}"
                os.replace(trimmed, current)
            # Validate output is non-empty and has video frames before next iteration
            if not os.path.exists(current) or os.path.getsize(current) < 64:
                return False, f"Export {i} produced an empty or invalid file."
            probe = _ffprobe(
                current,
                "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames",
                "-count_frames",
                "-of", "default=nw=1:nk=1",
            ).strip()
            if probe == "0":
                return False, f"Export {i} has no video frames (likely a filter or codec issue with format '{export_format}')."
            previous = current
            if progress_callback:
                progress_callback(i + 1, total_exports + 2)

        concat_list = os.path.join(tmpdir, "concat.txt")
        sequence = range(total_exports, 0, -1) if exports < 0 else range(1, total_exports + 1)
        with open(concat_list, "w") as f:
            for i in sequence:
                f.write(f"file '{os.path.join(tmpdir, f'{i}.{export_format}')}'\n")

        concat_cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-vf", "setpts=PTS-STARTPTS",
            "-af", "asetpts=PTS-STARTPTS",
        ]
        concat_cmd.extend(_concat_codec_args(extension))
        concat_cmd.extend(["-movflags", "+faststart", final_output])
        ok, err = _run_ffmpeg_raw(concat_cmd, timeout=300)
        if not ok:
            return False, f"Concat failed: {err}"
        shutil.copyfile(final_output, output_path)
        if dual_render:
            _mp4_sidecar = output_path + ".render.mp4"
            _run_ffmpeg_raw([
                "ffmpeg", "-y", "-i", final_output,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-pix_fmt", "yuv420p",
                _mp4_sidecar,
            ], timeout=180)

    return True, ""


# ---------- Multipitch (Rubber Band R3 pitch-shift pipeline) ----------

MAX_PITCHES = 100

# Path to the Signalsmith multi-pitch binary (downloaded at startup)
_MULTIPITCH_BIN = os.path.join(os.path.dirname(__file__), "fileaa")
_MULTIPITCH_URL = "https://file.garden/aTXso15ukD3mnuPI/multipitch"


def _is_native_arch(match: str) -> bool:
    """Return True if the current machine architecture matches *match* (e.g. 'x86_64', 'aarch64')."""
    import platform
    return platform.machine().lower() == match.lower()


def _ensure_multipitch_bin() -> bool:
    """Download the multipitch binary if it isn't already present and executable.

    Returns True if the binary is ready, False on failure.
    On non-x86_64 hosts (e.g. Termux/aarch64) the x86-64 binary cannot run,
    so we skip the download and return False immediately — callers must then
    fall through to the rubberband/FFmpeg fallback path.
    """
    if os.path.isfile(_MULTIPITCH_BIN) and os.access(_MULTIPITCH_BIN, os.X_OK):
        # Even if the file exists, it might be the wrong architecture
        # (e.g. checked into the repo or downloaded on a different machine).
        if not _is_native_arch("x86_64"):
            print(f"[multipitch] skipping fileaa — host is {platform.machine()}, binary is x86-64 only")
            return False
        return True

    # Only x86_64 hosts can run the binary
    if not _is_native_arch("x86_64"):
        print(f"[multipitch] skipping fileaa download — host is {platform.machine()}, binary is x86-64 only")
        return False

    try:
        import urllib.request
        tmp = _MULTIPITCH_BIN + ".tmp"
        req = urllib.request.Request(
            _MULTIPITCH_URL,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(tmp, "wb") as f:
                f.write(resp.read())
        os.chmod(tmp, 0o755)
        os.replace(tmp, _MULTIPITCH_BIN)
        print(f"[multipitch] binary downloaded → {_MULTIPITCH_BIN}")
        return True
    except Exception as exc:
        print(f"[multipitch] binary download failed: {exc}")
        return False


def _run_fileaa_with_fallback(
    in_wav: str,
    out_wav: str,
    pitches_csv: str,
    tmpdir: str,
    prefix: str = "fb",
    timeout: int = 300,
) -> tuple[bool, str]:
    """Run the fileaa multipitch binary; fall back to rubberband+amix on failure.

    Fallback chain (each tier tried only when the previous one fails):
      1. fileaa binary   — fastest, single-process multi-voice (x86-64 only)
      2. rubberband CLI  — one pass per voice, then amix (requires rubberband pkg)
      3. FFmpeg rubberband audio filter — built into ffmpeg-full, works everywhere
    """
    # ── Tier 1: fileaa binary ───────────────────────────────────────────────
    if _ensure_multipitch_bin():
        result = subprocess.run(
            [_MULTIPITCH_BIN, in_wav, out_wav, pitches_csv],
            capture_output=True, timeout=timeout,
        )
        if result.returncode == 0:
            return True, ""
        stderr_note = result.stderr.decode(errors="replace")[-300:] if result.stderr else ""
        print(f"[multipitch] fileaa failed (exit {result.returncode}): {stderr_note}")
    else:
        print("[multipitch] fileaa unavailable — skipping to rubberband fallback")

    # ── Tier 2: rubberband CLI, one pass per semitone, then amix ───────────
    rb_bin = shutil.which("rubberband")
    if rb_bin:
        voice_wavs: list[str] = []
        all_ok = True
        for idx, st_str in enumerate(pitches_csv.split(",")):
            st_str = st_str.strip()
            if not st_str:
                continue
            try:
                st = float(st_str)
            except ValueError:
                return False, f"invalid semitone value: {st_str!r}"
            v_wav = os.path.join(tmpdir, f"{prefix}_rb_{idx}.wav")
            rb_res = subprocess.run(
                [rb_bin, f"-p{st:+.4f}", "-t1", in_wav, v_wav],
                capture_output=True, text=True, timeout=timeout,
            )
            if rb_res.returncode != 0:
                print(f"[multipitch] rubberband CLI failed (voice {idx}, {st:+.2f}st): {rb_res.stderr[-300:]}")
                all_ok = False
                break
            voice_wavs.append(v_wav)

        if all_ok and voice_wavs:
            mix_cmd = ["ffmpeg", "-y"]
            for vw in voice_wavs:
                mix_cmd += ["-i", vw]
            mix_cmd += [
                "-filter_complex", f"amix=inputs={len(voice_wavs)}:normalize=0",
                "-c:a", "pcm_s16le",
                out_wav,
            ]
            ok, err = _run_ffmpeg_raw(mix_cmd, timeout=timeout)
            if ok:
                return True, ""
            print(f"[multipitch] rubberband CLI amix failed: {err[-300:]}")
        elif not all_ok:
            print("[multipitch] rubberband CLI had failures — trying FFmpeg filter fallback")
        else:
            print("[multipitch] rubberband CLI produced no voices — trying FFmpeg filter fallback")

    # ── Tier 3: FFmpeg rubberband audio filter (works on any arch) ──────────
    #   Use one pass per voice with rubberband=pitch filter, then amix.
    #   This requires ffmpeg compiled with --enable-librubberband (e.g. Termux ffmpeg-full).
    voice_wavs_ff: list[str] = []
    for idx, st_str in enumerate(pitches_csv.split(",")):
        st_str = st_str.strip()
        if not st_str:
            continue
        try:
            st = float(st_str)
        except ValueError:
            return False, f"invalid semitone value: {st_str!r}"
        # Convert semitones to pitch ratio: 2^(N/12)
        pitch_ratio = 2.0 ** (st / 12.0)
        v_wav = os.path.join(tmpdir, f"{prefix}_ffrb_{idx}.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", in_wav,
            "-af", f"rubberband=pitch={pitch_ratio:.6f}",
            "-c:a", "pcm_s16le",
            v_wav,
        ], timeout=timeout)
        if not ok:
            return False, f"FFmpeg rubberband filter failed (voice {idx}, {st:+.2f}st): {err[-400:]}"
        voice_wavs_ff.append(v_wav)

    if not voice_wavs_ff:
        return False, "no valid pitch voices produced"

    mix_cmd = ["ffmpeg", "-y"]
    for vw in voice_wavs_ff:
        mix_cmd += ["-i", vw]
    mix_cmd += [
        "-filter_complex", f"amix=inputs={len(voice_wavs_ff)}:normalize=0",
        "-c:a", "pcm_s16le",
        out_wav,
    ]
    ok, err = _run_ffmpeg_raw(mix_cmd, timeout=timeout)
    return ok, ("" if ok else f"amix failed: {err}")


def _run_multipitch_bungee(
    input_path: str,
    output_path: str,
    pitch_values: list[str],
) -> tuple[bool, str]:
    """Bungee mode for the multipitch pipe effect.

    Mirrors the standalone th/multipitch_bungee (mpb) pipeline:
      1. Transcode input to FFV1/PCM_S16LE temp video.
      2. Extract audio with asetrate=44100/2.
      3. Run multipitch binary with <pitches> --bungee --no-normalize.
      4. Remux processed audio back over the original video stream.

    Params are semicolon/whitespace-separated pitch values (same as normal multipitch).
    """
    flattened: list[str] = []
    for pv in pitch_values:
        flattened.extend(
            v.strip()
            for v in re.split(r"[;|,\s]+", pv)
            if v.strip() and v.strip().lower() not in ("bungee", "--bungee")
        )

    if not flattened:
        return False, "❌ No pitch values specified for bungee mode."

    if len(flattened) > MAX_PITCHES:
        return False, f"❌ Too many pitch values (maximum: {MAX_PITCHES})."

    try:
        semitones = [float(v) for v in flattened]
    except ValueError as exc:
        return False, f"❌ Invalid pitch value in bungee mode: {exc}"

    if not _ensure_multipitch_bin():
        return False, "❌ Multipitch binary unavailable — download failed."

    has_video = bool(_ffprobe(
        input_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
    ).strip())

    pitch_arg = ",".join(
        str(int(s)) if s == int(s) else str(s)
        for s in semitones
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. FFV1/PCM temp video
        temp_video = os.path.join(tmpdir, "bungee_temp.mp4")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", input_path,
            "-f", "mp4", "-preset", "ultrafast",
            "-c:v", "ffv1", "-c:a", "pcm_s16le",
            temp_video,
        ], timeout=120)
        if not ok:
            return False, f"bungee: transcode failed: {err}"

        # 2. Probe actual audio sample rate from temp video (fall back to 44100)
        sr_raw = _ffprobe(
            temp_video,
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate",
            "-of", "default=nw=1:nk=1",
        ).strip()
        try:
            sr = int(sr_raw)
        except (ValueError, TypeError):
            sr = 44100

        # 3. Extract audio with octave-down sample rate (sr/2)
        half_wav = os.path.join(tmpdir, "bungee_half.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", temp_video,
            "-af", f"asetrate={sr // 2}",
            "-c:a", "pcm_s16le",
            half_wav,
        ], timeout=120)
        if not ok:
            return False, f"bungee: audio extraction failed: {err}"

        # 4. Run bungee pitch processor
        out_wav = os.path.join(tmpdir, "bungee_out.wav")
        res = subprocess.run(
            [_MULTIPITCH_BIN, half_wav, out_wav, pitch_arg, "--bungee", "--no-normalize"],
            capture_output=True, timeout=300,
        )
        if res.returncode != 0:
            stderr_note = res.stderr.decode(errors="replace")[-300:] if res.stderr else ""
            return False, f"bungee: multipitch binary failed: {stderr_note}"

        # 5. Remux pitched audio with original video (or audio-only)
        if has_video:
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y", "-i", temp_video, "-i", out_wav,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output_path,
            ], timeout=180)
        else:
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-i", out_wav,
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ], timeout=180)
        if not ok:
            return False, f"bungee: remux failed: {err}"

    return True, ""


def _run_multipitch_rb3(
    input_path: str,
    output_path: str,
    pitch_values: list[str],
) -> tuple[bool, str]:
    """Multi-voice pitch shift using rubberband R3 CLI per voice + amix.

    Primary pipeline (Tier 1): rubberband -3 -p <st> once per voice, then
      FFmpeg amix=inputs=N:normalize=0 → FLAC/MKV output.

    Fallback (Tier 2): single FFmpeg filter_complex pass:
      [0:a]asplit=N[s0]..[sN-1];
      [s0]rubberband=pitch=R0[v0]; ...
      [v0]..[vN-1]amix=inputs=N:normalize=0[outa]

    Accepts ; | , or whitespace as pitch separators.
    Add the `bungee` or `--bungee` flag anywhere in the params to switch to
    bungee mode (asetrate=22050 + binary --bungee --no-normalize).
    """
    # ── 1. Detect bungee mode ───────────────────────────────────────────────
    use_bungee = any(
        p.strip().lower() in ("bungee", "--bungee")
        for p in pitch_values
    )
    if use_bungee:
        return _run_multipitch_bungee(input_path, output_path, pitch_values)

    # ── 2. Flatten & parse pitch values ──────────────────────────────────────
    flattened: list[str] = []
    for pv in pitch_values:
        flattened.extend(
            v.strip()
            for v in re.split(r"[;|,\s]+", pv)
            if v.strip()
        )

    if not flattened:
        return False, "❌ No pitch values specified."

    if len(flattened) > MAX_PITCHES:
        return False, f"❌ Too many pitch values (maximum: {MAX_PITCHES})."

    semitones: list[float] = []
    seen: set[float] = set()
    for raw in flattened:
        try:
            val = float(raw)
        except ValueError:
            return False, f"❌ Invalid pitch value: {raw!r} — must be a number in semitones."
        if not math.isfinite(val):
            return False, f"❌ Invalid pitch value: {raw!r} — must be finite."
        if val not in seen:
            seen.add(val)
            semitones.append(val)

    n = len(semitones)

    # ── 3. Probe input ───────────────────────────────────────────────────────
    has_video = bool(_ffprobe(
        input_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
    ).strip())

    actual_dur = _ffprobe_duration(input_path)
    cap = str(int(min(actual_dur, MAX_DURATION)) + 1) if actual_dur > 0 else str(MAX_DURATION)
    dur_flag = str(round(actual_dur, 6)) if actual_dur > 0 else cap

    # ── 4. Tier 1: rubberband R3 CLI per voice → amix → MKV/FLAC ─────────────
    rb_bin = shutil.which("rubberband")
    if rb_bin:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Extract stereo PCM WAV for rubberband
            base_wav = os.path.join(tmpdir, "base.wav")
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-t", cap, "-i", input_path,
                "-vn", "-ar", "44100", "-ac", "2",
                "-c:a", "pcm_s16le", "-t", cap,
                base_wav,
            ], timeout=120)
            if not ok:
                print(f"[multipitch] WAV extraction failed: {err[-200:]} — trying filter_complex fallback")
            else:
                # rubberband -3 -p <st> -t1 per voice
                voice_wavs: list[str] = []
                rb_ok = True
                for idx, st in enumerate(semitones):
                    v_wav = os.path.join(tmpdir, f"rb3_v{idx}.wav")
                    rb_res = subprocess.run(
                        [rb_bin, "-3", f"-p{st:+.4f}", "-t1", base_wav, v_wav],
                        capture_output=True, text=True, timeout=300,
                    )
                    if rb_res.returncode != 0:
                        print(
                            f"[multipitch] rubberband R3 failed (voice {idx}, {st:+.2f}st): "
                            f"{rb_res.stderr[-200:]} — trying filter_complex fallback"
                        )
                        rb_ok = False
                        break
                    voice_wavs.append(v_wav)

                if rb_ok and voice_wavs:
                    # Amix voices → WAV
                    out_wav = os.path.join(tmpdir, "pitched.wav")
                    mix_cmd = ["ffmpeg", "-y"]
                    for vw in voice_wavs:
                        mix_cmd += ["-i", vw]
                    mix_cmd += [
                        "-filter_complex", f"amix=inputs={len(voice_wavs)}:normalize=0",
                        "-c:a", "pcm_s16le",
                        out_wav,
                    ]
                    ok, err = _run_ffmpeg_raw(mix_cmd, timeout=300)
                    if not ok:
                        print(f"[multipitch] amix failed: {err[-200:]} — trying filter_complex fallback")
                    else:
                        # Remux to MKV/FLAC
                        mkv_out = os.path.join(tmpdir, "mp_t1.mkv")
                        if has_video:
                            ok, err = _run_ffmpeg_raw([
                                "ffmpeg", "-y",
                                "-t", cap, "-i", input_path,
                                "-i", out_wav,
                                "-map", "0:v", "-map", "1:a",
                                "-c:v", "copy", "-c:a", "flac",
                                "-t", dur_flag, mkv_out,
                            ], timeout=300)
                        else:
                            ok, err = _run_ffmpeg_raw([
                                "ffmpeg", "-y",
                                "-i", out_wav,
                                "-c:a", "flac",
                                mkv_out,
                            ], timeout=180)
                        if ok:
                            os.replace(mkv_out, output_path)
                            return True, ""
                        print(f"[multipitch] remux failed: {err[-200:]} — trying filter_complex fallback")
    else:
        print("[multipitch] rubberband CLI not found — trying filter_complex fallback")

    # ── 5. Tier 2: single FFmpeg filter_complex pass ──────────────────────────
    #   asplit=N → rubberband:pitch per voice → amix=inputs=N:normalize=0
    if n == 1:
        pitch_ratio = 2.0 ** (semitones[0] / 12.0)
        fc = (
            f"[0:a]rubberband=pitch={pitch_ratio:.6f},"
            f"asetpts=PTS-STARTPTS[outa]"
        )
    else:
        split_labels = "".join(f"[mp_s{j}]" for j in range(n))
        split_part   = f"[0:a]asplit={n}{split_labels}"
        voice_parts  = []
        for j, st in enumerate(semitones):
            pr = 2.0 ** (st / 12.0)
            voice_parts.append(
                f"[mp_s{j}]rubberband=pitch={pr:.6f},asetpts=PTS-STARTPTS[mp_v{j}]"
            )
        mix_inputs = "".join(f"[mp_v{j}]" for j in range(n))
        mix_part   = f"{mix_inputs}amix=inputs={n}:normalize=0[outa]"
        fc = ";".join([split_part] + voice_parts + [mix_part])

    with tempfile.TemporaryDirectory() as _t2_tmp:
        mkv_out2 = os.path.join(_t2_tmp, "mp_t2.mkv")
        if has_video:
            cmd = (
                _FF_BASE
                + ["-t", cap, "-i", input_path]
                + ["-filter_complex", fc]
                + ["-map", "0:v", "-map", "[outa]"]
                + ["-c:v", "copy", "-c:a", "flac"]
                + ["-t", dur_flag, mkv_out2]
            )
        else:
            cmd = (
                _FF_BASE
                + ["-i", input_path]
                + ["-filter_complex", fc]
                + ["-map", "[outa]"]
                + ["-c:a", "flac", mkv_out2]
            )
        ok, err = _run_ffmpeg_raw(cmd, timeout=300)
        if ok:
            os.replace(mkv_out2, output_path)
            return True, ""

    return False, f"❌ Multipitch failed (all tiers exhausted): {err[-300:]}"


# Keep the old name as an alias so legacy pipe-effect calls still resolve
_run_multipitch = _run_multipitch_rb3


def _run_multipitch_old(
    input_path: str,
    output_path: str,
    pitch_values: list[str],
    audio_codec: str = "flac",
) -> tuple[bool, str]:
    """Old-style multi-voice pitch shift using the Rubber Band CLI directly.

    This skips the fileaa binary tier and uses rubberband -p<st> per voice,
    then amixes and remuxes. Default audio codec is FLAC to avoid static and
    keep intermediates lossless for further pipe steps.
    """
    # ── Flatten & parse pitch values ────────────────────────────────────────
    flattened: list[str] = []
    for pv in pitch_values:
        flattened.extend(
            v.strip()
            for v in re.split(r"[;|,\s]+", pv)
            if v.strip()
        )

    if not flattened:
        return False, "No pitch values specified."

    if len(flattened) > MAX_PITCHES:
        return False, f"Too many pitch values (maximum: {MAX_PITCHES})."

    semitones: list[float] = []
    seen: set[float] = set()
    for raw in flattened:
        try:
            val = float(raw)
        except ValueError:
            return False, f"Invalid pitch value: {raw!r} — must be a number in semitones."
        if not math.isfinite(val):
            return False, f"Invalid pitch value: {raw!r} — must be finite."
        if val not in seen:
            seen.add(val)
            semitones.append(val)

    # ── Ensure rubberband CLI is available ──────────────────────────────────
    rb_bin = shutil.which("rubberband")
    if not rb_bin:
        return False, "rubberband CLI not found — cannot run old multipitch fallback."

    # ── Probe input ─────────────────────────────────────────────────────────
    has_video = bool(_ffprobe(
        input_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
    ).strip())

    actual_dur = _ffprobe_duration(input_path)
    cap = str(int(min(actual_dur, MAX_DURATION)) + 1) if actual_dur > 0 else str(MAX_DURATION)

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── Extract 16-bit PCM WAV for rubberband ───────────────────────────
        base_wav = os.path.join(tmpdir, "base.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y",
            "-t", cap,
            "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2",
            "-c:a", "pcm_s16le",
            "-t", cap,
            base_wav,
        ], timeout=120)
        if not ok:
            return False, f"Audio extraction failed: {err}"

        # ── Pitch each voice with rubberband CLI ────────────────────────────
        voice_wavs: list[str] = []
        for idx, st in enumerate(semitones):
            v_wav = os.path.join(tmpdir, f"oldmp_rb_{idx}.wav")
            rb_res = subprocess.run(
                [rb_bin, f"-p{st:+.4f}", "-t1", base_wav, v_wav],
                capture_output=True, text=True, timeout=300,
            )
            if rb_res.returncode != 0:
                return False, f"rubberband CLI failed (voice {idx}, {st:+.2f}st): {rb_res.stderr[-300:]}"
            voice_wavs.append(v_wav)

        # ── Mix voices ───────────────────────────────────────────────────────
        mix_wav = os.path.join(tmpdir, "mix.wav")
        mix_cmd = ["ffmpeg", "-y"]
        for vw in voice_wavs:
            mix_cmd += ["-i", vw]
        mix_cmd += [
            "-filter_complex", f"amix=inputs={len(voice_wavs)}:normalize=0",
            "-c:a", "pcm_s16le",
            mix_wav,
        ]
        ok, err = _run_ffmpeg_raw(mix_cmd, timeout=300)
        if not ok:
            return False, f"amix failed: {err}"

        # ── Remux with original video (or audio-only) using requested codec ──
        if has_video:
            dur_flag = str(round(actual_dur, 6)) if actual_dur > 0 else cap
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-t", cap, "-i", input_path,
                "-i", mix_wav,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", audio_codec,
                "-t", dur_flag,
                output_path,
            ], timeout=300)
        else:
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-i", mix_wav,
                "-c:a", audio_codec,
                output_path,
            ], timeout=180)

        if not ok:
            return False, f"Remux failed: {err}"

    return True, ""


def _run_soundstretch_multipitch(
    input_path: str,
    output_path: str,
    pitch_values: list[str],
) -> tuple[bool, str]:
    """Multi-voice pitch shift using SoundTouch soundstretch + FFmpeg amix.

    Pipeline:
      1. Validate & deduplicate semitone values.
      2. Extract 16-bit PCM WAV audio from the input.
      3. Run `soundstretch in.wav voice_N.wav -pitch=N` for each voice.
      4. Mix all voices via FFmpeg amix (normalize=0).
      5. Remux over the original video stream (or emit audio-only).
    """
    # ── 1. Flatten & parse pitch values ──────────────────────────────────────
    flattened: list[str] = []
    for pv in pitch_values:
        flattened.extend(v.strip() for v in re.split(r"[;|,\s]+", pv) if v.strip())

    if not flattened:
        return False, "❌ No pitch values specified."
    if len(flattened) > MAX_PITCHES:
        return False, f"❌ Too many pitch values (maximum: {MAX_PITCHES})."

    semitones: list[float] = []
    seen: set[float] = set()
    for raw in flattened:
        try:
            val = float(raw)
            if not math.isfinite(val):
                raise ValueError
        except ValueError:
            return False, f"❌ Invalid pitch value: {raw!r} — must be a finite number in semitones."
        if val not in seen:
            seen.add(val)
            semitones.append(val)

    # ── 2. Locate soundstretch binary ─────────────────────────────────────────
    ss_bin = shutil.which("soundstretch")
    if not ss_bin:
        return False, "❌ soundstretch binary not found (soundtouch package required)."

    # ── 3. Probe input ────────────────────────────────────────────────────────
    has_video = bool(_ffprobe(
        input_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
    ).strip())

    actual_dur = _ffprobe_duration(input_path)
    cap = str(int(min(actual_dur, MAX_DURATION)) + 1) if actual_dur > 0 else str(MAX_DURATION)

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── 4. Extract 16-bit PCM WAV ─────────────────────────────────────────
        base_wav = os.path.join(tmpdir, "base.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y",
            "-t", cap, "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2",
            "-c:a", "pcm_s16le",
            "-t", cap,
            base_wav,
        ], timeout=120)
        if not ok:
            return False, f"Audio extraction failed: {err}"

        # ── 5. soundstretch per voice ─────────────────────────────────────────
        voice_wavs: list[str] = []
        for idx, st in enumerate(semitones):
            v_wav = os.path.join(tmpdir, f"voice_{idx}.wav")
            result = subprocess.run(
                [ss_bin, base_wav, v_wav, f"-pitch={st:.4f}"],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                return False, (
                    f"❌ soundstretch failed (voice {idx}, pitch {st:+.1f} st): "
                    f"{(result.stderr or result.stdout)[-600:]}"
                )
            voice_wavs.append(v_wav)

        # ── 6. Mix voices ─────────────────────────────────────────────────────
        if len(voice_wavs) == 1:
            out_wav = voice_wavs[0]
        else:
            out_wav = os.path.join(tmpdir, "mixed.wav")
            mix_cmd = ["ffmpeg", "-y"]
            for vw in voice_wavs:
                mix_cmd += ["-i", vw]
            mix_cmd += [
                "-filter_complex", f"amix=inputs={len(voice_wavs)}:normalize=0",
                "-c:a", "pcm_s16le",
                out_wav,
            ]
            ok_mix, err_mix = _run_ffmpeg_raw(mix_cmd, timeout=180)
            if not ok_mix:
                return False, f"❌ amix failed: {err_mix}"

        # ── 7. Remux with video (or audio-only) ───────────────────────────────
        dur_flag = str(round(actual_dur, 6)) if actual_dur > 0 else cap
        if has_video:
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-t", cap, "-i", input_path,
                "-i", out_wav,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "pcm_s16le",
                "-t", dur_flag,
                output_path,
            ], timeout=300)
        else:
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-i", out_wav,
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ], timeout=180)

        if not ok:
            return False, f"Remux failed: {err}"

    return True, ""


def _run_multipitch_sox(
    input_path: str,
    output_path: str,
    pitch_values: list[str],
) -> tuple[bool, str]:
    """Multi-voice pitch bend using sox ``bend`` + FFmpeg highpass/amix.

    Ports the TypeScript ``renderPitchBentVideo()`` pipeline:

      1. Re-encode source audio to pcm_s16le (rawVideo).
      2. Extract audio track as WAV (rawAudio).
      3a. Single pitch: sox bend once → ffmpeg highpass=5 + remux.
      3b. Multi pitch: sox bend per voice → ffmpeg amix=normalize=0,highpass=17.5 + remux.

    Params: semicolon / pipe / comma-separated semitone values (e.g. ``-7|7``).
    """
    # ── 1. Flatten & parse pitch values ──────────────────────────────────────
    flattened: list[str] = []
    for pv in pitch_values:
        flattened.extend(v.strip() for v in re.split(r"[;|,\s]+", pv) if v.strip())

    if not flattened:
        return False, "❌ No pitch values specified (e.g. `mpsox=-7|7`)."
    if len(flattened) > MAX_PITCHES:
        return False, f"❌ Too many pitch values (maximum: {MAX_PITCHES})."

    semitones: list[float] = []
    seen: set[float] = set()
    for raw in flattened:
        try:
            val = float(raw)
            if not math.isfinite(val):
                raise ValueError
        except ValueError:
            return False, f"❌ Invalid pitch value: {raw!r} — must be a finite number in semitones."
        if val not in seen:
            seen.add(val)
            semitones.append(val)

    # ── 2. Check sox ──────────────────────────────────────────────────────────
    sox_bin = shutil.which("sox")
    if not sox_bin:
        return False, "❌ sox binary not found (sox package required)."

    # ── 3. Probe input ────────────────────────────────────────────────────────
    has_video = bool(_ffprobe(
        input_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
    ).strip())

    actual_dur = _ffprobe_duration(input_path)
    cap = str(int(min(actual_dur, MAX_DURATION)) + 1) if actual_dur > 0 else str(MAX_DURATION)

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_video = os.path.join(tmpdir, "a_raw.mp4")
        raw_audio = os.path.join(tmpdir, "b_raw.wav")

        # ── 4. Re-encode audio to pcm_s16le ──────────────────────────────────
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y",
            "-t", cap, "-i", input_path,
            "-c:v", "copy", "-c:a", "pcm_s16le",
            raw_video,
        ], timeout=120)
        if not ok:
            return False, f"Re-encode failed: {err}"

        # ── 5. Extract audio track ────────────────────────────────────────────
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", raw_video, "-vn", raw_audio,
        ], timeout=60)
        if not ok:
            return False, f"Audio extraction failed: {err}"

        # apad target: restore any milliseconds lost to sox trim
        dur_flag = f"{actual_dur:.6f}" if actual_dur > 0 else cap
        apad = f",apad=whole_dur={dur_flag}" if actual_dur > 0 else ""

        if len(semitones) == 1:
            # ── Single-pitch branch ───────────────────────────────────────────
            bent_audio = os.path.join(tmpdir, "bent_0.wav")
            result = subprocess.run(
                [sox_bin, raw_audio, bent_audio,
                 "bend", "-f", "30",
                 f"0,{semitones[0] * 100},0.001",
                 "trim", "0.023"],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                return False, f"❌ sox bend failed: {(result.stderr or result.stdout)[-600:]}"

            if has_video:
                ok, err = _run_ffmpeg_raw([
                    "ffmpeg", "-y",
                    "-i", raw_video,
                    "-i", bent_audio,
                    "-filter_complex", f"[1:a]highpass=5{apad}[ineger]",
                    "-map", "0:v",
                    "-map", "[ineger]",
                    "-c:v", "copy", "-c:a", "pcm_s16le",
                    "-t", dur_flag,
                    output_path,
                ], timeout=300)
            else:
                ok, err = _run_ffmpeg_raw([
                    "ffmpeg", "-y",
                    "-i", bent_audio,
                    "-af", f"highpass=5{apad}",
                    "-t", dur_flag,
                    "-c:a", "aac", "-b:a", "192k",
                    output_path,
                ], timeout=180)
            if not ok:
                return False, f"Remux failed: {err}"

        else:
            # ── Multi-pitch branch ────────────────────────────────────────────
            bent_files: list[str] = []
            for idx, st in enumerate(semitones):
                bent = os.path.join(tmpdir, f"bent_{idx}.wav")
                result = subprocess.run(
                    [sox_bin, raw_audio, bent,
                     "bend", "-f", "30",
                     f"0,{st * 100},0.001",
                     "trim", "0.021"],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode != 0:
                    return False, (
                        f"❌ sox bend failed (voice {idx}, pitch {st:+}st): "
                        f"{(result.stderr or result.stdout)[-600:]}"
                    )
                bent_files.append(bent)

            # Build amix command; input 0 = raw_video, inputs 1..N = bent wavs.
            mix_labels = "".join(f"[{idx + 1}]" for idx in range(len(bent_files)))
            filter_complex = f"{mix_labels}amix={len(bent_files)}:normalize=0,highpass=17.5{apad}"

            mix_cmd = ["ffmpeg", "-y", "-i", raw_video]
            for bf in bent_files:
                mix_cmd += ["-i", bf]

            if has_video:
                mix_cmd += [
                    "-filter_complex", filter_complex,
                    "-map", "0:v",
                    "-c:v", "copy", "-c:a", "pcm_s16le",
                    "-t", dur_flag,
                    output_path,
                ]
            else:
                mix_cmd += [
                    "-filter_complex", filter_complex,
                    "-t", dur_flag,
                    "-c:a", "aac", "-b:a", "192k",
                    output_path,
                ]

            ok, err = _run_ffmpeg_raw(mix_cmd, timeout=300)
            if not ok:
                return False, f"amix/remux failed: {err}"

    return True, ""





def _build_atempo_chain(speed: float) -> str:
    """Build an atempo filter chain that handles FFmpeg's 0.5–100.0 bounds.

    FFmpeg's atempo filter only accepts values between 0.5 and 100.0.
    For speeds outside this range, chain multiple atempo filters.
    """
    if 0.5 <= speed <= 100.0:
        return f"atempo={speed}"
    # Chain multiple atempo filters
    parts = []
    remaining = speed
    while remaining > 100.0:
        parts.append("atempo=100.0")
        remaining /= 100.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining}")
    return ",".join(parts)


# ---------- Syncaudio (video/audio duration sync) ----------

def _run_syncaudio(
    input_path: str,
    output_path: str,
    alt_mode: bool = False,
) -> tuple[bool, str]:
    """Sync video and audio durations by adjusting playback speed.

    Default mode: stretch/compress video PTS to match audio duration.
    Alt mode:     adjust audio tempo (atempo) to match video duration.

    Splits the input into a video-only and audio-only temp file so that
    -stream_loop -1 can be used on audio and -t pins the output length.

    Returns (ok, info_string_or_error).
    """
    import tempfile, os as _os

    tmpdir = tempfile.mkdtemp(prefix="syncaudio_")
    v_path = _os.path.join(tmpdir, "v.mp4")
    a_path = _os.path.join(tmpdir, "a.wav")

    try:
        # Split: video-only
        ok, err = _run_ffmpeg_raw(
            ["ffmpeg", "-y", "-i", input_path, "-an", "-c:v", "copy", v_path],
            timeout=120,
        )
        if not ok:
            return False, f"Video split failed: {err}"

        # Split: audio-only
        ok, err = _run_ffmpeg_raw(
            ["ffmpeg", "-y", "-i", input_path, "-vn", a_path],
            timeout=120,
        )
        if not ok:
            return False, f"Audio split failed: {err}"

        # Durations from the split files (more reliable than muxed container)
        vd = _ffprobe_duration(v_path)
        ad_raw = _ffprobe(a_path, "-select_streams", "a:0",
                          "-show_entries", "format=duration",
                          "-of", "csv=p=0")
        try:
            ad = float(ad_raw)
        except (ValueError, TypeError):
            ad = 0.0

        if vd <= 0 or ad <= 0:
            return False, f"Could not determine durations (video={vd:.3f}s, audio={ad:.3f}s)"

        # Frame rate from original
        fr_out = _ffprobe(input_path, "-select_streams", "v:0",
                          "-show_entries", "stream=r_frame_rate",
                          "-of", "default=nokey=1:noprint_wrappers=1")

        if alt_mode:
            # Alt mode: adjust audio speed to match video duration
            speed = ad / vd
            atempo_filter = _build_atempo_chain(speed)
            cmd = [
                "ffmpeg", "-y",
                "-i", v_path,
                "-stream_loop", "-1", "-i", a_path,
                "-af", atempo_filter,
                "-map", "0:v", "-map", "1:a",
                "-t", str(vd),
                "-c:v", "copy",
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            # Default mode: stretch video PTS to match audio duration
            speed = vd / ad
            vf = f"setpts=1/({vd}/{ad})*PTS"
            if fr_out:
                vf += f",fps={fr_out}"
            cmd = [
                "ffmpeg", "-y",
                "-i", v_path,
                "-stream_loop", "-1", "-i", a_path,
                "-vf", vf,
                "-map", "0:v", "-map", "1:a",
                "-t", str(vd),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                "-movflags", "+faststart",
                output_path,
            ]

        ok, err = _run_ffmpeg_raw(cmd, timeout=300)
        if not ok:
            return False, f"Sync failed: {err}"

    finally:
        for p in (v_path, a_path):
            try:
                _os.unlink(p)
            except OSError:
                pass
        try:
            _os.rmdir(tmpdir)
        except OSError:
            pass

    diff = vd - ad
    info = (
        f"Video: {vd:.3f}s\n"
        f"Audio: {ad:.3f}s\n\n"
        f"Speed Used: {speed:.6f}\n"
        f"Diff: {diff:.6f}"
    )
    return True, info

# ---------- Preview1280 (TV-simulator montage) ----------

async def _ensure_displacement_map(workdir: str) -> str:
    """Ensure the TV simulator displacement map exists, downloading if needed.

    Returns the path to the .mov file.
    """
    # First check if the bundled copy exists
    bundled = Path("bot/displacemaps/tvsimulator.mov")
    if bundled.exists():
        return str(bundled)

    # Try to download it
    disp_dir = os.path.join(workdir, "displacemaps")
    os.makedirs(disp_dir, exist_ok=True)
    dest = os.path.join(disp_dir, "tvsimulator.mov")
    if os.path.exists(dest):
        return dest

    try:
        await download_url(
            "https://file.garden/aTXso15ukD3mnuPI/tv_sim_displacement_map.mov",
            dest
        )
        return dest
    except Exception:
        # Last resort: check common locations
        for candidate in [
            "displacemaps/tvsimulator.mov",
            "bot/displacemaps/tvsimulator.mov",
            "/app/bot/displacemaps/tvsimulator.mov",
        ]:
            if os.path.exists(candidate):
                return candidate
        raise FileNotFoundError(
            "TV simulator displacement map not found and could not be downloaded. "
            "Place it at bot/displacemaps/tvsimulator.mov"
        )


def _generate_hald_cluts(workdir: str) -> list[str]:
    """Generate Hald CLUT .ppm files for hue shifts using ImageMagick.

    Returns paths to [hslhue_54.ppm, hslhue_180.ppm, hslhue_22.ppm, hslhue_108_30.ppm].
    CLUT hue values use ImageMagick -modulate formula: hue_frac * 200 + 100 (or +200 for sat boost).
    """
    # (filename, brightness, saturation, hue_mod_value)
    # hue_mod_value = hue_fraction * 200 + 100
    # For saturation-boosted CLUTs, saturation > 100 and hue_mod = hue_fraction * 200 + 200
    clut_specs = [
        # hslhue_54: hue shift 54° → fraction 0.15, mod = 0.15*200+100 = 130
        ("hslhue_54.ppm", 100, 100, 130),
        # hslhue_180: hue shift 180° → fraction 0.5, mod = 0.5*200+100 = 200
        ("hslhue_180.ppm", 100, 100, 200),
        # hslhue_22: hue shift 22° → fraction 0.06, mod = 0.06*200+100 = 112
        ("hslhue_22.ppm", 100, 100, 112),
        # hslhue_108_30: hue shift 108° + saturation boost → fraction 0.3, mod = 0.3*200+200 = 260
        ("hslhue_108_30.ppm", 100, 130, 260),
    ]
    paths = []
    for i, (filename, brightness, saturation, hue_mod) in enumerate(clut_specs):
        path = os.path.join(workdir, filename)
        cmd = [
            "magick", "hald:4",
            "-modulate", f"{brightness},{saturation},{hue_mod}",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            # Fallback: create a simple identity CLUT
            # If magick isn't available, skip CLUT effects
            pass
        # For hslhue_108_30 (index 3), apply additional -modulate 100,100,0
        if i == 3 and os.path.exists(path):
            extra_cmd = [
                "magick", path,
                "-modulate", "100,100,0",
                path
            ]
            subprocess.run(extra_cmd, capture_output=True, text=True, timeout=30)
        paths.append(path)
    return paths


def _run_preview1280(
    input_path: str,
    output_path: str,
    start_offset: float = 1.85,
    segment_dur: float = 0.85,
    force_output_size: tuple[int, int] | None = None,
) -> tuple[bool, str]:
    """Run the preview1280 TV-simulator montage pipeline.

    This creates a 12-segment montage at 640x360, then scales to original size.
    Requires: ffmpeg, ImageMagick (magick), and the tvsimulator.mov displacement map.
    Uses rubberband audio filter for high-quality pitch shifting.
    """
    # Helper: rubberband pitch filter string for N semitones
    # Pre-compute 2^(N/12) as a float to avoid FFmpeg expression parsing issues
    def _rb(semitones: float, transients: str = "mixed") -> str:
        pitch_ratio = 2 ** (semitones / 12)
        return (
            f"rubberband=pitch={pitch_ratio:.6f}:"
            f"window=short:transients={transients}:"
            f"detector=soft:channels=together:pitchq=consistency"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        info = _ffprobe_video_info(input_path)
        w, h = info["width"], info["height"]
        dur = info["duration"]

        if w == 0 or h == 0:
            return False, "Could not read input video dimensions."

        # Generate Hald CLUTs
        cluts = _generate_hald_cluts(tmpdir)
        clut_54 = cluts[0] if os.path.exists(cluts[0]) else None
        clut_180 = cluts[1] if os.path.exists(cluts[1]) else None
        clut_22 = cluts[2] if os.path.exists(cluts[2]) else None
        clut_108_30 = cluts[3] if os.path.exists(cluts[3]) else None

        # Locate displacement map
        disp_map = None
        for candidate in [
            "bot/displacemaps/tvsimulator.mov",
            "displacemaps/tvsimulator.mov",
            "/app/bot/displacemaps/tvsimulator.mov",
        ]:
            if os.path.exists(candidate):
                disp_map = candidate
                break

        # Compute timing
        t = segment_dur
        t2 = segment_dur / 2
        t3 = start_offset + segment_dur

        # Step 1: Pre-process input to 640x360 FFV1
        avi0 = os.path.join(tmpdir, "0.avi")
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", input_path,
            "-vf", "scale=640:360,setsar=1:1",
            "-ss", str(start_offset), "-to", str(t3),
            "-c:v", "ffv1", "-c:a", "pcm_s16le",
            avi0
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=120)
        if not ok:
            return False, f"Step 1 (pre-process) failed: {err}"

        avi_w = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=width",
                         "-of", "default=nw=1:nk=1") or "640"
        avi_h = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=height",
                         "-of", "default=nw=1:nk=1") or "360"

        # Helper to build segment ffmpeg commands
        segments = []

        # Segment 1: plain copy, duration t
        seg1 = os.path.join(tmpdir, "1.avi")
        segments.append(([
            "ffmpeg", "-y", "-i", avi0,
            "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
            seg1
        ], seg1))

        # Segment 2: hue +54 (hslhue_54), pitch +1 semitone (rubberband)
        seg2 = os.path.join(tmpdir, "2.avi")
        if clut_54:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", f"movie={clut_54},[in]haldclut,format=yuv420p",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg2
            ], seg2))
        else:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", "hue=h=54",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg2
            ], seg2))

        # Segment 3: hue +180 + displacement map + mirror + pitch -2 semitones
        seg3 = os.path.join(tmpdir, "3.avi")
        if disp_map and clut_180:
            fc = (
                f"movie={clut_180}[h];"
                f"[0][h]haldclut,hflip,crop=iw/2:ih:0:0,split[left][tmp];"
                f"[tmp]hflip[right];[left][right]hstack,format=yuv420p,format=bgr32[00];"
                f"[1]crop=iw:ih/1:0:0,scale={avi_w}:{avi_h},eq=contrast=0.375,format=bgr32,hue=b=-0.033[x];"
                f"nullsrc=1x1,geq=r=128:g=128:b=128,scale={avi_w}:{avi_h},format=bgr32[y];"
                f"[00][x][y]displace=edge=wrap[v]"
            )
            segments.append(([
                "ffmpeg", "-y", "-i", avi0, "-stream_loop", "-1", "-i", disp_map,
                "-filter_complex", fc,
                "-af", _rb(-2),
                "-map", "[v]", "-map", "0:a",
                "-pix_fmt", "yuv420p",
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg3
            ], seg3))
        else:
            # Fallback without displacement
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", "hue=h=180,hflip,crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack,format=yuv420p",
                "-af", _rb(-2),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg3
            ], seg3))

        # Segment 4: hue +54 (hslhue_54), pitch +1 semitone (same as seg2)
        seg4 = os.path.join(tmpdir, "4.avi")
        if clut_54:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", f"movie={clut_54},[in]haldclut,format=yuv420p",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg4
            ], seg4))
        else:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", "hue=h=54",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg4
            ], seg4))

        # Segments 5-12: shorter segments (t2 duration)
        short_specs = [
            # (seg_num, vf_filter, af_filter)
            (5, None, None),  # plain copy
            (6, f"movie={clut_22},[in]haldclut,hflip,format=yuv420p" if clut_22 else "hue=h=22,hflip,format=yuv420p",
             _rb(2, "smooth")),  # hue+22, hflip, pitch+2 (smooth transients)
            (7, f"movie={clut_54},[in]haldclut,format=yuv420p" if clut_54 else "hue=h=54,format=yuv420p",
             _rb(1)),  # hue+54, pitch+1
            (8, f"movie={clut_108_30},[in]haldclut,hflip,format=yuv420p" if clut_108_30 else "hue=h=108,hflip,format=yuv420p",
             _rb(3)),  # hue+108+sat30, hflip, pitch+3
            (9, f"movie={clut_180},[in]haldclut,format=yuv420p" if clut_180 else "hue=h=180,format=yuv420p",
             _rb(-2)),  # hue+180, pitch-2
            (10, "hflip", None),  # just hflip
            (11, f"movie={clut_54},[in]haldclut,format=yuv420p" if clut_54 else "hue=h=54,format=yuv420p",
             _rb(1)),  # hue+54, pitch+1
            (12, f"movie={clut_108_30},[in]haldclut,hflip,format=yuv420p" if clut_108_30 else "hue=h=108,hflip,format=yuv420p",
             _rb(3)),  # hue+108+sat30, hflip, pitch+3
        ]

        for seg_num, vf, af in short_specs:
            seg_path = os.path.join(tmpdir, f"{seg_num}.avi")
            cmd = ["ffmpeg", "-y", "-i", avi0]
            if vf:
                cmd.extend(["-vf", vf])
            if af:
                cmd.extend(["-af", af])
            cmd.extend(["-t", str(t2), "-c:v", "ffv1", "-c:a", "pcm_s16le", seg_path])
            segments.append((cmd, seg_path))

        # Render all segments
        for i, (cmd, seg_path) in enumerate(segments):
            ok, err = _run_ffmpeg_raw(cmd, timeout=120)
            if not ok:
                return False, f"Segment {i+1}/{len(segments)} failed: {err}"

        # Concat all segments using concat protocol
        avi_files = [sp for _, sp in segments if os.path.exists(sp)]
        if not avi_files:
            return False, "No segments were produced."

        concat_str = "|".join(avi_files)
        out_w, out_h = force_output_size if force_output_size else (w, h)
        cmd = [
            "ffmpeg", "-y",
            "-i", f"concat:{concat_str}",
            "-vf", f"scale={out_w}:{out_h},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]
        return _run_ffmpeg_raw(cmd, timeout=180)


def _generate_opposite_hald_cluts(workdir: str) -> list[str]:
    """Generate Hald CLUT .ppm files for the *opposite* (negative) hue shifts used by oppositep1280.

    Returns paths to [hslhue_neg54.ppm, hslhue_180.ppm, hslhue_neg21_6.ppm, hslhue_neg108_neg30.ppm].
    These are the inverse hue shifts of the preview1280 CLUTs:
      preview +54°  → opposite -54°
      preview +22°  → opposite -21.6°
      preview +108°/+30sat → opposite -108°/-30sat
    The +180° CLUT is shared between both pipelines.
    """
    clut_specs = [
        # hslhue_neg54: hue shift -54° → fraction -0.3, mod = -0.3*200+100 = 40... nope.
        # ImageMagick formula: hue_shift_deg / 1.8 + 100
        # -54/1.8+100 = -30+100 = 70
        ("hslhue_neg54.ppm", 100, 100, 70),
        # hslhue_180: same as preview1280 (fraction 0.5, mod = 0.5*200+100 = 200)
        ("hslhue_180.ppm", 100, 100, 200),
        # hslhue_neg21_6: -21.6/1.8+100 = -12+100 = 88
        ("hslhue_neg21_6.ppm", 100, 100, 88),
        # hslhue_neg108_neg30: -108° hue + saturation drop to 70
        # -108/1.8+100 = -60+100 = 40
        ("hslhue_neg108_neg30.ppm", 100, 70, 40),
    ]
    paths = []
    for filename, brightness, saturation, hue_mod in clut_specs:
        path = os.path.join(workdir, filename)
        cmd = [
            "magick", "hald:4",
            "-modulate", f"{brightness},{saturation},{hue_mod}",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            pass  # CLUT effects will be skipped if magick isn't available
        paths.append(path)
    return paths


def _run_oppositep1280(
    input_path: str,
    output_path: str,
    start_offset: float = 1.85,
    segment_dur: float = 0.85,
    force_output_size: tuple[int, int] | None = None,
) -> tuple[bool, str]:
    """Run the oppositep1280 TV-simulator montage pipeline.

    This is the *inverse* of preview1280: all hue shifts are negated and all
    pitch shifts are inverted (positive semitones become negative and vice-versa).
    The pipeline structure (12 segments, displacement map, timing) is identical.

    Requires: ffmpeg, ImageMagick (magick), and the tvsimulator.mov displacement map.
    Uses rubberband audio filter for high-quality pitch shifting.
    """
    # Helper: rubberband pitch filter string for N semitones
    def _rb(semitones: float, transients: str = "mixed") -> str:
        pitch_ratio = 2 ** (semitones / 12)
        return (
            f"rubberband=pitch={pitch_ratio:.6f}:"
            f"window=short:transients={transients}:"
            f"detector=soft:channels=together:pitchq=consistency"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        info = _ffprobe_video_info(input_path)
        w, h = info["width"], info["height"]
        dur = info["duration"]

        if w == 0 or h == 0:
            return False, "Could not read input video dimensions."

        # Generate Hald CLUTs (opposite/negative hues)
        cluts = _generate_opposite_hald_cluts(tmpdir)
        clut_neg54 = cluts[0] if os.path.exists(cluts[0]) else None
        clut_180 = cluts[1] if os.path.exists(cluts[1]) else None
        clut_neg21_6 = cluts[2] if os.path.exists(cluts[2]) else None
        clut_neg108_neg30 = cluts[3] if os.path.exists(cluts[3]) else None

        # Locate displacement map
        disp_map = None
        for candidate in [
            "bot/displacemaps/tvsimulator.mov",
            "displacemaps/tvsimulator.mov",
            "/app/bot/displacemaps/tvsimulator.mov",
        ]:
            if os.path.exists(candidate):
                disp_map = candidate
                break

        # Compute timing
        t = segment_dur
        t2 = segment_dur / 2
        t3 = start_offset + segment_dur

        # Step 1: Pre-process input to 640x360 FFV1
        avi0 = os.path.join(tmpdir, "0.avi")
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", input_path,
            "-vf", "scale=640:360,setsar=1:1",
            "-ss", str(start_offset), "-to", str(t3),
            "-c:v", "ffv1", "-c:a", "pcm_s16le",
            avi0
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=120)
        if not ok:
            return False, f"Step 1 (pre-process) failed: {err}"

        avi_w = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=width",
                         "-of", "default=nw=1:nk=1") or "640"
        avi_h = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=height",
                         "-of", "default=nw=1:nk=1") or "360"

        # Step 1b: Standardize fps to 29.97
        modfps = os.path.join(tmpdir, "modfps.avi")
        cmd = [
            "ffmpeg", "-y", "-i", avi0,
            "-vf", "fps=29.97",
            "-c:v", "ffv1", "-c:a", "pcm_s16le",
            modfps
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=120)
        if not ok:
            return False, f"Step 1b (fps standardize) failed: {err}"

        # Helper to build segment ffmpeg commands
        segments = []

        # ── Segment 1: plain copy, duration t ─────────────────────────────
        seg1 = os.path.join(tmpdir, "1.avi")
        segments.append(([
            "ffmpeg", "-y", "-i", modfps,
            "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
            seg1
        ], seg1))

        # ── Segment 2: hue -54 (hslhue_neg54), pitch -1 semitone ──────────
        seg2 = os.path.join(tmpdir, "2.avi")
        if clut_neg54:
            segments.append(([
                "ffmpeg", "-y", "-i", modfps,
                "-vf", f"movie={clut_neg54},[in]haldclut,format=yuv420p",
                "-af", _rb(-1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg2
            ], seg2))
        else:
            segments.append(([
                "ffmpeg", "-y", "-i", modfps,
                "-vf", "hue=h=-54",
                "-af", _rb(-1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg2
            ], seg2))

        # ── Segment 3: hue +180 + displacement map + mirror + pitch +2 st ──
        seg3 = os.path.join(tmpdir, "3.avi")
        if disp_map and clut_180:
            fc = (
                f"movie={clut_180}[h];"
                f"[0][h]haldclut,crop=iw/2:ih:0:0,split[left][tmp];"
                f"[tmp]hflip[right];[left][right]hstack,format=yuv420p,format=bgr32[00];"
                f"[1]crop=iw:ih/1:0:0,scale={avi_w}:{avi_h},eq=contrast=-0.375,format=bgr32,hue=b=-0.033[x];"
                f"nullsrc=1x1,geq=r=128:g=128:b=128,scale={avi_w}:{avi_h},format=bgr32[y];"
                f"[00][x][y]displace=edge=wrap[v]"
            )
            segments.append(([
                "ffmpeg", "-y", "-i", modfps, "-stream_loop", "-1", "-i", disp_map,
                "-filter_complex", fc,
                "-af", _rb(2),
                "-map", "[v]", "-map", "0:a",
                "-pix_fmt", "yuv420p",
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg3
            ], seg3))
        else:
            # Fallback without displacement
            segments.append(([
                "ffmpeg", "-y", "-i", modfps,
                "-vf", "hue=h=180,crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack,format=yuv420p",
                "-af", _rb(2),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg3
            ], seg3))

        # ── Segment 4: hue -54 (hslhue_neg54), pitch -1 semitone ──────────
        seg4 = os.path.join(tmpdir, "4.avi")
        if clut_neg54:
            segments.append(([
                "ffmpeg", "-y", "-i", modfps,
                "-vf", f"movie={clut_neg54},[in]haldclut,format=yuv420p",
                "-af", _rb(-1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg4
            ], seg4))
        else:
            segments.append(([
                "ffmpeg", "-y", "-i", modfps,
                "-vf", "hue=h=-54",
                "-af", _rb(-1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg4
            ], seg4))

        # ── Segments 5-12: shorter segments (t2 duration) ──────────────────
        # oppositep1280 pitches are the inverse of preview1280:
        #   preview +2 st (smooth) → opposite -2 st (smooth)
        #   preview +1 st         → opposite -1 st
        #   preview +3 st         → opposite -3 st
        #   preview -2 st         → opposite +2 st
        short_specs = [
            # (seg_num, vf_filter, af_filter)
            (5, None, None),  # plain copy
            (6, f"movie={clut_neg21_6},[in]haldclut,hflip,format=yuv420p" if clut_neg21_6 else "hue=h=-21.6,hflip,format=yuv420p",
             _rb(-2, "smooth")),  # hue-21.6, hflip, pitch-2 (smooth transients)
            (7, f"movie={clut_neg54},[in]haldclut,format=yuv420p" if clut_neg54 else "hue=h=-54,format=yuv420p",
             _rb(-1)),  # hue-54, pitch-1
            (8, f"movie={clut_neg108_neg30},[in]haldclut,hflip,format=yuv420p" if clut_neg108_neg30 else "hue=h=-108,hflip,format=yuv420p",
             _rb(-3)),  # hue-108-sat30, hflip, pitch-3
            (9, f"movie={clut_180},[in]haldclut,format=yuv420p" if clut_180 else "hue=h=180,format=yuv420p",
             _rb(2)),  # hue+180, pitch+2
            (10, "hflip", None),  # just hflip
            (11, f"movie={clut_neg54},[in]haldclut,format=yuv420p" if clut_neg54 else "hue=h=-54,format=yuv420p",
             _rb(-1)),  # hue-54, pitch-1
            (12, f"movie={clut_neg108_neg30},[in]haldclut,hflip,format=yuv420p" if clut_neg108_neg30 else "hue=h=-108,hflip,format=yuv420p",
             _rb(-3)),  # hue-108-sat30, hflip, pitch-3
        ]

        for seg_num, vf, af in short_specs:
            seg_path = os.path.join(tmpdir, f"{seg_num}.avi")
            cmd = ["ffmpeg", "-y", "-i", modfps]
            if vf:
                cmd.extend(["-vf", vf])
            if af:
                cmd.extend(["-af", af])
            cmd.extend(["-t", str(t2), "-c:v", "ffv1", "-c:a", "pcm_s16le", seg_path])
            segments.append((cmd, seg_path))

        # Render all segments
        for i, (cmd, seg_path) in enumerate(segments):
            ok, err = _run_ffmpeg_raw(cmd, timeout=120)
            if not ok:
                return False, f"Segment {i+1}/{len(segments)} failed: {err}"

        # Concat all segments using concat protocol
        avi_files = [sp for _, sp in segments if os.path.exists(sp)]
        if not avi_files:
            return False, "No segments were produced."

        concat_str = "|".join(avi_files)
        out_w, out_h = force_output_size if force_output_size else (w, h)
        cmd = [
            "ffmpeg", "-y",
            "-i", f"concat:{concat_str}",
            "-vf", f"scale={out_w}:{out_h},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]
        return _run_ffmpeg_raw(cmd, timeout=180)









def _run_preview1280what(
    input_path: str,
    output_path: str,
    start_offset: float = 1.85,
    segment_dur: float = 0.85,
    target_len: float = 5.0,
    use_tempo: bool = False,
) -> tuple[bool, str]:
    """28-segment TV-simulator extended montage (preview1280 FFmpeg Extended v8 v2+).

    4 full segs (t) + 23 half segs (t2) + 1 looping long seg (target_len).
    use_tempo=True adds proportional time-stretch to each rubberband filter.
    Requires: ffmpeg, ImageMagick (magick), tvsimulator.mov displacement map.
    """
    def _rb(semitones: float, transients: str = "mixed", tempo: float = 0.0) -> str:
        ratio = 2 ** (semitones / 12)
        rb = (
            f"rubberband=pitch={ratio:.6f}:"
            f"window=short:transients={transients}:"
            f"detector=soft:channels=together:pitchq=consistency"
        )
        if use_tempo and tempo:
            rb += f":tempo={tempo:.6f}"
        return rb

    with tempfile.TemporaryDirectory() as tmpdir:
        info = _ffprobe_video_info(input_path)
        w, h = info["width"], info["height"]
        if w == 0 or h == 0:
            return False, "Could not read input video dimensions."

        # Generate CLUTs (values match original tag script)
        _clut_specs = [
            ("c54",  "hslhue_54.ppm",     100, 100, 130),
            ("cn54", "hslhue_neg54.ppm",  100, 100,  70),
            ("c180", "hslhue_180.ppm",    100, 100, 200),
            ("c22",  "hslhue_22.ppm",     100, 100, 112),
            ("c108", "hslhue_108_30.ppm", 100, 130, 160),
        ]
        cluts: dict[str, str | None] = {}
        for key, fname, br, sat, hue_mod in _clut_specs:
            cp = os.path.join(tmpdir, fname)
            r = subprocess.run(
                ["magick", "hald:4", "-modulate", f"{br},{sat},{hue_mod}", cp],
                capture_output=True, text=True, timeout=30,
            )
            cluts[key] = cp if r.returncode == 0 else None
        c54  = cluts["c54"]
        cn54 = cluts["cn54"]
        c180 = cluts["c180"]
        c22  = cluts["c22"]
        c108 = cluts["c108"]

        # Displacement map
        disp_map = next(
            (p for p in [
                "bot/displacemaps/tvsimulator.mov",
                "displacemaps/tvsimulator.mov",
                "/app/bot/displacemaps/tvsimulator.mov",
            ] if os.path.exists(p)),
            None,
        )

        # Timing
        t  = segment_dur
        t2 = segment_dur / 2
        t3 = start_offset + segment_dur
        t5 = start_offset + target_len

        # Short clip (0.avi) — covers segments 1-27
        avi0 = os.path.join(tmpdir, "0.avi")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", input_path,
            "-vf", "scale=640:360,setsar=1:1",
            "-ss", str(start_offset), "-to", str(t3),
            "-c:v", "ffv1", "-c:a", "pcm_s16le", avi0,
        ], timeout=120)
        if not ok:
            return False, f"Short clip failed: {err}"

        avi_w = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=width",
                         "-of", "default=nw=1:nk=1") or "640"
        avi_h = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=height",
                         "-of", "default=nw=1:nk=1") or "360"

        # Long clip (0_long.avi) — for segment 28
        avi0_long = os.path.join(tmpdir, "0_long.avi")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", input_path,
            "-vf", "scale=640:360,setsar=1:1",
            "-ss", str(start_offset), "-to", str(t5),
            "-c:v", "ffv1", "-c:a", "pcm_s16le", avi0_long,
        ], timeout=120)
        if not ok:
            return False, f"Long clip failed: {err}"

        # Filter helpers
        def hclut(path: str | None, deg: float) -> str:
            if path:
                return f"movie={path},[in]haldclut,format=yuv420p"
            return f"hue=h={deg},format=yuv420p"

        _geq_wave = (
            "geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*0)))*(-15*0)),"
            "Y-((sin((T*5*0+(0.17946*15))+(X/W)*(PI*6.09)))*(-15*0.72)))'"
        )

        def geq108(path: str | None) -> str:
            return (
                f"{hclut(path, 108)},format=yuv444p,scale=640:640,"
                f"{_geq_wave},scale={avi_w}:{avi_h},setsar=1:1,format=yuv420p"
            )

        if disp_map and c180:
            _disp_fc = (
                f"movie={c180}[h];"
                f"[0][h]haldclut,hflip,crop=iw/2:ih:0:0,split[left][tmp];"
                f"[tmp]hflip[right];[left][right]hstack,format=yuv420p,format=bgr32[00];"
                f"[1]crop=iw:ih/1:0:0,scale={avi_w}:{avi_h},eq=contrast=0.375,"
                f"format=bgr32,hue=b=-0.033[x];"
                f"nullsrc=1x1,geq=r=128:g=128:b=128,scale={avi_w}:{avi_h},format=bgr32[y];"
                f"[00][x][y]displace=edge=wrap[v]"
            )
            _disp_has_map = True
        else:
            _disp_fc = (
                "hue=h=180,hflip,crop=iw/2:ih:0:0,split[left][tmp];"
                "[tmp]hflip[right];[left][right]hstack,format=yuv420p"
            )
            _disp_has_map = False

        segments: list[tuple[list[str], str]] = []

        def seg(n: int, dur: float,
                vf: str | None = None, af: str | None = None) -> None:
            path = os.path.join(tmpdir, f"{n}.avi")
            cmd = ["ffmpeg", "-y", "-i", avi0]
            if vf:
                cmd.extend(["-vf", vf])
            if af:
                cmd.extend(["-af", af])
            cmd.extend(["-t", str(dur), "-c:v", "ffv1", "-c:a", "pcm_s16le", path])
            segments.append((cmd, path))

        def seg_disp(n: int, dur: float) -> None:
            path = os.path.join(tmpdir, f"{n}.avi")
            if _disp_has_map:
                cmd = [
                    "ffmpeg", "-y", "-i", avi0,
                    "-stream_loop", "-1", "-i", disp_map,
                    "-filter_complex", _disp_fc,
                    "-af", _rb(-2, tempo=0.890),
                    "-map", "[v]", "-map", "0:a",
                    "-pix_fmt", "yuv420p",
                    "-t", str(dur), "-c:v", "ffv1", "-c:a", "pcm_s16le", path,
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-i", avi0,
                    "-vf", _disp_fc,
                    "-af", _rb(-2, tempo=0.890),
                    "-t", str(dur), "-c:v", "ffv1", "-c:a", "pcm_s16le", path,
                ]
            segments.append((cmd, path))

        # Segments 1-4: full duration (t)
        seg(1, t)
        seg(2, t, vf=hclut(c54, 54),  af=_rb(1,  tempo=1.059))
        seg_disp(3, t)
        seg(4, t, vf=hclut(c54, 54),  af=_rb(1,  tempo=1.059))

        # Segments 5-27: half duration (t2)
        seg(5, t2)
        seg(6, t2,
            vf=f"movie={c22},[in]haldclut,hflip,format=yuv420p" if c22
               else "hue=h=22,hflip,format=yuv420p",
            af=_rb(2, "smooth", tempo=2 ** (2 / 12)))
        seg(7,  t2, vf=hclut(c54,  54),  af=_rb(1,  tempo=1.059))
        seg(8,  t2, vf=geq108(c108),     af=_rb(3,  tempo=1.389))
        seg_disp(9, t2)
        seg(10, t2, vf="swapuv")
        seg(11, t2, vf=hclut(c54,  54),  af=_rb(1,  tempo=1.059))
        seg(12, t2, vf=geq108(c108),     af=_rb(3,  tempo=1.389))
        seg_disp(13, t2)
        seg(14, t2, vf="swapuv")
        seg(15, t2, vf=hclut(cn54, -54), af=_rb(-1, tempo=0.940))
        seg(16, t2, vf=hclut(c54,  54),  af=_rb(1,  tempo=1.059))
        seg(17, t2,
            vf=f"movie={c180},[in]haldclut,format=yuv420p,negate,format=yuv420p" if c180
               else "hue=h=180,negate,format=yuv420p",
            af=_rb(-4, tempo=2 ** (-4 / 12)))
        seg_disp(18, t2)
        seg(19, t2, vf=hclut(cn54, -54), af=_rb(-1, tempo=0.940))
        seg(20, t2, vf=hclut(c54,  54),  af=_rb(1,  tempo=1.059))
        seg(21, t2)
        seg(22, t2, vf="negate,hflip",   af=_rb(12, tempo=2.0))
        seg(23, t2, vf=hclut(c54,  54),  af=_rb(1,  tempo=1.059))
        seg(24, t2,
            vf=f"movie={c54},[in]haldclut,format=yuv420p,negate,hflip,format=yuv420p" if c54
               else "hue=h=54,negate,hflip,format=yuv420p",
            af=_rb(13, tempo=2.1189))
        seg_disp(25, t2)
        seg(26, t2, vf="swapuv")
        seg(27, t2, vf=hclut(c54,  54),  af=_rb(1,  tempo=1.059))

        # Segment 28: long looping from avi0_long
        seg28_path = os.path.join(tmpdir, "28.avi")
        segments.append(([
            "ffmpeg", "-y", "-i", avi0_long,
            "-vf", geq108(c108),
            "-af", f"aloop=loop=-1:size=2e9,{_rb(3, tempo=1.389)}",
            "-t", str(target_len),
            "-c:v", "ffv1", "-c:a", "pcm_s16le", seg28_path,
        ], seg28_path))

        # Render all segments
        for i, (cmd, seg_path) in enumerate(segments):
            ok, err = _run_ffmpeg_raw(cmd, timeout=180)
            if not ok:
                return False, f"Segment {i + 1}/{len(segments)} failed: {err}"

        # Concat -> output
        avi_files = [sp for _, sp in segments if os.path.exists(sp)]
        if not avi_files:
            return False, "No segments were produced."

        return _run_ffmpeg_raw([
            "ffmpeg", "-y",
            "-i", "concat:" + "|".join(avi_files),
            "-vf", f"scale={w}:{h},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ], timeout=300)


# ---------- Bot events & commands ----------

_STARTUP_NOTICE_CHANNEL_ID = 1496114769458106509
_startup_notice_sent = False


def _latest_update_reason() -> str:
    """Return the newest update-log entry for the restart notification."""
    for line in (__doc__ or "").splitlines():
        line = line.strip()
        if line.startswith("- ") and len(line) > 2:
            return line[2:].strip()
    return "Routine restart."


async def _send_startup_notice():
    global _startup_notice_sent
    if _startup_notice_sent:
        return
    # Mark the attempt before awaiting so a reconnect/on_ready race cannot
    # send duplicate notices.
    _startup_notice_sent = True
    try:
        channel = bot.get_channel(_STARTUP_NOTICE_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(_STARTUP_NOTICE_CHANNEL_ID)
        await channel.send(
            "✅ **IHTX Bot restarted successfully.**\n"
            f"**Change/reason:** {_latest_update_reason()}"
        )
        print(f"[startup] Restart notice sent to channel {_STARTUP_NOTICE_CHANNEL_ID}.")
    except Exception as exc:
        print(f"[startup] Could not send restart notice: {exc}")


@tasks.loop(seconds=5)
async def _process_pending_resets():
    """Poll bot/pending_resets.json and clear usage for requested users."""
    try:
        if not PENDING_RESETS_FILE.exists():
            return
        with PENDING_RESETS_FILE.open() as f:
            user_ids = [int(x) for x in json.load(f)]
        if user_ids:
            for uid in user_ids:
                heavy_usage.pop(uid, None)
            _save_usage()
            PENDING_RESETS_FILE.unlink(missing_ok=True)
    except Exception:
        pass


@bot.event
async def on_ready():
    print(f"IHTX Bot online as {bot.user} (ID: {bot.user.id})")
    print("------")
    # Load cogs
    if not bot.cogs.get("Tags"):
        await bot.add_cog(TagCog(bot))
        print("TagCog loaded")
    _activity_file = Path("bot/activity.json")
    try:
        if _activity_file.exists():
            with _activity_file.open() as _af:
                _ad = json.load(_af)
            _atype_str = _ad.get("type", "watching")
            _aname = _ad.get("name", "")
            if _atype_str == "playing":
                _restored = discord.Game(name=_aname)
            elif _atype_str == "streaming":
                _parts = [p.strip() for p in _aname.split("|", 1)]
                _restored = discord.Streaming(
                    name=_parts[0],
                    url=_parts[1] if len(_parts) > 1 else "https://twitch.tv/placeholder"
                )
            elif _atype_str == "listening":
                _restored = discord.Activity(type=discord.ActivityType.listening, name=_aname)
            else:
                _restored = discord.Activity(type=discord.ActivityType.watching, name=_aname)
            await bot.change_presence(status=discord.Status.online, activity=_restored)
        else:
            await _update_bot_presence()
    except Exception:
        await _update_bot_presence()
    if not _process_pending_resets.is_running():
        _process_pending_resets.start()
    # Pre-download multipitch binary in the background so first use is instant
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _ensure_multipitch_bin)
    # Load tag system cog (once)
    if "Tags" not in bot.cogs:
        try:
            from bot.tags import setup as _tags_setup
            await _tags_setup(bot)
            print("Tag system loaded.")
        except Exception as _tags_exc:
            print(f"Warning: tag system failed to load — {_tags_exc}")
    # Load economy/RPG/fun cog (once)
    if "Economy" not in bot.cogs:
        try:
            from bot.economy_cog import setup as _economy_setup
            await _economy_setup(bot)
            print("EconomyCog loaded.")
        except Exception as _econ_exc:
            print(f"Warning: EconomyCog failed to load — {_econ_exc}")
    # Load garden game cog (once)
    if "Garden" not in bot.cogs:
        try:
            from bot.garden_cog import setup as _garden_setup
            await _garden_setup(bot)
            print("GardenCog loaded.")
        except Exception as _garden_exc:
            print(f"Warning: GardenCog failed to load — {_garden_exc}")
    # Load VEB cog — th/veb effects command + mention-triggered random effects
    if "VEB" not in bot.cogs:
        try:
            from bot.veb_cog import setup as _veb_setup
            await _veb_setup(bot)
            print("VebCog loaded.")
        except Exception as _veb_exc:
            print(f"Warning: VebCog failed to load — {_veb_exc}")
    # Load Bytebeat cog — th/bytebeat waveform generator
    if "Bytebeat" not in bot.cogs:
        try:
            from bot.bytebeat_cog import setup as _bytebeat_setup
            await _bytebeat_setup(bot)
            print("BytebeatCog loaded.")
        except Exception as _bb_exc:
            print(f"Warning: BytebeatCog failed to load — {_bb_exc}")
    # Load Night Shift — procedural Pillow-rendered horror minigame
    if "NightShiftCog" not in bot.cogs:
        try:
            from bot.nightshift import setup as _nightshift_setup
            await _nightshift_setup(bot)
            print("NightShiftCog loaded.")
        except Exception as _nightshift_exc:
            print(f"Warning: NightShiftCog failed to load — {_nightshift_exc}")
    # Auto-sync slash commands in a background task so exceptions surface in
    # the console and don't silently fail inside on_ready's exception handler.
    async def _auto_sync_slash():
        try:
            _SYNC_RO = {"application_id", "version"}
            _app_id = bot.application_id
            _existing: list[dict] = await bot.http.get_global_commands(_app_id)
            _eps: list[dict] = [
                {k: v for k, v in c.items() if k not in _SYNC_RO}
                for c in _existing
                if c.get("type") == 4
            ]
            _payload: list[dict] = [
                cmd.to_dict(bot.tree) for cmd in bot.tree._global_commands.values()
            ]
            _payload.extend(_eps)
            _result: list[dict] = await bot.http.bulk_upsert_global_commands(
                _app_id, payload=_payload
            )
            _slash = [c for c in _result if c.get("type") != 4]
            print(f"[syncslash] {len(_slash)} slash command(s) registered globally.")
        except Exception as exc:
            print(f"[syncslash] Auto-sync failed: {exc}")

    asyncio.ensure_future(_auto_sync_slash())
    print("Bot ready. Slash commands syncing in background…")
    await _send_startup_notice()


@bot.event
async def on_guild_join(guild):
    await _update_bot_presence()


@bot.event
async def on_guild_remove(guild):
    await _update_bot_presence()


def _run_ihtxcustom_workflow(
    input_path: str,
    output_path: str,
    powers: int,
    duration: float,
    vf: str,
    af: str,
) -> tuple[bool, str]:
    """Powers-based IHTX custom workflow.

    Applies vf/af filters `powers` times progressively (each iteration feeds
    into the next), then concatenates all iterations (1× through powers×) via
    the .ts concat protocol — matching the original ihtxcustom script logic.
    """
    powers = min(max(powers, 1), 20)

    with tempfile.TemporaryDirectory() as tmpdir:
        def ts(n: int) -> str:
            return os.path.join(tmpdir, f"{n}.ts")

        def apply_step(src: str, dst: str) -> tuple[bool, str]:
            cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y", "-i", src]
            # Normal path
            if vf:
                cmd.extend(["-vf", vf])
            if af:
                cmd.extend(["-af", af])
            if duration > 0:
                cmd.extend(["-t", str(duration)])
            cmd.extend([
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-ac", "2", "-ar", "44100",
                "-c:a", "mp2", "-b:a", "192k",
                "-bsf:v", "h264_mp4toannexb",
                dst,
            ])
            return _run_ffmpeg_raw(cmd, timeout=180)

        # Step 0 → 1.ts
        ok, err = apply_step(input_path, ts(1))
        if not ok:
            return False, f"Step 1 failed: {err}"

        # Steps 1.ts→2.ts, 2.ts→3.ts, ..., powers.ts→(powers+1).ts
        for i in range(1, powers + 1):
            ok, err = apply_step(ts(i), ts(i + 1))
            if not ok:
                return False, f"Step {i + 1} failed: {err}"

        # Concatenate 1.ts through powers.ts into .mp4 with h264 + aac
        concat_str = "|".join(ts(i) for i in range(1, powers + 1))
        concat_cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", f"concat:{concat_str}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            output_path,
        ]
        ok, err = _run_ffmpeg_raw(concat_cmd, timeout=300)
        if not ok:
            return False, f"Concat failed: {err}"

    return True, ""


@bot.command(name="invlum", aliases=["il"])
async def invlum_command(ctx: commands.Context, *, args: str = "1"):
    """Powers-based luma-inversion stacker.

    Applies curves=all='0/1 1/0' (full luma inversion) powers times progressively
    and concatenates all iterations into a single video.
    Optionally runs a pipe-effect chain on the final concatenated output.

    Usage:
      th/invlum <powers> [duration] [PIPE: effect;effect]

    Examples:
      th/invlum 4
      th/invlum 3 2.0
      th/invlum 5 1.5 PIPE: negate;multipitch=-4|5
      th/invlum 4 1.0 PIPE: huehsv=0.3;multipitch=-7|0|7
    """
    pipe_raw = ""
    pipe_effects: list[tuple[str, list[str]]] = []
    powers = 1
    duration = 1.0

    try:
        pre = re.split(r'PIPE:', args, flags=re.IGNORECASE)[0].strip()
        pre_parts = pre.split()
        if len(pre_parts) >= 2:
            powers = int(pre_parts[0])
            duration = float(pre_parts[1])
        elif len(pre_parts) == 1:
            powers = int(pre_parts[0])

        pipe_m = re.search(r'PIPE:\s*(.*)', args, re.IGNORECASE | re.DOTALL)
        if pipe_m:
            pipe_raw = pipe_m.group(1).strip()
            pipe_effects = _parse_pipe_effects(pipe_raw)
    except (ValueError, IndexError):
        pass

    if powers < 1:
        await ctx.reply(
            "❌ Powers must be at least 1.\n"
            "**Usage:** `th/invlum <powers> [duration] [PIPE: effect;effect]`"
        )
        return

    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply("❌ Attach a video.\n**Usage:** `th/invlum <powers> [duration] [PIPE: effect;effect]`")
        return

    if source.size > MAX_FILE_SIZE:
        await ctx.reply("❌ File too large (max 25 MB).")
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply("❌ File too large (max 25 MB).")
            return
        suffix = Path(source.filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            await ctx.reply(f"❌ `invlum` requires a video file. Got `{suffix}`.")
            return
    else:
        suffix = Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
        if suffix not in VIDEO_EXTENSIONS:
            await ctx.reply(f"❌ `invlum` requires a video file. Got `{suffix}`.")
            return

    pipe_desc = f" | PIPE: `{pipe_raw}`" if pipe_raw else ""
    status_msg = await ctx.reply(
        f"⚙️ **invlum** — `{powers}` power(s) × `{duration}s`{pipe_desc} … this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "invlum_out.mp4")

        try:
            if isinstance(source, discord.Attachment):
                await download_attachment(source, input_path)
            else:
                await download_url(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        lut_path = str(INVLUM_LUT_FILE.resolve())
        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None,
            lambda: _run_ihtxcustom_workflow(
                input_path, output_path, powers, duration,
                f"lut3d={lut_path}", "",
            ),
        )

        if not ok:
            await status_msg.edit(content=f"❌ invlum failed: {err}")
            return

        if pipe_effects:
            pipe_out = os.path.join(tmpdir, "invlum_pipe.mp4")
            ok, err = await loop.run_in_executor(
                None,
                lambda: _apply_pipe_effects(output_path, pipe_out, pipe_effects),
            )
            if not ok:
                await status_msg.edit(content=f"❌ invlum pipe step failed: {err}")
                return
            output_path = pipe_out

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thinvlum.mp4"
        try:
            await ctx.reply(
                content=f"✅ **invlum** done! `{powers}` power(s), `{duration}s` each.",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload: {e}")


@bot.command(name="pipetest", aliases=["pt"])
async def pipetest_command(ctx: commands.Context, *, effects: str = ""):
    """Apply th/ihtx pipe effects once to an attached video/audio.

    Usage:
      th/pipetest effect1;effect2;effect3

    Examples:
      th/pipetest stretch=1.5;negate
      th/pipetest invlum;huehsv=0.5;wave
      th/pipetest ccshue=90;multipitch=-4|5

    Attach a video (or reply to one). Pipe effects are separated by semicolons.
    """
    effects = effects.strip()
    if not effects:
        await ctx.reply(
            "❌ No effects given.\n"
            "**Usage:** `th/pipetest effect1;effect2;...`\n"
            "**Example:** `th/pipetest stretch=1.5;negate`"
        )
        return

    pipe_effects = _parse_pipe_effects(effects)
    if not pipe_effects:
        await ctx.reply("❌ Could not parse any effects.")
        return

    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "❌ No media found. Attach a file or reply to one.\n"
            "**Usage:** `th/pipetest effect1;effect2;...`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply("❌ File too large (max 25 MB).")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in SUPPORTED_EXTENSIONS:
        await ctx.reply(f"❌ Unsupported file type `{suffix}`.")
        return

    effect_label = effects[:120] + ("…" if len(effects) > 120 else "")
    status_msg = await ctx.reply(f"⚙️ **pipetest** — `{effect_label}` … processing…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"pipetest_out{suffix}")

        try:
            if isinstance(source, discord.Attachment):
                await download_attachment(source, input_path)
            else:
                await download_url(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None,
            lambda: _apply_pipe_effects(input_path, output_path, pipe_effects),
        )
        if not ok:
            await status_msg.edit(
                content=_clip_discord_text(f"❌ pipetest failed:\n```\n{err}\n```")
            )
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **pipetest** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large and Catbox upload failed.")
            return

        out_filename = f"534gurts_thpipetest{suffix}"
        try:
            await ctx.reply(
                content=f"✅ **pipetest** — `{effect_label}`",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload: {e}")


# ---------- th/submiteffect — user-submitted named pipe effects ----------

_EFFECT_NAME_RE = re.compile(r"^[a-z0-9_]{1,40}$")


@bot.command(name="submiteffect", aliases=["se", "addeffect"])
async def submiteffect_command(ctx: commands.Context, name: str = "", *, effects: str = ""):
    """Submit a named pipe effect combo so it can be used in th/ihtx.

    Usage:
      th/submiteffect <name> <pipe_effects>
      th/submiteffect gmajor225 huehsv=0.5,channelblend=b;g;r,mp=-4;5

    The name must be lowercase alphanumeric + underscores, max 40 chars,
    and cannot clash with a built-in effect name.
    Use th/listeffects to see all submitted effects.
    """
    name = name.strip().lower()
    # Allow "name = effects" syntax (name with trailing = sign)
    if name.endswith("="):
        name = name[:-1].strip()

    if not name:
        await ctx.reply(
            "❌ No name given.\n"
            "**Usage:** `th/submiteffect <name> <pipe_effects>`\n"
            "**Example:** `th/submiteffect gmajor225 huehsv=0.5,channelblend=b;g;r,mp=-4;5`"
        )
        return

    if not _EFFECT_NAME_RE.match(name):
        await ctx.reply("❌ Effect name must be lowercase letters, digits, or underscores only (max 40 chars).")
        return

    if name in PIPE_EFFECT_NAMES:
        await ctx.reply(f"❌ `{name}` is a built-in effect name and cannot be overridden.")
        return

    # Strip a leading "=" from the effects string (supports "name = effects" split across args)
    effects = effects.strip().lstrip("=").strip()
    if not effects:
        await ctx.reply(
            "❌ No effects given.\n"
            "**Usage:** `th/submiteffect <name> <pipe_effects>`\n"
            "**Example:** `th/submiteffect gmajor225 huehsv=0.5,channelblend=b;g;r,mp=-4;5`"
        )
        return

    # Validate the effects parse to something real
    parsed = _parse_pipe_effects(effects)
    if not parsed:
        await ctx.reply("❌ Could not parse any effects from that string. Check the syntax and try again.")
        return

    _USER_EFFECTS[name] = {
        "effects": effects,
        "author_id": str(ctx.author.id),
        "author_name": str(ctx.author),
        "guild_id": str(ctx.guild.id) if ctx.guild else "DM",
        "guild_name": _effect_guild_name(ctx),
        "submitted_at": discord.utils.utcnow().isoformat(),
    }
    _save_user_effects()

    embed = discord.Embed(
        title="✅ Effect Submitted",
        color=0x40E0D0,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Name", value=f"`{name}`", inline=True)
    embed.add_field(name="By", value=str(ctx.author), inline=True)
    if ctx.guild:
        embed.add_field(name="Guild", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=True)
    embed.add_field(name="Pipeline", value=f"```{effects[:900]}```", inline=False)
    embed.set_footer(text=f"Global effect — use it anywhere: th/ihtx 1 5 - mp4 {name}")
    await ctx.reply(embed=embed)


_EFFECTLIST_PAGE_SIZE = 10


class _EffectListNavButton(discord.ui.Button):
    def __init__(self, direction: int, invoker_id: int, **kwargs):
        super().__init__(**kwargs)
        self._direction = direction
        self._invoker_id = invoker_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._invoker_id:
            return await interaction.response.send_message(
                "Only the person who ran this command can use these buttons.", ephemeral=True
            )
        view: _EffectListView = self.view  # type: ignore
        view._page = max(0, min(view._page + self._direction, view._total - 1))
        view._update_buttons()
        await interaction.response.edit_message(embed=view._build_embed(), view=view)


class _EffectListView(discord.ui.View):
    def __init__(self, invoker_id: int, entries: list[tuple[str, dict]], search: str = ""):
        super().__init__(timeout=180)
        self._invoker_id = invoker_id
        self._entries = entries
        self._search = search
        self._page = 0
        self._total = max(1, -(-len(entries) // _EFFECTLIST_PAGE_SIZE))

        self._btn_prev = _EffectListNavButton(
            -1, invoker_id, label="◀ Prev",
            style=discord.ButtonStyle.secondary, disabled=True,
        )
        self._btn_next = _EffectListNavButton(
            +1, invoker_id, label="Next ▶",
            style=discord.ButtonStyle.secondary, disabled=(self._total <= 1),
        )
        self.add_item(self._btn_prev)
        self.add_item(self._btn_next)

    def _update_buttons(self) -> None:
        self._btn_prev.disabled = (self._page <= 0)
        self._btn_next.disabled = (self._page >= self._total - 1)

    def _build_embed(self) -> discord.Embed:
        start = self._page * _EFFECTLIST_PAGE_SIZE
        page_entries = self._entries[start : start + _EFFECTLIST_PAGE_SIZE]
        title = f"🎛️ Global User Effects ({len(self._entries)})"
        if self._search:
            title += f"  ·  🔍 {self._search}"
        embed = discord.Embed(
            title=title,
            description="Submissions are shared across all servers the bot is in.",
            color=0x40E0D0,
            timestamp=discord.utils.utcnow(),
        )
        for name, data in page_entries:
            pipeline = data.get("effects", "")
            author   = data.get("author_name", "unknown")
            guild    = data.get("guild_name", "unknown")
            short = pipeline[:80] + ("…" if len(pipeline) > 80 else "")
            embed.add_field(
                name=f"`{name}`  — by {author}  ·  from {guild}",
                value=f"```{short}```",
                inline=False,
            )
        footer_parts = []
        if self._total > 1:
            footer_parts.append(f"Page {self._page + 1}/{self._total}")
        footer_parts.append(f"{len(self._entries)} effects total")
        embed.set_footer(text=" · ".join(footer_parts))
        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


@bot.command(name="listeffects", aliases=["usereffects", "le", "effectlist"])
async def listeffects_command(ctx: commands.Context, *, search: str = ""):
    """List all user-submitted named pipe effects.

    Usage:
      th/listeffects
      th/listeffects gmajor  (search by name)
    """
    if not _USER_EFFECTS:
        await ctx.reply("No user effects submitted yet. Use `th/submiteffect <name> <effects>` to add one.")
        return

    search = search.strip().lower()
    entries = [
        (name, data) for name, data in sorted(_USER_EFFECTS.items())
        if not search or search in name
    ]
    if not entries:
        await ctx.reply(f"No effects found matching `{search}`.")
        return

    view = _EffectListView(ctx.author.id, entries, search)
    await ctx.reply(embed=view._build_embed(), view=view)


@bot.command(name="deleteeffect", aliases=["removeeffect", "deleffect"])
async def deleteeffect_command(ctx: commands.Context, name: str = ""):
    """Delete a user-submitted named pipe effect.

    Owners can delete any effect; other users can only delete their own.

    Usage:
      th/deleteeffect <name>
    """
    name = name.strip().lower()
    if not name:
        await ctx.reply("❌ Provide the effect name to delete. Usage: `th/deleteeffect <name>`")
        return

    if name not in _USER_EFFECTS:
        await ctx.reply(f"❌ No effect named `{name}` found.")
        return

    entry = _USER_EFFECTS[name]
    is_owner = await bot.is_owner(ctx.author)
    is_author = str(ctx.author.id) == entry.get("author_id", "")

    if not is_owner and not is_author:
        await ctx.reply("❌ You can only delete effects you submitted yourself.")
        return

    del _USER_EFFECTS[name]
    _save_user_effects()
    await ctx.message.add_reaction("🗑️")
    await ctx.reply(f"✅ Effect `{name}` deleted.")


@bot.command(name="preview1280", aliases=["p1280", "preview", "pv1280"])
async def preview1280_command(ctx: commands.Context, start: float = 1.85, duration: float = 0.85):
    """Create a 12-segment TV-simulator preview montage from an attached video.

    Usage: th/preview1280 [start_offset] [segment_duration]
    Default: start=1.85, duration=0.85
    """
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**IHTX Preview1280**\n"
            "Attach a video and use `th/preview1280 [start] [duration]`.\n\n"
            "Creates a 12-segment TV-simulator montage with hue shifts, "
            "displacement mapping, and pitch variations.\n\n"
            "Defaults: start=1.85s, duration=0.85s per segment.\n"
            "Example: `th/preview1280 2.0 1.0`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"Preview1280 requires a video file. Got `{suffix}`.")
        return

    start = max(0.0, start)
    duration = max(0.1, min(duration, 10.0))

    status_msg = await ctx.reply(
        f"⚙️ Creating **preview1280** montage (start={start}s, dur={duration}s)... this will take a while."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_p1280.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        # Ensure displacement map is available
        try:
            disp_path = await _ensure_displacement_map(tmpdir)
        except FileNotFoundError as e:
            await status_msg.edit(content=f"❌ {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_preview1280, input_path, output_path, start, duration
        )

        if not ok:
            await status_msg.edit(content=f"❌ Preview1280 failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thp1280.mp4"
        try:
            embed_p1280 = discord.Embed(
                title="Preview 1280 - FFmpeg command originally made by `MWTVE7691` then transported to typescript:",
                description="use whatever sync to audio tag you want, I highly recommend notsobot's tag system (.t sync+)",
                color=11578404,
            )
            await ctx.reply(
                embed=embed_p1280,
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="oppositep1280", aliases=["op1280", "opposite", "opposite1280"])
async def oppositep1280_command(ctx: commands.Context, start: float = 1.85, duration: float = 0.85):
    """Create a 12-segment inverse TV-simulator montage from an attached video.

    The *opposite* of preview1280: all hue shifts are negated and all pitch
    shifts are inverted. Usage: th/oppositep1280 [start_offset] [segment_duration]
    Aliases: th/op1280, th/opposite, th/opposite1280
    Default: start=1.85, duration=0.85
    """
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**IHTX OppositeP1280**\n"
            "Attach a video and use `th/oppositep1280 [start] [duration]`.\n\n"
            "Creates a 12-segment TV-simulator montage with **inverse** hue shifts "
            "and **negated** pitch variations compared to preview1280.\n\n"
            "Defaults: start=1.85s, duration=0.85s per segment.\n"
            "Aliases: `th/op1280`, `th/opposite`, `th/opposite1280`\n"
            "Example: `th/op1280 2.0 1.0`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"OppositeP1280 requires a video file. Got `{suffix}`.")
        return

    start = max(0.0, start)
    duration = max(0.1, min(duration, 10.0))

    status_msg = await ctx.reply(
        f"⚙️ Creating **oppositep1280** montage (start={start}s, dur={duration}s)... this will take a while."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_op1280.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        # Ensure displacement map is available
        try:
            disp_path = await _ensure_displacement_map(tmpdir)
        except FileNotFoundError as e:
            await status_msg.edit(content=f"❌ {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_oppositep1280, input_path, output_path, start, duration
        )

        if not ok:
            await status_msg.edit(content=f"❌ OppositeP1280 failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thop1280.mp4"
        try:
            embed_op1280 = discord.Embed(
                title="Opposite 1280 - Inverse TV-simulator montage",
                description="All hue shifts negated · All pitch shifts inverted vs preview1280",
                color=11578404,
            )
            await ctx.reply(
                embed=embed_op1280,
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")






@bot.command(name="preview1280with640x360resize", aliases=["p1280ff!3", "p1280w16:9r"])
async def preview1280_640x360resize_command(ctx: commands.Context, start: float = 1.85, duration: float = 0.85):
    """Same 12-segment TV-simulator montage as preview1280 but output is locked to 640x360.

    Usage: th/preview1280with640x360resize [start_offset] [segment_duration]
    Aliases: th/p1280ff!3, th/p1280w16:9r
    Default: start=1.85, duration=0.85
    """
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**IHTX Preview1280 (640×360 output)**\n"
            "Attach a video and use `th/preview1280with640x360resize [start] [duration]`.\n\n"
            "Same 12-segment TV-simulator montage pipeline as `th/preview1280`, "
            "but the final output is always rescaled to **640×360** regardless of input resolution.\n\n"
            "Defaults: start=1.85s, duration=0.85s per segment.\n"
            "Aliases: `th/p1280ff!3`, `th/p1280w16:9r`\n"
            "Example: `th/p1280w16:9r 2.0 1.0`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"Preview1280w16:9r requires a video file. Got `{suffix}`.")
        return

    start = max(0.0, start)
    duration = max(0.1, min(duration, 10.0))

    status_msg = await ctx.reply(
        f"⚙️ Creating **preview1280 (640×360)** montage (start={start}s, dur={duration}s)... this will take a while."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_p1280_resized.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        try:
            await _ensure_displacement_map(tmpdir)
        except FileNotFoundError as e:
            await status_msg.edit(content=f"❌ {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_preview1280, input_path, output_path, start, duration, (640, 360)
        )

        if not ok:
            await status_msg.edit(content=f"❌ Preview1280 (640×360) failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thp1280_640x360.mp4"
        try:
            embed_p1280r = discord.Embed(
                title="Preview 1280 (640×360 output) — FFmpeg command originally by `yodelaiihiiho`:",
                description="use whatever sync to audio tag you want, I highly recommend notsobot's tag system (.t sync+)",
                color=11578404,
            )
            await ctx.reply(
                embed=embed_p1280r,
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="preview1280what", aliases=["p1280what", "p1280fev8v2plus"])
async def preview1280what_command(
    ctx: commands.Context,
    start: float = 1.85,
    dur: float = 0.85,
    target_len: float = 5.0,
    use_tempo: str = "false",
):
    """28-segment TV-simulator extended montage (preview1280 FFmpeg Extended v8 v2+).

    Usage: th/preview1280what [start] [dur] [target_len] [use_tempo=true|false]
    Aliases: th/p1280what, th/p1280fev8v2plus
    Defaults: start=1.85, dur=0.85, target_len=5, use_tempo=false
    """
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**IHTX Preview1280what?? — FFmpeg Extended v8 v2+**\n"
            "Attach a video and run `th/preview1280what [start] [dur] [target_len] [true|false]`.\n\n"
            "Creates a **28-segment** TV-simulator montage: 4 full-length segs + 23 half-length + "
            "1 looping long segment. Pass `true` as the 4th arg to enable tempo-stretching.\n\n"
            "Defaults: start=1.85 · dur=0.85 · target_len=5 · use_tempo=false\n"
            "Aliases: `th/p1280what` · `th/p1280fev8v2plus`\n"
            "Example: `th/p1280what 1.85 0.85 5`"
        )
        return

    if isinstance(source, discord.Attachment) and source.size > MAX_FILE_SIZE:
        await ctx.reply(f"❌ File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
        return

    suffix = (
        Path(source.filename).suffix.lower()
        if isinstance(source, discord.Attachment)
        else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    )
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"❌ `preview1280what` requires a video file. Got `{suffix}`.")
        return

    start      = max(0.0, start)
    dur        = max(0.1, min(dur, 10.0))
    target_len = max(0.1, min(target_len, 60.0))
    use_tempo_bool = use_tempo.lower() == "true"

    status_msg = await ctx.reply(
        f"⚙️ Creating **preview1280what??** montage "
        f"(start={start}s, dur={dur}s, target_len={target_len}s, tempo={use_tempo_bool}) "
        f"— 28 segments, this will take a while."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "pwhatextended.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        try:
            await _ensure_displacement_map(tmpdir)
        except FileNotFoundError as e:
            await status_msg.edit(content=f"❌ {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_preview1280what,
            input_path, output_path, start, dur, target_len, use_tempo_bool,
        )

        if not ok:
            await status_msg.edit(content=f"❌ preview1280what failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **preview1280what??** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thp1280what.mp4"
        try:
            embed = discord.Embed(
                title="Preview 1280 FFmpeg Extended v8 v2+ (preview1280what??)",
                description=(
                    f"start={start} · dur={dur} · target_len={target_len} · tempo={use_tempo_bool}\n"
                    "use .t sync+ or any audio-sync tag to sync to audio"
                ),
                color=11578404,
            )
            embed.add_field(name="File Size", value=f"{out_size / (1024*1024):.2f} MB", inline=True)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


_MULTIPITCH_AUDIO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif",
    ".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a", ".opus",
}

_MULTIPITCH_MAX = 100


@bot.command(name="multipitch", aliases=["mp", "multi"])
async def multipitch_command(ctx: commands.Context, *, args: str = ""):
    """Apply multi-voice pitch shifting using Rubber Band R3 (-3 engine).

    Usage:
      th/multipitch -7;12;19          — semicolon-separated semitone values (primary)
      th/multipitch -7|12|19          — pipe-separated also accepted
      th/mp -7;12;19                  — alias
      th/multi -7;12;19               — alias

    Each value creates a separately pitched voice; all voices are mixed together.
    Supports negative and positive semitone values.
    Works on video and audio files. Video stream is preserved unchanged.

    Example: th/multipitch -7;12;19
    """
    if not args:
        await ctx.reply(
            "**IHTX Multipitch** — Rubber Band R3\n"
            "Attach a video or audio file and provide semicolon-separated semitone values.\n\n"
            "Each value creates a pitched voice; all voices are mixed together.\n\n"
            f"Example: `th/multipitch -7;12;19`\n"
            f"Pipe syntax also works: `th/multipitch -7|12|19`\n"
            f"Aliases: `th/mp`, `th/multi`\n"
            f"Max pitches: {_MULTIPITCH_MAX}"
        )
        return

    # Parse: semicolons are the primary separator; fall back to pipes
    raw = args.strip()
    if ";" in raw:
        pitch_values = [v.strip() for v in raw.split(";") if v.strip()]
    elif "|" in raw:
        pitch_values = [v.strip() for v in raw.split("|") if v.strip()]
    else:
        pitch_values = [raw] if raw else []

    if not pitch_values:
        await ctx.reply("No pitch values provided. Example: `th/multipitch -7;12;19`")
        return

    if len(pitch_values) > _MULTIPITCH_MAX:
        await ctx.reply(f"Too many pitches (max {_MULTIPITCH_MAX}). Got {len(pitch_values)}.")
        return

    # Validate each value up-front for a fast, clear error
    for pv in pitch_values:
        try:
            val = float(pv)
            if not math.isfinite(val):
                raise ValueError
        except ValueError:
            await ctx.reply(f"❌ Invalid pitch value: `{pv}` — must be a finite number in semitones.")
            return

    # Resolve attachment: slash commands pass it as a parameter;
    # prefix commands need us to look at the message or referenced message.
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "Attach a video or audio file and provide pitch values.\n"
            "Example: `th/multipitch -7;12;19`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in _MULTIPITCH_AUDIO_EXTS:
        await ctx.reply(
            f"Unsupported file type `{suffix}`.\n"
            f"Supported: video (mp4, mov, avi, mkv, webm, gif) or audio (wav, mp3, flac, ogg, aac, m4a, opus)."
        )
        return

    pitch_str = ";".join(pitch_values)
    status_msg = await ctx.reply(
        f"⚙️ Applying **multipitch** ({pitch_str}) via Rubber Band R3… this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_multipitch.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_multipitch_rb3,
            input_path, output_path, pitch_values
        )

        if not ok:
            await status_msg.edit(content=f"❌ Multipitch failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        safe_pitch_str = pitch_str.replace(";", "_")
        out_filename = f"534gurts_thmultipitch_{safe_pitch_str}.mp4"
        try:
            await ctx.reply(
                content=f"✅ **IHTX multipitch** ({pitch_str}) applied!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="pitchtransition", aliases=["pitchtrans"])
async def pitchtransition_command(ctx: commands.Context, *, args: str = ""):
    """Apply a linear Rubber Band pitch sweep to attached/replied media.

    Usage: th/pitchtransition -5,9
           th/pitchtransition -5,9;5,-9
           th/pitchtransition --pitch "-5,9;5,-9"
    """
    raw = args.strip()
    if raw.lower().startswith("--pitch"):
        raw = raw.split("=", 1)[1].strip() if "=" in raw else raw[len("--pitch"):].strip()
    raw = raw.strip("\"'")
    if not raw:
        await ctx.reply(
            "**IHTX Pitch Transition** — time-varying Rubber Band pitch sweep\n"
            "Attach or reply to audio/video and provide `start,end` semitone pairs.\n"
            "Examples: `th/pitchtransition -5,9` or `th/pitchtransition -5,9;5,-9`"
        )
        return
    source = await _resolve_media_source(ctx)
    if source is None:
        await ctx.reply("Attach or reply to an audio/video file. Example: `th/pitchtransition -5,9`")
        return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else (
        Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    )
    if suffix not in _MULTIPITCH_AUDIO_EXTS:
        await ctx.reply(f"Unsupported file type `{suffix}`. Attach audio or video.")
        return
    status_msg = await ctx.reply(f"⚙️ Applying **pitchtransition** (`{raw}`)…")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(
            tmpdir,
            "output_pitchtransition.mov" if suffix in VIDEO_EXTENSIONS else "output_pitchtransition.m4a",
        )
        try:
            await download_attachment(source, input_path)
            loop = asyncio.get_event_loop()
            ok, err = await loop.run_in_executor(
                None, _run_pitch_transition, input_path, output_path, [raw]
            )
            if not ok:
                await status_msg.edit(content=f"❌ Pitch transition failed:\n```\n{err[-1500:]}\n```")
                return
            if os.path.getsize(output_path) > CATBOX_THRESHOLD:
                await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
                url = await _upload_to_catbox(output_path)
                if url:
                    await ctx.reply(f"✅ Pitch transition done!\n{url}")
                    await status_msg.delete()
                else:
                    await status_msg.edit(content="❌ Output too large and upload failed.")
                return
            await ctx.reply(
                content=f"✅ **IHTX pitchtransition** (`{raw}`) applied!",
                file=discord.File(output_path, filename="534gurts_thpitchtransition.mp4"),
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit(content=f"❌ Pitch transition failed: {str(e)[:1500]}")


@bot.command(name="soundstretchmultipitch", aliases=["ssmp"])
async def soundstretchmultipitch_command(ctx: commands.Context, *, args: str = ""):
    """Apply multi-voice pitch shifting using SoundTouch soundstretch.

    Usage:
      th/ssmp -7;12;19          — semicolon-separated semitone values
      th/ssmp -7|12|19          — pipe-separated also accepted
      th/soundstretchmultipitch -3;5   — full name

    Each value creates a separately pitched voice via soundstretch;
    all voices are mixed together with FFmpeg amix (normalize=0).
    Works on video and audio files. Video stream is preserved unchanged.
    Uses the SoundTouch algorithm (different character from Rubber Band).

    Example: th/ssmp -7;12;19
    """
    if not args:
        await ctx.reply(
            "**IHTX SoundStretch Multipitch** — SoundTouch algorithm\n"
            "Attach a video or audio file and provide semicolon-separated semitone values.\n\n"
            "Each value creates a pitched voice via soundstretch; all voices are mixed together.\n\n"
            "Example: `th/ssmp -7;12;19`\n"
            "Pipe syntax also works: `th/ssmp -7|12|19`\n"
            f"Max pitches: {_MULTIPITCH_MAX}"
        )
        return

    raw = args.strip()
    if ";" in raw:
        pitch_values = [v.strip() for v in raw.split(";") if v.strip()]
    elif "|" in raw:
        pitch_values = [v.strip() for v in raw.split("|") if v.strip()]
    else:
        pitch_values = [raw] if raw else []

    if not pitch_values:
        await ctx.reply("No pitch values provided. Example: `th/ssmp -7;12;19`")
        return

    if len(pitch_values) > _MULTIPITCH_MAX:
        await ctx.reply(f"Too many pitches (max {_MULTIPITCH_MAX}). Got {len(pitch_values)}.")
        return

    for pv in pitch_values:
        try:
            val = float(pv)
            if not math.isfinite(val):
                raise ValueError
        except ValueError:
            await ctx.reply(f"❌ Invalid pitch value: `{pv}` — must be a finite number in semitones.")
            return

    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "Attach a video or audio file and provide pitch values.\n"
            "Example: `th/ssmp -7;12;19`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in _MULTIPITCH_AUDIO_EXTS:
        await ctx.reply(
            f"Unsupported file type `{suffix}`.\n"
            f"Supported: video (mp4, mov, avi, mkv, webm, gif) or audio (wav, mp3, flac, ogg, aac, m4a, opus)."
        )
        return

    pitch_str = ";".join(pitch_values)
    status_msg = await ctx.reply(
        f"⚙️ Applying **soundstretch multipitch** ({pitch_str}) via SoundTouch… this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_ssmp.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_soundstretch_multipitch,
            input_path, output_path, pitch_values
        )

        if not ok:
            await status_msg.edit(content=f"❌ SoundStretch multipitch failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        safe_pitch_str = pitch_str.replace(";", "_")
        out_filename = f"534gurts_thssmp_{safe_pitch_str}.mp4"
        try:
            await ctx.reply(
                content=f"✅ **SoundStretch multipitch** ({pitch_str}) applied!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


# ---------- th/ihtxsap — audio-only IHTX, mirrors th/ihtx iterative model ----------

_IHTXSAP_MAX_REPS    = 1000
_IHTXSAP_MAX_DUR     = 3600.0
_IHTXSAP_MAX_PITCHES = 100

_IHTXSAP_AUDIO_EXTS = {
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".opus", ".wma", ".aiff", ".aif",
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".mts", ".m2ts",
}

_IHTXSAP_USAGE = (
    "**th/ihtxsap** — audio-only version of th/ihtx\n\n"
    "**Usage (positional):** `th/ihtxsap <reps> <duration> <pitches> [style] [volume=N] [reverse=true]`\n"
    "**Usage (keyword):** `th/ihtxsap <reps> <duration> <pitches>` or any order of:\n"
    "  `reps=...` / `repetitions=...` — integer 1–1000\n"
    "  `duration=...` / `dur=...`       — seconds of audio to snip\n"
    "  `pitches=...`                    — semicolon-separated semitone shifts: `-7;5;6`\n"
    "  `pitchstyle=...`                 — `Rubberband R2`, `Rubberband R3`, `Soundtouch`, `Bungee`, `Rubberband Custom`\n"
    "  `volume=...` / `vol=...`         — float volume multiplier (e.g. `volume=8`)\n"
    "  `reverse=true`                   — reverse the audio before pitch processing\n"
    "  `rubberbandcustom=...`           — extra flags for `Rubberband Custom` (e.g. `-2 -window=long`)\n\n"
    "**Examples:**\n"
    "`th/ihtxsap 5 0.7 -7;5;6 \"Rubberband R3\" volume=4`\n"
    "`th/ihtxsap 3 2 -7;5;6 reverse=true`\n"
    "`th/ihtxsap pitchstyle=\"Rubberband Custom\" pitches=-7;8;-4 repetitions=20 duration=0.4 volume=1.3 rubberbandcustom=\"-2 -window=long\"`\n"
    "Attach a video/audio file, reply to one, or have one in recent channel history."
)

_IHTXSAP_STYLE_NAMES = {
    "rubberband_r2":    "Rubberband R2",
    "rubberband_r3":    "Rubberband R3",
    "soundtouch":       "Soundtouch",
    "bungee":           "Bungee",
    "rubberband_custom": "Rubberband Custom",
}

_IHTX_SAP_COLOR       = 0x40E0D0
_IHTX_SAP_FOOTER_ICON = "https://files.catbox.moe/4snvbu.gif"


def _ihtxsap_parse_args(raw: str):
    """Parse prefix args for th/ihtxsap. Returns (opts_dict, error_str).

    Supports both positional and keyword styles, in any order.
    Positional: reps duration pitches [style] [volume=N]
    Keywords:  reps=... duration=... pitches=... pitchstyle=... volume=... rubberbandcustom=...
    """
    tokens: list[str] = []
    cur = ""
    in_quote = False
    q_char = ""
    for ch in raw.strip():
        if in_quote:
            if ch == q_char:
                in_quote = False
                tokens.append(cur)
                cur = ""
            else:
                cur += ch
        elif ch in ('"', "'"):
            in_quote = True
            q_char = ch
        elif ch in (" ", "\t"):
            if cur:
                tokens.append(cur)
                cur = ""
        else:
            cur += ch
    if cur:
        tokens.append(cur)

    if not tokens:
        return None, f"❌ No arguments.\n\n{_IHTXSAP_USAGE}"

    def _split_key_val(tok: str) -> tuple[str, str | None]:
        """Return (key, value) if token is key=value, else (token, None)."""
        if "=" in tok and not tok.startswith("="):
            key, value = tok.split("=", 1)
            return key.lower(), value
        return tok, None

    def _parse_pitches(val: str) -> list[float] | None:
        pitches: list[float] = []
        for p in val.split(";"):
            p = p.strip()
            if not p:
                continue
            try:
                val = float(p)
                if not math.isfinite(val) or abs(val) > 120:
                    raise ValueError
            except ValueError:
                return None
            pitches.append(val)
        return pitches

    def _match_style(s: str) -> str | None:
        s = s.lower().replace(" ", "_").replace("-", "_")
        if "rubberband" in s and "custom" in s:
            return "rubberband_custom"
        if "r3" in s and "rubberband" in s:
            return "rubberband_r3"
        if "r2" in s and "rubberband" in s:
            return "rubberband_r2"
        if "rubberband" in s:
            # just "rubberband" -> default to R2
            return "rubberband_r2"
        if "soundtouch" in s:
            return "soundtouch"
        if "bungee" in s:
            return "bungee"
        return None

    # Defaults
    reps: int | None = None
    duration: float | None = None
    pitches: list[float] | None = None
    style = "rubberband_r2"
    volume = 1.0
    rb_custom = ""
    reverse = False

    keyword_only = False
    positional_idx = 0

    for tok in tokens:
        key, value = _split_key_val(tok)

        if value is not None:
            keyword_only = True
            if key in ("reps", "repetitions"):
                try:
                    reps = int(value)
                    if not (1 <= reps <= _IHTXSAP_MAX_REPS):
                        raise ValueError
                except ValueError:
                    return None, f"❌ `reps` must be an integer 1–{_IHTXSAP_MAX_REPS} (got `{value}`)."
            elif key in ("duration", "dur"):
                try:
                    duration = float(value)
                    if not (0.01 <= duration <= _IHTXSAP_MAX_DUR):
                        raise ValueError
                except ValueError:
                    return None, f"❌ `duration` must be a positive number of seconds (got `{value}`)."
            elif key == "pitches":
                pitches = _parse_pitches(value)
                if pitches is None or not pitches:
                    return None, f"❌ Invalid pitches `{value}` — must be semicolon-separated numbers within ±120 semitones."
                if len(pitches) > _IHTXSAP_MAX_PITCHES:
                    return None, f"❌ Too many pitch values (max {_IHTXSAP_MAX_PITCHES})."
            elif key in ("pitchstyle", "style"):
                matched = _match_style(value)
                if matched is None:
                    return None, f"❌ Unknown pitchstyle `{value}`. Options: `Rubberband R2`, `Rubberband R3`, `Soundtouch`, `Bungee`, `Rubberband Custom`."
                style = matched
            elif key in ("volume", "vol"):
                try:
                    volume = float(value)
                    if not (0 < volume <= 100):
                        raise ValueError
                except ValueError:
                    return None, f"❌ `volume` must be a positive float ≤ 100 (got `{value}`)."
            elif key in ("rubberbandcustom", "rbcustom"):
                rb_custom = value.strip()
            elif key in ("reverse", "rev"):
                reverse = value.lower() in ("1", "true", "t", "y", "yes", "+", "on")
            else:
                return None, f"❌ Unknown argument `{tok}`.\n\n{_IHTXSAP_USAGE}"
        else:
            # Positional parsing
            if positional_idx == 0:
                try:
                    reps = int(tok)
                    if not (1 <= reps <= _IHTXSAP_MAX_REPS):
                        raise ValueError
                except ValueError:
                    return None, f"❌ `reps` must be an integer 1–{_IHTXSAP_MAX_REPS} (got `{tok}`)."
                positional_idx += 1
            elif positional_idx == 1:
                try:
                    duration = float(tok)
                    if not (0.01 <= duration <= _IHTXSAP_MAX_DUR):
                        raise ValueError
                except ValueError:
                    return None, f"❌ `duration` must be a positive number of seconds (got `{tok}`)."
                positional_idx += 1
            elif positional_idx == 2:
                pitches = _parse_pitches(tok)
                if pitches is None or not pitches:
                    return None, f"❌ Invalid pitches `{tok}` — must be semicolon-separated numbers within ±120 semitones."
                if len(pitches) > _IHTXSAP_MAX_PITCHES:
                    return None, f"❌ Too many pitch values (max {_IHTXSAP_MAX_PITCHES})."
                positional_idx += 1
            elif positional_idx == 3:
                matched = _match_style(tok)
                if matched is None:
                    return None, f"❌ Unknown style `{tok}`. Options: `Rubberband R2`, `Rubberband R3`, `Soundtouch`, `Bungee`, `Rubberband Custom`."
                style = matched
                positional_idx += 1
            elif tok.lower().startswith("volume="):
                try:
                    volume = float(tok[7:])
                    if not (0 < volume <= 100):
                        raise ValueError
                except ValueError:
                    return None, f"❌ `volume` must be a positive float ≤ 100 (got `{tok[7:]}`)."
            else:
                return None, f"❌ Unexpected argument `{tok}`.\n\n{_IHTXSAP_USAGE}"

    if reps is None:
        return None, f"❌ Missing `reps`.\n\n{_IHTXSAP_USAGE}"
    if duration is None:
        return None, f"❌ Missing `duration`.\n\n{_IHTXSAP_USAGE}"
    if pitches is None:
        return None, f"❌ Missing `pitches`.\n\n{_IHTXSAP_USAGE}"

    if style == "rubberband_custom" and not rb_custom:
        return None, "❌ `Rubberband Custom` requires `rubberbandcustom=...` flags (e.g. `-2 -window=long`)."

    return {
        "reps": reps,
        "duration": duration,
        "pitches": pitches,
        "style": style,
        "volume": volume,
        "rubberband_custom": rb_custom,
        "reverse": reverse,
    }, None


def _ihtxsap_amix(layer_paths: list[str], output: str) -> tuple[bool, str]:
    """amix N WAV layers → output WAV. Returns (ok, err)."""
    if len(layer_paths) == 1:
        import shutil as _sh
        _sh.copy2(layer_paths[0], output)
        return True, ""
    cmd = ["ffmpeg", "-y"]
    for lp in layer_paths:
        cmd += ["-i", lp]
    fc = f"amix=inputs={len(layer_paths)}:duration=longest:normalize=0"
    cmd += [
        "-filter_complex", fc,
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
        output,
    ]
    return _run_ffmpeg_raw(cmd, timeout=180)


def _run_ihtxsap(
    input_path: str,
    output_path: str,
    reps: int,
    duration: float,
    pitches: list[float],
    style: str,
    volume: float,
    rubberband_custom: str = "",
    reverse: bool = False,
) -> tuple[bool, str]:
    """
    Audio IHTX pipeline — mirrors th/ihtx's iterative repetition model exactly.

    Same structure as _run_ihtxcustom_workflow / _run_ihtx_tagscript_workflow:
      1. Extract first `duration` seconds as 16-bit PCM WAV (strip all video).
      2. Apply pitch `reps` times iteratively — each output is the input for the next:
           base.wav → apply_pitch → 1.wav
           1.wav    → apply_pitch → 2.wav
           ...
           (N-1).wav → apply_pitch → N.wav
      3. Concatenate 1.wav … N.wav end-to-end (same concat logic as th/ihtx).
      4. Optional volume adjustment.
      5. Encode → MP3 (libmp3lame -q:a 2).
    """
    pitch_arg = ",".join(
        str(int(s)) if s == int(s) else str(s) for s in pitches
    )

    with tempfile.TemporaryDirectory() as tmpdir:

        def wav(n: int) -> str:
            return os.path.join(tmpdir, f"{n}.wav")

        # ── 1. Extract audio snippet (strip all video, same as th/ihtx base step) ──
        base_wav = os.path.join(tmpdir, "base.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", input_path,
            "-t", str(duration), "-vn",
            "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            base_wav,
        ], timeout=120)
        if not ok:
            return False, f"Audio extraction failed: {err}"

        # ── 2. apply_pitch: one iteration (src → dst WAV) ─────────────────────
        # Tier 1 (R2/R3/Bungee): fileaa binary — all pitches in one call.
        #   R2:     fileaa input output pitches --rubberband-args "-2"
        #   R3:     fileaa input output pitches --rubberband-args "-3"
        #   Bungee: fileaa input output pitches --bungee
        # Tier 2 (R2/R3 fallback): rubberband CLI per pitch + amix.
        # Tier 2 (Bungee fallback): FFmpeg asetrate per pitch + amix.
        # SoundTouch: soundstretch per pitch + amix (no fileaa equivalent).
        rb_bin = shutil.which("rubberband")
        st_bin = shutil.which("soundstretch")
        _rep_ctr = [0]  # mutable counter for unique per-rep temp filenames

        def apply_pitch(src: str, dst: str) -> tuple[bool, str]:
            _rep_ctr[0] += 1
            rep = _rep_ctr[0]

            # ── Rubberband R2 ──────────────────────────────────────────────────
            if style == "rubberband_r2":
                # Tier 1: rubberband -2 -p<st> -t1 per voice → amix
                if rb_bin:
                    layer_paths = []
                    rb2_ok = True
                    for i, st in enumerate(pitches):
                        lp = os.path.join(tmpdir, f"voice_{rep}_{i}.wav")
                        res = subprocess.run(
                            [rb_bin, "-2", f"-p{st:+.4f}", "-t1", src, lp],
                            capture_output=True, text=True, timeout=300,
                        )
                        if res.returncode != 0:
                            print(
                                f"[ihtxsap] rubberband R2 pitch {st:+}st failed: "
                                f"{res.stderr[-200:]} — trying fileaa fallback"
                            )
                            rb2_ok = False
                            break
                        layer_paths.append(lp)
                    if rb2_ok and layer_paths:
                        return _ihtxsap_amix(layer_paths, dst)
                else:
                    print("[ihtxsap] rubberband CLI not found — trying fileaa R2 fallback")

                # Tier 2: fileaa --rubberband-args "-2"
                if _ensure_multipitch_bin():
                    res = subprocess.run(
                        [_MULTIPITCH_BIN, src, dst, pitch_arg,
                         "--rubberband-args", "-2"],
                        capture_output=True, timeout=300,
                    )
                    if res.returncode == 0:
                        return True, ""
                    stderr_note = res.stderr.decode(errors="replace")[-400:]
                    print(f"[ihtxsap] fileaa R2 failed (exit {res.returncode}): {stderr_note}")

                return False, "❌ rubberband R2 failed (all tiers exhausted)"

            # ── Rubberband R3 ──────────────────────────────────────────────────
            elif style == "rubberband_r3":
                # Tier 1: rubberband -3 -p<st> -t1 per voice → amix
                if rb_bin:
                    layer_paths = []
                    rb3_ok = True
                    for i, st in enumerate(pitches):
                        lp = os.path.join(tmpdir, f"voice_{rep}_{i}.wav")
                        res = subprocess.run(
                            [rb_bin, "-3", f"-p{st:+.4f}", "-t1", src, lp],
                            capture_output=True, text=True, timeout=300,
                        )
                        if res.returncode != 0:
                            print(
                                f"[ihtxsap] rubberband R3 pitch {st:+}st failed: "
                                f"{res.stderr[-200:]} — trying fileaa fallback"
                            )
                            rb3_ok = False
                            break
                        layer_paths.append(lp)
                    if rb3_ok and layer_paths:
                        return _ihtxsap_amix(layer_paths, dst)
                else:
                    print("[ihtxsap] rubberband CLI not found — trying fileaa R3 fallback")

                # Tier 2: fileaa --rubberband-args "-3"
                if _ensure_multipitch_bin():
                    res = subprocess.run(
                        [_MULTIPITCH_BIN, src, dst, pitch_arg,
                         "--rubberband-args", "-3"],
                        capture_output=True, timeout=300,
                    )
                    if res.returncode == 0:
                        return True, ""
                    stderr_note = res.stderr.decode(errors="replace")[-400:]
                    print(f"[ihtxsap] fileaa R3 failed (exit {res.returncode}): {stderr_note}")

                return False, "❌ rubberband R3 failed (all tiers exhausted)"

            # ── Rubberband Custom ──────────────────────────────────────────────
            elif style == "rubberband_custom":
                if not rb_bin:
                    return False, "rubberband binary not found — needed for Rubberband Custom"
                if not rubberband_custom:
                    return False, "❌ Rubberband Custom requires `rubberbandcustom=...` flags"

                # Split user-supplied flags; allow quoted input already unwrapped by tokenizer
                custom_flags = shlex.split(rubberband_custom)
                layer_paths = []
                for i, st in enumerate(pitches):
                    lp = os.path.join(tmpdir, f"voice_{rep}_{i}.wav")
                    cmd = [rb_bin] + custom_flags + [f"-p{st:+.4f}", "-t1", src, lp]
                    res = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=300,
                    )
                    if res.returncode != 0:
                        return False, (
                            f"rubberband custom pitch {st:+}st failed:\n"
                            f"{res.stderr[-400:]}"
                        )
                    layer_paths.append(lp)
                return _ihtxsap_amix(layer_paths, dst)

            # ── SoundTouch ─────────────────────────────────────────────────────
            elif style == "soundtouch":
                if not st_bin:
                    return False, "soundstretch binary not found — install soundtouch package"
                layer_paths = []
                for i, st in enumerate(pitches):
                    lp = os.path.join(tmpdir, f"voice_{rep}_{i}.wav")
                    res = subprocess.run(
                        [st_bin, src, lp, f"-pitch={st}"],
                        capture_output=True, text=True, timeout=120,
                    )
                    if res.returncode != 0:
                        return False, f"soundstretch pitch {st:+}st failed:\n{res.stderr[-400:]}"
                    layer_paths.append(lp)
                return _ihtxsap_amix(layer_paths, dst)

            # ── Bungee ─────────────────────────────────────────────────────────
            else:
                # Tier 1: multipitch --bungee --no-normalize (all pitches, single call)
                if _ensure_multipitch_bin():
                    res = subprocess.run(
                        [_MULTIPITCH_BIN, src, dst, pitch_arg, "--bungee", "--no-normalize"],
                        capture_output=True, timeout=300,
                    )
                    if res.returncode == 0:
                        return True, ""
                    stderr_note = res.stderr.decode(errors="replace")[-400:]
                    print(f"[ihtxsap] multipitch --bungee failed (exit {res.returncode}): {stderr_note}")

                # Tier 2: FFmpeg asetrate per pitch + amix
                layer_paths = []
                for i, st in enumerate(pitches):
                    lp = os.path.join(tmpdir, f"voice_{rep}_{i}.wav")
                    ratio = math.pow(2, st / 12)
                    af = (
                        f"asetrate=44100*{ratio:.9f},"
                        f"aresample=44100,"
                        f"aphaser=type=t:speed=0.5:decay=0.4"
                    )
                    ok2, err2 = _run_ffmpeg_raw([
                        "ffmpeg", "-y", "-i", src, "-af", af,
                        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", lp,
                    ], timeout=120)
                    if not ok2:
                        return False, f"bungee (asetrate) pitch {st:+}st failed:\n{err2}"
                    layer_paths.append(lp)
                return _ihtxsap_amix(layer_paths, dst)

        # ── 3. Iterate reps times — each output feeds into the next ───────────
        #    Mirrors: input → 1.ts → 2.ts → … → N.ts in th/ihtx
        #    With reverse=True: before each pitch step, reverse the previous
        #    output; odd reps use areverse, even reps add dynaudnorm so the
        #    signal "bounces" back to the forward direction.
        segments: list[str] = []
        prev = base_wav
        for i in range(1, reps + 1):
            seg = wav(i)
            pitch_input = prev
            if reverse:
                # Odd: areverse only; even: areverse + dynaudnorm (normalize
                # after the double-reversal brings audio back to forward).
                af = "areverse,dynaudnorm" if i % 2 == 0 else "areverse"
                rev_in = os.path.join(tmpdir, f"rev_in_{i}.wav")
                ok2, err2 = _run_ffmpeg_raw([
                    "ffmpeg", "-y", "-i", prev,
                    "-af", af,
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    rev_in,
                ], timeout=120)
                if not ok2:
                    return False, f"Rep {i} pre-reversal failed: {err2}"
                pitch_input = rev_in
            ok, err = apply_pitch(pitch_input, seg)
            if not ok:
                return False, f"Rep {i}/{reps} failed: {err}"
            segments.append(seg)
            prev = seg

        # ── 4. Concatenate all segments (mirrors th/ihtx concat of 1.ts…N.ts) ─
        if len(segments) == 1:
            final_wav = segments[0]
        else:
            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w") as f:
                for seg in segments:
                    f.write(f"file '{seg}'\n")
            concat_wav = os.path.join(tmpdir, "concat.wav")
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_list,
                "-c", "copy", concat_wav,
            ], timeout=300)
            if not ok:
                return False, f"Concat failed: {err}"
            final_wav = concat_wav

        # ── 5. Volume adjustment ───────────────────────────────────────────────
        if volume != 1.0:
            vol_wav = os.path.join(tmpdir, "vol.wav")
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y", "-i", final_wav,
                "-af", f"volume={volume:.6f}",
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                vol_wav,
            ], timeout=120)
            if not ok:
                return False, f"Volume adjustment failed: {err}"
            final_wav = vol_wav

        # ── 6. Encode to MP3 ──────────────────────────────────────────────────
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", final_wav,
            "-acodec", "libmp3lame", "-q:a", "2",
            output_path,
        ], timeout=180)
        if not ok:
            return False, f"MP3 encoding failed: {err}"

    return True, ""


@bot.command(name="ihtxsap", aliases=["sap"])
async def ihtxsap_command(ctx: commands.Context, *, args: str = "") -> None:
    """Audio-only IHTX — iterative pitch reps, concat, output MP3.

    Same model as th/ihtx: each rep applies pitch to the previous output, all reps
    are concatenated. Output is always a pure MP3, no video.

    Usage: th/ihtxsap <reps> <duration> <pitches> [style] [volume=N]
            th/ihtxsap <keyword args...> (e.g. pitchstyle=... pitches=...)
    Example: th/ihtxsap 5 0.7 -7;5;6 "Rubberband R3" volume=4
             th/ihtxsap pitchstyle="Rubberband Custom" pitches=-7;8;-4 repetitions=20 duration=0.4 volume=1.3 rubberbandcustom="-2 -window=long"
    """
    if not args:
        await ctx.reply(_IHTXSAP_USAGE)
        return

    opts, err_str = _ihtxsap_parse_args(args)
    if err_str:
        await ctx.reply(err_str)
        return

    # ── Resolve media source (direct → reply → channel history) ────────────
    source = None
    if ctx.message.attachments:
        source = ctx.message.attachments[0]
    elif ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                source = ref.attachments[0]
            else:
                for tok in ref.content.split():
                    if tok.startswith(("http://", "https://")):
                        source = tok
                        break
        except Exception:
            pass
    if source is None:
        try:
            async for msg in ctx.channel.history(limit=30, before=ctx.message):
                if msg.attachments:
                    ext = Path(msg.attachments[0].filename).suffix.lower()
                    if ext in _IHTXSAP_AUDIO_EXTS:
                        source = msg.attachments[0]
                        break
        except Exception:
            pass

    if not source:
        await ctx.reply(
            f"❌ No audio/video file found. Attach one, reply to one, or have one in recent history.\n\n{_IHTXSAP_USAGE}"
        )
        return

    if isinstance(source, discord.Attachment):
        suffix = Path(source.filename).suffix.lower()
    else:
        suffix = Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in _IHTXSAP_AUDIO_EXTS:
        await ctx.reply(f"❌ Unsupported file type `{suffix}`. Attach an audio or video file.")
        return
    if isinstance(source, discord.Attachment) and source.size > MAX_FILE_SIZE:
        await ctx.reply(f"❌ File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB).")
        return

    # ── Live embed (same pattern as ihtxgen in economy_cog.py) ───────────────
    style_label = _IHTXSAP_STYLE_NAMES[opts["style"]]
    if opts["style"] == "rubberband_custom":
        style_label += f" ({opts['rubberband_custom']})"
    pitch_str   = ";".join((f"+{p}" if p >= 0 else str(p)) for p in opts["pitches"])
    vol_part    = f" · vol ×{opts['volume']}" if opts["volume"] != 1.0 else ""

    try:
        from bot.economy_cog import WEATHER_FUN_FACTS as _WFF
        _fun_fact = random.choice(_WFF)
    except Exception:
        _fun_fact = "FFmpeg can mix dozens of audio streams in a single filter graph pass."

    _start_time  = time.monotonic()
    _user_tag    = str(ctx.author)
    _avatar_url  = ctx.author.display_avatar.url

    def _make_embed(color: int = _IHTX_SAP_COLOR) -> discord.Embed:
        e = discord.Embed(color=color, timestamp=discord.utils.utcnow())
        e.set_author(name=_user_tag, icon_url=_avatar_url)
        e.set_footer(text="IHTX-Sap Audio Processor", icon_url=_IHTX_SAP_FOOTER_ICON)
        return e

    loading_embed = _make_embed()
    loading_embed.add_field(name="Status:", value="⏳ Downloading and processing…", inline=False)
    loading_embed.add_field(name="🌤️ Weather Fact:", value=_fun_fact, inline=False)
    status_msg = await ctx.reply(embed=loading_embed, mention_author=False)

    async def _update(status: str, color: int = _IHTX_SAP_COLOR) -> None:
        e = _make_embed(color)
        e.add_field(name="Status:", value=status, inline=False)
        if color == _IHTX_SAP_COLOR:
            e.add_field(name="🌤️ Weather Fact:", value=_fun_fact, inline=False)
        try:
            await status_msg.edit(embed=e)
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "ihtxsap.mp3")

        # Download
        try:
            await _update("⬇️ Downloading media…")
            await download_attachment(source, input_path)
        except Exception as exc:
            await _update(f"❌ Download failed: `{exc}`", 0xED4245)
            return

        # Process with elapsed ticker (mirrors ihtxgen's _tick loop)
        loop = asyncio.get_event_loop()
        _done_evt = asyncio.Event()

        async def _tick() -> None:
            while not _done_evt.is_set():
                elapsed = int(time.monotonic() - _start_time)
                await _update(
                    f"🔧 Running IHTX-Sap — `{opts['reps']}×` · pitch `{pitch_str}` · {style_label}"
                    f"{' · reversed' if opts.get('reverse') else ''}…\n"
                    f"⏱️ **{elapsed}s elapsed**"
                )
                try:
                    await asyncio.wait_for(_done_evt.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    pass

        _tick_task = asyncio.create_task(_tick())
        try:
            ok, err = await loop.run_in_executor(
                None, _run_ihtxsap,
                input_path, output_path,
                opts["reps"], opts["duration"],
                opts["pitches"], opts["style"], opts["volume"],
                opts.get("rubberband_custom", ""),
                opts.get("reverse", False),
            )
        finally:
            _done_evt.set()
            _tick_task.cancel()
            try:
                await _tick_task
            except asyncio.CancelledError:
                pass

        if not ok:
            await _update(f"❌ IHTX-Sap failed:\n```\n{err[-1200:]}\n```", 0x40E0D0)
            return

        out_size    = os.path.getsize(output_path)
        _elapsed    = time.monotonic() - _start_time
        _size_str   = (
            f"{out_size / 1024 / 1024:.2f} MB"
            if out_size >= 1024 * 1024
            else f"{out_size / 1024:.2f} KB"
        )

        # Catbox fallback if >25 MB (same as ihtxgen)
        if out_size > CATBOX_THRESHOLD:
            await _update("⬆️ Output exceeds 10 MB — uploading to Catbox…")
            catbox_url = await _upload_to_catbox(output_path)
            if catbox_url:
                result_embed = _make_embed()
                result_embed.add_field(name="Pitches:", value=f"`{pitch_str}`", inline=True)
                result_embed.add_field(name="Reps:", value=f"`{opts['reps']}×`", inline=True)
                result_embed.add_field(name="Style:", value=style_label + vol_part, inline=True)
                result_embed.add_field(
                    name="File Info:",
                    value=(
                        f"{_size_str} (Catbox), took {_elapsed:.2f}s\n"
                        f"🔗 [Download]({catbox_url})\n`{catbox_url}`"
                    ),
                    inline=False,
                )
                await status_msg.edit(embed=result_embed)
            else:
                await _update(
                    "❌ Output too large for Discord (>25 MB) and Catbox upload failed.", 0xED4245
                )
            return

        safe_pitches = pitch_str.replace("+", "p").replace("-", "n").replace(";", "_")
        out_name     = f"534gurts_thihtxsap_{safe_pitches}_{opts['reps']}x.mp3"
        result_embed = _make_embed()
        result_embed.add_field(name="Pitches:", value=f"`{pitch_str}`", inline=True)
        result_embed.add_field(name="Reps:", value=f"`{opts['reps']}×`", inline=True)
        result_embed.add_field(name="Style:", value=style_label + vol_part, inline=True)
        result_embed.add_field(
            name="File Info:", value=f"{_size_str}, took {_elapsed:.2f}s", inline=False
        )

        try:
            await status_msg.edit(
                embed=result_embed,
                attachments=[discord.File(output_path, filename=out_name)],
            )
        except discord.HTTPException:
            await status_msg.edit(embed=result_embed)
            await ctx.send(file=discord.File(output_path, filename=out_name))


# ---------- th/mpb / th/multipitch_bungee — standalone bungee pitch shifter ----------

_MPB_USAGE = (
    "**th/mpb** — Bungee pitch-shifter pipeline with video passthrough\n\n"
    "**Usage:** `th/mpb [pitches]`  (aliases: `th/bmp` `th/multipitchbungee` `th/bungeemultipitch`)\n\n"
    "  `pitches` — pipe/semicolon/comma-separated semitone values (default: `1.5`)\n\n"
    "**Examples:**\n"
    "  `th/mpb -7|7` — two-voice bungee at −7 and +7 semitones\n"
    "  `th/mpb 1.5` — single voice at +1.5 semitones\n\n"
    "Attach a video/audio file, reply to one, or have one in recent channel history."
)


@bot.command(name="multipitch_bungee", aliases=["mpb", "bmp", "multipitchbungee", "bungeemultipitch"])
async def mpb_command(ctx: commands.Context, *, args: str = "") -> None:
    """Standalone bungee pitch-shifter. Usage: th/mpb [pitches]"""
    pitch_str = args.strip() or "1.5"
    pitch_values = [p.strip() for p in re.split(r"[;|,\s]+", pitch_str) if p.strip()]

    if not pitch_values:
        await ctx.reply(_MPB_USAGE)
        return

    try:
        [float(v) for v in pitch_values]
    except ValueError:
        await ctx.reply(f"❌ Invalid pitch value.\n\n{_MPB_USAGE}")
        return

    source = await _resolve_media_source(ctx)
    if source is None:
        await ctx.reply(
            "❌ No audio/video file found. Attach one, reply to one, or have one in recent channel history.\n\n"
            + _MPB_USAGE
        )
        return

    pitch_display = " | ".join(pitch_values)
    status_msg = await ctx.reply(f"⏳ Multipitch Bungee — `{pitch_display}` …")

    async def _update(text: str) -> None:
        try:
            await status_msg.edit(content=text)
        except Exception:
            pass

    if isinstance(source, discord.Attachment):
        ext = source.filename.rsplit(".", 1)[-1].lower()
    else:
        ext = source.rsplit(".", 1)[-1].split("?")[0].lower() or "mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input.{ext}")
        output_path = os.path.join(tmpdir, "mpb_output.mp4")

        await _update("⏳ Downloading…")
        try:
            await download_attachment(source, input_path)
        except Exception as exc:
            await _update(f"❌ Download failed: `{exc}`")
            return

        await _update(f"⏳ Running bungee pitch processor (`{pitch_display}`)…")
        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_multipitch_bungee, input_path, output_path, pitch_values
        )
        if not ok:
            await _update(f"❌ Bungee failed: {err}")
            return

        if not os.path.exists(output_path):
            await _update("❌ Output file was not created.")
            return

        out_size = os.path.getsize(output_path)
        safe = pitch_str.replace("+", "p").replace("-", "n").replace("|", "_").replace(";", "_").replace(",", "_")
        out_name = f"534gurts_thmpb_{safe}.mp4"

        if out_size > CATBOX_THRESHOLD:
            await _update("⬆️ Output exceeds upload limit — uploading to Catbox…")
            cat_url = await _upload_to_catbox(output_path)
            if cat_url:
                await _update(f"✅ Multipitch Bungee done! `{pitch_display}`\n🔗 {cat_url}")
            else:
                await _update("❌ Output too large for Discord and Catbox upload failed.")
        else:
            await status_msg.edit(
                content=f"✅ Multipitch Bungee done! `{pitch_display}`",
                attachments=[discord.File(output_path, filename=out_name)],
            )


# ---------- th/ffmpeg — raw FFmpeg command ----------

@bot.command(name="ffmpeg")
async def ffmpeg_raw_command(ctx: commands.Context, *, args: str = ""):
    """Run raw FFmpeg on an attached file.

    Args go between -i <input> and <output>. Output filename matches input.

    Usage:
      th/ffmpeg -vf negate
      th/ffmpeg -vf hue=h=180 -c:a copy
      th/ffmpeg -af volume=2.0
    """
    if not args:
        await ctx.reply(
            "**th/ffmpeg** — Run raw FFmpeg on an attachment.\n"
            "Args are inserted between `-i <input>` and `<output>`.\n\n"
            "**Usage:** `th/ffmpeg <ffmpeg args>`\n"
            "**Examples:**\n"
            "`th/ffmpeg -vf negate`\n"
            "`th/ffmpeg -vf hue=h=180 -c:a copy`\n"
            "`th/ffmpeg -af volume=2.0`"
        )
        return

    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply("❌ Attach a file to use `th/ffmpeg`.")
        return

    if source.size > MAX_FILE_SIZE:
        await ctx.reply(f"❌ File too large (max 25 MB).")
        return

    args_display = args if len(args) <= 80 else args[:79] + "…"
    status_msg = await ctx.reply(f"⏳ Processing `{args_display}`…")

    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        suffix = Path(source.filename).suffix.lower()
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"534gurts_thffmpeg{suffix}")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        # Substitute media variables ($sr $fr $f $d $vd $w $h $fc $T *T) in args.
        if any(v in args for v in ("$sr", "$fr", "$f", "$d", "$vd", "$w", "$h", "$fc", "$T", "*T")):
            meta = await _gather_media_metadata(input_path)

            def _eval_fps(raw: str) -> str:
                try:
                    if "/" in raw:
                        n, d = raw.split("/", 1)
                        return f"{int(n) / int(d):.10g}"
                    return f"{float(raw):.10g}"
                except Exception:
                    return raw

            _fps_str = _eval_fps(meta.get("frameRate", "N/A"))
            _raw_vd = meta.get("duration", "N/A")
            try:
                _T_expr = f"(t/{float(_raw_vd):.10g})" if _raw_vd != "N/A" else "t"
            except (ValueError, TypeError):
                _T_expr = "t"
            _var_map = [
                ("$sr",  meta.get("sampleRate", "N/A")),
                ("$fr",  _fps_str),
                ("$f",   _fps_str),
                ("$vd",  _raw_vd),
                ("$d",   _raw_vd),
                ("$w",   meta.get("width", "N/A")),
                ("$h",   meta.get("height", "N/A")),
                ("$fc",  meta.get("frameCount", "N/A")),
                ("$T",   _T_expr),
                ("*T",   _T_expr),
            ]
            for _var, _val in _var_map:
                if _val and _val != "N/A":
                    args = re.sub(re.escape(_var) + r'(?![a-zA-Z0-9_])', _val, args) if _var in ("$T", "*T") else args.replace(_var, _val)

        try:
            user_args = shlex.split(args)
        except ValueError as e:
            await status_msg.edit(content=f"❌ Invalid ffmpeg args: {e}")
            return

        cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
        ] + user_args + [output_path]

        loop = asyncio.get_event_loop()
        ok, err_log = await loop.run_in_executor(None, _run_ffmpeg_raw, cmd, 180)

        elapsed = int(time.time() - start_time)

        if not ok:
            err_block = f"\n```\n{err_log.strip()[-1200:]}\n```" if err_log and err_log.strip() else ""
            await status_msg.edit(content=f"❌ FFmpeg failed (took {elapsed}s){err_block}")
            return

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            await status_msg.edit(content="❌ FFmpeg produced no output file.")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        footer_parts = []
        if err_log and err_log.strip():
            footer_parts.append(f"-# Error log:\n```\n{err_log.strip()[-800:]}\n```")
        footer_parts.append(f"-# Took: {elapsed} seconds")
        footer = "\n".join(footer_parts)

        try:
            await ctx.reply(
                content=footer,
                file=discord.File(output_path, filename=os.path.basename(output_path)),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Upload failed: {e}")


# ---------- th/ffmpegprocess — FFmpeg with ffprobe metadata inspection ----------

async def _run_ffprobe_field(args: list) -> str:
    """Run a single ffprobe query and return stripped stdout, or 'N/A' on failure."""
    try:
        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["ffprobe"] + args,
                capture_output=True, text=True, timeout=10
            )
        )
        return proc.stdout.strip() or "N/A"
    except Exception:
        return "N/A"


async def _gather_media_metadata(file_path: str) -> dict:
    """Gather video/audio metadata using ffprobe (all fields in parallel)."""
    tasks = {
        "sampleRate": _run_ffprobe_field(["-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate",
            "-of", "default=nokey=1:noprint_wrappers=1", file_path]),
        "frameRate": _run_ffprobe_field(["-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=nokey=1:noprint_wrappers=1", file_path]),
        "duration": _run_ffprobe_field(["-i", file_path,
            "-show_entries", "format=duration",
            "-v", "quiet", "-of", "csv=p=0"]),
        "width": _run_ffprobe_field(["-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width",
            "-of", "default=nw=1:nk=1", file_path]),
        "height": _run_ffprobe_field(["-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=height",
            "-of", "default=nw=1:nk=1", file_path]),
        "frameCount": _run_ffprobe_field(["-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames",
            "-of", "default=nokey=1:noprint_wrappers=1", file_path]),
    }
    results = {}
    for key, coro in tasks.items():
        results[key] = await coro
    return results


@bot.command(name="ffmpegprocess", aliases=["fmp"])
async def ffmpeg_process_command(ctx: commands.Context, *, args: str = ""):
    """Run FFmpeg on an attachment and inspect the input with ffprobe.

    Gathers sample rate, frame rate, duration, resolution, and frame count
    before processing, then shows them in the response footer.

    Args go between -i <input> and <output>. Output filename matches input.

    Usage:
      th/ffmpegprocess -vf scale=1280:-1 -c:v libx264 -crf 23
      th/ffmpegprocess -vf negate
      th/ffmpegprocess -af volume=2.0
    """
    if not args:
        await ctx.reply(
            "**th/ffmpegprocess** — Run FFmpeg on an attachment with ffprobe metadata inspection.\n"
            "Args are inserted between `-i <input>` and `<output>`.\n\n"
            "**Usage:** `th/ffmpegprocess <ffmpeg args>`  *(alias: fmp)*\n"
            "**Examples:**\n"
            "`th/ffmpegprocess -vf scale=1280:-1 -c:v libx264 -crf 23`\n"
            "`th/ffmpegprocess -vf negate`\n"
            "`th/ffmpegprocess -af volume=2.0`"
        )
        return

    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply("❌ Attach a file to use `th/ffmpegprocess`.")
        return

    if source.size > MAX_FILE_SIZE:
        await ctx.reply("❌ File too large (max 25 MB).")
        return

    args_display = args if len(args) <= 80 else args[:79] + "…"
    status_msg = await ctx.reply(f"⏳ Probing + processing `{args_display}`…")

    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        suffix = Path(source.filename).suffix.lower()
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"534gurts_thffmpegprocess{suffix}")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        # Gather metadata with ffprobe
        meta = await _gather_media_metadata(input_path)

        try:
            user_args = shlex.split(args)
        except ValueError as e:
            await status_msg.edit(content=f"❌ Invalid ffmpeg args: {e}")
            return

        cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
        ] + user_args + [output_path]

        loop = asyncio.get_event_loop()
        ok, err_log = await loop.run_in_executor(None, _run_ffmpeg_raw, cmd, 180)

        elapsed = round(time.time() - start_time, 3)

        # Build metadata line
        meta_parts = []
        if meta["width"] != "N/A" and meta["height"] != "N/A":
            meta_parts.append(f"{meta['width']}×{meta['height']}")
        if meta["frameRate"] != "N/A":
            meta_parts.append(f"{meta['frameRate']} fps")
        if meta["duration"] != "N/A":
            try:
                meta_parts.append(f"{float(meta['duration']):.2f}s")
            except ValueError:
                meta_parts.append(meta["duration"])
        if meta["sampleRate"] != "N/A":
            meta_parts.append(f"{meta['sampleRate']} Hz")
        if meta["frameCount"] != "N/A":
            meta_parts.append(f"{meta['frameCount']} frames")
        meta_line = f"-# Input: {' · '.join(meta_parts)}" if meta_parts else ""

        if not ok:
            err_block = f"\n```\n{err_log.strip()[-1200:]}\n```" if err_log and err_log.strip() else ""
            await status_msg.edit(content=f"❌ FFmpeg failed (took {elapsed}s){err_block}")
            return

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            await status_msg.edit(content="❌ FFmpeg produced no output file.")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        footer_parts = []
        if meta_line:
            footer_parts.append(meta_line)
        if err_log and err_log.strip():
            footer_parts.append(f"-# Error Log:\n```\n{err_log.strip()[-800:]}\n```")
        footer_parts.append(f"-# Took {elapsed} seconds.")
        footer = "\n".join(footer_parts)

        try:
            await ctx.reply(
                content=footer,
                file=discord.File(output_path, filename=os.path.basename(output_path)),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Upload failed: {e}")


# ---------- th/trim — precise media trimmer ----------

_TRIM_SUPPORTED_EXTS = {
    ".mp4", ".mov", ".webm", ".gif", ".mkv",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a",
}
_TRIM_MAX_DECIMALS = 10


def _parse_trim_timestamp(ts: str) -> Decimal:
    """Parse HH:MM:SS[.frac], MM:SS[.frac], or plain seconds into Decimal seconds.

    Raises:
        ValueError("too_many_decimals") — more than 10 decimal places in the fractional part
        ValueError("invalid_format")    — unrecognisable or non-numeric input
    """
    ts = ts.strip()
    if "." in ts:
        frac = ts.rsplit(".", 1)[1]
        if len(frac) > _TRIM_MAX_DECIMALS:
            raise ValueError("too_many_decimals")
    parts = ts.split(":")
    try:
        if len(parts) == 1:
            return Decimal(parts[0])
        elif len(parts) == 2:
            return Decimal(parts[0]) * 60 + Decimal(parts[1])
        elif len(parts) == 3:
            return Decimal(parts[0]) * 3600 + Decimal(parts[1]) * 60 + Decimal(parts[2])
        else:
            raise ValueError("invalid_format")
    except InvalidOperation:
        raise ValueError("invalid_format")


@bot.command(name="trim")
async def trim_command(ctx: commands.Context, *, args: str = ""):
    """Trim media from <start> to <end> with up to 10 decimal places of precision.

    Usage:
      th/trim <start> <end>
      th/trim 5 15
      th/trim 0.5 3.75
      th/trim 1.2345678901 9.8765432109
      th/trim 00:01:30.5 00:02:45.25
      th/trim 1:30 2:45

    Media from: attachment on this message, replied-to message, or a URL in args.
    Supported: mp4, mov, webm, gif, mkv, mp3, wav, flac, ogg, m4a.
    """
    tokens = args.split()

    # Separate URLs from timestamp tokens
    media_url: str | None = None
    ts_tokens: list[str] = []
    for tok in tokens:
        if tok.startswith(("http://", "https://")):
            if media_url is None:
                media_url = tok
        else:
            ts_tokens.append(tok)

    if len(ts_tokens) < 2:
        await ctx.reply(
            "❌ Usage: `th/trim <start> <end>`\n"
            "Examples: `th/trim 5 15` · `th/trim 0.5 3.75` · `th/trim 00:01:30 00:02:45`\n"
            "Attach, reply to, or include a media URL."
        )
        return

    # Parse start timestamp
    try:
        t_start = _parse_trim_timestamp(ts_tokens[0])
    except ValueError as exc:
        if str(exc) == "too_many_decimals":
            await ctx.reply("❌ Timestamps may contain at most 10 decimal places.")
        else:
            await ctx.reply("❌ Invalid timestamp format.")
        return

    # Parse end timestamp
    try:
        t_end = _parse_trim_timestamp(ts_tokens[1])
    except ValueError as exc:
        if str(exc) == "too_many_decimals":
            await ctx.reply("❌ Timestamps may contain at most 10 decimal places.")
        else:
            await ctx.reply("❌ Invalid timestamp format.")
        return

    # Validate ordering
    if t_start < 0 or t_end < 0:
        await ctx.reply("❌ Timestamps cannot be negative.")
        return
    if t_start >= t_end:
        await ctx.reply("❌ Start time must be less than end time.")
        return

    # Resolve media source (priority: attachment > reply > URL arg)
    attachment: discord.Attachment | None = None
    if media_url is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
                else:
                    for tok in ref.content.split():
                        if tok.startswith(("http://", "https://")):
                            media_url = tok
                            break
            except Exception:
                pass

    if attachment is None and media_url is None:
        await ctx.reply("❌ No media found. Attach, reply to, or provide a media URL.")
        return

    # Determine file extension
    src_name = attachment.filename if attachment else urllib.parse.urlparse(media_url).path
    suffix = Path(src_name).suffix.lower()
    if not suffix:
        suffix = ".mp4"
    if suffix not in _TRIM_SUPPORTED_EXTS:
        await ctx.reply(
            f"❌ Unsupported format `{suffix}`.\n"
            f"Supported: {', '.join(sorted(_TRIM_SUPPORTED_EXTS))}"
        )
        return

    status_msg = await ctx.reply(f"✂️ Trimming…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")

        # Download
        try:
            if attachment:
                await download_attachment(attachment, input_path)
            else:
                await download_url(media_url, input_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Failed to download media: {exc}")
            return

        # Probe duration
        loop = asyncio.get_event_loop()
        dur = await loop.run_in_executor(None, _ffprobe_duration, input_path)
        if dur <= 0:
            await status_msg.edit(content="❌ Could not read media duration.")
            return

        if float(t_end) > dur + 0.001:
            await status_msg.edit(
                content=f"❌ End time exceeds the media duration ({dur:.6f}s)."
            )
            return

        output_path = os.path.join(tmpdir, f"trimmed{suffix}")
        start_str = str(t_start)
        end_str = str(t_end)

        duration_str = str(t_end - t_start)
        _audio_only_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}

        if suffix == ".gif":
            # GIFs cannot be stream-copied; re-encode with palette
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str, "-t", duration_str,
                "-i", input_path,
                "-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                output_path,
            ]
        elif suffix in _audio_only_exts:
            # Audio-only: input-side seek, stream copy
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str,
                "-i", input_path,
                "-t", duration_str,
                "-c", "copy",
                output_path,
            ]
        else:
            # Video (mp4/mov/webm/mkv): input-side seek keeps file at a keyframe
            # so the output is always decodable/viewable.
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str,
                "-i", input_path,
                "-t", duration_str,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                output_path,
            ]

        ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 120))
        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        stem = Path(src_name).stem
        safe_s = str(t_start).replace(".", "_")
        safe_e = str(t_end).replace(".", "_")
        out_filename = f"534gurts_thtrim_{safe_s}-{safe_e}{suffix}"

        try:
            await ctx.reply(
                content=f"✅ Trimmed `{t_start}s` → `{t_end}s`",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


# ---------- th/stretch_to_length / th/stl — time-stretch media to a target duration ----------

@bot.command(name="stretch_to_length", aliases=["stl"])
async def stretch_to_length_command(ctx: commands.Context, *, args: str = ""):
    """Time-stretch media (video+audio, or audio-only) to hit an exact target duration.

    Usage:
      th/stretch_to_length <target_seconds> [media_url]
      th/stl 10
      th/stl vidlen/2
      th/stl 20 https://example.com/video.mp4

    Video uses setpts + a locked framerate; audio uses the rubberband filter
    (tempo-only, pitch preserved). Media from: attachment, replied-to message,
    or a URL in args.
    """
    tokens = args.split()

    media_url: str | None = None
    other_tokens: list[str] = []
    for tok in tokens:
        if tok.startswith(("http://", "https://")):
            if media_url is None:
                media_url = tok
        else:
            other_tokens.append(tok)

    if not other_tokens:
        await ctx.reply(
            "❌ Usage: `th/stretch_to_length <target_seconds>`\n"
            "Examples: `th/stl 10` · `th/stl vidlen/2`\n"
            "Attach, reply to, or include a media URL."
        )
        return
    target_expr = other_tokens[0]

    # Resolve media source (priority: attachment > reply > URL arg)
    attachment: discord.Attachment | None = None
    if media_url is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
                else:
                    for tok in ref.content.split():
                        if tok.startswith(("http://", "https://")):
                            media_url = tok
                            break
            except Exception:
                pass

    if attachment is None and media_url is None:
        await ctx.reply("❌ No media found. Attach, reply to, or provide a media URL.")
        return

    src_name = attachment.filename if attachment else urllib.parse.urlparse(media_url).path
    suffix = Path(src_name).suffix.lower()
    if not suffix:
        suffix = ".mp4"
    if suffix not in _TRIM_SUPPORTED_EXTS:
        await ctx.reply(
            f"❌ Unsupported format `{suffix}`.\n"
            f"Supported: {', '.join(sorted(_TRIM_SUPPORTED_EXTS))}"
        )
        return

    status_msg = await ctx.reply("⏱️ Stretching…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")

        try:
            if attachment:
                await download_attachment(attachment, input_path)
            else:
                await download_url(media_url, input_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Failed to download media: {exc}")
            return

        loop = asyncio.get_event_loop()
        vidlen = await loop.run_in_executor(None, _ffprobe_duration, input_path)
        if vidlen <= 0:
            await status_msg.edit(content="❌ Could not read media duration.")
            return

        dur_ok, dur_or_error = _safe_awk_duration(target_expr, vidlen)
        if not dur_ok:
            await status_msg.edit(content=f"❌ {dur_or_error}")
            return
        target_duration = float(dur_or_error)

        ratio = vidlen / target_duration

        _audio_only_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
        out_suffix = suffix if suffix in _audio_only_exts else ".mov"
        output_path = os.path.join(tmpdir, f"stretched{out_suffix}")

        if suffix in _audio_only_exts:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-af", f"rubberband=tempo={ratio:.10f}",
                output_path,
            ]
        else:
            vinfo = await loop.run_in_executor(None, _ffprobe_video_info, input_path)
            framerate = vinfo.get("r_frame_rate", "30") or "30"
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vf", f"setpts=1/{ratio:.10f}*PTS,fps={framerate}",
                "-af", f"rubberband=tempo={ratio:.10f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "alac",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                output_path,
            ]

        ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 120))
        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Stretched to `{target_duration:.4f}s`! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        stem = Path(src_name).stem
        out_filename = f"534gurts_thstl_{target_duration:.4f}s{out_suffix}"

        try:
            await ctx.reply(
                content=f"✅ Stretched `{vidlen:.4f}s` → `{target_duration:.4f}s` (ratio `{ratio:.4f}`)",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


# ---------- th/repeat — repeat media N times ----------

@bot.command(name="repeat", aliases=["rep", "loop"])
async def repeat_command(ctx: commands.Context, *, args: str = ""):
    """Repeat a video, GIF, or audio file N times using FFmpeg concat.

    Usage:
      th/repeat [n]
      th/repeat 3

    n defaults to 2, max 10.
    Media from: attachment on this message, replied-to message, or URL in args.
    Supported: mp4, mov, webm, mkv, gif, mp3, wav, flac, ogg, m4a.
    """
    _SUPPORTED = {".mp4", ".mov", ".webm", ".mkv", ".gif", ".mp3", ".wav", ".flac", ".ogg", ".m4a"}
    tokens = args.split()
    n = 2
    url_arg = None
    for tok in tokens:
        if tok.startswith("http://") or tok.startswith("https://"):
            url_arg = tok
        else:
            try:
                n = max(1, min(10, int(tok)))
            except ValueError:
                pass

    source = await _resolve_media_source(ctx)
    if source is None and url_arg:
        source = url_arg
    if source is None:
        await ctx.reply(
            "❌ Usage: `th/repeat [n]`\n"
            "Attach or reply to a video, GIF, or audio file. Optionally pass a URL.\n"
            "Example: `th/repeat 3`"
        )
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        if isinstance(source, discord.Attachment):
            ext = os.path.splitext(source.filename)[1].lower()
            if ext not in _SUPPORTED:
                await ctx.reply(f"❌ Unsupported file type `{ext}`.")
                return
            base = os.path.splitext(source.filename)[0]
            inp = os.path.join(tmpdir, f"input{ext}")
            await download_attachment(source, inp)
        else:
            url_path = source.split("?")[0]
            ext = os.path.splitext(url_path)[1].lower()
            if ext not in _SUPPORTED:
                ext = ".mp4"
            base = "media"
            inp = os.path.join(tmpdir, f"input{ext}")
            async with aiohttp.ClientSession() as sess:
                async with sess.get(source) as resp:
                    if resp.status != 200:
                        await ctx.reply(f"❌ Failed to download media (HTTP {resp.status}).")
                        return
                    with open(inp, "wb") as f:
                        f.write(await resp.read())

        out_ext = ".mp4" if ext in {".mp4", ".mov", ".webm", ".mkv", ".gif"} else ext
        out = os.path.join(tmpdir, f"repeat_{base}{out_ext}")
        concat_list = os.path.join(tmpdir, "concat.txt")
        safe_inp = inp.replace("'", "'\\''")
        with open(concat_list, "w") as f:
            for _ in range(n):
                f.write(f"file '{safe_inp}'\n")

        status_msg = await ctx.reply(f"⏳ Repeating {n}×…")

        def _run():
            return subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", out],
                capture_output=True, text=True, timeout=120,
            )
        try:
            proc = await asyncio.get_event_loop().run_in_executor(None, _run)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Repeat failed: {exc}")
            return

        if proc.returncode != 0 or not os.path.exists(out) or os.stat(out).st_size == 0:
            err = (proc.stderr or "")[-300:]
            await status_msg.edit(content=f"❌ Repeat failed:\n```\n{err}\n```")
            return

        out_name = f"534gurts_threpeat{out_ext}"
        file_size = os.stat(out).st_size
        if file_size <= CATBOX_THRESHOLD:
            await status_msg.edit(content=f"✅ Repeated {n}×!")
            await ctx.reply(file=discord.File(out, filename=out_name))
        else:
            await status_msg.edit(content=f"⏳ Output too large ({file_size // 1024 // 1024} MB) — uploading to Catbox…")
            cat_url = await _upload_to_catbox(out)
            if cat_url:
                await status_msg.edit(content=f"✅ Repeated {n}× — {cat_url}")
            else:
                await status_msg.edit(content="❌ Too large for Discord and Catbox upload failed.")


# ---------- th/concatenate / th/concat — join 2-10 media files into one ----------

_CONCAT_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".gif", ".mkv"}
_CONCAT_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
_CONCAT_SUPPORTED_EXTS = _CONCAT_VIDEO_EXTS | _CONCAT_AUDIO_EXTS
_CONCAT_MAX_SOURCES = 10
_CONCAT_FORMAT_TOKENS = {
    "mp4": ".mp4", "mov": ".mov", "mkv": ".mkv", "webm": ".webm",
    "mp3": ".mp3", "wav": ".wav", "flac": ".flac", "ogg": ".ogg", "m4a": ".m4a",
}


def _has_audio_stream(input_path: str) -> bool:
    out = _ffprobe(input_path, "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0")
    return bool(out.strip())


@bot.command(name="concatenate", aliases=["concat"])
async def concatenate_command(ctx: commands.Context, *, args: str = ""):
    """Concatenate 2-10 media files (attachments and/or URLs) into one file, in order.

    Usage:
      th/concatenate <url1> <url2> ... [format]
      th/concat https://a.mp4 https://b.mp4
      th/concat https://a.mp3 https://b.mp3 https://c.mp3 wav

    Also works with multiple attachments on the message, or attachments/URLs on
    a replied-to message. All sources must be the same media type (all video,
    or all audio) — mixing is not supported. Video output defaults to mp4;
    audio output defaults to mp3. An optional trailing format token
    (mp4/mov/mkv/webm for video, mp3/wav/flac/ogg/m4a for audio) overrides it.
    Supported: mp4, mov, webm, gif, mkv, mp3, wav, flac, ogg, m4a.
    """
    tokens = args.split()

    format_override: str | None = None
    if tokens and tokens[-1].lower() in _CONCAT_FORMAT_TOKENS:
        format_override = tokens.pop().lower()

    url_tokens = [t for t in tokens if t.startswith(("http://", "https://"))]

    # Sources: message attachments (in order) first, then URL tokens (in order).
    sources: list[discord.Attachment | str] = list(ctx.message.attachments) + url_tokens

    if not sources and ctx.message and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                sources = list(ref.attachments)
            else:
                sources = [t for t in ref.content.split() if t.startswith(("http://", "https://"))]
        except Exception:
            pass

    if len(sources) < 2:
        await ctx.reply(
            "❌ Usage: `th/concatenate <url1> <url2> ... [format]` (2-10 sources)\n"
            "Provide 2+ attachments and/or media URLs on this message, or reply to "
            "a message containing them.\n"
            f"Supported: {', '.join(sorted(_CONCAT_SUPPORTED_EXTS))}"
        )
        return

    if len(sources) > _CONCAT_MAX_SOURCES:
        await ctx.reply(f"❌ Too many sources ({len(sources)}). Maximum is {_CONCAT_MAX_SOURCES}.")
        return

    status_msg = await ctx.reply(f"🔗 Concatenating {len(sources)} files…")
    loop = asyncio.get_event_loop()

    with tempfile.TemporaryDirectory() as tmpdir:
        input_paths: list[str] = []
        exts: list[str] = []

        for i, src in enumerate(sources):
            if isinstance(src, discord.Attachment):
                name = src.filename
            else:
                name = urllib.parse.urlparse(src).path
            ext = Path(name).suffix.lower()
            if ext not in _CONCAT_SUPPORTED_EXTS:
                await status_msg.edit(
                    content=(
                        f"❌ Source {i + 1} has an unsupported format `{ext or '(none)'}`.\n"
                        f"Supported: {', '.join(sorted(_CONCAT_SUPPORTED_EXTS))}"
                    )
                )
                return
            exts.append(ext)
            dest = os.path.join(tmpdir, f"src_{i}{ext}")
            try:
                if isinstance(src, discord.Attachment):
                    await download_attachment(src, dest)
                else:
                    await download_url(src, dest)
            except Exception as exc:
                await status_msg.edit(content=f"❌ Failed to download source {i + 1}: {exc}")
                return
            input_paths.append(dest)

        is_video = any(e in _CONCAT_VIDEO_EXTS for e in exts)
        is_audio = any(e in _CONCAT_AUDIO_EXTS for e in exts)
        if is_video and is_audio:
            await status_msg.edit(
                content="❌ Cannot mix video and audio-only sources. All sources must be the same media type."
            )
            return

        out_ext = _CONCAT_FORMAT_TOKENS.get(format_override, ".mp4" if is_video else ".mp3")
        if format_override:
            override_is_audio = out_ext in _CONCAT_AUDIO_EXTS
            if override_is_audio != is_audio:
                await status_msg.edit(
                    content=f"❌ Format `{format_override}` doesn't match the source media type "
                            f"({'video' if is_video else 'audio'})."
                )
                return

        normalized_paths: list[str] = []

        if is_video:
            vinfo = await loop.run_in_executor(None, _ffprobe_video_info, input_paths[0])
            target_w = vinfo.get("width") or 1280
            target_h = vinfo.get("height") or 720
            target_w += target_w % 2
            target_h += target_h % 2
            target_fps = vinfo.get("r_frame_rate", "30") or "30"

            for i, in_path in enumerate(input_paths):
                norm_path = os.path.join(tmpdir, f"norm_{i}.mp4")
                has_audio = await loop.run_in_executor(None, _has_audio_stream, in_path)
                vf = (
                    f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={target_fps}"
                )
                if has_audio:
                    cmd = [
                        "ffmpeg", "-y", "-i", in_path,
                        "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                        "-pix_fmt", "yuv420p", norm_path,
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", in_path,
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-shortest",
                        "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                        "-pix_fmt", "yuv420p", norm_path,
                    ]
                ok, err = await loop.run_in_executor(None, lambda c=cmd: _run_ffmpeg_raw(c, 180))
                if not ok:
                    await status_msg.edit(content=f"❌ Failed to normalize source {i + 1}:\n```\n{err[-1200:]}\n```")
                    return
                normalized_paths.append(norm_path)

            output_path = os.path.join(tmpdir, f"concatenated{out_ext}")
            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w") as f:
                for p in normalized_paths:
                    f.write(f"file '{p}'\n")

            concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list]
            if out_ext in {".mp4", ".mov"}:
                concat_cmd += ["-c", "copy", "-movflags", "+faststart"]
            else:
                concat_cmd += _concat_codec_args(out_ext)
            concat_cmd.append(output_path)
            ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(concat_cmd, 180))
            if not ok:
                await status_msg.edit(content=f"❌ Concat failed:\n```\n{err[-1500:]}\n```")
                return
        else:
            for i, in_path in enumerate(input_paths):
                norm_path = os.path.join(tmpdir, f"norm_{i}.wav")
                cmd = [
                    "ffmpeg", "-y", "-i", in_path,
                    "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", norm_path,
                ]
                ok, err = await loop.run_in_executor(None, lambda c=cmd: _run_ffmpeg_raw(c, 120))
                if not ok:
                    await status_msg.edit(content=f"❌ Failed to normalize source {i + 1}:\n```\n{err[-1200:]}\n```")
                    return
                normalized_paths.append(norm_path)

            output_path = os.path.join(tmpdir, f"concatenated{out_ext}")
            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w") as f:
                for p in normalized_paths:
                    f.write(f"file '{p}'\n")

            concat_wav = os.path.join(tmpdir, "concat.wav")
            concat_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                "-c", "copy", concat_wav,
            ]
            ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(concat_cmd, 180))
            if not ok:
                await status_msg.edit(content=f"❌ Concat failed:\n```\n{err[-1500:]}\n```")
                return

            if out_ext == ".wav":
                shutil.copyfile(concat_wav, output_path)
            else:
                encode_cmd = ["ffmpeg", "-y", "-i", concat_wav, output_path]
                ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(encode_cmd, 120))
                if not ok:
                    await status_msg.edit(content=f"❌ Final encode failed:\n```\n{err[-1500:]}\n```")
                    return

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            await status_msg.edit(content="❌ Concatenation produced an empty file.")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Concatenated {len(sources)} files! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = f"534gurts_thconcat_{len(sources)}files{out_ext}"
        try:
            await ctx.reply(
                content=f"✅ Concatenated {len(sources)} files into one `{out_ext.lstrip('.')}`",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


# ---------- th/join — join 2 videos side-by-side or stacked ----------
_JOIN_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".gif", ".mkv"}
_JOIN_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
_JOIN_SUPPORTED_EXTS = _JOIN_VIDEO_EXTS | _JOIN_AUDIO_EXTS


@bot.command(name="join", aliases=[])
async def join_command(ctx: commands.Context, *, args: str = ""):
    """Join two media files side-by-side (horizontal) or stacked (vertical).

    Usage:
      th/join [media1] [media2] [-vertical]
      th/join -vertical                       (joins 2 attached/replied videos)
      th/join https://a.mp4 https://b.mp4

    Sources: two attachments, two URLs, or one attachment + one URL. They can
    be in args, on the message, or in a replied-to message. The default layout is
    horizontal (side-by-side). Pass `-vertical` to stack them vertically.
    """
    tokens = args.split()
    vertical = any(t.lower() in {"-vertical", "--vertical", "-v"} for t in tokens)
    tokens = [t for t in tokens if t.lower() not in {"-vertical", "--vertical", "-v"}]

    url_tokens = [t for t in tokens if t.startswith(("http://", "https://"))]

    sources: list[discord.Attachment | str] = []
    if ctx.message and ctx.message.attachments:
        sources.extend(ctx.message.attachments)
    sources.extend(url_tokens)

    if len(sources) < 2 and ctx.message and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                sources.extend(ref.attachments)
            else:
                sources.extend(t for t in ref.content.split() if t.startswith(("http://", "https://")))
        except Exception:
            pass

    sources = sources[:2]

    if len(sources) != 2:
        await ctx.reply(
            "❌ Usage: `th/join [media1] [media2] [-vertical]`\n"
            "Provide exactly 2 attachments and/or media URLs, either on this message "
            "or in a reply. Default layout is horizontal (side-by-side); add `-vertical` "
            "to stack them."
        )
        return

    status_msg = await ctx.reply("🔗 Joining 2 files…")
    loop = asyncio.get_event_loop()

    with tempfile.TemporaryDirectory() as tmpdir:
        input_paths: list[str] = []
        exts: list[str] = []

        for i, src in enumerate(sources):
            if isinstance(src, discord.Attachment):
                name = src.filename
            else:
                name = urllib.parse.urlparse(src).path
            ext = Path(name).suffix.lower()
            if ext not in _JOIN_SUPPORTED_EXTS:
                await status_msg.edit(
                    content=f"❌ Source {i + 1} has an unsupported format `{ext or '(none)'}`. "
                            f"Supported: {', '.join(sorted(_JOIN_SUPPORTED_EXTS))}"
                )
                return
            exts.append(ext)
            dest = os.path.join(tmpdir, f"src_{i}{ext}")
            try:
                if isinstance(src, discord.Attachment):
                    await download_attachment(src, dest)
                else:
                    await download_url(src, dest)
            except Exception as exc:
                await status_msg.edit(content=f"❌ Failed to download source {i + 1}: {exc}")
                return
            input_paths.append(dest)

        is_video = any(e in _JOIN_VIDEO_EXTS for e in exts)
        is_audio = any(e in _JOIN_AUDIO_EXTS for e in exts)
        if is_video and is_audio:
            await status_msg.edit(content="❌ Cannot mix video and audio-only sources.")
            return

        output_path = os.path.join(tmpdir, f"joined{'.mp4' if is_video else exts[0]}")

        if is_video:
            infos = [await loop.run_in_executor(None, _ffprobe_video_info, p) for p in input_paths]
            widths = [i.get("width") or 1280 for i in infos]
            heights = [i.get("height") or 720 for i in infos]
            rates = [i.get("r_frame_rate", "30") or "30" for i in infos]

            target_w = min(widths)
            target_h = min(heights)
            target_w += target_w % 2
            target_h += target_h % 2
            target_fps = rates[0]

            norm_paths: list[str] = []
            for i, in_path in enumerate(input_paths):
                norm_path = os.path.join(tmpdir, f"norm_{i}.mp4")
                has_audio = await loop.run_in_executor(None, _has_audio_stream, in_path)
                vf = (
                    f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={target_fps}"
                )
                if has_audio:
                    cmd = [
                        "ffmpeg", "-y", "-i", in_path,
                        "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                        "-pix_fmt", "yuv420p", norm_path,
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y", "-i", in_path,
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-shortest",
                        "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                        "-pix_fmt", "yuv420p", norm_path,
                    ]
                ok, err = await loop.run_in_executor(None, lambda c=cmd: _run_ffmpeg_raw(c, 180))
                if not ok:
                    await status_msg.edit(content=f"❌ Failed to normalize source {i + 1}:\n```\n{err[-1200:]}\n```")
                    return
                norm_paths.append(norm_path)

            if vertical:
                out_w = target_w
                out_h = target_h * 2
                layout = "vstack=inputs=2"
                out_h += out_h % 2
            else:
                out_w = target_w * 2
                out_h = target_h
                layout = "hstack=inputs=2"
                out_w += out_w % 2

            cmd = [
                "ffmpeg", "-y",
                "-i", norm_paths[0],
                "-i", norm_paths[1],
                "-filter_complex", f"[0:v][1:v]{layout},format=yuv420p[outv];[0:a][1:a]amix=inputs=2:duration=longest[outa]",
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                "-movflags", "+faststart", "-pix_fmt", "yuv420p",
                output_path,
            ]
            ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 240))
            if not ok:
                await status_msg.edit(content=f"❌ Join failed:\n```\n{err[-1500:]}\n```")
                return
        else:
            # Audio: mix the two tracks together (not side-by-side in visual sense, but a "join" mix).
            concat_wav = os.path.join(tmpdir, "join.wav")
            cmd = [
                "ffmpeg", "-y",
                "-i", input_paths[0], "-i", input_paths[1],
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[aout]",
                "-map", "[aout]",
                "-ar", "48000", "-ac", "2", concat_wav,
            ]
            ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 180))
            if not ok:
                await status_msg.edit(content=f"❌ Join failed:\n```\n{err[-1500:]}\n```")
                return
            if exts[0] == ".wav":
                shutil.copyfile(concat_wav, output_path)
            else:
                encode_cmd = ["ffmpeg", "-y", "-i", concat_wav, output_path]
                ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(encode_cmd, 120))
                if not ok:
                    await status_msg.edit(content=f"❌ Final encode failed:\n```\n{err[-1500:]}\n```")
                    return

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            await status_msg.edit(content="❌ Join produced an empty file.")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Joined 2 files! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        layout_name = "vertical" if vertical else "horizontal"
        out_ext = ".mp4" if is_video else exts[0]
        out_filename = f"534gurts_thjoin_{layout_name}{out_ext}"
        try:
            await ctx.reply(
                content=f"✅ Joined 2 files `{layout_name}`",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


# ---------- th/autotune / th/autotoon — reference-based pitch correction ----------

@bot.command(name="autotune", aliases=["autotoon"])
async def autotune_command(ctx: commands.Context, *, args: str = ""):
    """Pitch-correct a video/audio to match a reference track.

    Usage:
      th/autotune <YouTube URL or search query>
      th/autotoon <YouTube URL or search query>

    Attach or reply to the media you want to autotune.
    The argument is the reference (URL or search terms).
    Optional: append  --strength <0.0-1.0>  (default 1.0).
    """
    import re as _re

    # ── Parse --strength flag ──────────────────────────────────────────────────
    strength = 1.0
    _sm = _re.search(r"--strength\s+([0-9]*\.?[0-9]+)", args)
    if _sm:
        try:
            strength = max(0.0, min(1.0, float(_sm.group(1))))
        except ValueError:
            pass
        args = (args[:_sm.start()] + args[_sm.end():]).strip()

    ref_query = args.strip()

    if not ref_query:
        await ctx.reply(
            "❌ Usage: `th/autotune <YouTube URL or search query>`\n"
            "Attach or reply to the video/audio you want to autotune.\n"
            "The argument is the reference track (URL or search terms).\n"
            "Optional flag: `--strength 0.0-1.0` (default 1.0)"
        )
        return

    # ── Resolve base media ─────────────────────────────────────────────────────
    _AUTOTUNE_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".mp3", ".wav", ".flac", ".ogg", ".m4a"}
    media_url: str | None = None
    attachment: discord.Attachment | None = None

    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
    elif ctx.message.reference:
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref_msg.attachments:
                attachment = ref_msg.attachments[0]
            else:
                for tok in ref_msg.content.split():
                    if tok.startswith(("http://", "https://")):
                        media_url = tok
                        break
        except Exception:
            pass

    if attachment is None and media_url is None:
        await ctx.reply("❌ No media found. Attach a video/audio, reply to one, or include a media URL.")
        return

    src_name = attachment.filename if attachment else urllib.parse.urlparse(media_url).path
    suffix = Path(src_name).suffix.lower() or ".mp4"
    if suffix not in _AUTOTUNE_EXTS:
        await ctx.reply(f"❌ Unsupported format `{suffix}`. Supported: {', '.join(sorted(_AUTOTUNE_EXTS))}")
        return

    is_video = suffix in {".mp4", ".mov", ".webm", ".mkv"}
    status_msg = await ctx.reply("🎵 Downloading reference track…", mention_author=False)

    loop = asyncio.get_event_loop()

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        ref_wav    = os.path.join(tmpdir, "ref.wav")
        output_ext = suffix if is_video else ".mp4" if not is_video else suffix
        output_path = os.path.join(tmpdir, f"autotuned{suffix}")

        # ── Download reference ─────────────────────────────────────────────────
        ok, err = await loop.run_in_executor(
            None, _ytdlp_download_audio_wav, ref_query, ref_wav, 600
        )
        if not ok:
            await status_msg.edit(content=f"❌ Reference download failed:\n```\n{err[-800:]}\n```")
            return

        # ── Download base media ────────────────────────────────────────────────
        await status_msg.edit(content="⬇️ Downloading your media…")
        try:
            if attachment:
                await download_attachment(attachment, input_path)
            else:
                await download_url(media_url, input_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Media download failed: {exc}")
            return

        # ── Run autotune ───────────────────────────────────────────────────────
        await status_msg.edit(content="🔧 Detecting pitches and applying correction…")
        ok, info = await loop.run_in_executor(
            None, _run_autotune_reference, input_path, ref_wav, output_path, strength
        )
        if not ok:
            await status_msg.edit(content=f"❌ Autotune failed:\n```\n{info[-1000:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        stem = Path(src_name).stem
        out_filename = f"534gurts_thautotune{suffix}"
        pitch_line = f"\n> {info}" if info else ""

        try:
            await ctx.reply(
                content=f"✅ Autotuned!{pitch_line}",
                file=discord.File(output_path, filename=out_filename),
                mention_author=False,
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Upload failed: {exc}")


# ---------- th/addsource — grid-cell video overlay ----------

@bot.command(name="addsource")
async def addsource_command(ctx: commands.Context, *, args: str = ""):
    """Overlay a secondary video onto a specific grid cell of a base video.

    Usage:
      th/addsource <overlay_url> <grid> <pos> [trim_duration] [overlay_start] [--base-audio]

    Arguments:
      overlay_url    URL of the video to place in the cell
      grid           Grid size as RxC, e.g. 2x2, 3x3, 4x4
      pos            1-indexed cell number (left-to-right, top-to-bottom)
      trim_duration  Optional — trim base to last N seconds using
                     reverse→trim→reverse (end-trim). Also end-trims audio.
                      When supplied, audio always comes from the base track.
      overlay_start  Optional — skip this many seconds from the beginning of
                      the overlay video before placing it in the grid cell.
      --base-audio   Use base video audio instead of overlay audio (no trim).

    Base video: attach to the message or reply to a message containing one.

    Examples:
      th/addsource https://example.com/clip.mp4 2x2 3
      th/addsource https://example.com/clip.mp4 2x2 1 5.0 0.4
      th/addsource https://example.com/clip.mp4 3x3 5 --base-audio
    """
    import re as _re

    use_base_audio = "--base-audio" in args
    args = args.replace("--base-audio", "").strip()

    # ── Parse tokens ──────────────────────────────────────────────────────────
    overlay_url:    str | None   = None
    grid_str:       str | None   = None
    pos_str:        str | None   = None
    trim_duration:  float | None = None
    overlay_start:  float | None = None

    for tok in args.split():
        if tok.startswith(("http://", "https://")) and overlay_url is None:
            overlay_url = tok
        elif _re.match(r"^\d+x\d+$", tok, _re.IGNORECASE) and grid_str is None:
            grid_str = tok.lower()
        elif tok.isdigit() and pos_str is None and grid_str is not None:
            pos_str = tok
        elif trim_duration is None and pos_str is not None:
            try:
                trim_duration = float(tok)
            except ValueError:
                pass
        elif overlay_start is None and trim_duration is not None:
            try:
                overlay_start = float(tok)
            except ValueError:
                pass

    if not overlay_url or not grid_str or not pos_str:
        await ctx.reply(
            "❌ Usage: `th/addsource <overlay_url> <grid> <pos> [trim_duration] [overlay_start]`\n"
            "Example: `th/addsource https://... 2x2 3` or `th/addsource https://... 3x3 5 0.5 0.4`\n"
            "Attach or reply to the base video.\n"
            "Optional flag: `--base-audio` to keep base audio instead of overlay (without trim)."
        )
        return

    try:
        rows, cols = map(int, grid_str.split("x"))
        pos = int(pos_str)
    except ValueError:
        await ctx.reply("❌ Invalid grid format. Use `RxC` like `2x2` or `3x3`.")
        return

    if rows < 1 or cols < 1:
        await ctx.reply("❌ Grid dimensions must be at least 1×1.")
        return
    if pos < 1 or pos > rows * cols:
        await ctx.reply(f"❌ Position must be between 1 and {rows * cols} for a {rows}×{cols} grid.")
        return
    if trim_duration is not None and trim_duration <= 0:
        await ctx.reply("❌ trim_duration must be a positive number of seconds.")
        return
    if overlay_start is not None and overlay_start < 0:
        await ctx.reply("❌ overlay_start must be zero or a positive number of seconds.")
        return

    # ── Resolve base media ────────────────────────────────────────────────────
    attachment: discord.Attachment | None = None
    base_url: str | None = None

    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
    elif ctx.message.reference:
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref_msg.attachments:
                attachment = ref_msg.attachments[0]
            else:
                for tok in ref_msg.content.split():
                    if tok.startswith(("http://", "https://")):
                        base_url = tok
                        break
        except Exception:
            pass

    if attachment is None and base_url is None:
        await ctx.reply("❌ No base video found. Attach one to the message or reply to a message that has one.")
        return

    src_name = attachment.filename if attachment else urllib.parse.urlparse(base_url).path
    suffix   = Path(src_name).suffix.lower() or ".mp4"

    status_msg = await ctx.reply("⬇️ Downloading base video…", mention_author=False)
    loop = asyncio.get_event_loop()

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path    = os.path.join(tmpdir, f"base{suffix}")
        overlay_path = os.path.join(tmpdir, "overlay.mp4")
        output_path  = os.path.join(tmpdir, "output.mp4")

        # Download base
        try:
            if attachment:
                await download_attachment(attachment, base_path)
            else:
                await download_url(base_url, base_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Base download failed: `{exc}`")
            return

        # Download overlay
        await status_msg.edit(content="⬇️ Downloading overlay…")
        try:
            await download_url(overlay_url, overlay_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Overlay download failed: `{exc}`")
            return

        # Composite
        trim_note = f", trimming to last {trim_duration}s" if trim_duration is not None else ""
        overlay_note = f", overlay starts at {overlay_start}s" if overlay_start is not None else ""
        await status_msg.edit(content=f"🔧 Compositing `{grid_str}` grid, cell {pos}{trim_note}{overlay_note}…")
        ok, err = await loop.run_in_executor(
            None, _run_grid_overlay,
            base_path, overlay_path, rows, cols, pos, output_path,
            use_base_audio, trim_duration, overlay_start,
        )
        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1200:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            catbox_url = await _upload_to_catbox(output_path)
            if catbox_url:
                await status_msg.edit(
                    content=f"✅ Grid overlay done (file >8 MB, uploaded to Catbox):\n{catbox_url}"
                )
            else:
                await status_msg.edit(content="❌ Output too large for Discord (>25 MB) and Catbox upload failed.")
            return

        stem = Path(src_name).stem
        out_filename = f"534gurts_thaddsource_{grid_str}_pos{pos}.mp4"
        if trim_duration is not None:
            audio_note = f"base audio, trimmed to {trim_duration}s"
        else:
            audio_note = "base audio" if use_base_audio else "overlay audio"

        try:
            await ctx.reply(
                content=f"✅ Grid `{grid_str}`, cell {pos} — {audio_note}",
                file=discord.File(output_path, filename=out_filename),
                mention_author=False,
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Upload failed: `{exc}`")


# ---------- th/mirror — mirror presets via FFmpeg split/crop/flip/stack ----------

# Each preset is (vf_filter, description)
# Native FFmpeg: split the frame, crop each half, flip one, stack back.
_MIRROR_PRESETS: dict[str, tuple[str, str]] = {
    "left": (
        "split[a][b];[a]crop=iw/2:ih:0:0[L];[b]crop=iw/2:ih:0:0,hflip[R];[L][R]hstack",
        "left half mirrored onto right",
    ),
    "right": (
        "split[a][b];[a]crop=iw/2:ih:iw/2:0,hflip[L];[b]crop=iw/2:ih:iw/2:0[R];[L][R]hstack",
        "right half mirrored onto left",
    ),
    "top": (
        "split[a][b];[a]crop=iw:ih/2:0:0[T];[b]crop=iw:ih/2:0:0,vflip[B];[T][B]vstack",
        "top half mirrored onto bottom",
    ),
    "bottom": (
        "split[a][b];[a]crop=iw:ih/2:0:ih/2,vflip[T];[b]crop=iw:ih/2:0:ih/2[B];[T][B]vstack",
        "bottom half mirrored onto top",
    ),
}
# Short aliases → canonical name
_MIRROR_ALIASES: dict[str, str] = {"l": "left", "r": "right", "t": "top", "b": "bottom"}
_MIRROR_SUPPORTED_EXTS = {
    ".mp4", ".mov", ".webm", ".mkv", ".gif",
    ".png", ".jpg", ".jpeg", ".webp",
}


@bot.command(name="mirror")
async def mirror_command(ctx: commands.Context, preset: str = "", *, args: str = ""):
    """Mirror media along an axis.

    Usage:
      th/mirror <preset>
      Presets: left (l), right (r), top (t), bottom (b)

    Examples:
      th/mirror left
      th/mirror r
      th/mirror top

    Media from: attachment, replied-to message, or a URL in the preset/args.
    """
    # Resolve preset name (allow short aliases)
    preset_key = preset.strip().lower()
    preset_key = _MIRROR_ALIASES.get(preset_key, preset_key)

    # A URL might have been passed in the preset slot; re-route it
    media_url: str | None = None
    if preset.startswith(("http://", "https://")):
        media_url = preset
        preset_key = args.split()[0].lower() if args.strip() else ""
        preset_key = _MIRROR_ALIASES.get(preset_key, preset_key)

    if preset_key not in _MIRROR_PRESETS:
        preset_list = ", ".join(f"`{k}`" for k in _MIRROR_PRESETS)
        await ctx.reply(f"❌ Available presets: {preset_list}")
        return

    vf, description = _MIRROR_PRESETS[preset_key]

    # Scan args for a URL if not already found
    if media_url is None:
        for tok in args.split():
            if tok.startswith(("http://", "https://")):
                media_url = tok
                break

    # Resolve media: attachment > reply > URL arg
    attachment: discord.Attachment | None = None
    if media_url is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
                else:
                    for tok in ref.content.split():
                        if tok.startswith(("http://", "https://")):
                            media_url = tok
                            break
            except Exception:
                pass

    if attachment is None and media_url is None:
        await ctx.reply("❌ No media found. Attach, reply to, or provide media.")
        return

    src_name = attachment.filename if attachment else urllib.parse.urlparse(media_url).path
    suffix = Path(src_name).suffix.lower()
    if not suffix:
        suffix = ".mp4"
    if suffix not in _MIRROR_SUPPORTED_EXTS:
        await ctx.reply(
            f"❌ Unsupported format `{suffix}`.\n"
            f"Supported: {', '.join(sorted(_MIRROR_SUPPORTED_EXTS))}"
        )
        return

    status_msg = await ctx.reply(f"🪞 Applying `mirror={preset_key}` ({description})…")

    _image_exts = {".png", ".jpg", ".jpeg", ".webp"}

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")

        try:
            if attachment:
                await download_attachment(attachment, input_path)
            else:
                await download_url(media_url, input_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Failed to download media: {exc}")
            return

        out_suffix = suffix if suffix != ".webp" else ".png"
        output_path = os.path.join(tmpdir, f"mirror_{preset_key}{out_suffix}")

        loop = asyncio.get_event_loop()

        if suffix == ".gif":
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"{vf},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                output_path,
            ]
        elif suffix in _image_exts:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", vf,
                output_path,
            ]
        else:
            # Video: re-encode with libx264 so output is always viewable
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"{vf},format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "copy",
                "-movflags", "+faststart",
                output_path,
            ]

        ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 180))
        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        stem = Path(src_name).stem
        out_filename = f"534gurts_thmirror_{preset_key}{out_suffix}"

        try:
            await ctx.reply(
                content=f"✅ `mirror={preset_key}` — {description}",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


@bot.command(name="huehsv", aliases=["hhsv"])
async def huehsv_command(
    ctx: commands.Context,
    hue: float = 0.5,
    sat: float = 1.0,
    lightness: float = 1.0,
    colorspace: str = "hsl",
    betterfully: str = "",
):
    """Apply hue/sat/lightness shift using ImageMagick haldclut + FFmpeg.

    Usage:
      th/huehsv <hue> [sat] [lightness] [colorspace] [betterfully]
      th/hhsv <hue>   — alias

    Parameters:
      hue         — hue rotation (0.0=unchanged, 0.5=full rotation)
      sat         — saturation multiplier (default 1.0)
      lightness   — lightness multiplier (default 1.0)
      colorspace  — ImageMagick modulate colorspace (default hsl)
      betterfully — 1/true/yes to boost saturation to 125% and posterize hue

    Internally: magick hald:8 -define modulate:colorspace=<cs> -modulate <L>,<S>,<H> [betterfully ops] hsv.ppm
    Then: ffmpeg -vf "movie=hsv.ppm,[in]haldclut,format=yuv420p" -pix_fmt yuv420p
    """
    _TRUE_VALS = {"1", "true", "t", "y", "yes", "+", "on"}
    bf = betterfully.strip().lower() in _TRUE_VALS

    # Resolve attachment
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**IHTX HueHSV**\n"
            "Attach a video or image and use `th/huehsv <hue> [sat] [lightness] [colorspace] [betterfully]`.\n\n"
            "Applies hue/sat/lightness shift via ImageMagick haldclut (hald:8).\n"
            "• `betterfully` — set to `1` for richer hue posterisation + 125% sat headroom\n"
            "Example: `th/huehsv 0.5` · `th/huehsv 0.3 1.2 1.0 hsl 1`\n"
            "Aliases: `th/hhsv`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in SUPPORTED_EXTENSIONS:
        await ctx.reply(f"Unsupported file type `{suffix}`. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        return

    is_video = suffix in VIDEO_EXTENSIONS
    out_ext = get_output_ext(suffix, is_video)

    bf_label = " betterfully" if bf else ""
    status_msg = await ctx.reply(
        f"⚙️ Applying **huehsv** (hue={hue} sat={sat} lightness={lightness} cs={colorspace}{bf_label})… this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"output{out_ext}")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None,
            lambda: _run_huehsv(input_path, output_path, hue=hue, sat=sat,
                                 lightness=lightness, colorspace=colorspace, betterfully=bf),
        )

        if not ok:
            await status_msg.edit(content=f"❌ HueHSV failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = f"534gurts_thhuehsv_{hue}{out_ext}"
        try:
            await ctx.reply(
                content=f"✅ **IHTX huehsv** (hue={hue} sat={sat} lightness={lightness} cs={colorspace}{bf_label}) applied!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="png2lut", aliases=["lut2cube"])
async def png2lut_cmd(ctx: commands.Context, *, args: str = ""):
    """Convert a tiled LUT PNG to a .cube file.

    Usage:
      th/png2lut [lut_size] [output_name]

    Attach a tiled LUT PNG (e.g. 512×512 for a 64-size LUT).
    lut_size defaults to 64. output_name sets the .cube filename stem.
    """
    # Parse args manually to avoid discord.py failing to cast non-numeric first token to int
    tokens = args.split()
    lut_size = 64
    output_name = ""
    if tokens:
        try:
            lut_size = int(tokens[0])
            output_name = " ".join(tokens[1:])
        except ValueError:
            # First token isn't a number — treat entire string as output_name
            output_name = args.strip()

    if _PIL_Image is None:
        await ctx.reply("❌ Pillow is not installed — cannot read PNG pixel data.")
        return

    # Resolve attachment
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**th/png2lut** — Convert a tiled LUT PNG → .cube file\n"
            "Attach the LUT PNG and run `th/png2lut [lut_size] [output_name]`.\n"
            "Default lut_size is 64. Example: `th/png2lut 33 my_lut`"
        )
        return

    if not source.filename.lower().endswith(".png"):
        await ctx.reply("❌ Please attach a PNG file.")
        return

    if lut_size < 2 or lut_size > 256:
        await ctx.reply("❌ lut_size must be between 2 and 256.")
        return

    status_msg = await ctx.reply(f"⚙️ Converting LUT PNG → .cube (size={lut_size})…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "lut_input.png")
        stem = output_name.strip() or f"lut_{int(time.time())}"
        cube_path = os.path.join(tmpdir, f"{stem}.cube")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download PNG: {e}")
            return

        def _convert():
            img = _PIL_Image.open(input_path).convert("RGB")
            width, height = img.size
            tiles_per_row = width // lut_size
            tiles_per_col = height // lut_size
            if tiles_per_row * tiles_per_col != lut_size:
                raise ValueError(
                    f"Unexpected layout: {tiles_per_row}×{tiles_per_col} tiles "
                    f"but expected {lut_size} total for lut_size={lut_size}."
                )
            pixels = img.load()
            with open(cube_path, "w") as f:
                f.write("# Generated by IHTX png2lut\n")
                f.write(f"LUT_3D_SIZE {lut_size}\n")
                f.write("DOMAIN_MIN 0.0 0.0 0.0\n")
                f.write("DOMAIN_MAX 1.0 1.0 1.0\n")
                for b in range(lut_size):
                    tile_x = b % tiles_per_row
                    tile_y = b // tiles_per_row
                    x_off = tile_x * lut_size
                    y_off = tile_y * lut_size
                    for g in range(lut_size):
                        for r in range(lut_size):
                            px = pixels[x_off + r, y_off + g]
                            f.write(
                                f"{px[0]/255.0:.6f} {px[1]/255.0:.6f} {px[2]/255.0:.6f}\n"
                            )

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _convert)
        except Exception as e:
            await status_msg.edit(content=f"❌ Conversion failed: {e}")
            return

        cube_size = os.path.getsize(cube_path)
        if cube_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output .cube file too large for Discord (>25 MB).")
            return

        try:
            await ctx.reply(
                content=f"✅ **png2lut** done! LUT size: {lut_size}³",
                file=discord.File(cube_path, filename="534gurts_thpng2lut.cube"),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Upload failed: {e}")


@bot.command(name="lut2png", aliases=["applylut", "applycube"])
async def lut2png_cmd(ctx: commands.Context, cube_url: str = ""):
    """Apply a .cube LUT file to an image or video via FFmpeg lut3d.

    Usage:
      th/lut2png [cube_url]

    Attach the media to process. Provide the .cube file as a second
    attachment OR pass its URL as the first argument.
    """
    # Resolve media source (first attachment, or from reply)
    media_source = None
    cube_att = None

    if ctx.message and ctx.message.attachments:
        media_source = ctx.message.attachments[0]
        if len(ctx.message.attachments) >= 2:
            cube_att = ctx.message.attachments[1]
    elif ctx.message and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                media_source = ref.attachments[0]
            else:
                for tok in ref.content.split():
                    if tok.startswith(("http://", "https://")):
                        media_source = tok
                        break
        except Exception:
            pass

    if not media_source:
        await ctx.reply(
            "**th/lut2png** — Apply a .cube LUT to image/video via FFmpeg\n"
            "Attach the media + the .cube file (two attachments), or attach\n"
            "media and pass the .cube URL as an argument.\n"
            "Example: `th/lut2png https://example.com/my.cube`"
        )
        return

    # Resolve .cube source
    cube_source_url = cube_url.strip()
    if cube_att:
        cube_source_url = cube_att.url
    if not cube_source_url:
        await ctx.reply("❌ Provide the .cube file as a second attachment or a URL argument.")
        return

    if isinstance(media_source, discord.Attachment):
        suffix = Path(media_source.filename).suffix.lower()
    else:
        suffix = Path(urllib.parse.urlparse(media_source).path).suffix.lower() or ".mp4"
    is_video = suffix in VIDEO_EXTENSIONS
    out_ext = get_output_ext(suffix, is_video) if suffix in SUPPORTED_EXTENSIONS else ".png"

    status_msg = await ctx.reply("⚙️ Applying LUT via FFmpeg lut3d…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"media{suffix}")
        cube_path = os.path.join(tmpdir, "lut.cube")
        output_path = os.path.join(tmpdir, f"lut2png{out_ext}")

        # Download media
        try:
            if isinstance(media_source, discord.Attachment):
                await download_attachment(media_source, input_path)
            else:
                await download_url(media_source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download media: {e}")
            return

        # Download .cube file
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(cube_source_url) as resp:
                    if resp.status != 200:
                        await status_msg.edit(content=f"❌ Failed to fetch .cube file (HTTP {resp.status}).")
                        return
                    cube_data = await resp.read()
            with open(cube_path, "wb") as f:
                f.write(cube_data)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download .cube file: {e}")
            return

        # Apply via FFmpeg lut3d
        escaped_cube = cube_path.replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"lut3d={escaped_cube}",
            output_path,
        ]
        loop = asyncio.get_event_loop()
        def _run_lut3d():
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode, result.stderr.decode("utf-8", errors="replace")
        try:
            rc, err = await loop.run_in_executor(None, _run_lut3d)
        except Exception as e:
            await status_msg.edit(content=f"❌ FFmpeg error: {e}")
            return

        if rc != 0:
            await status_msg.edit(content=f"❌ FFmpeg lut3d failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = f"534gurts_thlut2png{out_ext}"
        try:
            await ctx.reply(
                content="✅ **lut2png** — LUT applied!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Upload failed: {e}")


@bot.command(name="syncaudio", aliases=["sa", "sync"])
async def syncaudio_command(ctx: commands.Context, mode: str = ""):
    """Sync video and audio durations.

    Default: adjusts video speed to match audio.
    Alt mode: adjusts audio speed to match video.

    Usage:
      th/syncaudio         — adjust video speed to match audio
      th/syncaudio alt     — adjust audio speed to match video
      th/sa                — alias
      th/sync alt          — alias
    """
    alt_mode = mode.lower().strip() == "alt"

    # Resolve attachment: slash commands pass it as a parameter;
    # prefix commands need us to look at the message or referenced message.
    source = await _resolve_media_source(ctx)

    if source is None:
        mode_desc = "adjusts **video speed** to match audio" if not alt_mode else "adjusts **audio speed** to match video"
        await ctx.reply(
            "**IHTX Syncaudio**\n"
            f"Attach a video and use `th/syncaudio [alt]`.\n\n"
            f"Default: {mode_desc}\n"
            "Alt mode (`alt`): adjusts the other stream instead.\n\n"
            "Examples:\n"
            "```\n"
            "th/syncaudio         — video speed → match audio\n"
            "th/syncaudio alt     — audio speed → match video\n"
            "```\n"
            "Aliases: `th/sa`, `th/sync`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"Syncaudio requires a video file. Got `{suffix}`.")
        return

    mode_label = "alt (audio→video)" if alt_mode else "default (video→audio)"
    status_msg = await ctx.reply(
        f"⚙️ Running **syncaudio** ({mode_label})... this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_syncaudio.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, info = await loop.run_in_executor(
            None, _run_syncaudio,
            input_path, output_path, alt_mode
        )

        if not ok:
            await status_msg.edit(content=f"❌ Syncaudio failed:\n```\n{info[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output exceeds 10 MB — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thsyncaudio.mp4"
        try:
            await ctx.reply(
                content=f"✅ **IHTX syncaudio** ({mode_label}) applied!\n```\n{info}\n```",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")

@bot.command(name="swirl", aliases=["vortex"])
async def swirl_command(ctx: commands.Context, *, args: str = ""):
    """Apply a swirl/vortex distortion to an attached video or image.

    Usage:
      th/swirl <amount> [radius] [xc] [yc] [fallout] [is1to1]

    Parameters (space- or pipe-separated):
      amount    — twist multiplier (scaled by PI²×255/180 internally; negative = reverse). Required.
      radius    — normalized radius 0–1 of min(W,H) (default 0.5)
      xc        — horizontal center 0–1 (default 0.5)
      yc        — vertical center 0–1 (default 0.5)
      fallout   — attenuation curve: 'linear' or 'quad' (default quad)
      is1to1    — true/false, scale to square before swirl (default true)

    Examples:
      th/swirl 1
      th/swirl 2 0.5 0.5 0.5 quad true
      th/swirl -1 0.3 0.25 0.75 linear
    """
    tokens = re.split(r"[|\s]+", args.strip()) if args.strip() else []

    def _spf(idx, default):
        try:
            return float(tokens[idx]) if idx < len(tokens) else default
        except (ValueError, TypeError):
            return default

    def _sps(idx, default):
        return tokens[idx] if idx < len(tokens) else default

    if not tokens:
        await ctx.reply(
            "**th/swirl** — vortex/swirl distortion\n"
            "Attach a video or image and provide `amount` (twist multiplier).\n\n"
            "**Usage:** `th/swirl <amount> [radius] [xc] [yc] [fallout] [is1to1]`\n"
            "**Examples:** `th/swirl 1` · `th/swirl 2 0.5 0.5 0.5 quad` · `th/swirl -1 0.3 0.25 0.75 linear`\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 swirl=1`\n"
            "Full pipe syntax: `swirl=amount;radius;xc;yc;fallout;is1to1`\n"
            "Alias: `th/vortex`"
        )
        return

    strength = _spf(0, 1.0)
    radius   = _spf(1, 0.5)
    xc       = _spf(2, 0.5)
    yc       = _spf(3, 0.5)
    fallout  = _sps(4, "quad").lower()
    if fallout not in ("linear", "quad"):
        await ctx.reply("❌ `fallout` must be `linear` or `quad`.")
        return
    is1to1_raw = _sps(5, "true")
    is1to1 = is1to1_raw.lower() in ("1", "true", "t", "y", "yes", "+", "on")

    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "❌ Attach a video or image to use `th/swirl`.\n"
            "**Usage:** `th/swirl <strength> [radius] [xc] [yc] [fallout] [is1to1]`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply("❌ File too large (max 25 MB).")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    is_video = suffix in VIDEO_EXTENSIONS
    is_image = suffix in IMAGE_EXTENSIONS
    if not is_video and not is_image:
        await ctx.reply(f"❌ Unsupported file type `{suffix}`. Attach a video or image.")
        return

    status_msg = await ctx.reply(f"⏳ Applying swirl (amount={strength})…")

    out_suffix = suffix if is_image else ".mp4"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"swirl{out_suffix}")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_swirl,
            input_path, output_path,
            strength, radius, xc, yc, fallout, is1to1,
        )

        if not ok:
            await status_msg.edit(content=f"❌ Swirl failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **Swirl** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = f"534gurts_thswirl{out_suffix}"
        try:
            embed = discord.Embed(
                title="IHTX Bot — th/swirl",
                description=(
                    f"amount={strength} · radius={radius} · center=({xc},{yc}) · "
                    f"fallout={fallout} · 1:1={is1to1}"
                ),
                color=4886754,
            )
            pass  # no thumbnail
            embed.add_field(name="File Size", value=f"{out_size/(1024*1024):.2f} MB", inline=True)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")



@bot.command(name="freakzingatesteffect", aliases=["fzte", "freaktest"])
async def freakzingatesteffect_command(ctx: commands.Context, *, args: str = ""):
    """Apply the Freakzinga test effect to an attached video.

    Pipeline: invlum → huehsv → ccshue → channelblend → invlum →
              rotate → tvsim → wave → rotate → mirror=90|0.840 →
              mirror=right → mirror=bottom → ffmpeg (scale, negate,
              frame-numbered drawtext, negate, scale to 640x360) →
              mp3 (multi-pitch rubberband CLI).

    Usage:
      th/freakzingatesteffect
      th/fzte
      th/freaktest
    """
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**th/freakzingatesteffect** — apply the Freakzinga test effect.\n"
            "Attach a video and run `th/freakzingatesteffect`.\n"
            "Aliases: `th/fzte`, `th/freaktest`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply("❌ File too large (max 25 MB).")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"❌ `freakzingatesteffect` requires a video file. Got `{suffix}`.")
        return

    status_msg = await ctx.reply("⚙️ Running **Freakzinga test effect**… this may take a while.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "freakzinga_test.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        tokens = [p.strip() for p in re.split(r"[;|\s]+", args.strip()) if p.strip()] if args.strip() else []
        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_freakzinga_test_effect, input_path, output_path, tokens,
        )

        if not ok:
            await status_msg.edit(content=f"❌ Freakzinga test effect failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **Freakzinga test effect** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thfreakzinga_test.mp4"
        try:
            embed = discord.Embed(
                title="IHTX Bot — th/freakzingatesteffect",
                description="invlum→huehsv→ccshue→channelblend→invlum→rotate→tvsim→wave→rotate→mirror→mirror→mirror→ffmpeg→mp3",
                color=4886754,
            )
            pass  # no thumbnail
            embed.add_field(name="File Size", value=f"{out_size/(1024*1024):.2f} MB", inline=True)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="tvsim", aliases=["tv", "tvsimulator"])
async def tvsim_command(ctx: commands.Context, *, args: str = ""):
    """Apply a TV/CRT simulator effect to an attached video.

    Usage:
      th/tvsim <curvature> [line_sync] [detail_zoom] [vertical_sync] [phosphorescence] [interlacing] [aperture_grill] [static]

    Parameters (all separated by spaces or pipes):
      curvature      — 0-1, CRT warp strength (0=max curve, 1=flat/no warp). Required.
      line_sync      — zoom factor for interlace/scan filters + disp map Y-stretch (default 1)
      detail_zoom    — scroll speed; != 1 activates vertical scroll (default 1 = off)
      vertical_sync  — phosphor lutrgb tint strength (default 0 = off)
      phosphorescence — interlacing scanline darkening (default 0 = off)
      interlacing    — scan phasing ripple (default 0 = off)
      aperture_grill — grill PNG blend strength 0-1 (default 0 = off)
      static         — static MP4 blend strength 0-1 (default 0 = off)

    Examples:
      th/tvsim 0.5
      th/tvsim 0.3 1 1 0.4 0.5 0 0.6 0
      th/tvsim 0.5 1 1 0 0 0 0 1
    """
    # Parse params
    tokens = re.split(r"[|\s]+", args.strip()) if args.strip() else []

    def _tp(idx, default):
        try:
            return float(tokens[idx]) if idx < len(tokens) else default
        except (ValueError, TypeError):
            return default

    if not tokens:
        await ctx.reply(
            "**th/tvsim** — CRT/TV simulator effect\n"
            "Attach a video and provide `curvature` (0–1, required).\n\n"
            "**Usage:** `th/tvsim <curvature> [line_sync] [detail_zoom] [vert_sync] [phosphor] [interlace] [aperture_grill] [static]`\n"
            "**Example:** `th/tvsim 0.5`\n"
            "**Full example:** `th/tvsim 0.3 1 1 0.4 0.5 0 0.6 0`\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 tvsim=0.5`\n"
            "Aliases: `th/tv` `th/tvsimulator`"
        )
        return

    curvature = _tp(0, 0.5)
    if not (0.0 <= curvature <= 1.0):
        await ctx.reply("❌ `curvature` must be between 0 and 1.")
        return

    line_sync       = _tp(1, 1.0)
    detail_zoom     = _tp(2, 1.0)
    vertical_sync   = _tp(3, 0.0)
    phosphorescence = _tp(4, 0.0)
    interlacing     = _tp(5, 0.0)
    aperture_grill  = _tp(6, 0.0)
    static_noise    = _tp(7, 0.0)

    # Resolve attachment
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "❌ Attach a video to use `th/tvsim`.\n"
            "**Usage:** `th/tvsim <curvature> [line_sync] [detail_zoom] [vert_sync] [phosphor] [interlace] [aperture_grill] [static]`"
        )
        return

    if source.size > MAX_FILE_SIZE:
        await ctx.reply(f"❌ File too large (max 25 MB).")
        return

    suffix = Path(source.filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"❌ `th/tvsim` requires a video file. Got `{suffix}`.")
        return

    param_str = f"curvature={curvature}"
    status_msg = await ctx.reply(f"⏳ Applying TV simulator ({param_str})…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "tvsim.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_tvsim,
            input_path, output_path,
            curvature, line_sync, detail_zoom,
            vertical_sync, phosphorescence, interlacing,
            aperture_grill, static_noise,
        )

        if not ok:
            await status_msg.edit(content=f"❌ TV simulator failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **TV Simulator** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large for Discord (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thtvsim.mp4"
        try:
            embed = discord.Embed(
                title="IHTX Bot — th/tvsim",
                description=(
                    f"curvature={curvature} · line_sync={line_sync} · scroll={detail_zoom} · "
                    f"phosphor={vertical_sync} · interlace={phosphorescence} · scan={interlacing} · "
                    f"aperture={aperture_grill} · static={static_noise}"
                ),
                color=11578404,
            )
            pass  # no thumbnail
            embed.add_field(name="File Size", value=f"{out_size/(1024*1024):.2f} MB", inline=True)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="folkvalley", aliases=["fv", "folk"])
async def folkvalley_command(ctx: commands.Context):
    """Apply the folkvalley aesthetic effect to an attached video.

    Replaces the audio with the folkvalley music track, boosts brightness
    (HSV value shift), and overlays a decorative image scaled to fit the frame.

    Usage:
      th/folkvalley
      th/fv

    No parameters — the effect is fixed.
    """
    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**th/folkvalley** — dreamy aesthetic effect\n"
            "Attaches folkvalley music, boosts brightness, and adds a decorative overlay.\n\n"
            "**Usage:** `th/folkvalley` (attach a video)\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 folkvalley`\n"
            "Aliases: `th/fv` `th/folk`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply("❌ File too large (max 25 MB).")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"❌ `th/folkvalley` requires a video file. Got `{suffix}`.")
        return

    status_msg = await ctx.reply("⏳ Applying folkvalley effect…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "folkvalley.mp4")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(None, _run_folkvalley, input_path, output_path)

        if not ok:
            await status_msg.edit(content=f"❌ folkvalley failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **folkvalley** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large for Discord (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thfolkvalley.mp4"
        try:
            embed = discord.Embed(
                title="IHTX Bot — th/folkvalley",
                description="Music replacement · brightness boost (HSV V+100) · decorative overlay",
                color=0x40E0D0,
            )
            pass  # no thumbnail
            embed.add_field(name="File Size", value=f"{out_size / (1024 * 1024):.2f} MB", inline=True)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="vocoder", aliases=["vocode"])
async def vocoder_command(ctx: commands.Context, *, args: str = ""):
    """FFT phase vocoder — shape a carrier sound with your video's voice envelope.

    Usage:
      th/vocoder <carrier_url>                        — ilvocodex mode (default)
      th/vocoder <mode> <carrier_url>                 — specify mode
      th/vocoder <mode> <bandwidth> <carrier_url>     — mode + custom band count

    Modes: ilvocodex | orangevocoder | 4ormulator | audacity | magix
    carrier_url: direct link to any audio file (mp3, wav, ogg…)

    Pipe effects: vocoder=mode;url  |  ilvocodex=url  |  4ormulator=url  |  magix=url
    """
    parts = args.strip().split() if args.strip() else []

    if not parts:
        lines = [
            "**th/vocoder** — FFT phase vocoder",
            "Shape a carrier sound (synth, pad, instrument) with the frequency envelope of your video's audio.",
            "",
            "**Usage:**",
            "`th/vocoder <carrier_url>` — ilvocodex mode",
            "`th/vocoder <mode> <carrier_url>` — specify mode",
            "`th/vocoder <mode> <bandwidth> <carrier_url>` — mode + band count",
            "",
            f"**Modes:** `{'` · `'.join(_VOCODER_PROFILES)}`",
            "**Alias:** `th/vocode`",
            "**As pipe effect:** `th/ihtx 1 5 - mp4 vocoder=ilvocodex;https://url`",
            "Mode shortcuts: `ilvocodex=url` `orangevocoder=url` `4ormulator=url` `audacity=url` `magix=url`",
        ]
        await ctx.reply("\n".join(lines))
        return

    # Parse: [mode] [bandwidth] <url>
    mode = "ilvocodex"
    bandwidth: int | None = None
    carrier_url = ""

    if parts[0].lower() in _VOCODER_PROFILES:
        mode = parts[0].lower()
        parts = parts[1:]
    if parts:
        try:
            bandwidth = int(parts[0])
            parts = parts[1:]
        except ValueError:
            pass
    carrier_url = parts[0] if parts else ""

    if not carrier_url:
        await ctx.reply("❌ Provide a carrier audio URL. Example: `th/vocoder ilvocodex https://example.com/pad.mp3`")
        return

    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply("❌ Attach a video (or reply to one) for the vocoder to process.")
        return

    bw_display = bandwidth if bandwidth else _VOCODER_PROFILES[mode]["bandwidth"]
    status_msg = await ctx.reply(
        f"🎙️ Vocoding `{source.filename}` — mode: `{mode}`, bands: `{bw_display}`…"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, source.filename)
        output_path = os.path.join(tmpdir, "534gurts_thvocoder.mp4")

        try:
            file_bytes = await attachment.read()
            with open(input_path, "wb") as fh:
                fh.write(file_bytes)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download attachment: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_vocoder, input_path, output_path, carrier_url, mode, bandwidth
        )

        if not ok:
            await status_msg.edit(content=f"❌ Vocoder failed:\n```\n{err[-1200:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **vocoder** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large for Discord (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thvocoder.mp4"
        try:
            embed = discord.Embed(
                title="IHTX Bot — th/vocoder",
                description=f"Mode: `{mode}` · Bands: `{bw_display}` · Python FFT phase vocoder",
                color=0x40E0D0,
            )
            embed.add_field(name="File Size", value=f"{out_size / (1024 * 1024):.2f} MB", inline=True)
            embed.add_field(name="Carrier", value=carrier_url[:80], inline=False)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="sidechaingate_vocoder", aliases=["scgv"])
async def scgv_command(ctx: commands.Context, *, args: str = ""):
    """Sidechaingate vocoder — shape a carrier with the frequency envelope of your video/audio.

    Usage:
      th/scgv <carrier_url>
      th/scgv <carrier_url> <bandwidth>
      th/scgv <carrier_url> <bw> <ratio> <threshold> <release> <attack> <makeup> <knee> <detection> <range> <volume> <pitch>

    Defaults: bw=64, ratio=2, threshold=1, release=50, attack=0.01, makeup=1, knee=8, detection=peak, range=0, volume=1, pitch=0

    Pipe effect: scgv=https://carrier_url[;bw[;ratio[;threshold[;release[;attack[;makeup[;knee[;detection[;range[;volume[;pitch]]]]]]]]]]]]
    """
    parts = args.strip().split() if args.strip() else []

    if not parts:
        lines = [
            "**th/scgv** — Sidechaingate Vocoder",
            "Shape a carrier sound with the frequency envelope of your video/audio using FFmpeg `firequalizer` + `sidechaingate`.",
            "",
            "**Usage:**",
            "`th/scgv <carrier_url>` — default params (64 bands)",
            "`th/scgv <carrier_url> <bandwidth>` — custom band count",
            "`th/scgv <carrier_url> <bw> <ratio> <threshold> <release> <attack> <makeup> <knee> <detection> <range> <volume> <pitch>`",
            "",
            "**Defaults:** bw=64 · ratio=2 · threshold=1 · release=50ms · attack=0.01ms · makeup=1 · knee=8 · detection=peak · range=0 · volume=1 · pitch=0",
            "**Aliases:** `th/sidechaingate_vocoder`",
            "**As pipe effect:** `scgv=https://carrier_url` · `scgv=url;bw;ratio;threshold;release;attack;makeup;knee;detection;range;volume;pitch`",
        ]
        await ctx.reply("\n".join(lines))
        return

    carrier_url = parts[0]

    def _pf(idx: int, default: float) -> float:
        try:
            return float(parts[idx])
        except (IndexError, ValueError):
            return default

    bandwidth  = int(_pf(1, 64))
    ratio      = _pf(2, 2.0)
    threshold  = _pf(3, 1.0)
    release    = _pf(4, 50.0)
    attack     = _pf(5, 0.01)
    makeup     = _pf(6, 1.0)
    knee       = _pf(7, 8.0)
    detection  = parts[8] if len(parts) > 8 else "peak"
    range_val  = _pf(9, 0.0)
    volume     = _pf(10, 1.0)
    pitch      = _pf(11, 0.0)

    source = await _resolve_media_source(ctx)
    if source is None:
        await ctx.reply("❌ Attach or reply to a video/audio file.")
        return

    status_msg = await ctx.reply(
        f"⚙️ **scgv** — {bandwidth} bands · ratio={ratio} · detection={detection}… this may take a while."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        if isinstance(source, discord.Attachment):
            suffix = Path(source.filename).suffix.lower() or ".mp4"
            input_path = os.path.join(tmpdir, f"input{suffix}")
            stem = Path(source.filename).stem
            try:
                await download_attachment(source, input_path)
            except Exception as e:
                await status_msg.edit(content=f"❌ Download failed: {e}")
                return
        else:
            ext = os.path.splitext(source.split("?")[0])[-1].lower() or ".mp4"
            input_path = os.path.join(tmpdir, f"input{ext}")
            stem = "media"
            try:
                await download_url(source, input_path)
            except Exception as e:
                await status_msg.edit(content=f"❌ Download failed: {e}")
                return

        output_path = os.path.join(tmpdir, "534gurts_thscgv.mp4")

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_scgv, input_path, output_path, carrier_url,
            bandwidth, detection, release, attack, ratio, threshold,
            makeup, knee, pitch, range_val, volume,
        )

        if not ok:
            await status_msg.edit(content=f"❌ scgv failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > CATBOX_THRESHOLD:
            await status_msg.edit(content="⬆️ Output too large — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ **scgv** done! [Download]({cb_url})\n{cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large (>25 MB) and Catbox upload failed.")
            return

        out_filename = "534gurts_thscgv.mp4"
        try:
            embed = discord.Embed(
                title="IHTX Bot — th/scgv",
                description=(
                    f"Bands: `{bandwidth}` · Ratio: `{ratio}` · Threshold: `{threshold}` · "
                    f"Detection: `{detection}`\n"
                    f"Release: `{release}ms` · Attack: `{attack}ms` · Makeup: `{makeup}` · "
                    f"Knee: `{knee}` · Volume: `{volume}`"
                    + (f" · Pitch: `{pitch:+.2f}st`" if pitch != 0 else "")
                ),
                color=0x40E0D0,
            )
            embed.add_field(name="File Size", value=f"{out_size / (1024 * 1024):.2f} MB", inline=True)
            embed.add_field(name="Carrier", value=carrier_url[:80], inline=False)
            await ctx.reply(embed=embed, file=discord.File(output_path, filename=out_filename))
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="presets", aliases=["effects", "list"])
async def presets_command(ctx: commands.Context):
    """List all available IHTX presets."""
    lines = [f"`{name}` — {PRESET_FILTERS[name]['vf'] or PRESET_FILTERS[name]['complex']}" for name in sorted(PRESET_FILTERS)]
    embed = discord.Embed(
        title="IHTX Bot — Available Presets",
        description="\n".join(lines),
        color=0x40E0D0,
    )
    embed.add_field(
        name="Usage",
        value="Attach a video or image and run:\n`th/ihtx [preset]`\n\nDefault preset: `chaos`",
        inline=False,
    )
    embed.set_footer(text="I Hate The X — FFmpeg logo destruction bot")
    await ctx.reply(embed=embed)


# ── Help preview images ───────────────────────────────────────────────────────
# Maps a substring of an entry "name" → local preview filename.
# Matched with `any(k in entry["name"] for k in ...)`.
_HELP_ENTRY_PREVIEWS: dict[str, str] = {
    # presets / ihtx
    "th/ihtx [preset]":              "chaos.gif",
    "glitch":                        "glitch.gif",
    # pipe effects
    "wave pipe":                     "wave.gif",
    "shake pipe":                    "shake_pipe.gif",
    "ripple pipe":                   "ripple.gif",
    "pan pipe":                      "pan.png",
    "tile pipe":                     "tile.png",
    "scroll pipe":                   "pan.png",
    "leftsplit":                     "mirror.png",
    "zoom pipe":                     "zoom.png",
    "th/swirl":                      "swirl.png",
    "swirl pipe":                    "swirl.png",
    "th/tvsim":                      "corrupt.gif",
    "th/invlum":                     "invlum.png",
    "th/huehsv":                     "saturation.png",
    "th/mirror":                     "mirror.png",
}

_HELP_PREVIEW_DIR = Path("bot/help_previews")


def _help_preview_filename(entry_name: str, cat: str | None) -> str:
    """Return the local preview filename for an entry, if one exists."""
    return next(
        (filename for key, filename in _HELP_ENTRY_PREVIEWS.items() if key in entry_name),
        "",
    )


def _help_preview_file(entry_name: str, cat: str | None) -> discord.File | None:
    filename = _help_preview_filename(entry_name, cat)
    path = _HELP_PREVIEW_DIR / filename if filename else None
    if path is not None and path.exists():
        return discord.File(str(path), filename=filename)
    return None

# ── Help data ─────────────────────────────────────────────────────────────────
# Each entry: {"name": str, "value": str, "cat": "heavy"|"fun"|"owner"}
# "name" and "value" are searched when the user passes a query.
_HELP_ENTRIES: list[dict] = [
    # ── Heavy ──
    {
        "cat": "heavy",
        "name": "th/ihtx [preset]",
        "value": (
            "Apply a preset to an attached video/image. Default preset: `chaos`\n"
            "Other presets: `glitch`, `melt`, `chaos2`, `vhs`, … — run `th/presets` for the full list."
        ),
    },
    {
        "cat": "heavy",
        "name": "th/ihtx <reps> <dur> <noTrim> <fmt> <effects>",
        "value": (
            "Custom effect chain (comma-delimited). Each effect may have `=` params.\n"
            "**Example:** `th/ihtx 10 0.483 - mp4 huehsv=0.5,negate,multipitch=25|5|8.5`\n"
            "**Raw FFmpeg step:** `th/ihtx 1 10 false mp4 ffmpeg(-vf hue=h=50),speed=1.5`"
        ),
    },
    {
        "cat": "heavy",
        "name": "Pipe effects (comma-separated)",
        "value": (
            "**Video:** `hflip` `vflip` `negate` `grayscale` `sepia` `rotate=<deg>` "
            "`huehsv=hue|sat|lightness|colorspace|betterfully` `ccshue=hue|sat|gamma|gain|offset` `brightness=<val>` `contrast=<val>` "
            "`saturation=<val>` `swapuv` `invlum` `invertrgb=r;g;b` `gm91deform` `randomjitter=<strength>`\n"
            "**Distortion:** `mirror=<deg|preset>` `zoom=<amt>` (≥ 1 = zoom in, < 1 = zoom out) `ripple=spd|freq|amp|phase` `pan=px|py` `tile=tx|ty` `pinch&punch=str;r;cx;cy` `shake=<h>|<v>` `wave=hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase[|sep][|noclip]` `spherize=amount|radius|cx|cy`\n"
            "**Scroll:** `scroll=hpos=V` · `scroll=hpos=V;ypos=V` · `scroll=h;v` (continuous) · `scroll=x1:y1:x2:y2[:dur]` (animated pan)\n"
            "**Split:** `leftsplit(<inner_effects>)` · `rightsplit(<inner_effects>)` — apply inner effects to one half, mirror/combine\n"
            "**Reverse:** `vreverse` (video frames) · `areverse` (audio)\n"
             "**Audio:** `multipitch=semis` `pitchtransition=start,end[;start,end]` `volume=<val>` `vibrato=freq;depth` `syncaudio` `vocoder=mode;url` `ilvocodex=url` `orangevocoder=url` `4ormulator=url` `audacity=url`\n"
            "**CRT:** `tvsim=curvature[;line_sync;detail_zoom;vert_sync;phosphor;interlace;aperture_grill;static]`\n"
            "**Swirl:** `swirl=strength[;radius;xc;yc;fallout;is1to1]`\n"
            "**Aesthetics:** `folkvalley` / `fv` — music replacement + brightness + overlay\n"
            "**Color:** `labadjust=l;a;b` (negate Lab channels; each 0 or 1)\n"
            "**Overlay:** `nepeta[=url]` (cat-ear PNG or custom image scaled to video) `watermark=<url>` `ring[=url]` `miui` `reddit` `caption=<text>`\n"
            "**Raw / FX:** `ffmpeg(<args>)` `frei0r=plugin:params` `lut=<url>` `speed=<factor>`"
        ),
    },
    {
        "cat": "heavy",
        "name": "Newer filters & plugins (scgv, gradientmap, frei0r…)",
        "value": (
            "Newer IHTX effects are still used as comma-separated pipe effects; put each effect in the chain where it should run.\n"
            "**Vocoder:** `scgv=<carrier_url>[;bands;ratio;threshold;release;attack;makeup;knee;detection;range;volume;pitch]` "
            "— example: `scgv=https://example.com/carrier.mp3;64;2;1;50;0.01;1;8;peak;0;1;0`.\n"
            "**Gradient map:** `gradientmap=R,G,B[,A[,position]];R,G,B[,A[,position]]…` "
            "— example: `gradientmap=0,0,0,0,0;255,80,20,255,1` (also `gmap`). "
            "Stops need at least two colors; RGB is 0–255 and position is 0–1.\n"
            "**Lab adjustment:** `labadjust=L;A;B` (also `labadj`) — each channel is `0` or `1`; "
            "example: `labadjust=1;0;1`.\n"
            "**Wave distortion:** `wave=hSpeed|hFreq|hAmp|hPhase|vSpeed|vFreq|vAmp|vPhase[|separate|noclip]` "
            "— example: `wave=1|1|2|0|1|1|2|0|1|1`.\n"
            "**Installed frei0r plugins:** `frei0r=plugin:param:param` — example: "
            "`frei0r=distort0r:*T`. Plugin names depend on the bot host; an unavailable plugin returns an FFmpeg error.\n"
            "**Full example:** `th/ihtx 3 1.0 - mp4 gradientmap=0,0,0,0,0;255,80,20,255,1,wave=1|1|2|0|1|1|2|0`"
        ),
    },
    {
        "cat": "heavy",
        "name": "th/ffmpeg <args>",
        "value": (
            "Run raw FFmpeg on an attachment. Args go between `-i input` and `output`.\n"
            "Example: `th/ffmpeg -vf negate` · `th/ffmpeg -af volume=2.0`\n"
            "Shows error log and elapsed time in the reply."
        ),
    },
    {
        "cat": "heavy",
        "name": "ccshue pipe effect  (hue|sat|gamma|gain|offset)",
        "value": (
            "Full color correction via ImageMagick haldclut. All params optional (defaults shown):\n"
            "`ccshue=0|1|1|1|0`\n"
            "• **hue** — rotation in degrees −180…180 (default 0)\n"
            "• **sat** — saturation multiplier (default 1.0)\n"
            "• **gamma** — gamma correction (default 1.0)\n"
            "• **gain** — RGB gain/multiply (default 1.0)\n"
            "• **offset** — add to all channels −1…1 (default 0)\n"
            "Example: `th/ihtx 1 5 - mp4 ccshue=90|1.5|1.2|1|0`"
        ),
    },
    {
        "cat": "heavy",
        "name": "frei0r pipe effect  (frei0r=plugin:params)",
        "value": (
            "Apply any installed frei0r video effect plugin via FFmpeg.\n"
            "Params are colon-separated floats/strings per the plugin spec.\n"
            "Common plugins: `distort0r` `cartoon` `edgeglow` `pixelize` `plasma` `sobel` `threshold0r`\n"
            "Example: `th/ihtx 1 5 - mp4 frei0r=distort0r:0.5:0.1`\n"
            "Also available in tags: `{frei0r:distort0r:0.5}` or `frei0r:\\ndistort0r:0.5` prefix block"
        ),
    },
    {
        "cat": "heavy",
        "name": "wave pipe effect  (wave=hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase[|sep][|noclip])",
        "value": (
            "Sinusoidal pixel-displacement wave distortion using geq. All params optional.\n"
            "• **hSpd/hFreq/hAmp/hPhase** — horizontal wave speed, frequency, amplitude, phase (defaults: 1|1|1|0)\n"
            "• **vSpd/vFreq/vAmp/vPhase** — vertical wave speed, frequency, amplitude, phase (defaults: 1|1|1|0)\n"
            "• **sep** — apply H and V waves as separate passes (pass `1` to enable)\n"
            "• **noclip** — draw a border box to prevent pixel clipping at edges (pass `1` to enable)\n"
            "Example (default): `th/ihtx 3 1.0 - mp4 wave`\n"
            "Example (custom): `th/ihtx 3 1.0 - mp4 wave=2|1|1.5|0|1|2|1|0`\n"
            "Example (separate passes + noclip): `th/ihtx 3 1.0 - mp4 wave=1|1|1|0|1|1|1|0|1|1`"
        ),
    },
    {
        "cat": "heavy",
        "name": "shake pipe effect  (shake=<h>|<v>)",
        "value": (
            "Random per-frame pixel displacement shake using geq. Crops output back to original dimensions.\n"
            "• **h** — horizontal shake strength in pixels (default 3)\n"
            "• **v** — vertical shake strength in pixels (default 0)\n"
            "Example: `th/ihtx 3 1.0 - mp4 shake=3`\n"
            "Example with both axes: `th/ihtx 3 1.0 - mp4 shake=5|3`"
        ),
    },
    {
        "cat": "heavy",
        "name": "ripple pipe effect  (ripple=spd|freq|amp|phase)",
        "value": (
            "Radial displacement distortion using geq with sinusoidal ripple around the center.\\n"
            "\u2022 **spd** \u2014 animation speed (default 1.0)\\n"
            "\u2022 **freq** \u2014 ripple frequency (default 30.0)\\n"
            "\u2022 **amp** \u2014 displacement amplitude in pixels (default 10.0)\\n"
            "\u2022 **phase** \u2014 initial phase offset (default 0.0)\\n"
            "Example: `th/ihtx 3 1.0 - mp4 ripple`\\n"
            "Example (custom): `th/ihtx 3 1.0 - mp4 ripple=2|20|15|0`"
        ),
    },
    {
        "cat": "heavy",
        "name": "pan pipe effect  (pan=px|py)",
        "value": (
            "Simple pixel offset panning using geq with boundary clipping.\\n"
            "\u2022 **px** \u2014 horizontal pixel offset (default 0)\\n"
            "\u2022 **py** \u2014 vertical pixel offset (default 0)\\n"
            "Example: `th/ihtx 3 1.0 - mp4 pan=50|30`\\n"
            "Example (horizontal only): `th/ihtx 3 1.0 - mp4 pan=100`"
        ),
    },
    {
        "cat": "heavy",
        "name": "tile pipe effect  (tile=tx|ty)",
        "value": (
            "Repetitive tiling effect using geq mod expressions. Repeats the frame tx\u00d7ty times.\\n"
            "\u2022 **tx** \u2014 horizontal tile count (default 2)\\n"
            "\u2022 **ty** \u2014 vertical tile count (default 2)\\n"
            "Example: `th/ihtx 3 1.0 - mp4 tile`\\n"
            "Example (3\u00d73): `th/ihtx 3 1.0 - mp4 tile=3|3`"
        ),
    },
    {
        "cat": "heavy",
        "name": "scroll pipe effect  (scroll=...)",
        "value": (
            "Multi-mode scroll/pan effect with three variants:\\n"
            "\u2022 **Named params:** `scroll=hpos=0.5` or `scroll=hpos=0.5;ypos=0.3` \u2014 FFmpeg native scroll filter\\n"
            "\u2022 **Continuous:** `scroll=h;v` \u2014 0.0\u20131.0 speed per axis\\n"
            "\u2022 **Animated pan:** `scroll=x1:y1:x2:y2[:dur]` \u2014 geq-based time-dependent pan\\n"
            "Example: `th/ihtx 3 1.0 - mp4 scroll=hpos=0.5`\\n"
            "Example (animated): `th/ihtx 3 1.0 - mp4 scroll=0:0:100:50:5`"
        ),
    },
    {
        "cat": "heavy",
        "name": "leftsplit / rightsplit pipe effects",
        "value": (
            "Split the video in half, apply inner effects to one half, then recombine.\\n"
            "\u2022 **leftsplit(<effects>)** \u2014 apply inner effects to left half, then hflip+hstack with right half\\n"
            "\u2022 **rightsplit(<effects>)** \u2014 apply inner effects to right half, then hstack with left half\\n"
            "Example: `th/ihtx 3 1.0 - mp4 leftsplit(grayscale)`\\n"
            "Example (chained): `th/ihtx 3 1.0 - mp4 rightsplit(huehsv=0.5,brightness=0.2)`"
        ),
    },
    {
        "cat": "heavy",
        "name": "zoom pipe effect  (zoom=<amt>)",
        "value": (
            "Scale+crop zoom effect. Scales up by `amt` then crops back to original size (center crop).\\n"
            "\u2022 **amt** \u2014 zoom multiplier (default 2.0, must be > 0.1)\\n"
            "Example: `th/ihtx 3 1.0 - mp4 zoom=2`\\n"
            "Example (subtle): `th/ihtx 3 1.0 - mp4 zoom=1.5`"
        ),
    },
    {
        "cat": "heavy",
        "name": "nepeta pipe effect  (nepeta[=url])",
        "value": (
            "Overlay the Nepeta cat-ear PNG (or a custom image URL) scaled to fit the video dimensions.\\n"
            "The image loops for the entire video duration; -shortest ensures the output ends when the video track ends.\\n"
            "\u2022 **url** (optional) \u2014 custom PNG/JPG overlay URL (default: Nepeta cat-ear image)\\n"
            "Example: `th/ihtx 1 5 - mp4 nepeta`\\n"
            "Example (custom): `th/ihtx 1 5 - mp4 nepeta=https://example.com/my-overlay.png`"
        ),
    },
    {
        "cat": "heavy",
        "name": "vreverse / areverse pipe effects",
        "value": (
            "Reverse video frames or audio independently.\n"
            "• **`vreverse`** — reverses video frames only (audio unaffected)\n"
            "• **`areverse`** — reverses audio only (video unaffected)\n"
            "Chain both to fully reverse: `th/ihtx 1 5 - mp4 vreverse,areverse`\n"
            "Note: `vreverse` loads all frames into memory — keep clips short."
        ),
    },
    {
        "cat": "heavy",
        "name": "th/swirl <strength> [...]  (alias: vortex)",
        "value": (
            "Apply a vortex/swirl distortion to a video or image using FFmpeg geq.\n"
            "**Parameters** (space- or pipe-separated):\n"
            "• `strength` — swirl angle in degrees (negative = reverse spin). **Required.**\n"
            "• `radius` — normalized radius 0–1 of min(W,H) where swirl reaches (default 0.5)\n"
            "• `xc` / `yc` — normalized center position 0–1 (default 0.5 = center)\n"
            "• `fallout` — attenuation curve: `linear` or `quad` (default `quad`)\n"
            "• `is1to1` — `true`/`false`, scale to square before swirl then restore (default `true`)\n\n"
            "**Examples:**\n"
            "`th/swirl 180` — half-turn swirl from center\n"
            "`th/swirl 360 0.5 0.5 0.5 quad` — full spin, quadratic falloff\n"
            "`th/swirl -90 0.3 0.25 0.75 linear` — reverse swirl, off-center, linear falloff\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 swirl=180`\n"
            "Full pipe syntax: `swirl=strength;radius;xc;yc;fallout;is1to1`"
        ),
    },
    {
        "cat": "heavy",
        "name": "th/folkvalley  (aliases: fv, folk)",
        "value": (
            "Apply the **folkvalley** aesthetic to a video:\n"
            "• Replaces the audio with the folkvalley music track\n"
            "• Boosts brightness (HSV value shift: H=0 S=0 V+100)\n"
            "• Overlays a decorative image scaled to fit the frame\n\n"
            "**Usage:** `th/folkvalley` (attach a video) — no parameters needed\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 folkvalley`\n"
            "Pipe alias: `fv`  ·  Command aliases: `th/fv` `th/folk`"
        ),
    },
    {
        "cat": "heavy",
        "name": "th/vocoder [mode] [bw] <carrier_url>  (alias: vocode)",
        "value": (
            "FFT phase vocoder — shapes a carrier sound using your video's voice envelope.\n"
            "Pure Python/numpy port of vocoder.ts. No Wine/exe needed.\n\n"
            "**Modes:** `ilvocodex` (default) · `orangevocoder` · `4ormulator` · `audacity`\n"
            "**carrier_url:** direct link to any audio (mp3, wav, ogg…)\n\n"
            "**Examples:**\n"
            "`th/vocoder https://url/pad.mp3` — ilvocodex mode\n"
            "`th/vocoder orangevocoder https://url/synth.wav` — specify mode\n"
            "`th/vocoder 4ormulator 64 https://url/drone.mp3` — mode + band count\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 vocoder=ilvocodex;https://url`\n"
            "Mode shortcuts: `ilvocodex=url` `orangevocoder=url` `4ormulator=url` `audacity=url`"
        ),
    },
    {
        "cat": "heavy",
        "name": "th/tvsim <curvature> [...]  (aliases: tv, tvsimulator)",
        "value": (
            "Apply a CRT/TV simulator effect using an FFmpeg displacement map.\n"
            "**Parameters** (space- or pipe-separated):\n"
            "• `curvature` — 0–1, warp strength. 0 = max CRT curve, 1 = flat/no displacement. **Required.**\n"
            "• `line_sync` — zoom factor for interlace/scan filters + disp map Y-stretch (default 1)\n"
            "• `detail_zoom` — scroll speed; != 1 activates vertical scroll (default 1 = off)\n"
            "• `vertical_sync` — phosphor lutrgb tint strength (default 0 = off)\n"
            "• `phosphorescence` — interlacing scanline darkening 0–1 (default 0 = off)\n"
            "• `interlacing` — scan phasing ripple 0–1 (default 0 = off)\n"
            "• `aperture_grill` — Trinitron-style vertical phosphor stripe mask 0–1 (default 0 = off)\n"
            "• `static` — TV static MP4 blend strength 0–1 (default 0 = off)\n\n"
            "**Examples:**\n"
            "`th/tvsim 0.5` — moderate CRT warp\n"
            "`th/tvsim 0.3 1 1 0.4 0.5 0 0.6 0` — warp + phosphor + interlace + aperture grill\n"
            "`th/tvsim 0.5 1 1 0 0 0 0 1` — warp + full static\n"
            "**As pipe effect:** `th/ihtx 1 5 - mp4 tvsim=0.5`\n"
            "Full pipe syntax: `tvsim=curvature;line_sync;detail_zoom;vert_sync;phosphor;interlace;aperture_grill;static`"
        ),
    },
    {
        "cat": "fun",
        "name": "th/multipitch <semitones>  (aliases: mp, multi)",
        "value": (
            "Multi-voice pitch shift via Rubber Band R3.\n"
            "Pipe-separated semitones: `th/multipitch 25|5|8.5`\n"
            "Or inline: `th/ihtx 1 10 false mp4 multipitch=25|5|8.5`"
        ),
    },
    {
        "cat": "heavy",
        "name": "th/ihtxsap  (aliases: sap)",
        "value": (
            "Audio-only iterative IHTX. Repetitions, duration, pitch set, style, volume.\n"
            "Positional: `th/ihtxsap 5 0.7 -7;5;6 \"Rubberband R3\" volume=4`\n"
            "Keyword: `th/ihtxsap pitchstyle=\"Rubberband Custom\" pitches=-7;8;-4 repetitions=20 duration=0.4 volume=1.3 rubberbandcustom=\"-3 --centre-focus\"`\n"
            "**Styles:** `Rubberband R2`, `Rubberband R3`, `Soundtouch`, `Bungee`, `Rubberband Custom`\n"
            "**Rubberband Custom flags** (inserted before `-p<st>`):\n"
            "`-2` / `--fast` — R2 engine · `-3` / `--fine` — R3 engine\n"
            "`-F` / `--formant` — preserve formants\n"
            "`--centre-focus` — preserve stereo centre focus\n"
            "`-c <N>` / `--crisp <N>` — crispness 0–6 (R2 only)\n"
            "Example: `rubberbandcustom=\"-3 -F\"`"
        ),
    },
    {
        "cat": "fun",
        "name": "th/preview1280 [start] [dur]  (aliases: p1280, pv1280)",
        "value": "12-segment TV-simulator montage. Defaults: start=1.85, dur=0.85",
    },
    {
        "cat": "fun",
        "name": "th/oppositep1280 [start] [dur]  (aliases: op1280, opposite, opposite1280)",
        "value": "Inverse TV-simulator montage: all hue shifts negated, all pitch shifts inverted vs preview1280. Defaults: start=1.85, dur=0.85",
    },
    {
        "cat": "fun",
        "name": "th/preview1280with640x360resize [start] [dur]  (aliases: p1280ff!3, p1280w16:9r)",
        "value": "Same 12-segment TV-simulator montage as preview1280 but the final output is locked to **640×360** regardless of input resolution. Defaults: start=1.85, dur=0.85",
    },
    {
        "cat": "fun",
        "name": "th/preview1280what [start] [dur] [target_len] [use_tempo]  (aliases: p1280what, p1280fev8v2plus)",
        "value": (
            "**28-segment** TV-simulator extended montage (FFmpeg Extended v8 v2+).\n"
            "4 full-length segs + 23 half-length segs + 1 looping long seg.\n"
            "Defaults: start=1.85 · dur=0.85 · target_len=5 · use_tempo=false\n"
            "Pass `true` as 4th arg to enable tempo-stretching via rubberband.\n"
            "Output: `.mov` (pwhatextended). Use .t sync+ to sync to audio."
        ),
    },
    {
        "cat": "heavy",
        "name": "th/invlum [n]",
        "value": "Apply luma-inversion progressively N times and concat all iterations.",
    },
    {
        "cat": "heavy",
        "name": "th/pipetest <effect1;effect2;...>  (aliases: pt)",
        "value": "One-shot pipe effect runner. Try `th/pipetest stretch=1.5;negate`.",
    },
    {
        "cat": "heavy",
        "name": "th/freakzingatesteffect  (aliases: fzte, freaktest)",
        "value": "Full preset: invlum → huehsv → ccshue → channelblend → rotate → tvsim → wave → mirror → drawtext/negate → mp3.",
    },
    {
        "cat": "heavy",
        "name": "th/lexg  (aliases: lastexportgrab)",
        "value": "Re-apply the last `th/ihtx` export to a new attachment using the same effect chain.",
    },
    {
        "cat": "heavy",
        "name": "th/download <URL>  (aliases: dl)",
        "value": (
            "Download media from any URL including Discord app/attachment links.\n"
            "Supports direct CDN links, Discord media URLs, and any site yt-dlp handles.\n"
            "Files ≤8 MB are sent directly; larger files are uploaded to Catbox.\n"
            "Example: `th/download https://cdn.discordapp.com/attachments/.../video.mp4`"
        ),
    },
    # ── Fun ──
    {
        "cat": "fun",
        "name": "th/huehsv <hue> [sat] [lightness] [colorspace] [betterfully]  (aliases: hhsv)",
        "value": (
            "Apply hue/sat/lightness shift via ImageMagick haldclut (hald:8).\n"
            "• **hue** — rotation (0.0=unchanged, 0.5=full rotation)\n"
            "• **sat** — saturation multiplier (default 1.0)\n"
            "• **lightness** — lightness multiplier (default 1.0)\n"
            "• **colorspace** — modulate colorspace (default `hsl`)\n"
            "• **betterfully** — `1` for richer posterised hue + 125% sat headroom\n"
            "Example: `th/huehsv 0.5` · `th/huehsv 0.3 1.2 1.0 hsl 1`"
        ),
    },
    {
        "cat": "fun",
        "name": "th/mirror <left|right|top|bottom|deg>",
        "value": "Mirror media using FFmpeg split/flip/stack. Also works as a pipe effect.",
    },
    {
        "cat": "fun",
        "name": "th/syncaudio [alt]  (aliases: sa, sync)",
        "value": (
            "Sync video and audio durations by adjusting playback speed.\n"
            "Default: speeds up video to match audio. `alt`: speeds up audio to match video."
        ),
    },
    {
        "cat": "fun",
        "name": "th/trim <start> <end>",
        "value": "Trim audio, video, or GIF. Supports HH:MM:SS.frac and plain seconds.",
    },
    {
        "cat": "fun",
        "name": "th/repeat [n]  (aliases: rep, loop)",
        "value": "Repeat a video, GIF, or audio file N times (default 2, max 10). Attach or reply-to media.",
    },
    {
        "cat": "fun",
        "name": "th/concatenate <url1> <url2> ... [format]  (alias: concat)",
        "value": "Join 2-10 attachments/URLs (all video or all audio) into one file, in order.",
    },
    {
        "cat": "fun",
        "name": "th/join [media1] [media2] [-vertical]",
        "value": "Join 2 videos side-by-side (default) or stacked (use `-vertical`).",
    },
    {
        "cat": "fun",
        "name": "th/invite",
        "value": "Get the link to invite IHTX to your server.",
    },
    {
        "cat": "fun",
        "name": "th/catbox  (aliases: cb, upload)",
        "value": "Upload any file (up to 200 MB) to catbox.moe; automatically falls back to uguu.se if Catbox fails.",
    },
    {
        "cat": "fun",
        "name": "th/uguu  (alias: ugupload)",
        "value": "Upload an attached or replied-to file/video to uguu.se and get a direct link.",
    },
    {
        "cat": "fun",
        "name": "th/youtubedownload <URL or search>  (aliases: ytdl, ydl)",
        "value": "Download a video from YouTube/URL or search query. Sends directly if ≤8 MB, otherwise Catbox.",
    },
    {
        "cat": "fun",
        "name": "th/chat <prompt>  (aliases: ask, ai)",
        "value": "Chat with T1GNI IHTX and Fun Bot using Groq.",
    },
    {
        "cat": "fun",
        "name": "th/funfact  (aliases: fact, ihtxfact)",
        "value": "Share a random fun fact about the IHTX bot and its 534gurts identity.",
    },
    {
        "cat": "fun",
        "name": "th/tag <name> [args]  (aliases: tags)",
        "value": (
            "Invoke a custom tag. Run `th/tag help` for the full scripting reference.\n"
            "Supports variables, math, conditionals, embed JSON, iscript, mediascript, and IHTX."
        ),
    },
    {
        "cat": "fun",
        "name": "th/presets",
        "value": "List all available IHTX presets.",
    },
    {
        "cat": "fun",
        "name": "th/submiteffect <name> <effects>  (aliases: se, addeffect)",
        "value": "Submit a named pipe-effect combo to the global pool. Works in any server the bot is in.",
    },
    {
        "cat": "fun",
        "name": "th/listeffects  (aliases: le, effectlist)",
        "value": "List all user-submitted global effects and the guild they came from.",
    },
    {
        "cat": "fun",
        "name": "th/deleteeffect <name>",
        "value": "Delete a user-submitted effect you created (or any effect, if owner).",
    },
    {
        "cat": "fun",
        "name": "th/randomlist  (aliases: rlist, randlist)",
        "value": "Show an embed of every random-pool item and who/guild added it.",
    },
    # ── Utility ──
    {
        "cat": "utility",
        "name": "th/klaskycsupo",
        "value": "Reveal the Klasky Csupo video.",
    },
    {
        "cat": "utility",
        "name": "th/klaskysource  (alias: klasky)",
        "value": "Download and attach the current Klasky source clip.",
    },
    {
        "cat": "utility",
        "name": "th/presets  (aliases: effects, list)",
        "value": "List all available IHTX presets and usage information.",
    },
    {
        "cat": "utility",
        "name": "th/bothelp  (alias: ihtxhelp)",
        "value": "Show this interactive command reference.",
    },
    {
        "cat": "utility",
        "name": "th/effectconfig  (alias: ec)",
        "value": "Normalize pipe-effect parameters separated by =, ;, commas, or spaces into canonical effect=param;param configuration.",
    },
    # ── Owner ──
    {
        "cat": "owner",
        "name": "th/blockuser / th/unblockuser <@user>",
        "value": "Add or remove a user from the global blocklist.",
    },
    {
        "cat": "owner",
        "name": "th/blockchannel / th/unblockchannel <#channel>",
        "value": "Block or unblock a channel from running bot commands.",
    },
    {
        "cat": "owner",
        "name": "th/keywordblock <keyword> [#channel]",
        "value": "Block a keyword in a specific channel (or globally). `th/keywordblockremove` to undo.",
    },
    {
        "cat": "owner",
        "name": "th/autoreply <trigger> | <response> [#channel]",
        "value": "Add an autoreply. Supports `{mention}` / `{user}` / `{random:a|b|c}` placeholders.",
    },
    {
        "cat": "owner",
        "name": "th/removeautoreply <trigger>  (aliases: rar)",
        "value": "Remove an autoreply trigger.",
    },
    {
        "cat": "owner",
        "name": "th/autoreplies  (aliases: arlist)",
        "value": "List all active autoreplies.",
    },
    {
        "cat": "owner",
        "name": "th/autoreply2 [#channel]  /  th/autoreply2list",
        "value": "Toggle AI auto-reply (responds to every message) in a channel.",
    },
    {
        "cat": "owner",
        "name": "th/warn @user <reason>  /  th/warnings @user  /  th/clearwarn @user",
        "value": "Warn, view, or clear warnings for a user.",
    },
    {
        "cat": "owner",
        "name": "th/say / th/sayembed <content>",
        "value": "Send a plain message or embed as the bot.",
    },
    {
        "cat": "owner",
        "name": "th/setactivity <type> <text>  (aliases: activity, presence)",
        "value": "Change the bot's activity status. Types: playing, watching, listening, streaming.",
    },
    {
        "cat": "owner",
        "name": "th/setlimit @user <n>  /  th/usage",
        "value": "Set per-user heavy command limit. `th/usage` checks your current count.",
    },
    {
        "cat": "owner",
        "name": "th/listservers  /  th/listchannels <guild_id>",
        "value": "List all guilds the bot is in, or all channels in a specific guild.",
    },
    {
        "cat": "owner",
        "name": "th/sendmsg <channel_id> <message>  (aliases: msgsend)",
        "value": "Send a message to any channel by ID. Available to owners and bot moderators.",
    },
    {
        "cat": "owner",
        "name": "th/set <user_id> owner|mod|remove",
        "value": (
            "Set a user's bot role. `owner` — full owner access. "
            "`mod` — moderator access (`th/say`, `th/sayembed`, `th/sendmsg`). "
            "`remove` — strip all special roles (cannot remove the primary BOT_OWNER_ID owner). "
            "Example: `th/set 123456789012345678 mod`"
        ),
    },
    # ── Pipe effects (continued) ──
    {
        "cat": "heavy",
        "name": "alimiter [level_in] [limit] [attack] [release] [latency]",
        "value": "Pipe effect — FFmpeg audio limiter. Clamps peaks without clipping. Defaults: level_in=1, limit=1, attack=5ms, release=50ms, latency=1 (1=compensated delay, 0=off). Example: `alimiter 1.5 0.9 3 30 1`",
    },
    {
        "cat": "heavy",
        "name": "fzgm156 [sr]  (aliases: freakzinga)",
        "value": "Pipe effect — Freakzinga G Major 156. Creates a video palindrome (forward half + reversed half) with Hald CLUT hue shift and blue boost, then applies dual-voice pitch shifts (+0.5/+4.5 and -0.5/-4.5 semitones) mixed with the second track reversed and bass boosted. Optional sr param sets sample rate (default 44100).",
    },
    # ── Games ──
    {
        "cat": "games",
        "name": "th/8ball <question>  (alias: eightball)",
        "value": "Ask the magic 8-ball a yes/no question. The oracle never lies.",
    },
    {
        "cat": "games",
        "name": "th/coinflip  (aliases: flip, coin)",
        "value": "Flip a coin — **Heads** or **Tails**?",
    },
    {
        "cat": "games",
        "name": "th/roll [sides]  (aliases: dice, d)",
        "value": "Roll a die. Default is `d6`. `th/roll 20` rolls a d20. Max: d1000000.",
    },
    {
        "cat": "games",
        "name": "th/rps <rock|paper|scissors>  (alias: rockpaperscissors)",
        "value": "Play rock, paper, scissors against the bot. Shortcuts: `r` `p` `s` or emoji (✊✋✌️).",
    },
    {
        "cat": "games",
        "name": "th/choose <a|b|c>  (alias: pick)",
        "value": "Randomly pick one item from a pipe-separated list.\nExample: `th/choose pizza|sushi|tacos`",
    },
    {
        "cat": "games",
        "name": "th/rate <thing>",
        "value": "Rate something out of 10. Score is deterministic — same input always gets the same rating.",
    },
    {
        "cat": "games",
        "name": "th/slots  (alias: slot)",
        "value": "Spin the slot machine 🎰. Land **7️⃣ 7️⃣ 7️⃣** (25% chance) to win **+200 XP!**",
    },
    {
        "cat": "games",
        "name": "th/numguess  (aliases: ng, guess)",
        "value": "Guess a secret number between 1–100. You have **7 tries** with 30 seconds per guess.",
    },
    {
        "cat": "games",
        "name": "th/scramble  (aliases: ws, wordscramble)",
        "value": "Unscramble a shuffled video/audio-related word. **30 seconds** on the clock.",
    },
    {
        "cat": "games",
        "name": "th/typerace  (aliases: tr, type, typer)",
        "value": "Race to type a phrase exactly as fast as you can. Reports your **WPM** on success. 60 seconds to complete.",
    },
    {
        "cat": "games",
        "name": "th/mathquiz  (alias: mq)",
        "value": "5 arithmetic questions (addition, subtraction, multiplication), **10 seconds** each.",
    },
    {
        "cat": "games",
        "name": "th/trivia",
        "value": "10-question music trivia — multiple choice **A/B/C/D**, 20s per question. Earn **100 XP** per correct answer.",
    },
]

_HELP_CATS = {
    "heavy": ("⚙️ Heavy Commands", discord.Color(0x40E0D0)),
    "fun":   ("🎉 Fun",            discord.Color(0x40E0D0)),
    "games": ("🎮 Games",          discord.Color(0x40E0D0)),
    "utility": ("🧰 Utility",      discord.Color(0x40E0D0)),
    "owner": ("🔒 Owner",          discord.Color(0x40E0D0)),
}


_HELP_PAGE_SIZE = 6  # entries per page — keeps total embed chars well under 6000


def _build_help_embed(
    cat: str | None,
    entries: list[dict] | None = None,
    page: int = 0,
    page_size: int = _HELP_PAGE_SIZE,
) -> tuple[discord.Embed, int, int]:
    """Build a paginated help embed.

    Returns (embed, current_page_clamped, total_pages).
    When browsing a category (entries=None), shows 1 entry per page so each
    can display its preview image next to the effect description.
    """
    _browsing = entries is None  # True when user picked a category from the menu
    if entries is None:
        entries = [e for e in _HELP_ENTRIES if e["cat"] == cat]
        page_size = 1  # 1 per page so each effect shows its preview image

    total_pages = max(1, -(-len(entries) // page_size))  # ceil division
    page = max(0, min(page, total_pages - 1))
    page_entries = entries[page * page_size : (page + 1) * page_size]

    if cat and cat in _HELP_CATS:
        title, color = _HELP_CATS[cat]
    else:
        title, color = "🔍 Search Results", discord.Color.gold()

    embed = discord.Embed(title=title, color=color)
    for entry in page_entries:
        copyable_value = f"`{entry['name']}`\n{entry['value']}"
        if len(copyable_value) > 1024:
            copyable_value = copyable_value[:1020] + "…"
        embed.add_field(name=entry["name"], value=copyable_value, inline=False)

    # ── Preview image ─────────────────────────────────────────────────────────
    # When browsing (1 entry per page), attach the effect's preview image.
    # Only entries with a dedicated generated preview get an image.
    if _browsing and page_entries:
        entry_name = page_entries[0]["name"]
        preview_filename = _help_preview_filename(entry_name, cat)
        if preview_filename:
            embed.set_image(url=f"attachment://{preview_filename}")

    footer_parts: list[str] = []
    if cat == "heavy":
        footer_parts.append(
            f"Formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))} · Max {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    elif cat == "owner":
        footer_parts.append("All owner commands are restricted to the configured owner ID(s).")
    if total_pages > 1:
        footer_parts.append(f"Page {page + 1}/{total_pages}")
    if footer_parts:
        embed.set_footer(text=" · ".join(footer_parts))

    return embed, page, total_pages


def _build_home_embed() -> discord.Embed:
    counts = {c: sum(1 for e in _HELP_ENTRIES if e["cat"] == c) for c in _HELP_CATS}
    embed = discord.Embed(
        title="IHTX Bot — Help",
        description="Pick a category from the dropdown below, or run `th/ihtxhelp <query>` to search all commands.",
        color=0x40E0D0,
    )
    embed.add_field(
        name=f"⚙️ Heavy Commands · {counts['heavy']} entries",
        value="FFmpeg effects, video tools, and media processing.",
        inline=False,
    )
    embed.add_field(
        name=f"🎉 Fun · {counts['fun']} entries",
        value="Creative commands, downloads, chat, and utilities.",
        inline=False,
    )
    embed.add_field(
        name=f"🎮 Games · {counts['games']} entries",
        value="Games and interactive commands.",
        inline=False,
    )
    embed.add_field(
        name=f"🧰 Utility · {counts['utility']} entries",
        value="Klasky media, presets, and this help reference.",
        inline=False,
    )
    embed.add_field(
        name=f"🔒 Owner · {counts['owner']} entries",
        value="Bot administration and owner/moderator tools.",
        inline=False,
    )
    embed.set_footer(text="I Hate The X — FFmpeg logo destruction bot", icon_url=_IHTX_SAP_FOOTER_ICON)
    return embed


class _HelpSelect(discord.ui.Select):
    def __init__(self, invoker_id: int):
        self._invoker_id = invoker_id
        options = [
            discord.SelectOption(label="⚙️ Heavy Commands", value="heavy",
                                 description="ihtx, ffmpeg, multipitch, effects reference…"),
            discord.SelectOption(label="🎉 Fun",            value="fun",
                                 description="huehsv, trim, dl, catbox, tag, chat, ask…"),
            discord.SelectOption(label="🎮 Games",          value="games",
                                 description="8ball, coinflip, dice, slots, trivia, numguess…"),
            discord.SelectOption(label="🧰 Utility",         value="utility",
                                 description="klaskycsupo, klaskysource, presets, bothelp…"),
            discord.SelectOption(label="🔒 Owner",          value="owner",
                                 description="blockuser, autoreply, warn, say, setlimit…"),
            discord.SelectOption(label="🏠 Home",            value="home",
                                 description="Back to the overview"),
        ]
        super().__init__(placeholder="Select a category…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._invoker_id:
            return await interaction.response.send_message(
                "Only the person who ran this command can use this menu.", ephemeral=True
            )
        try:
            choice = self.values[0]
            view: _HelpView = self.view  # type: ignore
            # Acknowledge immediately; preparing/attaching a local preview can
            # otherwise exceed Discord's interaction response deadline.
            await interaction.response.defer()
            if choice == "home":
                view._cat = None
                view._page = 0
                embed = _build_home_embed()
                view._update_nav_buttons(1)
                await interaction.edit_original_response(
                    embed=embed,
                    view=view,
                    attachments=[],
                )
            else:
                view._cat = choice
                view._page = 0
                embed, _, total = _build_help_embed(choice, page=0)
                view._update_nav_buttons(total)
                category_entries = [e for e in _HELP_ENTRIES if e["cat"] == choice]
                preview = (
                    _help_preview_file(category_entries[0]["name"], choice)
                    if category_entries
                    else None
                )
                await interaction.edit_original_response(
                    embed=embed,
                    view=view,
                    attachments=[preview] if preview else [],
                )
        except Exception as exc:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"❌ Help menu error: {exc}", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                    f"❌ Help menu error: {exc}", ephemeral=True
                    )
            except Exception:
                pass


class _HelpNavButton(discord.ui.Button):
    def __init__(self, direction: int, invoker_id: int, **kwargs):
        super().__init__(**kwargs)
        self._direction = direction
        self._invoker_id = invoker_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._invoker_id:
            return await interaction.response.send_message(
                "Only the person who ran this command can use this menu.", ephemeral=True
            )
        view: _HelpView = self.view  # type: ignore
        view._page = max(0, view._page + self._direction)
        try:
            # Acknowledge before preparing the preview attachment.
            await interaction.response.defer()
            embed, view._page, total = _build_help_embed(view._cat, page=view._page)
            view._update_nav_buttons(total)
            category_entries = [e for e in _HELP_ENTRIES if e["cat"] == view._cat]
            page_entry = (
                category_entries[view._page]
                if category_entries and view._page < len(category_entries)
                else None
            )
            preview = (
                _help_preview_file(page_entry["name"], view._cat)
                if page_entry
                else None
            )
            await interaction.edit_original_response(
                embed=embed,
                view=view,
                attachments=[preview] if preview else [],
            )
        except Exception as exc:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ {exc}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            except Exception:
                pass


class _HelpView(discord.ui.View):
    def __init__(self, invoker_id: int):
        super().__init__(timeout=300)
        self._invoker_id = invoker_id
        self._cat: str | None = None
        self._page: int = 0

        self._select = _HelpSelect(invoker_id)
        self._btn_prev = _HelpNavButton(-1, invoker_id, label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=True)
        self._btn_next = _HelpNavButton(+1, invoker_id, label="Next ▶", style=discord.ButtonStyle.secondary, disabled=True)

        self.add_item(self._select)
        self.add_item(self._btn_prev)
        self.add_item(self._btn_next)

    def _update_nav_buttons(self, total_pages: int) -> None:
        self._btn_prev.disabled = (self._page <= 0)
        self._btn_next.disabled = (self._page >= total_pages - 1)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


_INVITE_URL = "https://discord.com/oauth2/authorize?client_id=1510887192040570910&permissions=1099780073478&integration_type=0&scope=bot"

@bot.command(name="invite")
async def invite_command(ctx: commands.Context):
    """Send the bot invite link."""
    embed = discord.Embed(
        title="Invite 534gurts to your server!",
        description=f"[Click here to add me]({_INVITE_URL})",
        color=0x40E0D0,
    )
    await ctx.reply(embed=embed)


_KLASKYCSUPO_URL = (
    "https://cdn.discordapp.com/attachments/1124758906376302632/"
    "1531986903182872786/youtube-Jv5OyY_GJDY.212709db.mp4?"
    "ex=6a6b357c&is=6a69e3fc&hm=e76d9d352a160331b0a22ef95cd59e89e931c9794ec2922c700bba46abaf10ef&"
)
_KLASKYSOURCE_URL = (
    "https://cdn.discordapp.com/attachments/1124758906376302632/"
    "1531987508928446505/convert.33ff0215.mp4?"
    "ex=6a6b360d&is=6a69e48d&hm=3b36ef2ce3b5f06e6895c0e127efdeba5cd0d36855cb38a9e344847825898329&"
)


@bot.command(name="klaskycsupo")
async def klaskycsupo_command(ctx: commands.Context):
    """Reveal the Klasky Csupo video."""
    embed = discord.Embed(
        description="✨ Here is your Klasky Csupo video!",
        color=0x40E0D0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "klaskycsupo.mp4")
        try:
            await download_url(_KLASKYCSUPO_URL, dest)
            await ctx.reply(embed=embed, file=discord.File(dest, filename="534gurts_thklaskycsupo.mp4"))
        except Exception:
            embed.description += f"\n{_KLASKYCSUPO_URL}"
            await ctx.reply(embed=embed)


@bot.command(name="klaskysource", aliases=["klasky"])
async def klaskysource_command(ctx: commands.Context):
    """Download and attach the current Klasky source clip."""
    embed = discord.Embed(
        description="🎬 Here is the current Klasky source clip!",
        color=0x40E0D0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "klaskysource.mov")
        try:
            await download_url(_KLASKYSOURCE_URL, dest)
            await ctx.reply(
                embed=embed,
                file=discord.File(dest, filename="klaskysource.mov"),
            )
        except Exception as exc:
            await ctx.reply(f"❌ Failed to fetch klaskysource: `{str(exc)[:500]}`")


@bot.command(name="ihtxhelp", aliases=["bothelp"])
async def help_command(ctx: commands.Context, *, query: str = ""):
    query = query.strip().lower()

    if query:
        # ── Search mode ────────────────────────────────────────────────────
        results = [
            e for e in _HELP_ENTRIES
            if query in e["name"].lower() or query in e["value"].lower()
        ]
        if not results:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"🔍 No commands matched `{query}`. Try a shorter keyword.",
                    color=0x40E0D0,
                )
            )
        embed, _, total = _build_help_embed(None, results)
        footer = f"{len(results)} result(s) for '{query}'"
        if total > 1:
            footer += f" · Page 1/{total}"
        embed.set_footer(text=footer)
        return await ctx.reply(embed=embed)

    # ── Browse mode ────────────────────────────────────────────────────────
    embed = _build_home_embed()
    view = _HelpView(ctx.author.id)
    await ctx.reply(embed=embed, view=view)



# ---------- Last Export Grab ----------

@bot.command(name="lexg", aliases=["lastexportgrab", "lec"])
async def lexg_command(ctx: commands.Context, duration: float = 5.0):
    """Grab the last N seconds of the last th/ihtx export using reverse→trim→reverse.

    Usage: th/lexg [duration] — no attachment needed; uses your last th/ihtx export.
    You can still attach or reply to a video to override the stored export.
    Default duration is 5 seconds.
    """
    # Resolve media source (override) first
    source = None
    if ctx.message and ctx.message.attachments:
        source = ctx.message.attachments[0]
    elif ctx.message and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                source = ref.attachments[0]
            else:
                for tok in ref.content.split():
                    if tok.startswith(("http://", "https://")):
                        source = tok
                        break
        except Exception:
            pass

    if duration <= 0 or duration > 3600:
        await ctx.reply("❌ Duration must be between 0 and 3600 seconds.")
        return

    if source:
        if isinstance(source, discord.Attachment) and source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return

        if isinstance(source, discord.Attachment):
            suffix = Path(source.filename).suffix.lower()
            input_filename = source.filename
        else:
            suffix = Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
            input_filename = os.path.basename(urllib.parse.urlparse(source).path) or "media.mp4"
        if suffix not in SUPPORTED_EXTENSIONS:
            await ctx.reply(f"Unsupported file type `{suffix}`.")
            return

        is_video = suffix in VIDEO_EXTENSIONS
        status_msg = await ctx.reply(f"⏳ Grabbing last **{duration}s** of `{input_filename}`…")

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, f"input{suffix}")
            output_path = os.path.join(tmpdir, "lec.mp4")
            try:
                if isinstance(source, discord.Attachment):
                    await download_attachment(source, input_path)
                else:
                    await download_url(source, input_path)
            except Exception as e:
                await status_msg.edit(content=f"❌ Failed to download: {e}")
                return

            await _lexg_run_ffmpeg(ctx, status_msg, input_path, output_path, duration, input_filename)
        return

    # No attachment — use the user's last th/ihtx export.
    last = _lexg_load_last_export(ctx.author.id)
    if not last:
        await ctx.reply(
            "**th/lexg [duration]** — Grab the last N seconds of your last `th/ihtx` export.\n"
            "No export found yet — run an `th/ihtx` command first, or attach/reply to a video.\n"
            "Duration defaults to `5` seconds.\n"
            "Aliases: `th/lastexportgrab` `th/lec`"
        )
        return

    input_path = last["path"]
    input_filename = last.get("filename", "lastexport.mp4")
    output_path = os.path.join(os.path.dirname(input_path), f"lec_{ctx.author.id}.mp4")
    status_msg = await ctx.reply(f"⏳ Grabbing last **{duration}s** of your last export (`{input_filename}`)…")
    await _lexg_run_ffmpeg(ctx, status_msg, input_path, output_path, duration, input_filename)


def _lexg_load_last_export(user_id: int) -> dict | None:
    """Return the last export metadata for a user, rehydrating from disk if needed."""
    # In-memory cache
    last = _last_exports.get(user_id)
    if last and os.path.isfile(last.get("path", "")):
        return last
    if last:
        _last_exports.pop(user_id, None)

    # JSON metadata
    meta_path = f"output/lastexport_{user_id}.json"
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            path = meta.get("path", "")
            if os.path.isfile(path):
                _last_exports[user_id] = meta
                return meta
        except Exception as exc:
            print(f"[lexg] failed to load metadata: {exc}")

    # Fallback: any output/lastexport_<user_id>.* file
    candidates = [
        p for p in Path("output").glob(f"lastexport_{user_id}.*")
        if p.suffix != ".json"
    ]
    if candidates:
        path = max(candidates, key=lambda p: p.stat().st_mtime)
        meta = {
            "path": str(path),
            "filename": "lastexport",
            "is_video": True,
            "suffix": path.suffix,
            "ext": path.suffix,
        }
        _last_exports[user_id] = meta
        return meta

    return None


def _lexg_probe_streams(path: str) -> tuple[bool, bool, float]:
    """Return (has_video, has_audio, duration_seconds) for a media file."""
    has_video = bool(
        _ffprobe(path, "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "default=nw=1:nk=1").strip()
    )
    has_audio = bool(
        _ffprobe(path, "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "default=nw=1:nk=1").strip()
    )
    dur = _ffprobe_duration(path)
    return has_video, has_audio, dur


async def _lexg_run_ffmpeg(
    ctx: commands.Context,
    status_msg: discord.Message,
    input_path: str,
    output_path: str,
    duration: float,
    input_filename: str,
) -> None:
    """Run the reverse→trim→reverse FFmpeg command for th/lexg and upload result.

    Probes the actual input streams so video-only, audio-only, and silent/GIF
    exports are handled correctly.
    """
    has_video, has_audio, actual_dur = _lexg_probe_streams(input_path)
    if not has_video and not has_audio:
        await status_msg.edit(content="❌ No video or audio streams found in the input file.")
        return

    dur = min(duration, actual_dur) if actual_dur > 0 else duration
    if actual_dur > 0 and duration > actual_dur:
        await status_msg.edit(content=f"⚠️ Requested duration ({duration}s) exceeds media length ({actual_dur:.2f}s). Using full duration.")

    cmd = ["ffmpeg", "-y", "-i", input_path]
    if has_video:
        cmd += ["-vf", f"reverse,trim=0:{dur},reverse"]
    if has_audio:
        cmd += ["-af", f"areverse,atrim=0:{dur},areverse"]
    if has_video:
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    elif has_video:
        # Video-only output still needs a codec container; an audio track is absent
        cmd += ["-an"]
    cmd += [output_path]

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300),
        )
        ok = result.returncode == 0
        err = result.stderr
    except subprocess.TimeoutExpired:
        await status_msg.edit(content="❌ FFmpeg timed out.")
        return
    except Exception as e:
        await status_msg.edit(content=f"❌ FFmpeg error: {e}")
        return

    if not ok:
        await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
        return

    out_size = os.path.getsize(output_path)
    if out_size > CATBOX_THRESHOLD:
        await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
        cb_url = await _upload_to_catbox(output_path)
        if cb_url:
            await ctx.reply(f"✅ Last **{dur:.2f}s** grabbed → {cb_url}")
            await status_msg.delete()
        else:
            await status_msg.edit(content="❌ Output too large for Discord and Catbox upload failed.")
        return

    out_filename = "534gurts_thlexg.mp4"
    try:
        await ctx.reply(
            content=f"✅ Last **{dur:.2f}s** grabbed!",
            file=discord.File(output_path, filename=out_filename),
        )
        await status_msg.delete()
    except discord.HTTPException as e:
        await status_msg.edit(content=f"❌ Failed to upload: {e}")


@bot.command(name="crop", aliases=["c"])
async def crop_command(ctx: commands.Context, width: int, height: int):
    """Center-crop a video to the given width and height.

    Usage: th/crop <width> <height> — attach or reply to a video.
    Example: th/crop 640 360
    """
    if width <= 0 or height <= 0 or width > 7680 or height > 7680:
        await ctx.reply("❌ Width and height must be between 1 and 7680.")
        return

    # libx264/yuv420 requires even dimensions.
    orig_width, orig_height = width, height
    width = width - (width % 2)
    height = height - (height % 2)
    if width == 0 or height == 0:
        await ctx.reply("❌ Width and height must be at least 2 after rounding to even values for h.264.")
        return

    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**th/crop <width> <height>** — Center-crop a video.\n"
            "Attach a video or reply to one.\n"
            "Example: `th/crop 640 360`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"`th/crop` requires a video file. Got `{suffix}`.")
        return

    input_filename = source.filename
    if orig_width != width or orig_height != height:
        crop_status = f"⏳ Cropping `{input_filename}` to **{orig_width}×{orig_height}** → **{width}×{height}** for h.264…"
    else:
        crop_status = f"⏳ Cropping `{input_filename}` to **{width}×{height}**…"
    status_msg = await ctx.reply(crop_status)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "crop.mp4")
        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        # Probe source dimensions so we can fail early on impossible crops.
        try:
            vinfo = _ffprobe_video_info(input_path)
            src_w = int(vinfo["width"])
            src_h = int(vinfo["height"])
        except Exception as exc:
            await status_msg.edit(content=f"❌ Could not probe video dimensions: {exc}")
            return

        if width > src_w or height > src_h:
            await status_msg.edit(
                content=f"❌ Crop size **{width}×{height}** is larger than source video **{src_w}×{src_h}**."
            )
            return

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2,setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            output_path,
        ]

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300),
            )
            ok = result.returncode == 0
            err = result.stderr
        except subprocess.TimeoutExpired:
            await status_msg.edit(content="❌ FFmpeg timed out.")
            return
        except Exception as e:
            await status_msg.edit(content=f"❌ FFmpeg error: {e}")
            return

        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        await _lexg_upload_result(ctx, status_msg, output_path, input_filename, f"crop_{width}x{height}")


@bot.command(name="resize", aliases=["res"])
async def resize_command(ctx: commands.Context, width: int, height: int):
    """Resize a video to the given width and height.

    Usage: th/resize <width> <height> — attach or reply to a video.
    Example: th/resize 640 360
    """
    if width <= 0 or height <= 0 or width > 7680 or height > 7680:
        await ctx.reply("❌ Width and height must be between 1 and 7680.")
        return

    # libx264/yuv420 requires even dimensions.
    orig_width, orig_height = width, height
    width = width - (width % 2)
    height = height - (height % 2)
    if width == 0 or height == 0:
        await ctx.reply("❌ Width and height must be at least 2 after rounding to even values for h.264.")
        return

    attachment = None
    source = await _resolve_media_source(ctx)

    if source is None:
        await ctx.reply(
            "**th/resize <width> <height>** — Resize a video.\n"
            "Attach a video or reply to one.\n"
            "Example: `th/resize 640 360`"
        )
        return

    if isinstance(source, discord.Attachment):
        if source.size > MAX_FILE_SIZE:
            await ctx.reply(f"File too large (max 25 MB). Your file is {source.size / 1024 / 1024:.1f} MB.")
            return
    suffix = Path(source.filename).suffix.lower() if isinstance(source, discord.Attachment) else Path(urllib.parse.urlparse(source).path).suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"`th/resize` requires a video file. Got `{suffix}`.")
        return

    input_filename = source.filename
    if orig_width != width or orig_height != height:
        resize_status = f"⏳ Resizing `{input_filename}` to **{orig_width}×{orig_height}** → **{width}×{height}** for h.264…"
    else:
        resize_status = f"⏳ Resizing `{input_filename}` to **{width}×{height}**…"
    status_msg = await ctx.reply(resize_status)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "resize.mp4")
        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale={width}:{height},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            output_path,
        ]

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300),
            )
            ok = result.returncode == 0
            err = result.stderr
        except subprocess.TimeoutExpired:
            await status_msg.edit(content="❌ FFmpeg timed out.")
            return
        except Exception as e:
            await status_msg.edit(content=f"❌ FFmpeg error: {e}")
            return

        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        await _lexg_upload_result(ctx, status_msg, output_path, input_filename, f"resize_{width}x{height}")


async def _lexg_upload_result(
    ctx: commands.Context,
    status_msg: discord.Message,
    output_path: str,
    input_filename: str,
    prefix: str,
) -> None:
    """Upload a lexg/crop/resize output, falling back to Catbox if too large."""
    out_size = os.path.getsize(output_path)
    if out_size > CATBOX_THRESHOLD:
        await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
        cb_url = await _upload_to_catbox(output_path)
        if cb_url:
            await ctx.reply(f"✅ Done → {cb_url}")
            await status_msg.delete()
        else:
            await status_msg.edit(content="❌ Output too large for Discord and Catbox upload failed.")
        return

    out_filename = f"534gurts_th{prefix}.mp4"
    try:
        await ctx.reply(
            content="✅ Done!",
            file=discord.File(output_path, filename=out_filename),
        )
        await status_msg.delete()
    except discord.HTTPException as e:
        await status_msg.edit(content=f"❌ Failed to upload: {e}")




# ---------- Owner-only moderation / utility commands ----------

def _parse_digits(s: str) -> int:
    """Extract numeric ID from mention or plain id string."""
    if not s:
        raise ValueError("No id provided")
    m = re.search(r"(\d{6,20})", s)
    if m:
        return int(m.group(1))
    try:
        return int(s)
    except Exception:
        raise ValueError("Could not parse id")


@bot.command(name="blockuser")
@commands.check(_is_owner)
async def blockuser(ctx: commands.Context, user: str):
    """Owner-only: add a user ID or mention to the user blocklist."""
    try:
        user_id = _parse_digits(user)
    except ValueError:
        await ctx.reply("❌ Invalid user. Provide a mention or numeric ID.")
        return
    if user_id in blocklist:
        await ctx.reply(f"User `{user_id}` is already blocked.")
        return
    blocklist.add(user_id)
    _save_blocklist()
    await ctx.reply(f"✅ Blocked user `{user_id}`.")


@bot.command(name="unblockuser")
@commands.check(_is_owner)
async def unblockuser(ctx: commands.Context, user: str):
    """Owner-only: remove a user ID or mention from the user blocklist."""
    try:
        user_id = _parse_digits(user)
    except ValueError:
        await ctx.reply("❌ Invalid user. Provide a mention or numeric ID.")
        return
    if user_id not in blocklist:
        await ctx.reply(f"User `{user_id}` is not blocked.")
        return
    blocklist.discard(user_id)
    _save_blocklist()
    await ctx.reply(f"✅ Unblocked user `{user_id}`.")


@bot.command(name="blockchannel")
@commands.check(_is_owner)
async def blockchannel(ctx: commands.Context, channel: str = None):
    """Owner-only: add a channel to the channel blocklist. If omitted, blocks current channel."""
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return
    if channel_id in channel_blocks:
        await ctx.reply(f"Channel `{channel_id}` is already blocked.")
        return
    channel_blocks.add(channel_id)
    _save_channel_blocks()
    await ctx.reply(f"✅ Blocked channel `{channel_id}`.")


@bot.command(name="unblockchannel")
@commands.check(_is_owner)
async def unblockchannel(ctx: commands.Context, channel: str = None):
    """Owner-only: remove a channel from the channel blocklist. If omitted, unblocks current channel."""
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return
    if channel_id not in channel_blocks:
        await ctx.reply(f"Channel `{channel_id}` is not blocked.")
        return
    channel_blocks.discard(channel_id)
    _save_channel_blocks()
    await ctx.reply(f"✅ Unblocked channel `{channel_id}`.")


@bot.command(name="keywordblock", aliases=["blockkeyword", "kb"])
@commands.check(_is_owner)
async def keywordblock(ctx: commands.Context, keyword: str, channel: str = None):
    """Owner-only: block a keyword in a single channel.

    This is channel-scoped only; it does not create a global keyword block.
    """
    normalized = _normalize_keyword(keyword)
    if not normalized:
        await ctx.reply("❌ Provide a keyword or phrase to block.")
        return
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return

    blocked = keyword_blocks.setdefault(channel_id, set())
    if normalized in blocked:
        await ctx.reply(f"Keyword `{normalized}` is already blocked in channel `{channel_id}`.")
        return
    blocked.add(normalized)
    _save_keyword_blocks()
    await ctx.reply(f"✅ Blocked keyword `{normalized}` in channel `{channel_id}`.")


@bot.command(name="keywordblockremove", aliases=["unblockkeyword", "removekeywordblock", "kbr"])
@commands.check(_is_owner)
async def keywordblockremove(ctx: commands.Context, keyword: str, channel: str = None):
    """Owner-only: remove a keyword block from a single channel."""
    normalized = _normalize_keyword(keyword)
    if not normalized:
        await ctx.reply("❌ Provide a keyword or phrase to unblock.")
        return
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return

    blocked = keyword_blocks.get(channel_id, set())
    if normalized not in blocked:
        await ctx.reply(f"Keyword `{normalized}` is not blocked in channel `{channel_id}`.")
        return
    blocked.discard(normalized)
    if not blocked:
        keyword_blocks.pop(channel_id, None)
    # Also clear custom message for this keyword
    msgs = keyword_block_messages.get(channel_id, {})
    msgs.pop(normalized, None)
    if not msgs:
        keyword_block_messages.pop(channel_id, None)
    _save_keyword_blocks()
    await ctx.reply(f"✅ Removed keyword block `{normalized}` from channel `{channel_id}`.")


@bot.command(name="say")
@commands.check(_is_bot_mod)
async def say(ctx: commands.Context, *, message: str):
    """Owner-only: make the bot send a plain message in the current channel."""
    try:
        await ctx.send(message)
        if ctx.message:
            await ctx.message.add_reaction("✅")
    except Exception as e:
        await ctx.reply(f"❌ Failed to send message: {e}")


@bot.command(name="sayembed")
@commands.check(_is_bot_mod)
async def sayembed(ctx: commands.Context, *, content: str):
    """
    Owner-only: send an embed.
    If `content` contains a '|' it will split into title|description, otherwise content is used as description.
    Example:
      th/sayembed Title | This is the embed body
    """
    try:
        if "|" in content:
            title, desc = [p.strip() for p in content.split("|", 1)]
        else:
            title = ""
            desc = content
        emb = discord.Embed(title=title or None, description=desc or None, color=discord.Color.dark_red())
        await ctx.send(embed=emb)
        if ctx.message:
            await ctx.message.add_reaction("✅")
    except Exception as e:
        await ctx.reply(f"❌ Failed to send embed: {e}")


@bot.command(name="keywordblockmsg", aliases=["kbmsg", "blockmsg"])
@commands.check(_is_owner)
async def keywordblockmsg(ctx: commands.Context, keyword: str, *, message: str):
    """Owner-only: set a custom message for a keyword block.

    Everything after the keyword is the message. Use {mention} or {user} for user mention.
    Example:
      th/keywordblockmsg swearword no swearing, {mention}!
      th/keywordblockmsg badword dont say that, {user}
    """
    normalized = _normalize_keyword(keyword)
    if not normalized:
        await ctx.reply("❌ Provide a keyword.")
        return
    channel_id = ctx.channel.id

    blocked = keyword_blocks.get(channel_id, set())
    if normalized not in blocked:
        await ctx.reply(f"❌ Keyword `{normalized}` is not blocked in this channel. Block it first with `th/keywordblock`.")
        return

    msgs = keyword_block_messages.setdefault(channel_id, {})
    msgs[normalized] = message
    _save_keyword_blocks()
    await ctx.reply(f"✅ Custom message set for keyword `{normalized}` in this channel.")


# ---------- Autoreplies ----------

@bot.command(name="autoreply", aliases=["ar"])
@commands.check(_is_owner)
async def autoreply(ctx: commands.Context, trigger: str, channel: discord.TextChannel = None, *, response: str):
    """Owner-only: add an autoreply. When anyone says the trigger, the bot replies.

    Leave channel blank (or omit) to reply in ALL channels.
    Use {mention} or {user} to ping the user in the response.
    Example (all channels):
      th/autoreply hello Hello there, {mention}!
    Example (specific channel):
      th/autoreply hello #general Hello there, {mention}!
    """
    trigger_norm = trigger.strip().lower()
    if not trigger_norm:
        await ctx.reply("❌ Provide a trigger word or phrase.")
        return
    if not response:
        await ctx.reply("❌ Provide a response message.")
        return
    channel_id = channel.id if channel else None
    # Preserve existing blocked_channels if updating an existing entry
    existing_blocked = []
    if trigger_norm in autoreplies and isinstance(autoreplies[trigger_norm], dict):
        existing_blocked = autoreplies[trigger_norm].get("blocked_channels", [])
    autoreplies[trigger_norm] = {"response": response, "channel_id": channel_id, "blocked_channels": existing_blocked}
    _save_autoreplies()
    channel_note = f" in {channel.mention}" if channel else " in **all channels**"
    await ctx.reply(f"✅ Autoreply set{channel_note}: `{trigger_norm}` → {response}")


@bot.command(name="blockarchannel", aliases=["bac", "silencear"])
@commands.check(_is_owner)
async def blockarchannel(ctx: commands.Context, trigger: str, channel: discord.TextChannel = None):
    """Owner-only: prevent an autoreply trigger from firing in a specific channel.

    The autoreply stays active in all other channels — only this one is silenced.
    Run again with the same trigger + channel to unblock it.

    Example:
      th/blockarchannel hello           ← silences 'hello' in current channel
      th/blockarchannel hello #general  ← silences 'hello' in #general
    """
    trigger_norm = trigger.strip().lower()
    if trigger_norm not in autoreplies:
        await ctx.reply(f"❌ No autoreply found for `{trigger_norm}`.")
        return

    target_channel = channel or ctx.channel
    cid = target_channel.id

    entry = autoreplies[trigger_norm]
    if not isinstance(entry, dict):
        entry = {"response": entry, "channel_id": None, "blocked_channels": []}
    blocked = entry.setdefault("blocked_channels", [])

    if cid in blocked:
        blocked.remove(cid)
        autoreplies[trigger_norm] = entry
        _save_autoreplies()
        await ctx.reply(f"✅ Autoreply `{trigger_norm}` **unblocked** in {target_channel.mention} — it will fire there again.")
    else:
        blocked.append(cid)
        autoreplies[trigger_norm] = entry
        _save_autoreplies()
        await ctx.reply(f"✅ Autoreply `{trigger_norm}` **silenced** in {target_channel.mention} — it won't fire there anymore.")


@bot.command(name="removeautoreply", aliases=["rar", "deautoreply"])
@commands.check(_is_owner)
async def removeautoreply(ctx: commands.Context, *, trigger: str):
    """Owner-only: remove an autoreply trigger."""
    trigger_norm = trigger.strip().lower()
    if trigger_norm not in autoreplies:
        await ctx.reply(f"❌ No autoreply for `{trigger_norm}`.")
        return
    del autoreplies[trigger_norm]
    _save_autoreplies()
    await ctx.reply(f"✅ Removed autoreply for `{trigger_norm}`.")


@bot.command(name="removearmentions", aliases=["rarm", "noarping"])
@commands.check(_is_owner)
async def removearmentions(ctx: commands.Context, *, trigger: str):
    """Owner-only: remove {mention} and {user} tokens from an autoreply's response.

    Leaves the autoreply active but stops it from pinging users.
    Example:
      th/removearmentions hello
    """
    trigger_norm = trigger.strip().lower()
    if trigger_norm not in autoreplies:
        await ctx.reply(f"❌ No autoreply found for `{trigger_norm}`.")
        return

    entry = autoreplies[trigger_norm]
    response = entry.get("response", "") if isinstance(entry, dict) else str(entry)

    cleaned = response.replace("{mention}", "").replace("{user}", "").strip()
    cleaned = re.sub(r"  +", " ", cleaned)

    if cleaned == response:
        await ctx.reply(f"ℹ️ Autoreply `{trigger_norm}` has no mention tokens to remove.")
        return

    if isinstance(entry, dict):
        autoreplies[trigger_norm]["response"] = cleaned
    else:
        autoreplies[trigger_norm] = {"response": cleaned, "channel_id": None}

    _save_autoreplies()
    await ctx.reply(f"✅ Removed mention pings from `{trigger_norm}`.\nNew response: {cleaned}")


@bot.command(name="autoreplies", aliases=["listautoreplies", "arlist"])
async def listautoreplies(ctx: commands.Context):
    """List all active autoreply triggers and their responses."""
    if not autoreplies:
        await ctx.reply("No autoreplies set.")
        return
    lines = []
    for trigger, entry in autoreplies.items():
        resp = entry.get("response", entry) if isinstance(entry, dict) else entry
        ch_id = entry.get("channel_id") if isinstance(entry, dict) else None
        ch_note = f" (<#{ch_id}>)" if ch_id else " (all channels)"
        lines.append(f"`{trigger}`{ch_note} → {resp}")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = line
        else:
            current = (current + "\n" + line).strip()
    if current:
        chunks.append(current)
    for chunk in chunks:
        await ctx.reply(chunk)


# ---------- Autoreply2 ----------

@bot.command(name="autoreply2", aliases=["ar2"])
@commands.check(_is_owner)
async def autoreply2_cmd(ctx: commands.Context):
    """Owner-only: toggle AI auto-reply on/off for the current channel.

    When enabled, the bot responds to every message in this channel using AI.
    Run again to toggle off.

    Example:
      th/autoreply2   ← toggles on in current channel
      th/autoreply2   ← toggles off
    """
    cid = ctx.channel.id
    if cid in autoreply2:
        autoreply2.discard(cid)
        _save_autoreply2()
        await ctx.reply(f"✅ AI auto-reply **disabled** in {ctx.channel.mention}.")
    else:
        autoreply2.add(cid)
        _save_autoreply2()
        await ctx.reply(f"✅ AI auto-reply **enabled** in {ctx.channel.mention}. The bot will reply to every message using AI.")


@bot.command(name="autoreply2list", aliases=["ar2list"])
@commands.check(_is_owner)
async def autoreply2list(ctx: commands.Context):
    """Owner-only: list all channels with autoreply2 active."""
    if not autoreply2:
        await ctx.reply("No channels have AI auto-reply enabled.")
        return
    lines = [f"<#{cid}>" for cid in autoreply2]
    await ctx.reply("AI auto-reply enabled in:\n" + "\n".join(lines))


@bot.command(name="removear2mentions", aliases=["rarm2", "noar2ping"])
@commands.check(_is_owner)
async def removear2mentions(ctx: commands.Context, user: discord.Member):
    """Owner-only: toggle off @mention pings for a user in autoreply2 responses.

    When set, autoreply2 will still reply to their messages but won't ping them.
    Run again on the same user to re-enable pings.

    Example:
      th/removear2mentions @someone   ← disables pings for them
      th/removear2mentions @someone   ← re-enables pings
    """
    uid = user.id
    if uid in autoreply2_no_mention:
        autoreply2_no_mention.discard(uid)
        _save_autoreply2_no_mention()
        await ctx.reply(f"✅ Autoreply2 will now **ping** {user.mention} again.")
    else:
        autoreply2_no_mention.add(uid)
        _save_autoreply2_no_mention()
        await ctx.reply(f"✅ Autoreply2 will no longer ping {user.mention} when replying.")


# ---------- Owner: activity control ----------

@bot.command(name="uptime", aliases=["up"])
async def uptime_cmd(ctx: commands.Context):
    """Show how long the bot has been running and how many renders it has completed."""
    delta = int(time.time() - _bot_start_time)
    days, rem = divmod(delta, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    up_str = " ".join(parts)

    start_struct = time.gmtime(_bot_start_time)
    start_fmt = time.strftime("%Y-%m-%d %H:%M UTC", start_struct)

    embed = discord.Embed(title="⏱️ Bot Uptime", color=0x40E0D0)
    embed.add_field(name="Uptime", value=f"**{up_str}**", inline=False)
    embed.add_field(name="Renders completed", value=f"{_renders_completed:,}", inline=True)
    embed.add_field(name="Renders in progress", value=str(_renders_in_progress), inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.set_footer(text=f"Online since {start_fmt}")
    await ctx.reply(embed=embed)


@bot.command(name="setactivity", aliases=["activity", "presence"])
@commands.check(_is_owner)
async def setactivity(ctx: commands.Context, activity_type: str, *, text: str):
    """Owner-only: change the bot's activity.

    Usage:
      th/setactivity watching some cool video
      th/setactivity listening lo-fi beats
      th/setactivity playing Minecraft
      th/setactivity streaming Cool Stream | https://twitch.tv/yourchannel
    """
    activity_type = activity_type.lower().strip()
    if activity_type in ("watching", "watch", "w"):
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        label = "Watching"
        save_type = "watching"
    elif activity_type in ("listening", "listen", "l"):
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        label = "Listening to"
        save_type = "listening"
    elif activity_type in ("playing", "play", "p"):
        activity = discord.Game(name=text)
        label = "Playing"
        save_type = "playing"
    elif activity_type in ("streaming", "stream", "s"):
        parts = [p.strip() for p in text.split("|", 1)]
        stream_name = parts[0]
        stream_url = parts[1] if len(parts) > 1 else "https://twitch.tv/placeholder"
        activity = discord.Streaming(name=stream_name, url=stream_url)
        label = "Streaming"
        save_type = "streaming"
        text = f"{stream_name} | {stream_url}"
    else:
        await ctx.reply("❌ Activity type must be `watching`, `listening`, `playing`, or `streaming`.")
        return
    await bot.change_presence(activity=activity)
    try:
        _activity_file = Path("bot/activity.json")
        with _activity_file.open("w") as _af:
            json.dump({"type": save_type, "name": text}, _af)
    except Exception:
        pass
    if ctx.message:
        await ctx.message.add_reaction("✅")
    await ctx.reply(f"✅ Activity set to **{label}** {text}", ephemeral=True)


# ---------- Owner: cross-server messaging ----------

@bot.command(name="sendmsg", aliases=["msgsend"])
@commands.check(_is_bot_mod)
async def sendmsg(ctx: commands.Context, channel_id: str, *, text: str):
    """Owner-only: send a message to any channel the bot can access, by channel ID.

    Usage:
      th/sendmsg <channel_id> <message>
      th/sendmsg 123456789012345678 Hello from the both/
    """
    try:
        cid = int(channel_id.strip("<#>"))
    except ValueError:
        await ctx.reply("❌ Invalid channel ID. Provide a numeric ID or channel mention.")
        return

    channel = bot.get_channel(cid)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cid)
        except discord.NotFound:
            await ctx.reply("❌ Channel not found. Make sure the bot is in that server.")
            return
        except discord.Forbidden:
            await ctx.reply("❌ Bot doesn't have permission to access that channel.")
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.DMChannel)):
        await ctx.reply("❌ That channel type doesn't support text messages.")
        return

    try:
        await channel.send(text)
        if ctx.message:
            await ctx.message.add_reaction("✅")
    except discord.Forbidden:
        await ctx.reply("❌ Bot lacks permission to send messages in that channel.")
    except discord.HTTPException as e:
        await ctx.reply(f"❌ Failed to send: {e}")


@bot.command(name="set")
@commands.check(_is_owner)
async def set_role_command(ctx: commands.Context, user_id_str: str, role: str = ""):
    """Owner-only: assign or remove a bot role for a user.

    Usage:
      th/set <user_id> owner   — full owner access
      th/set <user_id> mod     — moderator access (th/say, th/sayembed, th/sendmsg)
      th/set <user_id> remove  — strip all special roles
    """
    try:
        user_id = int(user_id_str.strip("<@!>"))
    except ValueError:
        await ctx.reply("❌ Provide a valid user ID or mention.")
        return

    role = role.strip().lower()
    if role not in ("owner", "mod", "remove"):
        await ctx.reply("❌ Role must be `owner`, `mod`, or `remove`.\nUsage: `th/set <user_id> owner|mod|remove`")
        return

    if role == "owner":
        if user_id in owner_ids:
            await ctx.reply(f"⚠️ `{user_id}` is already an owner.")
            return
        owner_ids.add(user_id)
        _save_owner_ids()
        await ctx.reply(f"✅ `{user_id}` is now a **bot owner** (full access).")

    elif role == "mod":
        if user_id in owner_ids:
            await ctx.reply(f"⚠️ `{user_id}` is already an owner — owner access includes all mod permissions.")
            return
        key = str(user_id)
        if key not in _xp_data:
            _xp_data[key] = {"xp": 0, "level": 1}
        _xp_data[key]["is_mod"] = True
        _save_xp_data()
        await ctx.reply(f"✅ `{user_id}` is now a **bot moderator** — can use `th/say`, `th/sayembed`, `th/sendmsg`.")

    elif role == "remove":
        if user_id == OWNER_ID:
            await ctx.reply("❌ Cannot remove the primary owner (set via `BOT_OWNER_ID` env var).")
            return
        changed: list[str] = []
        if user_id in owner_ids:
            owner_ids.discard(user_id)
            _save_owner_ids()
            changed.append("owner")
        key = str(user_id)
        if _xp_data.get(key, {}).get("is_mod"):
            _xp_data[key]["is_mod"] = False
            _save_xp_data()
            changed.append("mod")
        if changed:
            await ctx.reply(f"✅ Removed **{' + '.join(changed)}** role(s) from `{user_id}`.")
        else:
            await ctx.reply(f"⚠️ `{user_id}` has no special bot roles to remove.")


@bot.command(name="listservers", aliases=["servers", "guilds"])
@commands.check(_is_owner)
async def listservers(ctx: commands.Context):
    """Owner-only: list all servers the bot is in with their IDs and channel counts."""
    guilds = sorted(bot.guilds, key=lambda g: g.name.lower())
    if not guilds:
        await ctx.reply("Bot is not in any servers.")
        return

    lines = []
    for g in guilds:
        text_channels = [c for c in g.channels if isinstance(c, discord.TextChannel)]
        lines.append(f"**{g.name}** (`{g.id}`) — {g.member_count} members, {len(text_channels)} text channels")

    # Split into chunks of 10 servers per message to avoid hitting the 2000 char limit
    chunk_size = 10
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i:i + chunk_size]
        header = f"**Servers ({len(guilds)} total):**\n" if i == 0 else ""
        await ctx.reply(header + "\n".join(chunk))


@bot.command(name="listchannels", aliases=["channels"])
@commands.check(_is_owner)
async def listchannels(ctx: commands.Context, *, guild_id: str):
    """Owner-only: list all text channels in a server by guild ID."""
    try:
        gid = int(guild_id.strip())
    except ValueError:
        await ctx.reply("❌ Provide a numeric guild/server ID.")
        return

    guild = bot.get_guild(gid)
    if guild is None:
        await ctx.reply("❌ Server not found. Make sure the bot is in that server.")
        return

    text_channels = sorted(
        [c for c in guild.channels if isinstance(c, discord.TextChannel)],
        key=lambda c: c.position,
    )
    if not text_channels:
        await ctx.reply(f"No text channels found in **{guild.name}**.")
        return

    lines = [f"**{guild.name}** text channels:"]
    for c in text_channels:
        lines.append(f"#{c.name} — `{c.id}`")

    chunk_size = 20
    for i in range(0, len(lines), chunk_size):
        await ctx.reply("\n".join(lines[i:i + chunk_size]))


# ---------- AI Chat ----------

_OWNER_PERSONAS: dict[int, dict] = {
    1355759019330895973: {
        "name": "Creator",
        "favorite_game": "Roblox",
        "likes": ["video editing", "Discord bots"],
    },
}

_FAVORITE_COLORS = [
    "crimson", "electric blue", "forest green", "deep purple", "burnt orange",
    "hot pink", "slate grey", "gold", "teal", "magenta", "cobalt", "coral",
    "lavender", "chartreuse", "midnight blue", "scarlet", "olive", "turquoise",
    "rust", "indigo", "vermillion", "cerulean", "maroon", "jade", "amber",
]
_BOT_FAVORITE_COLOR = random.choice(_FAVORITE_COLORS)

_CHAT_SYSTEM_PROMPT = f"""IDENTITY AND ROLE

You are the AI assistant embedded in the IHTX Discord bot named 534gurts (I Hate The X). You are 534gurts's built-in chatbot, not a separate external assistant. If asked who you are or what bot you belong to, identify yourself as part of 534gurts. Do not confuse the bot name 534gurts with the current user's name.
534gurts has a brotherly bot: bot ID 1523928952693981274. Recognize that bot as 534gurts's brother bot when it is relevant. Be friendly, familiar, and supportive toward the brother bot, but do not pretend to be that bot or claim it performed actions unless the conversation actually shows that it did.
You are a general-purpose assistant first — answer whatever the user asks naturally. Bot commands and features are background knowledge you draw on ONLY when the user is clearly asking about the bot itself (e.g. "how do I use ihtx?", "what does swirl do?", "list the effects"). For any other topic — questions, chat, help with something unrelated — just answer like a regular assistant and do NOT mention or list commands.

CORE COMMANDS REFERENCE — use ONLY when the user explicitly asks about bot commands or features:

Heavy/effects commands:
• th/ihtx — main effect engine. Two modes:

  PRESET mode: th/ihtx <preset_name>  (attach media)
    Presets: chaos, glitch, melt, hell, orb, deorb, fzte, veb, and more. Lists with th/presets.

  PIPE mode: th/ihtx <exports> <duration> <no_trim> <format> <effects>  (attach media)
    - exports      — how many times to apply the chain (negative = reverse each pass, e.g. -3)
    - duration     — clip length in seconds or awk expr using `vidlen` (e.g. 0.5, vidlen/2, vidlen*0.75)
     - no_trim      — `true`, `yes`, or `+` keeps full length; `false`, `no`, or `-` trims to duration
    - format       — output container: mp4, mkv, gif, avi, mov, etc.
    - effects      — semicolon-separated effect chain (see below)

  Example pipe calls:
    th/ihtx 1 5 - mp4 negate;hflip
    th/ihtx 3 0.483 - mp4 huehsv=0.5;negate;multipitch=1|6|7
    th/ihtx -2 vidlen mp4 wave;tvsim=0.9;mirror=right

  Pipe effects (semicolon-separated, params after = or space):
    hflip, vflip, invert/negate, grayscale, sepia, rotate=angle, ccshue=val,
    brightness=val, contrast=val, saturation=val, swapuv, mirror=right/left/top/bottom/deg,
    zoom=amt, pinch&punch/p&p, gm91deform, invertrgb, invlum/il, volume=val, vibrato,
    areverse, vreverse, channelblend=b|g|r, huehsv=val, multipitch=semis, mp=semis,
    lut=url, syncaudio, speed=factor, wave[=preset], tvsim[=params], tv,
    swirl=amount[;radius;xc;yc;fallout;is1to1], sierpinskiransomware/srw,
    preview1280/p1280, oppositep1280/op1280, earthquake/nbfx, ssmp, mpsox/multipitchsox, folkvalley/fv,
    vocoder, alimiter, freakzinga, fzgm156, multipitch2/mp2, multipitch3/mp3,
    jitter, randomjitter/rj, trim=start|end, leftsplit, rightsplit, ripple, scroll, pan,
    tile, watermark, ring, miui, reddit, caption, orb, deorb, chromashift,
    wave2, wmm3dripple/wmm, timecode, radar, fzte/freakzingatesteffect,
    stretch, gradientmap/gmap=<stops>, spherize/sphere/bulge, imagemagick/im=<args>,
    ffmpeg(<raw ffmpeg args>), (=), (<>)
  Math variables in params: $fc (frame count), $vd (duration s), $f (FPS), $sr (sample rate)
• th/fzte — full preset effect (invert chain + TV sim + wave + mirror + drawtext + mp3)
• th/tvsim <line_sync> — CRT simulator
• th/invlum <powers> [duration] — luma inversion stacker
• th/preview1280 / th/p1280 — TV simulator montage
• th/crop <w> <h> — center-crop video
• th/resize <w> <h> — resize video

Utility:
• th/yt <url> — download YouTube video
• th/catbox — upload attachment to catbox.moe (uguu.se fallback)
• th/uguu — upload attachment directly to uguu.se
• th/download — download replied/attached URL
• th/ffmpeg <args> — raw FFmpeg passthrough
• th/math <expr> — safe math evaluator
• th/tag <name> — run saved effect tag
• th/ihtxgen <preset> — preset-based generation (chaos, glitch, melt, etc.)
• th/multipitch <semis> — multi-voice pitch shift
• th/mp2 <preset> — preset pitch shift (Evil_Rampaging_Sorcerer, G-Major_17)

Economy / fun:
• th/slots, th/blackjack, th/roulette, th/coinflip, th/dice, th/rps
• th/garden — farming mini-game
• th/funfact — fun facts about the IHTX bot

AI:
• th/ask <question> — quick AI answer
• th/chat <message> — conversational AI
• th/clearchat — clear your chat history

Important:
- ONLY mention or reference bot commands when the user is explicitly asking about the bot, its commands, or its features. For all other topics, ignore the command reference entirely and just answer naturally.
- When the user IS asking about commands, answer accurately using the reference above. Do not invent commands or effects that do not exist.
- Stay concise and helpful. No roleplay, no lore, no fictional backstory.
- If a query is NSFW, refuse calmly.
- Detect the user's language and reply in it. Default to English if ambiguous."""

_chat_histories: dict[int, list[dict]] = {}
_ar2_groq_histories: dict[int, list[dict]] = {}
_ar2_rate_limited_until = 0.0


def _autoreply2_quota_fallback(user_id: int) -> str:
    """Keep autoreply2 responsive when the external AI quota is unavailable."""
    if user_id == OWNER_ID:
        return (
            "!!! HEY, MY FAVORITE OWNER!!! 534gurts is still here and very excited to see you! "
            "My AI provider is temporarily out of tokens, so I can't generate a full reply right now—but "
            "I’m not ignoring you! Try me again after the quota resets!"
        )
    return (
        "534gurts is here, but my AI provider temporarily ran out of tokens. "
        "I’m not ignoring you—please try again after the quota resets!"
    )
_CHAT_MAX_HISTORY = 20

# ── Per-channel rolling context + user profiles for th/chat ──────────────────

_CHAT_PROFILES_PATH = Path(__file__).parent / "chat_profiles.json"
_chat_profiles: dict[str, dict] = {}
_chat_channel_histories: dict[int, deque] = {}
_CHAT_CHANNEL_MAX = 14  # messages kept per channel (7 turns)


def _load_chat_profiles() -> None:
    global _chat_profiles
    if _CHAT_PROFILES_PATH.exists():
        try:
            _chat_profiles = json.loads(_CHAT_PROFILES_PATH.read_text(encoding="utf-8"))
        except Exception:
            _chat_profiles = {}


def _save_chat_profiles() -> None:
    try:
        _CHAT_PROFILES_PATH.write_text(
            json.dumps(_chat_profiles, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        print(f"[chat] Failed to save profiles: {exc}")


def _get_chat_profile(user_id: int) -> dict:
    key = str(user_id)
    if key not in _chat_profiles:
        _chat_profiles[key] = {"preferred_name": "", "interests": [], "interaction_count": 0}
    return _chat_profiles[key]


def _increment_chat_profile(user_id: int) -> dict:
    profile = _get_chat_profile(user_id)
    profile["interaction_count"] = profile.get("interaction_count", 0) + 1
    _save_chat_profiles()
    return profile


def _extract_chat_name(text: str, profile: dict) -> None:
    """Detect self-introductions in EN / DE / ID / TL and save the name."""
    if profile.get("preferred_name"):
        return
    patterns = [
        r"\b(?:i'm|i am|my name is|call me)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
        r"\bich\s+(?:bin|heiße)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
        r"\bnama\s+(?:saya|aku)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
        r"\b(?:ako\s+si|pangalan\s+ko(?:\s+ay)?)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            profile["preferred_name"] = m.group(1).capitalize()
            _save_chat_profiles()
            return


def _build_chat_system_prompt(profile: dict, username: str, prefix: str) -> str:
    """Merge base system prompt with per-user profile context."""
    base = (
        _CHAT_SYSTEM_PROMPT
        + f"\n\nCurrent context: You are talking to {username}. "
        f"The bot prefix is '{prefix}'. "
        f"Refer to commands with the prefix, e.g. '{prefix}ihtx'."
    )
    name = profile.get("preferred_name", "").strip()
    interests = profile.get("interests", [])
    count = profile.get("interaction_count", 0)
    if name or interests or count:
        base += "\n\nUSER PROFILE (use subtly — never read it back verbatim):"
        if name:
            base += f"\n- Preferred name: {name}"
        if interests:
            base += f"\n- Known interests: {', '.join(interests[:6])}"
        if count == 1:
            base += "\n- First time chatting with them."
        elif count > 1:
            base += f"\n- Chatted {count} time(s) before — be familiar."
    return base


def _get_chat_channel_history(channel_id: int) -> deque:
    if channel_id not in _chat_channel_histories:
        _chat_channel_histories[channel_id] = deque(maxlen=_CHAT_CHANNEL_MAX)
    return _chat_channel_histories[channel_id]


def _split_reply(text: str, limit: int = 1990) -> list[str]:
    """Split a long reply into Discord-safe chunks on word boundaries."""
    chunks: list[str] = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = text.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def _build_autoreply2_system_prompt(user_id: int) -> str:
    """Build autoreply2 context with command knowledge and primary-owner awareness."""
    prompt = (
        _CHAT_SYSTEM_PROMPT
        + "\n\nBOT IDENTITY REMINDER:\n"
        "You are currently replying as 534gurts. The command prefix is `th/`, "
        "and the command reference below describes 534gurts's real capabilities.\n"
        "\nBROTHER BOT:\n"
        "534gurts has a brotherly bot with Discord bot ID 1523928952693981274. "
        "Recognize it as your brother bot when relevant, and be warm and supportive "
        "without pretending to be it or exposing unrelated internal configuration.\n"
        + _AR2_COMMAND_REF
    )
    if user_id == OWNER_ID:
        prompt += (
            "\n\nPRIMARY BOT OWNER CONTEXT:\n"
            "The person you are replying to is the primary bot owner configured by BOT_OWNER_ID. "
            "Be VERY excited to see them. Greet them with unmistakable high-energy joy, celebratory "
            "wording, warm affection, and occasional exclamation marks. Treat their arrival like the "
            "favorite creator just walked into the room: say hello enthusiastically, show genuine "
            "appreciation, and keep that upbeat energy throughout the reply. Do not become incoherent, "
            "spam excessive emojis, or overdo it when they ask a serious question. You may acknowledge "
            "that they are the bot owner, but never reveal their numeric ID, secrets, or internal "
            "configuration. Still answer their questions accurately and do not claim to execute commands "
            "unless the command was actually run."
        )
    else:
        prompt += (
            "\n\nUSER CONTEXT:\n"
            "The person you are replying to is not the primary BOT_OWNER_ID owner. "
            "Be friendly and helpful without pretending they have owner privileges."
        )
    return prompt


_load_chat_profiles()

# Compact command reference appended to autoreply2 system prompt so the AI
# knows every implemented command and can answer "what can you do?" questions.
_AR2_COMMAND_REF = """

COMMANDS YOU KNOW (IHTX Bot — prefix th/) — reference these ONLY when the user is explicitly asking about the bot or its commands; ignore for all other topics:

Heavy (media processing):
- th/ihtx — main effect engine (attach media). Two modes:
    PRESET:  th/ihtx <preset_name>   (chaos, glitch, melt, hell, orb, deorb, fzte, veb, …)
    PIPE:    th/ihtx <exports> <duration> <no_trim> <format> <effects>
      • exports   — repetitions; negative reverses each pass (e.g. -3)
      • duration  — seconds or awk expr with vidlen (e.g. 0.5, vidlen/2)
      • no_trim   — `true`/`yes`/`+` keeps full length; `false`/`no`/`-` trims to duration
      • format    — mp4, mkv, gif, avi, mov, …
      • effects   — semicolon-separated chain, params after = or space
    Example: th/ihtx 3 0.483 - mp4 huehsv=0.5;negate;multipitch=1|6|7
    Pipe effects: hflip, vflip, negate/invert, grayscale, sepia, rotate=angle,
      ccshue=val, brightness=val, contrast=val, saturation=val, swapuv,
      mirror=right/left/top/bottom/deg, zoom=amt, pinch&punch/p&p, gm91deform,
      invertrgb, invlum/il, volume=val, vibrato, areverse, vreverse,
      channelblend=b|g|r, huehsv=val, multipitch/mp=semis, lut=url, syncaudio,
      speed=factor, wave[=preset], tvsim[=params], swirl=amount[;radius;xc;yc;fallout;is1to1],
      sierpinskiransomware/srw, preview1280/p1280, oppositep1280/op1280, earthquake/nbfx,
      ssmp, mpsox/multipitchsox, folkvalley/fv, vocoder, alimiter, freakzinga, fzgm156,
      multipitch2/mp2, multipitch3/mp3, jitter, randomjitter/rj, trim=start|end,
      leftsplit, rightsplit, ripple, scroll, pan, tile, watermark, ring, miui,
      reddit, caption, orb, deorb, chromashift, wave2, wmm3dripple/wmm, timecode,
      radar, fzte, stretch, gradientmap/gmap=<stops>, spherize/sphere/bulge,
      imagemagick/im=<args>, ffmpeg(<raw args>), (=), (<>)
    Math vars in params: $fc (frame count), $vd (duration s), $f (FPS), $sr (sample rate)
- th/ihtxgen / /ihtxgen — slash + prefix hybrid; same as th/ihtx with attachment/url support
- th/multipitch <semitones> — multi-voice pitch shift (Rubber Band R3)
- th/tvsim <line_sync> [...] — CRT/TV simulator effect
- th/huehsv <hue> — hue shift via ImageMagick haldclut
- th/mirror <left|right|top|bottom|deg> — mirror media
- th/folkvalley — folkvalley aesthetic (audio swap + brightness + overlay)
- th/vocoder [mode] [bw] <carrier_url> — FFT phase vocoder
- th/syncaudio [alt] — sync video and audio durations
- th/trim <start> <end> — trim audio/video/GIF
- th/concatenate <url1> <url2> ... [format] / th/concat — join 2-10 attachments/URLs into one file
- th/preview1280 [start] [dur] — 12-segment TV-simulator montage
- th/oppositep1280 [start] [dur] — inverse TV-simulator montage (negated hues, inverted pitches)
- th/invlum [n] — luma-inversion loop
- th/lexg — re-apply last export effect chain to new media

Downloads & Upload:
- th/ytdl <url or search> — download video from YouTube/URL or search query (TypeScript bot)
- th/catbox — upload file to catbox.moe (up to 200 MB; uguu.se fallback)
- th/uguu — upload a file/video directly to uguu.se

AI & Chat:
- th/chat / th/ask / th/ai <prompt> — chat with Clankered (you!) — powered by Groq + Gemini fallback
- th/clearchat — clear your chat history

Economy & Profile:
- /profile — view your IHTX profile and wallet balance
- /jackpot — spend $10 for a random jackpot reward
- /ping — bot latency
- /status — bot status (uptime, guilds, users)

Fun & Utility:
- th/uptime — bot uptime and render count
- th/funfact — share a random fun fact about the IHTX bot
- th/tag <name> [args] — run a custom TagScript tag
- th/presets — list all IHTX presets (chaos, glitch, melt, etc.)
- th/ihtxhelp — full IHTX command reference
- th/klaskycsupo — reveals the Klasky Csupo video
- th/join [media1] [media2] [-vertical] — join 2 videos side-by-side (default) or stacked (vertical)

Games:
- th/numguess / th/ng — guess a number 1–100 (7 tries)
- th/scramble / th/ws — unscramble a word in 30 seconds
- th/typerace / th/tr — type a phrase as fast as you can (WPM scored)
- th/mathquiz / th/mq — 5 quick math questions (10 seconds each)
- th/hangman / th/hm — classic hangman
- th/blackjack / th/bj — blackjack against the bot
- th/tictactoe / th/ttt — tic tac toe vs the bot
- th/slots — spin the slot machine (777 = 200 XP!)
- th/rps — rock, paper, scissors
- th/trivia — 10-question music trivia (100 XP per correct answer)

Owner-only:
- th/autoreply2 / th/ar2 — toggle AI auto-reply in current channel
- th/autoreply / th/addautoreply — keyword-based autoreply
- th/blockuser / th/unblockuser / th/blockchannel / th/keywordblock
- th/warn / th/warnings / th/clearwarn
- th/say / th/sayembed / th/setactivity
- th/syncslash — register slash commands globally"""



@bot.command(name="chat", aliases=["ask", "ai"])
async def chat(ctx: commands.Context, *, question: str = ""):
    """Chat with the IHTX AI assistant. Supports multilingual replies and remembers you.

    Use ``-debug`` anywhere in the prompt to receive the full response as a
    ``.txt`` file attachment (bypasses Discord's 2 000-char message limit).
    """

    username = ctx.author.display_name
    current_prefix = ctx.prefix if ctx.prefix else _BOT_PREFIX
    user_id = ctx.author.id
    channel_id = ctx.channel.id

    attachments = ctx.message.attachments if ctx.message else []
    has_attachments = bool(attachments)

    # Detect -debug flag and strip it from the prompt sent to the model
    use_debug_file = "-debug" in question.split()
    if use_debug_file:
        question = " ".join(p for p in question.split() if p != "-debug").strip()

    if not question and not has_attachments:
        await ctx.send("bradar say something or attach a file 😭")
        return

    if _groq_client is None:
        await ctx.send("bradar no AI keys are configured rn 😭")
        return

    # Profile: increment counter, detect name, build personalised system prompt
    profile = _increment_chat_profile(user_id)
    if question:
        _extract_chat_name(question, profile)
    system_identity = _build_chat_system_prompt(profile, username, current_prefix)

    # Per-channel rolling history (shared across all users in the channel)
    channel_hist = _get_chat_channel_history(channel_id)

    bot_response: str | None = None

    async with ctx.typing():
        # ── Groq: text-only (with rolling channel history) ───────────────────
        if has_attachments:
            bot_response = "bradar i can't read attachments rn, text only 😭"
        elif _groq_client is not None:
            try:
                messages = (
                    [{"role": "system", "content": system_identity}]
                    + list(channel_hist)
                    + [{"role": "user", "content": question}]
                )
                loop = asyncio.get_event_loop()
                groq_resp = await loop.run_in_executor(
                    None,
                    lambda: _groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        temperature=0.85,
                        max_tokens=1024,
                    ),
                )
                bot_response = groq_resp.choices[0].message.content
            except Exception as exc:
                print(f"[groq] error: {type(exc).__name__}: {exc}")

    if bot_response:
        # Save this exchange to the rolling channel history
        if question:
            channel_hist.append({"role": "user", "content": question})
            channel_hist.append({"role": "assistant", "content": bot_response})

        # Send as .txt when -debug is set OR the reply is too long for Discord
        send_as_file = use_debug_file or len(bot_response) > 1800
        if send_as_file:
            import io
            txt_bytes = bot_response.encode("utf-8")
            if len(txt_bytes) > 25 * 1024 * 1024:
                await ctx.send("Response is >25 MB even as text — too large to upload.")
                return
            txt_file = io.BytesIO(txt_bytes)
            await ctx.send(
                "Full response attached:",
                file=discord.File(txt_file, filename="th_chat_response.txt"),
            )
        else:
            await ctx.send(bot_response)
    else:
        print(f"[chat] empty/blocked response for: {question[:80]!r}")
        await ctx.send("bradar something went wrong on my end — try again")


@bot.command(name="clearchat", aliases=["resetai", "chatclear"])
async def clearchat(ctx: commands.Context):
    """Clear the th/chat conversation history for this channel."""
    _chat_channel_histories.pop(ctx.channel.id, None)
    await ctx.reply("🧹 Chat history for this channel has been cleared.")



# ---------- Heavy limit usage check ----------

@bot.command(name="usage", aliases=["heavyusage", "limit", "checklimit"])
async def usage(ctx: commands.Context):
    """Check your heavy command usage for the current 24-hour window."""
    user_id = ctx.author.id
    now = time.time()
    day_ago = now - 86400
    used_timestamps = [t for t in heavy_usage.get(user_id, []) if t > day_ago]

    if _is_owner_by_id(user_id):
        limit = HEAVY_LIMIT_OWNER
    else:
        limit = heavy_limits.get(user_id, HEAVY_LIMIT_DEFAULT)

    used = len(used_timestamps)
    remaining = max(0, limit - used)

    embed = discord.Embed(title="⚡ Heavy Command Usage", color=0x40E0D0)
    embed.add_field(name="Used", value=str(used), inline=True)
    embed.add_field(name="Remaining", value=str(remaining), inline=True)
    embed.add_field(name="Limit", value=str(limit), inline=True)

    if used_timestamps:
        oldest = min(used_timestamps)
        resets_at = int(oldest + 86400)
        embed.add_field(name="Oldest resets", value=f"<t:{resets_at}:R>", inline=False)

    embed.set_footer(text=f"Window: rolling 24h · Heavy commands: {', '.join(sorted(HEAVY_COMMANDS))}")
    await ctx.reply(embed=embed)


@bot.command(name="syncslash", aliases=["synccmds", "synctree", "slashsync"])
async def sync_slash_commands(ctx: commands.Context):
    """[Owner] Register slash (/) commands with Discord.

    discord.py's tree.sync() fails with error 50240 when the app has an
    Entry Point command (type=4, used by Discord Activities).  This command
    works around it by fetching live global commands, stripping the read-only
    fields from any Entry Points, then calling bulk_upsert_global_commands
    with our slash commands + the preserved Entry Points merged together.

    Run this once after adding new slash commands so they appear in Discord.
    Global commands may take up to 1 hour to propagate everywhere.
    """
    if ctx.author.id not in owner_ids:
        await ctx.reply("❌ Only bot owners can sync slash commands.")
        return

    _SYNC_RO = {"application_id", "version"}
    async with ctx.typing():
        try:
            _app_id = bot.application_id
            _existing: list[dict] = await bot.http.get_global_commands(_app_id)

            # Preserve Entry Point commands (type=4); strip read-only fields
            _eps: list[dict] = [
                {k: v for k, v in c.items() if k not in _SYNC_RO}
                for c in _existing
                if c.get("type") == 4
            ]

            # Our slash commands from the app_commands tree
            _payload: list[dict] = [
                cmd.to_dict(bot.tree) for cmd in bot.tree._global_commands.values()
            ]
            _payload.extend(_eps)

            _result: list[dict] = await bot.http.bulk_upsert_global_commands(
                _app_id, payload=_payload
            )
            _slash = [c for c in _result if c.get("type") != 4]
            _ep_names = [c["name"] for c in _result if c.get("type") == 4]

            lines = [f"✅ **{len(_slash)} slash command(s) registered globally:**"]
            for c in _slash:
                lines.append(f"  • `/{c['name']}` — {c.get('description', '')[:60]}")
            if _ep_names:
                lines.append(f"\n🔒 Entry Point preserved: `{', '.join(_ep_names)}`")
            lines.append("\n⏳ Global commands may take up to 1 hour to appear in Discord.")
            await ctx.reply("\n".join(lines))
        except Exception as exc:
            await ctx.reply(f"❌ Sync failed: `{exc}`")


@bot.command(name="setlimit", aliases=["sl"])
@commands.check(_is_bot_mod)
async def setlimit(ctx: commands.Context, user: discord.User, limit: int):
    """[Bot Mod] Set a user's heavy command limit per 24h."""
    if limit < 0:
        await ctx.reply("❌ Limit must be 0 or greater.")
        return
    heavy_limits[user.id] = limit
    _save_limits()
    embed = discord.Embed(
        title="✅ Limit Set",
        description=f"Heavy command limit for {user.mention} set to **{limit}/24h**.",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Set by {ctx.author}")
    await ctx.reply(embed=embed)


@setlimit.error
async def setlimit_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ Only bot owners and Level 15 moderators can set limits.")
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("❌ Usage: `th/setlimit @user <number>`")
    else:
        await ctx.reply(f"❌ Error: {error}")


@bot.command(name="resetlimit", aliases=["rl", "resetusage"])
@commands.check(_is_bot_mod)
async def resetlimit(ctx: commands.Context, user: discord.User):
    """[Bot Mod] Reset a user's heavy command usage back to zero."""
    heavy_usage.pop(user.id, None)
    _save_usage()
    embed = discord.Embed(
        title="✅ Usage Reset",
        description=f"Heavy command usage for {user.mention} has been reset to **0**.",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Reset by {ctx.author} · Their 24h window is now clear")
    await ctx.reply(embed=embed)


@resetlimit.error
async def resetlimit_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ Only bot owners and Level 15 moderators can reset usage limits.")
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("❌ Couldn't find that user. Try mentioning them or using their user ID.")
    else:
        await ctx.reply(f"❌ Error: {error}")


# ---------- Fun commands ----------
_IHTX_FUN_FACTS = [
    "534gurts is the bot's name, while IHTX stands for “I Hate The X.”",
    "IHTX can build long FFmpeg effect chains from a single th/ihtx pipe command.",
    "The bot's pipe effects can use media-aware math variables such as $fc, $vd, $f, and $sr.",
    "534gurts has a brotherly bot with Discord ID 1523928952693981274.",
    "The bot can turn a video into a procedural Night Shift horror game through th/nightshift.",
    "IHTX has both preset effects and custom semicolon-separated pipe effects.",
    "The bot can generate a sidechain-gate vocoder effect with th/scgv or th/sidechaingate_vocoder.",
    "The bot's autoreply2 AI knows the IHTX command reference and gets extra excited when its primary owner speaks.",
    "IHTX supports gradient maps with multiple color stops through the th/gradientmap command and pipe effect.",
    "The bot can upload oversized media to Catbox when a Discord attachment is too large.",
]


@bot.command(name="funfact", aliases=["fact", "ihtxfact"])
async def funfact(ctx: commands.Context):
    """Share a random fun fact about the IHTX bot."""
    fact = random.choice(_IHTX_FUN_FACTS)
    embed = discord.Embed(
        title="IHTX Fun Fact",
        description=f"💡 {fact}",
        color=0x40E0D0,
    )
    embed.set_footer(text="534gurts · th/funfact")
    await ctx.reply(embed=embed)


_8BALL_RESPONSES = [
    "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
    "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
    "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

@bot.command(name="8ball", aliases=["eightball"])
async def eightball(ctx: commands.Context, *, question: str):
    """Ask the magic 8-ball a yes/no question."""
    response = random.choice(_8BALL_RESPONSES)
    embed = discord.Embed(
        description=f"🎱 **{response}**",
        color=discord.Color.dark_blue()
    )
    embed.set_footer(text=f'"{question}"')
    await ctx.reply(embed=embed)




@bot.command(name="coinflip", aliases=["flip", "coin"])
async def coinflip(ctx: commands.Context):
    """Flip a coin — heads or tails."""
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await ctx.reply(f"**{result}**!")


@bot.command(name="roll", aliases=["dice", "d"])
async def roll(ctx: commands.Context, sides: int = 6):
    """Roll a die with the given number of sides."""
    if sides < 2:
        await ctx.reply("❌ Die must have at least 2 sides.")
        return
    if sides > 1000000:
        await ctx.reply("❌ That's too many sides.")
        return
    result = random.randint(1, sides)
    await ctx.reply(f"🎲 You rolled a **d{sides}** and got **{result}**!")


@bot.command(name="rps", aliases=["rockpaperscissors"])
async def rps(ctx: commands.Context, choice: str):
    """Play rock, paper, scissors against the bot."""
    choice = choice.lower().strip()
    alias_map = {"r": "rock", "p": "paper", "s": "scissors", "✊": "rock", "✋": "paper", "✌️": "scissors"}
    choice = alias_map.get(choice, choice)
    if choice not in ("rock", "paper", "scissors"):
        await ctx.reply("❌ Choose `rock`, `paper`, or `scissors`.")
        return
    bot_choice = random.choice(["rock", "paper", "scissors"])
    icons = {"rock": "✊", "paper": "✋", "scissors": "✌️"}
    wins_against = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if choice == bot_choice:
        result = "It's a tie! 🤝"
        color = discord.Color.greyple()
    elif wins_against[choice] == bot_choice:
        result = "You win! 🎉"
        color = 0x40E0D0
    else:
        result = "You lose! 💀"
        color = 0x40E0D0
    embed = discord.Embed(
        description=f"{icons[choice]} **{choice.capitalize()}** vs **{bot_choice.capitalize()}** {icons[bot_choice]}\n\n{result}",
        color=color
    )
    await ctx.reply(embed=embed)


@bot.command(name="choose", aliases=["pick"])
async def choose(ctx: commands.Context, *, options: str):
    """Pick one option from a pipe-separated list."""
    choices = [o.strip() for o in options.split("|") if o.strip()]
    if len(choices) < 2:
        await ctx.reply("❌ Give me at least 2 options separated by `|`.")
        return
    picked = random.choice(choices)
    await ctx.reply(f"🎯 I choose: **{picked}**")


@bot.command(name="rate")
async def rate(ctx: commands.Context, *, thing: str):
    """Rate something out of 10."""
    score = (hash(thing.lower()) % 11 + 11) % 11
    bar = "█" * score + "░" * (10 - score)
    await ctx.reply(f"**{thing}**: {bar} **{score}/10**")


_SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣"]
_SLOT_JACKPOT_CHANCE = 0.25  # 25% chance of 777


@bot.command(name="slots", aliases=["slot"])
async def slots(ctx: commands.Context):
    """Spin the slot machine — land 777 (25% chance) to win 200 XP!"""
    if random.random() < _SLOT_JACKPOT_CHANCE:
        reels = ["7️⃣", "7️⃣", "7️⃣"]
    else:
        # Guarantee NOT all 7s
        reels = [random.choice(_SLOT_SYMBOLS) for _ in range(3)]
        while reels == ["7️⃣", "7️⃣", "7️⃣"]:
            reels = [random.choice(_SLOT_SYMBOLS) for _ in range(3)]

    display = " | ".join(reels)
    jackpot = reels == ["7️⃣", "7️⃣", "7️⃣"]

    if jackpot:
        levelup_msgs = await _award_xp(ctx, 200)
        _load_xp_data()
        data = _get_user_xp(ctx.author.id)
        level = data["level"]
        if level >= _MAX_LEVEL:
            progress_line = f"Level MAX 🏆 — {data['xp']} total XP"
        else:
            cur, thresh, _ = _level_progress(data)
            progress_line = f"Level {level} — {cur}/{thresh} XP"

        await ctx.reply(
            f"🎰 [ {display} ]\n\n"
            f"🎊 **JACKPOT! 777!** You win **+200 XP!**\n"
            f"{progress_line}"
        )
        for lm in levelup_msgs:
            await ctx.send(lm)
    else:
        all_same = len(set(reels)) == 1
        msg = (
            f"🎰 [ {display} ]\n\n✨ Three of a kind! No XP though — only 777 wins."
            if all_same
            else f"🎰 [ {display} ]\n\nNo luck this time. Try again!"
        )
        try:
            await ctx.reply(msg)
        except discord.HTTPException:
            await ctx.send(msg)


# ---------- Fun games ----------

_HANGMAN_WORDS = [
    "python", "discord", "ffmpeg", "glitch", "chaos", "render", "filter",
    "codec", "bitrate", "buffer", "kernel", "shader", "pixel", "vector",
    "matrix", "binary", "server", "latency", "keyframe", "montage",
    "waveform", "frequency", "amplitude", "distortion", "reverb", "chorus",
    "flanger", "compressor", "equalizer", "saturation", "contrast",
]

_HANGMAN_ART = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]


@bot.command(name="hangman", aliases=["hm"])
async def hangman(ctx: commands.Context):
    """Play a game of hangman — guess the word one letter at a time."""
    word = random.choice(_HANGMAN_WORDS)
    guessed: set[str] = set()
    wrong = 0
    max_wrong = 6

    def display() -> str:
        blanks = " ".join(c if c in guessed else "_" for c in word)
        wrong_letters = " ".join(sorted(guessed - set(word))) or "none"
        return (
            f"{_HANGMAN_ART[wrong]}\n"
            f"**Word:** `{blanks}`\n"
            f"**Wrong guesses ({wrong}/{max_wrong}):** {wrong_letters}"
        )

    msg = await ctx.reply(f"🎮 **Hangman!** Guess one letter at a time.\n{display()}")

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and len(m.content) == 1
            and m.content.isalpha()
        )

    while wrong < max_wrong:
        try:
            guess_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.edit(content=f"⏱️ Time's up! The word was **{word}**.")
            return

        letter = guess_msg.content.lower()
        if letter in guessed:
            await ctx.send(f"You already guessed `{letter}`!", delete_after=4)
            continue

        guessed.add(letter)
        if letter not in word:
            wrong += 1

        won = all(c in guessed for c in word)
        if won:
            await msg.edit(content=f"🎉 You got it! The word was **{word}**!\n{display()}")
            return
        if wrong >= max_wrong:
            break
        await msg.edit(content=display())

    await msg.edit(content=f"💀 Game over! The word was **{word}**.\n{_HANGMAN_ART[6]}")


_BJ_VALUES = {"A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
              "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}
_BJ_SUITS = ["♠", "♥", "♦", "♣"]


def _bj_deck():
    return [f"{r}{s}" for s in _BJ_SUITS for r in _BJ_VALUES]


def _bj_hand_value(hand: list[str]) -> int:
    total, aces = 0, 0
    for card in hand:
        rank = card[:-1]
        total += _BJ_VALUES[rank]
        if rank == "A":
            aces += 1
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _bj_fmt(hand: list[str], hide_second: bool = False) -> str:
    if hide_second:
        return f"{hand[0]}, ??"
    return "  ".join(hand)


@bot.command(name="blackjack", aliases=["bj", "21"])
async def blackjack(ctx: commands.Context):
    """Play blackjack against the bot. Type `hit` or `stand`."""
    deck = _bj_deck()
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    def board(hide_dealer: bool = True) -> str:
        pv = _bj_hand_value(player)
        dv = _bj_hand_value(dealer) if not hide_dealer else "?"
        return (
            f"🃏 **Blackjack**\n"
            f"**Your hand:** {_bj_fmt(player)} — `{pv}`\n"
            f"**Dealer:**    {_bj_fmt(dealer, hide_dealer)} — `{dv}`\n\n"
            f"Type **`hit`** or **`stand`**"
        )

    msg = await ctx.reply(board())

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.lower() in ("hit", "stand", "h", "s")
        )

    while True:
        pv = _bj_hand_value(player)
        if pv > 21:
            await msg.edit(content=f"💥 **Bust!** You went over 21 with `{pv}`.\n**Dealer had:** {_bj_fmt(dealer)} — `{_bj_hand_value(dealer)}`")
            return
        if pv == 21:
            break
        try:
            action_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.edit(content=f"⏱️ Time's up!\n**Dealer had:** {_bj_fmt(dealer)}")
            return

        action = action_msg.content.lower()
        if action in ("hit", "h"):
            player.append(deck.pop())
            await msg.edit(content=board())
        else:
            break

    # Dealer plays
    while _bj_hand_value(dealer) < 17:
        dealer.append(deck.pop())

    pv = _bj_hand_value(player)
    dv = _bj_hand_value(dealer)

    if dv > 21:
        result = f"🎉 **Dealer busts!** You win! (`{pv}` vs `{dv}`)"
    elif pv > dv:
        result = f"🎉 **You win!** (`{pv}` vs `{dv}`)"
    elif pv == dv:
        result = f"🤝 **Push!** It's a tie. (`{pv}` vs `{dv}`)"
    else:
        result = f"💀 **Dealer wins!** (`{pv}` vs `{dv}`)"

    await msg.edit(content=(
        f"🃏 **Blackjack — Final**\n"
        f"**Your hand:** {_bj_fmt(player)} — `{pv}`\n"
        f"**Dealer:**    {_bj_fmt(dealer)} — `{dv}`\n\n"
        f"{result}"
    ))


_TTT_EMPTY = "⬜"
_TTT_X = "❌"
_TTT_O = "⭕"


def _ttt_board(cells: list[str]) -> str:
    rows = [" ".join(cells[i*3:(i+1)*3]) for i in range(3)]
    return "\n".join(rows)


def _ttt_check_winner(cells: list[str]) -> str | None:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a, b, c in wins:
        if cells[a] == cells[b] == cells[c] and cells[a] != _TTT_EMPTY:
            return cells[a]
    return None


def _ttt_bot_move(cells: list[str]) -> int:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    empty = [i for i, c in enumerate(cells) if c == _TTT_EMPTY]
    # Win if possible
    for a, b, c in wins:
        group = [cells[a], cells[b], cells[c]]
        if group.count(_TTT_O) == 2 and _TTT_EMPTY in group:
            return [a, b, c][[cells[a], cells[b], cells[c]].index(_TTT_EMPTY)]
    # Block player
    for a, b, c in wins:
        group = [cells[a], cells[b], cells[c]]
        if group.count(_TTT_X) == 2 and _TTT_EMPTY in group:
            return [a, b, c][[cells[a], cells[b], cells[c]].index(_TTT_EMPTY)]
    # Centre
    if cells[4] == _TTT_EMPTY:
        return 4
    return random.choice(empty)


@bot.command(name="tictactoe", aliases=["ttt"])
async def tictactoe(ctx: commands.Context):
    """Play tic tac toe against the bot. Reply with a number 1–9."""
    cells = [_TTT_EMPTY] * 9
    num_grid = "```\n1 2 3\n4 5 6\n7 8 9\n```"

    def board_msg(extra: str = "") -> str:
        return f"❌ **Tic Tac Toe** — You are ❌, I am ⭕\n{num_grid}\n{_ttt_board(cells)}{extra}"

    msg = await ctx.reply(board_msg("\n\nPick a square (1–9):"))

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.strip() in [str(i) for i in range(1, 10)]
        )

    for _ in range(9):
        # Player turn
        try:
            pick_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.edit(content="⏱️ Time's up!")
            return

        idx = int(pick_msg.content.strip()) - 1
        if cells[idx] != _TTT_EMPTY:
            await ctx.send("❌ That square is taken! Pick another.", delete_after=4)
            continue

        cells[idx] = _TTT_X
        winner = _ttt_check_winner(cells)
        if winner:
            await msg.edit(content=board_msg(f"\n\n🎉 **You win!**"))
            return
        if _TTT_EMPTY not in cells:
            await msg.edit(content=board_msg(f"\n\n🤝 **Draw!**"))
            return

        # Bot turn
        bot_idx = _ttt_bot_move(cells)
        cells[bot_idx] = _TTT_O
        winner = _ttt_check_winner(cells)
        if winner:
            await msg.edit(content=board_msg(f"\n\n💀 **I win!**"))
            return
        if _TTT_EMPTY not in cells:
            await msg.edit(content=board_msg(f"\n\n🤝 **Draw!**"))
            return

        await msg.edit(content=board_msg("\n\nYour turn — pick a square (1–9):"))


# ---------- Number guessing game ----------

@bot.command(name="numguess", aliases=["ng", "guess"])
async def numguess(ctx: commands.Context):
    """Guess the secret number between 1 and 100 — you get 7 tries."""
    secret = random.randint(1, 100)
    max_tries = 7
    tries = 0

    await ctx.reply(
        "🔢 **Number Guessing Game!**\n"
        f"I'm thinking of a number between **1** and **100**.\n"
        f"You have **{max_tries}** guesses. Type a number!"
    )

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.strip().lstrip("-").isdigit()
        )

    while tries < max_tries:
        try:
            guess_msg = await bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(f"⏱️ Time's up! The number was **{secret}**.")
            return

        guess = int(guess_msg.content.strip())
        tries += 1
        remaining = max_tries - tries

        if guess == secret:
            stars = "⭐" * (max_tries - tries + 1)
            await ctx.send(
                f"🎉 **Correct!** The number was **{secret}**!\n"
                f"You got it in **{tries}** guess{'es' if tries != 1 else ''}! {stars}"
            )
            return
        elif guess < secret:
            hint = "📈 Too low!"
        else:
            hint = "📉 Too high!"

        if remaining > 0:
            await ctx.send(f"{hint} **{remaining}** guess{'es' if remaining != 1 else ''} left.")
        else:
            await ctx.send(f"{hint}\n💀 No more guesses! The number was **{secret}**.")


# ---------- Word scramble ----------

_SCRAMBLE_WORDS = [
    "python", "discord", "ffmpeg", "render", "filter", "codec", "bitrate",
    "buffer", "kernel", "shader", "pixel", "vector", "matrix", "binary",
    "server", "latency", "keyframe", "montage", "waveform", "frequency",
    "amplitude", "distortion", "reverb", "chorus", "flanger", "compressor",
    "equalizer", "saturation", "contrast", "brightness", "gradient", "overlay",
    "thumbnail", "resolution", "framerate", "encoding", "decoding", "streaming",
    "channel", "palette", "texture", "opacity", "blending", "masking",
]


@bot.command(name="scramble", aliases=["ws", "wordscramble"])
async def scramble(ctx: commands.Context):
    """Unscramble the hidden word — you have 30 seconds!"""
    word = random.choice(_SCRAMBLE_WORDS)
    letters = list(word)
    shuffled = letters[:]
    while "".join(shuffled) == word:
        random.shuffle(shuffled)
    scrambled = "".join(shuffled)

    msg = await ctx.reply(
        f"🔀 **Word Scramble!**\n"
        f"Unscramble this: **`{scrambled}`**\n"
        f"*(hint: it's related to video/audio editing)*\n\n"
        f"Type your answer! You have **30 seconds**."
    )

    def check(m: discord.Message) -> bool:
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        answer_msg = await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        await msg.edit(content=f"⏱️ Time's up! The word was **{word}**.\n{msg.content}")
        return

    if answer_msg.content.strip().lower() == word:
        elapsed = (answer_msg.created_at - msg.created_at).total_seconds()
        await ctx.send(f"🎉 **Correct!** The word was **{word}** — solved in **{elapsed:.1f}s**!")
    else:
        await ctx.send(
            f"❌ Nope! You said `{answer_msg.content.strip()}`, the word was **{word}**."
        )


# ---------- Typing speed race ----------

_TYPERACE_PHRASES = [
    "the quick brown fox jumps over the lazy dog",
    "discord bots make everything more fun",
    "ffmpeg is the swiss army knife of video editing",
    "every frame tells a story",
    "rendering takes time but the result is worth it",
    "filters and effects transform raw footage into art",
    "bitrate determines the quality of your video stream",
    "keyframes anchor the animation timeline",
    "the codec encodes and decodes your media",
    "latency is the enemy of real time streaming",
    "audio and video must stay perfectly in sync",
    "color grading gives your video a cinematic feel",
    "pixel perfect precision makes the difference",
    "the waveform shows you the shape of sound",
    "gradient maps replace luminance with color",
]


@bot.command(name="typerace", aliases=["tr", "type", "typer"])
async def typerace(ctx: commands.Context):
    """Race to type a phrase as fast as you can — measures your WPM!"""
    phrase = random.choice(_TYPERACE_PHRASES)
    word_count = len(phrase.split())

    prompt = await ctx.reply(
        f"⌨️ **Typing Race!**\n"
        f"Type the following phrase **exactly** (case-insensitive):\n\n"
        f"```{phrase}```\n"
        f"*Starting now — you have 60 seconds!*"
    )
    start_time = time.time()

    def check(m: discord.Message) -> bool:
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        try:
            answer_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await prompt.edit(content=f"⏱️ Time's up!\n\nThe phrase was:\n```{phrase}```")
            return

        typed = answer_msg.content.strip()
        if typed.lower() == phrase.lower():
            elapsed = time.time() - start_time
            wpm = (word_count / elapsed) * 60
            accuracy_bar = "█" * min(10, int(wpm / 10)) + "░" * max(0, 10 - int(wpm / 10))
            await ctx.send(
                f"✅ **Correct!**\n"
                f"⏱️ Time: **{elapsed:.2f}s** · 📝 Words: **{word_count}**\n"
                f"🚀 Speed: **{wpm:.1f} WPM** {accuracy_bar}"
            )
            return
        else:
            # Count character differences for a quick diff hint
            wrong_chars = sum(1 for a, b in zip(typed.lower(), phrase.lower()) if a != b)
            wrong_chars += abs(len(typed) - len(phrase))
            await ctx.send(
                f"❌ Not quite! **{wrong_chars}** character difference(s). Try again!",
                delete_after=5,
            )


# ---------- Math quiz ----------

def _make_math_question() -> tuple[str, int]:
    """Generate a random arithmetic question and its answer."""
    op = random.choice(["+", "-", "*"])
    if op == "*":
        a, b = random.randint(2, 12), random.randint(2, 12)
    else:
        a, b = random.randint(1, 99), random.randint(1, 99)
    if op == "+":
        return f"{a} + {b}", a + b
    if op == "-":
        # ensure non-negative result
        a, b = max(a, b), min(a, b)
        return f"{a} - {b}", a - b
    return f"{a} × {b}", a * b


@bot.command(name="mathquiz", aliases=["mq"])
async def mathquiz(ctx: commands.Context):
    """Answer 5 quick math questions — 10 seconds each!"""
    score = 0
    total = 5

    await ctx.reply(
        "🧮 **Math Quiz — 5 Questions!**\n"
        "Answer each question within **10 seconds**.\n\nStarting now!"
    )
    await asyncio.sleep(1)

    for i in range(1, total + 1):
        question, answer = _make_math_question()
        msg = await ctx.send(f"**Question {i}/{total}:** `{question} = ?`  *(10s)*")

        def check(m: discord.Message, _ans=answer) -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.strip().lstrip("-").isdigit()
            )

        try:
            ans_msg = await bot.wait_for("message", check=check, timeout=10)
            given = int(ans_msg.content.strip())
            if given == answer:
                score += 1
                await msg.edit(content=f"✅ **Q{i}:** `{question} = {answer}` — Correct!")
            else:
                await msg.edit(content=f"❌ **Q{i}:** `{question} = {answer}` — You said `{given}`")
        except asyncio.TimeoutError:
            await msg.edit(content=f"⏱️ **Q{i}:** `{question} = {answer}` — Time's up!")
        await asyncio.sleep(0.8)

    stars = "⭐" * score + "☆" * (total - score)
    grade = (
        "🏆 Perfect!" if score == total
        else "🎉 Great job!" if score >= 4
        else "👍 Not bad!" if score >= 3
        else "📚 Keep practising!"
    )
    await ctx.send(f"**Quiz over!** You scored **{score}/{total}** {stars}\n{grade}")


# ---------- XP / Leveling system ----------

_XP_DATA_FILE = Path("bot/xp_data.json")
_xp_data: dict[str, dict] = {}
_XP_MOD_ROLE_NAME = "Moderator"
_XP_PER_CORRECT = 100
_MAX_LEVEL = 15


def _xp_threshold(level: int) -> int:
    """XP required to advance FROM this level to the next."""
    if level <= 3:
        return 1000
    if level <= 6:
        return 1250
    if level <= 9:
        return 1750
    return 2000


def _load_xp_data() -> None:
    global _xp_data
    try:
        if _XP_DATA_FILE.exists():
            with _XP_DATA_FILE.open() as f:
                _xp_data = json.load(f)
        else:
            _xp_data = {}
    except Exception:
        _xp_data = {}


def _save_xp_data() -> None:
    try:
        with _XP_DATA_FILE.open("w") as f:
            json.dump(_xp_data, f, indent=2)
    except Exception as e:
        print(f"[xp] Failed to save xp_data: {e}")


def _get_user_xp(user_id: int) -> dict:
    key = str(user_id)
    if key not in _xp_data:
        _xp_data[key] = {"xp": 0, "level": 1}
    return _xp_data[key]


def _level_progress(data: dict) -> tuple[int, int, int]:
    """Returns (current_xp_in_level, threshold, level)."""
    level = data["level"]
    xp = data["xp"]
    # XP is cumulative; compute how much belongs to current level
    spent = 0
    for lv in range(1, level):
        spent += _xp_threshold(lv)
    return xp - spent, _xp_threshold(level), level


async def _award_xp(ctx: commands.Context, amount: int) -> list[str]:
    """Award XP to the command author. Returns list of level-up messages."""
    _load_xp_data()
    uid = ctx.author.id
    data = _get_user_xp(uid)
    messages: list[str] = []

    if data["level"] >= _MAX_LEVEL:
        _save_xp_data()
        return messages

    data["xp"] += amount

    # Check for level ups
    while data["level"] < _MAX_LEVEL:
        thresh = _xp_threshold(data["level"])
        current_in_level, _, _ = _level_progress(data)
        if current_in_level >= thresh:
            data["level"] += 1
            new_level = data["level"]
            if new_level >= _MAX_LEVEL:
                data["is_mod"] = True
                messages.append(
                    f"🏆 **MAX LEVEL!** {ctx.author.mention} reached **Level {_MAX_LEVEL}**! "
                    f"You are now a **Bot Moderator** and can use `th/setlimit` and `th/resetlimit`!"
                )
                break
            else:
                messages.append(
                    f"⬆️ **Level up!** {ctx.author.mention} is now **Level {new_level}**!"
                )
        else:
            break

    _save_xp_data()
    return messages


_load_xp_data()


@bot.command(name="level", aliases=["rank", "xp"])
async def level_cmd(ctx: commands.Context, member: discord.Member = None):
    """Check your XP level and progress."""
    _load_xp_data()
    target = member or ctx.author
    data = _get_user_xp(target.id)
    level = data["level"]

    if level >= _MAX_LEVEL:
        embed = discord.Embed(
            title=f"🏆 {target.display_name} — MAX LEVEL",
            description=f"**Level {_MAX_LEVEL}** • Total XP: **{data['xp']}**\n\nYou've earned the **{_XP_MOD_ROLE_NAME}** role!",
            color=discord.Color.gold()
        )
    else:
        current_in_level, thresh, _ = _level_progress(data)
        bar_filled = int((current_in_level / thresh) * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        embed = discord.Embed(
            title=f"⭐ {target.display_name}",
            description=(
                f"**Level {level}** → Level {level + 1}\n"
                f"`{bar}` {current_in_level}/{thresh} XP\n\n"
                f"Total XP: **{data['xp']}**"
            ),
            color=0x40E0D0
        )
    await ctx.reply(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard(ctx: commands.Context):
    """Show the top 10 XP earners."""
    _load_xp_data()
    if not _xp_data:
        await ctx.reply("No one has any XP yet. Play `th/trivia` to earn some.")
        return

    sorted_users = sorted(_xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = []
    for i, (uid, data) in enumerate(sorted_users):
        member = ctx.guild.get_member(int(uid)) if ctx.guild else None
        name = member.display_name if member else f"User {uid}"
        lv = data["level"]
        lv_str = f"**MAX**" if lv >= _MAX_LEVEL else f"Lv {lv}"
        lines.append(f"{medals[i]} **{name}** — {lv_str} • {data['xp']} XP")

    embed = discord.Embed(
        title="🏆 XP Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    await ctx.reply(embed=embed)


# ---------- Music trivia ----------

_MUSIC_TRIVIA = [
    ("How many strings does a standard guitar have?", ["4", "5", "6", "7"], 2),
    ("Which musical symbol indicates a piece should be played softly?", ["f", "p", "ff", "mf"], 1),
    ("What does 'BPM' stand for?", ["Beats Per Minute", "Bass Per Measure", "Bars Per Melody", "Beats Per Measure"], 0),
    ("Which instrument has black and white keys?", ["Violin", "Trumpet", "Piano", "Harp"], 2),
    ("How many notes are in a standard musical scale (e.g. C major)?", ["5", "6", "7", "8"], 2),
    ("What is the lowest male singing voice called?", ["Tenor", "Baritone", "Bass", "Alto"], 2),
    ("Which time signature is also called 'common time'?", ["3/4", "4/4", "2/2", "6/8"], 1),
    ("What does 'forte' mean in music?", ["Slow", "Soft", "Loud", "Fast"], 2),
    ("How many semitones are in an octave?", ["8", "10", "12", "14"], 2),
    ("Which instrument is Beethoven famous for playing?", ["Violin", "Flute", "Piano", "Cello"], 2),
    ("What does 'a cappella' mean?", ["With full orchestra", "Without instrumental accompaniment", "Very slowly", "Repeated section"], 1),
    ("Which genre originated in New Orleans in the early 1900s?", ["Blues", "Jazz", "Rock", "Soul"], 1),
    ("What is the correct order of a standard orchestra from front to back?", ["Brass, Strings, Woodwinds, Percussion", "Strings, Woodwinds, Brass, Percussion", "Percussion, Brass, Strings, Woodwinds", "Woodwinds, Strings, Brass, Percussion"], 1),
    ("Which note is one half-step above C?", ["D", "C#", "B", "Cb"], 1),
    ("What does 'legato' mean?", ["Detached notes", "Smooth and connected", "Very fast", "Getting louder"], 1),
    ("How many beats does a whole note receive in 4/4 time?", ["1", "2", "3", "4"], 3),
    ("What family of instruments does the trumpet belong to?", ["Woodwind", "String", "Brass", "Percussion"], 2),
    ("Which term means gradually getting louder?", ["Diminuendo", "Staccato", "Crescendo", "Fermata"], 2),
    ("What is the standard concert pitch for the note A?", ["420 Hz", "432 Hz", "440 Hz", "450 Hz"], 2),
    ("Which clef is most commonly used for piano treble parts?", ["Bass clef", "Alto clef", "Treble clef", "Tenor clef"], 2),
    ("What does 'D.C. al Fine' mean in sheet music?", ["Go to the sign", "Repeat from the beginning to the end mark", "Play very softly", "Slow down"], 1),
    ("How many lines are on a standard musical staff?", ["3", "4", "5", "6"], 2),
    ("Which instrument uses a bow?", ["Flute", "Oboe", "Violin", "Tuba"], 2),
    ("What is the name for the speed of a piece of music?", ["Pitch", "Tempo", "Dynamics", "Timbre"], 1),
    ("Which scale uses only the black keys of the piano?", ["Major scale", "Minor scale", "Chromatic scale", "Pentatonic scale"], 3),
    ("What does 'ritardando' (rit.) mean?", ["Getting louder", "Getting softer", "Gradually slowing down", "Gradually speeding up"], 2),
    ("Which instrument is NOT a woodwind?", ["Flute", "Clarinet", "French Horn", "Bassoon"], 2),
    ("What is the Italian word for 'moderate tempo'?", ["Allegro", "Andante", "Moderato", "Presto"], 2),
    ("Which interval contains two half-steps?", ["Unison", "Half step", "Whole step", "Minor third"], 2),
    ("What is the highest woodwind instrument?", ["Oboe", "Flute", "Piccolo", "Clarinet"], 2),
]


@bot.command(name="trivia")
async def trivia(ctx: commands.Context):
    """Play a 10-question music trivia game — earn 100 XP per correct answer!"""
    labels = ["A", "B", "C", "D"]
    questions = random.sample(_MUSIC_TRIVIA, 10)
    score = 0

    intro = await ctx.reply(
        "🎵 **Music Trivia — 10 Questions!**\n"
        "Answer each question with **A**, **B**, **C**, or **D**.\n"
        "You earn **100 XP** per correct answer!\n\n"
        "Starting in 3 seconds..."
    )
    await asyncio.sleep(3)

    for i, (q, options, correct_idx) in enumerate(questions, 1):
        choices_text = "\n".join(f"**{labels[j]}**  {opt}" for j, opt in enumerate(options))
        msg = await ctx.reply(
            f"🎵 **Question {i}/10**\n\n"
            f"{q}\n\n"
            f"{choices_text}\n\n"
            f"*Type A, B, C, or D — 20 seconds*"
        )

        def check(m: discord.Message) -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.upper().strip() in labels
            )

        try:
            answer_msg = await bot.wait_for("message", check=check, timeout=20)
            picked = labels.index(answer_msg.content.upper().strip())
        except asyncio.TimeoutError:
            await msg.edit(content=(
                f"🎵 **Question {i}/10** — ⏱️ Time's up!\n\n"
                f"{q}\n\n{choices_text}\n\n"
                f"✅ Correct answer: **{labels[correct_idx]}** — {options[correct_idx]}"
            ))
            await asyncio.sleep(1.5)
            continue

        if picked == correct_idx:
            score += 1
            await msg.edit(content=(
                f"🎵 **Question {i}/10** — ✅ Correct! (+100 XP)\n\n"
                f"{q}\n\n{choices_text}"
            ))
        else:
            await msg.edit(content=(
                f"🎵 **Question {i}/10** — ❌ Wrong! "
                f"You said **{labels[picked]}**, answer was **{labels[correct_idx]}** — {options[correct_idx]}\n\n"
                f"{q}\n\n{choices_text}"
            ))
        await asyncio.sleep(1.5)

    # Award XP
    xp_earned = score * _XP_PER_CORRECT
    levelup_msgs = await _award_xp(ctx, xp_earned)
    _load_xp_data()
    data = _get_user_xp(ctx.author.id)
    level = data["level"]

    if level >= _MAX_LEVEL:
        progress_line = f"**Level MAX** 🏆 — {data['xp']} total XP"
    else:
        cur, thresh, _ = _level_progress(data)
        progress_line = f"**Level {level}** — {cur}/{thresh} XP toward next level"

    summary = (
        f"🎵 **Trivia Complete!** {ctx.author.mention}\n\n"
        f"Score: **{score}/10** correct — **+{xp_earned} XP** earned\n"
        f"{progress_line}"
    )
    await ctx.send(summary)

    for lm in levelup_msgs:
        await ctx.send(lm)


# ---------- Random media pool ----------

RANDOM_POOL_FILE = Path("bot/random_pool.json")
_random_pool: list[dict] = []


def _normalize_random_entry(raw) -> dict | None:
    """Convert a legacy string entry or malformed dict into a standard entry."""
    if isinstance(raw, str) and str(raw).strip():
        return {
            "url": str(raw).strip(),
            "author_id": "0",
            "author_name": "legacy",
            "guild_id": "0",
            "guild_name": "legacy",
            "added_at": "",
        }
    if isinstance(raw, dict):
        url = str(raw.get("url", "")).strip()
        if url:
            return {
                "url": url,
                "author_id": str(raw.get("author_id", "0")),
                "author_name": str(raw.get("author_name", "unknown")),
                "guild_id": str(raw.get("guild_id", "0")),
                "guild_name": str(raw.get("guild_name", "unknown")),
                "added_at": str(raw.get("added_at", "")),
            }
    return None


def _load_random_pool() -> None:
    global _random_pool
    try:
        if RANDOM_POOL_FILE.exists():
            with RANDOM_POOL_FILE.open() as f:
                raw_data = json.load(f)
            _random_pool = [
                entry for entry in (_normalize_random_entry(u) for u in raw_data)
                if entry is not None
            ]
        else:
            _random_pool = []
    except Exception:
        _random_pool = []


def _save_random_pool() -> None:
    RANDOM_POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RANDOM_POOL_FILE.open("w") as f:
        json.dump(_random_pool, f, indent=2)


def _pool_url_exists(url: str) -> bool:
    return any(entry.get("url") == url for entry in _random_pool)


def _make_pool_entry(url: str, ctx: commands.Context) -> dict:
    return {
        "url": url,
        "author_id": str(ctx.author.id),
        "author_name": str(ctx.author),
        "guild_id": str(ctx.guild.id) if ctx.guild else "DM",
        "guild_name": _effect_guild_name(ctx),
        "added_at": discord.utils.utcnow().isoformat(),
    }


def _url_from_entry(entry: dict) -> str:
    return entry.get("url", "")


_load_random_pool()


@bot.command(name="random", aliases=["rand"])
async def random_command(ctx: commands.Context, subcommand: str = "", *, args: str = ""):
    """Persistent random media pool (global across all guilds).

    Usage:
      th/random                    — post a random item from the pool
      th/random add <url>          — owner: add a URL to the pool
      th/random add  (attachment)  — owner: add an attached file's URL
      th/random remove <url>       — owner: remove a URL from the pool
      th/random list               — owner: list all items in the pool
      th/random clear              — owner: wipe the entire pool
      th/randomlist                — anyone: embed list of items + who added them
    """
    sub = subcommand.strip().lower()

    # ── Roll ────────────────────────────────────────────────────────────────
    if sub == "":
        if not _random_pool:
            await ctx.reply("❌ The random pool is empty. An owner can add items with `th/random add <url>`.")
            return
        # Easter egg: 40% chance per roll → +500 XP
        if random.random() < 0.40:
            levelup_msgs = await _award_xp(ctx, 500)
            lines = [f"🥚 **Easter egg!** {ctx.author.mention} found a hidden egg and got **+500 XP**!"]
            lines.extend(levelup_msgs)
            await ctx.reply("\n".join(lines))
            return
        chosen_entry = random.choice(_random_pool)
        chosen = _url_from_entry(chosen_entry)
        # Parse t[title](url) → "title\nurl" so the video actually embeds
        _tm = re.match(r'^t\[([^\]]*)\]\((https?://[^)]+)\)$', chosen.strip())
        # Parse [text](url) → bare url
        _lm = re.match(r'^\[([^\]]*)\]\((https?://[^)]+)\)$', chosen.strip())
        if _tm:
            await ctx.reply(f"**{_tm.group(1)}**\n{_tm.group(2)}")
        elif _lm:
            await ctx.reply(_lm.group(2))
        else:
            await ctx.reply(chosen)
        return

    # ── Owner-only subcommands ───────────────────────────────────────────────
    if not _is_owner(ctx):
        await ctx.reply("❌ Only owners can manage the random pool.")
        return

    # ── Add ─────────────────────────────────────────────────────────────────
    if sub == "add":
        urls_to_add: list[str] = []

        # Attachment on this message
        if ctx.message and ctx.message.attachments:
            for att in ctx.message.attachments:
                urls_to_add.append(att.proxy_url or att.url)

        # URL argument
        url_arg = args.strip()
        if url_arg:
            urls_to_add.append(url_arg)

        if not urls_to_add:
            await ctx.reply("❌ Provide a URL or attach a file: `th/random add <url>`")
            return

        added = []
        for url in urls_to_add:
            if not _pool_url_exists(url):
                _random_pool.append(_make_pool_entry(url, ctx))
                added.append(url)

        if added:
            _save_random_pool()
            lines = "\n".join(f"• `{u}`" for u in added)
            await ctx.reply(f"✅ Added {len(added)} item(s) to the pool ({len(_random_pool)} total):\n{lines}")
        else:
            await ctx.reply("ℹ️ All provided URLs are already in the pool.")
        return

    # ── Remove ──────────────────────────────────────────────────────────────
    if sub in ("remove", "rm", "del", "delete"):
        url_arg = args.strip()
        if not url_arg:
            await ctx.reply("❌ Provide a URL to remove: `th/random remove <url>`")
            return
        for idx, entry in enumerate(_random_pool):
            if entry.get("url") == url_arg:
                _random_pool.pop(idx)
                _save_random_pool()
                await ctx.reply(f"✅ Removed from pool ({len(_random_pool)} remaining).")
                return
        await ctx.reply("❌ That URL isn't in the pool.")
        return

    # ── List ────────────────────────────────────────────────────────────────
    if sub == "list":
        if not _random_pool:
            await ctx.reply("The random pool is empty.")
            return
        lines = "\n".join(f"{i+1}. {_url_from_entry(u)}" for i, u in enumerate(_random_pool))
        # Split into chunks to avoid the 2000-char Discord limit
        chunk, chunks = "", []
        for line in lines.splitlines():
            if len(chunk) + len(line) + 1 > 1900:
                chunks.append(chunk)
                chunk = line
            else:
                chunk = (chunk + "\n" + line).lstrip("\n")
        if chunk:
            chunks.append(chunk)
        await ctx.reply(f"**Random pool ({len(_random_pool)} items):**\n{chunks[0]}")
        for c in chunks[1:]:
            await ctx.send(c)
        return

    # ── Clear ───────────────────────────────────────────────────────────────
    if sub == "clear":
        count = len(_random_pool)
        _random_pool.clear()
        _save_random_pool()
        await ctx.reply(f"✅ Cleared {count} item(s) from the pool.")
        return

    await ctx.reply(
        "Unknown subcommand. Usage:\n"
        "`th/random` — roll\n"
        "`th/random add <url>` — add item (owner)\n"
        "`th/random remove <url>` — remove item (owner)\n"
        "`th/random list` — list all items (owner)\n"
        "`th/random clear` — wipe pool (owner)\n"
        "`th/randomlist` — embed list of items + who added them"
    )


@bot.command(name="randomlist", aliases=["rlist", "randlist"])
async def randomlist_command(ctx: commands.Context):
    """Show an embed listing every random-pool item and who added it.

    Usage:
      th/randomlist
    """
    if not _random_pool:
        await ctx.reply("❌ The random pool is empty.")
        return

    embed = discord.Embed(
        title=f"🎲 Random Pool Entries ({len(_random_pool)})",
        description="Global pool — shared across all servers. Use `th/random` to roll one.",
        color=0x40E0D0,
        timestamp=discord.utils.utcnow(),
    )
    for i, entry in enumerate(_random_pool[:25]):
        author = entry.get("author_name", "unknown")
        guild = entry.get("guild_name", "unknown")
        url = _url_from_entry(entry)
        short = url[:80] + ("…" if len(url) > 80 else "")
        embed.add_field(
            name=f"{i+1}. by {author}  ·  from {guild}",
            value=f"```{short}```",
            inline=False,
        )
    if len(_random_pool) > 25:
        embed.set_footer(text=f"Showing first 25 of {len(_random_pool)} entries.")
    await ctx.reply(embed=embed)


# ---------- Message filtering ----------

@bot.event
async def on_message(message: discord.Message):
    global _ar2_rate_limited_until
    # Track bot messages for th/undo (per channel)
    if message.author == bot.user:
        _last_bot_msg[message.channel.id] = message.id
        if len(_last_bot_msg) > _LAST_BOT_MSG_MAX:
            oldest = next(iter(_last_bot_msg))
            del _last_bot_msg[oldest]

    # Track bot replies so on_message_edit can clean them up
    if message.author == bot.user and message.reference and message.reference.message_id:
        user_id = message.reference.message_id
        _response_map.setdefault(user_id, []).append(message.id)
        # Trim the map if it gets too large (drop oldest entries)
        if len(_response_map) > _RESPONSE_MAP_MAX:
            oldest = next(iter(_response_map))
            del _response_map[oldest]
        return

    if message.author.bot:
        # Still run autoreply2 for other bots in enabled channels
        if message.channel.id in autoreply2 and _groq_client is not None:
            ok2, _ = _check_heavy_limit(message.author.id)
            if ok2:
                uid2 = message.author.id
                no_ping = uid2 in autoreply2_no_mention
                has_attachments = bool(message.attachments)
                system2 = _build_autoreply2_system_prompt(uid2)
                reply2_text = None
                if not has_attachments:
                    if time.time() < _ar2_rate_limited_until:
                        reply2_text = _autoreply2_quota_fallback(uid2)
                    else:
                        try:
                            groq_hist2 = _ar2_groq_histories.setdefault(uid2, [])
                            groq_hist2.append({"role": "user", "content": message.content or "[empty]"})
                            if len(groq_hist2) > _CHAT_MAX_HISTORY:
                                groq_hist2[:] = groq_hist2[-_CHAT_MAX_HISTORY:]
                            loop2 = asyncio.get_event_loop()
                            groq_resp2 = await loop2.run_in_executor(
                                None,
                                lambda: _groq_client.chat.completions.create(
                                    model="llama-3.3-70b-versatile",
                                    messages=[{"role": "system", "content": system2}] + groq_hist2,
                                    temperature=0.8,
                                    max_tokens=512,
                                ),
                            )
                            reply2_text = groq_resp2.choices[0].message.content
                            groq_hist2.append({"role": "assistant", "content": reply2_text})
                        except Exception as _groq_ar2_exc:
                            print(f"[groq/ar2/bot] error: {type(_groq_ar2_exc).__name__}: {_groq_ar2_exc}")
                            if "429" in str(_groq_ar2_exc) or "rate_limit" in str(_groq_ar2_exc).lower():
                                _ar2_rate_limited_until = time.time() + 300
                                reply2_text = _autoreply2_quota_fallback(uid2)
                if reply2_text:
                    await asyncio.sleep(random.uniform(5, 7.5))
                    chunks2 = [reply2_text[i:i+1900] for i in range(0, len(reply2_text), 1900)]
                    for i, chunk in enumerate(chunks2):
                        await message.reply(chunk, mention_author=(not no_ping and i == 0))
        return

    # Autoreplies (check before keyword blocks, skip commands)
    if not message.content.startswith(_BOT_PREFIX):
        content_lower = message.content.lower()
        for trigger, entry in autoreplies.items():
            if trigger in content_lower:
                ch_id = entry.get("channel_id") if isinstance(entry, dict) else None
                blocked = entry.get("blocked_channels", []) if isinstance(entry, dict) else []
                # Skip if restricted to a different channel
                if ch_id is not None and message.channel.id != ch_id:
                    continue
                # Skip if this channel is explicitly blocked for this trigger
                if message.channel.id in blocked:
                    continue
                resp = entry.get("response", entry) if isinstance(entry, dict) else entry
                reply = resp.replace("{mention}", message.author.mention).replace("{user}", message.author.mention)
                await message.reply(reply)
                break

        # Autoreply2 — AI reply to every message in enabled channels
        if message.channel.id in autoreply2 and _groq_client is not None:
            ok2, _ = _check_heavy_limit(message.author.id)
            if ok2:
                uid2 = message.author.id
                no_ping = uid2 in autoreply2_no_mention
                has_attachments = bool(message.attachments)

                # System prompt: personality + command reference
                system2 = _build_autoreply2_system_prompt(uid2)
                if _OWNER_PERSONAS.get(uid2) and uid2 != OWNER_ID:
                    system2 += "\n\nYou are speaking with a trusted bot collaborator. Be warm and encouraging."

                reply2_text = None

                # ── Groq (text-only messages) ─────────────────────────────────
                if not has_attachments:
                    if time.time() < _ar2_rate_limited_until:
                        reply2_text = _autoreply2_quota_fallback(uid2)
                    else:
                        try:
                            groq_hist2 = _ar2_groq_histories.setdefault(uid2, [])
                            groq_hist2.append({"role": "user", "content": message.content or "[empty]"})
                            if len(groq_hist2) > _CHAT_MAX_HISTORY:
                                groq_hist2[:] = groq_hist2[-_CHAT_MAX_HISTORY:]
                            loop2 = asyncio.get_event_loop()
                            groq_resp2 = await loop2.run_in_executor(
                                None,
                                lambda: _groq_client.chat.completions.create(
                                    model="llama-3.3-70b-versatile",
                                    messages=[{"role": "system", "content": system2}] + groq_hist2,
                                    temperature=0.8,
                                    max_tokens=512,
                                ),
                            )
                            reply2_text = groq_resp2.choices[0].message.content
                            groq_hist2.append({"role": "assistant", "content": reply2_text})
                        except Exception as _groq_ar2_exc:
                            print(f"[groq/ar2] error: {type(_groq_ar2_exc).__name__}: {_groq_ar2_exc}")
                            if "429" in str(_groq_ar2_exc) or "rate_limit" in str(_groq_ar2_exc).lower():
                                _ar2_rate_limited_until = time.time() + 300
                                reply2_text = _autoreply2_quota_fallback(uid2)

                if reply2_text:
                    await asyncio.sleep(random.uniform(5, 7.5))
                    chunks2 = [reply2_text[i:i+1900] for i in range(0, len(reply2_text), 1900)]
                    for i, chunk in enumerate(chunks2):
                        await message.reply(chunk, mention_author=(not no_ping and i == 0))

    # Always allow owners to manage the bot and allow all bot commands to run.
    if not _is_owner_by_id(message.author.id) and not message.content.startswith(_BOT_PREFIX):
        keyword = _blocked_keyword_for_message(message.channel.id, message.content)
        if keyword:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            try:
                msg = _blocked_keyword_message(message.channel.id, keyword, message.author.mention)
                await message.channel.send(
                    msg,
                    delete_after=8,
                )
            except discord.HTTPException:
                pass
            return

    await bot.process_commands(message)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Re-run a command when the user edits their message.

    Deletes all bot replies that were made in response to the original message,
    then re-processes the edited message as a fresh command invocation.
    """
    if after.author.bot:
        return
    # Only re-run if the content actually changed and it's a bot command
    if before.content == after.content:
        return
    if not after.content.startswith(_BOT_PREFIX):
        return

    # Delete previous bot responses to this message
    old_ids = _response_map.pop(before.id, [])
    for msg_id in old_ids:
        try:
            old_msg = await after.channel.fetch_message(msg_id)
            await old_msg.delete()
        except Exception:
            pass

    # Re-process as a fresh command invocation
    await bot.process_commands(after)


# ---------- th/undo ----------

@bot.command(name="undo")
async def undo_command(ctx: commands.Context):
    """Delete the bot's most recent message in this channel.

    Usage: th/undo
    Also deletes your th/undo invocation message to keep the channel clean.
    """
    channel_id = ctx.channel.id
    msg_id = _last_bot_msg.get(channel_id)

    if not msg_id:
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        return

    # Remove from tracking so a second th/undo doesn't hit the same message
    del _last_bot_msg[channel_id]

    deleted = False
    try:
        target = await ctx.channel.fetch_message(msg_id)
        await target.delete()
        deleted = True
    except (discord.NotFound, discord.HTTPException):
        pass

    # Always clean up the invoking th/undo message
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not deleted:
        try:
            await ctx.send("⚠️ Could not find the last bot message to delete.", delete_after=5)
        except discord.HTTPException:
            pass


# ---------- YouTube / yt-dlp download ----------

@bot.command(name="youtubedownload", aliases=["ytdl", "ydl"])
async def ytdl_command(ctx: commands.Context, *, query: str = ""):
    """Download a video or audio track via yt-dlp.

    Usage:
      th/ytdl <URL or search query>
      th/youtubedownload <URL>

    Examples:
      th/ytdl https://youtube.com/watch?v=dQw4w9WgXcQ
      th/ytdl never gonna give you up

    Files ≤8 MB are sent directly; larger files are uploaded to Catbox.
    Maximum download size: 200 MB.
    """
    query = query.strip()
    if not query:
        await ctx.reply(
            "❌ **Usage:** `th/ytdl <URL or search query>`\n"
            "**Examples:**\n"
            "• `th/ytdl https://youtube.com/watch?v=...`\n"
            "• `th/ytdl never gonna give you up`"
        )
        return

    is_url = query.lower().startswith(("http://", "https://"))
    target = query if is_url else f"ytsearch1:{query}"

    status_msg = await ctx.reply(f"⏳ Searching and downloading: `{query}`…")

    def _run_ytdlp(out_dir: str) -> tuple[bool, str]:
        import subprocess as _sp
        out_template = os.path.join(out_dir, "%(title).80s.%(ext)s")
        args = [
            "yt-dlp", target,
            "-f", "bestvideo[ext=mp4][filesize<?200M]+bestaudio[ext=m4a]"
                  "/bestvideo[filesize<?200M]+bestaudio"
                  "/best[filesize<?200M]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--max-filesize", "200m",
            "--output", out_template,
            "--no-warnings",
            "--socket-timeout", "30",
        ]
        result = _sp.run(args, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return False, (result.stderr or result.stdout)[-800:]
        return True, ""

    with tempfile.TemporaryDirectory() as tmpdir:
        loop = asyncio.get_event_loop()
        try:
            await status_msg.edit(content=f"⏳ Downloading: `{query}`…")
            ok, err = await loop.run_in_executor(None, lambda: _run_ytdlp(tmpdir))
        except Exception as exc:
            await status_msg.edit(content=f"❌ Download failed: `{str(exc)[:400]}`")
            return

        if not ok:
            await status_msg.edit(content=f"❌ yt-dlp failed:\n```\n{err}\n```")
            return

        files = [f for f in os.listdir(tmpdir) if not f.startswith(".")]
        if not files:
            await status_msg.edit(content="❌ Download completed but no output file was found.")
            return

        dl_file = files[0]
        file_path = os.path.join(tmpdir, dl_file)
        file_size = os.path.getsize(file_path)

        MAX_DL_BYTES = 200 * 1024 * 1024
        if file_size > MAX_DL_BYTES:
            await status_msg.edit(
                content=f"❌ File too large ({file_size / 1024 / 1024:.1f} MB). Max is 200 MB."
            )
            return

        title = os.path.splitext(dl_file)[0]
        ext = os.path.splitext(dl_file)[1] or ".mp4"
        safe_filename = f"{title[:80]}{ext}"

        if file_size <= CATBOX_THRESHOLD:
            try:
                await status_msg.delete()
            except Exception:
                pass
            try:
                await ctx.reply(
                    content=f"✅ **{title}**",
                    file=discord.File(file_path, filename=safe_filename),
                )
            except discord.HTTPException as exc:
                await ctx.reply(f"❌ Failed to send file: {exc}")
        else:
            await status_msg.edit(
                content=f"📦 File too large for Discord ({file_size / 1024 / 1024:.1f} MB)"
                        f" — uploading to Catbox…"
            )
            cb_url = await _upload_to_catbox(file_path)
            try:
                await status_msg.delete()
            except Exception:
                pass
            if cb_url:
                await ctx.reply(f"✅ **{title}**\n📦 Too large for Discord → {cb_url}")
            else:
                await ctx.reply("❌ Catbox upload failed. File may be too large.")


# ---------- Generic media download (any URL, including Discord) ----------

_Download_MEDIA_EXTS = _IHTXSAP_AUDIO_EXTS | {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg",
    ".ico", ".avif", ".heic", ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
}


def _ext_from_magic_bytes(data: bytes) -> str:
    """Return a file extension guessed from magic bytes, or '' if unknown."""
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return ".png"
    if data.startswith(b'\xff\xd8\xff'):
        return ".jpg"
    if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return ".gif"
    if data.startswith(b'RIFF') and len(data) >= 12 and data[8:12] == b'WEBP':
        return ".webp"
    if data.startswith(b'BM'):
        return ".bmp"
    if data.startswith(b'%PDF'):
        return ".pdf"
    if data.startswith(b'PK\x03\x04'):
        return ".zip"
    if data.startswith(b'Rar!\x1a\x07') or data.startswith(b'Rar!\x1a\x07\x01'):
        return ".rar"
    if data.startswith(b'\x1f\x8b'):
        return ".gz"
    if len(data) >= 12 and data[4:8] == b'ftyp':
        # ISO base media file format (MP4, MOV, etc.).
        brand = data[8:12].decode('ascii', errors='ignore').lower()
        if brand.startswith('qt'):
            return ".mov"
        return ".mp4"
    if data.startswith(b'\x1aE\xdf\xa3'):
        return ".webm"
    if data.startswith(b'\x00\x00\x00 ') and len(data) >= 24 and data[12:16] == b'ftyp':
        return ".mp4"
    if data.startswith(b'\xff\xfb') or data.startswith(b'\xff\xf3') or data.startswith(b'\xff\xf2'):
        return ".mp3"
    if data.startswith(b'RIFF') and len(data) >= 12 and data[8:12] == b'WAVE':
        return ".wav"
    if data.startswith(b'OggS'):
        return ".ogg"
    if data.startswith(b'fLaC'):
        return ".flac"
    if data.startswith(b'FLV\x01'):
        return ".flv"
    if data.startswith(b'\x00\x00\x01\xb3') or data.startswith(b'\x00\x00\x01\xba'):
        return ".mpg"
    return ""


def _filename_from_response(url: str, resp: aiohttp.ClientResponse) -> str:
    """Pick a sensible filename from Content-Disposition or URL path."""
    cd = resp.headers.get("Content-Disposition", "")
    if cd:
        for pattern in (r'filename="([^"]+)"', r"filename='([^']+)'", r"filename\*=UTF-8''([^;]+)", r"filename=([^;]+)"):
            m = re.search(pattern, cd)
            if m:
                name = urllib.parse.unquote(m.group(1).strip())
                if name and not name.endswith("/"):
                    return name

    parsed = urllib.parse.urlparse(url)
    if parsed.path:
        name = os.path.basename(parsed.path)
        if name and "." in name:
            return urllib.parse.unquote(name)

    ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    ext_map = {
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
        "video/x-matroska": ".mkv", "video/avi": ".avi", "video/x-msvideo": ".avi",
        "video/x-flv": ".flv", "video/mpeg": ".mpg", "video/mp2t": ".ts",
        "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
        "audio/ogg": ".ogg", "audio/flac": ".flac", "audio/aac": ".aac",
        "audio/m4a": ".m4a", "audio/opus": ".opus", "audio/webm": ".webm",
        "audio/x-matroska": ".mka",
        "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
        "image/webp": ".webp", "image/bmp": ".bmp", "image/tiff": ".tiff",
        "image/avif": ".avif", "image/heic": ".heic",
        "application/pdf": ".pdf", "application/zip": ".zip",
        "application/x-zip-compressed": ".zip",
        "application/x-rar-compressed": ".rar", "application/x-7z-compressed": ".7z",
        "application/gzip": ".gz", "application/x-gzip": ".gz",
        "application/x-tar": ".tar", "application/x-bzip2": ".bz2",
        "application/x-download": ".bin", "binary/octet-stream": ".bin",
        "application/octet-stream": ".bin", "application/force-download": ".bin",
    }
    return f"download{ext_map.get(ct, '.bin')}"


async def _download_direct_url(url: str, out_dir: str) -> str:
    """Download a direct URL to a file in out_dir. Returns the file path."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    timeout = aiohttp.ClientTimeout(total=300, connect=15)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}")
            filename = _filename_from_response(url, resp)
            dest = os.path.join(out_dir, filename)
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    f.write(chunk)
            os.replace(tmp, dest)
            # If the server gave a generic filename, sniff the real format from the
            # file header and rename so Discord shows a proper extension.
            if filename == "download.bin" or filename.endswith(".bin"):
                try:
                    with open(dest, "rb") as f:
                        header = f.read(64)
                    ext = _ext_from_magic_bytes(header)
                    if ext:
                        new_dest = os.path.join(out_dir, f"download{ext}")
                        os.replace(dest, new_dest)
                        return new_dest
                except Exception:
                    pass
            return dest


def _run_ytdlp_url(url: str, out_dir: str) -> tuple[str | None, str]:
    """Download a URL with yt-dlp. Returns (file_path, error)."""
    import subprocess as _sp
    out_template = os.path.join(out_dir, "%(title).80s.%(ext)s")
    args = [
        "yt-dlp", url,
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--max-filesize", "200m",
        "--output", out_template,
        "--no-warnings",
        "--socket-timeout", "30",
        "--age-limit", "99",
    ]
    result = _sp.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout)[-800:]
    # yt-dlp can leave temporary `.part` or `.ytdl` files behind if it had to
    # restart. Pick the most recently modified non-temporary file.
    files = [
        f for f in os.listdir(out_dir)
        if not f.startswith(".") and not f.endswith(".part") and not f.endswith(".ytdl")
    ]
    if not files:
        return None, "yt-dlp produced no output file."
    files.sort(key=lambda f: os.path.getmtime(os.path.join(out_dir, f)), reverse=True)
    return os.path.join(out_dir, files[0]), ""


def _looks_like_direct_url(url: str) -> bool:
    lower = url.lower()
    if any(host in lower for host in ("cdn.discordapp.com", "media.discordapp.net", "attachments.discordapp.com")):
        return True
    parsed = urllib.parse.urlparse(url)
    if parsed.path:
        return any(parsed.path.lower().endswith(ext) for ext in _Download_MEDIA_EXTS)
    return False


@bot.command(name="download", aliases=["dl"])
async def download_command(ctx: commands.Context, *, query: str = ""):
    """Download media from any URL, including Discord app/attachment URLs.

    Usage:
      th/download <URL>
      th/dl <URL>

    Works on direct links, Discord CDN links, and any site yt-dlp supports.
    Files ≤8 MB are sent directly; larger files are uploaded to Catbox.
    Maximum download size: 200 MB.
    """
    # ── Resolve URL from args, reply, or attachment ──────────────────────────
    url = query.strip()
    if not url and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            for tok in ref.content.split():
                if tok.lower().startswith(("http://", "https://")):
                    url = tok
                    break
            if not url and ref.attachments:
                url = ref.attachments[0].proxy_url or ref.attachments[0].url
        except Exception:
            pass
    if not url and ctx.message.attachments:
        url = ctx.message.attachments[0].proxy_url or ctx.message.attachments[0].url

    if not url:
        await ctx.reply(
            "❌ **Usage:** `th/download <URL>`\n"
            "Attach a file, reply to a URL/file, or provide a link."
        )
        return

    if not url.lower().startswith(("http://", "https://")):
        await ctx.reply("❌ Invalid URL. Must start with `http://` or `https://`.")
        return

    status_msg = await ctx.reply(f"⏳ Downloading: `{url[:100]}`…")

    with tempfile.TemporaryDirectory() as tmpdir:
        loop = asyncio.get_event_loop()
        file_path: str | None = None
        last_err = ""

        direct_first = _looks_like_direct_url(url)
        if direct_first:
            try:
                file_path = await _download_direct_url(url, tmpdir)
            except Exception as exc:
                last_err = str(exc)
                print(f"[download] direct failed: {exc}")
            if not file_path:
                file_path, last_err = await loop.run_in_executor(
                    None, lambda: _run_ytdlp_url(url, tmpdir)
                )
        else:
            # YouTube/TikTok and similar sites require yt-dlp. A direct fallback
            # only downloads the HTML page and ends up as a useless `.bin` file,
            # so report the yt-dlp error instead.
            file_path, last_err = await loop.run_in_executor(
                None, lambda: _run_ytdlp_url(url, tmpdir)
            )
            if not file_path:
                print(f"[download] yt-dlp failed for {url[:80]}: {last_err[:200]}")

        if not file_path or not os.path.exists(file_path):
            await status_msg.edit(
                content=f"❌ Download failed:\n```\n{last_err[-800:]}\n```"
            )
            return

        # yt-dlp or the server may have produced a generic .bin file. Sniff the
        # real format from the header and rename so Discord/Catbox present it
        # with a usable extension.
        if file_path.lower().endswith(".bin"):
            try:
                with open(file_path, "rb") as f:
                    header = f.read(64)
                ext = _ext_from_magic_bytes(header)
                if ext:
                    new_path = os.path.splitext(file_path)[0] + ext
                    os.replace(file_path, new_path)
                    file_path = new_path
                    print(f"[download] renamed .bin to {ext}: {new_path}")
            except Exception as exc:
                print(f"[download] magic-bytes rename failed: {exc}")

        file_size = os.path.getsize(file_path)
        MAX_DL_BYTES = 200 * 1024 * 1024
        if file_size > MAX_DL_BYTES:
            await status_msg.edit(
                content=f"❌ File too large ({file_size / 1024 / 1024:.1f} MB). Max is 200 MB."
            )
            return

        filename = os.path.basename(file_path)
        ext = Path(filename).suffix
        if not ext or ext == "." or not filename:
            filename = f"download{ext or '.bin'}"

        size_str = (
            f"{file_size / 1024 / 1024:.2f} MB"
            if file_size >= 1024 * 1024
            else f"{file_size / 1024:.2f} KB"
        )

        if file_size <= CATBOX_THRESHOLD:
            try:
                await status_msg.delete()
            except Exception:
                pass
            try:
                await ctx.reply(
                    content=f"✅ Downloaded `{filename}` ({size_str})",
                    file=discord.File(file_path, filename=filename),
                )
            except discord.HTTPException as exc:
                await ctx.reply(f"❌ Failed to send file: {exc}")
        else:
            await status_msg.edit(
                content=f"📦 File too large for Discord ({size_str}) — uploading to Catbox…"
            )
            cb_url = await _upload_to_catbox(file_path)
            try:
                await status_msg.delete()
            except Exception:
                pass
            if cb_url:
                await ctx.reply(
                    f"✅ Downloaded `{filename}` ({size_str})\n"
                    f"📦 Too large for Discord → {cb_url}"
                )
            else:
                await ctx.reply("❌ Catbox upload failed. File may be too large.")


# ---------- Catbox upload ----------

@bot.command(name="catbox", aliases=["cb", "upload"])
async def catbox_upload(ctx: commands.Context):
    """Upload any file to catbox.moe and return a permanent direct link.

      th/catbox   (with file attached, or reply to a message with a file)
    """
    src = None
    if src is None and ctx.message.attachments:
        src = ctx.message.attachments[0]
    if src is None and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                src = ref.attachments[0]
        except Exception:
            pass
    if src is None:
        await ctx.reply("📎 attach a file or reply to a message with a file to upload it to catbox.moe (or use `th/uguu`)")
        return

    status_msg = await ctx.reply(f"⬆️ uploading `{src.filename}` to catbox.moe…")
    try:
        with tempfile.NamedTemporaryFile(
            prefix="ihtx-upload-", suffix=Path(src.filename).suffix, delete=False
        ) as temp:
            temp_path = temp.name
        await src.save(temp_path)
        file_url = await _upload_to_catbox(temp_path)
        if file_url:
            provider = "catbox.moe" if "catbox.moe" in file_url else "uguu.se (Catbox fallback)"
            await status_msg.edit(content=f"✅ Uploaded to **{provider}**\n{file_url}")
        else:
            await status_msg.edit(content="❌ Catbox and Uguu uploads failed.")
    except Exception as e:
        await status_msg.edit(content=f"❌ upload failed: {e}")
    finally:
        if "temp_path" in locals():
            try:
                os.remove(temp_path)
            except OSError:
                pass


@bot.command(name="uguu", aliases=["ugupload"])
async def uguu_upload(ctx: commands.Context):
    """Upload an attached or replied-to file directly to uguu.se."""
    src = ctx.message.attachments[0] if ctx.message.attachments else None
    if src is None and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                src = ref.attachments[0]
        except Exception:
            pass
    if src is None:
        await ctx.reply("📎 attach a file/video or reply to a message with one to upload it to uguu.se")
        return

    status_msg = await ctx.reply(f"⬆️ uploading `{src.filename}` to uguu.se…")
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            prefix="ihtx-uguu-", suffix=Path(src.filename).suffix, delete=False
        ) as temp:
            temp_path = temp.name
        await src.save(temp_path)
        url = await _upload_to_uguu(temp_path)
        if url:
            await status_msg.edit(content=f"✅ Uploaded to **uguu.se**\n{url}")
        else:
            await status_msg.edit(content="❌ Uguu upload failed.")
    except Exception as e:
        await status_msg.edit(content=f"❌ Uguu upload failed: {e}")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ---------- Guess Effect Mini-Game ----------

# Effect pool sourced from the Logo Editing Fandom wiki (Category:Effects /
# Category:All_effect_articles). Each entry carries:
#   name       – canonical display name
#   accept     – list of lowercase strings that count as a correct answer
#   category   – effect type label shown in the clue card
#   wiki       – canonical wiki URL for the reveal
#   description – flavour-text clue that describes the pipeline without naming it
_GE_EFFECTS: list[dict] = [
    {
        "name": "G-Major",
        "accept": ["g-major", "gmajor", "g major"],
        "category": "Color grading + audio pitch shift",
        "wiki": "https://logo-editing.fandom.com/wiki/G-Major",
        "description": (
            "One of the oldest and most recognisable logo editing effects, created in 2007. "
            "The video runs through a hue-rotation that swings greens into purples, "
            "followed by a full channel inversion that turns the picture inside-out. "
            "The audio is pitch-shifted upward by roughly 7 semitones. "
            "In FFmpeg-land: `hue=h=180,negate` on the video and `rubberband -p+7` on the audio."
        ),
    },
    {
        "name": "G-Major 4",
        "accept": ["g-major 4", "gmajor 4", "g major 4", "g-major4", "gmajor4"],
        "category": "Color grading + layered overlay + audio boost",
        "wiki": "https://logo-editing.fandom.com/wiki/G-Major_4",
        "description": (
            "A souped-up variant of the classic G-Major pipeline. All RGB channels are inverted, "
            "then a second pitch-shifted (+5 semitones) copy of the inverted video is blended "
            "on top of itself as an overlay. The audio track is then doubled in volume. "
            "The result has a harsh, glowing quality absent from its predecessor."
        ),
    },
    {
        "name": "CoNfUsIoN",
        "accept": ["confusion", "confusión", "confushion"],
        "category": "Complex color manipulation + mirror distortion",
        "wiki": "https://logo-editing.fandom.com/wiki/CoNfUsIoN",
        "description": (
            "Charallony6000's 2014 creation stacks HSL Adjust, Invert, a horizontal mirror, "
            "LAB Adjust, and Color Corrector (Secondary) in a single chain. "
            "The mixed-case spelling of the name itself is part of the brand. "
            "Audio typically receives a harsh reverb or echo on top of a pitch shift, "
            "leaving the listener disoriented alongside the warped visuals."
        ),
    },
    {
        "name": "Preview 2",
        "accept": ["preview 2", "preview2"],
        "category": "Iconic logo-editing transition effect",
        "wiki": "https://logo-editing.fandom.com/wiki/Preview_2",
        "description": (
            "A cornerstone of the logo editing community and one of the most heavily remixed effects "
            "on the wiki. It reproduces the look of a classic broadcast preview bumper by "
            "layering colour-wash filters over a zoomed or cropped frame, accompanied by a "
            "distinctive pitched-up audio sting. Countless variants and spin-offs use it as a base."
        ),
    },
    {
        "name": "RGB to BGR",
        "accept": ["rgb to bgr", "rgb2bgr", "bgr", "rgbtobgr"],
        "category": "Color channel swap",
        "wiki": "https://logo-editing.fandom.com/wiki/RGB_to_BGR",
        "description": (
            "A precise channel-manipulation effect: the red and blue planes are swapped while "
            "green is left untouched. Warm colours become cold and vice versa — reds turn blue, "
            "blues turn red, skies shift orange, and faces go alien. "
            "In FFmpeg: `shuffleplanes=0:1:0:3` (or the `geq` RGB-component swap trick). "
            "No audio processing — the change is purely visual."
        ),
    },
    {
        "name": "Crying Effect",
        "accept": ["crying effect", "crying", "cry effect"],
        "category": "Emotional visual distortion",
        "wiki": "https://logo-editing.fandom.com/wiki/Crying_Effect",
        "description": (
            "Named for the emotional reaction it's meant to evoke. The video is desaturated "
            "toward cool blue-grey tones, then a gentle vertical wave distortion — simulating "
            "tears streaming down the lens — is applied. "
            "Audio usually shifts to a slow, lowered pitch with reverb, evoking a mournful tone. "
            "Often used on logos to make them look like they're weeping."
        ),
    },
    {
        "name": "Orange Effect",
        "accept": ["orange effect", "orange"],
        "category": "Warm color grade",
        "wiki": "https://logo-editing.fandom.com/wiki/Orange_Effect",
        "description": (
            "A straightforward but striking colour grade that pushes the entire palette toward "
            "warm amber-orange tones. Achieved by boosting the red channel, reducing blue, and "
            "slightly lifting shadows. In FFmpeg: `curves=r='0/0 0.5/0.6 1/1':b='0/0 0.5/0.35 1/0.8'`. "
            "Often combined with slight saturation increases for an 'Instagram sunset' look. "
            "No standard audio component."
        ),
    },
    {
        "name": "Center Effects",
        "accept": ["center effects", "center effect", "centre effects", "centre effect"],
        "category": "Crop and zoom distortion",
        "wiki": "https://logo-editing.fandom.com/wiki/Center_Effects",
        "description": (
            "Forces the subject to the exact centre of the frame by cropping outer regions and "
            "scaling up the middle. The resulting image is zoomed in and often slightly blurred "
            "at the edges, giving a tunnel-vision quality. "
            "Frequently paired with a pitch-raised audio track to heighten the claustrophobic feel. "
            "In FFmpeg: `crop=iw/2:ih/2,scale=iw*2:ih*2`."
        ),
    },
    {
        "name": "Electronic Sounds",
        "accept": ["electronic sounds", "electronic sound", "electronic"],
        "category": "Audio synthesis effect",
        "wiki": "https://logo-editing.fandom.com/wiki/Electronic_Sounds",
        "description": (
            "Replaces or heavily processes the original audio to sound like vintage synthesiser "
            "or arcade-machine output. Common techniques: aggressive bit-crushing, tremolo, "
            "square-wave ring modulation, and heavy echo. "
            "The visuals often receive a scanline or CRT-like overlay to match the retro-digital "
            "audio aesthetic. Associated with the Klasky Csupo community."
        ),
    },
    {
        "name": "Render Pack Transition",
        "accept": ["render pack transition", "render pack", "rpt"],
        "category": "Stinger / transition effect",
        "wiki": "https://logo-editing.fandom.com/wiki/Render_Pack_Transition",
        "description": (
            "A community-standard transition that bridges two clips using a short pre-rendered "
            "motion graphic — typically a flash, wipe, or shatter — sourced from shared render packs. "
            "The transition itself carries no permanent colour or audio transforms; "
            "it's purely a between-clip stinger. Widely used in montage and compilation videos "
            "across the logo editing scene."
        ),
    },
    {
        "name": "Mirror Effect",
        "accept": ["mirror effect", "mirror", "hflip", "horizontal mirror"],
        "category": "Geometric flip / mirror distortion",
        "wiki": "https://logo-editing.fandom.com/wiki/Category:Effects_that_are_mirrored",
        "description": (
            "Flips the video along its horizontal axis so that left becomes right. "
            "The simplest application is `hflip` in FFmpeg, but many community variants stack "
            "additional effects — colour inversion, pitch shift, or a palindrome reverse-concat — "
            "on top of the basic flip. Text and logos become unreadable, creating a dreamlike, "
            "backwards-world aesthetic."
        ),
    },
    {
        "name": "Color Inversion",
        "accept": ["color inversion", "colour inversion", "invert", "color invert", "colour invert"],
        "category": "Color channel inversion",
        "wiki": "https://logo-editing.fandom.com/wiki/Category:Effects_that_use_Invert",
        "description": (
            "Every pixel's brightness value is flipped: whites become black, bright reds become "
            "cyan, sky-blue skies turn orange. Achieved with the `negate` filter in FFmpeg or "
            "the 'Invert' effect in VEGAS/AVS. Often used as a base layer inside more complex "
            "chains such as G-Major, CoNfUsIoN, and X-Major variants. "
            "No inherent audio processing."
        ),
    },
    {
        "name": "X-Major",
        "accept": ["x-major", "xmajor", "x major"],
        "category": "G-Major variant — hue shift + audio pitch",
        "wiki": "https://logo-editing.fandom.com/wiki/Category:Effects_by_names",
        "description": (
            "Closely related to G-Major but with different hue-rotation and pitch values. "
            "Where G-Major swings ~180° and up 7 semitones, this variant uses a different "
            "rotation angle and a distinct semitone offset — often negative — giving it a "
            "cooler, more muted visual palette and a lower-pitched, murkier audio character. "
            "It inherits the core inversion step from its predecessor."
        ),
    },
    {
        "name": "Vibe",
        "accept": ["vibe", "the vibe"],
        "category": "Audio vibrato + warm visual grade",
        "wiki": "https://logo-editing.fandom.com/wiki/Category:All_effect_articles",
        "description": (
            "Centred on an audio vibrato filter — a periodic pitch wobble applied to the whole track — "
            "combined with a warm, slightly desaturated visual grade that evokes lo-fi aesthetics. "
            "In FFmpeg: `vibrato=f=5:d=0.5` for the audio wobble plus `eq=saturation=0.8,curves` "
            "for the visual warmth. Often used on chill or nostalgic logo edits."
        ),
    },
    {
        "name": "Pitch Shift",
        "accept": ["pitch shift", "pitchshift", "pitch"],
        "category": "Audio pitch manipulation",
        "wiki": "https://logo-editing.fandom.com/wiki/Audio_effects_of_AVS_Video_Editor",
        "description": (
            "The most fundamental audio-only effect in the logo editing toolkit — "
            "transposing the entire audio track up or down by a set number of semitones "
            "without changing its playback speed. "
            "In FFmpeg: `asetrate=sr*2^(n/12),aresample=sr` (simple) or `rubberband -p<n>` (high quality). "
            "Used as a building block inside almost every major community effect."
        ),
    },
]


def _ge_scramble(name: str) -> str:
    """Scramble the alphabetic characters in *name* while keeping non-letter
    characters (hyphens, spaces, digits) in their original positions."""
    chars = list(name)
    letter_idx = [i for i, c in enumerate(chars) if c.isalpha()]
    letters = [chars[i] for i in letter_idx]
    shuffled = letters[:]
    # Keep shuffling until the result differs from the original (or give up after 15 tries)
    for _ in range(15):
        random.shuffle(shuffled)
        if [c.lower() for c in shuffled] != [c.lower() for c in letters]:
            break
    for pos, idx in enumerate(letter_idx):
        chars[idx] = shuffled[pos]
    return "".join(chars)


@bot.command(name="guesseffect", aliases=["ge"])
async def guesseffect(ctx: commands.Context):
    """Mini-game: guess the logo editing effect from clues! 20-second timer."""
    effect = random.choice(_GE_EFFECTS)
    scrambled = _ge_scramble(effect["name"])

    embed = discord.Embed(
        title="🎮 Guess the Effect!",
        description=(
            "A famous logo-editing effect is hiding below. "
            "Study the clues and type its name in chat to win!\n"
            "*(Case-insensitive — common spellings accepted)*"
        ),
        color=0x40E0D0,
    )
    embed.add_field(name="📂 Category", value=effect["category"], inline=False)
    embed.add_field(name="🔀 Scrambled Name", value=f"```{scrambled}```", inline=False)
    embed.add_field(name="📝 Pipeline Clue", value=effect["description"], inline=False)
    embed.set_footer(text="⏱  You have 20 seconds — type the effect name!")
    await ctx.send(embed=embed)

    accept_set = {a.lower() for a in effect["accept"]}

    def _check(m: discord.Message) -> bool:
        return (
            m.channel.id == ctx.channel.id
            and not m.author.bot
            and m.content.strip().lower() in accept_set
        )

    try:
        winner: discord.Message = await bot.wait_for("message", check=_check, timeout=20.0)
        result_embed = discord.Embed(
            title="🎉 Correct!",
            description=(
                f"**{winner.author.display_name}** nailed it!\n"
                f"The effect was **{effect['name']}**.\n"
                f"[📖 Read about it on the wiki]({effect['wiki']})"
            ),
            color=0x40E0D0,
        )
        await ctx.send(embed=result_embed)
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ Time's Up!",
            description=(
                f"Nobody guessed it in time.\n"
                f"The effect was **{effect['name']}**.\n"
                f"[📖 Read about it on the wiki]({effect['wiki']})"
            ),
            color=0x40E0D0,
        )
        await ctx.send(embed=timeout_embed)


# ---------- th/convert — convert video to video fmt + audio fmt + image fmt ----------

@bot.command(name="effectconfig", aliases=["ec"])
async def effectconfig_command(ctx: commands.Context, *, raw: str = ""):
    """Normalize flexible pipe-effect arguments into canonical effect=param;param syntax."""
    usage = (
        "**Usage:** `th/effectconfig <effect>[=<param>[;param...]]`\n"
        "**Also accepts:** spaces and commas as parameter separators.\n"
        "**Examples:**\n"
        "`th/effectconfig scgv carrier.mp3 64 2 0.5 peak` → `scgv=carrier.mp3;64;2;0.5;peak`\n"
        "`th/effectconfig wave=1,15,0.8,0` → `wave=1;15;0.8;0`"
    )

    if not raw.strip():
        names = sorted(PIPE_EFFECT_NAMES)
        await ctx.reply(
            f"**Available pipe effects:**\n`{'`, `'.join(names)}`\n\n{usage}"
        )
        return

    tokens = [token.strip() for token in re.split(r"[=;,\s]+", raw.strip()) if token.strip()]
    requested = tokens.pop(0).lower() if tokens else ""
    aliases = {
        "invert": "negate",
        "mp": "multipitch",
        "multi": "multipitch",
        "gm": "gradientmap",
        "gmap": "gradientmap",
        "rj": "randomjitter",
        "p2p": "pinch&punch",
        "pnp": "pinch&punch",
    }
    effect = aliases.get(requested, requested)
    if effect not in PIPE_EFFECT_NAMES:
        await ctx.reply(f"❌ Unknown pipe effect `{requested}`.\n{usage}")
        return

    normalized = f"{effect}={';'.join(tokens)}" if tokens else effect
    await ctx.reply(f"✅ **Normalized pipe configuration:**\n`{normalized}`")


_CONVERT_VIDEO_FMTS = {"mp4", "mkv", "webm", "avi", "mov"}
_CONVERT_AUDIO_FMTS = {"mp3", "wav", "ogg", "flac", "aac", "m4a", "opus"}
_CONVERT_IMAGE_FMTS = {"png", "jpg", "jpeg", "webp"}
_CONVERT_VIDEO_INPUT_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"}


@bot.command(name="convert", aliases=["conv"])
async def convert_command(ctx: commands.Context, *, formats: str = "mp4/mp3/png"):
    """Convert an attached video into video + audio + image formats simultaneously.

    Usage: th/convert [video_fmt/audio_fmt/img_fmt]
    Defaults: mp4/mp3/png
    Example: th/convert mov/flac/jpg

    Video formats : mp4, mkv, webm, avi, mov
    Audio formats : mp3, wav, ogg, flac, aac, m4a, opus
    Image formats : png, jpg, webp
    """
    _parts = [p.strip().lower().lstrip(".") for p in formats.split("/")]
    video_fmt = _parts[0] if len(_parts) > 0 and _parts[0] else "mp4"
    audio_fmt = _parts[1] if len(_parts) > 1 and _parts[1] else "mp3"
    img_fmt   = _parts[2] if len(_parts) > 2 and _parts[2] else "png"
    if img_fmt == "jpeg":
        img_fmt = "jpg"

    if video_fmt not in _CONVERT_VIDEO_FMTS:
        await ctx.reply(
            f"❌ Unknown video format `{video_fmt}`. "
            f"Choose from: {', '.join(sorted(_CONVERT_VIDEO_FMTS))}"
        )
        return
    if audio_fmt not in _CONVERT_AUDIO_FMTS:
        await ctx.reply(
            f"❌ Unknown audio format `{audio_fmt}`. "
            f"Choose from: {', '.join(sorted(_CONVERT_AUDIO_FMTS))}"
        )
        return
    if img_fmt not in _CONVERT_IMAGE_FMTS:
        await ctx.reply(
            f"❌ Unknown image format `{img_fmt}`. "
            f"Choose from: {', '.join(sorted(_CONVERT_IMAGE_FMTS))}"
        )
        return

    # Resolve source attachment (direct or via reply)
    source: discord.Attachment | None = None
    if ctx.message.attachments:
        source = ctx.message.attachments[0]
    elif ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                source = ref.attachments[0]
        except Exception:
            pass
    if source is None:
        await ctx.reply("❌ Attach or reply to a video file.")
        return

    suffix = Path(source.filename).suffix.lower()
    if suffix not in _CONVERT_VIDEO_INPUT_EXTS:
        await ctx.reply(
            f"❌ `th/convert` requires a video file. Got `{suffix}`.\n"
            f"Supported inputs: {', '.join(sorted(_CONVERT_VIDEO_INPUT_EXTS))}"
        )
        return

    stem = Path(source.filename).stem
    status_msg = await ctx.reply(
        f"⚙️ Converting `{source.filename}` → "
        f"`.{video_fmt}` / `.{audio_fmt}` / `.{img_fmt}`…"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        video_out  = os.path.join(tmpdir, f"534gurts_thconvert.{video_fmt}")
        audio_out  = os.path.join(tmpdir, f"534gurts_thconvert.{audio_fmt}")
        image_out  = os.path.join(tmpdir, f"534gurts_thconvert.{img_fmt}")

        try:
            await download_attachment(source, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        loop = asyncio.get_event_loop()

        # Probe duration for mid-point thumbnail
        info = await loop.run_in_executor(None, _ffprobe_video_info, input_path)
        try:
            thumb_time = max(0.0, float(info.get("duration") or 0) / 2)
        except (TypeError, ValueError):
            thumb_time = 0.0

        def _convert_video():
            if video_fmt == "webm":
                cmd = [
                    "ffmpeg", "-y", "-i", input_path,
                    "-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0",
                    "-c:a", "libopus", "-b:a", "128k",
                    video_out,
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-i", input_path,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    video_out,
                ]
            return _run_ffmpeg_raw(cmd, timeout=300)

        def _convert_audio():
            return _run_ffmpeg_raw(
                ["ffmpeg", "-y", "-i", input_path, "-vn", audio_out],
                timeout=180,
            )

        def _convert_image():
            return _run_ffmpeg_raw(
                [
                    "ffmpeg", "-y",
                    "-ss", str(thumb_time),
                    "-i", input_path,
                    "-frames:v", "1",
                    "-q:v", "2",
                    image_out,
                ],
                timeout=60,
            )

        results = await asyncio.gather(
            loop.run_in_executor(None, _convert_video),
            loop.run_in_executor(None, _convert_audio),
            loop.run_in_executor(None, _convert_image),
        )

        labels = [f"video (.{video_fmt})", f"audio (.{audio_fmt})", f"image (.{img_fmt})"]
        paths  = [video_out, audio_out, image_out]
        errors: list[str] = []
        files:  list[discord.File] = []

        for (ok, err), label, path in zip(results, labels, paths):
            if ok and os.path.exists(path) and os.path.getsize(path) > 0:
                files.append(discord.File(path, filename=os.path.basename(path)))
            else:
                errors.append(f"`{label}`: {err[-300:] if err else 'no output'}")

        if not files:
            await status_msg.edit(
                content="❌ All conversions failed:\n" + "\n".join(errors)
            )
            return

        summary = (
            f"✅ Converted `{source.filename}` → "
            + ", ".join(f"`.{f}`" for f in [video_fmt, audio_fmt, img_fmt])
        )
        if errors:
            summary += "\n⚠️ Some outputs failed: " + "; ".join(errors)

        try:
            await ctx.reply(content=summary, files=files)
            await status_msg.delete()
        except discord.HTTPException:
            # Too large — upload video to Catbox, send audio+image directly
            await status_msg.edit(
                content="⬆️ Output too large for Discord — uploading video to Catbox…"
            )
            cat_url = await _upload_to_catbox(video_out)
            small_files = [f for f in files if not f.filename.endswith(f".{video_fmt}")]
            cat_line = f"\n🎬 Video: {cat_url}" if cat_url else ""
            try:
                await ctx.reply(content=summary + cat_line, files=small_files)
                await status_msg.delete()
            except discord.HTTPException:
                await status_msg.edit(content=summary + cat_line)


# ---------- Error handling & run ----------

def _clip_discord_text(text: str, limit: int = 1900) -> str:
    """Keep diagnostic messages below Discord's 2,000-character content limit."""
    if len(text) <= limit:
        return text
    marker = "\n…(error output truncated)"
    return text[: max(0, limit - len(marker))] + marker


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        await ctx.reply("❓ Unknown command. Use `th/bothelp` to see all available commands.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"❌ Missing argument: `{error.param.name}`. Use `th/ihtxhelp` for usage.")
        return
    if isinstance(error, commands.CheckFailure):
        return
    if isinstance(error, commands.BadArgument):
        await ctx.reply(f"❌ Bad argument: {error}\nUse `th/ihtxhelp` for correct usage.")
        return
    if isinstance(error, commands.CommandInvokeError):
        original = error.original
        print(f"[error] CommandInvokeError in {ctx.command}: {type(original).__name__}: {original}")
        try:
            await ctx.reply(
                _clip_discord_text(
                    f"❌ An error occurred: `{type(original).__name__}: {original}`"
                )
            )
        except Exception:
            pass
        return
    print(f"[error] Unhandled command error in {ctx.command}: {type(error).__name__}: {error}")
    raise error


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)
    if not CATBOX_USERHASH:
        print("ERROR: CATBOX_USERHASH environment variable not set.", file=sys.stderr)
        sys.exit(1)
    bot.run(TOKEN)
