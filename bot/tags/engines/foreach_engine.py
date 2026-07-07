"""
foreach: engine — loop N times or iterate over items.

Count mode  : {foreach:N|template}
  Template is re-evaluated each iteration so {set:}/{get:} mutations persist.
  e.g. {set:#|0}{foreach:3|{set:#|{math:{get:#}+1}}[a{get:#}]} -> [a1][a2][a3]

Item mode   : {foreach:template|item1|item2|...}
  @ in template = current item. Default separator: newline.
  Custom separator: prefix template with sep~ e.g. {foreach:;~pitch=@|0|3|7}
"""

from . import BaseEngine, EngineResult


class ForEachEngine(BaseEngine):
    name = "foreach"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        from bot.tags.parser import (
            resolve_variables,
            resolve_blocks,
            _extract_deep_blocks,
            sort_engine_blocks,
        )
        from bot.tags import engines as _engines

        parts = content.split("|", 1)
        if len(parts) < 2:
            return EngineResult(text="")

        first = parts[0].strip()
        rest = parts[1]

        # ── Count mode ────────────────────────────────────────────────────────
        try:
            n = int(first)
            n = max(0, min(n, 50))
            template = rest
            results = []
            for _ in range(n):
                # 1. Resolve outer variables (e.g. {user}, {args})
                t = resolve_variables(template, tag_ctx)
                # 2. Extract deep blocks (set, nested foreach, embedjson …)
                t, deep_blocks = _extract_deep_blocks(t)
                # 3. Execute deep blocks first so mutations (set) take effect
                for block in sort_engine_blocks(deep_blocks):
                    engine = _engines.get(block["engine"])
                    if engine:
                        res = await engine.execute(block["content"], ctx, tag_ctx)
                        # deep blocks in a count-foreach are side-effects only;
                        # their text output (usually "") is discarded here
                # 4. Resolve remaining shallow blocks (get, math, if, …)
                t, _ = resolve_blocks(t, tag_ctx)
                results.append(t)
            return EngineResult(text="".join(results))
        except ValueError:
            pass

        # ── Item mode ─────────────────────────────────────────────────────────
        template = first
        sep = "\n"
        if "~" in template:
            tilde_idx = template.index("~")
            sep = template[:tilde_idx]
            template = template[tilde_idx + 1:]

        items = rest.split("|")
        results = []
        for item in items:
            t = template.replace("@", item.strip())
            t = resolve_variables(t, tag_ctx)
            t, _ = resolve_blocks(t, tag_ctx)
            results.append(t)
        return EngineResult(text=sep.join(results))
