---
name: Help preview attachments
description: Discord help previews must use local attachments because the Catbox objects returned zero-byte responses.
---
Use the generated files in `bot/help_previews/` and attach the selected PNG/GIF directly to the help message with an `attachment://` embed image URL. Replace the attachment when the help category or page changes.

**Why:** The Catbox upload endpoint returned HTTP 200 with zero-byte image bodies for these preview files, which made Discord display no image.

**How to apply:** Keep preview filenames mapped to local files, and update both the embed image and message attachments together for home/category/page transitions.