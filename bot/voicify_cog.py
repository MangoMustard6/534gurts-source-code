"""Hybrid audio -> native Discord voice-message conversion.

Discord.py 2.7.1 does not expose a voice_message MessageFlags keyword or a
flags parameter on Messageable.send. This cog therefore uses discord.py's
HTTP multipart primitive with Discord's documented voice-message flag (8192)
and attachment metadata (duration_secs + waveform).
"""

from __future__ import annotations

import asyncio
import base64
import math
import os
import struct
import tempfile
import uuid
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from discord.http import MultipartParameters


SUPPORTED_AUDIO = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".webm"}
MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_DURATION_SECONDS = 600
FFMPEG_TIMEOUT = 120
VOICE_MESSAGE_FLAG = 8192


async def _run_process(
    *args: str,
    timeout: float = FFMPEG_TIMEOUT,
    stdin=None,
) -> tuple[bytes, bytes]:
    """Run a subprocess without a shell and kill it on timeout/failure."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=stdin,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise TimeoutError(f"{args[0]} exceeded the {int(timeout)}-second limit")
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        detail = stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"{args[0]} failed with exit code {process.returncode}: {detail}")
    return stdout, stderr


async def transcode_voice(input_path: str, output_path: str) -> None:
    """Encode Discord voice-message audio: Ogg container, Opus, mono, 48 kHz."""
    await _run_process(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", input_path,
        "-vn", "-map", "0:a:0",
        "-c:a", "libopus", "-application", "voip",
        "-ar", "48000", "-ac", "1", "-b:a", "64k",
        "-f", "ogg", output_path,
    )


async def _audio_metadata(path: str) -> tuple[float, bytes]:
    """Return duration and Discord's normalized 256-sample waveform bytes.

    Discord expects the attachment waveform to be a base64-encoded sequence
    of 256 unsigned byte amplitudes. RMS plus per-file normalization gives the
    client useful visual contrast; raw 16-bit peaks often render as a nearly
    flat line for quiet or dynamically compressed recordings.
    """
    raw, _ = await _run_process(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", path, "-f", "s16le", "-ac", "1", "-ar", "8000", "-",
    )
    duration_raw, _ = await _run_process(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    )
    try:
        duration = float(duration_raw.decode().strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("could not determine the converted audio duration") from exc
    if not math.isfinite(duration) or duration <= 0 or duration > MAX_DURATION_SECONDS:
        raise ValueError("audio duration must be greater than 0 and at most 10 minutes")

    samples = [
        value[0]
        for value in struct.iter_unpack("<h", raw[: len(raw) - (len(raw) % 2)])
    ]
    if not samples:
        raise ValueError("the converted audio contains no samples")
    bucket_count = 256
    levels: list[float] = []
    for index in range(bucket_count):
        start = index * len(samples) // bucket_count
        end = max(start + 1, (index + 1) * len(samples) // bucket_count)
        bucket = samples[start:end]
        rms = math.sqrt(sum(value * value for value in bucket) / len(bucket))
        levels.append(rms)
    floor = min(levels)
    ceiling = max(levels)
    spread = ceiling - floor
    if spread < 1e-9:
        # A constant/near-silent recording still needs a valid visible
        # waveform rather than 256 zero bytes.
        waveform = bytes([max(8, min(255, round(ceiling / 32767 * 255)))] * bucket_count)
    else:
        waveform = bytes(
            max(8, min(255, round(8 + 247 * ((level - floor) / spread))))
            for level in levels
        )
    return duration, waveform


async def _save_attachment(attachment: discord.Attachment, path: str) -> None:
    if attachment.size and attachment.size > MAX_INPUT_BYTES:
        raise ValueError("the input attachment exceeds the 50 MB limit")
    await attachment.save(path)
    if os.path.getsize(path) > MAX_INPUT_BYTES:
        raise ValueError("the input attachment exceeds the 50 MB limit")


async def _send_voice_message(
    channel: discord.abc.Messageable,
    path: str,
    duration: float,
    waveform: bytes,
    *,
    reply_to: discord.Message | None = None,
) -> None:
    """Post a raw voice-message multipart payload through discord.py's HTTP client."""
    channel_id = getattr(channel, "id", None)
    state = getattr(channel, "_state", None)
    http = getattr(state, "http", None)
    if channel_id is None or http is None:
        raise RuntimeError("this channel cannot send native voice messages")

    filename = "voice-message.ogg"
    file = discord.File(path, filename=filename)
    waveform_b64 = base64.b64encode(waveform).decode("ascii")
    if len(waveform) != 256 or len(base64.b64decode(waveform_b64)) != 256:
        raise ValueError("internal waveform generation did not produce 256 samples")
    attachment = {
        "id": 0,
        "filename": filename,
        "duration_secs": round(duration, 3),
        "waveform": waveform_b64,
    }
    payload: dict[str, object] = {
        "content": "",
        "flags": VOICE_MESSAGE_FLAG,
        "attachments": [attachment],
    }
    if reply_to is not None:
        payload["message_reference"] = {
            "message_id": str(reply_to.id),
            "channel_id": str(reply_to.channel.id),
            "fail_if_not_exists": False,
        }
    try:
        with MultipartParameters(
            payload=payload,
            multipart=[{
                "name": "files[0]",
                "value": file.fp,
                "filename": filename,
                "content_type": "audio/ogg",
            }],
            files=[file],
        ) as params:
            await http.send_message(channel_id, params=params)
    except Exception:
        file.close()
        raise


class VoicifyCog(commands.Cog, name="Voicify"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _run(self, ctx: commands.Context, attachment: discord.Attachment | None) -> None:
        if attachment is None:
            await ctx.reply("❌ Attach an audio file to use `th/voicify`.")
            return
        suffix = Path(attachment.filename).suffix.lower()
        if suffix not in SUPPORTED_AUDIO:
            await ctx.reply(
                f"❌ Unsupported audio type `{suffix or 'unknown'}`. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO))}"
            )
            return
        if attachment.size and attachment.size > MAX_INPUT_BYTES:
            await ctx.reply("❌ Audio attachments are limited to 50 MB.")
            return

        await ctx.defer()
        status = await ctx.send("📥 Downloading audio…")
        try:
            with tempfile.TemporaryDirectory(prefix=f"voicify_{uuid.uuid4().hex}_") as directory:
                input_path = os.path.join(directory, f"input{suffix}")
                output_path = os.path.join(directory, "voice-message.ogg")
                await _save_attachment(attachment, input_path)
                await status.edit(content="⚙️ Transcoding to mono 48 kHz Opus…")
                await transcode_voice(input_path, output_path)
                duration, waveform = await _audio_metadata(output_path)
                await status.edit(content="⬆️ Sending native Discord voice message…")
                await _send_voice_message(
                    ctx.channel, output_path, duration, waveform,
                    reply_to=getattr(ctx, "message", None),
                )
                await status.edit(content="✅ Voice message sent.")
        except Exception as exc:
            await status.edit(content=f"❌ Voicify failed: {str(exc)[:1600]}")

    @commands.hybrid_command(
        name="voicify",
        description="Convert an attached audio file into a native Discord voice message.",
    )
    @app_commands.describe(attachment="MP3, WAV, FLAC, M4A, AAC, OGG, or Opus audio")
    async def voicify(
        self, ctx: commands.Context, attachment: discord.Attachment | None = None
    ) -> None:
        message = getattr(ctx, "message", None)
        message_attachments = getattr(message, "attachments", ()) if message else ()
        attachment = attachment or (message_attachments[0] if message_attachments else None)
        await self._run(ctx, attachment)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoicifyCog(bot))