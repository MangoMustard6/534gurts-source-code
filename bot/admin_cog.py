"""Owner-only administrative commands."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands


BASH_TIMEOUT_SECONDS = 45
BASH_AUDIT_FILE = Path("bot/bash_audit.log")
_BASH_PREFIX_RE = re.compile(r"^!bash(?:\s+([\s\S]*))?$", re.IGNORECASE)


def _is_configured_owner(ctx: commands.Context) -> bool:
    """Check the shared owner registry and fail closed if it is unavailable."""
    try:
        from bot.ihtx_bot import _is_owner_by_id
        return bool(_is_owner_by_id(ctx.author.id))
    except Exception:
        return False


def _clip_output(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    marker = "\n…(output truncated)"
    return text[: max(0, limit - len(marker))] + marker


class AdminCog(commands.Cog, name="Admin"):
    """Commands that require the configured bot owner."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _audit(command: str, user_id: int) -> None:
        BASH_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "command": command,
        }
        with BASH_AUDIT_FILE.open("a", encoding="utf-8") as audit:
            audit.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def _run_bash(self, ctx: commands.Context, command: str) -> None:
        is_owner = _is_configured_owner(ctx)
        try:
            await asyncio.to_thread(self._audit, command, ctx.author.id)
        except OSError:
            if is_owner:
                await ctx.reply("❌ The command was not run because its audit entry could not be recorded.")
            return
        if not is_owner:
            return
        if not command.strip():
            await ctx.reply("❌ Usage: `th>bash <command>`.")
            return

        process: asyncio.subprocess.Process | None = None
        timed_out = False
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=BASH_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                stdout, stderr = await process.communicate()
        except OSError as exc:
            await ctx.reply(f"❌ Could not start the command: `{str(exc)[:500]}`")
            return

        output = (stdout + stderr).decode("utf-8", errors="replace").strip()
        if not output:
            output = "(no output)"
        output = output.replace("```", "`\u200b``")
        status = "timed out" if timed_out else f"exit code {process.returncode}"
        await ctx.reply(f"**{status}**\n```text\n{_clip_output(output)}\n```")

    @commands.command(name="bash")
    async def bash_prefix(self, ctx: commands.Context, *, command: str = "") -> None:
        """Run an owner-only shell command asynchronously."""
        await self._run_bash(ctx, command)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Support !bash without making ! a global command prefix."""
        if message.author.bot:
            return
        match = _BASH_PREFIX_RE.fullmatch(message.content.strip())
        if not match:
            return
        ctx = await self.bot.get_context(message)
        await self._run_bash(ctx, match.group(1) or "")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))