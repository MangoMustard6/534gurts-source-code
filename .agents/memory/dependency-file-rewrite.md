---
name: Dependency file rewrite
description: Package installation may rewrite Python dependency files during environment synchronization.
---

When installing Python packages through the workspace package manager, verify tracked dependency files afterward; the installer can rewrite or re-expand requirements entries.

**Why:** A dependency install restored duplicate requirements after they had been removed, so the cleanup had to be applied after installation.

**How to apply:** Install dependencies first, then inspect and clean requirements.txt before final verification.