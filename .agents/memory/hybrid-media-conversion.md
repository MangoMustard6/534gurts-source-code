---
name: Hybrid media conversion
description: The bot's unified media conversion command and its compatibility boundary with the older converter.
---

The canonical media converter is a hybrid command available as `/convert` and `th/convert`, with a module-level `Convert Media` message context menu. Discord cannot express an attachment-or-string union in one slash option, so the slash form uses an optional attachment plus optional URL input; prefix usage accepts an attachment or URL.

**Why:** The bot already had a legacy `th/convert` command that generated three outputs at once. Keeping both under the same name prevents the new Cog from loading and creates ambiguous user behavior.

**How to apply:** Keep the legacy implementation under `th/convert_legacy` with `th/conv` as its compatibility alias. The new Cog owns the canonical `convert` name and uses temporary directories, safe argv-based FFmpeg subprocesses, and bounded processing.