---
name: Pitchtransition tail preservation
description: Pitchtransition must pad audio before Rubber Band so the final automation command is emitted before latency compensation and trimming.
---

Pitchtransition needs a small padded tail before Rubber Band processing. Remove the look-ahead delay only after processing, then trim to the source duration; trimming first cuts off the final pitch endpoint.

**Why:** The start-time correction fixed leading delay but initially caused the final transition to be truncated.

**How to apply:** Any timing or export change must test both stream start timestamps and a distinct endpoint marker through the full IHTX export loop.