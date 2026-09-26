---
name: Raw multi-command FFmpeg pipelines
description: Imported owner IHTX scripts that chain FFmpeg and multipitch commands inside one ffmpeg() pipe step.
---

Owner-only `ffmpeg(...)` pipe steps may contain a sequential Bash pipeline rather than a single FFmpeg argument list. The first argument block receives the current export as its input; later `ffmpeg -i ...` and `multipitch ...` commands run in one temporary working directory.

**Why:** Imported effects use intermediate names such as `a$i.mp4`, `h$i.wav`, `out$i.wav`, and `$i.mov`, and depend on Bash command substitutions to build repeated audio filters. Treating the whole payload as one argv invocation loses both the command boundaries and the shell expansion semantics.

**How to apply:** Keep this path owner-only, set `$i` to the current export number, support numbered variables such as `$i5`, expose the bundled multipitch executable through the temporary job directory, and collect the final command's generated file into IHTX's managed output path.