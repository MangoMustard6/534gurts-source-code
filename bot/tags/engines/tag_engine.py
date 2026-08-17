"""
tag: engine — inline-run another tag and insert its text output.

Syntax  : {tag:tagname}
Shorthand: {tagname}  (any unknown {var} not in context becomes {tag:var})

Nesting is limited to 3 levels to prevent infinite recursion.
File / embed outputs from the sub-tag are ignored; only text is returned.
"""

from . import BaseEngine, EngineResult

_MAX_DEPTH = 3


class TagRunEngine(BaseEngine):
    name = "tag"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        from bot.tags.storage import TagStorage
        from bot.tags.parser import parse
        from bot.tags import engines as _engines

        name = content.strip().lower()
        if not name:
            return EngineResult(text="")

        guild = getattr(ctx, "guild", None)
        if guild is None:
            return EngineResult(text="")

        depth = tag_ctx.get("_tag_depth", 0)
        if depth >= _MAX_DEPTH:
            return EngineResult(text="")

        storage = TagStorage()
        tag = await storage.get(guild.id, name)
        if tag is None:
            return EngineResult(text="")

        sub_ctx = dict(tag_ctx)
        sub_ctx["_tag_depth"] = depth + 1

        text, engine_blocks = parse(tag["content"], sub_ctx)

        parts = [text] if text else []
        for block in engine_blocks:
            engine = _engines.get(block["engine"])
            if engine is None:
                continue
            result = await engine.execute(block["content"], ctx, sub_ctx)
            if result.text:
                parts.append(result.text)

        return EngineResult(text="\n".join(p for p in parts if p).strip())
