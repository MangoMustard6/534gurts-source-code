"""Synthetic regression test for the Freakzinga test-effect filter graph.

This test does not download the real LUT/displacement assets or run the pitch
shifter.  It builds the same FFmpeg filter graph used by `_run_freakzinga_test_effect`
using synthetic lavfi inputs and a minimal dummy 3D LUT, and asserts that FFmpeg
accepts the graph without error.

Run with: python3 tests/test_freakzinga_filter.py
"""

import os
import subprocess
import tempfile
import textwrap


def _make_dummy_cube(path: str) -> None:
    """Write a minimal valid 2×2×2 3D LUT cube file."""
    with open(path, "w") as f:
        f.write(textwrap.dedent("""\
            # Minimal 3D LUT for Freakzinga filter regression test
            LUT_3D_SIZE 2
            0 0 0
            1 0 0
            0 1 0
            1 1 0
            0 0 1
            1 0 1
            0 1 1
            1 1 1
        """))


def _find_font() -> str | None:
    """Return a system font path usable by FFmpeg drawtext, or None."""
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    )
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        lut_path = os.path.join(tmpdir, "a.cube")
        _make_dummy_cube(lut_path)

        font_path = _find_font()
        if not font_path:
            print("SKIP: no system font available for drawtext")
            return 0

        w, h = 1920, 1080
        # Same graph structure as _run_freakzinga_test_effect, but fed from
        # two lavfi test sources so no external downloads are required.
        filter_complex = (
            "[0]lut3d={lut_path},format=yuv420p,rotate=-45/180*PI,format=yuv420p,scale=854:854,format=bgr32[00];"
            "[1]format=yuv444p,geq='p(mod(X,W),mod(Y/4,H))',scale=854:854,eq=contrast='(1-0.9)*2.366666':eval=frame,format=bgr32,hue=b=-0.033[x];"
            "color=s=854x854:c=#808080,format=bgr32[y];"
            "[00][x][y]displace=edge=wrap,scale={w}:{h},setsar=1,format=yuv444p,format=yuv444p,scale=640:640,"
            "geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*0)))*(-15*0)),Y-((sin((T*5*0+(0.34666*15))+(X/W)*(PI*15)))*(-15*0.8)))',"
            "scale={w}:{h},format=yuv420p,rotate=45/180*PI,format=yuv420p,hflip,"
            "crop={w}*0.840:{h}:{w}*0.840:0,split[right][tmp];"
            "[tmp]hflip[left];"
            "[left][right]hstack,crop={w}:{h}:{w}*0.840:0,hflip,scroll=0:0:.5,"
            "crop=iw/2:ih:0:0,split=2[_ml1][_mr1];[_mr1]hflip[_mrf1];[_ml1][_mrf1]hstack,"
            "scroll=0:0:0:.5,"
            "crop=iw/2:ih:0:0,split=2[_ml2][_mr2];[_mr2]hflip[_mrf2];[_ml2][_mrf2]hstack,"
            "negate,"
            "drawtext=fontfile={font_path}:text='%{{n}}.000':text_align=R:fontcolor=white:fontsize=w/24:"
            "box=1:boxcolor=black:boxborderw=7*(text_h):x=(w/2)-(text_w/2):y=(h-text_h)/1.12,negate"
        ).format(lut_path=lut_path, w=w, h=h, font_path=font_path)

        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=640x480:rate=30",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=640x480:rate=30",
            "-filter_complex", filter_complex,
            "-frames:v", "1",
            "-an",
            "-f", "null", "-",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print("FAIL: filter graph did not initialize")
            print(result.stderr[-1500:])
            return 1

        print("PASS: freakzingatesteffect filter graph accepted by FFmpeg")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
