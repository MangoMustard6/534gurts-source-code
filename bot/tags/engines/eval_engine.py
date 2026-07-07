"""
eval: engine — re-parse content as TagScript after resolving sub-engines.

This makes {eval:{text:attachment}} work:
  1. The inner {text:attachment} engine runs and returns file contents.
  2. eval re-parses those file contents as a full TagScript string, resolving
     variables, inline functions, and any further engine blocks.

Maximum nesting depth: 3  (prevents infinite recursion)
"""

from __future__ import annotations

from . import BaseEngine, EngineResult

_MAX_DEPTH = 3


class EvalEngine(BaseEngine):
    name = "eval"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        from bot.tags.parser import parse
        from bot.tags import engines as _engines

        depth = int(tag_ctx.get("_eval_depth", 0))
        if depth >= _MAX_DEPTH:
            return EngineResult(error="eval: maximum nesting depth reached")

        sub_ctx = {**tag_ctx, "_eval_depth": depth + 1}

        # ── Step 1: parse the raw content, running any sub-engines ───────────
        text, sub_blocks = parse(content, sub_ctx)
        parts = [text] if text else []

        for block in sub_blocks:
            engine = _engines.get(block["engine"])
            if engine is None:
                parts.append(f"[unknown engine: {block['engine']}]")
                continue
            result = await engine.execute(block["content"], ctx, sub_ctx)
            if result.error:
                return EngineResult(error=result.error)
            if result.text:
                parts.append(result.text)

        combined = "\n".join(p for p in parts if p).strip()
        if not combined:
            return EngineResult(text="")

        # ── Step 2: re-parse the combined output as fresh TagScript ──────────
        final_text, final_blocks = parse(combined, sub_ctx)
        final_parts = [final_text] if final_text else []

        for block in final_blocks:
            engine = _engines.get(block["engine"])
            if engine is None:
                continue
            result = await engine.execute(block["content"], ctx, sub_ctx)
            if result.error:
                return EngineResult(error=result.error)
            if result.text:
                final_parts.append(result.text)

        return EngineResult(text="\n".join(p for p in final_parts if p).strip())
