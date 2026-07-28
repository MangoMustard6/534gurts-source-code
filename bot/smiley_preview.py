"""
Smiley face reference image + effect preview builder for th/bothelp.

Generates bot/smiley_ref.png at startup (PIL), then generates PNG/GIF previews
for each listed effect by running FFmpeg on the smiley image.  Previews are
uploaded to Catbox and their URLs cached in bot/preview_cache.json so they
survive restarts without re-generating.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Awaitable, Callable, Optional

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

SMILEY_PATH  = Path(__file__).parent / "smiley_ref.png"
CACHE_PATH   = Path(__file__).parent / "preview_cache.json"
W = H = 320


# ─────────────────────────────────────────────────────────────────────────────
# Smiley face
# ─────────────────────────────────────────────────────────────────────────────

def generate_smiley() -> bool:
    """Draw and save bot/smiley_ref.png.  Returns True on success."""
    if not _PIL:
        return False

    img  = Image.new("RGB", (W, H), (40, 40, 55))          # dark bg
    draw = ImageDraw.Draw(img)

    # ── face ──────────────────────────────────────────────────────────────────
    # shadow
    draw.ellipse([16, 20, W - 16, H - 10], fill=(170, 130, 8))
    # main face
    draw.ellipse([10, 10, W - 10, H - 18], fill=(255, 220, 48),
                 outline=(38, 28, 0), width=5)

    # ── left eye ──────────────────────────────────────────────────────────────
    draw.ellipse([68, 84, 132, 148], fill=(255, 255, 255), outline=(38, 28, 0), width=3)
    draw.ellipse([86, 102, 116, 132], fill=(28, 18, 8))          # pupil
    draw.ellipse([90, 106, 100, 116], fill=(255, 255, 255))       # highlight

    # ── right eye ─────────────────────────────────────────────────────────────
    draw.ellipse([188, 84, 252, 148], fill=(255, 255, 255), outline=(38, 28, 0), width=3)
    draw.ellipse([206, 102, 236, 132], fill=(28, 18, 8))
    draw.ellipse([210, 106, 220, 116], fill=(255, 255, 255))

    # ── eyebrows ──────────────────────────────────────────────────────────────
    draw.line([(66, 73), (134, 60)], fill=(38, 28, 0), width=6)
    draw.line([(186, 60), (254, 73)], fill=(38, 28, 0), width=6)

    # ── nose (small triangle) ─────────────────────────────────────────────────
    draw.polygon([(160, 158), (148, 190), (172, 190)],
                 fill=(208, 162, 28), outline=(38, 28, 0))

    # ── mouth (smile with teeth) ──────────────────────────────────────────────
    # white teeth fill
    draw.pieslice([68, 172, 252, 280], start=12, end=168, fill=(255, 255, 255))
    # lip outline
    draw.arc([68, 172, 252, 280], start=10, end=170, fill=(38, 28, 0), width=7)

    # ── cheeks (semi-transparent pink overlay) ────────────────────────────────
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od      = ImageDraw.Draw(overlay)
    od.ellipse([12, 188,  98, 248], fill=(255, 88, 88, 72))
    od.ellipse([222, 188, 308, 248], fill=(255, 88, 88, 72))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")

    img.save(str(SMILEY_PATH))
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Effect preview definitions
# key → (vf_filter_string | None, is_animated, duration_seconds)
#   vf=None  →  no filter, just copy the smiley as the preview
# ─────────────────────────────────────────────────────────────────────────────

EFFECT_PREVIEWS: dict[str, tuple[str | None, bool, float]] = {
    # reference (no filter)
    "smiley":     (None,                                                                   False, 0),

    # ── basic transforms ──────────────────────────────────────────────────────
    "negate":     ("negate",                                                               False, 0),
    "hflip":      ("hflip",                                                                False, 0),
    "vflip":      ("vflip",                                                                False, 0),
    "grayscale":  ("colorchannelmixer=.299:.587:.114:0:.299:.587:.114:0:.299:.587:.114",   False, 0),
    "sepia":      ("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",   False, 0),
    "swapuv":     ("swapuv",                                                               False, 0),

    # ── colour ────────────────────────────────────────────────────────────────
    "huehsv":     ("hue=h=130:s=2.2",                                                     False, 0),
    "ccshue":     ("hue=h=60:s=2.8",                                                      False, 0),
    "brightness": ("eq=brightness=0.35:contrast=1.2",                                     False, 0),
    "contrast":   ("eq=contrast=2.5",                                                     False, 0),
    "saturation": ("eq=saturation=4.0",                                                   False, 0),
    "invlum":     ("lutyuv=y=negval",                                                     False, 0),
    "labadjust":  ("hue=h=180:s=1",                                                      False, 0),
    "folkvalley": ("eq=brightness=0.15:contrast=1.2:saturation=1.8",                     False, 0),

    # ── geometry ──────────────────────────────────────────────────────────────
    "zoom":       ("crop=iw*0.5:ih*0.5:(iw-iw*0.5)/2:(ih-ih*0.5)/2,scale=320:320",      False, 0),
    "rotate":     ("rotate=PI/5:ow=hypot(iw\\,ih):oh=ow:fillcolor=0x28283a,"
                   "crop=320:320:(ow-320)/2:(oh-320)/2,scale=320:320",                   False, 0),
    "mirror":     ("hflip",                                                               False, 0),
    "tile":       ("tile=2x2,scale=320:320",                                              False, 0),
    "swirl":      ("rotate=0.45:ow=hypot(iw\\,ih):oh=ow:fillcolor=0x28283a,"
                   "crop=320:320:(ow-320)/2:(oh-320)/2,scale=320:320",                   False, 0),

    # ── animated ──────────────────────────────────────────────────────────────
    "wave": (
        "geq="
        "lum='p(X+25*sin(Y/20+2*PI*T)\\,Y)':"
        "cb='p(X+25*sin(Y/20+2*PI*T)\\,Y)':"
        "cr='p(X+25*sin(Y/20+2*PI*T)\\,Y)'",
        True, 2.5,
    ),
    "shake": (
        "crop=iw-20:ih-20:10+8*sin(t*25):10+8*cos(t*21),scale=320:320",
        True, 2.0,
    ),
    "ripple": (
        "geq="
        "lum='p(X+10*sin(T*5+hypot(X-W/2\\,Y-H/2)/30)\\,Y)':"
        "cb='p(X+10*sin(T*5+hypot(X-W/2\\,Y-H/2)/30)\\,Y)':"
        "cr='p(X+10*sin(T*5+hypot(X-W/2\\,Y-H/2)/30)\\,Y)'",
        True, 2.5,
    ),
    "tvsim": (
        "geq="
        "lum='p(X+6*sin(Y/4+T*18)\\,Y)':"
        "cb='p(X+6*sin(Y/4+T*18)\\,Y)':"
        "cr='p(X+6*sin(Y/4+T*18)\\,Y)'",
        True, 2.5,
    ),
    "pan":    ("scroll=v=0.25:h=0",                                                       True, 2.0),
    "scroll": ("scroll=h=0.2:v=0",                                                        True, 2.0),
}


# ─────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_cache() -> dict[str, str]:
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text())
    except Exception:
        pass
    return {}


def save_cache(cache: dict[str, str]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass


def get_preview_url(key: str, cache: dict[str, str]) -> str | None:
    return cache.get(key)


# ─────────────────────────────────────────────────────────────────────────────
# Preview generation
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 60) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout).returncode == 0
    except Exception:
        return False


def _static_preview(vf: str | None, out: str) -> bool:
    """Generate a single-frame PNG preview."""
    if not SMILEY_PATH.exists():
        return False
    src = str(SMILEY_PATH)
    if vf is None:
        import shutil
        shutil.copy(src, out)
        return True
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", src,
        "-vf", f"{vf},scale=320:320",
        "-frames:v", "1", out,
    ]
    return _run(cmd)


def _gif_preview(vf: str, dur: float, out: str) -> bool:
    """Two-pass GIF generation: palettegen → paletteuse."""
    if not SMILEY_PATH.exists():
        return False
    src  = str(SMILEY_PATH)
    dur_s = str(dur)
    with tempfile.TemporaryDirectory() as tmp:
        palette = os.path.join(tmp, "palette.png")

        # Pass 1 — generate palette from all frames
        p1vf = f"{vf},fps=10,scale=320:320,palettegen=stats_mode=full"
        ok = _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-t", dur_s, "-i", src,
            "-vf", p1vf, palette,
        ], timeout=60)
        if not ok or not os.path.exists(palette):
            return False

        # Pass 2 — render GIF with palette
        p2fc = f"[0:v]{vf},fps=10,scale=320:320[x];[x][1:v]paletteuse=dither=sierra2_4a"
        ok = _run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-t", dur_s, "-i", src,
            "-i", palette,
            "-filter_complex", p2fc,
            "-loop", "0", out,
        ], timeout=90)
        return ok and os.path.exists(out)


async def build_preview(
    key: str,
    upload_fn: Callable[[str], Awaitable[Optional[str]]],
) -> str | None:
    """Generate the preview for *key*, upload it, return the catbox URL or None."""
    spec = EFFECT_PREVIEWS.get(key)
    if spec is None:
        return None
    vf, animated, dur = spec
    ext = "gif" if animated else "png"

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, f"preview_{key}.{ext}")
        loop = asyncio.get_event_loop()
        if animated and vf:
            ok = await loop.run_in_executor(None, lambda: _gif_preview(vf, dur, out))
        else:
            ok = await loop.run_in_executor(None, lambda: _static_preview(vf, out))
        if ok and os.path.exists(out):
            return await upload_fn(out)
    return None


async def ensure_previews(
    upload_fn: Callable[[str], Awaitable[Optional[str]]],
    cache: dict[str, str],
) -> dict[str, str]:
    """Generate any missing previews and return the updated cache."""
    for key in EFFECT_PREVIEWS:
        if key not in cache:
            print(f"[previews] Generating preview: {key} …", flush=True)
            url = await build_preview(key, upload_fn)
            if url:
                cache[key] = url
                save_cache(cache)
                print(f"[previews]   ✓ {key} → {url}", flush=True)
            else:
                print(f"[previews]   ✗ {key} failed", flush=True)
    return cache
