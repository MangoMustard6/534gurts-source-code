---
name: Audio put replace
description: NotSoBot-style nested multimedia audio replacement command behavior.
---

The audio replacement command uses a dedicated nested prefix group plus a manually registered slash group so prefix mode can parse free-form URL/reference tokens and `-longest`/`-noloop`, while slash mode exposes typed options and separate attachment inputs.

**Why:** discord.py hybrid decorators cannot express the requested free-form nested parser and typed slash attachment union cleanly in one declaration.

**How to apply:** Preserve shared source resolution for attachments, URLs, and replies; replace only the base container's audio stream; loop shorter replacement audio unless `-noloop`; use finite longest-duration padding when `-longest` is selected.

Always pass an explicit finite `-t` output duration to FFmpeg, including when `-stream_loop -1` is used; relying on `-shortest` alone can hang when source duration metadata is ambiguous.