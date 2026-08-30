"""Discord file export command.

The export path deliberately uses a parser registry so dedicated formats can
be added without growing a monolithic command handler.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


MAX_INPUT_BYTES = 25 * 1024 * 1024
DEFAULT_UPLOAD_LIMIT = 25 * 1024 * 1024
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=120, connect=15)
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class ExportError(ValueError):
    """An expected user-facing export failure."""


def _safe_filename(filename: str) -> str:
    name = Path(filename or "attachment.bin").name
    name = _SAFE_FILENAME.sub("_", name).strip("._")
    return (name[:160] or "attachment.bin")


def _metadata(filename: str, data: bytes) -> dict[str, Any]:
    safe_name = _safe_filename(filename)
    extension = Path(safe_name).suffix.lower()
    mime, _ = mimetypes.guess_type(safe_name)
    return {
        "filename": safe_name,
        "size": len(data),
        "mime": mime or "application/octet-stream",
        "extension": extension or None,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _number(value: str, line_number: int) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ExportError(f"Invalid LUT number on line {line_number}.") from exc
    if not math.isfinite(parsed):
        raise ExportError(f"Non-finite LUT number on line {line_number}.")
    return parsed


def parse_cube(data: bytes, filename: str) -> dict[str, Any]:
    """Parse a 3D .cube LUT into metadata, directives, and RGB rows."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExportError("The .cube file is not valid UTF-8 text.") from exc

    title: str | None = None
    size: int | None = None
    domain_min = [0.0, 0.0, 0.0]
    domain_max = [1.0, 1.0, 1.0]
    rows: list[dict[str, float]] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        directive = parts[0].upper()
        values = parts[1:]

        if directive == "TITLE":
            raw_title = line[len(parts[0]):].strip()
            if len(raw_title) >= 2 and raw_title[0] == raw_title[-1] == '"':
                raw_title = raw_title[1:-1]
            title = raw_title
        elif directive == "LUT_3D_SIZE":
            if len(values) != 1:
                raise ExportError(f"Invalid LUT_3D_SIZE on line {line_number}.")
            try:
                size = int(values[0])
            except ValueError as exc:
                raise ExportError(f"Invalid LUT_3D_SIZE on line {line_number}.") from exc
            if size < 2:
                raise ExportError("LUT_3D_SIZE must be at least 2.")
        elif directive in {"DOMAIN_MIN", "DOMAIN_MAX"}:
            if len(values) != 3:
                raise ExportError(f"{directive} must contain three values.")
            parsed = [_number(value, line_number) for value in values]
            if directive == "DOMAIN_MIN":
                domain_min = parsed
            else:
                domain_max = parsed
        elif directive in {"LUT_1D_SIZE", "LUT_1D_INPUT_RANGE"}:
            raise ExportError("1D LUTs are not supported; attach a 3D .cube LUT.")
        elif len(parts) == 3:
            rows.append({
                "r": _number(parts[0], line_number),
                "g": _number(parts[1], line_number),
                "b": _number(parts[2], line_number),
            })
        else:
            raise ExportError(f"Unrecognized .cube content on line {line_number}.")

    if size is None:
        raise ExportError("The .cube file is missing LUT_3D_SIZE.")
    expected_rows = size ** 3
    if len(rows) != expected_rows:
        raise ExportError(
            f"The .cube table has {len(rows)} rows; expected {expected_rows} for size {size}."
        )

    return {
        "mode": "cube_3d",
        "metadata": _metadata(filename, data),
        "cube": {
            "title": title,
            "size": size,
            "domain_min": domain_min,
            "domain_max": domain_max,
            "rows": rows,
        },
    }


def parse_raw(data: bytes, filename: str) -> dict[str, Any]:
    """Fallback parser for arbitrary files."""
    return {
        "mode": "raw",
        "metadata": _metadata(filename, data),
        "encoding": "base64",
        "content": base64.b64encode(data).decode("ascii"),
    }


Parser = Callable[[bytes, str], dict[str, Any]]
PARSERS: dict[str, Parser] = {
    ".cube": parse_cube,
}


async def _download_attachment(attachment: discord.Attachment) -> bytes:
    if attachment.size and attachment.size > MAX_INPUT_BYTES:
        raise ExportError(
            f"`{_safe_filename(attachment.filename)}` is too large. "
            f"Export inputs are limited to {MAX_INPUT_BYTES // (1024 * 1024)} MiB."
        )

    url = attachment.proxy_url or attachment.url
    chunks: list[bytes] = []
    total = 0
    try:
        async with aiohttp.ClientSession(timeout=DOWNLOAD_TIMEOUT) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    raise ExportError(f"Discord returned HTTP {response.status} while downloading the file.")
                async for chunk in response.content.iter_chunked(256 * 1024):
                    total += len(chunk)
                    if total > MAX_INPUT_BYTES:
                        raise ExportError(
                            f"`{_safe_filename(attachment.filename)}` exceeds the "
                            f"{MAX_INPUT_BYTES // (1024 * 1024)} MiB input limit."
                        )
                    chunks.append(chunk)
    except ExportError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        raise ExportError(f"Could not download `{_safe_filename(attachment.filename)}`.") from exc
    return b"".join(chunks)


def _upload_limit(source: discord.Interaction | commands.Context) -> int:
    guild = getattr(source, "guild", None)
    limit = getattr(guild, "filesize_limit", None)
    if isinstance(limit, int) and limit > 0:
        return limit
    return DEFAULT_UPLOAD_LIMIT


def _error_text(error: Exception) -> str:
    return f"❌ Export failed: {str(error)[:700]}"


class FileExportCog(commands.Cog, name="File Export"):
    """Export Discord attachments as structured JSON."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _build_export(
        self,
        attachment: discord.Attachment,
        output_directory: str,
        upload_limit: int,
    ) -> str:
        data = await _download_attachment(attachment)
        filename = _safe_filename(attachment.filename)
        parser = PARSERS.get(Path(filename).suffix.lower(), parse_raw)
        payload = parser(data, filename)

        output_name = f"{filename}.json"
        output_path = os.path.join(output_directory, output_name)
        with open(output_path, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")

        output_size = os.path.getsize(output_path)
        if output_size > upload_limit:
            raise ExportError(
                f"The JSON output is {output_size / (1024 * 1024):.1f} MiB, "
                f"which exceeds this server's {upload_limit / (1024 * 1024):.1f} MiB upload limit."
            )
        return output_path

    async def _prefix_export(self, ctx: commands.Context) -> None:
        attachment = ctx.message.attachments[0] if ctx.message.attachments else None
        if attachment is None:
            await ctx.reply("❌ Attach a file to export. Usage: `th>export`.")
            return
        with tempfile.TemporaryDirectory(prefix="discord-export-") as directory:
            try:
                output_path = await self._build_export(
                    attachment, directory, _upload_limit(ctx)
                )
                await ctx.reply(
                    content=f"✅ Exported `{_safe_filename(attachment.filename)}`.",
                    file=discord.File(output_path, filename=Path(output_path).name),
                )
            except (ExportError, OSError, discord.HTTPException) as exc:
                await ctx.reply(_error_text(exc))

    @commands.command(name="export")
    async def export_prefix(self, ctx: commands.Context) -> None:
        """Export the first attached file as JSON."""
        await self._prefix_export(ctx)

    @app_commands.command(name="export", description="Export an attached file as structured JSON.")
    @app_commands.describe(attachment="The file to parse and export as JSON.")
    async def export_slash(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment,
    ) -> None:
        await interaction.response.defer()
        with tempfile.TemporaryDirectory(prefix="discord-export-") as directory:
            try:
                output_path = await self._build_export(
                    attachment, directory, _upload_limit(interaction)
                )
                await interaction.followup.send(
                    content=f"✅ Exported `{_safe_filename(attachment.filename)}`.",
                    file=discord.File(output_path, filename=Path(output_path).name),
                )
            except (ExportError, OSError, discord.HTTPException) as exc:
                await interaction.followup.send(_error_text(exc), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Support the requested !export spelling without enabling ! globally."""
        if message.author.bot:
            return
        match = re.match(r"^!export(?:\s*)$", message.content, flags=re.IGNORECASE)
        if not match:
            return
        ctx = await self.bot.get_context(message)
        await self._prefix_export(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FileExportCog(bot))