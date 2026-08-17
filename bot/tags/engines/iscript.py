"""
iscript: engine — ImageMagick-powered image processing with named image variables.

Each operation takes a variable name as its first argument (default: "f").
Use `load` or `load_attachment` to create variables, then chain operations.

Usage:
    {iscript:
        load {iv} f
        hueshifthsv f 180
    }
    {iscript:
        load_attachment img
        blur img 5
        caption img nice picture
        output img jpg
    }

Old positional syntax still works (no var name needed):
    {iscript:
        load_attachment
        blur 5
        grayscale
        output png
    }

Operations:
    load URL [var]               load image from URL (default var: f)
    load_attachment [var]        load from message attachment (default var: f)
    output [var] FORMAT          set output var + format: jpg png gif webp

  Color:
    hueshifthsv var degrees      hue rotation 0–360 (HSV)
    hueshift var degrees         alias for hueshifthsv
    grayscale var                desaturate
    negate / invert var          invert colours
    sepia var                    sepia tone
    brightness var N             brightness -100 to 100
    contrast var N               contrast -100 to 100
    saturate var N               saturation multiplier 0.0–5.0

  Filters:
    blur var radius              Gaussian blur 0–50
    sharpen var amount           sharpening 0–50
    pixelate var size            pixelate 2–200 px blocks
    jpeg var [quality]           JPEG compress at quality 1–95 (default 20)
    deepfry var                  extreme JPEG + over-saturation + sharpening
    edges var                    edge detection
    emboss var                   emboss / relief
    charcoal var [radius]        charcoal sketch
    oil var [radius]             oil-paint effect
    solarize var [threshold%]    solarise (default 50%)
    posterize var [levels]       reduce colours to 2–8 levels
    vignette var                 dark vignette border

  Geometry:
    rotate var degrees           rotate
    resize var WxH               exact resize (e.g. 640x480)
    thumbnail var WxH            resize keeping aspect ratio
    flip var                     flip vertically
    flop var                     flip horizontally (mirror left-right)
    mirror var [left|right|top|bottom]  mirror half of the image
    spin var [frames] [fps]      spinning GIF (default 16 frames, 12 fps)

  Text:
    caption var text             text strip below image
    impact var top [| bottom]    meme impact font; | splits top and bottom text
"""

from __future__ import annotations

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

# ── Constants ─────────────────────────────────────────────────────────────────

_ALLOWED_FORMATS = frozenset({"jpg", "jpeg", "png", "gif", "webp"})
_MAX_BYTES = 8 * 1024 * 1024
_DEFAULT_VAR = "f"
_VAR_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_BLOCKED_HOSTS = ("localhost", "127.", "0.0.0.0", "192.168.", "10.", "metadata.google")

_ALLOWED_OPS = frozenset({
    "load", "load_attachment", "output",
    "hueshifthsv", "hueshift", "grayscale", "negate", "invert",
    "sepia", "brightness", "contrast", "saturate",
    "blur", "sharpen", "pixelate", "jpeg", "deepfry",
    "edges", "emboss", "charcoal", "oil", "solarize", "posterize", "vignette",
    "rotate", "resize", "thumbnail", "flip", "flop", "mirror", "spin",
    "caption", "impact",
})


# ── Small helpers ─────────────────────────────────────────────────────────────

def _is_varname(s: str) -> bool:
    """True if s looks like a variable identifier (not a number, URL, or dim)."""
    return bool(_VAR_NAME_RE.match(s)) and not re.fullmatch(r'[\d.]+', s)


def _var_file(tmpdir: str, var: str, ext: str = "png") -> str:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', var)
    return os.path.join(tmpdir, f"var_{safe}.{ext}")


async def _download_to(url: str, dest: str) -> str | None:
    """Download url → dest. Returns error string or None."""
    for h in _BLOCKED_HOSTS:
        if h in url:
            return "iscript: blocked host in URL"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    return f"iscript: HTTP {r.status} downloading image"
                data = await r.read()
    except Exception as exc:
        return f"iscript: download failed — {exc}"
    if len(data) > 50 * 1024 * 1024:
        return "iscript: image too large (max 50 MB)"
    Path(dest).write_bytes(data)
    return None


async def _im(*args: str, timeout: float = 30.0) -> str | None:
    """Run `convert *args`. Returns error string or None."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "convert", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return "iscript: timed out (30 s)"
    except FileNotFoundError:
        return "iscript: ImageMagick not installed"
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace").strip()[:200]
        return f"iscript: ImageMagick — {msg}"
    return None


async def _im_inplace(path: str, *mid: str, timeout: float = 30.0) -> str | None:
    """Apply convert filters to path in-place (read → process → overwrite)."""
    tmp = path + "._tmp.png"
    err = await _im(path, *mid, tmp, timeout=timeout)
    if err:
        if os.path.exists(tmp):
            os.remove(tmp)
        return err
    os.replace(tmp, path)
    return None


# ── Engine ────────────────────────────────────────────────────────────────────

class IScriptEngine(BaseEngine):
    name = "iscript"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        lines = [
            ln.strip()
            for ln in content.strip().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if not lines:
            return EngineResult(error="iscript: no commands")

        tmpdir = tempfile.mkdtemp(prefix="iscript_")
        try:
            return await self._run(lines, ctx, tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _run(self, lines: list[str], ctx, tmpdir: str) -> EngineResult:
        vars: dict[str, str] = {}    # varname → current file path (PNG unless spin)
        output_var: str | None = None
        output_format: str = "png"
        last_var: str | None = None

        for line in lines:
            # Split into at most 3 tokens; anything after the 2nd space is one arg
            tokens = line.split(None, 3)
            op = tokens[0].lower()

            if op not in _ALLOWED_OPS:
                return EngineResult(error=f"iscript: unknown operation '{op}'")

            # ── load ──────────────────────────────────────────────────────
            if op == "load":
                if len(tokens) < 2:
                    return EngineResult(error="iscript: load requires a URL")
                url = tokens[1]
                if not url.startswith(("http://", "https://")):
                    return EngineResult(error="iscript: load only accepts http/https URLs")
                # Optional trailing var name
                var = _DEFAULT_VAR
                if len(tokens) >= 3 and _is_varname(tokens[2]):
                    var = tokens[2]
                raw = _var_file(tmpdir, var, "raw")
                err = await _download_to(url, raw)
                if err:
                    return EngineResult(error=err)
                dest = _var_file(tmpdir, var)
                err = await _im(raw, dest)
                if err:
                    # Try just renaming if convert fails (might be unsupported format)
                    os.rename(raw, dest)
                else:
                    os.remove(raw)
                vars[var] = dest
                last_var = var

            # ── load_attachment ───────────────────────────────────────────
            elif op == "load_attachment":
                var = _DEFAULT_VAR
                if len(tokens) >= 2 and _is_varname(tokens[1]):
                    var = tokens[1]
                att = None
                if ctx.message.attachments:
                    att = ctx.message.attachments[0]
                else:
                    ref = getattr(ctx.message, "reference", None)
                    if ref and getattr(ref, "resolved", None) and \
                       getattr(ref.resolved, "attachments", None):
                        att = ref.resolved.attachments[0]
                if att is None:
                    return EngineResult(error="iscript: no attachment found in message or reply")
                suffix = Path(att.filename).suffix or ".png"
                raw = os.path.join(tmpdir, f"att_{var}{suffix}")
                await att.save(raw)
                dest = _var_file(tmpdir, var)
                err = await _im(raw, dest)
                if err:
                    os.rename(raw, dest)
                vars[var] = dest
                last_var = var

            # ── output ────────────────────────────────────────────────────
            elif op == "output":
                if len(tokens) < 2:
                    return EngineResult(error="iscript: output requires a format")
                # output [varname] FORMAT  OR  output FORMAT
                if len(tokens) >= 3 and _is_varname(tokens[1]) and tokens[1] in vars:
                    output_var = tokens[1]
                    fmt = tokens[2].lower().lstrip(".")
                else:
                    fmt = tokens[1].lower().lstrip(".")
                if fmt not in _ALLOWED_FORMATS:
                    return EngineResult(error="iscript: format must be jpg/png/gif/webp")
                output_format = "jpg" if fmt == "jpeg" else fmt

            # ── everything else ───────────────────────────────────────────
            else:
                err, new_path, new_var = await self._apply_op(op, tokens[1:], vars, last_var, tmpdir)
                if err:
                    return EngineResult(error=err)
                if new_path and new_var:
                    vars[new_var] = new_path
                    last_var = new_var
                    # If op produced a GIF, default output to gif
                    if new_path.endswith(".gif") and output_format == "png":
                        output_format = "gif"

        # ── Final output ──────────────────────────────────────────────────
        final_var = output_var or last_var
        if not vars:
            return EngineResult(error="iscript: no image loaded — use 'load' or 'load_attachment'")
        if final_var is None or final_var not in vars:
            final_var = next(iter(vars))

        src = vars[final_var]
        out_path = os.path.join(tmpdir, f"output.{output_format}")
        err = await _im(src, out_path)
        if err:
            return EngineResult(error=err)

        out_bytes = Path(out_path).read_bytes()
        if len(out_bytes) > _MAX_BYTES:
            return EngineResult(error="iscript: output too large for Discord (max 8 MB)")
        return EngineResult(
            files=[discord.File(io.BytesIO(out_bytes), filename=f"iscript.{output_format}")]
        )

    async def _apply_op(
        self,
        op: str,
        rest: list[str],
        vars: dict[str, str],
        last_var: str | None,
        tmpdir: str,
    ) -> tuple[str | None, str | None, str | None]:
        """
        Dispatch an image operation.
        Returns (error, new_path, var_name).
        new_path is only set when the op changes the file location (spin).
        Otherwise returns (None, None, var_name) on success.
        """
        # Resolve variable: first token is var if it's in vars dict
        var = None
        args = list(rest)
        if args and _is_varname(args[0]) and args[0] in vars:
            var = args.pop(0)
        else:
            var = last_var or _DEFAULT_VAR

        if var not in vars:
            return f"iscript: variable '{var}' not loaded — use 'load' or 'load_attachment' first", None, None

        path = vars[var]
        a0 = args[0].strip() if len(args) > 0 else ""
        a1 = args[1].strip() if len(args) > 1 else ""
        a_rest = " ".join(args).strip()  # full remaining text (for caption/impact)

        err = await self._op(op, path, a0, a1, a_rest, tmpdir)
        if isinstance(err, tuple):
            # spin returns (None, new_gif_path) or (error, None)
            op_err, new_path = err
            return op_err, new_path, var
        return err, None, var

    async def _op(self, op: str, path: str, a0: str, a1: str, a_rest: str, tmpdir: str):
        """
        Run the operation on path in-place.
        Returns None on success, error string on failure.
        For spin, returns (error|None, new_gif_path|None).
        """

        # ── Hue shift ─────────────────────────────────────────────────────
        if op in ("hueshifthsv", "hueshift"):
            try:
                deg = float(a0) if a0 else 180.0
            except ValueError:
                return f"iscript: {op} requires degrees (e.g. hueshifthsv f 180)"
            hue_pct = (deg % 360) / 180.0 * 100.0 + 100.0
            return await _im_inplace(path, "-modulate", f"100,100,{hue_pct:.2f}")

        # ── Grayscale ─────────────────────────────────────────────────────
        if op == "grayscale":
            return await _im_inplace(path, "-colorspace", "Gray", "-colorspace", "sRGB")

        # ── Negate / invert ───────────────────────────────────────────────
        if op in ("negate", "invert"):
            return await _im_inplace(path, "-negate")

        # ── Sepia ─────────────────────────────────────────────────────────
        if op == "sepia":
            return await _im_inplace(path, "-sepia-tone", "80%")

        # ── Brightness ────────────────────────────────────────────────────
        if op == "brightness":
            try:
                val = max(-100, min(int(float(a0)), 100))
            except (ValueError, TypeError):
                return "iscript: brightness requires a number (-100 to 100)"
            return await _im_inplace(path, "-brightness-contrast", f"{val}x0")

        # ── Contrast ──────────────────────────────────────────────────────
        if op == "contrast":
            try:
                val = max(-100, min(int(float(a0)), 100))
            except (ValueError, TypeError):
                return "iscript: contrast requires a number (-100 to 100)"
            return await _im_inplace(path, "-brightness-contrast", f"0x{val}")

        # ── Saturate ──────────────────────────────────────────────────────
        if op == "saturate":
            try:
                pct = max(0.0, min(float(a0), 5.0)) * 100.0
            except (ValueError, TypeError):
                return "iscript: saturate requires a multiplier (e.g. 2.0)"
            return await _im_inplace(path, "-modulate", f"100,{pct:.1f},100")

        # ── Blur ──────────────────────────────────────────────────────────
        if op == "blur":
            try:
                r = max(0.0, min(float(a0), 50.0))
            except (ValueError, TypeError):
                return "iscript: blur requires a radius (e.g. blur f 5)"
            return await _im_inplace(path, "-blur", f"0x{r}")

        # ── Sharpen ───────────────────────────────────────────────────────
        if op == "sharpen":
            try:
                r = max(0.0, min(float(a0), 50.0))
            except (ValueError, TypeError):
                return "iscript: sharpen requires an amount (e.g. sharpen f 3)"
            return await _im_inplace(path, "-sharpen", f"0x{r}")

        # ── Pixelate ──────────────────────────────────────────────────────
        if op == "pixelate":
            try:
                size = max(2, min(int(float(a0)), 200))
            except (ValueError, TypeError):
                return "iscript: pixelate requires a size (e.g. pixelate f 20)"
            return await _im_inplace(path, "-scale", f"{size}%", "-scale", "10000%")

        # ── JPEG compress ─────────────────────────────────────────────────
        if op == "jpeg":
            try:
                q = max(1, min(int(float(a0)), 95)) if a0 else 20
            except (ValueError, TypeError):
                q = 20
            tmp_jpg = path + "._j.jpg"
            err = await _im(path, "-quality", str(q), tmp_jpg)
            if err:
                return err
            err = await _im(tmp_jpg, path)
            if os.path.exists(tmp_jpg):
                os.remove(tmp_jpg)
            return err

        # ── Deep fry ──────────────────────────────────────────────────────
        if op == "deepfry":
            tmp_jpg = path + "._df.jpg"
            err = await _im(path, "-quality", "1", tmp_jpg)
            if err:
                return err
            err = await _im(tmp_jpg, "-modulate", "100,300,100", "-sharpen", "0x8", path)
            if os.path.exists(tmp_jpg):
                os.remove(tmp_jpg)
            return err

        # ── Edges ─────────────────────────────────────────────────────────
        if op == "edges":
            return await _im_inplace(path, "-edge", "1")

        # ── Emboss ────────────────────────────────────────────────────────
        if op == "emboss":
            return await _im_inplace(path, "-emboss", "0x1")

        # ── Charcoal ──────────────────────────────────────────────────────
        if op == "charcoal":
            try:
                r = max(0.0, min(float(a0), 10.0)) if a0 else 1.0
            except (ValueError, TypeError):
                r = 1.0
            return await _im_inplace(path, "-charcoal", str(r))

        # ── Oil paint ─────────────────────────────────────────────────────
        if op == "oil":
            try:
                r = max(1, min(int(float(a0)), 8)) if a0 else 3
            except (ValueError, TypeError):
                r = 3
            return await _im_inplace(path, "-paint", str(r))

        # ── Solarize ──────────────────────────────────────────────────────
        if op == "solarize":
            try:
                t = max(0, min(int(float(a0.rstrip("%"))), 100)) if a0 else 50
            except (ValueError, TypeError):
                t = 50
            return await _im_inplace(path, "-solarize", f"{t}%")

        # ── Posterize ─────────────────────────────────────────────────────
        if op == "posterize":
            try:
                lv = max(2, min(int(float(a0)), 8)) if a0 else 4
            except (ValueError, TypeError):
                lv = 4
            return await _im_inplace(path, "-posterize", str(lv))

        # ── Vignette ──────────────────────────────────────────────────────
        if op == "vignette":
            return await _im_inplace(path, "-vignette", "0x8+5+5")

        # ── Rotate ────────────────────────────────────────────────────────
        if op == "rotate":
            try:
                deg = float(a0) if a0 else 90.0
            except (ValueError, TypeError):
                return "iscript: rotate requires degrees"
            return await _im_inplace(path, "-rotate", str(deg % 360))

        # ── Resize ────────────────────────────────────────────────────────
        if op == "resize":
            if not a0 or not re.fullmatch(r'\d+x\d+', a0, re.IGNORECASE):
                return "iscript: resize requires WxH (e.g. resize f 640x480)"
            return await _im_inplace(path, "-resize", a0 + "!")

        # ── Thumbnail ─────────────────────────────────────────────────────
        if op == "thumbnail":
            if not a0 or not re.fullmatch(r'\d+x\d+', a0, re.IGNORECASE):
                return "iscript: thumbnail requires WxH (e.g. thumbnail f 640x480)"
            return await _im_inplace(path, "-thumbnail", a0)

        # ── Flip / Flop ───────────────────────────────────────────────────
        if op == "flip":
            return await _im_inplace(path, "-flip")
        if op == "flop":
            return await _im_inplace(path, "-flop")

        # ── Mirror ────────────────────────────────────────────────────────
        if op == "mirror":
            d = (a0 or "left").lower()
            if d in ("left", "right"):
                # Flop the image, then append the original and flop side by side
                tmp_flop = path + "._flop.png"
                err = await _im(path, "-flop", tmp_flop)
                if err:
                    return err
                if d == "left":
                    # left mirror: original left + its flop
                    err = await _im(path, tmp_flop, "+append", path + "._mirr.png")
                else:
                    # right mirror: flop + original
                    err = await _im(tmp_flop, path, "+append", path + "._mirr.png")
                if os.path.exists(tmp_flop):
                    os.remove(tmp_flop)
                if err:
                    return err
                os.replace(path + "._mirr.png", path)
            elif d in ("top", "bottom"):
                tmp_flip = path + "._flip.png"
                err = await _im(path, "-flip", tmp_flip)
                if err:
                    return err
                if d == "top":
                    err = await _im(path, tmp_flip, "-append", path + "._mirr.png")
                else:
                    err = await _im(tmp_flip, path, "-append", path + "._mirr.png")
                if os.path.exists(tmp_flip):
                    os.remove(tmp_flip)
                if err:
                    return err
                os.replace(path + "._mirr.png", path)
            else:
                return "iscript: mirror direction must be left/right/top/bottom"
            return None

        # ── Spin GIF ──────────────────────────────────────────────────────
        if op == "spin":
            try:
                frames = max(4, min(int(float(a0)), 60)) if a0 else 16
                fps    = max(1, min(int(float(a1)), 30)) if a1 else 12
            except (ValueError, TypeError):
                frames, fps = 16, 12
            delay = max(1, round(100 / fps))
            frame_paths = []
            for i in range(frames):
                deg = i * (360.0 / frames)
                fp = os.path.join(tmpdir, f"_spin_{i:03d}.png")
                err = await _im(
                    path,
                    "-background", "none",
                    "-distort", "ScaleRotateTranslate", f"0,0 1,1 {deg}",
                    fp,
                )
                if err:
                    return (err, None)
                frame_paths.append(fp)
            gif_path = path.replace(".png", "_spin.gif")
            err = await _im(
                "-delay", str(delay), "-loop", "0",
                *frame_paths,
                gif_path,
                timeout=90.0,
            )
            for fp in frame_paths:
                if os.path.exists(fp):
                    os.remove(fp)
            if err:
                return (err, None)
            return (None, gif_path)

        # ── Caption ───────────────────────────────────────────────────────
        if op == "caption":
            text = a_rest.strip()
            if not text:
                return "iscript: caption requires text"
            return await _im_inplace(
                path,
                "-gravity", "South",
                "-background", "#000000CC",
                "-splice", "0x50",
                "-fill", "white",
                "-font", "DejaVu-Sans-Bold",
                "-pointsize", "32",
                "-annotate", "+0+9",
                text,
            )

        # ── Impact (meme text) ────────────────────────────────────────────
        if op == "impact":
            full = a_rest.strip()
            if "|" in full:
                top_text, bottom_text = full.split("|", 1)
                top_text = top_text.strip()
                bottom_text = bottom_text.strip()
            else:
                top_text = full
                bottom_text = ""
            im_args: list[str] = [
                "-font", "DejaVu-Sans-Bold",
                "-pointsize", "56",
            ]
            if top_text:
                im_args += [
                    "-fill", "white", "-stroke", "black", "-strokewidth", "3",
                    "-gravity", "North", "-annotate", "+0+10", top_text,
                ]
            if bottom_text:
                im_args += [
                    "-fill", "white", "-stroke", "black", "-strokewidth", "3",
                    "-gravity", "South", "-annotate", "+0+10", bottom_text,
                ]
            if not im_args:
                return "iscript: impact requires text"
            return await _im_inplace(path, *im_args)

        return f"iscript: unknown operation '{op}'"
