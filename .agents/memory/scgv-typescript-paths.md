---
name: SCGV TypeScript paths
description: The TypeScript sidechain-gate vocoder is exposed through both pipe processing and a standalone command.
---

SCGV should share one vocoder execution implementation between `scgv=...` pipe effects and the standalone `th/scgv` command.

**Why:** Keeping both entry points on the same builder and FFmpeg runner prevents positional defaults and filtergraph behavior from drifting between command modes.

**How to apply:** Update the shared SCGV builder/runner first, then keep `pipetest` routing and standalone command parsing as thin adapters.