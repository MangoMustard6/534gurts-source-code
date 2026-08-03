---
name: IHTX output format
description: The positional distinction between intermediate and final output containers in th/ihtx.
---

`th/ihtx` accepts `exports duration no_trim format [output_format] effects`. `format` controls intermediate effect-pass files; `output_format`, when supplied, controls the final concatenated export. When omitted, the final format remains `format`.

**Why:** Some effects and codec combinations are more reliable in an intermediate container, while users may want the final attachment in another container without changing every processing pass.

**How to apply:** Preserve the four-argument legacy syntax. In the extended syntax, keep intermediate filenames and processing based on `format`, and use `output_format` only for the final output path, concat codec selection, and uploaded filename.