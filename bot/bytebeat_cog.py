"""
Bytebeat cog — th/bytebeat <mode> <samplerate> <duration> <expression>

Generates PCM audio from a mathematical expression t → sample,
renders it as a waveform MP4 video via FFmpeg, and posts to Discord.
Mirrors the behaviour of bytebeat.ts (TS bot).
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import os
import shutil
import struct
import subprocess
import tempfile

import discord
from discord.ext import commands

log = logging.getLogger(__name__)

# ── Limits (match bytebeat.ts) ────────────────────────────────────────────────

DISCORD_MAX_BYTES = 8 * 1024 * 1024
MAX_DURATION      = 60
MIN_DURATION      = 0.1
MAX_SAMPLERATE    = 96000
MIN_SAMPLERATE    = 1000

# ── Mode aliases ──────────────────────────────────────────────────────────────

MODE_ALIASES: dict[str, str] = {
    "u8": "u8", "mono": "u8", "classic": "u8", "unsigned": "u8",
    "s8": "s8", "signed": "s8",
    "float": "float", "floatbeat": "float", "f32": "float",
}

# ── Math sandbox (mirrors bytebeat.ts BYTEBEAT_SANDBOX) ──────────────────────

def _gcd(a, b) -> int:
    a, b = abs(int(round(a))), abs(int(round(b)))
    while b:
        a, b = b, a % b
    return a


def _sign(x) -> float:
    if x > 0:  return  1.0
    if x < 0:  return -1.0
    return 0.0


def _cbrt(x) -> float:
    if x == 0:
        return 0.0
    return math.copysign(abs(x) ** (1 / 3), x)


_SAFE_GLOBALS: dict = {
    "__builtins__": {},
    # arithmetic
    "abs": abs, "round": round, "min": min, "max": max,
    "int": int, "float": float,
    # math
    "sqrt": math.sqrt,   "cbrt": _cbrt,
    "pow":  pow,          "exp":  math.exp,   "sign": _sign,
    "floor": math.floor, "ceil": math.ceil,
    "log":  math.log10,  "log2": math.log2,  "ln": math.log,
    "sin":  math.sin,    "cos":  math.cos,   "tan": math.tan,
    "asin": math.asin,   "acos": math.acos,  "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,   "cosh": math.cosh,  "tanh": math.tanh,
    "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
    "gcd": _gcd,
    "mod": lambda a, b: a % b,
    # constants
    "e": math.e, "pi": math.pi, "PI": math.pi,
    "tau": math.tau, "phi": (1 + math.sqrt(5)) / 2,
    # type helpers
    "isnan": math.isnan, "isfinite": math.isfinite,
    "parseInt": int, "parseFloat": float,
}


def _prep_math(expr: str) -> str:
    """Replace ^ with ** so users can write 2^8 (mirrors prepMath in bytebeat.ts)."""
    return expr.replace("^", "**")


def _build_evaluator(code: str):
    """Compile expression to a code object. Raises SyntaxError / ValueError."""
    prepared = _prep_math(code.strip())
    if not prepared:
        raise ValueError("Empty expression.")
    compiled = compile(prepared, "<bytebeat>", "eval")
    # Test at t=0 to catch obvious runtime errors early
    ns = dict(_SAFE_GLOBALS)
    ns["t"] = 0
    eval(compiled, ns)   # noqa: S307 — restricted namespace
    return compiled


# ── PCM generation ────────────────────────────────────────────────────────────

def _generate_pcm(compiled, mode: str, sample_rate: int, duration: float) -> bytes:
    """Return raw PCM bytes. Uses numpy vectorisation when available."""
    num_samples = int(sample_rate * duration)

    # ── Fast path: numpy vectorised eval ────────────────────────────────────
    try:
        import numpy as np

        np_ns = dict(_SAFE_GLOBALS)
        np_ns.update({
            "abs":   np.abs,      "sqrt":  np.sqrt,
            "cbrt":  lambda x: np.cbrt(x) if hasattr(np, "cbrt") else np.sign(x) * np.abs(x) ** (1 / 3),
            "pow":   np.power,    "exp":   np.exp,
            "sign":  np.sign,
            "floor": np.floor,    "ceil":  np.ceil,    "round": np.round,
            "min":   np.minimum,  "max":   np.maximum,
            "log":   np.log10,    "log2":  np.log2,    "ln": np.log,
            "sin":   np.sin,      "cos":   np.cos,     "tan": np.tan,
            "asin":  np.arcsin,   "acos":  np.arccos,  "atan": np.arctan,
            "atan2": np.arctan2,
            "sinh":  np.sinh,     "cosh":  np.cosh,    "tanh": np.tanh,
            "asinh": np.arcsinh,  "acosh": np.arccosh, "atanh": np.arctanh,
            "isnan": np.isnan,    "isfinite": np.isfinite,
        })

        if mode == "float":
            t_arr = np.arange(num_samples, dtype=np.float64)
            np_ns["t"] = t_arr
            result = np.asarray(eval(compiled, np_ns), dtype=np.float32)  # noqa: S307
            return np.clip(result, -1.0, 1.0).tobytes()
        else:
            t_arr = np.arange(num_samples, dtype=np.int64)
            np_ns["t"] = t_arr
            result = np.asarray(eval(compiled, np_ns), dtype=np.int64)    # noqa: S307
            if mode == "u8":
                return (result & 0xFF).astype(np.uint8).tobytes()
            else:  # s8
                return (result & 0xFF).astype(np.uint8).view(np.int8).tobytes()

    except Exception:
        pass  # fall through to scalar path

    # ── Slow path: scalar Python loop ────────────────────────────────────────
    ns = dict(_SAFE_GLOBALS)

    if mode == "float":
        buf = bytearray(num_samples * 4)
        for i in range(num_samples):
            ns["t"] = i
            try:
                v = float(eval(compiled, ns))   # noqa: S307
                v = max(-1.0, min(1.0, v))
            except Exception:
                v = 0.0
            struct.pack_into("<f", buf, i * 4, v)
        return bytes(buf)
    else:
        buf = bytearray(num_samples)
        for i in range(num_samples):
            ns["t"] = i
            try:
                raw = int(eval(compiled, ns))   # noqa: S307
            except Exception:
                raw = 0
            buf[i] = raw & 0xFF
        return bytes(buf)


# ── FFmpeg waveform video ─────────────────────────────────────────────────────

def _pcm_to_waveform_video(
    pcm_bytes: bytes,
    mode: str,
    sample_rate: int,
    tmp: str,
) -> bytes:
    """Render raw PCM to a 640×360 waveform MP4 using FFmpeg (mirrors bytebeat.ts)."""
    fmt_map = {"float": "f32le", "u8": "u8", "s8": "s8"}
    ffmpeg_fmt = fmt_map[mode]

    raw_path = os.path.join(tmp, "input.raw")
    out_path = os.path.join(tmp, "bytebeat.mkv")

    with open(raw_path, "wb") as f:
        f.write(pcm_bytes)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", ffmpeg_fmt,
            "-ar", str(sample_rate),
            "-ac", "1",
            "-i", raw_path,
            "-filter_complex",
            "[0:a]showwaves=s=640x360:mode=line:colors=lime|white:rate=60[v]",
            "-map", "[v]",
            "-map", "0:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "flac",
            "-movflags", "+faststart",
            out_path,
        ],
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")[-800:]
        raise RuntimeError(f"FFmpeg exited {result.returncode}: {err}")

    with open(out_path, "rb") as f:
        return f.read()


# ── Cog ───────────────────────────────────────────────────────────────────────

class BytebeatCog(commands.Cog, name="Bytebeat"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="bytebeat", aliases=["bb"])
    async def bytebeat(self, ctx: commands.Context, *, args: str = ""):
        """
        Generate a bytebeat waveform video.
        Usage: th/bytebeat <mode> <samplerate> <duration> <expression>
        """
        if not args.strip():
            await ctx.reply(
                "❌ Usage: `th/bytebeat <mode> <samplerate> <duration> <expression>`\n"
                "**Modes:** `u8` (classic unsigned) · `s8` (signed) · `float` (floatbeat, −1..1)\n"
                "**Examples:**\n"
                "• `th/bytebeat u8 8000 10 t*(t>>5|t>>8)`\n"
                "• `th/bytebeat float 44100 5 sin(t/10)*sin(t/700)`\n"
                "`t` = sample index · supports sin/cos/floor/^/&/|/>>/<<\n"
                f"Max duration: **{MAX_DURATION}s** · Sample rate: **{MIN_SAMPLERATE}–{MAX_SAMPLERATE} Hz**"
            )
            return

        parts = args.split(None, 3)
        if len(parts) < 4:
            await ctx.reply(
                "❌ Not enough arguments.\n"
                "Usage: `th/bytebeat <mode> <samplerate> <duration> <expression>`\n"
                "Example: `th/bytebeat u8 8000 10 t*(t>>5|t>>8)`"
            )
            return

        raw_mode, raw_sr, raw_dur, code = parts

        mode = MODE_ALIASES.get(raw_mode.lower())
        if not mode:
            await ctx.reply(
                f"❌ Unknown mode `{raw_mode}`.\n"
                "Valid: `u8` / `mono` / `classic` · `s8` / `signed` · `float` / `floatbeat`"
            )
            return

        try:
            sample_rate = round(float(raw_sr))
        except ValueError:
            sample_rate = 0
        if not (MIN_SAMPLERATE <= sample_rate <= MAX_SAMPLERATE):
            await ctx.reply(
                f"❌ Sample rate must be between **{MIN_SAMPLERATE}** and **{MAX_SAMPLERATE}** Hz."
            )
            return

        try:
            duration = float(raw_dur)
        except ValueError:
            duration = -1.0
        if not (MIN_DURATION <= duration <= MAX_DURATION):
            await ctx.reply(
                f"❌ Duration must be between **{MIN_DURATION}s** and **{MAX_DURATION}s**."
            )
            return

        # Compile & validate expression
        try:
            compiled = _build_evaluator(code)
        except Exception as exc:
            await ctx.reply(f"❌ Invalid expression: `{str(exc)[:200]}`")
            return

        num_samples = int(sample_rate * duration)
        status_msg = await ctx.reply(
            f"⏳ Generating bytebeat — mode: `{mode}` · {sample_rate:,} Hz · "
            f"{duration}s · {num_samples:,} samples…"
        )

        loop = asyncio.get_event_loop()
        tmp = tempfile.mkdtemp(prefix="bytebeat-")
        try:
            pcm = await loop.run_in_executor(
                None, _generate_pcm, compiled, mode, sample_rate, duration
            )
            video_bytes = await loop.run_in_executor(
                None, _pcm_to_waveform_video, pcm, mode, sample_rate, tmp
            )

            snippet = (code[:80] + "…") if len(code) > 80 else code
            label = (
                f"🎵 **Bytebeat** — `{snippet}`\n"
                f"Mode: `{mode}` · {sample_rate:,} Hz · {duration}s"
            )

            if len(video_bytes) <= DISCORD_MAX_BYTES:
                await status_msg.delete()
                await ctx.reply(
                    content=label,
                    file=discord.File(io.BytesIO(video_bytes), filename="bytebeat.mkv"),
                )
            else:
                await status_msg.edit(
                    content="📦 File too large for Discord — uploading to catbox.moe…"
                )
                # Write to tmp file so _upload_to_catbox can read it
                video_path = os.path.join(tmp, "bytebeat.mkv")
                with open(video_path, "wb") as f:
                    f.write(video_bytes)
                from bot.ihtx_bot import _upload_to_catbox
                catbox_url = await _upload_to_catbox(video_path)
                await status_msg.delete()
                url_str = catbox_url or "(upload failed)"
                await ctx.reply(f"{label}\n📦 Too large for Discord → {url_str}")

        except Exception as exc:
            log.error("th/bytebeat failed: %s", exc, exc_info=True)
            try:
                await status_msg.edit(content=f"❌ Bytebeat failed: `{str(exc)[:300]}`")
            except Exception:
                pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BytebeatCog(bot))
