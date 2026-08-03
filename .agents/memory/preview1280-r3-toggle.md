---
name: Preview1280 R3 pitch toggle
description: Trailing argument convention for native Rubber Band R3 pitch rendering in preview1280 montage commands.
---

The preview1280 family keeps FFmpeg Rubber Band as the default pitch renderer. A trailing `r3`-style argument selects native `rubberband-r3` direct `--pitch`/`--tempo` controls while preserving each segment's intended semitone and tempo values.

**Why:** A constant pitch map was interpreted as a relative offset and could sound effectively unchanged; direct native controls make the R3 path actually apply each fixed segment's pitch.

**How to apply:** Keep the flag optional and trailing after numeric duration/other arguments; accept the same convention across preview1280, oppositep1280, the fixed-size preview variant, and preview1280what.