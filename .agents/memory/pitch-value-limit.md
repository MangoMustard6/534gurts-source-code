---
name: Pitch value limit
description: Maximum number of pitch layers accepted by IHTX pitch-processing commands.
---

Pitch-processing commands accept at most 100 pitch values per request. This is a
shared input-safety limit across Python and TypeScript implementations; individual
pitch magnitude validation remains separate.

**Why:** More pitch layers multiply external process count, FFmpeg filtergraph
size, memory use, and output time, so the limit must be enforced before rendering.

**How to apply:** Keep standalone commands, pipe effects, prefix commands, and
slash-command adapters aligned at 100 when adding or changing pitch processors.