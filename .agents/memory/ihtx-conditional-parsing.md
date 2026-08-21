---
name: IHTX conditional parsing
description: Quote-aware conditional branches and semicolon effect-chain parsing in th/ihtx.
---

Conditional pipe expressions must be recognized before generic user-effect expansion or delimiter scanning; branch payloads are quote-protected, while semicolons are effect separators only when followed by a known effect name. Export-count controls also accept `$i`, `i`, `powers`, `repetitions`, and `reps`.

**Why:** Comparison operators and branch code can contain the same characters used by the normal pipe parser, so parsing them in the generic path silently changes the condition or branch.

**How to apply:** Preserve quote-aware field splitting for any future IHTX control syntax, keep positional semicolon parameters intact unless the following token is a registered pipe effect, and normalize named controls before invoking the shared workflow.