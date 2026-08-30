---
name: Custom pitch pipe
description: Custom fileaa pitch-engine usage inside IHTX.
---

Use the dedicated `mpcustom`/`multipitchcustom`/`fileaa` pipe effect when users need a custom pitch engine or fileaa flags instead of the stock multipitch path. The first parameter is the semitone list; `::` separates additional fileaa arguments.

**Why:** The stock multipitch effect chooses its own Rubber Band/bungee path and only exposes pitch values. Custom fileaa options need a separate, safe subprocess path that preserves uploaded per-job binary overrides.

**How to apply:** Use forms such as `mpcustom=-3.5|5::--backend bungee::--no-normalize` or `mpcustom=-3.5|5::--backend rubberband::--rubberband-args="-2 --pitch-hc"`. Do not claim unsupported flags work with the bundled binary; its accepted custom options are shown by `fileaa --help`.