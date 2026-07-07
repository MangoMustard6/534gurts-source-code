"""
ihtx: engine — run the IHTX TagScript workflow on an attachment.

Syntax in a tag:
    {ihtx:repetitions duration noTrim format pipe_effects}

Examples:
    {ihtx:1 10 false mp4 speed=2}
    {ihtx:2 15 false mp4 multipitch=-12;12}
    {ihtx:1 8 false mp4 ffmpeg(-vf hue=h=50),negate}

Parameters:
    repetitions — integer number of processing passes
    duration    — duration expression (supports decimals, awk math)
    noTrim      — "true" or "false"
    format      — output format: mp4, gif, webm, mov, etc.
    pipe_effects — standard IHTX comma-delimited effect chain

The engine grabs the first attachment from the invoking message or its reply.
"""

import asyncio
import io
import os
import tempfile
from pathlib import Path

import discord

from . import BaseEngine, EngineResult

_MAX_OUTPUT = 25 * 1024 * 1024  # 25 MB Discord limit


class IHTXEngine(BaseEngine):
    name = "ihtx"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        try:
            from bot.ihtx_bot import (
                _run_ihtx_tagscript_workflow,
                download_attachment as _dl,
            )
        except ImportError as exc:
            return EngineResult(error=f"ihtx engine unavailable: {exc}")

        args_str = content.strip()
        if not args_str:
            return EngineResult(
                error="ihtx: provide args — repetitions duration noTrim format effects"
            )

        # Parse: reps duration noTrim format pipe_effects
        parts = args_str.split(None, 4)
        if len(parts) < 5:
            return EngineResult(
                error="ihtx: need all 5 args — repetitions duration noTrim format effects"
            )

        try:
            reps = int(parts[0])
        except ValueError:
            return EngineResult(error="ihtx: repetitions must be an integer")

        duration_expr = parts[1]
        no_trim = parts[2]
        export_format = parts[3].lstrip(".")
        pipe_effects = parts[4]

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
            return EngineResult(
                error="ihtx: no attachment found in this message or its reply"
            )

        suffix = Path(attachment.filename).suffix.lower() or ".mp4"
        loop = asyncio.get_running_loop()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, f"input{suffix}")
            output_path = os.path.join(tmpdir, "output.mp4")

            try:
                await _dl(attachment, input_path)
            except Exception as exc:
                return EngineResult(error=f"ihtx: download failed — {exc}")

            ok, err = await loop.run_in_executor(
                None,
                _run_ihtx_tagscript_workflow,
                input_path,
                output_path,
                reps,
                duration_expr,
                no_trim,
                export_format,
                pipe_effects,
            )

            if not ok:
                return EngineResult(error=f"ihtx failed: {err[-500:]}")

            if not os.path.exists(output_path):
                return EngineResult(error="ihtx: FFmpeg produced no output")

            out_size = os.path.getsize(output_path)
            if out_size > _MAX_OUTPUT:
                return EngineResult(error="ihtx: output too large (>25 MB)")

            out_bytes = Path(output_path).read_bytes()

        return EngineResult(
            files=[discord.File(io.BytesIO(out_bytes), filename="ihtx_output.mp4")]
        )
