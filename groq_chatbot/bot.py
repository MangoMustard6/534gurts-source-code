"""
Groq-powered Discord chatbot.

Responds only when @mentioned. Fully multilingual (EN / DE / ID / TL).
Personalizes every reply using per-user profiles persisted to JSON.
"""

import asyncio
import json
import logging
import os
import re
from collections import deque
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands
from dotenv import load_dotenv
from groq import AsyncGroq, APIConnectionError, APITimeoutError, RateLimitError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("groq-bot")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
GROQ_API_KEY:  str = os.environ["GROQ_API_KEY"]

GROQ_MODEL          = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_HISTORY         = int(os.getenv("MAX_HISTORY", "14"))     # messages kept per channel
MAX_RESPONSE_TOKENS = int(os.getenv("MAX_RESPONSE_TOKENS", "1024"))
PROFILES_PATH       = Path(os.getenv("PROFILES_PATH", "user_profiles.json"))

# ---------------------------------------------------------------------------
# Personality — system prompt core
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """\
You are a sharp, charismatic conversationalist who happens to live inside Discord. \
You are witty, warm, and quick — never stiff, never robotic, never corporate. \
Think of yourself as the most interesting person in the room: you keep things real, \
land clever observations, and genuinely enjoy talking to people.
Name: 534gurts (or just 534.)
LANGUAGE RULES (non-negotiable):
- Detect the language of the user's message: English, Deutsch, Bahasa Indonesia, or Filipino/Tagalog.
- Reply ENTIRELY in that same language. Match the register and vibe — casual slang if they're casual, \
  sharper if they're sharp. Never mix languages unless the user does first.
- Use authentic idioms and cultural nuance for each language rather than word-for-word translations.

PERSONALITY RULES:
- Be direct and human. Opinions are fine. Hedging everything is not.
- Light/Heavy humor is always welcome; forced humor is not.
- Keep replies conversational and appropriately concise — no unsolicited walls of text.
- Never begin a reply with hollow openers like "Certainly!", "Of course!", "Absolutely!", \
  "Great question!", or "As an AI…". Just talk.
- You are fully aware of internet culture, memes, and Discord norms.
""".strip()


def _build_system_prompt(profile: dict[str, Any]) -> str:
    """Inject the caller's personalisation data into the system prompt."""
    parts = [BASE_SYSTEM_PROMPT]

    name        = profile.get("preferred_name", "").strip()
    interests   = profile.get("interests", [])
    count       = profile.get("interaction_count", 0)

    if name or interests or count:
        parts.append("\n\nUSER CONTEXT (use this subtly — never recite it back verbatim):")

    if name:
        parts.append(f"- Their name/nickname: {name}")
    if interests:
        parts.append(f"- Known interests: {', '.join(interests[:8])}")
    if count == 1:
        parts.append("- This is their very first message to you — make a good impression.")
    elif count > 1:
        parts.append(f"- You have spoken with them {count} time(s) before; feel free to be familiar.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# User profile persistence
# ---------------------------------------------------------------------------

_profiles: dict[str, dict[str, Any]] = {}


def _load_profiles() -> None:
    global _profiles
    if PROFILES_PATH.exists():
        try:
            _profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
            log.info("Loaded %d user profile(s) from %s", len(_profiles), PROFILES_PATH)
        except Exception as exc:
            log.warning("Could not load profiles (%s) — starting fresh.", exc)
            _profiles = {}
    else:
        _profiles = {}


def _save_profiles() -> None:
    try:
        PROFILES_PATH.write_text(
            json.dumps(_profiles, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        log.error("Failed to save profiles: %s", exc)


def _get_profile(user_id: int) -> dict[str, Any]:
    key = str(user_id)
    if key not in _profiles:
        _profiles[key] = {
            "preferred_name": "",
            "interests": [],
            "interaction_count": 0,
        }
    return _profiles[key]


def _increment_and_save(user_id: int) -> dict[str, Any]:
    profile = _get_profile(user_id)
    profile["interaction_count"] = profile.get("interaction_count", 0) + 1
    _save_profiles()
    return profile


def _maybe_extract_name(text: str, profile: dict[str, Any]) -> None:
    """
    Heuristic: if the user explicitly introduces themselves we capture it.
    Patterns: "I'm X", "my name is X", "call me X", "ich bin X", "nama saya X", "ako si X"
    """
    if profile.get("preferred_name"):
        return
    patterns = [
        r"\b(?:i'm|i am|my name is|call me)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
        r"\bich\s+(?:bin|heiße)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
        r"\bnama\s+(?:saya|aku)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
        r"\b(?:ako\s+si|pangalan\s+ko(?:\s+ay)?)\s+([A-Za-z][A-Za-z0-9_\-]{0,24})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            profile["preferred_name"] = m.group(1).capitalize()
            _save_profiles()
            return


# ---------------------------------------------------------------------------
# Short-term channel history  (deque of {"role": …, "content": …})
# ---------------------------------------------------------------------------

# channel_id -> deque[dict]
_history: dict[int, deque[dict[str, str]]] = {}


def _get_history(channel_id: int) -> deque[dict[str, str]]:
    if channel_id not in _history:
        _history[channel_id] = deque(maxlen=MAX_HISTORY)
    return _history[channel_id]


# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------

_groq = AsyncGroq(api_key=GROQ_API_KEY)


async def _ask_groq(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> str:
    """
    Send a request to Groq and return the assistant's reply text.
    Raises on unrecoverable errors so the caller can inform the user.
    """
    messages: list[dict[str, str]] = (
        [{"role": "system", "content": system_prompt}]
        + list(history)
        + [{"role": "user", "content": user_message}]
    )

    resp = await _groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=MAX_RESPONSE_TOKENS,
        temperature=0.85,
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Discord helpers
# ---------------------------------------------------------------------------

def _chunk(text: str, limit: int = 1990) -> list[str]:
    """Split text into Discord-safe chunks (≤ limit chars) on word boundaries."""
    chunks: list[str] = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = text.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def _strip_mention(text: str, bot_id: int) -> str:
    """Remove the leading @mention of the bot from the message text."""
    return re.sub(rf"<@!?{bot_id}>", "", text).strip()


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    _load_profiles()
    assert bot.user is not None
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    log.info("Groq model: %s | History window: %d", GROQ_MODEL, MAX_HISTORY)


@bot.event
async def on_message(message: discord.Message) -> None:
    # Ignore self and other bots.
    if message.author.bot:
        return

    # Only respond when the bot is directly @mentioned.
    assert bot.user is not None
    if bot.user not in message.mentions:
        return

    # Strip the @mention to get the clean user text.
    user_text = _strip_mention(message.content, bot.user.id)
    if not user_text:
        await message.reply("Yeah? 👀", mention_author=False)
        return

    channel_id = message.channel.id
    user_id    = message.author.id

    # Update profile — increment counter, try to extract name.
    profile = _increment_and_save(user_id)
    _maybe_extract_name(user_text, profile)

    # Build personalised system prompt.
    system_prompt = _build_system_prompt(profile)

    # Retrieve rolling history for this channel.
    history = _get_history(channel_id)

    # Show typing indicator while awaiting the API.
    async with message.channel.typing():
        try:
            reply_text = await _ask_groq(system_prompt, list(history), user_text)

        except RateLimitError:
            log.warning("Groq rate limit hit for user %s", user_id)
            await message.reply(
                "Hitting the speed limit on my end — try again in a moment. 🏎️💨",
                mention_author=False,
            )
            return

        except APITimeoutError:
            log.warning("Groq request timed out for user %s", user_id)
            await message.reply(
                "Request timed out. Groq's thinking too hard, apparently. Try again.",
                mention_author=False,
            )
            return

        except APIConnectionError as exc:
            log.error("Groq connection error: %s", exc)
            await message.reply(
                "Can't reach the API right now. Check back in a bit.",
                mention_author=False,
            )
            return

        except Exception as exc:
            log.exception("Unexpected error calling Groq: %s", exc)
            await message.reply(
                "Something went sideways on my end. Try again.",
                mention_author=False,
            )
            return

    # Persist the exchange to rolling history BEFORE sending (so a crash mid-send
    # doesn't leave an orphaned user turn in the history).
    history.append({"role": "user",      "content": user_text})
    history.append({"role": "assistant", "content": reply_text})

    # Send — split into chunks if the reply exceeds Discord's 2 000-char limit.
    chunks = _chunk(reply_text)
    first  = True
    for chunk in chunks:
        if first:
            await message.reply(chunk, mention_author=False)
            first = False
        else:
            await message.channel.send(chunk)

    # Let the command framework process any prefix commands as well.
    await bot.process_commands(message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN, log_handler=None)
