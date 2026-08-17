---
name: IHTX restart recovery
description: How interrupted prefix th/ihtx jobs are recovered after a bot restart.
---

**Rule:** Prefix `th/ihtx` records its original Discord message before processing and replays pending messages after reconnecting.

**Why:** FFmpeg work runs inside the bot process, so a process restart cancels it; Discord messages provide a durable source for replay.

**How to apply:** Keep pending-job writes atomic, remove records only after command completion, and guard recovery so repeated `on_ready` events do not replay a job twice.