---
name: IHTX output format
description: The positional distinction between intermediate and final output containers in th/ihtx.
---

`th/ihtx` accepts `exports duration no_trim format output_format effects`. `format` controls intermediate effect-pass files; the required `output_format` controls the final concatenated export. Final output formats are limited to `mp4`, `mov`, `mkv`, `mxf`, and `avi`.

**Why:** Some effects and codec combinations are more reliable in an intermediate container, while users may want the final attachment in another container without changing every processing pass. Requiring the final format avoids ambiguous fallback behavior.

**How to apply:** Require both formats in custom pipe syntax. Keep intermediate filenames and processing based on `format`, and use `output_format` only for the final output path, concat codec selection, and uploaded filename.