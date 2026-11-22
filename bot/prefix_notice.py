"""Prefix-command shutdown notice.

Prefix commands stop working in January 2027.  Instead of editing hundreds of
reply sites, the bot uses :class:`NoticeContext` as its command context: the
first reply a *prefix* invocation sends carries a short notice that points at
the matching slash command.  Slash invocations never show it.

Where the notice goes depends on what is being sent:

* Components V2 layout  -> subtext line at the bottom of the container
* classic embed(s)      -> appended to the last embed's footer
* plain ``content``     -> subtext line under the message
* file / view only      -> sent as the message's ``content``

Install with ``install(bot)`` right after the bot is created.
"""

from __future__ import annotations

from typing import Any, Optional

import discord
from discord import ui
from discord.ext import commands

from bot.ui_v2 import add_notice

SHUTDOWN = "January 2027"

# Qualified prefix-command name -> slash path ("/effects trim").  Filled in by
# bot.slash_bridge when it registers the slash versions.
SLASH_PATHS: dict[str, str] = {}

_CONTENT_LIMIT = 2000
_FOOTER_LIMIT = 2048


def slash_path_for(command: Optional[commands.Command]) -> Optional[str]:
    """Slash path that replaces ``command``, or ``None`` if unknown."""
    if command is None:
        return None
    path = SLASH_PATHS.get(command.qualified_name)
    if path:
        return path
    if isinstance(command, commands.HybridCommand):
        return "/" + command.qualified_name  # already has a native slash form
    return None


def notice_markdown(prefix: str, command: Optional[commands.Command]) -> str:
    path = slash_path_for(command)
    use = f"Use `{path}` instead." if path else "Please use the slash (`/`) commands instead."
    return f"⚠️ Prefix commands (`{prefix}`) shut down in **{SHUTDOWN}**. {use}"


def notice_plain(command: Optional[commands.Command]) -> str:
    path = slash_path_for(command)
    use = f"use {path} instead" if path else "use slash commands instead"
    return f"⚠️ Prefix commands shut down in {SHUTDOWN} — {use}"


class NoticeContext(commands.Context):
    """Context that adds the shutdown notice to a prefix command's first reply."""

    _notice_done: bool = False

    # -- notice injection ---------------------------------------------------

    def _wants_notice(self) -> bool:
        return (
            not self._notice_done
            and self.interaction is None  # slash invocations never get it
            and self.command is not None
            and self.invoked_with is not None
        )

    def _with_notice(self, content: Optional[str], kwargs: dict[str, Any]) -> Optional[str]:
        """Attach the notice to the outgoing message; returns the new ``content``.

        Mutates ``kwargs`` (view / embed / embeds) as needed.  Never raises: a
        notice that does not fit is simply skipped.
        """
        if not self._wants_notice():
            return content
        try:
            view = kwargs.get("view")
            embed = kwargs.get("embed")
            embeds = kwargs.get("embeds")

            if isinstance(view, ui.LayoutView):
                if add_notice(view, notice_markdown(self.prefix or "", self.command)):
                    self._notice_done = True
                return content

            target = embed if embed is not None else (embeds[-1] if embeds else None)
            if target is not None:
                text = notice_plain(self.command)
                old = target.footer.text if target.footer else None
                combined = f"{old}\n{text}" if old else text
                if len(combined) <= _FOOTER_LIMIT:
                    target.set_footer(
                        text=combined,
                        icon_url=target.footer.icon_url if target.footer else None,
                    )
                    self._notice_done = True
                return content

            line = "-# " + notice_markdown(self.prefix or "", self.command)
            if content:
                joined = f"{content}\n{line}"
                if len(joined) <= _CONTENT_LIMIT:
                    self._notice_done = True
                    return joined
                return content

            if kwargs.get("file") or kwargs.get("files") or view is not None:
                self._notice_done = True
                return line
        except Exception:  # a notice must never break a command's reply
            pass
        return content

    # -- overridden senders -------------------------------------------------

    async def send(self, content: Optional[str] = None, **kwargs: Any):
        content = self._with_notice(content, kwargs)
        return await super().send(content, **kwargs)

    async def reply(self, content: Optional[str] = None, **kwargs: Any):
        content = self._with_notice(content, kwargs)
        return await super().reply(content, **kwargs)


def install(bot: commands.Bot) -> None:
    """Make ``bot`` build :class:`NoticeContext` for every prefix invocation."""
    original = bot.get_context

    async def get_context(origin, *, cls=NoticeContext):
        return await original(origin, cls=cls)

    bot.get_context = get_context  # type: ignore[method-assign]
