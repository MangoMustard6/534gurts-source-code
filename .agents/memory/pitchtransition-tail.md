---
name: Pitchtransition tail preservation
description: Pitchtransition must pad audio before Rubber Band so the final automation command is emitted before latency compensation and trimming.
---

Pitchtransition needs a small, finite padded tail before native Rubber Band R3 pitchmap processing. Normalize timestamps without trimming the processed front, and carry the extra tail through the IHTX base render, per-export trim, and final mux. Never leave `apad` unbounded.

**Why:** Native R3 pitchmap supports the requested dynamic sweep directly; front-trimming after Rubber Band removed the source beginning, and an unbounded padding attempt produced runaway WAV output.

**How to apply:** Any timing or export change must test both stream start timestamps and a distinct endpoint marker through the full IHTX export loop.