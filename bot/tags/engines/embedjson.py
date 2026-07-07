"""
embedjson: engine — build a Discord embed from inline JSON.

Usage inside a tag:
    {embedjson:{"title":"Hello","description":"World","color":5765000}}

Supported fields:
    title, description, url, color (integer), timestamp (ISO string),
    footer {text, icon_url},
    author {name, url, icon_url},
    thumbnail {url},
    image {url},
    fields [{name, value, inline?}]

Variables are expanded before the JSON is parsed, so {user}, {args}, etc.
all work inside the JSON values.
"""

import json
from datetime import datetime, timezone

import discord

from . import BaseEngine, EngineResult


class EmbedJSONEngine(BaseEngine):
    name = "embedjson"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        raw = content.strip()
        if not raw:
            return EngineResult(error="embedjson: empty content")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return EngineResult(error=f"embedjson: invalid JSON — {exc}")

        if not isinstance(data, dict):
            return EngineResult(error="embedjson: JSON root must be an object {…}")

        embed = discord.Embed()

        if "title" in data:
            embed.title = str(data["title"])[:256]
        if "description" in data:
            embed.description = str(data["description"])[:4096]
        if "url" in data:
            try:
                embed.url = str(data["url"])
            except Exception:
                pass
        if "color" in data:
            try:
                embed.color = discord.Color(int(data["color"]) & 0xFFFFFF)
            except (ValueError, TypeError):
                pass
        if "timestamp" in data:
            try:
                embed.timestamp = datetime.fromisoformat(str(data["timestamp"]))
            except Exception:
                embed.timestamp = datetime.now(timezone.utc)

        footer = data.get("footer")
        if isinstance(footer, dict) and "text" in footer:
            embed.set_footer(
                text=str(footer["text"])[:2048],
                icon_url=footer.get("icon_url") or discord.utils.MISSING,
            )
        elif isinstance(footer, str):
            embed.set_footer(text=footer[:2048])

        author = data.get("author")
        if isinstance(author, dict) and "name" in author:
            embed.set_author(
                name=str(author["name"])[:256],
                url=author.get("url") or discord.utils.MISSING,
                icon_url=author.get("icon_url") or discord.utils.MISSING,
            )

        thumbnail = data.get("thumbnail")
        if isinstance(thumbnail, dict):
            url = thumbnail.get("url")
            if url:
                embed.set_thumbnail(url=url)
        elif isinstance(thumbnail, str) and thumbnail:
            embed.set_thumbnail(url=thumbnail)

        image = data.get("image")
        if isinstance(image, dict):
            url = image.get("url")
            if url:
                embed.set_image(url=url)
        elif isinstance(image, str) and image:
            embed.set_image(url=image)

        for field in (data.get("fields") or [])[:25]:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name", "\u200b"))[:256]
            value = str(field.get("value", "\u200b"))[:1024]
            inline = bool(field.get("inline", False))
            embed.add_field(name=name, value=value, inline=inline)

        return EngineResult(embed=embed)
