"""
attach: engine — download a file from a URL and attach it to the message.

Usage inside a tag:
    {attach:https://example.com/image.png}
"""

import io
import aiohttp
import discord
from . import BaseEngine, EngineResult

_ALLOWED_SCHEMES = ("http://", "https://")
_BLOCKED_HOSTS = ("localhost", "127.", "0.", "192.168.", "10.", "172.16.",
                  "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
                  "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
                  "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
                  "::1", "metadata.google")
_MAX_BYTES = 8 * 1024 * 1024  # 8 MB Discord limit


class AttachEngine(BaseEngine):
    name = "attach"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        url = content.strip()

        if not any(url.startswith(s) for s in _ALLOWED_SCHEMES):
            return EngineResult(error="attach: only http/https URLs are allowed")

        url_lower = url.lower()
        for blocked in _BLOCKED_HOSTS:
            if blocked in url_lower:
                return EngineResult(error="attach: URL is not allowed")

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return EngineResult(error=f"attach: HTTP {resp.status}")

                    cl = int(resp.headers.get("Content-Length", 0))
                    if cl > _MAX_BYTES:
                        return EngineResult(error="attach: file too large (max 8 MB)")

                    data = await resp.read()
                    if len(data) > _MAX_BYTES:
                        return EngineResult(error="attach: file too large (max 8 MB)")

                    filename = url.split("?")[0].rstrip("/").split("/")[-1] or "file"
                    if "." not in filename:
                        ct = resp.headers.get("Content-Type", "")
                        ext = ct.split("/")[-1].split(";")[0].strip()
                        filename = f"file.{ext}" if ext else "file.bin"

                    return EngineResult(
                        files=[discord.File(io.BytesIO(data), filename=filename)]
                    )

        except aiohttp.ClientError as exc:
            return EngineResult(error=f"attach: network error — {exc}")
        except Exception as exc:
            return EngineResult(error=f"attach: {exc}")
