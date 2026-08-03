---
name: Pitchtransition export timing
description: Rubber Band look-ahead and later IHTX export passes can shift processed audio unless latency and PTS are normalized.
---

Rubber Band pitch-transition audio has a small look-ahead delay, and AAC/video export stages can preserve or compound timestamp offsets. Compensate the filter latency before muxing, reset audio and video PTS during each trim/export pass, and reset them again at final concatenation.

**Why:** Parser correctness alone does not guarantee that the audible transition starts at the requested video time; the export pipeline can shift otherwise-correct audio.

**How to apply:** When changing pitchtransition or IHTX export/mux commands, verify the actual output with `ffprobe` and require both audio and video streams to start at `0.000000s`.