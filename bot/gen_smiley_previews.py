#!/usr/bin/env python3
"""
Generate smiley face reference image + effect preview images/GIFs.
Upload them all to Catbox and print a Python dict of effect_key → URL.

Run from the repo root:  python3 bot/gen_smiley_previews.py
"""
import os, subprocess, tempfile, math, json, sys, time
from pathlib import Path
from PIL import Image, ImageDraw
import requests

CATBOX_USERHASH = os.environ.get("CATBOX_USERHASH", "")
SIZE = 400  # smiley face dimensions


# ── 1. Draw smiley face ─────────────────────────────────────────────────────

def create_smiley(size=SIZE) -> Image.Image:
    """Python-art smiley: blue background, yellow face, snake accent."""
    img = Image.new("RGB", (size, size), "#3776AB")  # Python blue bg
    draw = ImageDraw.Draw(img)
    pad = int(size * 0.07)

    # Face (yellow)
    draw.ellipse([pad, pad, size - pad, size - pad],
                 fill="#FFD43B", outline="#1a1a2e", width=int(size * 0.015))

    # Eyes
    ey = size * 0.36
    er = size * 0.07
    for ex in (size * 0.33, size * 0.67):
        draw.ellipse([ex - er, ey - er, ex + er, ey + er], fill="#1a1a2e")
        # White highlight
        draw.ellipse([ex - er * 0.35, ey - er * 0.55,
                      ex + er * 0.1, ey - er * 0.1], fill="white")

    # Nose (small Python "snout")
    nx, ny, nr = size * 0.5, size * 0.53, size * 0.03
    draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill="#e0a010")

    # Smile arc
    sb = [size * 0.26, size * 0.45, size * 0.74, size * 0.80]
    draw.arc(sb, start=5, end=175, fill="#1a1a2e", width=int(size * 0.025))

    # Python snake-style "cheek scales" (two small overlapping arcs)
    for cx, cy, start, end in [
        (size * 0.24, size * 0.6, 200, 320),
        (size * 0.76, size * 0.6, 220, 340),
    ]:
        sr = size * 0.09
        draw.arc([cx - sr, cy - sr, cx + sr, cy + sr],
                 start=start, end=end, fill="#3776AB", width=int(size * 0.018))

    # Small "Python" text label at bottom
    # (skip font for portability — use simple dots)
    dot_y = size - int(size * 0.1)
    for dx in range(-2, 3):
        draw.ellipse([size // 2 + dx * 6 - 2, dot_y - 2,
                      size // 2 + dx * 6 + 2, dot_y + 2], fill="#FFD43B")

    return img


# ── 2. FFmpeg helpers ────────────────────────────────────────────────────────

def ff(args: list[str]) -> tuple[bool, str]:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args,
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def make_loop_video(smiley_path: str, out_path: str, duration: float = 2.0) -> bool:
    """Create a short looped video from the smiley PNG for animated previews."""
    ok, _ = ff([
        "-loop", "1", "-framerate", "30", "-t", str(duration),
        "-i", smiley_path,
        "-vf", "format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
        "-f", "mp4", out_path,
    ])
    return ok


def video_to_gif(in_path: str, out_path: str) -> bool:
    """Convert mp4 → gif with palette."""
    ok, _ = ff([
        "-i", in_path,
        "-vf", "fps=20,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        "-loop", "0", out_path,
    ])
    return ok


def apply_static_vf(smiley_path: str, vf: str, out_path: str) -> bool:
    ok, err = ff(["-i", smiley_path, "-vf", vf, out_path])
    if not ok:
        print(f"  WARN: {vf[:60]!r} → {err[-200:]}", file=sys.stderr)
    return ok


def apply_animated_vf(loop_video: str, vf: str, out_gif: str, tmpdir: str) -> bool:
    """Apply vf to looped video → animated GIF."""
    tmp_mp4 = os.path.join(tmpdir, "anim_tmp.mp4")
    ok, err = ff([
        "-i", loop_video,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
        "-t", "2", tmp_mp4,
    ])
    if not ok:
        print(f"  WARN (vf→mp4): {vf[:60]!r} → {err[-200:]}", file=sys.stderr)
        return False
    ok2 = video_to_gif(tmp_mp4, out_gif)
    if not ok2:
        print(f"  WARN (mp4→gif): {out_gif}", file=sys.stderr)
    return ok2


def apply_preset_to_smiley(smiley_path: str, preset_vf: str, out_gif: str, tmpdir: str, use_complex: str | None = None) -> bool:
    """Apply a PRESET_FILTERS vf (or complex) to the smiley image → animated GIF."""
    if use_complex:
        fc = use_complex + ",split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        ok, err = ff([
            "-loop", "1", "-t", "3", "-i", smiley_path,
            "-filter_complex", fc, "-loop", "0", out_gif,
        ])
    else:
        vf = preset_vf + ",split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        ok, err = ff([
            "-loop", "1", "-t", "3", "-i", smiley_path,
            "-vf", vf, "-loop", "0", out_gif,
        ])
    if not ok:
        print(f"  WARN (preset gif): {err[-200:]}", file=sys.stderr)
    return ok


# ── 3. Catbox upload ─────────────────────────────────────────────────────────

def upload_catbox(path: str) -> str | None:
    try:
        data = {"reqtype": "fileupload"}
        if CATBOX_USERHASH:
            data["userhash"] = CATBOX_USERHASH
        with open(path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data=data,
                files={"fileToUpload": (Path(path).name, f)},
                timeout=120,
            )
        url = r.text.strip()
        return url if url.startswith("https://") else None
    except Exception as e:
        print(f"  WARN: catbox upload failed: {e}", file=sys.stderr)
        return None


# ── 4. Effect definitions ────────────────────────────────────────────────────

# (key, output_filename, effect_type, vf_or_preset)
# effect_type: "static" | "animated_vf" | "preset"
_BASE_NOISE = "noise=alls=40:allf=t+u"
_SHAKE_VF   = "crop=iw-20:ih-20:10+5*sin(t*30):10+5*cos(t*17),scale=iw+20:ih+20"

EFFECTS = [
    # key                     filename                     type          vf / preset_vf
    ("negate",     "negate.png",        "static",       "negate"),
    ("hflip",      "hflip.png",         "static",       "hflip"),
    ("vflip",      "vflip.png",         "static",       "vflip"),
    ("grayscale",  "grayscale.png",     "static",
        "colorchannelmixer=.299:.587:.114:0:.299:.587:.114:0:.299:.587:.114"),
    ("sepia",      "sepia.png",         "static",
        "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"),
    ("swapuv",     "swapuv.png",        "static",       "swapuv"),
    ("mirror",     "mirror.png",        "static",
        "split[_ma][_mb];[_ma]crop=iw/2:ih:0:0[_mL];[_mb]crop=iw/2:ih:0:0,hflip[_mR];[_mL][_mR]hstack"),
    ("zoom",       "zoom.png",          "static",
        "format=yuv444p,rotate=0:iw*1.1:ih*1.1,"
        "geq='p((W/2)+(X-(W/2))/2.0,(H/2)+(Y-(H/2))/2.0)',"
        "scale=iw:ih,crop=iw/1.1:ih/1.1:(iw-iw/1.1)/2:(ih-ih/1.1)/2,format=yuv420p"),
    ("tile",       "tile.png",          "static",
        "format=yuv444p,"
        "geq='p(mod(X*2.0,W),mod(Y*2.0,H)):cb(mod(X*2.0,W),mod(Y*2.0,H)):cr(mod(X*2.0,W),mod(Y*2.0,H))',"
        "scale=iw:ih,format=yuv420p"),
    ("pan",        "pan.png",           "static",
        f"format=yuv444p,"
        f"geq='p(clip(X+60,0,W-1),clip(Y+40,0,H-1))"
        f":cb(clip(X+60,0,W-1),clip(Y+40,0,H-1))"
        f":cr(clip(X+60,0,W-1),clip(Y+40,0,H-1))',"
        f"scale=iw:ih,format=yuv420p"),
    ("brightness", "brightness.png",    "static",       "eq=brightness=0.35:contrast=1.1:saturation=1.0:gamma=1.0"),
    ("contrast",   "contrast.png",      "static",       "eq=contrast=2.5:brightness=0:saturation=1.0:gamma=1.0"),
    ("saturation", "saturation.png",    "static",       "hue=s=3.0:h=0"),
    ("invlum",     "invlum.png",        "static",
        "lut3d=file=bot/InvertLuminosity.cube" if os.path.exists("bot/InvertLuminosity.cube")
        else "negate"),  # fallback
    ("labadjust",  "labadjust.png",     "static",
        "colorspace=all=bt601:iall=bt709,lutrgb=g=negval,colorspace=all=bt709"),
    ("rotate",     "rotate.png",        "static",       "rotate=PI/5:iw:ih:fillcolor=0x3776AB"),
    ("swirl",      "swirl.png",         "static",
        # simplified swirl: geq-based 180° rotation falloff around centre
        f"format=yuv444p,"
        f"geq='p("
        f"W/2+hypot(X-W/2,Y-H/2)*cos(atan2(Y-H/2,X-W/2)+3.14159*exp(-pow(hypot(X-W/2,Y-H/2)/(W*0.5),2))),"
        f"H/2+hypot(X-W/2,Y-H/2)*sin(atan2(Y-H/2,X-W/2)+3.14159*exp(-pow(hypot(X-W/2,Y-H/2)/(W*0.5),2)))"
        f")',"
        f"scale=iw:ih,format=yuv420p"),
    # ── Animated (from looped video) ──
    ("wave",       "wave.gif",          "animated_vf",
        "format=yuv444p,"
        "geq='p(X-sin((T*5+(0))+(Y/H)*(PI*1))*(-15*(W/640)),"
        "Y-sin((T*5+(0))+(X/W)*(PI*1))*(-15*(W/640)))',"
        "scale=iw:ih,format=yuv420p"),
    ("ripple",     "ripple.gif",        "animated_vf",
        "format=yuv444p,"
        "geq='p(W*0.5+(hypot(X-W*0.5,Y-H*0.5)+10.0*sin(2*PI*1.0*T+(-hypot(X-W*0.5,Y-H*0.5)/30.0)))*cos(atan2(Y-H*0.5,X-W*0.5)),"
        "H*0.5+(hypot(X-W*0.5,Y-H*0.5)+10.0*sin(2*PI*1.0*T+(-hypot(X-W*0.5,Y-H*0.5)/30.0)))*sin(atan2(Y-H*0.5,X-W*0.5)))',"
        "scale=iw:ih,format=yuv420p"),
    ("shake_pipe", "shake_pipe.gif",    "animated_vf",
        f"rotate=0:iw*1.1:ih*1.1,format=yuv444p,"
        f"geq='p(X+(5.0)*(2*mod(1000*sin(N*12.9898),1)-1),"
        f"Y+(3.0)*(2*mod(1000*sin(N+1000)*78.233,1)-1))',"
        f"crop={SIZE}:{SIZE},format=yuv420p"),
    # ── Preset-based (image → animated GIF) ──
    ("chaos",      "chaos.gif",         "preset",
        f"{_SHAKE_VF},{_BASE_NOISE},hue=h=t*180:s=2,eq=contrast=1.5:brightness=0.05:saturation=3"),
    ("glitch",     "glitch.gif",        "preset",
        f"rgbashift=rh=8:rv=-8:gh=-4:gv=4:bh=6:bv=-6,{_BASE_NOISE},eq=contrast=1.8:saturation=0"),
    ("static",     "static.gif",        "preset",
        f"{_BASE_NOISE},curves=vintage,eq=contrast=1.2"),
    ("melt",       "melt.gif",          "preset",
        f"perspective=x0=0:y0=0:x1=iw:y1=20*sin(t*3)"
        f":x2=0:y2=ih:x3=iw:y3=ih-20*sin(t*3),"
        + _BASE_NOISE),
    ("corrupt",    "corrupt.gif",       "preset",
        f"drawgrid=x=0:y=0:w=iw:h=5:t=1:color=white@0.1,{_BASE_NOISE},"
        f"eq=gamma=1.5:saturation=0.3:contrast=2"),
    ("rainbow",    "rainbow.gif",       "preset_complex",
        "[0:v]split=3[r][g][b];"
        "[r]lutrgb=r=val:g=0:b=0,pad=iw+6:ih:3:0[ro];"
        "[g]lutrgb=r=0:g=val:b=0[go];"
        "[b]lutrgb=r=0:g=0:b=val,pad=iw+6:ih:0:0[bo];"
        "[ro][go]blend=all_mode=addition[rg];"
        "[rg][bo]blend=all_mode=addition"),
]


# ── 5. Main ──────────────────────────────────────────────────────────────────

def main():
    os.makedirs("bot/help_previews", exist_ok=True)

    # Save smiley reference
    smiley_png = "bot/help_previews/smiley_reference.png"
    smiley = create_smiley()
    smiley.save(smiley_png)
    print(f"✅ Smiley saved: {smiley_png}")

    with tempfile.TemporaryDirectory() as tmpdir:
        loop_mp4 = os.path.join(tmpdir, "smiley_loop.mp4")
        loop_ok = make_loop_video(smiley_png, loop_mp4)
        if not loop_ok:
            print("❌ Failed to create loop video", file=sys.stderr)
            sys.exit(1)
        print("✅ Loop video created")

        results: dict[str, str] = {}

        for (key, filename, effect_type, vf_or_data) in EFFECTS:
            out_path = f"bot/help_previews/{filename}"
            print(f"  Generating {key} ({effect_type})…", end=" ", flush=True)
            ok = False
            if effect_type == "static":
                ok = apply_static_vf(smiley_png, vf_or_data, out_path)
            elif effect_type == "animated_vf":
                ok = apply_animated_vf(loop_mp4, vf_or_data, out_path, tmpdir)
            elif effect_type == "preset":
                ok = apply_preset_to_smiley(smiley_png, vf_or_data, out_path, tmpdir)
            elif effect_type == "preset_complex":
                ok = apply_preset_to_smiley(smiley_png, "", out_path, tmpdir, use_complex=vf_or_data)

            if ok and os.path.exists(out_path):
                url = upload_catbox(out_path)
                if url:
                    results[key] = url
                    print(f"→ {url}")
                else:
                    print("upload FAILED")
            else:
                print("render FAILED")
            time.sleep(0.4)  # rate-limit catbox

        # Upload smiley reference itself
        print("  Uploading smiley reference…", end=" ", flush=True)
        smiley_url = upload_catbox(smiley_png)
        if smiley_url:
            results["_smiley"] = smiley_url
            print(f"→ {smiley_url}")
        else:
            print("upload FAILED")

    print("\n# ── RESULTS DICT ──")
    print("HELP_PREVIEW_URLS = " + json.dumps(results, indent=4))


if __name__ == "__main__":
    main()
