---
name: Raw FFmpeg pipe codecs
description: Codec and container rules for custom ffmpeg(...) steps inside IHTX.
---

Raw `ffmpeg(...)` pipe steps must encode filtered audio with `pcm_s16le` and video with `ffv1`; never leave filtered audio on stream-copy. Non-final raw passes use a lossless Matroska intermediate, while the final container must support those codecs.

**Why:** FFmpeg rejects `-af` with `-c:a copy`, and MP4 does not support FFV1 video. The bot's automatic input/output wrapping also means a raw pipe step should not include its own `-i` or output filename.

**How to apply:** Normalize raw-step codec overrides to FFV1/PCM, omit explicit shell-style input/output filenames, and use a compatible `mkv`, `nut`, or similar intermediate when composing multiple raw passes.