---
name: IHTX auxiliary uploads
description: The attachment contract for local LUTs and pitch binaries used by prefix IHTX jobs.
---

Prefix IHTX jobs may include a supported source video plus up to four explicitly recognized auxiliary uploads: `.cube` LUTs and `multipitch`/`fileaa` binaries (including `.bin` files). LUT references must use the uploaded filename.

**Why:** Discord attachments are not shell-visible files, and changing the shared binary path during a render would let concurrent jobs affect one another.

**How to apply:** Download assets into the job's temporary directory, require `lut=<uploaded filename>` for every attached LUT, rewrite only asset references to those paths, and scope any uploaded pitch binary through the worker context so the bundled fallback remains unchanged for other jobs.