---
name: Pipe output format default
description: Behavior when pipe mode omits its optional final output format.
---

**Rule:** In pipe mode, an omitted final output format means no final container conversion; the intermediate export format is retained.

**Why:** Pipe effects should work without requiring users to provide a redundant second format when they are satisfied with the intermediate container.

**How to apply:** Treat `output_fmt` as optional in user-facing pipe commands and use `export_fmt` as the effective final format when it is blank.