"""
ffmpeg: engine — run FFmpeg on an attachment and return the result.

Aliases: ffmpeg, ff

The content is passed directly as FFmpeg arguments inserted between
``-i <input>`` and ``<output>``.

Usage (prefix syntax):
    ffmpeg:
    -vf negate

    ff:
    -vf hue=h=90 -af volume=2.0

Usage (brace syntax):
    {ffmpeg:-vf negate}
    {ff:-af volume=2.0}

Limits:
    Timeout: 120 seconds
    Output:  25 MB
"""

from __future__ import annotations

import asyncio
import io
import os
import shlex
import tempfile
from pathlib import Path

import discord

from . import BaseEngine, EngineResult

_TIMEOUT = 120.0
_MAX_OUTPUT = 25 * 1024 * 1024


class FFmpegScriptEngine(BaseEngine):
    name = "ffmpeg"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        raw_args = content.strip()
        if not raw_args:
            return EngineResult(error="ffmpeg: no arguments provided")

        try:
            user_args = shlex.split(raw_args)
        except ValueError as exc:
            return EngineResult(error=f"ffmpeg: invalid arguments — {exc}")

        # Locate attachment
        attachment = None
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

        if attachment is None:
            return EngineResult(error="ffmpeg: no attachment found in this message or its reply")

        suffix = Path(attachment.filename).suffix.lower() or ".mp4"

        loop = asyncio.get_running_loop()
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, f"input{suffix}")
            output_path = os.path.join(tmpdir, "output.mp4")

            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        data = await resp.read()
                with open(input_path, "wb") as f:
                    f.write(data)
            except Exception as exc:
                return EngineResult(error=f"ffmpeg: download failed — {exc}")

            cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                   "-i", input_path] + user_args + [output_path]

            def _run():
                import subprocess
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=_TIMEOUT,
                    )
                    return result.returncode, result.stderr
                except subprocess.TimeoutExpired:
                    return -1, f"timed out after {_TIMEOUT:.0f}s"
                except Exception as e:
                    return -1, str(e)

            rc, stderr = await loop.run_in_executor(None, _run)

            if rc != 0:
                return EngineResult(error=f"ffmpeg failed (rc={rc}): {stderr[-400:]}")

            if not os.path.exists(output_path):
                return EngineResult(error="ffmpeg: produced no output file")

            if os.path.getsize(output_path) > _MAX_OUTPUT:
                return EngineResult(error="ffmpeg: output too large (>25 MB)")

            out_bytes = Path(output_path).read_bytes()

        return EngineResult(
            files=[discord.File(io.BytesIO(out_bytes), filename="ffmpeg_output.mp4")]
        )
