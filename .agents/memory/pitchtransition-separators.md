---
name: Pitchtransition separators
description: Pitchtransition voice-pair parsing across standalone and custom pipe export paths
---

`pitchtransition` accepts semicolon-separated voice pairs such as `-7,7;7,-7`. The custom export parser may normalize semicolons to spaces, so the processor must also accept `-7,7 7,-7` and identify complete numeric pairs rather than splitting on whitespace alone.

**Why:** Custom IHTX export parsing can transform effect parameters before the pipe processor receives them, which previously combined multiple voice pairs into one invalid voice.

**How to apply:** When adding or changing multi-value pipe effects, validate both the direct pipe syntax and the normalized syntax produced by the export parser.