---
name: Hybrid media conversion
description: The bot's unified media conversion command and its compatibility boundary with the older converter.
---

The canonical media converter is a hybrid command available as `/convert` and `th/convert`, with a module-level `Convert Media` message context menu. Discord cannot express an attachment-or-string union in one slash option, so the slash form uses an optional attachment plus optional URL input; prefix usage accepts an attachment or URL.

**Why:** The bot previously had a three-output prefix converter that conflicted with the unified command’s name and created ambiguous user behavior.

**How to apply:** Do not reintroduce the old converter or `th/conv`; the new Cog owns the canonical `convert` name and uses temporary directories, safe argv-based FFmpeg subprocesses, and bounded processing.