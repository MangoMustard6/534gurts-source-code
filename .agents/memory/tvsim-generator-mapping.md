---
name: TVSIM generator mapping
description: Current Python TV simulator parameter order and output mapping.
---

The active Python TVSIM renderer follows the supplied `genTvSim` parameter order: `ls` line sync, `dz` detail zoom, `vs` vertical sync, `ph` phosphorescence, `it` interlacing, `sp` scan phasing, `ag` aperture grill, and `st` static. It uses the displacement, grill, and static assets and preserves source audio.

**Why:** The previous Python implementation used a different curvature-first parameter model, so pipe and standalone calls did not match the requested generator.

**How to apply:** Keep the final filtergraph output explicitly labeled and map only that processed video pad plus `0:a?`; otherwise FFmpeg may auto-map the untouched source video as an extra stream.