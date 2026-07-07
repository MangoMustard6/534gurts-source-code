"""
TagScript parser — resolves variables and dispatches engine blocks.

Syntax:
  Variables  : {varname}  /  {varname.N}
  Functions  : {random:a|b|c}  {random:1:100}  {choose:a|b|c}
               {upper:text}  {lower:text}  {title:text}  {reverse:text}
               {len:text}  {repeat:N|text}  {slice:s|e|text}
               {math:1+2}  {if:a|=|b|then:yes}
  Engines    : {attach:URL}  {text:…}  {eval:…}
               {iscript:…}  {mediascript:…}  {py:…}  {bash:…}
               {embedjson:{…}}  {ihtx:…}  {tagscript:…}

Script prefix syntax (multiline):
  tagscript:        tscript:
  imagescript:      iscript:
  mediascript:      mscript:
  python:           py:
  bash:             sh:
"""

from __future__ import annotations

import random
import re
from typing import Any

# ── Script alias map ──────────────────────────────────────────────────────────
# Maps any alias/prefix → canonical engine name used in the registry.
SCRIPT_ALIASES: dict[str, str] = {
    "tagscript":   "tagscript",
    "tscript":     "tagscript",
    "imagescript": "iscript",
    "iscript":     "iscript",
    "mediascript": "mediascript",
    "mscript":     "mediascript",
    "python":      "py",
    "py":          "py",
    "bash":        "bash",
    "sh":          "bash",
    "ffmpeg":      "ffmpeg",
    "ff":          "ffmpeg",
    "frei0r":      "frei0r",
    "fr0r":        "frei0r",
    # brace-syntax engines (kept for KNOWN_ENGINES)
    "text":        "text",
    "eval":        "eval",
    "attach":      "attach",
    "embedjson":   "embedjson",
    "ihtx":        "ihtx",
    # new engines
    "foreach":     "foreach",
    "set":         "set",
    "tag":         "tag",
    "js":          "js",
    "javascript":  "js",
}

# Human-readable display names for engine types
ENGINE_DISPLAY_NAMES: dict[str, str] = {
    "tagscript":   "TagScript",
    "iscript":     "ImageScript",
    "mediascript": "MediaScript",
    "py":          "Python",
    "bash":        "Bash",
    "ffmpeg":      "FFmpeg",
    "frei0r":      "Frei0r",
    "text":        "Text",
    "eval":        "Eval",
    "attach":      "Attach",
    "embedjson":   "EmbedJSON",
    "ihtx":        "IHTX",
    "foreach":     "ForEach",
    "set":         "Set",
    "tag":         "Tag",
    "js":          "JavaScript",
}

# Execution order — lower index = runs first
_ENGINE_ORDER: list[str] = [
    "set", "foreach", "tag",
    "tagscript", "iscript", "mediascript", "py", "bash",
    "ffmpeg", "frei0r", "js",
    "text", "attach", "embedjson", "eval", "ihtx",
]
_ENGINE_PRIORITY: dict[str, int] = {name: i for i, name in enumerate(_ENGINE_ORDER)}

# ── Regex patterns ────────────────────────────────────────────────────────────

_VAR_RE = re.compile(r"\{([a-z_][a-z0-9_]*(?:\.[a-z0-9_]+)?)\}", re.IGNORECASE)

# Matches {name:content} — content may contain ONE level of nested {}.
_BLOCK_RE = re.compile(
    r"\{([a-z_][a-z0-9_]*):((?:[^{}]|\{[^{}]*\})*)\}",
    re.DOTALL | re.IGNORECASE,
)

# Script-prefix line: "enginealias:" alone on a line (trailing whitespace OK)
_SCRIPT_PREFIX_LINE = re.compile(
    r"^(" + "|".join(re.escape(k) for k in SCRIPT_ALIASES) + r"):\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Engines whose content may contain deeply nested braces (e.g. JSON objects).
# These are extracted by a depth-counting pre-pass before the regex runs.
_DEEP_ENGINES = ("embedjson", "eval", "foreach", "set")

# All engine names — blocks with these names are dispatched to engines.
KNOWN_ENGINES = frozenset(SCRIPT_ALIASES.values())


# ── Safe math ─────────────────────────────────────────────────────────────────

class _MathParser:
    """Recursive-descent math parser — no eval/exec used."""

    _TOK = re.compile(r"\d+\.?\d*|[+\-*/^%()\s]")

    def __init__(self, expr: str):
        raw = "".join(self._TOK.findall(expr))
        self._tokens = [t for t in re.split(r"(\d+\.?\d*|[+\-*/^%()])", raw) if t.strip()]
        self._pos = 0

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _eat(self) -> str:
        t = self._tokens[self._pos]
        self._pos += 1
        return t

    def parse(self) -> float:
        v = self._expr()
        if self._pos < len(self._tokens):
            raise ValueError(f"unexpected token: {self._peek()!r}")
        return v

    def _expr(self) -> float:
        return self._additive()

    def _additive(self) -> float:
        left = self._mult()
        while self._peek() in ("+", "-"):
            op = self._eat()
            right = self._mult()
            left = left + right if op == "+" else left - right
        return left

    def _mult(self) -> float:
        left = self._power()
        while self._peek() in ("*", "/", "%"):
            op = self._eat()
            right = self._power()
            if op == "*":
                left *= right
            elif op == "/":
                if right == 0:
                    raise ValueError("division by zero")
                left /= right
            else:
                left %= right
        return left

    def _power(self) -> float:
        left = self._unary()
        if self._peek() == "^":
            self._eat()
            right = self._unary()
            left = left ** right
        return left

    def _unary(self) -> float:
        if self._peek() == "-":
            self._eat()
            return -self._primary()
        if self._peek() == "+":
            self._eat()
        return self._primary()

    def _primary(self) -> float:
        t = self._peek()
        if t == "(":
            self._eat()
            v = self._expr()
            if self._peek() != ")":
                raise ValueError("missing closing paren")
            self._eat()
            return v
        if t is not None and re.fullmatch(r"\d+\.?\d*", t):
            self._eat()
            return float(t)
        raise ValueError(f"unexpected: {t!r}")


def _safe_math(expr: str) -> str:
    try:
        result = _MathParser(expr.strip()).parse()
        if result == int(result) and abs(result) < 1e15:
            return str(int(result))
        return f"{result:.10g}"
    except Exception as exc:
        return f"[math error: {exc}]"


# ── Deep-block pre-pass ───────────────────────────────────────────────────────

def _extract_deep_blocks(text: str) -> tuple[str, list[dict]]:
    """Extract {engine:...} blocks whose content may contain nested braces."""
    engine_blocks: list[dict] = []

    for engine_name in _DEEP_ENGINES:
        prefix = "{" + engine_name + ":"
        prefix_lo = prefix.lower()
        result_chars: list[str] = []
        i = 0
        text_lo = text.lower()

        while i < len(text):
            if text_lo[i:i + len(prefix_lo)] == prefix_lo:
                start_content = i + len(prefix)
                depth = 1
                j = start_content
                while j < len(text) and depth > 0:
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                    j += 1
                if depth == 0:
                    content = text[start_content : j - 1].strip()
                    engine_blocks.append({"engine": engine_name, "content": content})
                    i = j
                    text_lo = text.lower()
                    continue
            result_chars.append(text[i])
            i += 1

        text = "".join(result_chars)

    return text, engine_blocks


# ── Script prefix block extractor ─────────────────────────────────────────────

def _extract_script_blocks(text: str) -> tuple[str, list[dict]]:
    """
    Extract prefix-based multiline script blocks.

    Recognises patterns like:
        tagscript:
        Hello {user}

        iscript:
        caption=hello

    Returns (remaining_plain_text, list_of_engine_block_dicts).
    The remaining_plain_text contains lines that weren't part of any engine block.
    """
    lines = text.splitlines(keepends=True)

    # Quick bail-out — avoid work if no prefix line present
    if not any(_SCRIPT_PREFIX_LINE.match(ln) for ln in lines):
        return text, []

    blocks: list[dict] = []
    plain_lines: list[str] = []
    current_engine: str | None = None
    current_content: list[str] = []

    def _flush():
        nonlocal current_engine, current_content
        if current_engine is not None:
            canonical = SCRIPT_ALIASES[current_engine.lower()]
            blocks.append({
                "engine": canonical,
                "content": "".join(current_content).strip(),
                "_script_prefix": True,
            })
        elif current_content:
            plain_lines.extend(current_content)
        current_engine = None
        current_content = []

    for line in lines:
        m = _SCRIPT_PREFIX_LINE.match(line)
        if m:
            _flush()
            current_engine = m.group(1)
        else:
            current_content.append(line)

    _flush()

    return "".join(plain_lines), blocks


# ── Variable resolution ───────────────────────────────────────────────────────

def _resolve_var(key: str, ctx: dict) -> str:
    key = key.lower()
    if key.startswith("args."):
        try:
            idx = int(key.split(".", 1)[1]) - 1
            words = ctx.get("args", "").split()
            return words[idx] if 0 <= idx < len(words) else ""
        except (ValueError, IndexError):
            return ""
    val = ctx.get(key)
    return str(val) if val is not None else ""


def resolve_variables(text: str, ctx: dict) -> str:
    def replacer(m: re.Match) -> str:
        result = _resolve_var(m.group(1), ctx)
        if result:
            return result
        # Unknown {var} → shorthand for {tag:var} (e.g. {invert} runs tag "invert")
        return "{tag:" + m.group(1).lower() + "}"
    return _VAR_RE.sub(replacer, text)


# ── Block processing ──────────────────────────────────────────────────────────

def _eval_if(content: str) -> str:
    parts = content.split("|")
    if len(parts) < 4:
        return ""
    a, op, b = parts[0], parts[1], parts[2]
    then_rest = "|".join(parts[3:])
    if not then_rest.startswith("then:"):
        return ""
    after_then = then_rest[5:]
    # Split on |else: to find optional else branch
    then_val = after_then
    else_val = ""
    if "|else:" in after_then:
        idx = after_then.index("|else:")
        then_val = after_then[:idx]
        else_val = after_then[idx + 6:]
    try:
        a_num, b_num = float(a), float(b)
        numeric = True
    except ValueError:
        numeric = False
    matched = False
    if op in ("=", "=="):
        matched = a == b
    elif op == "!=":
        matched = a != b
    elif op == ">" and numeric:
        matched = a_num > b_num
    elif op == "<" and numeric:
        matched = a_num < b_num
    elif op == ">=" and numeric:
        matched = a_num >= b_num
    elif op == "<=" and numeric:
        matched = a_num <= b_num
    return then_val if matched else else_val


def _handle_block(name: str, content: str, engine_blocks: list, ctx: dict = None) -> str:
    if ctx is None:
        ctx = {}
    name_lo = name.lower()
    canonical = SCRIPT_ALIASES.get(name_lo)

    # ── Engine dispatch ──
    if canonical in KNOWN_ENGINES:
        engine_blocks.append({"engine": canonical, "content": content.strip()})
        return ""

    # ── {arg:n} / {arg:*} — 0-indexed argument access ──
    if name_lo == "arg":
        words = ctx.get("args", "").split()
        c = content.strip()
        if c == "*":
            return ctx.get("args", "")
        try:
            return words[int(c)] if 0 <= int(c) < len(words) else ""
        except (ValueError, IndexError):
            return ""

    # ── {get:var} — retrieve named variable ──
    if name_lo == "get":
        return str(ctx.get(content.strip(), ""))

    # ── Conditionals ──
    if name_lo == "if":
        return _eval_if(content)

    # ── Math (resolves inner blocks first, e.g. {math:{get:#}+1}) ──
    if name_lo == "math":
        inner, _ = resolve_blocks(content, ctx)
        return _safe_math(inner)

    # ── Random / range ──
    if name_lo in ("random", "choose"):
        if ":" in content and "|" not in content:
            halves = content.split(":", 1)
            try:
                lo, hi = int(halves[0].strip()), int(halves[1].strip())
                return str(random.randint(min(lo, hi), max(lo, hi)))
            except ValueError:
                pass
        choices = [c.strip() for c in content.split("|") if c.strip()]
        return random.choice(choices) if choices else ""

    if name_lo == "range":
        parts = content.split("|", 1)
        if len(parts) == 2:
            try:
                lo_s, hi_s = parts[0].strip(), parts[1].strip()
                is_float = "." in lo_s or "." in hi_s
                lo, hi = float(lo_s), float(hi_s)
                if lo > hi:
                    lo, hi = hi, lo
                if is_float:
                    val = random.uniform(lo, hi)
                    return f"{val:.4f}".rstrip("0").rstrip(".")
                return str(random.randint(int(lo), int(hi)))
            except ValueError:
                pass
        return ""

    # ── Text functions ──
    if name_lo == "upper":
        return content.upper()
    if name_lo == "lower":
        return content.lower()
    if name_lo == "title":
        return content.title()
    if name_lo == "reverse":
        return content[::-1]
    if name_lo == "len":
        return str(len(content.strip()))

    if name_lo == "repeat":
        # Support both {repeat:N|text} and {repeat:N:text}
        if "|" in content:
            parts = content.split("|", 1)
        elif ":" in content:
            parts = content.split(":", 1)
        else:
            return ""
        try:
            n = max(0, min(int(parts[0].strip()), 50))
            val = parts[1] if len(parts) > 1 else ""
            return val * n
        except ValueError:
            return ""

    if name_lo == "slice":
        parts = content.split("|", 2)
        if len(parts) == 3:
            try:
                s, e = int(parts[0]), int(parts[1])
                return parts[2][s:e]
            except (ValueError, IndexError):
                pass
        return ""

    # ── {substring:text|start[|end]} ──
    if name_lo == "substring":
        parts = content.split("|", 2)
        if len(parts) >= 2:
            try:
                text_val = parts[0]
                start = int(parts[1])
                if len(parts) == 3:
                    return text_val[start:int(parts[2])]
                return text_val[start:]
            except (ValueError, IndexError):
                pass
        return ""

    # ── {indexof:needle|haystack} ──
    if name_lo == "indexof":
        parts = content.split("|", 1)
        if len(parts) == 2:
            return str(parts[1].find(parts[0]))
        return "-1"

    # Unknown — leave intact
    return "{" + name + ":" + content + "}"


def resolve_blocks(text: str, ctx: dict) -> tuple[str, list[dict]]:
    engine_blocks: list[dict] = []

    def replacer(m: re.Match) -> str:
        return _handle_block(m.group(1), m.group(2), engine_blocks, ctx)

    processed = _BLOCK_RE.sub(replacer, text)
    return processed.strip(), engine_blocks


# ── Execution ordering ────────────────────────────────────────────────────────

def sort_engine_blocks(blocks: list[dict]) -> list[dict]:
    """Sort engine blocks by canonical execution order."""
    return sorted(blocks, key=lambda b: _ENGINE_PRIORITY.get(b.get("engine", ""), 99))


# ── Tag content analysis (for t!tag info) ─────────────────────────────────────

def detect_engines(content: str) -> list[str]:
    """
    Return a sorted list of canonical engine names present in tag content.
    Checks both {engine:} brace syntax and prefix-based script blocks.
    """
    found: set[str] = set()

    # Brace syntax: {engine:...}
    for m in re.finditer(r"\{([a-z_][a-z0-9_]*):", content, re.IGNORECASE):
        canonical = SCRIPT_ALIASES.get(m.group(1).lower())
        if canonical:
            found.add(canonical)

    # Script prefix syntax: "engine:\n"
    for m in _SCRIPT_PREFIX_LINE.finditer(content):
        canonical = SCRIPT_ALIASES.get(m.group(1).lower())
        if canonical:
            found.add(canonical)

    return [e for e in _ENGINE_ORDER if e in found]


# ── Top-level ─────────────────────────────────────────────────────────────────

def parse(content: str, ctx: dict) -> tuple[str, list[dict]]:
    """Full TagScript parse: script prefixes → variables → deep engines → blocks."""
    # 1. Extract prefix-based script blocks (multiline engine: syntax)
    text, script_blocks = _extract_script_blocks(content)
    # 2. Variable substitution
    text = resolve_variables(text, ctx)
    # 3. Extract engines with potentially nested braces (e.g. embedjson)
    text, deep_blocks = _extract_deep_blocks(text)
    # 4. Extract remaining function/engine blocks via regex
    text, shallow_blocks = resolve_blocks(text, ctx)
    # 5. Combine + sort all engine blocks by execution order
    all_blocks = sort_engine_blocks(script_blocks + deep_blocks + shallow_blocks)
    return text, all_blocks


_VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".gif"})
_VIDEO_MIME_PREFIXES = ("video/", "image/gif")


def _first_attachment_url(msg) -> str:
    """Return the URL of the first attachment on a message, or ''."""
    if msg and msg.attachments:
        return msg.attachments[0].url
    return ""


def _first_video_url(msg) -> str:
    """Return the URL of the first video/gif attachment on a message, or ''."""
    if not msg or not msg.attachments:
        return ""
    for att in msg.attachments:
        # Check MIME type first (most reliable)
        ct = att.content_type or ""
        if ct.startswith(_VIDEO_MIME_PREFIXES):
            return att.url
        # Fall back to extension check
        import os
        ext = os.path.splitext(att.filename)[1].lower()
        if ext in _VIDEO_EXTS:
            return att.url
    # Nothing video-like — return first attachment anyway so the tag can try
    return msg.attachments[0].url


def _resolved_ref(discord_ctx) -> object | None:
    """Return the resolved referenced (replied-to) message, if any."""
    ref = getattr(discord_ctx.message, "reference", None)
    if ref is None:
        return None
    resolved = getattr(ref, "resolved", None)
    if isinstance(resolved, Exception) or resolved is None:
        return None
    return resolved


def build_context(discord_ctx, args: str) -> dict:
    """Build the variable context dict from a discord.py Context object."""
    user = discord_ctx.author
    guild = discord_ctx.guild
    channel = discord_ctx.channel
    args = args.strip()
    nick = None
    if hasattr(user, "nick"):
        nick = user.nick
    nickname = nick or user.display_name

    # Resolve media attachment variables: prefer current message, fall back to reply
    cur_msg = discord_ctx.message
    ref_msg = _resolved_ref(discord_ctx)

    # {ia} — first attachment URL (any type)
    ia = _first_attachment_url(cur_msg) or _first_attachment_url(ref_msg)
    # {iv} — first video/gif attachment URL, then any attachment
    iv = _first_video_url(cur_msg) or _first_video_url(ref_msg)
    if not iv:
        iv = ia  # last resort: use whatever attachment is there

    return {
        "user":      user.display_name,
        "username":  user.name,
        "userid":    str(user.id),
        "id":        str(user.id),
        "mention":   user.mention,
        "avatar":    str(user.display_avatar.url),
        "nickname":  nickname,
        "usertag":   str(user),
        "server":    guild.name if guild else "DM",
        "serverid":  str(guild.id) if guild else "0",
        "channel":   getattr(channel, "name", "DM"),
        "channelid": str(channel.id),
        "args":      args,
        "argslen":   str(len(args.split()) if args else 0),
        "iv":        iv,
        "ia":        ia,
    }
