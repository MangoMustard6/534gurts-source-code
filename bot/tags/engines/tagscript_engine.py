"""
tagscript: engine — re-evaluate content using the native TagScript parser.

Aliases: tagscript, tscript

This engine resolves variables and inline functions in its content.
It does NOT recursively execute other engines (use {eval:} for that).

Usage (prefix syntax):
    tagscript:
    Hello {user}, you rolled {random:1:100}!

Usage (brace syntax):
    {tagscript:Hello {user}, you rolled {random:1:100}!}
"""

from . import BaseEngine, EngineResult


class TagScriptEngine(BaseEngine):
    name = "tagscript"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        from bot.tags.parser import resolve_variables, resolve_blocks

        text = resolve_variables(content.strip(), tag_ctx)
        text, _ = resolve_blocks(text, tag_ctx)
        return EngineResult(text=text)
