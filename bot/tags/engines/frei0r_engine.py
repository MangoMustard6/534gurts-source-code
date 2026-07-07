"""
frei0r: engine — apply a frei0r video effect plugin via FFmpeg.

Aliases: frei0r, fr0r

Content format:
    <plugin_name>[:<param1>:<param2>:…]

Where params are colon-separated floats or strings accepted by the plugin.
FFmpeg must be built with frei0r support and the frei0r plugins must be installed.

Usage (prefix syntax):
    frei0r:
    distort0r:0.5:0.1

    fr0r:
    cartoon:0.5:0.1:0.01

Usage (brace syntax):
    {frei0r:distort0r:0.5:0.1}

Finding available plugins:
    Run `ffmpeg -vf frei0r=<plugin>` to test a plugin.
    Common plugins: distort0r, cartoon, edgeglow, pixelize, plasma, sobel, threshold0r

Limits:
    Timeout: 120 seconds
    Output:  25 MB
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from pathlib import Path

import discord

from . import BaseEngine, EngineResult

_TIMEOUT = 120.0
_MAX_OUTPUT = 25 * 1024 * 1024


class Frei0rScriptEngine(BaseEngine):
    name = "frei0r"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        spec = content.strip()
        if not spec:
            return EngineResult(error="frei0r: provide a plugin name, e.g. `frei0r:distort0r:0.5`")

        # Build the frei0r filter string: frei0r=plugin:p1:p2:...
        frei0r_filter = f"frei0r={spec}"

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
            return EngineResult(error="frei0r: no attachment found in this message or its reply")

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
                return EngineResult(error=f"frei0r: download failed — {exc}")

            cmd = [
                "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                "-i", input_path,
                "-vf", frei0r_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-c:a", "copy",
                output_path,
            ]

            def _run():
                import subprocess
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=_TIMEOUT
                    )
                    return result.returncode, result.stderr
                except subprocess.TimeoutExpired:
                    return -1, f"timed out after {_TIMEOUT:.0f}s"
                except Exception as e:
                    return -1, str(e)

            rc, stderr = await loop.run_in_executor(None, _run)

            if rc != 0:
                short_err = stderr[-500:].strip()
                if "No such filter" in stderr or "not found" in stderr.lower():
                    return EngineResult(
                        error=f"frei0r: plugin not found — check plugin name or that frei0r is installed.\n```\n{short_err}\n```"
                    )
                return EngineResult(error=f"frei0r failed (rc={rc}): {short_err}")

            if not os.path.exists(output_path):
                return EngineResult(error="frei0r: produced no output file")

            if os.path.getsize(output_path) > _MAX_OUTPUT:
                return EngineResult(error="frei0r: output too large (>25 MB)")

            out_bytes = Path(output_path).read_bytes()

        return EngineResult(
            files=[discord.File(io.BytesIO(out_bytes), filename="frei0r_output.mp4")]
        )
