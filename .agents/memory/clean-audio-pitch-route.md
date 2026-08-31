---
name: Clean audio pitch route
description: No-gap audio handling for custom pitch and raw filtered IHTX jobs.
---

Custom pitch and stock multipitch exports use PCM audio and preview-compatible H.264 video through the export loop. Raw `ffmpeg(...)` audio-filter steps may still use FFV1/PCM for their filter-safe intermediate, but the custom/multipitch remux and clean export stages use H.264/PCM so Discord can decode the video.

**Why:** The user prioritizes continuous, clean audio over timestamp-based gap repair, while FFV1 made custom-pitch videos oversized and gray in Discord previews. AAC priming and timestamp resets can introduce audible discontinuities, while PCM keeps the processed samples contiguous.

**How to apply:** Use `+` when the full source duration should be preserved, choose `nut`/`mkv` for intermediates and `mkv`/`mov` for final PCM output, and do not reintroduce audio timestamp filters into the clean route.