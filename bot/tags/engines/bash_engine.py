"""
bash: engine — execute a shell command and return stdout.

Aliases: bash, sh

SECURITY: Restricted to bot owners only.

Limits:
  Timeout : 5 seconds
  Output  : 4 000 characters max
  Stderr  : merged into stdout

Usage (prefix syntax):
    sh:
    echo Hello World

    bash:
    date +"%Y-%m-%d"

Usage (brace syntax):
    {bash:echo Hello World}
"""

import asyncio

from . import BaseEngine, EngineResult

_TIMEOUT = 5.0
_MAX_OUTPUT = 4_000


class BashEngine(BaseEngine):
    name = "bash"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        try:
            from bot.ihtx_bot import owner_ids
            is_owner = ctx.author.id in owner_ids
        except Exception:
            is_owner = False

        if not is_owner:
            return EngineResult(error="bash: restricted to bot owners")

        cmd = content.strip()
        if not cmd:
            return EngineResult(error="bash: no command provided")

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        except asyncio.TimeoutError:
            return EngineResult(error=f"bash: command timed out ({_TIMEOUT:.0f}s)")
        except Exception as exc:
            return EngineResult(error=f"bash: {exc}")

        text = out.decode("utf-8", errors="replace").strip()
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + f"\n… (truncated to {_MAX_OUTPUT} chars)"

        return EngineResult(text=text or "(no output)")
