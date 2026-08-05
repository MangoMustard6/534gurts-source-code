---
name: Pipe export progress
description: User-facing progress behavior for repeated IHTX pipe exports.
---

Pipe-mode progress should describe the code workflow and export passes: duration, trim behavior, intermediate format, final output format, then `Exports: 1/N...` through `Exports: N/N!`, with a 20-segment visual bar. Internal base preparation, compatibility passes, concatenation, and individual effect names should not appear as export counts.

**Why:** Users need to understand progress toward the requested number of exports, not the implementation stages or pipe-effect list.

**How to apply:** Keep the worker callback on requested export numbers and reserve the terminal exclamation mark for the final `N/N` state.