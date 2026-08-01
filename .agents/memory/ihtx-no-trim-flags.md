---
name: IHTX no-trim flags
description: The positional no_trim argument semantics for the IHTX iterative workflow.
---

`th/ihtx` treats the argument after duration as an explicit mode flag:
`true`, `yes`, and `+` preserve the full source and processed export lengths;
`false`, `no`, and `-` loop and trim each generated step to the requested duration.

**Why:** The original shell syntax used this slot to select two materially different
FFmpeg command branches, so it must not be treated as a placeholder or implicit truthy value.

**How to apply:** Keep prefix tags, the tag engine, and slash/custom adapters aligned
with these six accepted values whenever IHTX argument parsing changes.