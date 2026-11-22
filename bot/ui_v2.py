"""Components V2 helpers.

``embed_view(embed)`` turns any ``discord.Embed`` into a Components V2
``LayoutView`` so an existing embed can be sent as a V2 message:

    await ctx.reply(view=embed_view(embed))

Rules of Components V2 messages that callers must respect:

* the message cannot also carry ``content``, ``embed``/``embeds`` or a poll;
* the flag is permanent, so a V2 message cannot later be edited back into a
  classic embed message (edit it with ``view=`` again, or send a new one);
* at most 40 components and 4000 characters of text per message.

Only the discord.py 2.6+ V2 API is used (``ui.LayoutView``, ``ui.Container``,
``ui.TextDisplay``, ``ui.Section``, ``ui.Thumbnail``, ``ui.MediaGallery``,
``ui.Separator``).
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import ui

MAX_TEXT = 4000        # display characters across all text in one V2 message
MAX_COMPONENTS = 40    # components in one V2 message, children included
_ELLIPSIS = "…"
_TRUNCATED = "\n…(truncated)"


def _clip(text: str, limit: int) -> str:
    """Clip ``text`` to ``limit`` characters, marking the cut."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= len(_TRUNCATED):
        return text[:limit]
    return text[: limit - len(_TRUNCATED)].rstrip() + _TRUNCATED


def _is_http(url: Optional[str]) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _footer_text(embed: discord.Embed) -> str:
    parts: list[str] = []
    footer = embed.footer.text if embed.footer else None
    if footer:
        parts.append(str(footer))
    if embed.timestamp is not None:
        parts.append(discord.utils.format_dt(embed.timestamp, "f"))
    return " • ".join(parts)


def _compose(embed: discord.Embed) -> tuple[str, str, str]:
    """The embed's text as V2 markdown, unclipped: ``(head, fields, footer)``."""
    head_lines: list[str] = []
    author = embed.author.name if embed.author else None
    if author:
        head_lines.append(f"-# {author}")
    if embed.title:
        title = str(embed.title)
        head_lines.append(f"## [{title}]({embed.url})" if _is_http(embed.url) else f"## {title}")
    if embed.description:
        head_lines.append(str(embed.description))
    head = "\n".join(head_lines)

    fields_text = "\n\n".join(f"**{f.name}**\n{f.value}" for f in embed.fields)

    footer_line = _footer_text(embed)
    footer_block = f"-# {footer_line}" if footer_line else ""
    return head, fields_text, footer_block


# Room kept free for the prefix-command notice (see bot.prefix_notice) and
# separators when deciding whether an embed fits.
_NOTICE_RESERVE = 300


def embed_fits(embed: discord.Embed) -> bool:
    """True if ``embed`` can be shown as V2 without clipping any text."""
    head, fields_text, footer_block = _compose(embed)
    return len(head) + len(fields_text) + len(footer_block) + _NOTICE_RESERVE <= MAX_TEXT


def embed_payload(embed: discord.Embed) -> dict:
    """Keyword arguments that send ``embed`` in the best available format.

    ``{"view": <Components V2 layout>}`` when the embed fits, otherwise
    ``{"embed": embed}`` so long output (help pages, listings) is never cut:

        await ctx.reply(**embed_payload(embed))

    Only use it for messages that are sent once and never edited: a V2 message
    cannot be edited back into a classic embed message.
    """
    if embed_fits(embed):
        # Text inside an embed never pings, but text in a V2 message can, so
        # block mentions (user-written tag text, ``say`` ...) while keeping the
        # normal reply ping to the person who ran the command.
        return {
            "view": embed_to_layout(embed),
            "allowed_mentions": discord.AllowedMentions(
                everyone=False, users=False, roles=False, replied_user=True
            ),
        }
    return {"embed": embed}


def embed_to_layout(
    embed: discord.Embed,
    *,
    notice: Optional[str] = None,
    timeout: Optional[float] = None,
) -> ui.LayoutView:
    """Render ``embed`` as a Components V2 layout.

    The embed's colour becomes the container's accent colour, the title becomes
    a heading, fields become bold-labelled blocks, the thumbnail becomes the
    header section's accessory, the image becomes a media gallery and the
    footer/timestamp become small subtext.  ``notice`` (optional) is appended
    as subtext at the bottom.

    Text is clipped so the message always stays within Discord's limits; use
    :func:`embed_payload` to fall back to a classic embed instead of clipping.
    """
    head, fields_text, footer_block = _compose(embed)
    notice_line = f"-# {notice}" if notice else ""

    # Reserve room for the bottom lines first so they are never clipped away.
    reserved = len(footer_block) + len(notice_line)
    budget = max(MAX_TEXT - reserved - 16, 200)

    # Split the remaining budget: header first, fields get what is left but
    # never less than a quarter, so a long description cannot hide every field.
    if head and fields_text:
        head_cap = max(budget - min(len(fields_text), budget // 4), budget // 2)
    else:
        head_cap = budget
    head = _clip(head, head_cap)
    fields_text = _clip(fields_text, budget - len(head))

    children: list[ui.Item] = []

    thumb = embed.thumbnail.url if embed.thumbnail else None
    if head and _is_http(thumb):
        children.append(ui.Section(ui.TextDisplay(head), accessory=ui.Thumbnail(thumb)))
    elif head:
        children.append(ui.TextDisplay(head))

    if fields_text:
        if children:
            children.append(ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small))
        children.append(ui.TextDisplay(fields_text))

    image = embed.image.url if embed.image else None
    if _is_http(image):
        children.append(ui.MediaGallery(discord.MediaGalleryItem(image)))

    if footer_block or notice_line:
        if children:
            children.append(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        if footer_block:
            children.append(ui.TextDisplay(footer_block))
        if notice_line:
            children.append(ui.TextDisplay(notice_line))

    if not children:  # an empty embed still has to render something
        children.append(ui.TextDisplay("​"))

    colour = embed.colour
    container = ui.Container(*children, accent_colour=colour) if colour else ui.Container(*children)

    view = ui.LayoutView(timeout=timeout)
    view.add_item(container)
    return view


def embed_view(embed: discord.Embed, **kwargs) -> ui.LayoutView:
    """Short alias for :func:`embed_to_layout`, used at call sites."""
    return embed_to_layout(embed, **kwargs)


def _walk_text_len(item) -> int:
    total = 0
    content = getattr(item, "content", None)
    if isinstance(content, str) and isinstance(item, ui.TextDisplay):
        total += len(content)
    for child in getattr(item, "children", ()) or ():
        total += _walk_text_len(child)
    return total


def add_notice(view: ui.LayoutView, text: str) -> bool:
    """Append ``text`` as subtext at the bottom of ``view``.

    The notice goes inside the last container, below a separator, so it
    shares the embed's accent colour.  Returns ``False`` (and leaves the view
    untouched) when it would not fit within Discord's limits.
    """
    line = f"-# {text}"
    used = sum(_walk_text_len(c) for c in view.children)
    if used + len(line) > MAX_TEXT:
        return False

    container = next((c for c in reversed(view.children) if isinstance(c, ui.Container)), None)
    try:
        if container is not None:
            container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            container.add_item(ui.TextDisplay(line))
        else:
            view.add_item(ui.TextDisplay(line))
    except ValueError:  # too many components
        return False
    return True
