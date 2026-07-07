"""
set: engine — store a value in a named variable.

Syntax: {set:varname|value}

The value may contain nested tagscript blocks such as {math:{get:#}+1}.
Deep extraction ensures the full value string (including nested braces)
is captured before the engine runs.  The engine resolves the value using
the standard variable + block pipeline before storing it in the tag context,
so mutations from other sets in the same iteration are visible here.
"""

from . import BaseEngine, EngineResult


class SetEngine(BaseEngine):
    name = "set"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        from bot.tags.parser import resolve_variables, resolve_blocks

        idx = content.find("|")
        if idx == -1:
            return EngineResult(text="")

        var_name = content[:idx].strip()
        raw_value = content[idx + 1:]

        # Resolve any inner functions/variables in the value
        resolved = resolve_variables(raw_value, tag_ctx)
        resolved, _ = resolve_blocks(resolved, tag_ctx)

        tag_ctx[var_name] = resolved
        return EngineResult(text="")
