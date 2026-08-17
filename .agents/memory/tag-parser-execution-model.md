---
name: Tag parser execution model
description: How set/get/foreach/math interact across the parse pipeline; ordering gotchas.
---

## The parse() pipeline (bot/tags/parser.py)
1. _extract_script_blocks — prefix blocks (tagscript:, py:, bash:, …)
2. resolve_variables — {var} without colon → ctx lookup. Unknown → {tag:varname} (tag shorthand)
3. _extract_deep_blocks — depth-counted extraction for engines in _DEEP_ENGINES ("embedjson", "eval", "foreach", "set")
4. resolve_blocks — regex-based extraction for all remaining {name:content} blocks; calls _handle_block()
5. sort_engine_blocks — orders by _ENGINE_ORDER priority list
6. cog.py executes engine blocks in order

## Key ordering rules
- {set:} is in _DEEP_ENGINES so it gets depth-counted extraction (handles nested values like {set:#|{math:{get:#}+1}})
- {foreach:} is also _DEEP_ENGINES so its entire template (however deeply nested) is captured
- {get:} is a shallow inline function in _handle_block — resolved at parse() time (step 4)
- {math:} now calls resolve_blocks on its content first, so {math:{get:#}+1} works in one pass

## ForEachEngine execution (foreach_engine.py)
Count mode ({foreach:N|template}):
  For each iteration:
    1. resolve_variables(template, tag_ctx)        ← outer vars
    2. _extract_deep_blocks(t)                      ← extract nested sets/foreachs
    3. Execute deep blocks (e.g. SetEngine) FIRST   ← mutations happen
    4. resolve_blocks(t, tag_ctx)                   ← {get:} reads updated ctx

This ordering is critical: set must run BEFORE resolve_blocks in each iteration so {get:}
reads the just-updated value. Result of {set:#|0}{foreach:3|{set:#|{math:{get:#}+1}}[a{get:#}]} = [a1][a2][a3]

## Unknown {var} shorthand
resolve_variables converts unknown {varname} (no colon, not in ctx) → {tag:varname}.
This makes {invert} an implicit {tag:invert} call. Known ctx vars ({user}, {args}, etc.) are not affected.

## Alias arg order (cog.py)
t!tag alias <new_alias> <existing_name>  ← new alias first, existing tag second
storage.add_alias(guild_id, existing_name, new_alias, …)  ← storage takes (existing, new)
