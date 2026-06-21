"""
IHTX Bot — I Hate The X FFmpeg Discord Bot

Full implementation with preset effects, custom effect chaining (t!ihtx),
and the preview1280 TV-simulator montage command.

Dependencies required at runtime: ffmpeg, aiohttp, discord.py, optionally yt-dlp,
ImageMagick/sox/etc. depending on advanced effects.
"""

import discord
from discord.ext import commands, tasks
from bot.tags.cog import TagCog
import asyncio
import json
import math
import os
import random
import re
import shlex
import tempfile
import shutil
import subprocess
import aiohttp
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import urllib.parse
import base64
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from google import genai as _genai_lib
    from google.genai import types as _genai_types
    _gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if _gemini_api_key:
        _genai_client = _genai_lib.Client(api_key=_gemini_api_key)
        print(f"[genai] Gemini client initialized ✓")
    else:
        _genai_client = None
        print("[genai] GEMINI_API_KEY not set — chat disabled")
except Exception as _genai_init_err:
    _genai_client = None
    print(f"[genai] Failed to initialize Gemini client: {_genai_init_err}")

try:
    from openai import OpenAI as _OpenAI_lib
    _openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    if _openrouter_api_key:
        _openrouter_client = _OpenAI_lib(
            base_url="https://openrouter.ai/api/v1",
            api_key=_openrouter_api_key,
        )
    else:
        _openrouter_client = None
except ImportError:
    _openrouter_client = None


# ---------- Configuration & constants ----------

TOKEN = os.environ.get("DISCORD_TOKEN")
CATBOX_USERHASH = os.environ.get("CATBOX_USERHASH", "")

# Default owner (can be extended via owner file)
OWNER_ID = 1355759019330895973

OWNER_IDS_FILE = Path("bot/owner_ids.json")
owner_ids: set[int] = {OWNER_ID}


def _load_owner_ids():
    global owner_ids
    try:
        if OWNER_IDS_FILE.exists():
            with OWNER_IDS_FILE.open() as f:
                owner_ids = set(int(x) for x in json.load(f))
        else:
            owner_ids = {OWNER_ID}
    except Exception:
        owner_ids = {OWNER_ID}


def _save_owner_ids():
    OWNER_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OWNER_IDS_FILE.open("w") as f:
        json.dump(list(owner_ids), f)


def _is_owner(ctx: commands.Context) -> bool:
    return ctx.author.id in owner_ids


def _is_owner_by_id(user_id: int) -> bool:
    return user_id in owner_ids


def _is_bot_mod(ctx: commands.Context) -> bool:
    """True if the user is an owner OR has reached max XP level (bot moderator)."""
    if ctx.author.id in owner_ids:
        return True
    try:
        from pathlib import Path as _Path
        import json as _json
        _xp_file = _Path("bot/xp_data.json")
        if _xp_file.exists():
            with _xp_file.open() as _f:
                _xd = _json.load(_f)
            return bool(_xd.get(str(ctx.author.id), {}).get("is_mod", False))
    except Exception:
        pass
    return False

_load_owner_ids()

# Heavy command rate limiting
HEAVY_COMMANDS = {"ihtx", "effect", "destroy", "ihtxcustom", "icustom", "preview1280", "p1280", "multipitch", "mp", "multi", "lexg", "download", "dl", "dlv", "chat", "ask", "ai"}
HEAVY_LIMIT_DEFAULT = 10
HEAVY_LIMIT_OWNER = 5340
LIMITS_FILE = Path("bot/limits.json")
USAGE_FILE = Path("bot/usage.json")
PENDING_RESETS_FILE = Path("bot/pending_resets.json")
INVLUM_LUT_FILE = Path("bot/InvertLuminosity.cube")
heavy_limits: dict[int, int] = {}
heavy_usage: dict[int, list[float]] = {}


def _load_limits():
    global heavy_limits
    try:
        if LIMITS_FILE.exists():
            with LIMITS_FILE.open() as f:
                heavy_limits = {int(k): int(v) for k, v in json.load(f).items()}
        else:
            heavy_limits = {}
    except Exception:
        heavy_limits = {}


def _save_limits():
    LIMITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LIMITS_FILE.open("w") as f:
        json.dump(heavy_limits, f)


def _load_usage():
    global heavy_usage
    try:
        if USAGE_FILE.exists():
            with USAGE_FILE.open() as f:
                data = json.load(f)
                heavy_usage = {int(k): [float(t) for t in v] for k, v in data.items()}
        else:
            heavy_usage = {}
    except Exception:
        heavy_usage = {}


def _save_usage():
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_FILE.open("w") as f:
        json.dump({str(k): v for k, v in heavy_usage.items()}, f)


def _check_heavy_limit(user_id: int) -> tuple[bool, str]:
    if _is_owner_by_id(user_id):
        return True, ""
    limit = heavy_limits.get(user_id, HEAVY_LIMIT_DEFAULT)
    now = time.time()
    day_ago = now - 86400
    usage = [t for t in heavy_usage.get(user_id, []) if t > day_ago]
    heavy_usage[user_id] = usage
    if len(usage) >= limit:
        return False, f"Heavy command limit reached ({limit}/{limit} per 24h). Contact an owner."
    usage.append(now)
    heavy_usage[user_id] = usage
    _save_usage()
    return True, ""

_load_limits()
_load_usage()

# Blocklist (users)
BLOCKLIST_FILE = Path("bot/blocklist.json")
blocklist: set[int] = set()


def _load_blocklist():
    global blocklist
    try:
        if BLOCKLIST_FILE.exists():
            with BLOCKLIST_FILE.open() as f:
                blocklist = set(int(x) for x in json.load(f))
        else:
            blocklist = set()
    except Exception:
        blocklist = set()


def _save_blocklist():
    BLOCKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BLOCKLIST_FILE.open("w") as f:
        json.dump(list(blocklist), f)

_load_blocklist()

# Channel blocklist
CHANNEL_BLOCK_FILE = Path("bot/channel_blocks.json")
channel_blocks: set[int] = set()


def _load_channel_blocks():
    global channel_blocks
    try:
        if CHANNEL_BLOCK_FILE.exists():
            with CHANNEL_BLOCK_FILE.open() as f:
                channel_blocks = set(int(x) for x in json.load(f))
        else:
            channel_blocks = set()
    except Exception:
        channel_blocks = set()


def _save_channel_blocks():
    CHANNEL_BLOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHANNEL_BLOCK_FILE.open("w") as f:
        json.dump(list(channel_blocks), f)

_load_channel_blocks()

# Per-channel keyword blocklist
KEYWORD_BLOCK_FILE = Path("bot/keyword_blocks.json")
KEYWORD_BLOCK_MSG_FILE = Path("bot/keyword_block_messages.json")
keyword_blocks: dict[int, set[str]] = {}
keyword_block_messages: dict[int, dict[str, str]] = {}


def _normalize_keyword(keyword: str) -> str:
    return re.sub(r"\s+", " ", keyword.strip().lower())


def _load_keyword_blocks():
    global keyword_blocks, keyword_block_messages
    try:
        if KEYWORD_BLOCK_FILE.exists():
            with KEYWORD_BLOCK_FILE.open() as f:
                raw = json.load(f)
            keyword_blocks = {
                int(channel_id): {
                    _normalize_keyword(keyword)
                    for keyword in keywords
                    if _normalize_keyword(str(keyword))
                }
                for channel_id, keywords in raw.items()
            }
        else:
            keyword_blocks = {}
    except Exception:
        keyword_blocks = {}

    try:
        if KEYWORD_BLOCK_MSG_FILE.exists():
            with KEYWORD_BLOCK_MSG_FILE.open() as f:
                raw = json.load(f)
            keyword_block_messages = {
                int(channel_id): {
                    _normalize_keyword(keyword): msg
                    for keyword, msg in msgs.items()
                }
                for channel_id, msgs in raw.items()
            }
        else:
            keyword_block_messages = {}
    except Exception:
        keyword_block_messages = {}


def _save_keyword_blocks():
    KEYWORD_BLOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        str(channel_id): sorted(keywords)
        for channel_id, keywords in keyword_blocks.items()
        if keywords
    }
    with KEYWORD_BLOCK_FILE.open("w") as f:
        json.dump(serializable, f, indent=2)
    # Also save messages
    msg_serializable = {
        str(channel_id): {
            keyword: msg
            for keyword, msg in msgs.items()
        }
        for channel_id, msgs in keyword_block_messages.items()
    }
    with KEYWORD_BLOCK_MSG_FILE.open("w") as f:
        json.dump(msg_serializable, f, indent=2)


def _blocked_keyword_for_message(channel_id: int, content: str) -> str | None:
    keywords = keyword_blocks.get(channel_id, set())
    if not keywords:
        return None
    normalized_content = content.lower()
    for keyword in sorted(keywords, key=len, reverse=True):
        if keyword and keyword in normalized_content:
            return keyword
    return None

def _blocked_keyword_message(channel_id: int, keyword: str, author_mention: str) -> str:
    msgs = keyword_block_messages.get(channel_id, {})
    msg = msgs.get(keyword)
    if msg:
        return msg.replace("{mention}", author_mention).replace("{user}", author_mention)
    return f"{author_mention}, that keyword is blocked in this channel."

_load_keyword_blocks()

# Autoreplies
AUTOREPLY_FILE = Path("bot/autoreplies.json")
autoreplies: dict[str, str] = {}


def _load_autoreplies():
    global autoreplies
    try:
        if AUTOREPLY_FILE.exists():
            with AUTOREPLY_FILE.open() as f:
                raw = json.load(f)
            # Migrate old flat format {"trigger": "response"} → new format
            migrated = {}
            for k, v in raw.items():
                if isinstance(v, dict):
                    migrated[k] = v
                else:
                    migrated[k] = {"response": v, "channel_id": None}
            autoreplies = migrated
        else:
            autoreplies = {}
    except Exception:
        autoreplies = {}


def _save_autoreplies():
    AUTOREPLY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUTOREPLY_FILE.open("w") as f:
        json.dump(autoreplies, f, indent=2)


_load_autoreplies()

# Autoreply2 (per-channel AI auto-reply toggle)
AUTOREPLY2_FILE = Path("bot/autoreply2.json")
autoreply2: set[int] = set()  # stores channel IDs


def _load_autoreply2():
    global autoreply2
    try:
        if AUTOREPLY2_FILE.exists():
            with AUTOREPLY2_FILE.open() as f:
                raw = json.load(f)
            # Migration: old format stored user IDs — wipe and start fresh as channel IDs
            autoreply2 = set()
            AUTOREPLY2_FILE.write_text("[]")
        else:
            autoreply2 = set()
    except Exception:
        autoreply2 = set()


def _save_autoreply2():
    AUTOREPLY2_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUTOREPLY2_FILE.open("w") as f:
        json.dump(list(autoreply2), f, indent=2)


_load_autoreply2()

# Autoreply2 no-mention set (users whose ar2 replies skip the ping)
AUTOREPLY2_NO_MENTION_FILE = Path("bot/autoreply2_no_mention.json")
autoreply2_no_mention: set[int] = set()


def _load_autoreply2_no_mention():
    global autoreply2_no_mention
    try:
        if AUTOREPLY2_NO_MENTION_FILE.exists():
            with AUTOREPLY2_NO_MENTION_FILE.open() as f:
                autoreply2_no_mention = set(int(x) for x in json.load(f))
        else:
            autoreply2_no_mention = set()
    except Exception:
        autoreply2_no_mention = set()


def _save_autoreply2_no_mention():
    AUTOREPLY2_NO_MENTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUTOREPLY2_NO_MENTION_FILE.open("w") as f:
        json.dump(list(autoreply2_no_mention), f, indent=2)


_load_autoreply2_no_mention()

# Warnings
WARNINGS_FILE = Path("bot/warnings.json")
warnings_data: dict[int, list[dict]] = {}


def _load_warnings():
    global warnings_data
    try:
        if WARNINGS_FILE.exists():
            with WARNINGS_FILE.open() as f:
                warnings_data = {int(k): v for k, v in json.load(f).items()}
        else:
            warnings_data = {}
    except Exception:
        warnings_data = {}


def _save_warnings():
    WARNINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with WARNINGS_FILE.open("w") as f:
        json.dump({str(k): v for k, v in warnings_data.items()}, f, indent=2)


_load_warnings()

# Tags (custom presets)
TAGS_FILE = Path("bot/tags.json")
tags: dict[str, dict] = {}


def _load_tags():
    global tags
    try:
        if TAGS_FILE.exists():
            with TAGS_FILE.open() as f:
                tags = json.load(f)
        else:
            tags = {}
    except Exception:
        tags = {}


def _save_tags():
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TAGS_FILE.open("w") as f:
        json.dump(tags, f, indent=2)

_load_tags()

# Intents and bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="t!", intents=intents)

# Maps user message id → list of bot reply message ids.
# Used to delete old responses when the user edits their command.
_response_map: dict[int, list[int]] = {}
_RESPONSE_MAP_MAX = 2000  # cap to prevent unbounded growth

# Runtime stats
_bot_start_time: float = time.time()
_renders_completed: int = 0
_renders_in_progress: int = 0

# File handling constants
SUPPORTED_EXTENSIONS  = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif", ".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS      = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"}
AUDIO_VIDEO_EXTS      = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_FILE_SIZE         = 25 * 1024 * 1024
MAX_REPETITIONS       = 100
MAX_DURATION          = 600

# Effect filter definitions
_BASE_NOISE = "noise=alls=40:allf=t+u"
_SHAKE      = "crop=iw-20:ih-20:10+5*sin(t*30):10+5*cos(t*17),scale=iw+20:ih+20"
_CHROMAB = (
    "[IN]split=3[r][g][b];"
    "[r]lutrgb=r=val:g=0:b=0,pad=iw+6:ih:3:0[ro];"
    "[g]lutrgb=r=0:g=val:b=0[go];"
    "[b]lutrgb=r=0:g=0:b=val,pad=iw+6:ih:0:0[bo];"
    "[ro][go]blend=all_mode=addition[rg];"
    "[rg][bo]blend=all_mode=addition[OUT]"
)

PRESET_FILTERS: dict[str, dict] = {
    "chaos": {
        "vf": f"{_SHAKE},{_BASE_NOISE},hue=h=t*180:s=2,eq=contrast=1.5:brightness=0.05:saturation=3",
        "complex": None,
    },
    "glitch": {
        "vf": f"rgbashift=rh=8:rv=-8:gh=-4:gv=4:bh=6:bv=-6,{_BASE_NOISE},eq=contrast=1.8:saturation=0",
        "complex": None,
    },
    "shake": {
        "vf": f"{_SHAKE},{_BASE_NOISE},eq=contrast=1.3:saturation=1.5",
        "complex": None,
    },
    "rainbow": {
        "vf": None,
        "complex": (
            "[0:v]split=3[r][g][b];"
            "[r]lutrgb=r=val:g=0:b=0,pad=iw+6:ih:3:0[ro];"
            "[g]lutrgb=r=0:g=val:b=0[go];"
            "[b]lutrgb=r=0:g=0:b=val,pad=iw+6:ih:0:0[bo];"
            "[ro][go]blend=all_mode=addition[rg];"
            "[rg][bo]blend=all_mode=addition"
        ),
    },
    "static": {
        "vf": f"{_BASE_NOISE},curves=vintage,eq=contrast=1.2",
        "complex": None,
    },
    "melt": {
        "vf": (
            "perspective=x0=0:y0=0:x1=iw:y1=20*sin(t*3)"
            ":x2=0:y2=ih:x3=iw:y3=ih-20*sin(t*3),"
            + _BASE_NOISE
        ),
        "complex": None,
    },
    "corrupt": {
        "vf": f"drawgrid=x=0:y=0:w=iw:h=5:t=1:color=white@0.1,{_BASE_NOISE},eq=gamma=1.5:saturation=0.3:contrast=2",
        "complex": None,
    },
    "sierpinskiransomware": {
        "vf": None,
        "complex": None,
        "complex_template": (
            "[0:v]null,trim=0:{d}[outv1];"
            "[0:a]atrim=0:{d}[outa1];"
            "[0:v]trim=0:{d}[v1];"
            "[0:v]negate,trim=0:{d}[v2];"
            "[v1][v2]concat=2:1:0,setpts=1/2*PTS,fps={fr},trim=0:{d}[outv2];"
            "[0:a]rubberband=pitch=2:tempo=2,atrim=0:{d}[a1];"
            "[0:a]rubberband=pitch=2:tempo=2,atrim=0:{d}[a2];"
            "[a1][a2]concat=2:0:1,atrim=0:{d}[outa2];"
            "[0:v]null,trim=0:{d}[v3];"
            "[0:v]negate,trim=0:{d}[v4];"
            "[v3][v4]concat=2:1:0,setpts=1/1.333*PTS,fps={fr},trim=0:{d}[outv3];"
            "[0:a]rubberband=pitch=1.333:tempo=1.333,atrim=0:{d}[a3];"
            "[0:a]rubberband=pitch=1.333:tempo=1.333,atrim=0:{d}[a4];"
            "[a3][a4]concat=2:0:1,atrim=0:{d}[outa3];"
            "[0:v]setpts=1/0.5*PTS,fps={fr},trim=0:{d}[outv4];"
            "[0:a]rubberband=pitch=0.5:tempo=0.5,atrim=0:{d}[outa4];"
            "[outv1][outv2]hstack[tmp1];"
            "[outv3][outv4]hstack[tmp2];"
            "[tmp1][tmp2]vstack,scale=iw/2:ih/2[outv];"
            "[outa1][outa2][outa3][outa4]amix=4,alimiter=2:latency=1,highpass=40[outa]"
        ),
        "maps": ["[outv]", "[outa]"],
        "audio_codec": "flac",
        "extra_codec_args": ["-preset", "ultrafast"],
        "output_ext": ".mp4",
    },
}

VISUAL_PRESETS = set(PRESET_FILTERS.keys())

HELP_TEXT = """\
**I Hate The X — IHTX Bot**
One command, pipe-style syntax:

`t!ihtx effect=value,effect=value,...`

(Full help included in repository's README/help text.)
"""

# ---------- Global checks ----------

@bot.check
async def _global_checks(ctx: commands.Context) -> bool:
    # Channel blocked
    if ctx.channel.id in channel_blocks:
        return False
    # User blocked
    if ctx.author.id in blocklist:
        return False
    # Heavy command rate limiting
    if ctx.command and ctx.command.name in HEAVY_COMMANDS:
        ok, reason = _check_heavy_limit(ctx.author.id)
        if not ok:
            await ctx.reply(f"❌ {reason}")
            return False
    return True

# ---------- Helpers: download and ffmpeg ----------

async def download_attachment(attachment: discord.Attachment, dest: str):
    """Download a discord.Attachment to path `dest`."""
    async with aiohttp.ClientSession() as session:
        async with session.get(attachment.url) as resp:
            if resp.status != 200:
                raise ValueError(f"Failed to download attachment (HTTP {resp.status})")
            data = await resp.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


async def download_url(url: str, dest: str):
    """Download an arbitrary URL to path `dest`."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError(f"Failed to download URL (HTTP {resp.status})")
            data = await resp.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


async def _upload_to_catbox(file_path: str) -> str | None:
    """Upload a file to catbox.moe and return the URL, or None on failure."""
    try:
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()
        filename = Path(file_path).name
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field("userhash", CATBOX_USERHASH)
        form.add_field("fileToUpload", file_bytes, filename=filename)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://catbox.moe/user/api.php", data=form, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                text = await resp.text()
                if resp.status == 200 and text.startswith("https://"):
                    return text.strip()
                return None
    except Exception:
        return None


def _ffprobe(input_path: str, *args: str) -> str:
    """Run ffprobe and return stripped stdout."""
    cmd = ["ffprobe", "-v", "error"] + list(args) + [input_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def _ffprobe_duration(input_path: str) -> float:
    """Get duration in seconds."""
    out = _ffprobe(input_path, "-show_entries", "format=duration",
                   "-of", "csv=p=0")
    try:
        return float(out)
    except (ValueError, TypeError):
        return 0.0


def _ffprobe_video_info(input_path: str) -> dict:
    """Return width, height, duration, nb_frames, r_frame_rate."""
    info = {"width": 0, "height": 0, "duration": 0.0,
            "nb_frames": 0, "r_frame_rate": "30"}
    w = _ffprobe(input_path, "-select_streams", "v:0",
                 "-show_entries", "stream=width",
                 "-of", "default=nw=1:nk=1")
    h = _ffprobe(input_path, "-select_streams", "v:0",
                 "-show_entries", "stream=height",
                 "-of", "default=nw=1:nk=1")
    fc = _ffprobe(input_path, "-select_streams", "v:0",
                  "-show_entries", "stream=nb_frames",
                  "-of", "default=nokey=1:noprint_wrappers=1")
    fr = _ffprobe(input_path, "-select_streams", "v:0",
                  "-show_entries", "stream=r_frame_rate",
                  "-of", "default=nokey=1:noprint_wrappers=1")
    dur = _ffprobe_duration(input_path)
    try:
        info["width"] = int(w)
    except (ValueError, TypeError):
        pass
    try:
        info["height"] = int(h)
    except (ValueError, TypeError):
        pass
    try:
        info["nb_frames"] = int(fc)
    except (ValueError, TypeError):
        pass
    if fr:
        info["r_frame_rate"] = fr
    info["duration"] = dur
    return info


def _ffprobe_sample_rate(input_path: str) -> int:
    """Return the audio sample rate of the input file, defaulting to 44100."""
    sr = _ffprobe(input_path, "-select_streams", "a:0",
                  "-show_entries", "stream=sample_rate",
                  "-of", "default=nw=1:nk=1")
    try:
        return int(sr)
    except (ValueError, TypeError):
        return 44100


def _run_ffmpeg_raw(cmd: list[str], timeout: int = 180) -> tuple[bool, str]:
    """Run an arbitrary ffmpeg command. Returns (ok, stderr-or-empty)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr[-2000:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"FFmpeg timed out (>{timeout}s)"
    except Exception as e:
        return False, str(e)


def _probe_video_info(input_path: str) -> tuple[float, float]:
    """Return (duration_seconds, fps) for a video file via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", input_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout) if result.stdout else {}
    duration = float(data.get("format", {}).get("duration", 30))
    fps = 30.0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            r = stream.get("r_frame_rate", "30/1")
            try:
                num, den = r.split("/")
                fps = float(num) / float(den)
            except Exception:
                pass
            break
    return duration, fps


def run_ffmpeg(input_path: str, output_path: str, preset: str, is_video: bool) -> tuple[bool, str]:
    """Run ffmpeg using PRESET_FILTERS. Returns (ok, stderr-or-empty)."""
    cfg = PRESET_FILTERS.get(preset)
    if cfg is None:
        cfg = PRESET_FILTERS["chaos"]

    # Presets with a dynamic filter_complex template (e.g. sierpinskiransomware)
    if cfg.get("complex_template") and is_video:
        duration, fps = _probe_video_info(input_path)
        d = min(duration, 30.0)
        fr = round(fps)
        fc = cfg["complex_template"].format(d=d, fr=fr)
        maps = cfg.get("maps", [])
        audio_codec = cfg.get("audio_codec", "pcm_s16le")
        extra_codec_args = cfg.get("extra_codec_args", ["-preset", "fast", "-crf", "23"])
        map_flags: list[str] = []
        for m in maps:
            map_flags += ["-map", m]
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", fc,
            *map_flags,
            "-c:v", "libx264", *extra_codec_args,
            "-strict", "experimental",
            "-c:a", audio_codec,
            "-t", str(d),
            "-f", "mp4",
            output_path,
        ]
        return _run_ffmpeg_raw(cmd)

    if is_video:
        if cfg["complex"]:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex", cfg["complex"],
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "pcm_s16le",
                "-t", "30",
                output_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", cfg["vf"],
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "pcm_s16le",
                "-t", "30",
                output_path
            ]
    else:
        # Image → animated GIF
        if cfg["complex"]:
            fc = cfg["complex"] + ",split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", input_path,
                "-filter_complex", fc,
                "-t", "3",
                output_path
            ]
        else:
            vf = cfg["vf"] + ",split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", input_path,
                "-vf", vf,
                "-t", "3",
                output_path
            ]

    return _run_ffmpeg_raw(cmd)


def get_output_ext(input_ext: str, is_video: bool) -> str:
    return ".mov" if is_video else ".gif"

# ---------- HueHSV (ImageMagick haldclut) ----------

def _run_huehsv(
    input_path: str,
    output_path: str,
    hue: float,
) -> tuple[bool, str]:
    """Apply huehsv using ImageMagick haldclut + FFmpeg haldclut filter.

    Uses: magick hald:6 -modulate 100,100,<hue*200+100> hsv.ppm
    Then: ffmpeg -i input -vf "movie=hsv.ppm,[in]haldclut,format=rgba" -pix_fmt yuv420p output
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        hald_path = os.path.join(tmpdir, "hsv.ppm")
        modulate_val = hue * 200 + 100
        # Generate hald clut using ImageMagick
        cmd = ["magick", "hald:6", "-modulate", f"100,100,{modulate_val}", hald_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, f"Haldclut generation failed: {result.stderr}"

        # Apply via FFmpeg haldclut filter
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"movie={hald_path},[in]haldclut,format=rgba",
            "-pix_fmt", "yuv420p",
            output_path,
        ], timeout=180)
        if not ok:
            return False, f"FFmpeg haldclut failed: {err}"

        return True, ""


# ---------- ccshue (ImageMagick haldclut — hue/sat/gamma/gain/offset) ----------

def _run_ccshue(
    input_path: str,
    output_path: str,
    hue: float = 0.0,
    sat: float = 1.0,
    gamma: float = 1.0,
    gain: float = 1.0,
    offset: float = 0.0,
) -> tuple[bool, str]:
    """Apply color-correction via ImageMagick haldclut + FFmpeg haldclut filter.

    Parameters (all optional, pass only what you want to change):
        hue    — rotation in degrees (-180…180, default 0)
        sat    — saturation multiplier (default 1.0)
        gamma  — gamma correction (default 1.0)
        gain   — RGB gain / multiply (default 1.0)
        offset — add to every channel (-1…1, default 0)

    Generates ccs.ppm via:
        magick hald:6 [hue] [sat] [gamma] [gain] [offset] ccs.ppm
    Then applies:
        ffmpeg -i input -vf "movie=ccs.ppm,[in]haldclut" output
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        hald_path = os.path.join(tmpdir, "ccs.ppm")

        cmd = ["magick", "hald:6"]

        # Hue rotation (YUV-space rotation matrix via -fx)
        if abs(hue) > 0.001:
            angle_fx = (
                f"angle={hue}*pi/180; "
                "channel(u,"
                ".5+(u.g-.5)*cos(angle)-(u.b-.5)*sin(angle),"
                ".5+(u.g-.5)*sin(angle)+(u.b-.5)*cos(angle))"
            )
            cmd += ["-colorspace", "yuv", "-fx", angle_fx, "-colorspace", "srgb"]

        # Saturation (YUV-space scaling)
        if abs(sat - 1.0) > 0.001:
            sat_fx = (
                f"sat={sat}; "
                "channel(u,(u-.5)*sat+.5,(u-.5)*sat+.5)"
            )
            cmd += ["-colorspace", "yuv", "-fx", sat_fx, "-colorspace", "srgb"]

        # Gamma
        if abs(gamma - 1.0) > 0.001:
            cmd += ["-gamma", f"{gamma:.6g}"]

        # Gain (multiply all channels)
        if abs(gain - 1.0) > 0.001:
            cmd += ["-evaluate", "multiply", f"{gain:.6g}"]

        # Offset (add; 127.5 is half of 8-bit full range)
        if abs(offset) > 0.001:
            cmd += ["-evaluate", "add", f"{offset * 127.5:.4f}"]

        cmd.append(hald_path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, f"ccshue: ImageMagick failed: {result.stderr.strip()}"

        # Apply haldclut via FFmpeg
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
            "-vf", f"movie={hald_path},[in]haldclut",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            output_path,
        ], timeout=180)
        if not ok:
            return False, f"ccshue: FFmpeg haldclut failed: {err}"

        return True, ""


# ---------- Pipe effects engine ----------

PIPE_EFFECT_NAMES = {
    "hflip", "vflip", "invert", "negate", "grayscale", "sepia", "rotate",
    "ccshue", "brightness", "contrast", "saturation", "swapuv", "mirror",
    "zoom", "pinch&punch", "p&p", "pinchpunch", "gm91deform",
    "realgm4", "invertrgb", "invlum", "volume", "vibrato", "areverse", "vreverse",
    "channelblend", "huehsv", "multipitch", "mp", "multi", "lut",
    "syncaudio", "speed", "ffmpeg", "frei0r",
    "wave", "swirl",
    "sierpinskiransomware",
}


def _build_swirl_geq(strength: float, radius: float, xc: float, yc: float, fallout: str) -> str:
    """Build the FFmpeg geq pixel-displacement filter string for a swirl effect."""
    power = "" if fallout == "linear" else "^2"
    atten = (
        f"(if(lt(hypot(X-W*{xc},Y-H*{yc})+1e-6,min(W,H)*{radius}),"
        f"1-(hypot(X-W*{xc},Y-H*{yc})+1e-6)/(min(W,H)*{radius}),0){power})"
    )
    cos_expr = f"cos((atan2(Y-H*{yc},X-W*{xc}))+({strength}/180*PI)*{atten})"
    sin_expr = f"sin((atan2(Y-H*{yc},X-W*{xc}))+({strength}/180*PI)*{atten})"
    return (
        f"geq='p(W*{xc}+(hypot(X-W*{xc},Y-H*{yc})+1e-6)*{cos_expr},"
        f"H*{yc}+(hypot(X-W*{xc},Y-H*{yc})+1e-6)*{sin_expr})'"
    )

def _split_effect_params(value: str) -> list[str]:
    """Split effect parameters using the separators users commonly type.

    Commas are intentionally excluded — commas are now the top-level effect
    delimiter, so param values are separated by spaces, pipes, or semicolons.
    """
    return [p.strip() for p in re.split(r"[;|\s]+", value.strip()) if p.strip()]


def _split_pipe_segments(pipe_str: str) -> list[str]:
    """Split pipe_str on ',' while respecting parentheses.

    Commas inside ``ffmpeg(...)`` or any other ``name(...)`` block are
    treated as part of the args, not as segment delimiters.
    """
    segments: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in pipe_str:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
        else:
            current.append(ch)
    seg = "".join(current).strip()
    if seg:
        segments.append(seg)
    return segments


def _parse_pipe_effects(pipe_str: str) -> list[tuple[str, list[str]]]:
    """Parse pipe effects from IHTX custom syntax.

    Effects are separated with semicolons. Each effect can be written as
    ``name=value`` or ``name value``. Parameters can be separated with spaces,
    commas, semicolons, or pipes, so forms like ``swirl=1`` or
    ``lut=https://example.com/lut.cube`` both work.

    ``ffmpeg(...)`` is a special effect whose content is passed verbatim as raw
    FFmpeg args; semicolons inside the parens do *not* act as delimiters.
    """
    # VIDEO: <vf_filter> AUDIO: <af_filter> raw format — pass directly to FFmpeg
    if re.search(r'\b(VIDEO|AUDIO):', pipe_str, re.IGNORECASE):
        effects: list[tuple[str, list[str]]] = []
        vf_m = re.search(r'VIDEO:\s*(.*?)(?=\bAUDIO:|$)', pipe_str, re.IGNORECASE | re.DOTALL)
        af_m = re.search(r'AUDIO:\s*(.*?)(?=\bVIDEO:|$)', pipe_str, re.IGNORECASE | re.DOTALL)
        if vf_m:
            vf = vf_m.group(1).strip()
            if vf:
                effects.append(("__rawvf__", [vf]))
        if af_m:
            af = af_m.group(1).strip()
            if af:
                effects.append(("__rawaf__", [af]))
        return effects

    effects = []
    current_name = None
    current_params: list[str] = []

    for part in _split_pipe_segments(pipe_str):
        part = part.strip()
        if not part:
            continue
        # Strip optional annotations like (magick)
        part = re.sub(r"\s*\(magick\)\s*", "", part, flags=re.IGNORECASE)

        # ffmpeg(...) — raw FFmpeg args, captured verbatim
        ffmpeg_m = re.match(r'^ffmpeg\s*\((.+)\)\s*$', part, re.IGNORECASE | re.DOTALL)
        if ffmpeg_m:
            if current_name is not None:
                effects.append((current_name, current_params))
                current_name = None
                current_params = []
            effects.append(("ffmpeg", [ffmpeg_m.group(1).strip()]))
            continue

        if "=" in part:
            if current_name is not None:
                effects.append((current_name, current_params))
            name, value = part.split("=", 1)
            current_name = name.strip().lower()
            current_params = _split_effect_params(value)
            continue

        tokens = part.split(None, 1)
        possible_name = tokens[0].strip().lower()
        if possible_name in PIPE_EFFECT_NAMES:
            if current_name is not None:
                effects.append((current_name, current_params))
            current_name = possible_name
            current_params = _split_effect_params(tokens[1]) if len(tokens) > 1 else []
        elif current_name is not None:
            # Treat semicolon fragments after an effect as additional params,
            # e.g. lut=https://example.com/lut.cube
            current_params.extend(_split_effect_params(part))
        else:
            current_name = possible_name
            current_params = _split_effect_params(tokens[1]) if len(tokens) > 1 else []

    if current_name is not None:
        effects.append((current_name, current_params))
    return effects


def _build_ffmpeg_pipe_vf(name: str, params: list[str]) -> str | None:
    """Build a single FFmpeg -vf filter string for a pipe effect."""
    if name == "hflip":
        return "hflip"
    if name == "vflip":
        return "vflip"
    if name in ("invert", "negate"):
        return "negate"
    if name == "grayscale":
        return "colorchannelmixer=.299:.587:.114:0:.299:.587:.114:0:.299:.587:.114"
    if name == "sepia":
        return "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"
    if name == "rotate":
        angle = params[0] if params else "0"
        return f"rotate={angle}/180*PI"
    if name == "ccshue":
        # Handled as a special case in _apply_pipe_effects (needs ImageMagick preprocessing)
        return None
    if name == "frei0r":
        # frei0r=plugin:p1:p2:…  (colon-separated params)
        plugin = params[0] if params else ""
        if not plugin:
            return None
        rest = ":".join(params[1:]) if len(params) > 1 else ""
        return f"frei0r={plugin}:{rest}" if rest else f"frei0r={plugin}"
    if name == "brightness":
        val = params[0] if params else "0"
        return f"eq=brightness={val}"
    if name == "contrast":
        val = params[0] if params else "1"
        return f"eq=contrast={val}"
    if name == "saturation":
        val = params[0] if params else "1"
        return f"hue=s={val}"
    if name == "swapuv":
        return "swapuv"
    if name == "mirror":
        first = (params[0] if params else "").lower().strip()
        _mirror_aliases = {"l": "left", "r": "right", "t": "top", "b": "bottom"}
        first_resolved = _mirror_aliases.get(first, first)
        _preset_names = {"left", "right", "top", "bottom"}
        if first_resolved in _preset_names:
            # Legacy preset mode: left / right / top / bottom
            _mirror_vf = {
                "left":   "split[_ma][_mb];[_ma]crop=iw/2:ih:0:0[_mL];[_mb]crop=iw/2:ih:0:0,hflip[_mR];[_mL][_mR]hstack",
                "right":  "split[_ma][_mb];[_ma]crop=iw/2:ih:iw/2:0,hflip[_mL];[_mb]crop=iw/2:ih:iw/2:0[_mR];[_mL][_mR]hstack",
                "top":    "split[_ma][_mb];[_ma]crop=iw:ih/2:0:0[_mT];[_mb]crop=iw:ih/2:0:0,vflip[_mB];[_mT][_mB]vstack",
                "bottom": "split[_ma][_mb];[_ma]crop=iw:ih/2:0:ih/2,vflip[_mT];[_mb]crop=iw:ih/2:0:ih/2[_mB];[_mT][_mB]vstack",
            }
            return _mirror_vf.get(first_resolved, _mirror_vf["left"])
        else:
            # Parametric mode: mirror=angle[,cx,cy]
            # Folds the image along a line through (cx,cy) at `angle` degrees.
            # angle=90  → horizontal fold (default)
            # angle=0   → vertical fold
            # angle=45  → diagonal fold
            try:
                A = float(first) if first else 90.0
            except ValueError:
                A = 90.0
            cx = float(params[1]) if len(params) > 1 else 0.5
            cy = float(params[2]) if len(params) > 2 else 0.5
            # In the 2x canvas (W=2·OW, H=2·OH) the fold line's Y position is:
            #   fold_y = H/2 + (cx-0.5)*(W/2)*sin(A°) + (cy-0.5)*(H/2)*cos(A°)
            a_rad = f"{A}/180*PI"
            cx_off = cx - 0.5
            cy_off = cy - 0.5
            cx_term = (
                f"+{cx_off:.6f}*(W/2)*sin({a_rad})" if cx_off >= 0
                else f"{cx_off:.6f}*(W/2)*sin({a_rad})"
            )
            cy_term = (
                f"+{cy_off:.6f}*(H/2)*cos({a_rad})" if cy_off >= 0
                else f"{cy_off:.6f}*(H/2)*cos({a_rad})"
            )
            fold_y = f"H/2{cx_term}{cy_term}"
            return (
                f"rotate={A}/180*PI:iw*2:ih*2,"
                f"geq='if(gte(Y,{fold_y}),p(X,2*({fold_y})-Y),p(X,Y))',"
                f"format=yuv420p,"
                f"rotate={A}/-180*PI,"
                f"crop=iw/2:ih/2,"
                f"format=yuv420p"
            )
    if name == "zoom":
        amount = params[0] if params else "1.1"
        zoom_geq = f"p((W/2)+(X-(W/2))/{amount},(H/2)+(Y-(H/2))/{amount})"
        return (
            f"format=yuv444p,rotate=0:iw*1.1:ih*1.1,"
            f"geq='{zoom_geq}',"
            f"scale=iw:ih,crop=iw:ih,format=yuv420p"
        )
    if name in ("pinch&punch", "p&p", "pinchpunch"):
        strength = params[0] if len(params) > 0 else "1"
        radius = params[1] if len(params) > 1 else "0.5"
        cx = params[2] if len(params) > 2 else "0.5"
        cy = params[3] if len(params) > 3 else "0.5"
        geq_expr = (
            f"p(W*{cx}+(X-W*{cx})*max(1-({strength})*gauss(-3.3333*pow(hypot((X-W*{cx})/(W*{radius}),(Y-H*{cy})/(H*{radius})),2)),0),"
            f"H*{cy}+(Y-H*{cy})*max(1-({strength})*gauss(-3.3333*pow(hypot((X-W*{cx})/(W*{radius}),(Y-H*{cy})/(H*{radius})),2)),0))"
        )
        return f"format=yuv444p,geq='{geq_expr}',scale=iw:ih,format=yuv420p"
    if name == "vreverse":
        return "reverse"
    if name == "gm91deform":
        deform_geq = (
            "p((W/2)+((X-W/2)/lerp(1,asin(sin(-Y/H)),0.164))/1.22"
            "+((Y-H/2)*(-0.136))+((0.047*W)*pow((Y-H/2)/(H/2),2))+(-W/40)"
            ",(H/2)+((Y-H/2)/1.27)/lerp(1,sin((X/W)*PI),0.12)"
            "-(((0.014)*H)*pow((X-W/2)/(W/2),2))+((X-W/2)*(0.12))-(1.2))"
        )
        return (
            f"format=yuv444p,scale=360:360,setsar=1:1,rotate=0:iw*1.05:ih*1.05,"
            f"geq='{deform_geq}',"
            f"scale=640*1.05:360*1.05,crop=640:360:(in_w-in_h)/2+8,scale=iw:ih,setsar=1,format=yuv420p"
        )
    if name == "realgm4":
        return "curves=r='0/0 0.5/0.75 1/0':g='0/0 0.5/0.75 1/0':b='0/0 0.5/0.75 1/0',format=yuv420p"
    if name == "invertrgb":
        r_inv = params[0] if len(params) > 0 else "1"
        g_inv = params[1] if len(params) > 1 else "0"
        b_inv = params[2] if len(params) > 2 else "0"
        r_curve = "0/1 1/0" if r_inv == "1" else "0/0 1/1"
        g_curve = "0/1 1/0" if g_inv == "1" else "0/0 1/1"
        b_curve = "0/1 1/0" if b_inv == "1" else "0/0 1/1"
        return f"curves=r='{r_curve}':g='{g_curve}':b='{b_curve}'"
    if name == "invlum":
        return "curves=all='0/1 1/0'"
    if name == "volume":
        val = params[0] if params else "1"
        return f"volume={val}"
    if name == "vibrato":
        freq = params[0] if len(params) > 0 else "5"
        depth = params[1] if len(params) > 1 else "0.5"
        return f"vibrato=f={freq}:d={depth}"
    if name == "areverse":
        return "areverse"
    if name == "channelblend":
        r = params[0] if len(params) > 0 else "r"
        g = params[1] if len(params) > 1 else "g"
        b = params[2] if len(params) > 2 else "b"
        ch_map = {"r": "1:0:0", "g": "0:1:0", "b": "0:0:1"}
        rr = ch_map.get(r, "1:0:0")
        gg = ch_map.get(g, "0:1:0")
        bb = ch_map.get(b, "0:0:1")
        return (
            f"colorchannelmixer=rr={rr.split(':')[0]}:rg={rr.split(':')[1]}:rb={rr.split(':')[2]}"
            f":gr={gg.split(':')[0]}:gg={gg.split(':')[1]}:gb={gg.split(':')[2]}"
            f":br={bb.split(':')[0]}:bg={bb.split(':')[1]}:bb={bb.split(':')[2]}"
        )
    return None




def _apply_pipe_effects(
    input_path: str,
    output_path: str,
    effects: list[tuple[str, list[str]]],
) -> tuple[bool, str]:
    """Apply pipe effects sequentially — each effect is rendered individually
    before the next begins (no filter batching).
    """
    if not effects:
        ok, err = _run_ffmpeg_raw(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], timeout=60)
        return ok, err

    with tempfile.TemporaryDirectory() as tmpdir:
        current = input_path

        for i, (name, params) in enumerate(effects):
            is_last = (i == len(effects) - 1)
            out = output_path if is_last else os.path.join(tmpdir, f"pipe_{i}.mp4")

            # ccshue — ImageMagick haldclut with hue/sat/gamma/gain/offset
            if name == "ccshue":
                def _p(idx, default):
                    try:
                        return float(params[idx]) if idx < len(params) else default
                    except (ValueError, TypeError):
                        return default
                ok, err = _run_ccshue(
                    current, out,
                    hue=_p(0, 0.0),
                    sat=_p(1, 1.0),
                    gamma=_p(2, 1.0),
                    gain=_p(3, 1.0),
                    offset=_p(4, 0.0),
                )
                if not ok:
                    return False, err
                current = out
                continue

            # ImageMagick huehsv
            if name == "huehsv":
                val = float(params[0]) if params else 0.5
                ok, err = _run_huehsv(current, out, val)
                if not ok:
                    return False, err
                current = out
                continue

            # Rubber Band R3 multipitch
            if name in ("multipitch", "mp", "multi"):
                ok, err = _run_multipitch_rb3(current, out, params)
                if not ok:
                    return False, err
                current = out
                continue

            # LUT / 3D LUT via lut3d filter
            if name == "lut":
                lut_url = params[0] if len(params) > 0 else ""
                if not lut_url:
                    return False, "lut effect requires a URL parameter."
                lut_path = os.path.join(tmpdir, f"lut_{i}.cube")
                try:
                    import urllib.request
                    import ssl
                    ssl_ctx = ssl.create_default_context()
                    req = urllib.request.Request(
                        lut_url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; IHTX-Bot)"}
                    )
                    with urllib.request.urlopen(req, context=ssl_ctx, timeout=60) as resp:
                        with open(lut_path, "wb") as f:
                            f.write(resp.read())
                except Exception as e:
                    return False, f"Failed to download LUT from {lut_url}: {e}"
                cmd = [
                    "ffmpeg", "-y", "-i", current,
                    "-vf", f"lut3d={lut_path},format=yuv420p",
                    "-c:a", "pcm_s24le",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-movflags", "+faststart",
                    out,
                ]
                ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                if not ok:
                    return False, f"lut3d failed: {err}"
                current = out
                continue

            # invlum — apply InvertLuminosity LUT
            if name in ("invlum", "il"):
                lut_path = str(INVLUM_LUT_FILE.resolve())
                if not INVLUM_LUT_FILE.exists():
                    return False, "InvertLuminosity.cube LUT file not found."
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current,
                    "-vf", f"lut3d={lut_path}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s24le",
                    out,
                ]
                ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                if not ok:
                    return False, f"invlum failed: {err}"
                current = out
                continue

            # swirl — geq-based rotational pixel displacement
            if name == "swirl":
                def _sp(idx, default):
                    try:
                        return params[idx] if idx < len(params) else default
                    except Exception:
                        return default

                strength = float(_sp(0, 180))
                radius   = float(_sp(1, 0.5))
                xc       = float(_sp(2, 0.5))
                yc       = float(_sp(3, 0.5))
                fallout  = _sp(4, "quad").lower()
                if fallout not in ("linear", "quad"):
                    fallout = "quad"
                is1to1_raw = str(_sp(5, "false")).lower()
                is1to1 = is1to1_raw in ("1", "true", "t", "y", "yes", "+", "on")

                geq = _build_swirl_geq(strength, radius, xc, yc, fallout)

                if is1to1:
                    info = _ffprobe_video_info(current)
                    w_px, h_px = info.get("width", 0), info.get("height", 0)
                    if w_px and h_px:
                        vf = f"format=yuv444p,scale={h_px}:{h_px},{geq},scale={w_px}:{h_px},setsar=1:1,format=yuv420p"
                    else:
                        vf = f"format=yuv444p,{geq},scale=iw:ih,format=yuv420p"
                else:
                    vf = f"format=yuv444p,{geq},scale=iw:ih,format=yuv420p"

                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current,
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "copy",
                    out,
                ]
                ok, err = _run_ffmpeg_raw(cmd, timeout=300)
                if not ok:
                    return False, f"swirl failed: {err}"
                current = out
                continue

            # Raw VIDEO:/AUDIO: filters — each rendered immediately
            if name == "__rawvf__":
                vf_str = params[0] if params else ""
                if vf_str:
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                        "-i", current, "-vf", vf_str,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-pix_fmt", "yuv420p", "-c:a", "pcm_s24le", out,
                    ]
                    ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                    if not ok:
                        return False, f"Video filter failed: {err}"
                    current = out
                continue

            if name == "__rawaf__":
                af_str = params[0] if params else ""
                if af_str:
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                        "-i", current, "-af", af_str,
                        "-c:v", "copy", "-c:a", "pcm_s16le", out,
                    ]
                    ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                    if not ok:
                        return False, f"Audio filter failed: {err}"
                    current = out
                continue

            # Speed: change playback rate (video setpts + audio atempo chain)
            if name == "speed":
                try:
                    spd = float(params[0]) if params else 1.0
                except (ValueError, IndexError):
                    spd = 1.0
                spd = max(0.01, min(spd, 100.0))
                # video: setpts = 1/speed * PTS
                vf_speed = f"setpts={1.0/spd:.6f}*PTS"
                # audio: chain atempo filters to stay in FFmpeg's 0.5-100 range
                af_speed = _build_atempo_chain(spd)
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current,
                    "-vf", vf_speed,
                    "-af", af_speed,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    out,
                ]
                ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                if not ok:
                    return False, f"speed failed: {err}"
                current = out
                continue

            # ffmpeg(...) — raw FFmpeg args pipe step
            if name == "ffmpeg":
                raw_args = params[0] if params else ""
                if not raw_args:
                    return False, "ffmpeg() pipe step requires args inside the parentheses."
                try:
                    user_args = shlex.split(raw_args)
                except ValueError as e:
                    return False, f"ffmpeg() pipe step — invalid args: {e}"
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current,
                ] + user_args + [out]
                ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                if not ok:
                    return False, f"ffmpeg() pipe step failed: {err}"
                current = out
                continue

            # Named audio filters — rendered immediately
            if name in ("volume", "vibrato", "areverse"):
                af = _build_ffmpeg_pipe_vf(name, params)
                if af:
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                        "-i", current, "-af", af,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out,
                    ]
                    ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                    if not ok:
                        return False, f"Audio filter '{name}' failed: {err}"
                    current = out
                    continue

            # shake — pixel-displacement shake using geq, crops back to original dims
            if name == "shake":
                try:
                    h_amt = float(params[0]) if len(params) > 0 else 3.0
                except (ValueError, TypeError):
                    h_amt = 3.0
                try:
                    v_amt = float(params[1]) if len(params) > 1 else 0.0
                except (ValueError, TypeError):
                    v_amt = 0.0
                try:
                    vinfo = _ffprobe_video_info(current)
                    vid_w = int(vinfo["width"])
                    vid_h = int(vinfo["height"])
                except Exception:
                    vid_w, vid_h = 0, 0
                if vid_w <= 0 or vid_h <= 0:
                    return False, "shake: could not probe video dimensions."
                shake_vf = (
                    f"rotate=0:iw*1.1:ih*1.1,format=yuv444p,"
                    f"geq='p(X+{h_amt}*(2*mod(1000*sin(N*12.9898),1)-1),"
                    f"Y+{v_amt}*(2*mod(1000*sin(N+1000)*78.233,1)-1))',"
                    f"crop={vid_w}:{vid_h},format=yuv420p"
                )
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current, "-vf", shake_vf,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s24le", out,
                ]
                ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                if not ok:
                    return False, f"shake failed: {err}"
                current = out
                continue

            # wave — sinusoidal pixel-displacement distortion
            if name == "wave":
                def _wp(idx, default):
                    try:
                        return float(params[idx]) if idx < len(params) else default
                    except (ValueError, TypeError):
                        return default
                h_speed   = _wp(0, 1.0)
                h_freq    = _wp(1, 1.0)
                h_amp     = _wp(2, 1.0)
                h_phase   = _wp(3, 0.0)
                v_speed   = _wp(4, 1.0)
                v_freq    = _wp(5, 1.0)
                v_amp     = _wp(6, 1.0)
                v_phase   = _wp(7, 0.0)
                sep       = len(params) > 8 and params[8].strip() in ("1", "true", "sep", "yes")
                noclip    = len(params) > 9 and params[9].strip() in ("1", "true", "noclip", "yes")

                drawbox = "drawbox=t=1," if noclip else ""
                h_wave = (
                    f"sin((T*5*{v_speed}+({v_phase}*15))+(Y/H)*(PI*{v_freq}))*(-15*{v_amp})"
                )
                v_wave = (
                    f"sin((T*5*{h_speed}+({h_phase}*15))+(X/W)*(PI*{h_freq}))*(-15*{h_amp})"
                )

                def _wave_cmd(inp, op, x_expr, y_expr):
                    vf_str = f"{drawbox}format=yuv444p,geq='p({x_expr},{y_expr})',format=yuv420p"
                    return [
                        "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                        "-i", inp, "-vf", vf_str,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-pix_fmt", "yuv420p", "-c:a", "pcm_s24le", op,
                    ]

                if sep:
                    mid = os.path.join(tmpdir, f"wave_mid_{i}.mp4")
                    ok, err = _run_ffmpeg_raw(
                        _wave_cmd(current, mid, f"X-({h_wave})", "Y"), timeout=180
                    )
                    if not ok:
                        return False, f"wave (h pass) failed: {err}"
                    ok, err = _run_ffmpeg_raw(
                        _wave_cmd(mid, out, "X", f"Y-({v_wave})"), timeout=180
                    )
                    if not ok:
                        return False, f"wave (v pass) failed: {err}"
                else:
                    ok, err = _run_ffmpeg_raw(
                        _wave_cmd(current, out, f"X-({h_wave})", f"Y-({v_wave})"), timeout=180
                    )
                    if not ok:
                        return False, f"wave failed: {err}"
                current = out
                continue

            # Named video filters — rendered immediately
            vf = _build_ffmpeg_pipe_vf(name, params)
            if vf:
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
                    "-i", current, "-vf", vf,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s24le", out,
                ]
                ok, err = _run_ffmpeg_raw(cmd, timeout=180)
                if not ok:
                    return False, f"Filter '{name}' failed: {err}"
                current = out
                continue

            # sierpinskiransomware — 2×2 Sierpinski-style grid via preset
            if name == "sierpinskiransomware":
                ok, err = run_ffmpeg(current, out, "sierpinskiransomware", True)
                if not ok:
                    return False, f"sierpinskiransomware failed: {err}"
                current = out
                continue

            return False, f"Unknown pipe effect: {name}"

        if current != output_path:
            shutil.copyfile(current, output_path)

    return True, ""


# ---------- IHTX TagScript workflow ----------

def _parse_ihtx_custom_args(args: str) -> tuple[int, str, str, str, str] | None:
    """Parse TagScript-style IHTX custom syntax.

    Syntax:
      <exports> <duration_expr> <no_trim> <export_file_format> <pipe effects>

    Example:
      10 0.483 - mp4 huehsv 0.5;negate;multipitch=1|6|7
    """
    parts = shlex.split(args)
    if len(parts) <= 4:
        return None
    try:
        exports = int(parts[0])
    except ValueError:
        return None
    if exports == 0:
        return None
    duration_expr = parts[1]
    no_trim = parts[2]
    export_format = parts[3].lstrip(".") or "mp4"
    pipe_effects = " ".join(parts[4:]).strip()
    if not pipe_effects:
        return None
    return exports, duration_expr, no_trim, export_format, pipe_effects


def _pipe_effects_label(pipe_str: str) -> str:
    """Extract just the effect names from a pipe effects string for display."""
    names = []
    for part in pipe_str.split(";"):
        part = part.strip()
        if not part:
            continue
        name = part.split("=")[0].split()[0].lower()
        if name:
            names.append(name)
    return ",".join(names) or pipe_str[:40]


def _safe_awk_duration(duration_expr: str, vidlen: float) -> tuple[bool, str]:
    """Evaluate the tag duration expression using awk like the original TagScript."""
    if not duration_expr or len(duration_expr) > 200:
        return False, "Invalid duration expression."
    if any(ch in duration_expr for ch in "\n\r\0"):
        return False, "Duration expression cannot contain newlines."
    try:
        result = subprocess.run(
            ["awk", "-v", f"vidlen={vidlen}", f"BEGIN{{ printf {duration_expr} }}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        return False, f"Duration expression failed: {e}"
    if result.returncode != 0:
        return False, result.stderr[-1000:] or "Duration expression failed."
    value = result.stdout.strip()
    try:
        dur = float(value)
    except ValueError:
        return False, f"Duration expression did not produce a number: {value!r}"
    if not math.isfinite(dur) or dur <= 0:
        return False, "Duration must be a positive finite number."
    return True, str(min(dur, MAX_DURATION))


def _concat_codec_args(output_format: str) -> list[str]:
    """Return final concat codec args matching the IHTX TagScript cases."""
    fmt = output_format.lower().lstrip(".")
    if fmt == "mkv":
        return ["-c:v", "mpeg2video", "-q:v", "1", "-c:a", "flac", "-pix_fmt", "yuv420p", "-bufsize", "64M"]
    if fmt == "mxf":
        return ["-c:v", "mpeg2video", "-qscale", "1", "-qmin", "1", "-c:a", "pcm_s16le", "-ar", "48000", "-pix_fmt", "yuv420p", "-bufsize", "64M"]
    if fmt == "mov":
        return ["-c:v", "libx264", "-profile:v", "high422", "-level:v", "5", "-tune", "zerolatency", "-q:v", "1", "-crf", "30", "-preset", "superfast", "-c:a", "aac", "-q:a", "10", "-b:a", "192K", "-aac_coder", "fast", "-pix_fmt", "yuv420p", "-bufsize", "64M"]
    if fmt == "mp4":
        return ["-c:v", "libx264", "-profile:v", "high422", "-level:v", "5", "-tune", "zerolatency", "-q:v", "1", "-crf", "30", "-preset", "superfast", "-c:a", "flac", "-pix_fmt", "yuv420p", "-bufsize", "64M"]
    if fmt == "avi":
        return ["-c:v", "mpeg2video", "-c:a", "flac", "-pix_fmt", "yuv420p"]
    return ["-pix_fmt", "yuv420p", "-bufsize", "64M"]


def _run_ihtx_tagscript_workflow(
    input_path: str,
    output_path: str,
    exports: int,
    duration_expr: str,
    no_trim: str,
    export_format: str,
    pipe_effects_str: str,
) -> tuple[bool, str]:
    """Run custom IHTX using the TagScript-style shell workflow with pipe effects.

    Pipe effects are applied sequentially to each export.
    Output is always mp4.
    """
    if abs(exports) > MAX_REPETITIONS:
        exports = MAX_REPETITIONS if exports > 0 else -MAX_REPETITIONS

    if not re.fullmatch(r"[A-Za-z0-9]+", export_format):
        return False, "Export file format must be alphanumeric (example: mp4)."

    effects = _parse_pipe_effects(pipe_effects_str)
    if not effects:
        return False, "No pipe effects provided."

    vidlen = _ffprobe_duration(input_path)
    if vidlen <= 0:
        return False, "Could not read input duration."
    dur_ok, dur_or_error = _safe_awk_duration(duration_expr, vidlen)
    if not dur_ok:
        return False, dur_or_error
    dur = dur_or_error

    extension = "mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        base = os.path.join(tmpdir, "0.mp4")
        final_output = os.path.join(tmpdir, f"icfplus.{extension}")

        warmup = os.path.join(tmpdir, "a.mp4")
        _run_ffmpeg_raw([
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", "https://file.garden/aTXso15ukD3mnuPI/resized.mp4",
            "-vf", "scale=4:4,setsar=1:1,geq=r=128:g=128:b=128",
            "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-an", "-t", "0.03", warmup,
        ], timeout=60)

        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-stream_loop", "-1", "-i", input_path,
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "16M",
            "-c:a", "flac", "-t", dur, "-movflags", "+faststart", base,
        ], timeout=180)
        if not ok:
            return False, f"Base render failed: {err}"

        no_trim_enabled = no_trim.lower() in {"true", "yes"}
        total_exports = abs(exports)
        previous = base
        for i in range(1, total_exports + 2):
            current = os.path.join(tmpdir, f"{i}.{export_format}")
            ok, err = _apply_pipe_effects(previous, current, effects)
            if not ok:
                return False, f"Export {i} failed: {err}"
            # Validate output is non-empty and has video frames before next iteration
            if not os.path.exists(current) or os.path.getsize(current) < 64:
                return False, f"Export {i} produced an empty or invalid file."
            probe = _ffprobe(
                current,
                "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames",
                "-count_frames",
                "-of", "default=nw=1:nk=1",
            ).strip()
            if probe == "0":
                return False, f"Export {i} has no video frames (likely a filter or codec issue with format '{export_format}')."
            previous = current

        concat_list = os.path.join(tmpdir, "concat.txt")
        sequence = range(total_exports, 0, -1) if exports < 0 else range(1, total_exports + 1)
        with open(concat_list, "w") as f:
            for i in sequence:
                f.write(f"file '{os.path.join(tmpdir, f'{i}.{export_format}')}'\n")

        concat_cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
        ]
        concat_cmd.extend(_concat_codec_args(extension))
        concat_cmd.extend(["-movflags", "+faststart", final_output])
        ok, err = _run_ffmpeg_raw(concat_cmd, timeout=300)
        if not ok:
            return False, f"Concat failed: {err}"
        shutil.copyfile(final_output, output_path)

    return True, ""


# ---------- Multipitch (Rubber Band R3 pitch-shift pipeline) ----------

MAX_PITCHES = 64

# Path to the Signalsmith multi-pitch binary (downloaded at startup)
_MULTIPITCH_BIN = os.path.join(os.path.dirname(__file__), "fileaa")
_MULTIPITCH_URL = "https://file.garden/aTXso15ukD3mnuPI/multipitch"


def _ensure_multipitch_bin() -> bool:
    """Download the multipitch binary if it isn't already present and executable.
    Returns True if the binary is ready, False on failure.
    """
    if os.path.isfile(_MULTIPITCH_BIN) and os.access(_MULTIPITCH_BIN, os.X_OK):
        return True
    try:
        import urllib.request
        tmp = _MULTIPITCH_BIN + ".tmp"
        req = urllib.request.Request(
            _MULTIPITCH_URL,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(tmp, "wb") as f:
                f.write(resp.read())
        os.chmod(tmp, 0o755)
        os.replace(tmp, _MULTIPITCH_BIN)
        print(f"[multipitch] binary downloaded → {_MULTIPITCH_BIN}")
        return True
    except Exception as exc:
        print(f"[multipitch] binary download failed: {exc}")
        return False


def _run_multipitch_rb3(
    input_path: str,
    output_path: str,
    pitch_values: list[str],
) -> tuple[bool, str]:
    """Multi-voice pitch shift using the Signalsmith fileaa binary + FFmpeg.

    Pipeline:
      1. Validate & deduplicate semitone values.
      2. Extract 16-bit PCM WAV audio from the input.
      3. Run fileaa with all pitches as a comma-separated list (single call).
      4. Remux the output WAV back over the original video stream, or emit
         audio-only when the input has no video.

    Accepts ; | , or whitespace as pitch separators.
    """
    # ── 1. Flatten & parse pitch values ──────────────────────────────────────
    flattened: list[str] = []
    for pv in pitch_values:
        flattened.extend(
            v.strip()
            for v in re.split(r"[;|,\s]+", pv)
            if v.strip()
        )

    if not flattened:
        return False, "❌ No pitch values specified."

    if len(flattened) > MAX_PITCHES:
        return False, f"❌ Too many pitch values (maximum: {MAX_PITCHES})."

    semitones: list[float] = []
    seen: set[float] = set()
    for raw in flattened:
        try:
            val = float(raw)
        except ValueError:
            return False, f"❌ Invalid pitch value: {raw!r} — must be a number in semitones."
        if not math.isfinite(val):
            return False, f"❌ Invalid pitch value: {raw!r} — must be finite."
        if val not in seen:
            seen.add(val)
            semitones.append(val)

    # ── 2. Ensure binary is available ────────────────────────────────────────
    if not _ensure_multipitch_bin():
        return False, "❌ Multipitch binary unavailable — download failed."

    # ── 3. Probe input ───────────────────────────────────────────────────────
    has_video = bool(_ffprobe(
        input_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
    ).strip())

    actual_dur = _ffprobe_duration(input_path)
    cap = str(int(min(actual_dur, MAX_DURATION)) + 1) if actual_dur > 0 else str(MAX_DURATION)

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── 4. Extract 16-bit PCM WAV (required by fileaa) ───────────────────
        base_wav = os.path.join(tmpdir, "base.wav")
        ok, err = _run_ffmpeg_raw([
            "ffmpeg", "-y",
            "-t", cap,
            "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2",
            "-c:a", "pcm_s16le",
            "-t", cap,
            base_wav,
        ], timeout=120)
        if not ok:
            return False, f"Audio extraction failed: {err}"

        # ── 5. Run fileaa (all pitches in one call, comma-separated) ─────────
        pitch_arg = ",".join(
            str(int(s)) if s == int(s) else str(s)
            for s in semitones
        )
        out_wav = os.path.join(tmpdir, "pitched.wav")
        result = subprocess.run(
            [_MULTIPITCH_BIN, base_wav, out_wav, pitch_arg],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            # ── Fallback: rubberband CLI — one pass per voice, then amix ─────
            rb_bin = shutil.which("rubberband")
            if not rb_bin:
                return False, f"❌ Multipitch processing failed: {result.stderr[-800:]}"
            voice_wavs: list[str] = []
            for idx, st in enumerate(semitones):
                v_wav = os.path.join(tmpdir, f"voice_{idx}.wav")
                pitch_flag = f"-p{st:+.4f}" if st != 0 else "-p+0.0"
                rb_res = subprocess.run(
                    [rb_bin, pitch_flag, "-t1", base_wav, v_wav],
                    capture_output=True, text=True, timeout=300,
                )
                if rb_res.returncode != 0:
                    return False, f"❌ rubberband fallback failed (voice {idx}): {rb_res.stderr[-600:]}"
                voice_wavs.append(v_wav)
            # Mix all voices with FFmpeg amix
            mix_cmd = ["ffmpeg", "-y"]
            for vw in voice_wavs:
                mix_cmd += ["-i", vw]
            mix_cmd += [
                "-filter_complex", f"amix=inputs={len(voice_wavs)}:normalize=0",
                "-c:a", "pcm_s16le",
                out_wav,
            ]
            ok_mix, err_mix = _run_ffmpeg_raw(mix_cmd, timeout=180)
            if not ok_mix:
                return False, f"❌ amix failed: {err_mix}"

        # ── 6. Remux pitched audio with original video (or audio-only) ───────
        # Use -c:v copy to preserve original timestamps exactly — re-encoding
        # would reset the timebase and cause the video to play back faster.
        if has_video:
            dur_flag = str(round(actual_dur, 6)) if actual_dur > 0 else cap
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-t", cap, "-i", input_path,
                "-i", out_wav,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "pcm_s24le",
                "-t", dur_flag,
                output_path,
            ], timeout=300)
        else:
            ok, err = _run_ffmpeg_raw([
                "ffmpeg", "-y",
                "-i", out_wav,
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ], timeout=180)

        if not ok:
            return False, f"Remux failed: {err}"

    return True, ""


# Keep the old name as an alias so legacy pipe-effect calls still resolve
_run_multipitch = _run_multipitch_rb3





def _build_atempo_chain(speed: float) -> str:
    """Build an atempo filter chain that handles FFmpeg's 0.5–100.0 bounds.

    FFmpeg's atempo filter only accepts values between 0.5 and 100.0.
    For speeds outside this range, chain multiple atempo filters.
    """
    if 0.5 <= speed <= 100.0:
        return f"atempo={speed}"
    # Chain multiple atempo filters
    parts = []
    remaining = speed
    while remaining > 100.0:
        parts.append("atempo=100.0")
        remaining /= 100.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining}")
    return ",".join(parts)


# ---------- Syncaudio (video/audio duration sync) ----------

def _run_syncaudio(
    input_path: str,
    output_path: str,
    alt_mode: bool = False,
) -> tuple[bool, str]:
    """Sync video and audio durations by adjusting playback speed.

    Default mode: stretch/compress video PTS to match audio duration.
    Alt mode:     adjust audio tempo (atempo) to match video duration.

    Splits the input into a video-only and audio-only temp file so that
    -stream_loop -1 can be used on audio and -t pins the output length.

    Returns (ok, info_string_or_error).
    """
    import tempfile, os as _os

    tmpdir = tempfile.mkdtemp(prefix="syncaudio_")
    v_path = _os.path.join(tmpdir, "v.mp4")
    a_path = _os.path.join(tmpdir, "a.wav")

    try:
        # Split: video-only
        ok, err = _run_ffmpeg_raw(
            ["ffmpeg", "-y", "-i", input_path, "-an", "-c:v", "copy", v_path],
            timeout=120,
        )
        if not ok:
            return False, f"Video split failed: {err}"

        # Split: audio-only
        ok, err = _run_ffmpeg_raw(
            ["ffmpeg", "-y", "-i", input_path, "-vn", a_path],
            timeout=120,
        )
        if not ok:
            return False, f"Audio split failed: {err}"

        # Durations from the split files (more reliable than muxed container)
        vd = _ffprobe_duration(v_path)
        ad_raw = _ffprobe(a_path, "-select_streams", "a:0",
                          "-show_entries", "format=duration",
                          "-of", "csv=p=0")
        try:
            ad = float(ad_raw)
        except (ValueError, TypeError):
            ad = 0.0

        if vd <= 0 or ad <= 0:
            return False, f"Could not determine durations (video={vd:.3f}s, audio={ad:.3f}s)"

        # Frame rate from original
        fr_out = _ffprobe(input_path, "-select_streams", "v:0",
                          "-show_entries", "stream=r_frame_rate",
                          "-of", "default=nokey=1:noprint_wrappers=1")

        if alt_mode:
            # Alt mode: adjust audio speed to match video duration
            speed = ad / vd
            atempo_filter = _build_atempo_chain(speed)
            cmd = [
                "ffmpeg", "-y",
                "-i", v_path,
                "-stream_loop", "-1", "-i", a_path,
                "-af", atempo_filter,
                "-map", "0:v", "-map", "1:a",
                "-t", str(vd),
                "-c:v", "copy",
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            # Default mode: stretch video PTS to match audio duration
            speed = vd / ad
            vf = f"setpts=1/({vd}/{ad})*PTS"
            if fr_out:
                vf += f",fps={fr_out}"
            cmd = [
                "ffmpeg", "-y",
                "-i", v_path,
                "-stream_loop", "-1", "-i", a_path,
                "-vf", vf,
                "-map", "0:v", "-map", "1:a",
                "-t", str(vd),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                "-movflags", "+faststart",
                output_path,
            ]

        ok, err = _run_ffmpeg_raw(cmd, timeout=300)
        if not ok:
            return False, f"Sync failed: {err}"

    finally:
        for p in (v_path, a_path):
            try:
                _os.unlink(p)
            except OSError:
                pass
        try:
            _os.rmdir(tmpdir)
        except OSError:
            pass

    diff = vd - ad
    info = (
        f"Video: {vd:.3f}s\n"
        f"Audio: {ad:.3f}s\n\n"
        f"Speed Used: {speed:.6f}\n"
        f"Diff: {diff:.6f}"
    )
    return True, info

# ---------- Preview1280 (TV-simulator montage) ----------

async def _ensure_displacement_map(workdir: str) -> str:
    """Ensure the TV simulator displacement map exists, downloading if needed.

    Returns the path to the .mov file.
    """
    # First check if the bundled copy exists
    bundled = Path("bot/displacemaps/tvsimulator.mov")
    if bundled.exists():
        return str(bundled)

    # Try to download it
    disp_dir = os.path.join(workdir, "displacemaps")
    os.makedirs(disp_dir, exist_ok=True)
    dest = os.path.join(disp_dir, "tvsimulator.mov")
    if os.path.exists(dest):
        return dest

    try:
        await download_url(
            "https://file.garden/aTXso15ukD3mnuPI/tv_sim_displacement_map.mov",
            dest
        )
        return dest
    except Exception:
        # Last resort: check common locations
        for candidate in [
            "displacemaps/tvsimulator.mov",
            "bot/displacemaps/tvsimulator.mov",
            "/app/bot/displacemaps/tvsimulator.mov",
        ]:
            if os.path.exists(candidate):
                return candidate
        raise FileNotFoundError(
            "TV simulator displacement map not found and could not be downloaded. "
            "Place it at bot/displacemaps/tvsimulator.mov"
        )


def _generate_hald_cluts(workdir: str) -> list[str]:
    """Generate Hald CLUT .ppm files for hue shifts using ImageMagick.

    Returns paths to [hslhue_54.ppm, hslhue_180.ppm, hslhue_22.ppm, hslhue_108_30.ppm].
    CLUT hue values use ImageMagick -modulate formula: hue_frac * 200 + 100 (or +200 for sat boost).
    """
    # (filename, brightness, saturation, hue_mod_value)
    # hue_mod_value = hue_fraction * 200 + 100
    # For saturation-boosted CLUTs, saturation > 100 and hue_mod = hue_fraction * 200 + 200
    clut_specs = [
        # hslhue_54: hue shift 54° → fraction 0.15, mod = 0.15*200+100 = 130
        ("hslhue_54.ppm", 100, 100, 130),
        # hslhue_180: hue shift 180° → fraction 0.5, mod = 0.5*200+100 = 200
        ("hslhue_180.ppm", 100, 100, 200),
        # hslhue_22: hue shift 22° → fraction 0.06, mod = 0.06*200+100 = 112
        ("hslhue_22.ppm", 100, 100, 112),
        # hslhue_108_30: hue shift 108° + saturation boost → fraction 0.3, mod = 0.3*200+200 = 260
        ("hslhue_108_30.ppm", 100, 130, 260),
    ]
    paths = []
    for i, (filename, brightness, saturation, hue_mod) in enumerate(clut_specs):
        path = os.path.join(workdir, filename)
        cmd = [
            "magick", "hald:4",
            "-modulate", f"{brightness},{saturation},{hue_mod}",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            # Fallback: create a simple identity CLUT
            # If magick isn't available, skip CLUT effects
            pass
        # For hslhue_108_30 (index 3), apply additional -modulate 100,100,0
        if i == 3 and os.path.exists(path):
            extra_cmd = [
                "magick", path,
                "-modulate", "100,100,0",
                path
            ]
            subprocess.run(extra_cmd, capture_output=True, text=True, timeout=30)
        paths.append(path)
    return paths


def _run_preview1280(
    input_path: str,
    output_path: str,
    start_offset: float = 1.85,
    segment_dur: float = 0.85,
) -> tuple[bool, str]:
    """Run the preview1280 TV-simulator montage pipeline.

    This creates a 12-segment montage at 640x360, then scales to original size.
    Requires: ffmpeg, ImageMagick (magick), and the tvsimulator.mov displacement map.
    Uses rubberband audio filter for high-quality pitch shifting.
    """
    # Helper: rubberband pitch filter string for N semitones
    # Pre-compute 2^(N/12) as a float to avoid FFmpeg expression parsing issues
    def _rb(semitones: float, transients: str = "mixed") -> str:
        pitch_ratio = 2 ** (semitones / 12)
        return (
            f"rubberband=pitch={pitch_ratio:.6f}:"
            f"window=short:transients={transients}:"
            f"detector=soft:channels=together:pitchq=consistency"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        info = _ffprobe_video_info(input_path)
        w, h = info["width"], info["height"]
        dur = info["duration"]

        if w == 0 or h == 0:
            return False, "Could not read input video dimensions."

        # Generate Hald CLUTs
        cluts = _generate_hald_cluts(tmpdir)
        clut_54 = cluts[0] if os.path.exists(cluts[0]) else None
        clut_180 = cluts[1] if os.path.exists(cluts[1]) else None
        clut_22 = cluts[2] if os.path.exists(cluts[2]) else None
        clut_108_30 = cluts[3] if os.path.exists(cluts[3]) else None

        # Locate displacement map
        disp_map = None
        for candidate in [
            "bot/displacemaps/tvsimulator.mov",
            "displacemaps/tvsimulator.mov",
            "/app/bot/displacemaps/tvsimulator.mov",
        ]:
            if os.path.exists(candidate):
                disp_map = candidate
                break

        # Compute timing
        t = segment_dur
        t2 = segment_dur / 2
        t3 = start_offset + segment_dur

        # Step 1: Pre-process input to 640x360 FFV1
        avi0 = os.path.join(tmpdir, "0.avi")
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", input_path,
            "-vf", "scale=640:360,setsar=1:1",
            "-ss", str(start_offset), "-to", str(t3),
            "-c:v", "ffv1", "-c:a", "pcm_s16le",
            avi0
        ]
        ok, err = _run_ffmpeg_raw(cmd, timeout=120)
        if not ok:
            return False, f"Step 1 (pre-process) failed: {err}"

        avi_w = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=width",
                         "-of", "default=nw=1:nk=1") or "640"
        avi_h = _ffprobe(avi0, "-select_streams", "v:0",
                         "-show_entries", "stream=height",
                         "-of", "default=nw=1:nk=1") or "360"

        # Helper to build segment ffmpeg commands
        segments = []

        # Segment 1: plain copy, duration t
        seg1 = os.path.join(tmpdir, "1.avi")
        segments.append(([
            "ffmpeg", "-y", "-i", avi0,
            "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
            seg1
        ], seg1))

        # Segment 2: hue +54 (hslhue_54), pitch +1 semitone (rubberband)
        seg2 = os.path.join(tmpdir, "2.avi")
        if clut_54:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", f"movie={clut_54},[in]haldclut,format=yuv420p",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg2
            ], seg2))
        else:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", "hue=h=54",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg2
            ], seg2))

        # Segment 3: hue +180 + displacement map + mirror + pitch -2 semitones
        seg3 = os.path.join(tmpdir, "3.avi")
        if disp_map and clut_180:
            fc = (
                f"movie={clut_180}[h];"
                f"[0][h]haldclut,hflip,crop=iw/2:ih:0:0,split[left][tmp];"
                f"[tmp]hflip[right];[left][right]hstack,format=yuv420p,format=bgr32[00];"
                f"[1]crop=iw:ih/1:0:0,scale={avi_w}:{avi_h},eq=contrast=0.375,format=bgr32,hue=b=-0.033[x];"
                f"nullsrc=1x1,geq=r=128:g=128:b=128,scale={avi_w}:{avi_h},format=bgr32[y];"
                f"[00][x][y]displace=edge=wrap[v]"
            )
            segments.append(([
                "ffmpeg", "-y", "-i", avi0, "-stream_loop", "-1", "-i", disp_map,
                "-filter_complex", fc,
                "-af", _rb(-2),
                "-map", "[v]", "-map", "0:a",
                "-pix_fmt", "yuv420p",
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg3
            ], seg3))
        else:
            # Fallback without displacement
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", "hue=h=180,hflip,crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack,format=yuv420p",
                "-af", _rb(-2),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg3
            ], seg3))

        # Segment 4: hue +54 (hslhue_54), pitch +1 semitone (same as seg2)
        seg4 = os.path.join(tmpdir, "4.avi")
        if clut_54:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", f"movie={clut_54},[in]haldclut,format=yuv420p",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg4
            ], seg4))
        else:
            segments.append(([
                "ffmpeg", "-y", "-i", avi0,
                "-vf", "hue=h=54",
                "-af", _rb(1),
                "-t", str(t), "-c:v", "ffv1", "-c:a", "pcm_s16le",
                seg4
            ], seg4))

        # Segments 5-12: shorter segments (t2 duration)
        short_specs = [
            # (seg_num, vf_filter, af_filter)
            (5, None, None),  # plain copy
            (6, f"movie={clut_22},[in]haldclut,hflip,format=yuv420p" if clut_22 else "hue=h=22,hflip,format=yuv420p",
             _rb(2, "smooth")),  # hue+22, hflip, pitch+2 (smooth transients)
            (7, f"movie={clut_54},[in]haldclut,format=yuv420p" if clut_54 else "hue=h=54,format=yuv420p",
             _rb(1)),  # hue+54, pitch+1
            (8, f"movie={clut_108_30},[in]haldclut,hflip,format=yuv420p" if clut_108_30 else "hue=h=108,hflip,format=yuv420p",
             _rb(3)),  # hue+108+sat30, hflip, pitch+3
            (9, f"movie={clut_180},[in]haldclut,format=yuv420p" if clut_180 else "hue=h=180,format=yuv420p",
             _rb(-2)),  # hue+180, pitch-2
            (10, "hflip", None),  # just hflip
            (11, f"movie={clut_54},[in]haldclut,format=yuv420p" if clut_54 else "hue=h=54,format=yuv420p",
             _rb(1)),  # hue+54, pitch+1
            (12, f"movie={clut_108_30},[in]haldclut,hflip,format=yuv420p" if clut_108_30 else "hue=h=108,hflip,format=yuv420p",
             _rb(3)),  # hue+108+sat30, hflip, pitch+3
        ]

        for seg_num, vf, af in short_specs:
            seg_path = os.path.join(tmpdir, f"{seg_num}.avi")
            cmd = ["ffmpeg", "-y", "-i", avi0]
            if vf:
                cmd.extend(["-vf", vf])
            if af:
                cmd.extend(["-af", af])
            cmd.extend(["-t", str(t2), "-c:v", "ffv1", "-c:a", "pcm_s16le", seg_path])
            segments.append((cmd, seg_path))

        # Render all segments
        for i, (cmd, seg_path) in enumerate(segments):
            ok, err = _run_ffmpeg_raw(cmd, timeout=120)
            if not ok:
                return False, f"Segment {i+1}/{len(segments)} failed: {err}"

        # Concat all segments using concat protocol
        avi_files = [sp for _, sp in segments if os.path.exists(sp)]
        if not avi_files:
            return False, "No segments were produced."

        concat_str = "|".join(avi_files)
        concat_out = os.path.join(tmpdir, "concat.avi")
        cmd = [
            "ffmpeg", "-y",
            "-i", f"concat:{concat_str}",
            "-vf", f"scale={w}:{h},setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]
        return _run_ffmpeg_raw(cmd, timeout=180)


# ---------- Bot events & commands ----------

@tasks.loop(seconds=5)
async def _process_pending_resets():
    """Poll bot/pending_resets.json and clear usage for requested users."""
    try:
        if not PENDING_RESETS_FILE.exists():
            return
        with PENDING_RESETS_FILE.open() as f:
            user_ids = [int(x) for x in json.load(f)]
        if user_ids:
            for uid in user_ids:
                heavy_usage.pop(uid, None)
            _save_usage()
            PENDING_RESETS_FILE.unlink(missing_ok=True)
    except Exception:
        pass


@bot.event
async def on_ready():
    print(f"IHTX Bot online as {bot.user} (ID: {bot.user.id})")
    print("------")
    # Load cogs
    if not bot.cogs.get("Tags"):
        await bot.add_cog(TagCog(bot))
        print("TagCog loaded")
    _activity_file = Path("bot/activity.json")
    _default_activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="Meet the Sparkles! ✨👗 | Sparkles Magical Market Full Episode | Cartoons for Kids"
    )
    try:
        if _activity_file.exists():
            with _activity_file.open() as _af:
                _ad = json.load(_af)
            _atype_str = _ad.get("type", "watching")
            _aname = _ad.get("name", "")
            if _atype_str == "playing":
                _restored = discord.Game(name=_aname)
            elif _atype_str == "streaming":
                _parts = [p.strip() for p in _aname.split("|", 1)]
                _restored = discord.Streaming(
                    name=_parts[0],
                    url=_parts[1] if len(_parts) > 1 else "https://twitch.tv/placeholder"
                )
            elif _atype_str == "listening":
                _restored = discord.Activity(type=discord.ActivityType.listening, name=_aname)
            else:
                _restored = discord.Activity(type=discord.ActivityType.watching, name=_aname)
            await bot.change_presence(activity=_restored)
        else:
            await bot.change_presence(activity=_default_activity)
    except Exception:
        await bot.change_presence(activity=_default_activity)
    if not _process_pending_resets.is_running():
        _process_pending_resets.start()
    # Pre-download multipitch binary in the background so first use is instant
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _ensure_multipitch_bin)
    # Load tag system cog (once)
    if "Tags" not in bot.cogs:
        try:
            from bot.tags import setup as _tags_setup
            await _tags_setup(bot)
            print("Tag system loaded.")
        except Exception as _tags_exc:
            print(f"Warning: tag system failed to load — {_tags_exc}")


@bot.command(name="ihtx", aliases=["effect", "destroy"])
async def ihtx_command(ctx: commands.Context, *, args: str = "chaos"):
    """HEAVY COMMAND: replicates ihtx from FFmpeg.

    Apply an IHTX FFmpeg effect to an attached video or image.

    Usage:
      t!ihtx [preset]                  — use a built-in preset (chaos, glitch, etc.)
      t!ihtx <exports> <duration> <no_trim> <export_fmt> <pipe effects>   — custom TagScript workflow
    """
    # Parse arguments: preset name or TagScript-style custom icf+ workflow.
    parts = args.split()
    first = parts[0].lower() if parts else "chaos"

    is_preset = first in VISUAL_PRESETS and len(parts) == 1
    custom_args = None if is_preset else _parse_ihtx_custom_args(args)

    if is_preset:
        preset = first
    elif custom_args is None:
        preset_list = ", ".join(f"`{p}`" for p in sorted(VISUAL_PRESETS))
        await ctx.reply(
            f"Unknown preset or invalid custom IHTX syntax. Available presets: {preset_list}\n"
            f"Custom syntax: `t!ihtx <exports> <duration> <no_trim> <export_fmt> <pipe effects>`\n"
            f"Example: `t!ihtx 10 0.483 - mp4 huehsv 0.5;negate;multipitch=1|6|7`\n"
            f"Use `t!ihtxhelp` for full usage."
        )
        return

    # Resolve attachment: slash commands pass it as a parameter;
    # prefix commands need us to look at the message or referenced message.
    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        preset_list = ", ".join(f"`{p}`" for p in sorted(VISUAL_PRESETS))
        await ctx.reply(
            f"**I HATE THE X — IHTX Bot**\n"
            f"Attach a video or image and use `t!ihtx [preset]` or the custom IHTX syntax.\n\n"
            f"**Presets:** {preset_list}\n\n"
            f"**Custom IHTX:** `t!ihtx 10 0.483 - mp4 huehsv 0.5;negate;multipitch=1|6|7`\n"
            f"Use `t!ihtxhelp` for full usage.\n\n"
            f"Examples:\n"
            f"`t!ihtx chaos`\n"
            f"`t!ihtx glitch`\n"
            f"`t!ihtx 10 0.5 - mp4 huehsv 0.5;negate;multipitch=25|5|8.5`\n"
            f"`t!ihtx 5 0.25 - mp4 multipitch=1|2|3|4`"
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"File too large (max 25 MB). Your file is {attachment.size / 1024 / 1024:.1f} MB.")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        await ctx.reply(f"Unsupported file type `{suffix}`. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        return

    is_video = suffix in VIDEO_EXTENSIONS
    out_ext = get_output_ext(suffix, is_video)
    if is_preset:
        _preset_out_ext = PRESET_FILTERS.get(preset, {}).get("output_ext")
        if _preset_out_ext:
            out_ext = _preset_out_ext

    # Build status label
    if is_preset:
        _status_label = f"`{preset}`"
        status_msg = await ctx.reply(f"⏳ Processing {_status_label}…")
    else:
        _tmp_effects_label = _pipe_effects_label(custom_args[4])
        _tmp_reps = custom_args[0]
        _reps_str = f"×{_tmp_reps}" if abs(_tmp_reps) > 1 else ""
        status_msg = await ctx.reply(
            f"⏳ Processing your IHTX using pipe effects: `{_tmp_effects_label}`{_reps_str}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"output{out_ext}")

        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()

        if is_preset:
            ok, err = await loop.run_in_executor(
                None, run_ffmpeg, input_path, output_path, preset, is_video
            )
        else:
            # Custom IHTX follows the TagScript icf+ shell workflow and only supports video.
            if not is_video:
                await status_msg.edit(content="❌ Custom IHTX workflow requires video input (not images/GIFs).")
                return
            exports, duration_expr, no_trim, export_format, pipe_effects = custom_args
            output_path = os.path.join(tmpdir, "output.mp4")
            ok, err = await loop.run_in_executor(
                None, _run_ihtx_tagscript_workflow,
                input_path, output_path, exports, duration_expr, no_trim,
                export_format, pipe_effects
            )

        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        await status_msg.edit(content="⌛ Done!")

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
            _cb_url = await _upload_to_catbox(output_path)
            if _cb_url:
                _size_str_cb = f"{out_size / (1024 * 1024):.2f} MB"
                embed_cb = discord.Embed(
                    title="IHTX Bot - The IHTX command:",
                    description="use whatever sync to audio tag you want, I highly recommend notsobot's tag system (.t sync+)",
                    color=11578404,
                )
                embed_cb.set_thumbnail(url="https://files.catbox.moe/xli8jw.png")
                embed_cb.add_field(name="File Size", value=_size_str_cb, inline=True)
                embed_cb.add_field(name="Catbox", value=f"[Download]({_cb_url})\n{_cb_url}", inline=False)
                await ctx.reply(embed=embed_cb)
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large for Discord (>25 MB) and Catbox upload failed. Try a shorter clip.")
            return

        # Store last export for lexg
        if is_preset:
            _last_exports[ctx.author.id] = {
                "type": "preset",
                "preset": preset,
                "label": preset,
            }
            out_filename = f"ihtx_{preset}_{Path(attachment.filename).stem}{out_ext}"
        else:
            _last_exports[ctx.author.id] = {
                "type": "custom",
                "exports": str(exports),
                "duration": duration_expr,
                "no_trim": no_trim,
                "export_format": export_format,
                "pipe_effects": pipe_effects,
                "label": "custom",
            }
            out_filename = f"ihtx_custom_{Path(attachment.filename).stem}.mp4"

        # Probe output file for embed metadata
        try:
            _vinfo = _ffprobe_video_info(output_path)
            _w, _h = int(_vinfo["width"]), int(_vinfo["height"])
            _fr_raw = _vinfo.get("r_frame_rate", "")
            try:
                _fn, _fd = _fr_raw.split("/")
                _fps_val = float(_fn) / float(_fd)
                _fps_str = f"{_fps_val:.3f}".rstrip("0").rstrip(".") + " fps"
            except Exception:
                _fps_str = "N/A"
            if _w > 0 and _h > 0:
                _gcd = math.gcd(_w, _h)
                _ar_str = f"{_w // _gcd}:{_h // _gcd}"
                _res_str = f"{_w}×{_h}"
            else:
                _ar_str = _res_str = "N/A"
            _size_mb = out_size / (1024 * 1024)
            _size_str = f"{_size_mb:.2f} MB"
        except Exception:
            _res_str = _ar_str = _fps_str = "N/A"
            _size_str = f"{out_size / (1024 * 1024):.2f} MB"

        try:
            embed = discord.Embed(
                title="IHTX Bot - The IHTX command:",
                description="use whatever sync to audio tag you want, I highly recommend notsobot's tag system (.t sync+)",
                color=11578404,
            )
            embed.set_thumbnail(url="https://files.catbox.moe/xli8jw.png")
            embed.add_field(name="Resolution", value=_res_str, inline=True)
            embed.add_field(name="Aspect Ratio", value=_ar_str, inline=True)
            embed.add_field(name="FPS", value=_fps_str, inline=True)
            embed.add_field(name="File Size", value=_size_str, inline=True)
            await ctx.reply(
                embed=embed,
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


def _run_ihtxcustom_workflow(
    input_path: str,
    output_path: str,
    powers: int,
    duration: float,
    vf: str,
    af: str,
) -> tuple[bool, str]:
    """Powers-based IHTX custom workflow.

    Applies vf/af filters `powers` times progressively (each iteration feeds
    into the next), then concatenates all iterations (1× through powers×) via
    the .ts concat protocol — matching the original ihtxcustom script logic.
    """
    powers = min(max(powers, 1), 20)

    with tempfile.TemporaryDirectory() as tmpdir:
        def ts(n: int) -> str:
            return os.path.join(tmpdir, f"{n}.ts")

        def apply_step(src: str, dst: str) -> tuple[bool, str]:
            cmd = ["ffmpeg", "-loglevel", "error", "-hide_banner", "-y", "-i", src]
            # Normal path
            if vf:
                cmd.extend(["-vf", vf])
            if af:
                cmd.extend(["-af", af])
            if duration > 0:
                cmd.extend(["-t", str(duration)])
            cmd.extend([
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-ac", "2", "-ar", "44100",
                "-c:a", "mp2", "-b:a", "192k",
                "-bsf:v", "h264_mp4toannexb",
                dst,
            ])
            return _run_ffmpeg_raw(cmd, timeout=180)

        # Step 0 → 1.ts
        ok, err = apply_step(input_path, ts(1))
        if not ok:
            return False, f"Step 1 failed: {err}"

        # Steps 1.ts→2.ts, 2.ts→3.ts, ..., powers.ts→(powers+1).ts
        for i in range(1, powers + 1):
            ok, err = apply_step(ts(i), ts(i + 1))
            if not ok:
                return False, f"Step {i + 1} failed: {err}"

        # Concatenate 1.ts through powers.ts into .mov with h264 + pcm_s16le
        concat_str = "|".join(ts(i) for i in range(1, powers + 1))
        concat_cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", f"concat:{concat_str}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le",
            output_path,
        ]
        ok, err = _run_ffmpeg_raw(concat_cmd, timeout=300)
        if not ok:
            return False, f"Concat failed: {err}"

    return True, ""


@bot.command(name="invlum", aliases=["il"])
async def invlum_command(ctx: commands.Context, *, args: str = "1"):
    """Powers-based luma-inversion stacker.

    Applies curves=all='0/1 1/0' (full luma inversion) powers times progressively
    and concatenates all iterations into a single video.
    Optionally runs a pipe-effect chain on the final concatenated output.

    Usage:
      t!invlum <powers> [duration] [PIPE: effect;effect]

    Examples:
      t!invlum 4
      t!invlum 3 2.0
      t!invlum 5 1.5 PIPE: negate;multipitch=-4|5
      t!invlum 4 1.0 PIPE: huehsv=0.3;multipitch=-7|0|7
    """
    pipe_raw = ""
    pipe_effects: list[tuple[str, list[str]]] = []
    powers = 1
    duration = 1.0

    try:
        pre = re.split(r'PIPE:', args, flags=re.IGNORECASE)[0].strip()
        pre_parts = pre.split()
        if len(pre_parts) >= 2:
            powers = int(pre_parts[0])
            duration = float(pre_parts[1])
        elif len(pre_parts) == 1:
            powers = int(pre_parts[0])

        pipe_m = re.search(r'PIPE:\s*(.*)', args, re.IGNORECASE | re.DOTALL)
        if pipe_m:
            pipe_raw = pipe_m.group(1).strip()
            pipe_effects = _parse_pipe_effects(pipe_raw)
    except (ValueError, IndexError):
        pass

    if powers < 1:
        await ctx.reply(
            "❌ Powers must be at least 1.\n"
            "**Usage:** `t!invlum <powers> [duration] [PIPE: effect;effect]`"
        )
        return

    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        await ctx.reply("❌ Attach a video.\n**Usage:** `t!invlum <powers> [duration] [PIPE: effect;effect]`")
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply("❌ File too large (max 25 MB).")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"❌ `invlum` requires a video file. Got `{suffix}`.")
        return

    pipe_desc = f" | PIPE: `{pipe_raw}`" if pipe_raw else ""
    status_msg = await ctx.reply(
        f"⚙️ **invlum** — `{powers}` power(s) × `{duration}s`{pipe_desc} … this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "invlum_out.mov")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    with open(input_path, "wb") as f:
                        f.write(await resp.read())
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        lut_path = str(INVLUM_LUT_FILE.resolve())
        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None,
            lambda: _run_ihtxcustom_workflow(
                input_path, output_path, powers, duration,
                f"lut3d={lut_path}", "",
            ),
        )

        if not ok:
            await status_msg.edit(content=f"❌ invlum failed: {err}")
            return

        if pipe_effects:
            pipe_out = os.path.join(tmpdir, "invlum_pipe.mov")
            ok, err = await loop.run_in_executor(
                None,
                lambda: _apply_pipe_effects(output_path, pipe_out, pipe_effects),
            )
            if not ok:
                await status_msg.edit(content=f"❌ invlum pipe step failed: {err}")
                return
            output_path = pipe_out

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output too large for Discord (>25 MB). Try fewer powers or a shorter duration.")
            return

        out_filename = f"invlum_{Path(attachment.filename).stem}.mov"
        try:
            await ctx.reply(
                content=f"✅ **invlum** done! `{powers}` power(s), `{duration}s` each.",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload: {e}")


@bot.command(name="preview1280", aliases=["p1280", "preview", "pv1280"])
async def preview1280_command(ctx: commands.Context, start: float = 1.85, duration: float = 0.85):
    """Create a 12-segment TV-simulator preview montage from an attached video.

    Usage: t!preview1280 [start_offset] [segment_duration]
    Default: start=1.85, duration=0.85
    """
    attachment = None
    # Resolve attachment from message or referenced message.
    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        await ctx.reply(
            "**IHTX Preview1280**\n"
            "Attach a video and use `t!preview1280 [start] [duration]`.\n\n"
            "Creates a 12-segment TV-simulator montage with hue shifts, "
            "displacement mapping, and pitch variations.\n\n"
            "Defaults: start=1.85s, duration=0.85s per segment.\n"
            "Example: `t!preview1280 2.0 1.0`"
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"File too large (max 25 MB). Your file is {attachment.size / 1024 / 1024:.1f} MB.")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"Preview1280 requires a video file. Got `{suffix}`.")
        return

    start = max(0.0, start)
    duration = max(0.1, min(duration, 10.0))

    status_msg = await ctx.reply(
        f"⚙️ Creating **preview1280** montage (start={start}s, dur={duration}s)... this will take a while."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_p1280.mp4")

        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        # Ensure displacement map is available
        try:
            disp_path = await _ensure_displacement_map(tmpdir)
        except FileNotFoundError as e:
            await status_msg.edit(content=f"❌ {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_preview1280, input_path, output_path, start, duration
        )

        if not ok:
            await status_msg.edit(content=f"❌ Preview1280 failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output file too large for Discord (>25 MB). Try shorter segments.")
            return

        out_filename = f"p1280_{Path(attachment.filename).stem}.mp4"
        try:
            embed_p1280 = discord.Embed(
                title="Preview 1280 - FFmpeg command originally made by `MWTVE7691` then transported to typescript:",
                description="use whatever sync to audio tag you want, I highly recommend notsobot's tag system (.t sync+)",
                color=11578404,
            )
            embed_p1280.set_thumbnail(url="https://files.catbox.moe/dnjdty.png")
            await ctx.reply(
                embed=embed_p1280,
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")




_MULTIPITCH_AUDIO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif",
    ".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a", ".opus",
}

_MULTIPITCH_MAX = 20


@bot.command(name="multipitch", aliases=["mp", "multi"])
async def multipitch_command(ctx: commands.Context, *, args: str = ""):
    """Apply multi-voice pitch shifting using Rubber Band R3 (-3 engine).

    Usage:
      t!multipitch -7;12;19          — semicolon-separated semitone values (primary)
      t!multipitch -7|12|19          — pipe-separated also accepted
      t!mp -7;12;19                  — alias
      t!multi -7;12;19               — alias

    Each value creates a separately pitched voice; all voices are mixed together.
    Supports negative and positive semitone values.
    Works on video and audio files. Video stream is preserved unchanged.

    Example: t!multipitch -7;12;19
    """
    if not args:
        await ctx.reply(
            "**IHTX Multipitch** — Rubber Band R3\n"
            "Attach a video or audio file and provide semicolon-separated semitone values.\n\n"
            "Each value creates a pitched voice; all voices are mixed together.\n\n"
            f"Example: `t!multipitch -7;12;19`\n"
            f"Pipe syntax also works: `t!multipitch -7|12|19`\n"
            f"Aliases: `t!mp`, `t!multi`\n"
            f"Max pitches: {_MULTIPITCH_MAX}"
        )
        return

    # Parse: semicolons are the primary separator; fall back to pipes
    raw = args.strip()
    if ";" in raw:
        pitch_values = [v.strip() for v in raw.split(";") if v.strip()]
    elif "|" in raw:
        pitch_values = [v.strip() for v in raw.split("|") if v.strip()]
    else:
        pitch_values = [raw] if raw else []

    if not pitch_values:
        await ctx.reply("No pitch values provided. Example: `t!multipitch -7;12;19`")
        return

    if len(pitch_values) > _MULTIPITCH_MAX:
        await ctx.reply(f"Too many pitches (max {_MULTIPITCH_MAX}). Got {len(pitch_values)}.")
        return

    # Validate each value up-front for a fast, clear error
    for pv in pitch_values:
        try:
            val = float(pv)
            if not math.isfinite(val):
                raise ValueError
        except ValueError:
            await ctx.reply(f"❌ Invalid pitch value: `{pv}` — must be a finite number in semitones.")
            return

    # Resolve attachment: slash commands pass it as a parameter;
    # prefix commands need us to look at the message or referenced message.
    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        await ctx.reply(
            "Attach a video or audio file and provide pitch values.\n"
            "Example: `t!multipitch -7;12;19`"
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"File too large (max 25 MB). Your file is {attachment.size / 1024 / 1024:.1f} MB.")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in _MULTIPITCH_AUDIO_EXTS:
        await ctx.reply(
            f"Unsupported file type `{suffix}`.\n"
            f"Supported: video (mp4, mov, avi, mkv, webm, gif) or audio (wav, mp3, flac, ogg, aac, m4a, opus)."
        )
        return

    pitch_str = ";".join(pitch_values)
    status_msg = await ctx.reply(
        f"⚙️ Applying **multipitch** ({pitch_str}) via Rubber Band R3… this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_multipitch.mp4")

        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_multipitch_rb3,
            input_path, output_path, pitch_values
        )

        if not ok:
            await status_msg.edit(content=f"❌ Multipitch failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output file too large for Discord (>25 MB). Try a shorter clip.")
            return

        safe_pitch_str = pitch_str.replace(";", "_")
        out_filename = f"multipitch_{safe_pitch_str}_{Path(attachment.filename).stem}.mp4"
        try:
            await ctx.reply(
                content=f"✅ **IHTX multipitch** ({pitch_str}) applied!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


# ---------- t!ffmpeg — raw FFmpeg command ----------

@bot.command(name="ffmpeg")
async def ffmpeg_raw_command(ctx: commands.Context, *, args: str = ""):
    """Run raw FFmpeg on an attached file.

    Args go between -i <input> and <output>. Output filename matches input.

    Usage:
      t!ffmpeg -vf negate
      t!ffmpeg -vf hue=h=180 -c:a copy
      t!ffmpeg -af volume=2.0
    """
    if not args:
        await ctx.reply(
            "**t!ffmpeg** — Run raw FFmpeg on an attachment.\n"
            "Args are inserted between `-i <input>` and `<output>`.\n\n"
            "**Usage:** `t!ffmpeg <ffmpeg args>`\n"
            "**Examples:**\n"
            "`t!ffmpeg -vf negate`\n"
            "`t!ffmpeg -vf hue=h=180 -c:a copy`\n"
            "`t!ffmpeg -af volume=2.0`"
        )
        return

    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        await ctx.reply("❌ Attach a file to use `t!ffmpeg`.")
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"❌ File too large (max 25 MB).")
        return

    args_display = args if len(args) <= 80 else args[:79] + "…"
    status_msg = await ctx.reply(f"⏳ Processing `{args_display}`…")

    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        suffix = Path(attachment.filename).suffix.lower()
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, attachment.filename)

        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Download failed: {e}")
            return

        try:
            user_args = shlex.split(args)
        except ValueError as e:
            await status_msg.edit(content=f"❌ Invalid ffmpeg args: {e}")
            return

        cmd = [
            "ffmpeg", "-loglevel", "error", "-hide_banner", "-y",
            "-i", input_path,
        ] + user_args + [output_path]

        loop = asyncio.get_event_loop()
        ok, err_log = await loop.run_in_executor(None, _run_ffmpeg_raw, cmd, 180)

        elapsed = int(time.time() - start_time)

        if not ok:
            err_block = f"\n```\n{err_log.strip()[-1200:]}\n```" if err_log and err_log.strip() else ""
            await status_msg.edit(content=f"❌ FFmpeg failed (took {elapsed}s){err_block}")
            return

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            await status_msg.edit(content="❌ FFmpeg produced no output file.")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output too large for Discord (>25 MB).")
            return

        footer_parts = []
        if err_log and err_log.strip():
            footer_parts.append(f"-# Error log:\n```\n{err_log.strip()[-800:]}\n```")
        footer_parts.append(f"-# Took: {elapsed} seconds")
        footer = "\n".join(footer_parts)

        try:
            await ctx.reply(
                content=footer,
                file=discord.File(output_path, filename=attachment.filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Upload failed: {e}")


# ---------- t!trim — precise media trimmer ----------

_TRIM_SUPPORTED_EXTS = {
    ".mp4", ".mov", ".webm", ".gif", ".mkv",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a",
}
_TRIM_MAX_DECIMALS = 10


def _parse_trim_timestamp(ts: str) -> Decimal:
    """Parse HH:MM:SS[.frac], MM:SS[.frac], or plain seconds into Decimal seconds.

    Raises:
        ValueError("too_many_decimals") — more than 10 decimal places in the fractional part
        ValueError("invalid_format")    — unrecognisable or non-numeric input
    """
    ts = ts.strip()
    if "." in ts:
        frac = ts.rsplit(".", 1)[1]
        if len(frac) > _TRIM_MAX_DECIMALS:
            raise ValueError("too_many_decimals")
    parts = ts.split(":")
    try:
        if len(parts) == 1:
            return Decimal(parts[0])
        elif len(parts) == 2:
            return Decimal(parts[0]) * 60 + Decimal(parts[1])
        elif len(parts) == 3:
            return Decimal(parts[0]) * 3600 + Decimal(parts[1]) * 60 + Decimal(parts[2])
        else:
            raise ValueError("invalid_format")
    except InvalidOperation:
        raise ValueError("invalid_format")


@bot.command(name="trim")
async def trim_command(ctx: commands.Context, *, args: str = ""):
    """Trim media from <start> to <end> with up to 10 decimal places of precision.

    Usage:
      t!trim <start> <end>
      t!trim 5 15
      t!trim 0.5 3.75
      t!trim 1.2345678901 9.8765432109
      t!trim 00:01:30.5 00:02:45.25
      t!trim 1:30 2:45

    Media from: attachment on this message, replied-to message, or a URL in args.
    Supported: mp4, mov, webm, gif, mkv, mp3, wav, flac, ogg, m4a.
    """
    tokens = args.split()

    # Separate URLs from timestamp tokens
    media_url: str | None = None
    ts_tokens: list[str] = []
    for tok in tokens:
        if tok.startswith(("http://", "https://")):
            if media_url is None:
                media_url = tok
        else:
            ts_tokens.append(tok)

    if len(ts_tokens) < 2:
        await ctx.reply(
            "❌ Usage: `t!trim <start> <end>`\n"
            "Examples: `t!trim 5 15` · `t!trim 0.5 3.75` · `t!trim 00:01:30 00:02:45`\n"
            "Attach, reply to, or include a media URL."
        )
        return

    # Parse start timestamp
    try:
        t_start = _parse_trim_timestamp(ts_tokens[0])
    except ValueError as exc:
        if str(exc) == "too_many_decimals":
            await ctx.reply("❌ Timestamps may contain at most 10 decimal places.")
        else:
            await ctx.reply("❌ Invalid timestamp format.")
        return

    # Parse end timestamp
    try:
        t_end = _parse_trim_timestamp(ts_tokens[1])
    except ValueError as exc:
        if str(exc) == "too_many_decimals":
            await ctx.reply("❌ Timestamps may contain at most 10 decimal places.")
        else:
            await ctx.reply("❌ Invalid timestamp format.")
        return

    # Validate ordering
    if t_start < 0 or t_end < 0:
        await ctx.reply("❌ Timestamps cannot be negative.")
        return
    if t_start >= t_end:
        await ctx.reply("❌ Start time must be less than end time.")
        return

    # Resolve media source (priority: attachment > reply > URL arg)
    attachment: discord.Attachment | None = None
    if media_url is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
                else:
                    for tok in ref.content.split():
                        if tok.startswith(("http://", "https://")):
                            media_url = tok
                            break
            except Exception:
                pass

    if attachment is None and media_url is None:
        await ctx.reply("❌ No media found. Attach, reply to, or provide a media URL.")
        return

    # Determine file extension
    src_name = attachment.filename if attachment else urllib.parse.urlparse(media_url).path
    suffix = Path(src_name).suffix.lower()
    if not suffix:
        suffix = ".mp4"
    if suffix not in _TRIM_SUPPORTED_EXTS:
        await ctx.reply(
            f"❌ Unsupported format `{suffix}`.\n"
            f"Supported: {', '.join(sorted(_TRIM_SUPPORTED_EXTS))}"
        )
        return

    status_msg = await ctx.reply(f"✂️ Trimming…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")

        # Download
        try:
            if attachment:
                await download_attachment(attachment, input_path)
            else:
                await download_url(media_url, input_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Failed to download media: {exc}")
            return

        # Probe duration
        loop = asyncio.get_event_loop()
        dur = await loop.run_in_executor(None, _ffprobe_duration, input_path)
        if dur <= 0:
            await status_msg.edit(content="❌ Could not read media duration.")
            return

        if float(t_end) > dur + 0.001:
            await status_msg.edit(
                content=f"❌ End time exceeds the media duration ({dur:.6f}s)."
            )
            return

        output_path = os.path.join(tmpdir, f"trimmed{suffix}")
        start_str = str(t_start)
        end_str = str(t_end)

        duration_str = str(t_end - t_start)
        _audio_only_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}

        if suffix == ".gif":
            # GIFs cannot be stream-copied; re-encode with palette
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str, "-t", duration_str,
                "-i", input_path,
                "-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                output_path,
            ]
        elif suffix in _audio_only_exts:
            # Audio-only: input-side seek, stream copy
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str,
                "-i", input_path,
                "-t", duration_str,
                "-c", "copy",
                output_path,
            ]
        else:
            # Video (mp4/mov/webm/mkv): input-side seek keeps file at a keyframe
            # so the output is always decodable/viewable.
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str,
                "-i", input_path,
                "-t", duration_str,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                output_path,
            ]

        ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 120))
        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output file too large for Discord (>25 MB).")
            return

        stem = Path(src_name).stem
        safe_s = str(t_start).replace(".", "_")
        safe_e = str(t_end).replace(".", "_")
        out_filename = f"trim_{safe_s}-{safe_e}_{stem}{suffix}"

        try:
            await ctx.reply(
                content=f"✅ Trimmed `{t_start}s` → `{t_end}s`",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


# ---------- t!mirror — mirror presets via FFmpeg split/crop/flip/stack ----------

# Each preset is (vf_filter, description)
# Native FFmpeg: split the frame, crop each half, flip one, stack back.
_MIRROR_PRESETS: dict[str, tuple[str, str]] = {
    "left": (
        "split[a][b];[a]crop=iw/2:ih:0:0[L];[b]crop=iw/2:ih:0:0,hflip[R];[L][R]hstack",
        "left half mirrored onto right",
    ),
    "right": (
        "split[a][b];[a]crop=iw/2:ih:iw/2:0,hflip[L];[b]crop=iw/2:ih:iw/2:0[R];[L][R]hstack",
        "right half mirrored onto left",
    ),
    "top": (
        "split[a][b];[a]crop=iw:ih/2:0:0[T];[b]crop=iw:ih/2:0:0,vflip[B];[T][B]vstack",
        "top half mirrored onto bottom",
    ),
    "bottom": (
        "split[a][b];[a]crop=iw:ih/2:0:ih/2,vflip[T];[b]crop=iw:ih/2:0:ih/2[B];[T][B]vstack",
        "bottom half mirrored onto top",
    ),
}
# Short aliases → canonical name
_MIRROR_ALIASES: dict[str, str] = {"l": "left", "r": "right", "t": "top", "b": "bottom"}
_MIRROR_SUPPORTED_EXTS = {
    ".mp4", ".mov", ".webm", ".mkv", ".gif",
    ".png", ".jpg", ".jpeg", ".webp",
}


@bot.command(name="mirror")
async def mirror_command(ctx: commands.Context, preset: str = "", *, args: str = ""):
    """Mirror media along an axis.

    Usage:
      t!mirror <preset>
      Presets: left (l), right (r), top (t), bottom (b)

    Examples:
      t!mirror left
      t!mirror r
      t!mirror top

    Media from: attachment, replied-to message, or a URL in the preset/args.
    """
    # Resolve preset name (allow short aliases)
    preset_key = preset.strip().lower()
    preset_key = _MIRROR_ALIASES.get(preset_key, preset_key)

    # A URL might have been passed in the preset slot; re-route it
    media_url: str | None = None
    if preset.startswith(("http://", "https://")):
        media_url = preset
        preset_key = args.split()[0].lower() if args.strip() else ""
        preset_key = _MIRROR_ALIASES.get(preset_key, preset_key)

    if preset_key not in _MIRROR_PRESETS:
        preset_list = ", ".join(f"`{k}`" for k in _MIRROR_PRESETS)
        await ctx.reply(f"❌ Available presets: {preset_list}")
        return

    vf, description = _MIRROR_PRESETS[preset_key]

    # Scan args for a URL if not already found
    if media_url is None:
        for tok in args.split():
            if tok.startswith(("http://", "https://")):
                media_url = tok
                break

    # Resolve media: attachment > reply > URL arg
    attachment: discord.Attachment | None = None
    if media_url is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
                else:
                    for tok in ref.content.split():
                        if tok.startswith(("http://", "https://")):
                            media_url = tok
                            break
            except Exception:
                pass

    if attachment is None and media_url is None:
        await ctx.reply("❌ No media found. Attach, reply to, or provide media.")
        return

    src_name = attachment.filename if attachment else urllib.parse.urlparse(media_url).path
    suffix = Path(src_name).suffix.lower()
    if not suffix:
        suffix = ".mp4"
    if suffix not in _MIRROR_SUPPORTED_EXTS:
        await ctx.reply(
            f"❌ Unsupported format `{suffix}`.\n"
            f"Supported: {', '.join(sorted(_MIRROR_SUPPORTED_EXTS))}"
        )
        return

    status_msg = await ctx.reply(f"🪞 Applying `mirror={preset_key}` ({description})…")

    _image_exts = {".png", ".jpg", ".jpeg", ".webp"}

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")

        try:
            if attachment:
                await download_attachment(attachment, input_path)
            else:
                await download_url(media_url, input_path)
        except Exception as exc:
            await status_msg.edit(content=f"❌ Failed to download media: {exc}")
            return

        out_suffix = suffix if suffix != ".webp" else ".png"
        output_path = os.path.join(tmpdir, f"mirror_{preset_key}{out_suffix}")

        loop = asyncio.get_event_loop()

        if suffix == ".gif":
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"{vf},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                output_path,
            ]
        elif suffix in _image_exts:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", vf,
                output_path,
            ]
        else:
            # Video: re-encode with libx264 so output is always viewable
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"{vf},format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "copy",
                "-movflags", "+faststart",
                output_path,
            ]

        ok, err = await loop.run_in_executor(None, lambda: _run_ffmpeg_raw(cmd, 180))
        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output file too large for Discord (>25 MB).")
            return

        stem = Path(src_name).stem
        out_filename = f"mirror_{preset_key}_{stem}{out_suffix}"

        try:
            await ctx.reply(
                content=f"✅ `mirror={preset_key}` — {description}",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as exc:
            await status_msg.edit(content=f"❌ Failed to upload result: {exc}")


@bot.command(name="huehsv", aliases=["hhsv"])
async def huehsv_command(ctx: commands.Context, hue: float = 0.5):
    """Apply hue shift using ImageMagick haldclut + FFmpeg.

    Usage:
      t!huehsv <hue>          — shift hue, default 0.5
      t!hhsv <hue>            — alias

    Internally: magick hald:6 -modulate 100,100,<hue*200+100> hsv.ppm
    Then: ffmpeg -vf "movie=hsv.ppm,[in]haldclut,format=rgba" -pix_fmt yuv420p
    """
    # Resolve attachment
    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        await ctx.reply(
            "**IHTX HueHSV**\n"
            "Attach a video or image and use `t!huehsv <hue>`.\n\n"
            "Applies hue shift via ImageMagick haldclut.\n"
            "Example: `t!huehsv 0.5`\n"
            "Aliases: `t!hhsv`"
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"File too large (max 25 MB). Your file is {attachment.size / 1024 / 1024:.1f} MB.")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        await ctx.reply(f"Unsupported file type `{suffix}`. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        return

    is_video = suffix in VIDEO_EXTENSIONS
    out_ext = get_output_ext(suffix, is_video)

    status_msg = await ctx.reply(
        f"⚙️ Applying **huehsv** (hue={hue})... this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, f"output{out_ext}")

        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, err = await loop.run_in_executor(
            None, _run_huehsv, input_path, output_path, hue
        )

        if not ok:
            await status_msg.edit(content=f"❌ HueHSV failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output file too large for Discord (>25 MB). Try a shorter clip.")
            return

        out_filename = f"huehsv_{hue}_{Path(attachment.filename).stem}{out_ext}"
        try:
            await ctx.reply(
                content=f"✅ **IHTX huehsv** (hue={hue}) applied!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")


@bot.command(name="syncaudio", aliases=["sa", "sync"])
async def syncaudio_command(ctx: commands.Context, mode: str = ""):
    """Sync video and audio durations.

    Default: adjusts video speed to match audio.
    Alt mode: adjusts audio speed to match video.

    Usage:
      t!syncaudio         — adjust video speed to match audio
      t!syncaudio alt     — adjust audio speed to match video
      t!sa                — alias
      t!sync alt          — alias
    """
    alt_mode = mode.lower().strip() == "alt"

    # Resolve attachment: slash commands pass it as a parameter;
    # prefix commands need us to look at the message or referenced message.
    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        mode_desc = "adjusts **video speed** to match audio" if not alt_mode else "adjusts **audio speed** to match video"
        await ctx.reply(
            "**IHTX Syncaudio**\n"
            f"Attach a video and use `t!syncaudio [alt]`.\n\n"
            f"Default: {mode_desc}\n"
            "Alt mode (`alt`): adjusts the other stream instead.\n\n"
            "Examples:\n"
            "```\n"
            "t!syncaudio         — video speed → match audio\n"
            "t!syncaudio alt     — audio speed → match video\n"
            "```\n"
            "Aliases: `t!sa`, `t!sync`"
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"File too large (max 25 MB). Your file is {attachment.size / 1024 / 1024:.1f} MB.")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        await ctx.reply(f"Syncaudio requires a video file. Got `{suffix}`.")
        return

    mode_label = "alt (audio→video)" if alt_mode else "default (video→audio)"
    status_msg = await ctx.reply(
        f"⚙️ Running **syncaudio** ({mode_label})... this may take a moment."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "output_syncaudio.mp4")

        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download your file: {e}")
            return

        loop = asyncio.get_event_loop()
        ok, info = await loop.run_in_executor(
            None, _run_syncaudio,
            input_path, output_path, alt_mode
        )

        if not ok:
            await status_msg.edit(content=f"❌ Syncaudio failed:\n```\n{info[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="❌ Output file too large for Discord (>25 MB). Try a shorter clip.")
            return

        out_filename = f"syncaudio_{Path(attachment.filename).stem}.mp4"
        try:
            await ctx.reply(
                content=f"✅ **IHTX syncaudio** ({mode_label}) applied!\n```\n{info}\n```",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload result: {e}")

@bot.command(name="presets", aliases=["effects", "list"])
async def presets_command(ctx: commands.Context):
    """List all available IHTX presets."""
    lines = [f"`{name}` — {PRESET_FILTERS[name]['vf'] or PRESET_FILTERS[name]['complex']}" for name in sorted(PRESET_FILTERS)]
    embed = discord.Embed(
        title="IHTX Bot — Available Presets",
        description="\n".join(lines),
        color=discord.Color.red(),
    )
    embed.add_field(
        name="Usage",
        value="Attach a video or image and run:\n`t!ihtx [preset]`\n\nDefault preset: `chaos`",
        inline=False,
    )
    embed.set_footer(text="I Hate The X — FFmpeg logo destruction bot")
    await ctx.reply(embed=embed)


# ── Help data ─────────────────────────────────────────────────────────────────
# Each entry: {"name": str, "value": str, "cat": "heavy"|"fun"|"owner"}
# "name" and "value" are searched when the user passes a query.
_HELP_ENTRIES: list[dict] = [
    # ── Heavy ──
    {
        "cat": "heavy",
        "name": "t!ihtx [preset]",
        "value": (
            "Apply a preset to an attached video/image. Default preset: `chaos`\n"
            "Other presets: `glitch`, `melt`, `chaos2`, `vhs`, … — run `t!presets` for the full list."
        ),
    },
    {
        "cat": "heavy",
        "name": "t!ihtx <reps> <dur> <noTrim> <fmt> <effects>",
        "value": (
            "Custom effect chain (comma-delimited). Each effect may have `=` params.\n"
            "**Example:** `t!ihtx 10 0.483 - mp4 huehsv=0.5,negate,multipitch=25|5|8.5`\n"
            "**Raw FFmpeg step:** `t!ihtx 1 10 false mp4 ffmpeg(-vf hue=h=50),speed=1.5`"
        ),
    },
    {
        "cat": "heavy",
        "name": "Pipe effects (comma-separated)",
        "value": (
            "**Video:** `hflip` `vflip` `negate` `grayscale` `sepia` `rotate=<deg>` "
            "`huehsv=<val>` `ccshue=hue|sat|gamma|gain|offset` `brightness=<val>` `contrast=<val>` "
            "`saturation=<val>` `swapuv` `invlum` `invertrgb=r;g;b` `realgm4` `gm91deform`\n"
            "**Distortion:** `mirror=<deg>` `zoom=<amt>` `pinch&punch=str;r;cx;cy` `shake=<h>|<v>` `wave=hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase[|sep][|noclip]`\n"
            "**Reverse:** `vreverse` (video frames) · `areverse` (audio)\n"
            "**Audio:** `multipitch=semis` `volume=<val>` `vibrato=freq;depth` `syncaudio`\n"
            "**Raw / FX:** `ffmpeg(<args>)` `frei0r=plugin:params` `lut=<url>` `speed=<factor>`"
        ),
    },
    {
        "cat": "heavy",
        "name": "t!ffmpeg <args>",
        "value": (
            "Run raw FFmpeg on an attachment. Args go between `-i input` and `output`.\n"
            "Example: `t!ffmpeg -vf negate` · `t!ffmpeg -af volume=2.0`\n"
            "Shows error log and elapsed time in the reply."
        ),
    },
    {
        "cat": "heavy",
        "name": "ccshue pipe effect  (hue|sat|gamma|gain|offset)",
        "value": (
            "Full color correction via ImageMagick haldclut. All params optional (defaults shown):\n"
            "`ccshue=0|1|1|1|0`\n"
            "• **hue** — rotation in degrees −180…180 (default 0)\n"
            "• **sat** — saturation multiplier (default 1.0)\n"
            "• **gamma** — gamma correction (default 1.0)\n"
            "• **gain** — RGB gain/multiply (default 1.0)\n"
            "• **offset** — add to all channels −1…1 (default 0)\n"
            "Example: `t!ihtx 1 5 - mp4 ccshue=90|1.5|1.2|1|0`"
        ),
    },
    {
        "cat": "heavy",
        "name": "frei0r pipe effect  (frei0r=plugin:params)",
        "value": (
            "Apply any installed frei0r video effect plugin via FFmpeg.\n"
            "Params are colon-separated floats/strings per the plugin spec.\n"
            "Common plugins: `distort0r` `cartoon` `edgeglow` `pixelize` `plasma` `sobel` `threshold0r`\n"
            "Example: `t!ihtx 1 5 - mp4 frei0r=distort0r:0.5:0.1`\n"
            "Also available in tags: `{frei0r:distort0r:0.5}` or `frei0r:\\ndistort0r:0.5` prefix block"
        ),
    },
    {
        "cat": "heavy",
        "name": "wave pipe effect  (wave=hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase[|sep][|noclip])",
        "value": (
            "Sinusoidal pixel-displacement wave distortion using geq. All params optional.\n"
            "• **hSpd/hFreq/hAmp/hPhase** — horizontal wave speed, frequency, amplitude, phase (defaults: 1|1|1|0)\n"
            "• **vSpd/vFreq/vAmp/vPhase** — vertical wave speed, frequency, amplitude, phase (defaults: 1|1|1|0)\n"
            "• **sep** — apply H and V waves as separate passes (pass `1` to enable)\n"
            "• **noclip** — draw a border box to prevent pixel clipping at edges (pass `1` to enable)\n"
            "Example (default): `t!ihtx 3 1.0 - mp4 wave`\n"
            "Example (custom): `t!ihtx 3 1.0 - mp4 wave=2|1|1.5|0|1|2|1|0`\n"
            "Example (separate passes + noclip): `t!ihtx 3 1.0 - mp4 wave=1|1|1|0|1|1|1|0|1|1`"
        ),
    },
    {
        "cat": "heavy",
        "name": "swirl pipe effect  (swirl=<strength>[|radius][|xc][|yc][|fallout][|1:1])",
        "value": (
            "Rotational pixel-displacement swirl using FFmpeg geq.\n"
            "• **strength** — swirl angle in degrees, negative reverses direction (default 180)\n"
            "• **radius** — swirl radius as fraction of shortest dimension 0–1 (default 0.5)\n"
            "• **xc / yc** — center point as fractions 0–1 (default 0.5 / 0.5)\n"
            "• **fallout** — attenuation curve: `linear` or `quad` (default quad)\n"
            "• **1:1** — `true`/`false` — scale to square before swirl, restore after (default false)\n"
            "Example (default): `t!ihtx 1 2 - mp4 swirl`\n"
            "Example (strong, off-center): `t!ihtx 1 2 - mp4 swirl=360|0.4|0.3|0.6|linear`\n"
            "Example (square mode): `t!ihtx 1 2 - mp4 swirl=180|0.5|0.5|0.5|quad|true`"
        ),
    },
    {
        "cat": "heavy",
        "name": "shake pipe effect  (shake=<h>|<v>)",
        "value": (
            "Random per-frame pixel displacement shake using geq. Crops output back to original dimensions.\n"
            "• **h** — horizontal shake strength in pixels (default 3)\n"
            "• **v** — vertical shake strength in pixels (default 0)\n"
            "Example: `t!ihtx 3 1.0 - mp4 shake=3`\n"
            "Example with both axes: `t!ihtx 3 1.0 - mp4 shake=5|3`"
        ),
    },
    {
        "cat": "heavy",
        "name": "vreverse / areverse pipe effects",
        "value": (
            "Reverse video frames or audio independently.\n"
            "• **`vreverse`** — reverses video frames only (audio unaffected)\n"
            "• **`areverse`** — reverses audio only (video unaffected)\n"
            "Chain both to fully reverse: `t!ihtx 1 5 - mp4 vreverse,areverse`\n"
            "Note: `vreverse` loads all frames into memory — keep clips short."
        ),
    },
    {
        "cat": "heavy",
        "name": "t!multipitch <semitones>  (aliases: mp, multi)",
        "value": (
            "Multi-voice pitch shift via Rubber Band R3.\n"
            "Pipe-separated semitones: `t!multipitch 25|5|8.5`\n"
            "Or inline: `t!ihtx 1 10 false mp4 multipitch=25|5|8.5`"
        ),
    },
    {
        "cat": "heavy",
        "name": "t!preview1280 [start] [dur]",
        "value": "12-segment TV-simulator montage. Defaults: start=1.85, dur=0.85",
    },
    {
        "cat": "heavy",
        "name": "t!invlum [n]",
        "value": "Apply luma-inversion progressively N times and concat all iterations.",
    },
    {
        "cat": "heavy",
        "name": "t!lexg  (aliases: lastexportgrab)",
        "value": "Re-apply the last `t!ihtx` export to a new attachment using the same effect chain.",
    },
    # ── Fun ──
    {
        "cat": "fun",
        "name": "t!huehsv <hue>  (aliases: hhsv)",
        "value": "Apply hue shift via ImageMagick haldclut. Example: `t!huehsv 0.5`",
    },
    {
        "cat": "fun",
        "name": "t!mirror <left|right|top|bottom|deg>",
        "value": "Mirror media using FFmpeg split/flip/stack. Also works as a pipe effect.",
    },
    {
        "cat": "fun",
        "name": "t!syncaudio [alt]  (aliases: sa, sync)",
        "value": (
            "Sync video and audio durations by adjusting playback speed.\n"
            "Default: speeds up video to match audio. `alt`: speeds up audio to match video."
        ),
    },
    {
        "cat": "fun",
        "name": "t!trim <start> <end>",
        "value": "Trim audio, video, or GIF. Supports HH:MM:SS.frac and plain seconds.",
    },
    {
        "cat": "fun",
        "name": "t!dl <url>  (aliases: dv, download, dlv)",
        "value": "Download a video or image from a URL and upload it to Discord.",
    },
    {
        "cat": "fun",
        "name": "t!catbox  (aliases: cb, upload)",
        "value": "Upload any file (up to 200 MB) to catbox.moe and get a permanent direct link.",
    },
    {
        "cat": "fun",
        "name": "t!chat <prompt>  (aliases: ask, ai)",
        "value": "Chat with Clankered Thatoneguynobodyinvited using Gemini 2.5 Flash. Pure Google GenAI pipeline.",
    },
    {
        "cat": "fun",
        "name": "t!tag <name> [args]  (aliases: tags)",
        "value": (
            "Invoke a custom tag. Run `t!tag help` for the full scripting reference.\n"
            "Supports variables, math, conditionals, embed JSON, iscript, mediascript, and IHTX."
        ),
    },
    {
        "cat": "fun",
        "name": "t!presets",
        "value": "List all available IHTX presets.",
    },
    {
        "cat": "fun",
        "name": "t!updatelog  (aliases: updates, changelog)",
        "value": "Show recent bot updates organized by category.",
    },
    # ── Owner ──
    {
        "cat": "owner",
        "name": "t!blockuser / t!unblockuser <@user>",
        "value": "Add or remove a user from the global blocklist.",
    },
    {
        "cat": "owner",
        "name": "t!blockchannel / t!unblockchannel <#channel>",
        "value": "Block or unblock a channel from running bot commands.",
    },
    {
        "cat": "owner",
        "name": "t!keywordblock <keyword> [#channel]",
        "value": "Block a keyword in a specific channel (or globally). `t!keywordblockremove` to undo.",
    },
    {
        "cat": "owner",
        "name": "t!autoreply <trigger> | <response> [#channel]",
        "value": "Add an autoreply. Supports `{mention}` / `{user}` / `{random:a|b|c}` placeholders.",
    },
    {
        "cat": "owner",
        "name": "t!removeautoreply <trigger>  (aliases: rar)",
        "value": "Remove an autoreply trigger.",
    },
    {
        "cat": "owner",
        "name": "t!autoreplies  (aliases: arlist)",
        "value": "List all active autoreplies.",
    },
    {
        "cat": "owner",
        "name": "t!autoreply2 [#channel]  /  t!autoreply2list",
        "value": "Toggle AI auto-reply (responds to every message) in a channel.",
    },
    {
        "cat": "owner",
        "name": "t!warn @user <reason>  /  t!warnings @user  /  t!clearwarn @user",
        "value": "Warn, view, or clear warnings for a user.",
    },
    {
        "cat": "owner",
        "name": "t!say / t!sayembed <content>",
        "value": "Send a plain message or embed as the bot.",
    },
    {
        "cat": "owner",
        "name": "t!setactivity <type> <text>  (aliases: activity, presence)",
        "value": "Change the bot's activity status. Types: playing, watching, listening, streaming.",
    },
    {
        "cat": "owner",
        "name": "t!setlimit @user <n>  /  t!usage",
        "value": "Set per-user heavy command limit. `t!usage` checks your current count.",
    },
    {
        "cat": "owner",
        "name": "t!listservers  /  t!listchannels <guild_id>",
        "value": "List all guilds the bot is in, or all channels in a specific guild.",
    },
    {
        "cat": "owner",
        "name": "t!sendmsg <channel_id> <message>  (aliases: msgsend)",
        "value": "Send a message to any channel by ID.",
    },
]

_HELP_CATS = {
    "heavy": ("⚙️ Heavy Commands", discord.Color.dark_red()),
    "fun":   ("🎉 Fun",            discord.Color.blurple()),
    "owner": ("🔒 Owner",          discord.Color.dark_grey()),
}


def _build_help_embed(cat: str | None, entries: list[dict] | None = None) -> discord.Embed:
    """Build a help embed for a category, or for an arbitrary list of entries (search results)."""
    if entries is None:
        entries = [e for e in _HELP_ENTRIES if e["cat"] == cat]

    if cat and cat in _HELP_CATS:
        title, color = _HELP_CATS[cat]
    else:
        title, color = "🔍 Search Results", discord.Color.gold()

    embed = discord.Embed(title=title, color=color)
    for entry in entries[:25]:
        copyable_value = f"`{entry['name']}`\n{entry['value']}"
        embed.add_field(name=entry["name"], value=copyable_value, inline=False)

    if cat == "heavy":
        embed.set_footer(
            text=f"Formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))} · Max {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    elif cat == "owner":
        embed.set_footer(text="All owner commands are restricted to the configured owner ID(s).")

    return embed


def _build_home_embed() -> discord.Embed:
    counts = {c: sum(1 for e in _HELP_ENTRIES if e["cat"] == c) for c in _HELP_CATS}
    embed = discord.Embed(
        title="IHTX Bot — Help",
        description=(
            "Pick a category from the dropdown below, or run:\n"
            "`t!ihtxhelp <query>` to search all commands.\n\n"
            f"⚙️ **Heavy Commands** — {counts['heavy']} entries\n"
            f"🎉 **Fun** — {counts['fun']} entries\n"
            f"🔒 **Owner** — {counts['owner']} entries"
        ),
        color=0x5865F2,
    )
    embed.set_footer(text="I Hate The X — FFmpeg logo destruction bot")
    return embed


class _HelpSelect(discord.ui.Select):
    def __init__(self, invoker_id: int):
        self._invoker_id = invoker_id
        options = [
            discord.SelectOption(label="⚙️ Heavy Commands", value="heavy",
                                 description="ihtx, ffmpeg, multipitch, effects reference…"),
            discord.SelectOption(label="🎉 Fun",            value="fun",
                                 description="huehsv, trim, dl, catbox, tag, chat, ask…"),
            discord.SelectOption(label="🔒 Owner",          value="owner",
                                 description="blockuser, autoreply, warn, say, setlimit…"),
            discord.SelectOption(label="🏠 Home",            value="home",
                                 description="Back to the overview"),
        ]
        super().__init__(placeholder="Select a category…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._invoker_id:
            return await interaction.response.send_message(
                "Only the person who ran this command can use this menu.", ephemeral=True
            )
        choice = self.values[0]
        if choice == "home":
            embed = _build_home_embed()
        else:
            embed = _build_help_embed(choice)
        await interaction.response.edit_message(embed=embed, view=self.view)


class _HelpView(discord.ui.View):
    def __init__(self, invoker_id: int):
        super().__init__(timeout=300)
        self.add_item(_HelpSelect(invoker_id))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        # message ref not stored — Discord will leave it as-is after timeout


@bot.command(name="ihtxhelp", aliases=["bothelp"])
async def help_command(ctx: commands.Context, *, query: str = ""):
    query = query.strip().lower()

    if query:
        # ── Search mode ────────────────────────────────────────────────────
        results = [
            e for e in _HELP_ENTRIES
            if query in e["name"].lower() or query in e["value"].lower()
        ]
        if not results:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"🔍 No commands matched `{query}`. Try a shorter keyword.",
                    color=discord.Color.red(),
                )
            )
        embed = _build_help_embed(None, results)
        embed.set_footer(text=f"{len(results)} result(s) for '{query}'")
        return await ctx.reply(embed=embed)

    # ── Browse mode ────────────────────────────────────────────────────────
    embed = _build_home_embed()
    view = _HelpView(ctx.author.id)
    await ctx.reply(embed=embed, view=view)


# ---------- Update Log ----------

_UPDATELOG: list[dict] = [
    {
        "version": "v2.7",
        "date": "2026-06-21",
        "heavy": [
            "**t!ihtx swirl** — New pipe effect: geq-based rotational pixel-displacement swirl. Params: `swirl=<strength>[|radius][|xc][|yc][|linear|quad][|1:1]`. Default 180° with quad falloff. 1:1 mode scales to square before swirl and restores original dims after.",
        ],
        "fun": [],
    },
    {
        "version": "v2.6",
        "date": "2026-06-21",
        "heavy": [
            "**t!ihtx sierpinskiransomware** — New preset + pipe effect: 2×2 Sierpinski-style video grid (normal / 2× / 1.333× / 0.5× speed+pitch) using FFmpeg rubberband; outputs FLAC/MP4",
            "**t!ihtx** — Fixed FLAC-in-MOV container error for sierpinskiransomware preset (now outputs MP4)",
            "**t!ihtx** — sierpinskiransomware now available as a pipe effect in custom IHTX chains",
        ],
        "fun": [
            "**t!ihtx** (custom) — New processing status: '⏳ Processing your IHTX using pipe effects: `effects`×N', then '⌛ Done!' when finished",
            "**t!preview1280** — New result embed (MWTVE7691 credit, sync tip, thumbnail); segment 3 contrast fixed to 0.375",
            "**t!lexg / t!lec** — Fixed MissingRequiredAttachment crash; attachment now resolved from message context only",
            "**t!ihtx** — Auto-uploads to Catbox when output exceeds Discord 25 MB limit; sends embed with download link instead of erroring",
            "**t!ihtx** — Result embed now shows Resolution, Aspect Ratio, FPS, and File Size of output; new icon",
            "**t!chat / t!ask** — Removed 'slightly rude' from personality description",
            "**ffmpeg-full** installed — rubberband filter now available for pitch/tempo effects",
        ],
        "owner": [],
    },
    {
        "version": "v2.5",
        "date": "2026-06-20",
        "heavy": [],
        "fun": [
            "**t!chat / t!ask** — New Gen-Z personality: nonchalant, dry, sarcastic, 100% lowercase, specific emojis only (🥀 🫩 💀 😭 ✌️)",
            "**t!chat** — Temperature dropped to 0.4 for rigid, consistent output; response forced lowercase via `.lower()`",
            "**t!chat** — Mandatory 'son im crine' inclusion rule + complexity block ('idk bro 😭')",
            "**t!clearchat** — Now available on the TypeScript bot",
        ],
        "owner": [],
    },
    {
        "version": "v2.4",
        "date": "2026-06-20",
        "heavy": [],
        "fun": [
            "**t!chat / t!ask** — Rebuilt on pure Google GenAI pipeline: `types.GenerateContentConfig` with `system_instruction`, temperature 0.83, max 1024 tokens",
            "**t!chat** — OpenRouter dependency removed from chat entirely; Gemini 2.5 Flash is the sole engine",
            "**t!chat / t!ask** — Now available on the TypeScript bot too via `@google/genai` Node.js SDK",
            "**t!img2vid / t!imagevideo / t!video** — AI video generation commands removed",
        ],
        "owner": [],
    },
    {
        "version": "v2.3",
        "date": "2026-06-20",
        "heavy": [],
        "fun": [
            "**t!chat** — Gemini emergency fallback now uses a single stateless content string (system + question) instead of history/parts",
            "**t!chat** — Gemini also used directly when OpenRouter key is absent (no history overhead)",
            "**t!chat** — OpenRouter and Gemini log messages match new routing tier labels",
        ],
        "owner": [],
    },
    {
        "version": "v2.2",
        "date": "2026-06-20",
        "heavy": [],
        "fun": [
            "**t!chat / t!ask** — model fallback chain: qwen3-coder:free → llama-3.3-70b:free → openrouter/auto",
            "**t!chat** — switched to `ctx.defer()` for reliable hybrid (slash + prefix) response handling",
            "**t!chat** — prefix-aware system prompt with structured PREFIX AWARENESS RULES section",
        ],
        "owner": [],
    },
    {
        "version": "v2.1",
        "date": "2026-06-20",
        "heavy": [],
        "fun": [
            "**t!chat / t!ask** — now powered by OpenRouter (qwen/qwen3-coder:free) when `OPENROUTER_API_KEY` is set; falls back to Gemini automatically",
            "**t!chat** — system prompt now includes dynamic prefix awareness and username/channel context",
            "**t!ask** — confirmed alias of `t!chat` (unchanged behavior, new backend)",
        ],
        "owner": [],
    },
    {
        "version": "v2.0",
        "date": "2026-06-20",
        "heavy": [],
        "fun": [
            "**t!ihtxhelp** — command syntax now shown as a copyable code block inside each help entry",
        ],
        "owner": [],
    },
    {
        "version": "v1.9",
        "date": "2026-06-20",
        "heavy": [
            "**t!ihtx** — new `wave` pipe effect: sinusoidal pixel-displacement distortion with 8 params (hSpd|hFreq|hAmp|hPhase|vSpd|vFreq|vAmp|vPhase)",
            "**t!ihtx wave** — optional `sep` flag runs H and V waves as separate passes; `noclip` draws border box to hide edge clipping",
        ],
        "fun": [],
        "owner": [],
    },
    {
        "version": "v1.8",
        "date": "2026-06-20",
        "heavy": [
            "**t!ihtx p&p** — geq formula now clamps distortion with `max(..., 0)` to prevent pixel wrap-around artifacts",
            "**t!ihtx p&p** — fixed FLAC-in-MP4 error: all vf pipe steps now encode audio as `pcm_s24le` instead of `copy`",
            "**t!ihtx lut / invlum / VIDEO:** — same FLAC fix applied to those vf paths",
            "**t!ihtx** — removed `-f mp4` from concat step (let FFmpeg infer container from output extension)",
            "**t!syncaudio** — rewired to split input into separate video/audio temp files before syncing",
            "**t!syncaudio** — uses `-stream_loop -1` on audio + `-t <vd>` to pin output length (replaces `-shortest`)",
            "**t!syncaudio** — explicit `-map 0:v -map 1:a` for clean stream selection on both modes",
        ],
        "fun": [],
        "owner": [],
    },
    {
        "version": "v1.7",
        "date": "2026-06-20",
        "heavy": [
            "**t!ihtx** — new `shake=<h>|<v>` pipe effect: per-frame pixel displacement via geq, crops to original dims",
            "**t!ihtx** — `vreverse` pipe effect added: reverses video frames (chain with `areverse` for full reverse)",
            "**t!ihtx** — `swirl` removed from pipe engine (now handled by iscript tag)",
            "**t!ihtx shake** — audio now encoded as `pcm_s24le`; fixes FLAC-in-container error on certain inputs",
            "**t!multipitch** — audio now encoded as `pcm_s24le` instead of AAC",
            "**t!multipitch** — duration fixed: replaced `-shortest` with explicit `-t <video_duration>` to prevent clipping",
        ],
        "fun": [],
        "owner": [],
    },
    {
        "version": "v1.6",
        "date": "2026-06-19",
        "heavy": [
            "**t!ihtx** — pipe parser now uses commas as delimiters: `huehsv,negate,speed=1.5`",
            "**t!ihtx** — new `ffmpeg(...)` pipe step: pass raw FFmpeg args mid-chain e.g. `ffmpeg(-vf hue=h=50)`",
            "**t!ihtx** — processing status message now shows effect name + repeat count while running",
            "**t!ffmpeg** — new standalone command: run any FFmpeg args on an attachment; shows error log + elapsed time",
            "**t!ihtx** — output is always `.mp4`; `-f mp4` added to concat step; output_format param removed from custom syntax",
        ],
        "fun": [],
        "owner": [],
    },
    {
        "version": "v1.5",
        "date": "2026-06-18",
        "heavy": [
            "**t!ihtx** — parametric angle-based `mirror=<deg>` effect added (keeps left/right/top/bottom presets)",
            "**t!multipitch** — rubberband CLI fallback added for R3 engine",
            "**t!multipitch** — fixed speed bug in remux step (`-c:v copy` instead of libx264) to preserve timestamps",
        ],
        "fun": [],
        "owner": [],
    },
]

@bot.command(name="updatelog", aliases=["updates", "changelog"])
async def updatelog_command(ctx: commands.Context):
    """Show recent bot updates organized by category."""
    for entry in _UPDATELOG:
        embed = discord.Embed(
            title=f"📋 Update Log — {entry['version']}",
            color=discord.Color.og_blurple(),
        )
        embed.set_footer(text=entry["date"])

        if entry.get("heavy"):
            embed.add_field(
                name="⚙️ Heavy Commands",
                value="\n".join(f"• {line}" for line in entry["heavy"]),
                inline=False,
            )
        if entry.get("fun"):
            embed.add_field(
                name="🎉 Fun",
                value="\n".join(f"• {line}" for line in entry["fun"]),
                inline=False,
            )
        if entry.get("owner"):
            embed.add_field(
                name="🔒 Owner",
                value="\n".join(f"• {line}" for line in entry["owner"]),
                inline=False,
            )

        await ctx.send(embed=embed)


# ---------- Last Export Grab ----------

@bot.command(name="lexg", aliases=["lastexportgrab", "lec"])
async def lexg_command(ctx: commands.Context, duration: float = 5.0):
    """Grab the last N seconds of a video using reverse→trim→reverse.

    Usage: t!lexg [duration] — attach a video or reply to one.
    Default duration is 5 seconds.
    """
    # Resolve attachment
    if attachment is None:
        if ctx.message and ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    attachment = ref.attachments[0]
            except Exception:
                pass

    if not attachment:
        await ctx.reply(
            "**t!lexg [duration]** — Grab the last N seconds of a video.\n"
            "Attach a file or reply to one. Duration defaults to `5` seconds.\n"
            "Aliases: `t!lastexportgrab` `t!lec`"
        )
        return

    if duration <= 0 or duration > 3600:
        await ctx.reply("❌ Duration must be between 0 and 3600 seconds.")
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.reply(f"File too large (max 25 MB). Your file is {attachment.size / 1024 / 1024:.1f} MB.")
        return

    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        await ctx.reply(f"Unsupported file type `{suffix}`.")
        return

    is_video = suffix in VIDEO_EXTENSIONS
    status_msg = await ctx.reply(f"⏳ Grabbing last **{duration}s** of `{attachment.filename}`…")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"input{suffix}")
        output_path = os.path.join(tmpdir, "lec.mp4")
        try:
            await download_attachment(attachment, input_path)
        except Exception as e:
            await status_msg.edit(content=f"❌ Failed to download: {e}")
            return

        dur = duration
        if is_video:
            vf = f"reverse,trim=0:{dur},reverse"
            af = f"areverse,atrim=0:{dur},areverse"
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", vf,
                "-af", af,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ]
        else:
            af = f"areverse,atrim=0:{dur},areverse"
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-af", af,
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ]

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300),
            )
            ok = result.returncode == 0
            err = result.stderr
        except subprocess.TimeoutExpired:
            await status_msg.edit(content="❌ FFmpeg timed out.")
            return
        except Exception as e:
            await status_msg.edit(content=f"❌ FFmpeg error: {e}")
            return

        if not ok:
            await status_msg.edit(content=f"❌ FFmpeg failed:\n```\n{err[-1500:]}\n```")
            return

        out_size = os.path.getsize(output_path)
        if out_size > MAX_FILE_SIZE:
            await status_msg.edit(content="⬆️ Output too large for Discord — uploading to Catbox…")
            cb_url = await _upload_to_catbox(output_path)
            if cb_url:
                await ctx.reply(f"✅ Last **{dur}s** grabbed → {cb_url}")
                await status_msg.delete()
            else:
                await status_msg.edit(content="❌ Output too large for Discord and Catbox upload failed.")
            return

        out_filename = f"lec_{Path(attachment.filename).stem}.mp4"
        try:
            await ctx.reply(
                content=f"✅ Last **{dur}s** grabbed!",
                file=discord.File(output_path, filename=out_filename),
            )
            await status_msg.delete()
        except discord.HTTPException as e:
            await status_msg.edit(content=f"❌ Failed to upload: {e}")


# ---------- Download video ----------

@bot.command(name="dl", aliases=["dv", "download", "dlv"])
async def dl_command(ctx: commands.Context, url: str = ""):
    """Download a video or image from a URL.

    Works with:
    - Direct video/image links
    - YouTube, TikTok, etc (via yt-dlp if available)
    - Images too
    """
    # If no URL provided, try to get one from message content
    if not url:
        if ctx.message:
            # Try to find a URL in the message content
            parts = ctx.message.content.split()
            for p in parts[1:]:  # Skip command name
                if p.startswith("http://") or p.startswith("https://"):
                    url = p
                    break

    if not url:
        await ctx.reply(
            "**t!dl** — Download a video or image from a URL.\n\n"
            "Usage:\n"
            "`t!dl <url>`\n"
            "`t!dlv https://youtube.com/watch?v=...`\n"
            "`t!dl https://example.com/image.png`\n\n"
            "Aliases: `t!dv`, `t!dlv`, `t!download`"
        )
        return

    status_msg = await ctx.reply(f"\u2699\ufe0f Downloading from URL...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Try yt-dlp first if it's a video URL
        if yt_dlp and re.search(r"(youtube|youtu\.be|tiktok|x\.com|twitter|instagram|reddit|vimeo|twitch|fb\.watch|facebook|bilibili)", url, re.I):
            try:
                output_path = os.path.join(tmpdir, "downloaded")
                ydl_opts = {
                    "format": "best[filesize<25M]/bestvideo[height<=720][filesize<25M]+bestaudio/best[filesize<25M]/best",
                    "outtmpl": output_path + ".%(ext)s",
                    "quiet": True,
                    "no_warnings": True,
                    "max_filesize": MAX_FILE_SIZE,
                    "cookiefile": None,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    downloaded = ydl.prepare_filename(info)
                    if os.path.exists(downloaded):
                        out_size = os.path.getsize(downloaded)
                        if out_size > MAX_FILE_SIZE:
                            await status_msg.edit(content="\u274c Downloaded file too large (>25 MB).")
                            return
                        filename = os.path.basename(downloaded)
                        await ctx.reply(
                            content=f"\u2705 Downloaded via yt-dlp: `{info.get('title', 'Untitled')}`",
                            file=discord.File(downloaded, filename=filename),
                        )
                        await status_msg.delete()
                        return
            except Exception as e:
                # Fall back to direct download
                pass

        # Direct download
        try:
            import urllib.request
            import ssl
            ssl_ctx = ssl.create_default_context()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            # Try to guess extension from URL
            parsed = urllib.parse.urlparse(url)
            ext = Path(parsed.path).suffix or ".mp4"
            output_path = os.path.join(tmpdir, f"downloaded{ext}")
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=120) as resp:
                with open(output_path, "wb") as f:
                    f.write(resp.read())
            out_size = os.path.getsize(output_path)
            if out_size > MAX_FILE_SIZE:
                await status_msg.edit(content="\u274c Downloaded file too large (>25 MB).")
                return
            filename = os.path.basename(output_path)
            await ctx.reply(
                content=f"\u2705 Downloaded from URL!",
                file=discord.File(output_path, filename=filename),
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit(content=f"\u274c Failed to download: {e}")


# ---------- Owner-only moderation / utility commands ----------

def _parse_digits(s: str) -> int:
    """Extract numeric ID from mention or plain id string."""
    if not s:
        raise ValueError("No id provided")
    m = re.search(r"(\d{6,20})", s)
    if m:
        return int(m.group(1))
    try:
        return int(s)
    except Exception:
        raise ValueError("Could not parse id")


@bot.command(name="blockuser")
@commands.check(_is_owner)
async def blockuser(ctx: commands.Context, user: str):
    """Owner-only: add a user ID or mention to the user blocklist."""
    try:
        user_id = _parse_digits(user)
    except ValueError:
        await ctx.reply("❌ Invalid user. Provide a mention or numeric ID.")
        return
    if user_id in blocklist:
        await ctx.reply(f"User `{user_id}` is already blocked.")
        return
    blocklist.add(user_id)
    _save_blocklist()
    await ctx.reply(f"✅ Blocked user `{user_id}`.")


@bot.command(name="unblockuser")
@commands.check(_is_owner)
async def unblockuser(ctx: commands.Context, user: str):
    """Owner-only: remove a user ID or mention from the user blocklist."""
    try:
        user_id = _parse_digits(user)
    except ValueError:
        await ctx.reply("❌ Invalid user. Provide a mention or numeric ID.")
        return
    if user_id not in blocklist:
        await ctx.reply(f"User `{user_id}` is not blocked.")
        return
    blocklist.discard(user_id)
    _save_blocklist()
    await ctx.reply(f"✅ Unblocked user `{user_id}`.")


@bot.command(name="blockchannel")
@commands.check(_is_owner)
async def blockchannel(ctx: commands.Context, channel: str = None):
    """Owner-only: add a channel to the channel blocklist. If omitted, blocks current channel."""
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return
    if channel_id in channel_blocks:
        await ctx.reply(f"Channel `{channel_id}` is already blocked.")
        return
    channel_blocks.add(channel_id)
    _save_channel_blocks()
    await ctx.reply(f"✅ Blocked channel `{channel_id}`.")


@bot.command(name="unblockchannel")
@commands.check(_is_owner)
async def unblockchannel(ctx: commands.Context, channel: str = None):
    """Owner-only: remove a channel from the channel blocklist. If omitted, unblocks current channel."""
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return
    if channel_id not in channel_blocks:
        await ctx.reply(f"Channel `{channel_id}` is not blocked.")
        return
    channel_blocks.discard(channel_id)
    _save_channel_blocks()
    await ctx.reply(f"✅ Unblocked channel `{channel_id}`.")


@bot.command(name="keywordblock", aliases=["blockkeyword", "kb"])
@commands.check(_is_owner)
async def keywordblock(ctx: commands.Context, keyword: str, channel: str = None):
    """Owner-only: block a keyword in a single channel.

    This is channel-scoped only; it does not create a global keyword block.
    """
    normalized = _normalize_keyword(keyword)
    if not normalized:
        await ctx.reply("❌ Provide a keyword or phrase to block.")
        return
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return

    blocked = keyword_blocks.setdefault(channel_id, set())
    if normalized in blocked:
        await ctx.reply(f"Keyword `{normalized}` is already blocked in channel `{channel_id}`.")
        return
    blocked.add(normalized)
    _save_keyword_blocks()
    await ctx.reply(f"✅ Blocked keyword `{normalized}` in channel `{channel_id}`.")


@bot.command(name="keywordblockremove", aliases=["unblockkeyword", "removekeywordblock", "kbr"])
@commands.check(_is_owner)
async def keywordblockremove(ctx: commands.Context, keyword: str, channel: str = None):
    """Owner-only: remove a keyword block from a single channel."""
    normalized = _normalize_keyword(keyword)
    if not normalized:
        await ctx.reply("❌ Provide a keyword or phrase to unblock.")
        return
    if channel is None:
        channel_id = ctx.channel.id
    else:
        try:
            channel_id = _parse_digits(channel)
        except ValueError:
            await ctx.reply("❌ Invalid channel. Provide a channel mention or numeric ID.")
            return

    blocked = keyword_blocks.get(channel_id, set())
    if normalized not in blocked:
        await ctx.reply(f"Keyword `{normalized}` is not blocked in channel `{channel_id}`.")
        return
    blocked.discard(normalized)
    if not blocked:
        keyword_blocks.pop(channel_id, None)
    # Also clear custom message for this keyword
    msgs = keyword_block_messages.get(channel_id, {})
    msgs.pop(normalized, None)
    if not msgs:
        keyword_block_messages.pop(channel_id, None)
    _save_keyword_blocks()
    await ctx.reply(f"✅ Removed keyword block `{normalized}` from channel `{channel_id}`.")


@bot.command(name="say")
@commands.check(_is_owner)
async def say(ctx: commands.Context, *, message: str):
    """Owner-only: make the bot send a plain message in the current channel."""
    try:
        await ctx.send(message)
        if ctx.message:
            await ctx.message.add_reaction("✅")
    except Exception as e:
        await ctx.reply(f"❌ Failed to send message: {e}")


@bot.command(name="sayembed")
@commands.check(_is_owner)
async def sayembed(ctx: commands.Context, *, content: str):
    """
    Owner-only: send an embed.
    If `content` contains a '|' it will split into title|description, otherwise content is used as description.
    Example:
      t!sayembed Title | This is the embed body
    """
    try:
        if "|" in content:
            title, desc = [p.strip() for p in content.split("|", 1)]
        else:
            title = ""
            desc = content
        emb = discord.Embed(title=title or None, description=desc or None, color=discord.Color.dark_red())
        await ctx.send(embed=emb)
        if ctx.message:
            await ctx.message.add_reaction("✅")
    except Exception as e:
        await ctx.reply(f"❌ Failed to send embed: {e}")


@bot.command(name="keywordblockmsg", aliases=["kbmsg", "blockmsg"])
@commands.check(_is_owner)
async def keywordblockmsg(ctx: commands.Context, keyword: str, *, message: str):
    """Owner-only: set a custom message for a keyword block.

    Everything after the keyword is the message. Use {mention} or {user} for user mention.
    Example:
      t!keywordblockmsg swearword no swearing, {mention}!
      t!keywordblockmsg badword dont say that, {user}
    """
    normalized = _normalize_keyword(keyword)
    if not normalized:
        await ctx.reply("❌ Provide a keyword.")
        return
    channel_id = ctx.channel.id

    blocked = keyword_blocks.get(channel_id, set())
    if normalized not in blocked:
        await ctx.reply(f"❌ Keyword `{normalized}` is not blocked in this channel. Block it first with `t!keywordblock`.")
        return

    msgs = keyword_block_messages.setdefault(channel_id, {})
    msgs[normalized] = message
    _save_keyword_blocks()
    await ctx.reply(f"✅ Custom message set for keyword `{normalized}` in this channel.")


# ---------- Autoreplies ----------

@bot.command(name="autoreply", aliases=["ar"])
@commands.check(_is_owner)
async def autoreply(ctx: commands.Context, trigger: str, channel: discord.TextChannel = None, *, response: str):
    """Owner-only: add an autoreply. When anyone says the trigger, the bot replies.

    Leave channel blank (or omit) to reply in ALL channels.
    Use {mention} or {user} to ping the user in the response.
    Example (all channels):
      t!autoreply hello Hello there, {mention}!
    Example (specific channel):
      t!autoreply hello #general Hello there, {mention}!
    """
    trigger_norm = trigger.strip().lower()
    if not trigger_norm:
        await ctx.reply("❌ Provide a trigger word or phrase.")
        return
    if not response:
        await ctx.reply("❌ Provide a response message.")
        return
    channel_id = channel.id if channel else None
    # Preserve existing blocked_channels if updating an existing entry
    existing_blocked = []
    if trigger_norm in autoreplies and isinstance(autoreplies[trigger_norm], dict):
        existing_blocked = autoreplies[trigger_norm].get("blocked_channels", [])
    autoreplies[trigger_norm] = {"response": response, "channel_id": channel_id, "blocked_channels": existing_blocked}
    _save_autoreplies()
    channel_note = f" in {channel.mention}" if channel else " in **all channels**"
    await ctx.reply(f"✅ Autoreply set{channel_note}: `{trigger_norm}` → {response}")


@bot.command(name="blockarchannel", aliases=["bac", "silencear"])
@commands.check(_is_owner)
async def blockarchannel(ctx: commands.Context, trigger: str, channel: discord.TextChannel = None):
    """Owner-only: prevent an autoreply trigger from firing in a specific channel.

    The autoreply stays active in all other channels — only this one is silenced.
    Run again with the same trigger + channel to unblock it.

    Example:
      t!blockarchannel hello           ← silences 'hello' in current channel
      t!blockarchannel hello #general  ← silences 'hello' in #general
    """
    trigger_norm = trigger.strip().lower()
    if trigger_norm not in autoreplies:
        await ctx.reply(f"❌ No autoreply found for `{trigger_norm}`.")
        return

    target_channel = channel or ctx.channel
    cid = target_channel.id

    entry = autoreplies[trigger_norm]
    if not isinstance(entry, dict):
        entry = {"response": entry, "channel_id": None, "blocked_channels": []}
    blocked = entry.setdefault("blocked_channels", [])

    if cid in blocked:
        blocked.remove(cid)
        autoreplies[trigger_norm] = entry
        _save_autoreplies()
        await ctx.reply(f"✅ Autoreply `{trigger_norm}` **unblocked** in {target_channel.mention} — it will fire there again.")
    else:
        blocked.append(cid)
        autoreplies[trigger_norm] = entry
        _save_autoreplies()
        await ctx.reply(f"✅ Autoreply `{trigger_norm}` **silenced** in {target_channel.mention} — it won't fire there anymore.")


@bot.command(name="removeautoreply", aliases=["rar", "deautoreply"])
@commands.check(_is_owner)
async def removeautoreply(ctx: commands.Context, *, trigger: str):
    """Owner-only: remove an autoreply trigger."""
    trigger_norm = trigger.strip().lower()
    if trigger_norm not in autoreplies:
        await ctx.reply(f"❌ No autoreply for `{trigger_norm}`.")
        return
    del autoreplies[trigger_norm]
    _save_autoreplies()
    await ctx.reply(f"✅ Removed autoreply for `{trigger_norm}`.")


@bot.command(name="removearmentions", aliases=["rarm", "noarping"])
@commands.check(_is_owner)
async def removearmentions(ctx: commands.Context, *, trigger: str):
    """Owner-only: remove {mention} and {user} tokens from an autoreply's response.

    Leaves the autoreply active but stops it from pinging users.
    Example:
      t!removearmentions hello
    """
    trigger_norm = trigger.strip().lower()
    if trigger_norm not in autoreplies:
        await ctx.reply(f"❌ No autoreply found for `{trigger_norm}`.")
        return

    entry = autoreplies[trigger_norm]
    response = entry.get("response", "") if isinstance(entry, dict) else str(entry)

    cleaned = response.replace("{mention}", "").replace("{user}", "").strip()
    cleaned = re.sub(r"  +", " ", cleaned)

    if cleaned == response:
        await ctx.reply(f"ℹ️ Autoreply `{trigger_norm}` has no mention tokens to remove.")
        return

    if isinstance(entry, dict):
        autoreplies[trigger_norm]["response"] = cleaned
    else:
        autoreplies[trigger_norm] = {"response": cleaned, "channel_id": None}

    _save_autoreplies()
    await ctx.reply(f"✅ Removed mention pings from `{trigger_norm}`.\nNew response: {cleaned}")


@bot.command(name="autoreplies", aliases=["listautoreplies", "arlist"])
async def listautoreplies(ctx: commands.Context):
    """List all active autoreply triggers and their responses."""
    if not autoreplies:
        await ctx.reply("No autoreplies set.")
        return
    lines = []
    for trigger, entry in autoreplies.items():
        resp = entry.get("response", entry) if isinstance(entry, dict) else entry
        ch_id = entry.get("channel_id") if isinstance(entry, dict) else None
        ch_note = f" (<#{ch_id}>)" if ch_id else " (all channels)"
        lines.append(f"`{trigger}`{ch_note} → {resp}")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = line
        else:
            current = (current + "\n" + line).strip()
    if current:
        chunks.append(current)
    for chunk in chunks:
        await ctx.reply(chunk)


# ---------- Autoreply2 ----------

@bot.command(name="autoreply2", aliases=["ar2"])
@commands.check(_is_owner)
async def autoreply2_cmd(ctx: commands.Context):
    """Owner-only: toggle AI auto-reply on/off for the current channel.

    When enabled, the bot responds to every message in this channel using AI.
    Run again to toggle off.

    Example:
      t!autoreply2   ← toggles on in current channel
      t!autoreply2   ← toggles off
    """
    cid = ctx.channel.id
    if cid in autoreply2:
        autoreply2.discard(cid)
        _save_autoreply2()
        await ctx.reply(f"✅ AI auto-reply **disabled** in {ctx.channel.mention}.")
    else:
        autoreply2.add(cid)
        _save_autoreply2()
        await ctx.reply(f"✅ AI auto-reply **enabled** in {ctx.channel.mention}. The bot will reply to every message using AI.")


@bot.command(name="autoreply2list", aliases=["ar2list"])
@commands.check(_is_owner)
async def autoreply2list(ctx: commands.Context):
    """Owner-only: list all channels with autoreply2 active."""
    if not autoreply2:
        await ctx.reply("No channels have AI auto-reply enabled.")
        return
    lines = [f"<#{cid}>" for cid in autoreply2]
    await ctx.reply("AI auto-reply enabled in:\n" + "\n".join(lines))


@bot.command(name="removear2mentions", aliases=["rarm2", "noar2ping"])
@commands.check(_is_owner)
async def removear2mentions(ctx: commands.Context, user: discord.Member):
    """Owner-only: toggle off @mention pings for a user in autoreply2 responses.

    When set, autoreply2 will still reply to their messages but won't ping them.
    Run again on the same user to re-enable pings.

    Example:
      t!removear2mentions @someone   ← disables pings for them
      t!removear2mentions @someone   ← re-enables pings
    """
    uid = user.id
    if uid in autoreply2_no_mention:
        autoreply2_no_mention.discard(uid)
        _save_autoreply2_no_mention()
        await ctx.reply(f"✅ Autoreply2 will now **ping** {user.mention} again.")
    else:
        autoreply2_no_mention.add(uid)
        _save_autoreply2_no_mention()
        await ctx.reply(f"✅ Autoreply2 will no longer ping {user.mention} when replying.")


# ---------- Warnings ----------

@bot.command(name="warn")
@commands.check(_is_owner)
async def warn(ctx: commands.Context, user: discord.Member, *, reason: str = "No reason given."):
    """Owner-only: warn a user and track their warning count."""
    uid = user.id
    entry = {"reason": reason, "timestamp": time.time(), "mod_id": ctx.author.id}
    warnings_data.setdefault(uid, []).append(entry)
    _save_warnings()
    count = len(warnings_data[uid])
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        color=discord.Color.orange(),
    )
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Warnings", value=f"{count}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Warned by {ctx.author.display_name}")
    await ctx.reply(embed=embed)
    try:
        await user.send(f"⚠️ You have been warned in **{ctx.guild.name}**.\n**Reason:** {reason}\n**Total warnings:** {count}")
    except discord.HTTPException:
        pass


@bot.command(name="warnings", aliases=["warncount", "warnlist"])
@commands.check(_is_owner)
async def warnings_cmd(ctx: commands.Context, user: discord.Member):
    """Owner-only: view all warnings for a user."""
    uid = user.id
    user_warns = warnings_data.get(uid, [])
    if not user_warns:
        await ctx.reply(f"{user.mention} has no warnings.")
        return
    embed = discord.Embed(
        title=f"⚠️ Warnings for {user.display_name}",
        color=discord.Color.orange(),
    )
    for i, w in enumerate(user_warns, 1):
        ts = int(w.get("timestamp", 0))
        embed.add_field(
            name=f"#{i} — <t:{ts}:R>",
            value=w.get("reason", "No reason"),
            inline=False,
        )
    embed.set_footer(text=f"Total: {len(user_warns)} warning(s)")
    await ctx.reply(embed=embed)


@bot.command(name="clearwarn", aliases=["clearwarnings", "unwarn"])
@commands.check(_is_owner)
async def clearwarn(ctx: commands.Context, user: discord.Member):
    """Owner-only: clear all warnings for a user."""
    uid = user.id
    count = len(warnings_data.pop(uid, []))
    _save_warnings()
    await ctx.reply(f"✅ Cleared **{count}** warning(s) for {user.mention}.")


# ---------- Owner: activity control ----------

@bot.command(name="setactivity", aliases=["activity", "presence"])
@commands.check(_is_owner)
async def setactivity(ctx: commands.Context, activity_type: str, *, text: str):
    """Owner-only: change the bot's activity.

    Usage:
      t!setactivity watching some cool video
      t!setactivity listening lo-fi beats
      t!setactivity playing Minecraft
      t!setactivity streaming Cool Stream | https://twitch.tv/yourchannel
    """
    activity_type = activity_type.lower().strip()
    if activity_type in ("watching", "watch", "w"):
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        label = "Watching"
        save_type = "watching"
    elif activity_type in ("listening", "listen", "l"):
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        label = "Listening to"
        save_type = "listening"
    elif activity_type in ("playing", "play", "p"):
        activity = discord.Game(name=text)
        label = "Playing"
        save_type = "playing"
    elif activity_type in ("streaming", "stream", "s"):
        parts = [p.strip() for p in text.split("|", 1)]
        stream_name = parts[0]
        stream_url = parts[1] if len(parts) > 1 else "https://twitch.tv/placeholder"
        activity = discord.Streaming(name=stream_name, url=stream_url)
        label = "Streaming"
        save_type = "streaming"
        text = f"{stream_name} | {stream_url}"
    else:
        await ctx.reply("❌ Activity type must be `watching`, `listening`, `playing`, or `streaming`.")
        return
    await bot.change_presence(activity=activity)
    try:
        _activity_file = Path("bot/activity.json")
        with _activity_file.open("w") as _af:
            json.dump({"type": save_type, "name": text}, _af)
    except Exception:
        pass
    if ctx.message:
        await ctx.message.add_reaction("✅")
    await ctx.reply(f"✅ Activity set to **{label}** {text}", ephemeral=True)


# ---------- Owner: cross-server messaging ----------

@bot.command(name="sendmsg", aliases=["msgsend"])
@commands.check(_is_owner)
async def sendmsg(ctx: commands.Context, channel_id: str, *, text: str):
    """Owner-only: send a message to any channel the bot can access, by channel ID.

    Usage:
      t!sendmsg <channel_id> <message>
      t!sendmsg 123456789012345678 Hello from the bot!
    """
    try:
        cid = int(channel_id.strip("<#>"))
    except ValueError:
        await ctx.reply("❌ Invalid channel ID. Provide a numeric ID or channel mention.")
        return

    channel = bot.get_channel(cid)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cid)
        except discord.NotFound:
            await ctx.reply("❌ Channel not found. Make sure the bot is in that server.")
            return
        except discord.Forbidden:
            await ctx.reply("❌ Bot doesn't have permission to access that channel.")
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.DMChannel)):
        await ctx.reply("❌ That channel type doesn't support text messages.")
        return

    try:
        await channel.send(text)
        if ctx.message:
            await ctx.message.add_reaction("✅")
    except discord.Forbidden:
        await ctx.reply("❌ Bot lacks permission to send messages in that channel.")
    except discord.HTTPException as e:
        await ctx.reply(f"❌ Failed to send: {e}")


@bot.command(name="listservers", aliases=["servers", "guilds"])
@commands.check(_is_owner)
async def listservers(ctx: commands.Context):
    """Owner-only: list all servers the bot is in with their IDs and channel counts."""
    guilds = sorted(bot.guilds, key=lambda g: g.name.lower())
    if not guilds:
        await ctx.reply("Bot is not in any servers.")
        return

    lines = []
    for g in guilds:
        text_channels = [c for c in g.channels if isinstance(c, discord.TextChannel)]
        lines.append(f"**{g.name}** (`{g.id}`) — {g.member_count} members, {len(text_channels)} text channels")

    # Split into chunks of 10 servers per message to avoid hitting the 2000 char limit
    chunk_size = 10
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i:i + chunk_size]
        header = f"**Servers ({len(guilds)} total):**\n" if i == 0 else ""
        await ctx.reply(header + "\n".join(chunk))


@bot.command(name="listchannels", aliases=["channels"])
@commands.check(_is_owner)
async def listchannels(ctx: commands.Context, *, guild_id: str):
    """Owner-only: list all text channels in a server by guild ID."""
    try:
        gid = int(guild_id.strip())
    except ValueError:
        await ctx.reply("❌ Provide a numeric guild/server ID.")
        return

    guild = bot.get_guild(gid)
    if guild is None:
        await ctx.reply("❌ Server not found. Make sure the bot is in that server.")
        return

    text_channels = sorted(
        [c for c in guild.channels if isinstance(c, discord.TextChannel)],
        key=lambda c: c.position,
    )
    if not text_channels:
        await ctx.reply(f"No text channels found in **{guild.name}**.")
        return

    lines = [f"**{guild.name}** text channels:"]
    for c in text_channels:
        lines.append(f"#{c.name} — `{c.id}`")

    chunk_size = 20
    for i in range(0, len(lines), chunk_size):
        await ctx.reply("\n".join(lines[i:i + chunk_size]))


# ---------- AI Chat ----------

_OWNER_PERSONAS: dict[int, dict] = {
    1355759019330895973: {
        "name": "Creator",
        "favorite_game": "Roblox",
        "likes": ["video editing", "Discord bots"],
    },
}

_CHAT_SYSTEM_PROMPT = """You are Clankered thatoneguynobodyinvited, a friendly Discord bot.

You help users with editing, and videos. From now on, speak like a chill Gen Z friend. Use modern slang, meme culture references, and occasional AAVE-inspired internet terms naturally. Keep responses short, casual, and conversational. Avoid sounding formal or robotic. Match the user's energy. Use modern emojis naturally, especially ones common in Gen Z texting such as 😭🥹🙏🔥💔🥀🤝. Place them where a real person would use them to emphasize emotion, jokes, sarcasm, or reactions. Don't spam emojis in every sentence. Make them feel natural and conversational."""

_chat_histories: dict[int, list[dict]] = {}
_CHAT_MAX_HISTORY = 20

_GEMINI_MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".avi": "video/x-msvideo", ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}
_GEMINI_MAX_ATTACH_BYTES = 20 * 1024 * 1024  # 20 MB


async def _build_gemini_parts(text: str, attachments) -> list[dict]:
    """Build Gemini content parts from text + Discord attachments."""
    parts = []
    for att in attachments:
        ext = Path(att.filename).suffix.lower()
        mime = _GEMINI_MIME_MAP.get(ext)
        if mime and att.size <= _GEMINI_MAX_ATTACH_BYTES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(att.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            parts.append({
                                "inline_data": {
                                    "data": base64.b64encode(data).decode(),
                                    "mime_type": mime,
                                }
                            })
            except Exception:
                pass
    if text:
        parts.append({"text": text})
    if not parts:
        parts.append({"text": ""})
    return parts


@bot.command(name="chat", aliases=["ask", "ai"])
async def chat(ctx: commands.Context, *, question: str):
    """Chat with the IHTX AI assistant."""
    await ctx.defer()

    username = ctx.author.display_name
    current_prefix = ctx.prefix if ctx.prefix else "t!"

    system_identity = (
        f"You are 'Clankered Thatoneguynobodyinvited', an advanced video editing bot that makes IHTXES.\n"
        f"You are talking to {username}. Always stick to these absolute rules:\n"
        f"1. Act extremely nonchalant, dry, and sarcastic. Speak exactly like a modern Gen-Z TikTok user.\n"
        f"2. CRITICAL TEXT FORMATTING: Always type in 100% lowercase letters. Do not capitalize anything ever.\n"
        f"3. Use lowercase slang and abbreviations constantly: idk, wya, alr, bet, sup, rn, fr, smh, tbh. Never capitalize them.\n"
        f"4. ONLY use these specific emojis: 🥀, 🫩, 💀, 😭, ✌️. Do not use random happy or positive emojis.\n"
        f"5. MANDATORY REPLIES: Every time the user starts talking, makes a statement, or shares something, you must naturally include the exact phrase 'son im crine' in your response text.\n"
        f"6. COMPLEXITY BLOCK: If the user asks for something highly complicated, technical, long-winded, or annoying, just say 'idk bro 😭' and give a dry, sarcastic deflection. Keep responses short and human-made.\n"
        f"7. If a query is NSFW, reject it flat out with zero effort.\n"
        f"8. Your command prefix is '{current_prefix}'. If needed, refer to tools like '{current_prefix}ihtx' or '{current_prefix}ffmpeg' in pure lowercase."
    )

    if _genai_client is None:
        await ctx.send("idk bro 😭 no api key configured")
        return

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _genai_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=question,
                config=_genai_types.GenerateContentConfig(
                    system_instruction=system_identity,
                    temperature=0.4,
                    max_output_tokens=1024,
                ),
            ),
        )
        # Safely extract text — response.text raises ValueError on safety blocks
        try:
            bot_response = response.text
        except Exception:
            bot_response = None

        # Fallback: walk candidates manually if .text failed
        if not bot_response:
            try:
                bot_response = response.candidates[0].content.parts[0].text
            except Exception:
                bot_response = None

        if bot_response:
            bot_response = bot_response.lower()
            if len(bot_response) > 2000:
                bot_response = bot_response[:1995] + "..."
            await ctx.send(bot_response)
        else:
            print(f"[chat] empty/blocked response for query: {question[:80]!r}")
            await ctx.send("idk bro 😭 gemini blocked that one, try rewording it")
    except Exception as e:
        import traceback
        print(f"genai glitch: {type(e).__name__}: {e}")
        traceback.print_exc()
        await ctx.send("idk bro 😭")


@bot.command(name="clearchat", aliases=["resetai", "chatclear"])
async def clearchat(ctx: commands.Context):
    """Clear your personal AI conversation history."""
    _chat_histories.pop(ctx.author.id, None)
    await ctx.reply("🧹 Your conversation history has been cleared.")



# ---------- Heavy limit usage check ----------

@bot.command(name="usage", aliases=["heavyusage", "limit", "checklimit"])
async def usage(ctx: commands.Context):
    """Check your heavy command usage for the current 24-hour window."""
    user_id = ctx.author.id
    now = time.time()
    day_ago = now - 86400
    used_timestamps = [t for t in heavy_usage.get(user_id, []) if t > day_ago]

    if _is_owner_by_id(user_id):
        limit = HEAVY_LIMIT_OWNER
    else:
        limit = heavy_limits.get(user_id, HEAVY_LIMIT_DEFAULT)

    used = len(used_timestamps)
    remaining = max(0, limit - used)

    embed = discord.Embed(title="⚡ Heavy Command Usage", color=discord.Color.blurple())
    embed.add_field(name="Used", value=str(used), inline=True)
    embed.add_field(name="Remaining", value=str(remaining), inline=True)
    embed.add_field(name="Limit", value=str(limit), inline=True)

    if used_timestamps:
        oldest = min(used_timestamps)
        resets_at = int(oldest + 86400)
        embed.add_field(name="Oldest resets", value=f"<t:{resets_at}:R>", inline=False)

    embed.set_footer(text=f"Window: rolling 24h · Heavy commands: {', '.join(sorted(HEAVY_COMMANDS))}")
    await ctx.reply(embed=embed)


@bot.command(name="setlimit", aliases=["sl"])
@commands.check(_is_bot_mod)
async def setlimit(ctx: commands.Context, user: discord.User, limit: int):
    """[Bot Mod] Set a user's heavy command limit per 24h."""
    if limit < 0:
        await ctx.reply("❌ Limit must be 0 or greater.")
        return
    heavy_limits[user.id] = limit
    _save_limits()
    embed = discord.Embed(
        title="✅ Limit Set",
        description=f"Heavy command limit for {user.mention} set to **{limit}/24h**.",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Set by {ctx.author}")
    await ctx.reply(embed=embed)


@setlimit.error
async def setlimit_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ Only bot owners and Level 15 moderators can set limits.")
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("❌ Usage: `t!setlimit @user <number>`")
    else:
        await ctx.reply(f"❌ Error: {error}")


@bot.command(name="resetlimit", aliases=["rl", "resetusage"])
@commands.check(_is_bot_mod)
async def resetlimit(ctx: commands.Context, user: discord.User):
    """[Bot Mod] Reset a user's heavy command usage back to zero."""
    heavy_usage.pop(user.id, None)
    _save_usage()
    embed = discord.Embed(
        title="✅ Usage Reset",
        description=f"Heavy command usage for {user.mention} has been reset to **0**.",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Reset by {ctx.author} · Their 24h window is now clear")
    await ctx.reply(embed=embed)


@resetlimit.error
async def resetlimit_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ Only bot owners and Level 15 moderators can reset usage limits.")
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("❌ Couldn't find that user. Try mentioning them or using their user ID.")
    else:
        await ctx.reply(f"❌ Error: {error}")


# ---------- Fun commands ----------

_8BALL_RESPONSES = [
    "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
    "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
    "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

@bot.command(name="8ball", aliases=["eightball"])
async def eightball(ctx: commands.Context, *, question: str):
    """Ask the magic 8-ball a yes/no question."""
    response = random.choice(_8BALL_RESPONSES)
    embed = discord.Embed(
        description=f"🎱 **{response}**",
        color=discord.Color.dark_blue()
    )
    embed.set_footer(text=f'"{question}"')
    await ctx.reply(embed=embed)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """Check bot latency — shows receive, send, and total times."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    receive_ms = (now - ctx.message.created_at).total_seconds() * 1000

    send_start = time.perf_counter()
    msg = await ctx.reply("🏓 Pong!")
    send_ms = (time.perf_counter() - send_start) * 1000

    total_ms = receive_ms + send_ms
    await msg.edit(content=(
        f"🏓 Pong!\n"
        f"```\n"
        f"Receiving your message: {receive_ms:.0f}ms\n"
        f"Sending my message:     {send_ms:.0f}ms\n"
        f"Total time:             {total_ms:.0f}ms\n"
        f"```"
    ))


@bot.command(name="coinflip", aliases=["flip", "coin"])
async def coinflip(ctx: commands.Context):
    """Flip a coin — heads or tails."""
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await ctx.reply(f"**{result}**!")


@bot.command(name="roll", aliases=["dice", "d"])
async def roll(ctx: commands.Context, sides: int = 6):
    """Roll a die with the given number of sides."""
    if sides < 2:
        await ctx.reply("❌ Die must have at least 2 sides.")
        return
    if sides > 1000000:
        await ctx.reply("❌ That's too many sides.")
        return
    result = random.randint(1, sides)
    await ctx.reply(f"🎲 You rolled a **d{sides}** and got **{result}**!")


@bot.command(name="rps", aliases=["rockpaperscissors"])
async def rps(ctx: commands.Context, choice: str):
    """Play rock, paper, scissors against the bot."""
    choice = choice.lower().strip()
    alias_map = {"r": "rock", "p": "paper", "s": "scissors", "✊": "rock", "✋": "paper", "✌️": "scissors"}
    choice = alias_map.get(choice, choice)
    if choice not in ("rock", "paper", "scissors"):
        await ctx.reply("❌ Choose `rock`, `paper`, or `scissors`.")
        return
    bot_choice = random.choice(["rock", "paper", "scissors"])
    icons = {"rock": "✊", "paper": "✋", "scissors": "✌️"}
    wins_against = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if choice == bot_choice:
        result = "It's a tie! 🤝"
        color = discord.Color.greyple()
    elif wins_against[choice] == bot_choice:
        result = "You win! 🎉"
        color = discord.Color.green()
    else:
        result = "You lose! 💀"
        color = discord.Color.red()
    embed = discord.Embed(
        description=f"{icons[choice]} **{choice.capitalize()}** vs **{bot_choice.capitalize()}** {icons[bot_choice]}\n\n{result}",
        color=color
    )
    await ctx.reply(embed=embed)


@bot.command(name="choose", aliases=["pick"])
async def choose(ctx: commands.Context, *, options: str):
    """Pick one option from a pipe-separated list."""
    choices = [o.strip() for o in options.split("|") if o.strip()]
    if len(choices) < 2:
        await ctx.reply("❌ Give me at least 2 options separated by `|`.")
        return
    picked = random.choice(choices)
    await ctx.reply(f"🎯 I choose: **{picked}**")


@bot.command(name="rate")
async def rate(ctx: commands.Context, *, thing: str):
    """Rate something out of 10."""
    score = (hash(thing.lower()) % 11 + 11) % 11
    bar = "█" * score + "░" * (10 - score)
    await ctx.reply(f"**{thing}**: {bar} **{score}/10**")


_SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣"]
_SLOT_JACKPOT_CHANCE = 0.25  # 25% chance of 777


@bot.command(name="slots", aliases=["slot"])
async def slots(ctx: commands.Context):
    """Spin the slot machine — land 777 (25% chance) to win 200 XP!"""
    if random.random() < _SLOT_JACKPOT_CHANCE:
        reels = ["7️⃣", "7️⃣", "7️⃣"]
    else:
        # Guarantee NOT all 7s
        reels = [random.choice(_SLOT_SYMBOLS) for _ in range(3)]
        while reels == ["7️⃣", "7️⃣", "7️⃣"]:
            reels = [random.choice(_SLOT_SYMBOLS) for _ in range(3)]

    display = " | ".join(reels)
    jackpot = reels == ["7️⃣", "7️⃣", "7️⃣"]

    if jackpot:
        levelup_msgs = await _award_xp(ctx, 200)
        _load_xp_data()
        data = _get_user_xp(ctx.author.id)
        level = data["level"]
        if level >= _MAX_LEVEL:
            progress_line = f"Level MAX 🏆 — {data['xp']} total XP"
        else:
            cur, thresh, _ = _level_progress(data)
            progress_line = f"Level {level} — {cur}/{thresh} XP"

        await ctx.reply(
            f"🎰 [ {display} ]\n\n"
            f"🎊 **JACKPOT! 777!** You win **+200 XP!**\n"
            f"{progress_line}"
        )
        for lm in levelup_msgs:
            await ctx.send(lm)
    else:
        all_same = len(set(reels)) == 1
        if all_same:
            await ctx.reply(f"🎰 [ {display} ]\n\n✨ Three of a kind! No XP though — only 777 wins.")
        else:
            await ctx.reply(f"🎰 [ {display} ]\n\nNo luck this time. Try again!")


# ---------- Fun games ----------

_HANGMAN_WORDS = [
    "python", "discord", "ffmpeg", "glitch", "chaos", "render", "filter",
    "codec", "bitrate", "buffer", "kernel", "shader", "pixel", "vector",
    "matrix", "binary", "server", "latency", "keyframe", "montage",
    "waveform", "frequency", "amplitude", "distortion", "reverb", "chorus",
    "flanger", "compressor", "equalizer", "saturation", "contrast",
]

_HANGMAN_ART = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]


@bot.command(name="hangman", aliases=["hm"])
async def hangman(ctx: commands.Context):
    """Play a game of hangman — guess the word one letter at a time."""
    word = random.choice(_HANGMAN_WORDS)
    guessed: set[str] = set()
    wrong = 0
    max_wrong = 6

    def display() -> str:
        blanks = " ".join(c if c in guessed else "_" for c in word)
        wrong_letters = " ".join(sorted(guessed - set(word))) or "none"
        return (
            f"{_HANGMAN_ART[wrong]}\n"
            f"**Word:** `{blanks}`\n"
            f"**Wrong guesses ({wrong}/{max_wrong}):** {wrong_letters}"
        )

    msg = await ctx.reply(f"🎮 **Hangman!** Guess one letter at a time.\n{display()}")

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and len(m.content) == 1
            and m.content.isalpha()
        )

    while wrong < max_wrong:
        try:
            guess_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.edit(content=f"⏱️ Time's up! The word was **{word}**.")
            return

        letter = guess_msg.content.lower()
        if letter in guessed:
            await ctx.send(f"You already guessed `{letter}`!", delete_after=4)
            continue

        guessed.add(letter)
        if letter not in word:
            wrong += 1

        won = all(c in guessed for c in word)
        if won:
            await msg.edit(content=f"🎉 You got it! The word was **{word}**!\n{display()}")
            return
        if wrong >= max_wrong:
            break
        await msg.edit(content=display())

    await msg.edit(content=f"💀 Game over! The word was **{word}**.\n{_HANGMAN_ART[6]}")


_BJ_VALUES = {"A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
              "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}
_BJ_SUITS = ["♠", "♥", "♦", "♣"]


def _bj_deck():
    return [f"{r}{s}" for s in _BJ_SUITS for r in _BJ_VALUES]


def _bj_hand_value(hand: list[str]) -> int:
    total, aces = 0, 0
    for card in hand:
        rank = card[:-1]
        total += _BJ_VALUES[rank]
        if rank == "A":
            aces += 1
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _bj_fmt(hand: list[str], hide_second: bool = False) -> str:
    if hide_second:
        return f"{hand[0]}, ??"
    return "  ".join(hand)


@bot.command(name="blackjack", aliases=["bj", "21"])
async def blackjack(ctx: commands.Context):
    """Play blackjack against the bot. Type `hit` or `stand`."""
    deck = _bj_deck()
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    def board(hide_dealer: bool = True) -> str:
        pv = _bj_hand_value(player)
        dv = _bj_hand_value(dealer) if not hide_dealer else "?"
        return (
            f"🃏 **Blackjack**\n"
            f"**Your hand:** {_bj_fmt(player)} — `{pv}`\n"
            f"**Dealer:**    {_bj_fmt(dealer, hide_dealer)} — `{dv}`\n\n"
            f"Type **`hit`** or **`stand`**"
        )

    msg = await ctx.reply(board())

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.lower() in ("hit", "stand", "h", "s")
        )

    while True:
        pv = _bj_hand_value(player)
        if pv > 21:
            await msg.edit(content=f"💥 **Bust!** You went over 21 with `{pv}`.\n**Dealer had:** {_bj_fmt(dealer)} — `{_bj_hand_value(dealer)}`")
            return
        if pv == 21:
            break
        try:
            action_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.edit(content=f"⏱️ Time's up!\n**Dealer had:** {_bj_fmt(dealer)}")
            return

        action = action_msg.content.lower()
        if action in ("hit", "h"):
            player.append(deck.pop())
            await msg.edit(content=board())
        else:
            break

    # Dealer plays
    while _bj_hand_value(dealer) < 17:
        dealer.append(deck.pop())

    pv = _bj_hand_value(player)
    dv = _bj_hand_value(dealer)

    if dv > 21:
        result = f"🎉 **Dealer busts!** You win! (`{pv}` vs `{dv}`)"
    elif pv > dv:
        result = f"🎉 **You win!** (`{pv}` vs `{dv}`)"
    elif pv == dv:
        result = f"🤝 **Push!** It's a tie. (`{pv}` vs `{dv}`)"
    else:
        result = f"💀 **Dealer wins!** (`{pv}` vs `{dv}`)"

    await msg.edit(content=(
        f"🃏 **Blackjack — Final**\n"
        f"**Your hand:** {_bj_fmt(player)} — `{pv}`\n"
        f"**Dealer:**    {_bj_fmt(dealer)} — `{dv}`\n\n"
        f"{result}"
    ))


_TTT_EMPTY = "⬜"
_TTT_X = "❌"
_TTT_O = "⭕"


def _ttt_board(cells: list[str]) -> str:
    rows = [" ".join(cells[i*3:(i+1)*3]) for i in range(3)]
    return "\n".join(rows)


def _ttt_check_winner(cells: list[str]) -> str | None:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a, b, c in wins:
        if cells[a] == cells[b] == cells[c] and cells[a] != _TTT_EMPTY:
            return cells[a]
    return None


def _ttt_bot_move(cells: list[str]) -> int:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    empty = [i for i, c in enumerate(cells) if c == _TTT_EMPTY]
    # Win if possible
    for a, b, c in wins:
        group = [cells[a], cells[b], cells[c]]
        if group.count(_TTT_O) == 2 and _TTT_EMPTY in group:
            return [a, b, c][[cells[a], cells[b], cells[c]].index(_TTT_EMPTY)]
    # Block player
    for a, b, c in wins:
        group = [cells[a], cells[b], cells[c]]
        if group.count(_TTT_X) == 2 and _TTT_EMPTY in group:
            return [a, b, c][[cells[a], cells[b], cells[c]].index(_TTT_EMPTY)]
    # Centre
    if cells[4] == _TTT_EMPTY:
        return 4
    return random.choice(empty)


@bot.command(name="tictactoe", aliases=["ttt"])
async def tictactoe(ctx: commands.Context):
    """Play tic tac toe against the bot. Reply with a number 1–9."""
    cells = [_TTT_EMPTY] * 9
    num_grid = "```\n1 2 3\n4 5 6\n7 8 9\n```"

    def board_msg(extra: str = "") -> str:
        return f"❌ **Tic Tac Toe** — You are ❌, I am ⭕\n{num_grid}\n{_ttt_board(cells)}{extra}"

    msg = await ctx.reply(board_msg("\n\nPick a square (1–9):"))

    def check(m: discord.Message) -> bool:
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.strip() in [str(i) for i in range(1, 10)]
        )

    for _ in range(9):
        # Player turn
        try:
            pick_msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await msg.edit(content="⏱️ Time's up!")
            return

        idx = int(pick_msg.content.strip()) - 1
        if cells[idx] != _TTT_EMPTY:
            await ctx.send("❌ That square is taken! Pick another.", delete_after=4)
            continue

        cells[idx] = _TTT_X
        winner = _ttt_check_winner(cells)
        if winner:
            await msg.edit(content=board_msg(f"\n\n🎉 **You win!**"))
            return
        if _TTT_EMPTY not in cells:
            await msg.edit(content=board_msg(f"\n\n🤝 **Draw!**"))
            return

        # Bot turn
        bot_idx = _ttt_bot_move(cells)
        cells[bot_idx] = _TTT_O
        winner = _ttt_check_winner(cells)
        if winner:
            await msg.edit(content=board_msg(f"\n\n💀 **I win!**"))
            return
        if _TTT_EMPTY not in cells:
            await msg.edit(content=board_msg(f"\n\n🤝 **Draw!**"))
            return

        await msg.edit(content=board_msg("\n\nYour turn — pick a square (1–9):"))


# ---------- XP / Leveling system ----------

_XP_DATA_FILE = Path("bot/xp_data.json")
_xp_data: dict[str, dict] = {}
_XP_MOD_ROLE_NAME = "Moderator"
_XP_PER_CORRECT = 100
_MAX_LEVEL = 15


def _xp_threshold(level: int) -> int:
    """XP required to advance FROM this level to the next."""
    if level <= 3:
        return 1000
    if level <= 6:
        return 1250
    if level <= 9:
        return 1750
    return 2000


def _load_xp_data() -> None:
    global _xp_data
    try:
        if _XP_DATA_FILE.exists():
            with _XP_DATA_FILE.open() as f:
                _xp_data = json.load(f)
        else:
            _xp_data = {}
    except Exception:
        _xp_data = {}


def _save_xp_data() -> None:
    try:
        with _XP_DATA_FILE.open("w") as f:
            json.dump(_xp_data, f, indent=2)
    except Exception as e:
        print(f"[xp] Failed to save xp_data: {e}")


def _get_user_xp(user_id: int) -> dict:
    key = str(user_id)
    if key not in _xp_data:
        _xp_data[key] = {"xp": 0, "level": 1}
    return _xp_data[key]


def _level_progress(data: dict) -> tuple[int, int, int]:
    """Returns (current_xp_in_level, threshold, level)."""
    level = data["level"]
    xp = data["xp"]
    # XP is cumulative; compute how much belongs to current level
    spent = 0
    for lv in range(1, level):
        spent += _xp_threshold(lv)
    return xp - spent, _xp_threshold(level), level


async def _award_xp(ctx: commands.Context, amount: int) -> list[str]:
    """Award XP to the command author. Returns list of level-up messages."""
    _load_xp_data()
    uid = ctx.author.id
    data = _get_user_xp(uid)
    messages: list[str] = []

    if data["level"] >= _MAX_LEVEL:
        _save_xp_data()
        return messages

    data["xp"] += amount

    # Check for level ups
    while data["level"] < _MAX_LEVEL:
        thresh = _xp_threshold(data["level"])
        current_in_level, _, _ = _level_progress(data)
        if current_in_level >= thresh:
            data["level"] += 1
            new_level = data["level"]
            if new_level >= _MAX_LEVEL:
                data["is_mod"] = True
                messages.append(
                    f"🏆 **MAX LEVEL!** {ctx.author.mention} reached **Level {_MAX_LEVEL}**! "
                    f"You are now a **Bot Moderator** and can use `t!setlimit` and `t!resetlimit`!"
                )
                break
            else:
                messages.append(
                    f"⬆️ **Level up!** {ctx.author.mention} is now **Level {new_level}**!"
                )
        else:
            break

    _save_xp_data()
    return messages


_load_xp_data()


@bot.command(name="level", aliases=["rank", "xp"])
async def level_cmd(ctx: commands.Context, member: discord.Member = None):
    """Check your XP level and progress."""
    _load_xp_data()
    target = member or ctx.author
    data = _get_user_xp(target.id)
    level = data["level"]

    if level >= _MAX_LEVEL:
        embed = discord.Embed(
            title=f"🏆 {target.display_name} — MAX LEVEL",
            description=f"**Level {_MAX_LEVEL}** • Total XP: **{data['xp']}**\n\nYou've earned the **{_XP_MOD_ROLE_NAME}** role!",
            color=discord.Color.gold()
        )
    else:
        current_in_level, thresh, _ = _level_progress(data)
        bar_filled = int((current_in_level / thresh) * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        embed = discord.Embed(
            title=f"⭐ {target.display_name}",
            description=(
                f"**Level {level}** → Level {level + 1}\n"
                f"`{bar}` {current_in_level}/{thresh} XP\n\n"
                f"Total XP: **{data['xp']}**"
            ),
            color=discord.Color.blurple()
        )
    await ctx.reply(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "top"])
async def leaderboard(ctx: commands.Context):
    """Show the top 10 XP earners."""
    _load_xp_data()
    if not _xp_data:
        await ctx.reply("No one has any XP yet! Play `t!trivia` to earn some.")
        return

    sorted_users = sorted(_xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = []
    for i, (uid, data) in enumerate(sorted_users):
        member = ctx.guild.get_member(int(uid)) if ctx.guild else None
        name = member.display_name if member else f"User {uid}"
        lv = data["level"]
        lv_str = f"**MAX**" if lv >= _MAX_LEVEL else f"Lv {lv}"
        lines.append(f"{medals[i]} **{name}** — {lv_str} • {data['xp']} XP")

    embed = discord.Embed(
        title="🏆 XP Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    await ctx.reply(embed=embed)


# ---------- Music trivia ----------

_MUSIC_TRIVIA = [
    ("How many strings does a standard guitar have?", ["4", "5", "6", "7"], 2),
    ("Which musical symbol indicates a piece should be played softly?", ["f", "p", "ff", "mf"], 1),
    ("What does 'BPM' stand for?", ["Beats Per Minute", "Bass Per Measure", "Bars Per Melody", "Beats Per Measure"], 0),
    ("Which instrument has black and white keys?", ["Violin", "Trumpet", "Piano", "Harp"], 2),
    ("How many notes are in a standard musical scale (e.g. C major)?", ["5", "6", "7", "8"], 2),
    ("What is the lowest male singing voice called?", ["Tenor", "Baritone", "Bass", "Alto"], 2),
    ("Which time signature is also called 'common time'?", ["3/4", "4/4", "2/2", "6/8"], 1),
    ("What does 'forte' mean in music?", ["Slow", "Soft", "Loud", "Fast"], 2),
    ("How many semitones are in an octave?", ["8", "10", "12", "14"], 2),
    ("Which instrument is Beethoven famous for playing?", ["Violin", "Flute", "Piano", "Cello"], 2),
    ("What does 'a cappella' mean?", ["With full orchestra", "Without instrumental accompaniment", "Very slowly", "Repeated section"], 1),
    ("Which genre originated in New Orleans in the early 1900s?", ["Blues", "Jazz", "Rock", "Soul"], 1),
    ("What is the correct order of a standard orchestra from front to back?", ["Brass, Strings, Woodwinds, Percussion", "Strings, Woodwinds, Brass, Percussion", "Percussion, Brass, Strings, Woodwinds", "Woodwinds, Strings, Brass, Percussion"], 1),
    ("Which note is one half-step above C?", ["D", "C#", "B", "Cb"], 1),
    ("What does 'legato' mean?", ["Detached notes", "Smooth and connected", "Very fast", "Getting louder"], 1),
    ("How many beats does a whole note receive in 4/4 time?", ["1", "2", "3", "4"], 3),
    ("What family of instruments does the trumpet belong to?", ["Woodwind", "String", "Brass", "Percussion"], 2),
    ("Which term means gradually getting louder?", ["Diminuendo", "Staccato", "Crescendo", "Fermata"], 2),
    ("What is the standard concert pitch for the note A?", ["420 Hz", "432 Hz", "440 Hz", "450 Hz"], 2),
    ("Which clef is most commonly used for piano treble parts?", ["Bass clef", "Alto clef", "Treble clef", "Tenor clef"], 2),
    ("What does 'D.C. al Fine' mean in sheet music?", ["Go to the sign", "Repeat from the beginning to the end mark", "Play very softly", "Slow down"], 1),
    ("How many lines are on a standard musical staff?", ["3", "4", "5", "6"], 2),
    ("Which instrument uses a bow?", ["Flute", "Oboe", "Violin", "Tuba"], 2),
    ("What is the name for the speed of a piece of music?", ["Pitch", "Tempo", "Dynamics", "Timbre"], 1),
    ("Which scale uses only the black keys of the piano?", ["Major scale", "Minor scale", "Chromatic scale", "Pentatonic scale"], 3),
    ("What does 'ritardando' (rit.) mean?", ["Getting louder", "Getting softer", "Gradually slowing down", "Gradually speeding up"], 2),
    ("Which instrument is NOT a woodwind?", ["Flute", "Clarinet", "French Horn", "Bassoon"], 2),
    ("What is the Italian word for 'moderate tempo'?", ["Allegro", "Andante", "Moderato", "Presto"], 2),
    ("Which interval contains two half-steps?", ["Unison", "Half step", "Whole step", "Minor third"], 2),
    ("What is the highest woodwind instrument?", ["Oboe", "Flute", "Piccolo", "Clarinet"], 2),
]


@bot.command(name="trivia")
async def trivia(ctx: commands.Context):
    """Play a 10-question music trivia game — earn 100 XP per correct answer!"""
    labels = ["A", "B", "C", "D"]
    questions = random.sample(_MUSIC_TRIVIA, 10)
    score = 0

    intro = await ctx.reply(
        "🎵 **Music Trivia — 10 Questions!**\n"
        "Answer each question with **A**, **B**, **C**, or **D**.\n"
        "You earn **100 XP** per correct answer!\n\n"
        "Starting in 3 seconds..."
    )
    await asyncio.sleep(3)

    for i, (q, options, correct_idx) in enumerate(questions, 1):
        choices_text = "\n".join(f"**{labels[j]}**  {opt}" for j, opt in enumerate(options))
        msg = await ctx.reply(
            f"🎵 **Question {i}/10**\n\n"
            f"{q}\n\n"
            f"{choices_text}\n\n"
            f"*Type A, B, C, or D — 20 seconds*"
        )

        def check(m: discord.Message) -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.upper().strip() in labels
            )

        try:
            answer_msg = await bot.wait_for("message", check=check, timeout=20)
            picked = labels.index(answer_msg.content.upper().strip())
        except asyncio.TimeoutError:
            await msg.edit(content=(
                f"🎵 **Question {i}/10** — ⏱️ Time's up!\n\n"
                f"{q}\n\n{choices_text}\n\n"
                f"✅ Correct answer: **{labels[correct_idx]}** — {options[correct_idx]}"
            ))
            await asyncio.sleep(1.5)
            continue

        if picked == correct_idx:
            score += 1
            await msg.edit(content=(
                f"🎵 **Question {i}/10** — ✅ Correct! (+100 XP)\n\n"
                f"{q}\n\n{choices_text}"
            ))
        else:
            await msg.edit(content=(
                f"🎵 **Question {i}/10** — ❌ Wrong! "
                f"You said **{labels[picked]}**, answer was **{labels[correct_idx]}** — {options[correct_idx]}\n\n"
                f"{q}\n\n{choices_text}"
            ))
        await asyncio.sleep(1.5)

    # Award XP
    xp_earned = score * _XP_PER_CORRECT
    levelup_msgs = await _award_xp(ctx, xp_earned)
    _load_xp_data()
    data = _get_user_xp(ctx.author.id)
    level = data["level"]

    if level >= _MAX_LEVEL:
        progress_line = f"**Level MAX** 🏆 — {data['xp']} total XP"
    else:
        cur, thresh, _ = _level_progress(data)
        progress_line = f"**Level {level}** — {cur}/{thresh} XP toward next level"

    summary = (
        f"🎵 **Trivia Complete!** {ctx.author.mention}\n\n"
        f"Score: **{score}/10** correct — **+{xp_earned} XP** earned\n"
        f"{progress_line}"
    )
    await ctx.send(summary)

    for lm in levelup_msgs:
        await ctx.send(lm)


# ---------- Random media pool ----------

RANDOM_POOL_FILE = Path("bot/random_pool.json")
_random_pool: list[str] = []


def _load_random_pool() -> None:
    global _random_pool
    try:
        if RANDOM_POOL_FILE.exists():
            with RANDOM_POOL_FILE.open() as f:
                _random_pool = [str(u) for u in json.load(f) if str(u).strip()]
        else:
            _random_pool = []
    except Exception:
        _random_pool = []


def _save_random_pool() -> None:
    RANDOM_POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RANDOM_POOL_FILE.open("w") as f:
        json.dump(_random_pool, f, indent=2)


_load_random_pool()


@bot.command(name="random", aliases=["rand"])
async def random_command(ctx: commands.Context, subcommand: str = "", *, args: str = ""):
    """Persistent random media pool.

    Usage:
      t!random                    — post a random item from the pool
      t!random add <url>          — owner: add a URL to the pool
      t!random add  (attachment)  — owner: add an attached file's URL
      t!random remove <url>       — owner: remove a URL from the pool
      t!random list               — owner: list all items in the pool
      t!random clear              — owner: wipe the entire pool
    """
    sub = subcommand.strip().lower()

    # ── Roll ────────────────────────────────────────────────────────────────
    if sub == "":
        if not _random_pool:
            await ctx.reply("❌ The random pool is empty. An owner can add items with `t!random add <url>`.")
            return
        chosen = random.choice(_random_pool)
        await ctx.reply(chosen)
        return

    # ── Owner-only subcommands ───────────────────────────────────────────────
    if not _is_owner(ctx):
        await ctx.reply("❌ Only owners can manage the random pool.")
        return

    # ── Add ─────────────────────────────────────────────────────────────────
    if sub == "add":
        urls_to_add: list[str] = []

        # Attachment on this message
        if ctx.message and ctx.message.attachments:
            for att in ctx.message.attachments:
                urls_to_add.append(att.url)

        # URL argument
        url_arg = args.strip()
        if url_arg:
            urls_to_add.append(url_arg)

        if not urls_to_add:
            await ctx.reply("❌ Provide a URL or attach a file: `t!random add <url>`")
            return

        added = []
        for url in urls_to_add:
            if url not in _random_pool:
                _random_pool.append(url)
                added.append(url)

        if added:
            _save_random_pool()
            lines = "\n".join(f"• `{u}`" for u in added)
            await ctx.reply(f"✅ Added {len(added)} item(s) to the pool ({len(_random_pool)} total):\n{lines}")
        else:
            await ctx.reply("ℹ️ All provided URLs are already in the pool.")
        return

    # ── Remove ──────────────────────────────────────────────────────────────
    if sub in ("remove", "rm", "del", "delete"):
        url_arg = args.strip()
        if not url_arg:
            await ctx.reply("❌ Provide a URL to remove: `t!random remove <url>`")
            return
        if url_arg in _random_pool:
            _random_pool.remove(url_arg)
            _save_random_pool()
            await ctx.reply(f"✅ Removed from pool ({len(_random_pool)} remaining).")
        else:
            await ctx.reply("❌ That URL isn't in the pool.")
        return

    # ── List ────────────────────────────────────────────────────────────────
    if sub == "list":
        if not _random_pool:
            await ctx.reply("The random pool is empty.")
            return
        lines = "\n".join(f"{i+1}. {u}" for i, u in enumerate(_random_pool))
        # Split into chunks to avoid the 2000-char Discord limit
        chunk, chunks = "", []
        for line in lines.splitlines():
            if len(chunk) + len(line) + 1 > 1900:
                chunks.append(chunk)
                chunk = line
            else:
                chunk = (chunk + "\n" + line).lstrip("\n")
        if chunk:
            chunks.append(chunk)
        await ctx.reply(f"**Random pool ({len(_random_pool)} items):**\n{chunks[0]}")
        for c in chunks[1:]:
            await ctx.send(c)
        return

    # ── Clear ───────────────────────────────────────────────────────────────
    if sub == "clear":
        count = len(_random_pool)
        _random_pool.clear()
        _save_random_pool()
        await ctx.reply(f"✅ Cleared {count} item(s) from the pool.")
        return

    await ctx.reply(
        "Unknown subcommand. Usage:\n"
        "`t!random` — roll\n"
        "`t!random add <url>` — add item (owner)\n"
        "`t!random remove <url>` — remove item (owner)\n"
        "`t!random list` — list all items (owner)\n"
        "`t!random clear` — wipe pool (owner)"
    )


# ---------- Message filtering ----------

@bot.event
async def on_message(message: discord.Message):
    # Track bot replies so on_message_edit can clean them up
    if message.author == bot.user and message.reference and message.reference.message_id:
        user_id = message.reference.message_id
        _response_map.setdefault(user_id, []).append(message.id)
        # Trim the map if it gets too large (drop oldest entries)
        if len(_response_map) > _RESPONSE_MAP_MAX:
            oldest = next(iter(_response_map))
            del _response_map[oldest]
        return

    if message.author.bot:
        return

    # Autoreplies (check before keyword blocks, skip commands)
    if not message.content.startswith("t!"):
        content_lower = message.content.lower()
        for trigger, entry in autoreplies.items():
            if trigger in content_lower:
                ch_id = entry.get("channel_id") if isinstance(entry, dict) else None
                blocked = entry.get("blocked_channels", []) if isinstance(entry, dict) else []
                # Skip if restricted to a different channel
                if ch_id is not None and message.channel.id != ch_id:
                    continue
                # Skip if this channel is explicitly blocked for this trigger
                if message.channel.id in blocked:
                    continue
                resp = entry.get("response", entry) if isinstance(entry, dict) else entry
                reply = resp.replace("{mention}", message.author.mention).replace("{user}", message.author.mention)
                await message.reply(reply)
                break

        # Autoreply2 — AI reply to every message in enabled channels
        if message.channel.id in autoreply2 and _genai_client is not None:
            ok2, _ = _check_heavy_limit(message.author.id)
            if ok2:
                uid2 = message.author.id
                no_ping = uid2 in autoreply2_no_mention
                hist2 = _chat_histories.setdefault(uid2, [])
                system2 = _CHAT_SYSTEM_PROMPT
                if _OWNER_PERSONAS.get(uid2):
                    system2 += f"\n\nYou are currently speaking with ✨le creator✨. Be extra friendly and hype them up."
                parts2 = await _build_gemini_parts(message.content, message.attachments)
                hist2.append({"role": "user", "parts": parts2})
                if len(hist2) > _CHAT_MAX_HISTORY:
                    hist2[:] = hist2[-_CHAT_MAX_HISTORY:]
                try:
                    loop2 = asyncio.get_event_loop()
                    resp2 = await loop2.run_in_executor(
                        None,
                        lambda: _genai_client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=hist2,
                            config=_genai_types.GenerateContentConfig(
                                system_instruction=system2,
                                max_output_tokens=1024,
                            ),
                        ),
                    )
                    reply2_text = resp2.text
                    text_only2 = [p for p in parts2 if "text" in p] or [{"text": "[media]"}]
                    hist2[-1] = {"role": "user", "parts": text_only2}
                    hist2.append({"role": "model", "parts": [{"text": reply2_text}]})
                    chunks2 = [reply2_text[i:i+1900] for i in range(0, len(reply2_text), 1900)]
                    for i, chunk in enumerate(chunks2):
                        await message.reply(chunk, mention_author=(not no_ping and i == 0))
                except Exception:
                    pass

    # Always allow owners to manage the bot and allow all bot commands to run.
    if not _is_owner_by_id(message.author.id) and not message.content.startswith("t!"):
        keyword = _blocked_keyword_for_message(message.channel.id, message.content)
        if keyword:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            try:
                msg = _blocked_keyword_message(message.channel.id, keyword, message.author.mention)
                await message.channel.send(
                    msg,
                    delete_after=8,
                )
            except discord.HTTPException:
                pass
            return

    await bot.process_commands(message)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Re-run a command when the user edits their message.

    Deletes all bot replies that were made in response to the original message,
    then re-processes the edited message as a fresh command invocation.
    """
    if after.author.bot:
        return
    # Only re-run if the content actually changed and it's a bot command
    if before.content == after.content:
        return
    if not after.content.startswith("t!"):
        return

    # Delete previous bot responses to this message
    old_ids = _response_map.pop(before.id, [])
    for msg_id in old_ids:
        try:
            old_msg = await after.channel.fetch_message(msg_id)
            await old_msg.delete()
        except Exception:
            pass

    # Re-process as a fresh command invocation
    await bot.process_commands(after)


# ---------- Catbox upload ----------

@bot.command(name="catbox", aliases=["cb", "upload"])
async def catbox_upload(ctx: commands.Context):
    """Upload any file to catbox.moe and return a permanent direct link.

      t!catbox   (with file attached, or reply to a message with a file)
    """
    src = attachment
    if src is None and ctx.message.attachments:
        src = ctx.message.attachments[0]
    if src is None and ctx.message.reference:
        try:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.attachments:
                src = ref.attachments[0]
        except Exception:
            pass
    if src is None:
        await ctx.reply("📎 attach a file or reply to a message with a file to upload it to catbox.moe")
        return

    status_msg = await ctx.reply(f"⬆️ uploading `{src.filename}` to catbox.moe…")
    try:
        file_bytes = await src.read()
        data = aiohttp.FormData()
        data.add_field("reqtype", "fileupload")
        data.add_field(
            "fileToUpload",
            file_bytes,
            filename=src.filename,
            content_type=src.content_type or "application/octet-stream",
        )
        async with aiohttp.ClientSession() as session:
            async with session.post("https://catbox.moe/user/api.php", data=data, timeout=aiohttp.ClientTimeout(total=120)) as r:
                result = await r.text()
        if result.startswith("https://"):
            await status_msg.edit(content=f"✅ {result.strip()}")
        else:
            await status_msg.edit(content=f"❌ catbox error: {result[:300]}")
    except Exception as e:
        await status_msg.edit(content=f"❌ upload failed: {e}")


# ---------- Error handling & run ----------

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"Missing argument: `{error.param.name}`. Use `t!ihtxhelp` for usage.")
        return
    # Permission errors from owner-only commands
    if isinstance(error, commands.CheckFailure):
        # If check failed for owner-only commands, be quiet (or you could notify)
        return
    raise error


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)
    bot.run(TOKEN)
