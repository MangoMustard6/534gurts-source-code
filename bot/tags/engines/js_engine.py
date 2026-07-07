"""
js: engine — run Node.js code and return stdout.

Syntax (brace)  : {js:console.log("hello")}
Syntax (prefix) :
    js:
    const x = 2 + 2;
    console.log(x);

Restrictions: bot owner only.  5 s timeout.  4 000 char output cap.
"""

import asyncio
import shlex

from . import BaseEngine, EngineResult

_TIMEOUT = 5
_MAX_OUT = 4000


def _is_bot_owner(ctx) -> bool:
    try:
        from bot.ihtx_bot import owner_ids
        return ctx.author.id in owner_ids
    except Exception:
        return False


class JsEngine(BaseEngine):
    name = "js"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        if not _is_bot_owner(ctx):
            return EngineResult(error="js: engine is bot-owner only")

        code = content.strip()
        if not code:
            return EngineResult(text="")

        try:
            proc = await asyncio.create_subprocess_exec(
                "node", "--input-type=module",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=code.encode()),
                timeout=_TIMEOUT,
            )
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            if err and not out:
                return EngineResult(error=f"js error: {err[:500]}")
            combined = (out + ("\n" + err if err else "")).strip()
            return EngineResult(text=combined[:_MAX_OUT])
        except asyncio.TimeoutError:
            return EngineResult(error="js: timed out (5 s)")
        except Exception as exc:
            return EngineResult(error=f"js: {exc}")
