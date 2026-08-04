---
name: Preview1280 R3 pitch toggle
description: Trailing argument convention for native Rubber Band R3 pitch rendering in preview1280 montage commands.
---

The preview1280 family keeps FFmpeg Rubber Band as the default pitch renderer. A boolean argument after the duration selects the engine: `true` runs the resolved native `rubberband-r3` binary with direct semitone `--pitch`/`--tempo` controls, while `false` runs FFmpeg Rubber Band.

**Why:** A constant pitch map was interpreted as a relative offset and could sound effectively unchanged, and the CLI `--pitch` option expects semitones rather than the FFmpeg filter's ratio. Runtime proof requires logging the resolved binary path, version, exact argv, and final installed audio stream.

**How to apply:** Keep the boolean optional after numeric duration; accept bare booleans, `r3=true`/`r3=false`, and R3 aliases across preview1280, oppositep1280, the fixed-size preview variant, and preview1280what. Pipe forms use a third positional parameter, e.g. `preview1280=1.85|0.85|true` and `op1280=1.85|0.85|true`. In preview1280what, its later boolean remains the legacy tempo toggle.

Native R3 tempo output is normalized to each rendered video segment by looping short audio and trimming long audio before remux.

The YTPMV scan command uses the same native R3 segment renderer for its fixed semitone sequence; classic FFmpeg rubberband is retained only as an internal pitch marker that the R3 renderer removes.

YTPMV scan source segments retain `volume=4`; its composed audio keeps the existing SoX reverb stage without an added FFmpeg echo.

YTPMV scan pitch segments should be concatenated with the FFmpeg concat demuxer and individually duration-checked; concat protocol can drop the final short R3 segment.

YTPMV scan is available as a dedicated pipe effect fixed at start 0; its pitch-source segment begins at start+2.09375 while the first segment begins exactly at start.

In pipe mode, YTPMV scan is intentionally bare and fixed at start 0; reject all pipe parameters. Only the standalone command accepts a custom start.

Pipe YTPMV uses immediate pitch-source timing and preserves the generated scan when duration is `vidlen`; numeric pipe durations still use normal IHTX trimming.