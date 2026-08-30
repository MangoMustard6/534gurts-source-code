---
name: Clean audio pitch route
description: No-gap audio handling for custom pitch and raw filtered IHTX jobs.
---

Custom pitch and raw `ffmpeg(...)` audio-filter jobs use PCM audio and lossless FFV1/PCM-capable containers through the export loop. Their trim and concat stages do not apply audio `setpts`/`asetpts` or `atrim`; stock effects retain the legacy compatible path.

**Why:** The user prioritizes continuous, clean audio over timestamp-based gap repair. AAC priming and timestamp resets can introduce audible discontinuities, while PCM keeps the processed samples contiguous.

**How to apply:** Use `+` when the full source duration should be preserved, choose `nut`/`mkv` for intermediates and `mkv`/`mov` for final lossless output, and do not reintroduce audio timestamp filters into the clean route.