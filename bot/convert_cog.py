"""Hybrid /convert media transcoder.

Flow: Discord attachment/URL -> temporary local file -> ffprobe validation ->
async FFmpeg subprocess -> size-aware retry -> Discord upload. Every job uses
TemporaryDirectory and a 120-second subprocess deadline.

Discord does not support a union-typed slash option, so the hybrid command
exposes an optional URL/text input and an optional attachment override. This
allows `/convert attachment:...`, `/convert input:https://...`, and
`!convert` with either an attached file or a URL.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

try:
    import yt_dlp
except ImportError:  # pragma: no cover - the bot reports a useful runtime error
    yt_dlp = None


FORMATS = {
    "mp4", "webm", "mov", "mkv", "gif",
    "png", "jpg", "webp",
    "mp3", "wav", "ogg", "flac",
}
VIDEO_FORMATS = {"mp4", "webm", "mov", "mkv", "gif"}
IMAGE_FORMATS = {"png", "jpg", "webp"}
AUDIO_FORMATS = {"mp3", "wav", "ogg", "flac"}
QUALITIES = {"low", "medium", "high", "lossless"}
MAX_JOB_SECONDS = 120
MAX_INPUT_BYTES = 200 * 1024 * 1024
MAX_CLIP_SECONDS = 30
MAX_GENERAL_DURATION = 600
URL_RE = re.compile(r"https?://\S+", re.I)


def _guild_upload_limit(guild: Optional[discord.Guild]) -> int:
    """Return the requested conservative tier-based upload ceiling."""
    if guild is None:
        return 25 * 1024 * 1024
    # Discord's documented limits vary by account/client; these are deliberate
    # safety ceilings matching the bot's configured boost-tier policy.
    return {
        0: 25 * 1024 * 1024,
        1: 50 * 1024 * 1024,
        2: 100 * 1024 * 1024,
        3: 500 * 1024 * 1024,
    }.get(getattr(guild, "premium_tier", 0), 25 * 1024 * 1024)


def _safe_name(value: str, fallback: str = "input") -> str:
    name = Path(urllib.parse.urlparse(value).path).name or fallback
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:100] or fallback


def _parse_start(value: str) -> float:
    raw = value.strip().lower()
    if not raw:
        return 0.0
    if raw.endswith("ms"):
        return float(raw[:-2]) / 1000
    if raw.endswith("s"):
        return float(raw[:-1])
    parts = raw.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) > 3 or any(not p for p in parts):
        raise ValueError("start_time must be seconds or HH:MM:SS (for example `00:15`).")
    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError("start_time must be seconds or HH:MM:SS.") from exc
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0] * 3600 + nums[1] * 60 + nums[2]


async def _direct_download(url: str, destination: str) -> str:
    headers = {"User-Agent": "IHTX-Discord-Bot/convert"}
    timeout = aiohttp.ClientTimeout(total=300, connect=15)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            name = _safe_name(url, "download.bin")
            path = os.path.join(destination, name)
            with open(path, "wb") as handle:
                async for chunk in response.content.iter_chunked(256 * 1024):
                    handle.write(chunk)
                    if handle.tell() > MAX_INPUT_BYTES:
                        raise ValueError("input exceeds the 200 MB safety limit")
            return path


def _ytdlp_download(url: str, destination: str) -> str:
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed; URL conversion is unavailable.")
    template = os.path.join(destination, "%(title).80s.%(ext)s")
    options = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": template,
        "noplaylist": True,
        "max_filesize": MAX_INPUT_BYTES,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([url])
    files = [
        p for p in Path(destination).iterdir()
        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
    ]
    if not files:
        raise ValueError("yt-dlp produced no media file.")
    path = max(files, key=lambda p: p.stat().st_mtime)
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("input exceeds the 200 MB safety limit")
    return str(path)


async def _download_source(source: str | discord.Attachment, directory: str) -> str:
    if isinstance(source, discord.Attachment):
        if source.size and source.size > MAX_INPUT_BYTES:
            raise ValueError("input attachment exceeds the 200 MB safety limit")
        path = os.path.join(directory, _safe_name(source.filename, "attachment"))
        await source.save(path)
        if os.path.getsize(path) > MAX_INPUT_BYTES:
            raise ValueError("input exceeds the 200 MB safety limit")
        return path
    url = source.strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("input must be an HTTP(S) media URL or an attachment.")
    direct = any(host in parsed.netloc.lower() for host in (
        "cdn.discordapp.com", "media.discordapp.net", "attachments.discordapp.com",
    )) or bool(Path(parsed.path).suffix)
    if direct:
        try:
            return await _direct_download(url, directory)
        except Exception as direct_error:
            if yt_dlp is None:
                raise direct_error
    return await asyncio.wait_for(
        asyncio.to_thread(_ytdlp_download, url, directory), timeout=MAX_JOB_SECONDS
    )


async def _probe(path: str) -> tuple[float, bool]:
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-show_entries", "stream=codec_type", "-of", "default=nw=1", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), MAX_JOB_SECONDS)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ValueError("ffprobe timed out; the media may be corrupted.")
    if process.returncode:
        raise ValueError((stderr.decode(errors="replace") or "ffprobe rejected the input")[-500:])
    text = stdout.decode(errors="replace")
    duration = 0.0
    match = re.search(r"duration=(\d+(?:\.\d+)?)", text)
    if match:
        duration = float(match.group(1))
    return duration, "codec_type=video" in text


def _quality_args(fmt: str, quality: str, retry: bool = False) -> list[str]:
    q = "low" if retry else quality
    if fmt in {"mp4", "mov", "mkv"}:
        crf = {"low": "32", "medium": "27", "high": "21", "lossless": "0"}[q]
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", crf,
                "-c:a", "aac", "-b:a", "64k" if q == "low" else "128k"]
    if fmt == "webm":
        crf = {"low": "40", "medium": "32", "high": "24", "lossless": "4"}[q]
        return ["-c:v", "libvpx-vp9", "-crf", crf, "-b:v", "0",
                "-c:a", "libopus", "-b:a", "64k" if q == "low" else "128k"]
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", {"low": "96k", "medium": "160k",
                "high": "256k", "lossless": "320k"}[q]]
    if fmt == "ogg":
        return ["-c:a", "libvorbis", "-q:a", {"low": "2", "medium": "5",
                "high": "8", "lossless": "10"}[q]]
    if fmt == "flac":
        return ["-c:a", "flac", "-compression_level", "8"]
    return []


async def _run_ffmpeg(args: list[str], status_cb) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-y", "-progress", "pipe:1", "-nostats", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    async def consume_progress() -> None:
        last_update = 0.0
        while True:
            line = await process.stdout.readline()
            if not line:
                return
            decoded = line.decode(errors="replace").strip()
            if decoded.startswith("out_time_ms="):
                now = time.monotonic()
                if now - last_update > 1.0:
                    last_update = now
                    await status_cb(decoded.split("=", 1)[1])

    progress_task = asyncio.create_task(consume_progress())
    try:
        await asyncio.wait_for(
            asyncio.gather(progress_task, process.wait()),
            MAX_JOB_SECONDS,
        )
    except (asyncio.TimeoutError, TimeoutError):
        process.kill()
        await process.wait()
        raise ValueError("FFmpeg exceeded the 120-second processing limit.")
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    finally:
        if not progress_task.done():
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)
    if process.returncode:
        error = (await process.stderr.read()).decode(errors="replace")
        raise ValueError(f"FFmpeg failed: {error[-700:]}")


def _build_ffmpeg_args(input_path: str, output_path: str, fmt: str, quality: str,
                       start: float, duration: Optional[int], retry: bool = False) -> list[str]:
    args: list[str] = []
    if start:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", input_path]
    if duration:
        args += ["-t", str(duration)]
    if fmt == "gif":
        scale = "scale=480:-1:flags=lanczos" if retry else "scale=640:-1:flags=lanczos"
        args += ["-vf", f"fps=12,{scale},split[s0][s1];[s0]palettegen=max_colors=192[p];[s1][p]paletteuse"]
        return args + ["-an", output_path]
    if fmt in IMAGE_FORMATS:
        args += ["-frames:v", "1", "-vf", "scale=1024:-1:force_original_aspect_ratio=decrease"]
        if fmt == "jpg":
            args += ["-q:v", "8" if retry else ("3" if quality == "high" else "5")]
        return args + ["-an", output_path]
    if fmt in AUDIO_FORMATS:
        return args + ["-vn", *_quality_args(fmt, quality, retry), output_path]
    if retry:
        args += ["-vf", "scale=1280:-2:force_original_aspect_ratio=decrease"]
    return args + [*_quality_args(fmt, quality, retry), "-movflags", "+faststart", output_path]


class ConvertModal(discord.ui.Modal, title="Convert Media"):
    format_name = discord.ui.TextInput(label="Format", placeholder="mp4, gif, png, mp3…", max_length=8)
    quality = discord.ui.TextInput(label="Quality", default="medium", required=False, max_length=10)
    start_time = discord.ui.TextInput(label="Start time", placeholder="00:15 or 30s", required=False, max_length=16)
    duration = discord.ui.TextInput(label="Duration (seconds)", required=False, max_length=4)

    def __init__(self, cog: "ConvertCog", message: discord.Message):
        super().__init__()
        self.cog = cog
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        source = self.message.attachments[0] if self.message.attachments else None
        if source is None:
            match = URL_RE.search(self.message.content or "")
            source = match.group(0) if match else None
        if source is None:
            await interaction.response.send_message("❌ The message has no video attachment or URL.", ephemeral=True)
            return
        await self.cog.process(
            interaction, source, self.format_name.value, self.quality.value or "medium",
            self.start_time.value or "", self.duration.value or "",
        )


class ConvertCog(commands.Cog, name="Convert"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def process(self, ctx: commands.Context | discord.Interaction, source, fmt: str,
                      quality: str, start_raw: str, duration_raw: str) -> None:
        fmt = fmt.strip().lower().lstrip(".")
        quality = quality.strip().lower() or "medium"
        try:
            if fmt not in FORMATS:
                raise ValueError(f"unsupported format `{fmt}`")
            if quality not in QUALITIES:
                raise ValueError("quality must be low, medium, high, or lossless")
            start = _parse_start(start_raw)
            if start < 0:
                raise ValueError("start_time cannot be negative")
            duration = int(duration_raw) if duration_raw.strip() else None
            if duration is not None and not 1 <= duration <= MAX_GENERAL_DURATION:
                raise ValueError("duration must be between 1 and 600 seconds")
            if fmt in {"gif", *AUDIO_FORMATS} and duration and duration > MAX_CLIP_SECONDS:
                raise ValueError("GIF and audio conversions are capped at 30 seconds")
        except (TypeError, ValueError) as exc:
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(f"❌ {exc}", ephemeral=True)
            else:
                await ctx.send(f"❌ {exc}")
            return

        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer(ephemeral=True, thinking=True)
            status = await ctx.edit_original_response(content="📥 Downloading media…")
        else:
            status = await ctx.send("📥 Downloading media…")
        guild = ctx.guild

        async def update_status(content: str) -> None:
            await status.edit(content=content)

        try:
            with tempfile.TemporaryDirectory(prefix="ihtx_convert_") as directory:
                input_path = await _download_source(source, directory)
                await update_status("🔎 Validating media with ffprobe…")
                media_duration, has_video = await _probe(input_path)
                if start >= media_duration and media_duration > 0:
                    raise ValueError(f"start_time is beyond the media duration ({media_duration:.1f}s).")
                if fmt in VIDEO_FORMATS and not has_video:
                    raise ValueError("the selected output requires a video stream")
                output_path = os.path.join(directory, f"converted.{fmt}")

                async def progress(value: str):
                    try:
                        seconds = int(value) / 1_000_000
                        suffix = f" ({seconds:.0f}s processed)"
                    except ValueError:
                        suffix = ""
                    await update_status(f"⚙️ Transcoding via FFmpeg…{suffix}")

                await _run_ffmpeg(
                    _build_ffmpeg_args(input_path, output_path, fmt, quality, start, duration),
                    progress,
                )
                upload_limit = _guild_upload_limit(guild)
                warning = ""
                if os.path.getsize(output_path) > upload_limit:
                    warning = f"\n⚠️ Initial output exceeded {upload_limit // (1024 * 1024)} MB; compressed/downscaled."
                    await update_status("⚙️ Output is large; compressing/downscaling…")
                    await _run_ffmpeg(
                        _build_ffmpeg_args(input_path, output_path, fmt, quality, start, duration, True),
                        progress,
                    )
                output_size = os.path.getsize(output_path)
                if output_size > upload_limit:
                    raise ValueError(
                        f"output is still {output_size / 1024 / 1024:.1f} MB, above the "
                        f"{upload_limit // (1024 * 1024)} MB Discord limit"
                    )
                await update_status("⬆️ Uploading converted media…")
                await status.edit(
                    content=f"✅ Converted to `{fmt}` · {output_size / 1024 / 1024:.2f} MB{warning}",
                    attachments=[discord.File(output_path, filename=f"converted.{fmt}")],
                )
        except Exception as exc:
            try:
                await update_status(f"❌ Conversion failed: {str(exc)[:1600]}")
            except Exception:
                pass

    @commands.hybrid_command(
        name="convert",
        description="Convert media to video, image, or audio format.",
    )
    @app_commands.describe(
        input="Media URL; with !convert, omit this when attaching a file",
        format="Target extension",
        quality="Quality preset; defaults to medium",
        start_time="Start point such as 00:15 or 30s",
        duration="Maximum clip duration in seconds",
        attachment="Optional Discord attachment; takes precedence over input",
    )
    @app_commands.choices(format=[
        app_commands.Choice(name=f"Video: {v}", value=v) for v in ("mp4", "webm", "mov", "mkv", "gif")
    ] + [
        app_commands.Choice(name=f"Image: {v}", value=v) for v in ("png", "jpg", "webp")
    ] + [
        app_commands.Choice(name=f"Audio: {v}", value=v) for v in ("mp3", "wav", "ogg", "flac")
    ], quality=[
        app_commands.Choice(name=q.title(), value=q) for q in ("low", "medium", "high", "lossless")
    ])
    async def convert(
        self, ctx: commands.Context, input: str | None = None,
        format: str = "mp4",
        quality: str = "medium", start_time: str | None = None,
        duration: int | None = None, attachment: discord.Attachment | None = None,
    ) -> None:
        source = attachment or input
        if source is None and ctx.message.attachments:
            source = ctx.message.attachments[0]
        if source is None:
            await ctx.reply("❌ Attach a media file or provide an HTTP(S) URL.")
            return
        await self.process(ctx, source, format,
                           quality or "medium", start_time or "",
                           str(duration) if duration is not None else "")

@app_commands.context_menu(name="Convert Media")
async def convert_media_context(
    interaction: discord.Interaction, message: discord.Message
) -> None:
    """Message context-menu entry point: Apps -> Convert Media."""
    cog = interaction.client.get_cog("Convert")
    if not isinstance(cog, ConvertCog):
        await interaction.response.send_message(
            "❌ The conversion service is not ready.", ephemeral=True
        )
        return
    await interaction.response.send_modal(ConvertModal(cog, message))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConvertCog(bot))
    bot.tree.add_command(convert_media_context)