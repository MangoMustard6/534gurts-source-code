---
name: Discord message length
description: Discord content messages must stay below the 2,000-character limit, especially when returning FFmpeg diagnostics.
---

Diagnostic and exception replies should be clipped before sending or editing a Discord message.

**Why:** FFmpeg and wrapped HTTP exceptions can exceed Discord's content limit and cause a second `Invalid Form Body` failure that hides the original error.

**How to apply:** Use a shared clipping helper for command failures, subprocess output, and global exception fallbacks; preserve the beginning of the diagnostic and mark truncation.