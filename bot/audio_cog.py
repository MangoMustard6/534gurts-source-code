"""NotSoBot-style multimedia audio replacement commands."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


MAX_INPUT_BYTES = 200 * 1024 * 1024
FFMPEG_TIMEOUT = 180
URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
MEDIA_EXTENSIONS = {
    ".3gp", ".aac", ".avi", ".flac", ".gif", ".jpeg", ".jpg", ".m4a",
    ".mkv", ".mov", ".mp3", ".mp4", ".ogg", ".opus", ".png", ".wav",
    ".webm", ".webp", ".wmv",
}


def _url_name(url: str, fallback: str) -> str:
    name = Path(urllib.parse.urlparse(url).path).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:120] or fallback


async def _download(url: str, destination: str, fallback: str) -> str:
    timeout = aiohttp.ClientTimeout(total=300, connect=20)
    async with aiohttp.ClientSession(
        timeout=timeout, headers={"User-Agent": "IHTX-Discord-Bot/audio"}
    ) as session:
        async with session.get(url, allow_redirects=True) as response:
            if response.status != 200:
                raise ValueError(f"download failed with HTTP {response.status}")
            path = os.path.join(destination, _url_name(url, fallback))
            with open(path, "wb") as handle:
                async for chunk in response.content.iter_chunked(256 * 1024):
                    handle.write(chunk)
                    if handle.tell() > MAX_INPUT_BYTES:
                        raise ValueError("input exceeds the 200 MB limit")
            return path


async def _run(*args: str, timeout: float = FFMPEG_TIMEOUT) -> tuple[bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise TimeoutError(f"{args[0]} timed out after {int(timeout)} seconds")
    if process.returncode:
        detail = stderr.decode("utf-8", "replace")[-1600:]
        command = " ".join(args)
        raise RuntimeError(f"{args[0]} failed: {detail}\nCommand: {command[-1200:]}")
    return stdout, stderr


async def _duration(path: str) -> float:
    stdout, _ = await _run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    )
    try:
        value = float(stdout.decode().strip())
    except ValueError as exc:
        if stdout.decode().strip().upper() in {"N/A", "NA", ""}:
            return 0.0
        raise ValueError(f"could not determine duration for `{Path(path).name}`") from exc
    if value <= 0:
        # Still images have no media duration until FFmpeg loops them. The
        # caller supplies the replacement audio duration for that case.
        return 0.0
    return value


async def _has_video(path: str) -> bool:
    stdout, _ = await _run(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_type", "-of", "csv=p=0", path,
    )
    return bool(stdout.strip())


async def _stream_types(path: str) -> set[str]:
    stdout, _ = await _run(
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1", path,
    )
    return {line.strip() for line in stdout.decode("utf-8", "replace").splitlines() if line.strip()}


def _is_still_image(path: str) -> bool:
    return Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}


async def _resolve_reference(ctx: commands.Context, query: str | None) -> discord.Message | None:
    message = getattr(ctx, "message", None)
    if query and query.lower() in {"ref", "reply", "reference"}:
        query = None
    if not query and message and message.reference and message.reference.message_id:
        try:
            return await ctx.channel.fetch_message(message.reference.message_id)
        except Exception:
            return None
    if not query:
        return None
    match = re.search(r"/channels/\d+/(\d+)/(\d+)$", query)
    if match:
        try:
            return await ctx.channel.fetch_message(int(match.group(3)))
        except Exception:
            return None
    if query.isdigit():
        try:
            return await ctx.channel.fetch_message(int(query))
        except Exception:
            return None
    return None


async def _resolve_source(
    ctx: commands.Context,
    token: str | None,
    attachments: list[discord.Attachment],
    attachment_index: int,
    destination: str,
    fallback: str,
) -> tuple[str, int]:
    if token and token.lower() in {"ref", "reply", "reference"}:
        token = None
    if token and URL_RE.match(token):
        return await _download(token, destination, fallback), attachment_index
    reference = await _resolve_reference(ctx, token)
    if reference and reference.attachments:
        attachment = reference.attachments[0]
        path = os.path.join(destination, _url_name(attachment.filename, fallback))
        await attachment.save(path)
        return path, attachment_index
    if token and token.isdigit():
        raise ValueError(f"could not resolve media reference `{token}`")
    if attachment_index < len(attachments):
        attachment = attachments[attachment_index]
        path = os.path.join(destination, _url_name(attachment.filename, fallback))
        await attachment.save(path)
        return path, attachment_index + 1
    raise ValueError("provide both media inputs as attachments, URLs, or references")


async def replace_audio(
    media_path: str,
    audio_path: str,
    output_path: str,
    *,
    longest: bool = False,
    noloop: bool = False,
) -> None:
    """Replace media audio, looping only when the shorter audio needs it."""
    media_duration, audio_duration = await asyncio.gather(
        _duration(media_path), _duration(audio_path)
    )
    if audio_duration <= 0:
        raise ValueError("replacement input has no usable audio duration")
    if media_duration <= 0:
        media_duration = audio_duration
    media_video = await _has_video(media_path)
    still_image = _is_still_image(media_path)
    has_visual = media_video or still_image
    should_loop = not noloop and audio_duration < media_duration
    should_pad = longest and noloop and audio_duration < media_duration
    if longest:
        target_duration = max(media_duration, audio_duration)
    elif should_loop:
        target_duration = media_duration
    else:
        target_duration = min(media_duration, audio_duration)

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if still_image:
        command += ["-loop", "1", "-i", media_path]
    else:
        command += ["-i", media_path]
    if should_loop:
        command += ["-stream_loop", "-1"]
    command += ["-i", audio_path]

    if has_visual:
        command += [
            "-map", "0:v:0", "-map", "1:a:0", "-sn",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
        ]
    else:
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"]
    if should_pad:
        command += ["-af", "apad"]
    if not longest:
        command += ["-shortest"]
    # Always bound the output explicitly. This prevents FFmpeg from waiting
    # forever on an infinite stream_loop input when duration metadata is
    # missing or unreliable.
    command += ["-t", f"{target_duration:.6f}"]
    command += ["-movflags", "+faststart", output_path]
    await _run(*command)
    if not os.path.isfile(output_path) or os.path.getsize(output_path) < 1024:
        raise RuntimeError("FFmpeg produced an empty output video")
    streams = await _stream_types(output_path)
    if has_visual and "video" not in streams:
        raise RuntimeError("FFmpeg output is missing its video stream")
    if "audio" not in streams:
        raise RuntimeError("FFmpeg output is missing its replacement audio stream")


class AudioCog(commands.Cog, name="Audio"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _execute(
        self,
        ctx: commands.Context,
        media: str | None,
        audio: str | None,
        longest: bool,
        noloop: bool,
        slash_attachments: list[discord.Attachment] | None = None,
    ) -> None:
        await ctx.defer()
        status = await ctx.send("📥 Resolving media inputs…")
        try:
            message = getattr(ctx, "message", None)
            attachments = list(getattr(message, "attachments", ()) if message else ())
            if slash_attachments:
                attachments = slash_attachments + attachments
            with tempfile.TemporaryDirectory(prefix="audio_replace_") as directory:
                media_path, next_index = await _resolve_source(
                    ctx, media, attachments, 0, directory, "media.bin"
                )
                audio_path, _ = await _resolve_source(
                    ctx, audio, attachments, next_index, directory, "audio.bin"
                )
                if os.path.getsize(media_path) == 0:
                    raise ValueError("the base media download was empty")
                if os.path.getsize(audio_path) == 0:
                    raise ValueError("the replacement audio download was empty")
                await status.edit(content="⚙️ Replacing audio with FFmpeg…")
                output_path = os.path.join(directory, "audio-replaced.mp4")
                await replace_audio(
                    media_path, audio_path, output_path,
                    longest=longest, noloop=noloop,
                )
                await status.edit(content="⬆️ Uploading result…")
                output_size = os.path.getsize(output_path)
                if output_size < 1024:
                    raise RuntimeError("the rendered output is empty")
                try:
                    await ctx.send(
                        file=discord.File(output_path, filename="audio-replaced.mp4"),
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"Discord rejected the {output_size / 1024 / 1024:.1f} MB output: {exc}"
                    ) from exc
                await status.edit(content="✅ Audio replaced.")
        except Exception as exc:
            await status.edit(content=f"❌ Audio replacement failed: {str(exc)[:1600]}")

    @commands.group(
        name="audio",
        aliases=["a"],
        invoke_without_command=True,
    )
    async def audio(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.reply("Usage: `.audio put replace <media> <audio> [-longest] [-noloop]`")

    @audio.group(name="put", invoke_without_command=True)
    async def audio_put(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.reply("Usage: `.audio put replace <media> <audio> [-longest] [-noloop]`")

    @audio_put.command(name="replace")
    async def audio_put_replace_prefix(
        self, ctx: commands.Context, *, args: str = ""
    ) -> None:
        tokens = shlex.split(args)
        longest = any(t.lower() in {"-longest", "longest"} for t in tokens)
        noloop = any(t.lower() in {"-noloop", "noloop"} for t in tokens)
        tokens = [
            t for t in tokens
            if t.lower() not in {"-longest", "longest", "-noloop", "noloop"}
        ]
        if len(tokens) > 2:
            await ctx.reply("Usage: `.audio put replace <media> <audio> [-longest] [-noloop]`")
            return
        await self._execute(
            ctx, tokens[0] if tokens else None, tokens[1] if len(tokens) > 1 else None,
            longest, noloop,
        )

async def setup(bot: commands.Bot) -> None:
    cog = AudioCog(bot)
    await bot.add_cog(cog)

    # Keep prefix parsing free-form (URLs and `-longest`/`-noloop` tokens),
    # while exposing typed Boolean options for the slash command.
    slash_audio = app_commands.Group(
        name="audio", description="Multimedia audio operations."
    )
    slash_put = app_commands.Group(
        name="put", description="Put or replace multimedia streams."
    )
    slash_audio.add_command(slash_put)

    @slash_put.command(
        name="replace",
        description="Replace a media container's audio stream.",
    )
    @app_commands.describe(
        media="Base image, video, or audio URL/reference.",
        audio="Replacement audio URL/reference.",
        longest="Extend output to the longest input stream.",
        noloop="Do not loop shorter replacement audio.",
    )
    async def slash_replace(
        interaction: discord.Interaction,
        media: str | None = None,
        audio: str | None = None,
        longest: bool = False,
        noloop: bool = False,
        media_attachment: discord.Attachment | None = None,
        audio_attachment: discord.Attachment | None = None,
    ) -> None:
        ctx = await commands.Context.from_interaction(interaction)
        await cog._execute(
            ctx,
            media,
            audio,
            longest,
            noloop,
            [a for a in (media_attachment, audio_attachment) if a is not None],
        )

    bot.tree.add_command(slash_audio)