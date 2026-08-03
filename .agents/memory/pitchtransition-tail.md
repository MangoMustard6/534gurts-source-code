---
name: Pitchtransition tail preservation
description: Pitchtransition must pad audio before Rubber Band so the final automation command is emitted before latency compensation and trimming.
---

Pitchtransition needs a small, finite padded tail before Rubber Band processing. Remove the look-ahead delay only after processing, and carry the extra tail through the IHTX base render, per-export trim, and final mux. Never leave `apad` unbounded.

**Why:** The start-time correction fixed leading delay but initially caused the final transition to be truncated; an unbounded padding attempt also produced runaway WAV output.

**How to apply:** Any timing or export change must test both stream start timestamps and a distinct endpoint marker through the full IHTX export loop.