"""
mediascript: engine — FFmpeg-based audio/video/GIF processing.

Usage inside a tag:
    {mediascript:
        load_attachment
        scale 640x360
        fps 24
        trim 0 10
        speed 1.5
        volume 0.8
        output mp4
    }

Available operations:
    load_attachment          — first attachment from the invoking message
    load URL                 — download media from a URL
    scale WxH                — scale video (e.g. 640x360)
    fps N                    — change framerate (1–60)
    trim START END           — trim to time range in seconds
    speed FACTOR             — playback speed (0.25–4.0)
    volume LEVEL             — audio volume (0.0–2.0)
    strip_audio              — remove audio track
    reverse                  — reverse video + audio
    grayscale                — desaturate video
    rotate DEGREES           — rotate video
    loop N                   — loop input N times (1–10)
    fade_in SECONDS          — fade in at start
    fade_out SECONDS         — fade out at end
    gif                      — two-pass palette GIF conversion
    output FORMAT            — mp4 | gif | mp3 | webm | wav  (default: mp4)
"""

import asyncio
import io
import os
import re
import shutil
import tempfile
from pathlib import Path

import aiohttp
import discord

from . import BaseEngine, EngineResult

_ALLOWED_OPS = frozenset({
    "load_attachment", "load", "scale", "fps", "trim", "speed", "volume",
    "strip_audio", "reverse", "grayscale", "rotate", "loop", "fade_in",
    "fade_out", "gif", "output",
})
_ALLOWED_FORMATS = frozenset({"mp4", "gif", "mp3", "webm", "wav", "mov"})
_ALLOWED_EXTS = frozenset({
    "mp4", "mov", "webm", "mkv", "avi",
    "mp3", "wav", "ogg", "m4a", "flac",
    "gif",
})
_MAX_INPUT = 50 * 1024 * 1024   # 50 MB
_MAX_OUTPUT = 8 * 1024 * 1024   # 8 MB Discord limit
_BLOCKED_HOSTS = ("localhost", "127.", "0.", "192.168.", "10.", "metadata.google")


class MediaScriptEngine(BaseEngine):
    name = "mediascript"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        lines = [
            ln.strip()
            for ln in content.strip().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if not lines:
            return EngineResult(error="mediascript: no commands")

        tmpdir = tempfile.mkdtemp(prefix="mediascript_")
        try:
            return await self._run(lines, ctx, tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _run(self, lines: list, ctx, tmpdir: str) -> EngineResult:
        input_path: str | None = None
        output_format: str | None = None
        vf_filters: list = []
        af_filters: list = []
        input_args: list = []
        output_args: list = []

        for line in lines:
            parts = line.split(None, 1)
            op = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if op not in _ALLOWED_OPS:
                return EngineResult(error=f"mediascript: unknown operation '{op}'")

            if op == "load_attachment":
                if not ctx.message.attachments:
                    return EngineResult(error="mediascript: no attachment in message")
                att = ctx.message.attachments[0]
                suffix = Path(att.filename).suffix or ".mp4"
                input_path = os.path.join(tmpdir, "input" + suffix)
                await att.save(input_path)

            elif op == "load":
                if not arg.startswith(("http://", "https://")):
                    return EngineResult(error="mediascript: load only accepts http/https URLs")
                for blocked in _BLOCKED_HOSTS:
                    if blocked in arg.lower():
                        return EngineResult(error="mediascript: URL is not allowed")
                ext = arg.split("?")[0].rsplit(".", 1)[-1].lower()
                if ext not in _ALLOWED_EXTS:
                    ext = "mp4"
                input_path = os.path.join(tmpdir, f"input.{ext}")
                try:
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with aiohttp.ClientSession(timeout=timeout) as s:
                        async with s.get(arg) as r:
                            if r.status != 200:
                                return EngineResult(error=f"mediascript: HTTP {r.status}")
                            data = await r.read()
                            if len(data) > _MAX_INPUT:
                                return EngineResult(error="mediascript: input too large (max 50 MB)")
                            Path(input_path).write_bytes(data)
                except Exception as exc:
                    return EngineResult(error=f"mediascript: load failed — {exc}")

            elif op == "scale":
                if not re.fullmatch(r"\d+x\d+", arg):
                    return EngineResult(error="mediascript: scale format is WxH (e.g. 640x360)")
                w, h = arg.split("x")
                vf_filters.append(f"scale={w}:{h}")

            elif op == "fps":
                try:
                    fps = max(1, min(float(arg), 60))
                    vf_filters.append(f"fps={fps}")
                except ValueError:
                    return EngineResult(error="mediascript: fps requires a number")

            elif op == "trim":
                nums = arg.split()
                if len(nums) < 2:
                    return EngineResult(error="mediascript: trim requires START END (seconds)")
                try:
                    start = max(0.0, float(nums[0]))
                    end = float(nums[1])
                    if end <= start:
                        return EngineResult(error="mediascript: trim END must be after START")
                    if end - start > 300:
                        return EngineResult(error="mediascript: trim max duration is 300 s")
                    input_args += ["-ss", str(start), "-to", str(end)]
                except ValueError:
                    return EngineResult(error="mediascript: trim requires numeric values")

            elif op == "speed":
                try:
                    factor = max(0.25, min(float(arg), 4.0))
                    vf_filters.append(f"setpts={1/factor:.6f}*PTS")
                    if factor <= 0.5:
                        af_filters.append(f"atempo=0.5,atempo={factor * 2:.6f}")
                    elif factor >= 2.0:
                        af_filters.append(f"atempo=2.0,atempo={factor / 2:.6f}")
                    else:
                        af_filters.append(f"atempo={factor:.6f}")
                except ValueError:
                    return EngineResult(error="mediascript: speed requires a number (0.25–4.0)")

            elif op == "volume":
                try:
                    vol = max(0.0, min(float(arg), 2.0))
                    af_filters.append(f"volume={vol}")
                except ValueError:
                    return EngineResult(error="mediascript: volume requires a number (0.0–2.0)")

            elif op == "strip_audio":
                output_args += ["-an"]

            elif op == "reverse":
                vf_filters.append("reverse")
                af_filters.append("areverse")

            elif op == "grayscale":
                vf_filters.append("hue=s=0")

            elif op == "rotate":
                try:
                    deg = float(arg) % 360
                    vf_filters.append(f"rotate={deg}*PI/180")
                except ValueError:
                    return EngineResult(error="mediascript: rotate requires degrees")

            elif op == "loop":
                try:
                    n = max(1, min(int(arg), 10))
                    input_args = ["-stream_loop", str(n - 1)] + input_args
                except ValueError:
                    return EngineResult(error="mediascript: loop requires an integer (1–10)")

            elif op == "fade_in":
                try:
                    dur = max(0.1, min(float(arg), 10.0))
                    vf_filters.append(f"fade=in:0:d={dur}")
                    af_filters.append(f"afade=in:0:d={dur}")
                except ValueError:
                    return EngineResult(error="mediascript: fade_in requires seconds")

            elif op == "fade_out":
                try:
                    dur = max(0.1, min(float(arg), 10.0))
                    vf_filters.append(f"fade=out:st=9999:d={dur}")
                except ValueError:
                    return EngineResult(error="mediascript: fade_out requires seconds")

            elif op == "gif":
                output_format = "gif"

            elif op == "output":
                fmt = arg.lower().lstrip(".")
                if fmt not in _ALLOWED_FORMATS:
                    return EngineResult(
                        error="mediascript: output must be mp4/gif/mp3/webm/wav"
                    )
                output_format = fmt

        if input_path is None:
            return EngineResult(error="mediascript: no input — use 'load_attachment' or 'load URL'")

        if output_format is None:
            ext = Path(input_path).suffix.lower().lstrip(".")
            output_format = ext if ext in _ALLOWED_FORMATS else "mp4"

        output_path = os.path.join(tmpdir, f"output.{output_format}")

        try:
            if output_format == "gif":
                result = await self._render_gif(
                    input_path, output_path, vf_filters, input_args, tmpdir
                )
            else:
                result = await self._render_ffmpeg(
                    input_path, output_path, output_format,
                    vf_filters, af_filters, input_args, output_args
                )
        except Exception as exc:
            return EngineResult(error=f"mediascript: unexpected error — {exc}")

        if result:
            return result

        out_bytes = Path(output_path).read_bytes()
        if len(out_bytes) > _MAX_OUTPUT:
            return EngineResult(
                error=f"mediascript: output too large for Discord (max 8 MB)"
            )

        return EngineResult(
            files=[discord.File(io.BytesIO(out_bytes), filename=f"output.{output_format}")]
        )

    async def _render_ffmpeg(
        self,
        input_path: str,
        output_path: str,
        fmt: str,
        vf: list,
        af: list,
        in_args: list,
        out_args: list,
    ) -> EngineResult | None:
        cmd = ["ffmpeg", "-y", "-loglevel", "error"] + in_args + ["-i", input_path]

        is_audio_only = fmt in ("mp3", "wav")

        if vf and not is_audio_only:
            cmd += ["-vf", ",".join(vf)]
        if af and fmt != "gif":
            cmd += ["-af", ",".join(af)]

        cmd += out_args

        if fmt == "mp4":
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "28",
                    "-c:a", "aac", "-movflags", "+faststart"]
        elif fmt == "webm":
            cmd += ["-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "0"]
        elif fmt == "mp3":
            cmd += ["-q:a", "2"]
        elif fmt == "mov":
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "28"]

        cmd.append(output_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        except asyncio.TimeoutError:
            proc.kill()
            return EngineResult(error="mediascript: timed out (120 s limit)")

        if proc.returncode != 0:
            msg = stderr.decode(errors="replace")[:300].strip()
            return EngineResult(error=f"mediascript: FFmpeg error — {msg}")

        return None

    async def _render_gif(
        self,
        input_path: str,
        output_path: str,
        vf: list,
        in_args: list,
        tmpdir: str,
    ) -> EngineResult | None:
        palette_path = os.path.join(tmpdir, "palette.png")

        vf_no_gif = [f for f in vf if "palettegen" not in f and "paletteuse" not in f]
        palette_vf = ",".join(vf_no_gif + ["palettegen"]) if vf_no_gif else "palettegen"

        p1 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-loglevel", "error",
            *in_args, "-i", input_path,
            "-vf", palette_vf, palette_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(p1.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            p1.kill()
            return EngineResult(error="mediascript: GIF palette timed out")

        if p1.returncode != 0:
            msg = err.decode(errors="replace")[:200].strip()
            return EngineResult(error=f"mediascript: GIF palette error — {msg}")

        use_vf = ",".join(vf_no_gif + ["paletteuse"]) if vf_no_gif else "paletteuse"
        p2 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-loglevel", "error",
            *in_args, "-i", input_path, "-i", palette_path,
            "-lavfi", use_vf, output_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(p2.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            p2.kill()
            return EngineResult(error="mediascript: GIF render timed out")

        if p2.returncode != 0:
            msg = err.decode(errors="replace")[:200].strip()
            return EngineResult(error=f"mediascript: GIF error — {msg}")

        return None
