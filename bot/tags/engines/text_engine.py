"""
text: engine — load and return plain text from inline text, attachment,
replied attachment, or a URL.

Usage:
    {text:Hello World}              → "Hello World"
    {text:attachment}               → contents of the message attachment
    {text:reply}                    → contents of the replied-to attachment
    {text:https://example.com/f.txt}→ downloaded text

Supported file extensions: .txt .log .md .csv .json .yaml .yml .toml .ini .cfg
Supported encodings (tried in order): UTF-8 · UTF-16 · UTF-32 · Latin-1 · ASCII

Wrapping in {eval:...} re-parses the returned text as TagScript:
    {eval:{text:attachment}}
"""

from __future__ import annotations

import asyncio
import io

import aiohttp

from . import BaseEngine, EngineResult

# ── Limits ─────────────────────────────────────────────────────────────────────
MAX_BYTES = 1 * 1024 * 1024          # 1 MB
MAX_CHARS = 50_000
MAX_LINES = 5_000

# ── Allowed file extensions ────────────────────────────────────────────────────
_ALLOWED_EXT = frozenset({
    ".txt", ".log", ".md", ".csv",
    ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".html", ".xml",
})

# ── Encoding probe order ───────────────────────────────────────────────────────
_ENCODINGS = ("utf-8-sig", "utf-16", "utf-32", "latin-1", "ascii")


def _decode(raw: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError("unable to decode with any supported encoding")


def _truncate(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        text = "".join(lines) + f"\n… (truncated to {MAX_LINES} lines)"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n… (truncated to {MAX_CHARS} chars)"
    return text


async def _read_attachment(att) -> tuple[str, str]:
    """Download a discord Attachment and return (text, filename)."""
    from pathlib import Path
    ext = Path(att.filename).suffix.lower()
    if ext and ext not in _ALLOWED_EXT:
        return "", f"unsupported file type `{ext}`"

    async with aiohttp.ClientSession() as session:
        async with session.get(att.url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return "", f"download failed (HTTP {resp.status})"
            raw = await resp.read()

    if len(raw) > MAX_BYTES:
        return "", f"file too large ({len(raw) // 1024} KB, max {MAX_BYTES // 1024} KB)"

    try:
        text = _decode(raw)
    except ValueError as exc:
        return "", str(exc)

    return _truncate(text), ""


async def _read_url(url: str) -> tuple[str, str]:
    """Download a text URL and return (text, error)."""
    from pathlib import PurePosixPath
    from urllib.parse import urlparse
    parsed = urlparse(url)
    ext = PurePosixPath(parsed.path).suffix.lower()
    if ext and ext not in _ALLOWED_EXT:
        return "", f"unsupported file type `{ext}`"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return "", f"download failed (HTTP {resp.status})"
                ct = resp.headers.get("Content-Type", "")
                # Reject binary content types
                if ct and not any(t in ct for t in ("text", "json", "yaml", "xml", "csv", "plain")):
                    return "", f"URL content-type `{ct}` is not a text type"
                raw = await resp.read()
        except aiohttp.ClientError as exc:
            return "", f"network error: {exc}"

    if len(raw) > MAX_BYTES:
        return "", f"file too large ({len(raw) // 1024} KB, max {MAX_BYTES // 1024} KB)"

    try:
        text = _decode(raw)
    except ValueError as exc:
        return "", str(exc)

    return _truncate(text), ""


class TextEngine(BaseEngine):
    name = "text"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        source = content.strip()

        # ── Inline text ──────────────────────────────────────────────────────
        if not source:
            return EngineResult(error="text: no source provided")

        src_lower = source.lower()

        # ── URL ──────────────────────────────────────────────────────────────
        if src_lower.startswith("http://") or src_lower.startswith("https://"):
            text, err = await _read_url(source)
            if err:
                return EngineResult(error=f"text: {err}")
            return EngineResult(text=text)

        # ── Attachment ───────────────────────────────────────────────────────
        if src_lower == "attachment":
            att = None
            if ctx.message.attachments:
                att = ctx.message.attachments[0]
            if att is None:
                return EngineResult(error="text: no attachment found in this message")
            text, err = await _read_attachment(att)
            if err:
                return EngineResult(error=f"text: {err}")
            return EngineResult(text=text)

        # ── Reply ─────────────────────────────────────────────────────────────
        if src_lower == "reply":
            att = None
            if ctx.message.reference:
                try:
                    ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    if ref.attachments:
                        att = ref.attachments[0]
                except Exception:
                    pass
            if att is None:
                return EngineResult(error="text: no text attachment found in the replied-to message")
            text, err = await _read_attachment(att)
            if err:
                return EngineResult(error=f"text: {err}")
            return EngineResult(text=text)

        # ── Inline text (everything else) ─────────────────────────────────────
        return EngineResult(text=_truncate(source))
