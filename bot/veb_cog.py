"""
VEB Cog — videoeditbot-style effects command for IHTX Bot.

Commands
--------
th/veb <effects>     — apply comma-separated veb-shorthand or native IHTX pipe effects
th/veb               — apply random effects (same as not specifying anything)

Mention trigger
---------------
Ping the bot (@bot) in a message that has a media attachment (or that replies to
one) without using the th/ prefix → bot picks 1–3 random effects and destroys it.
"""

from __future__ import annotations

import random

import discord
from discord.ext import commands

# ── shorthand → IHTX pipe-effect name ────────────────────────────────────────
# Each value must be a valid PIPE_EFFECT_NAMES entry (or an ffmpeg(...) literal).
VEB_SHORTHANDS: dict[str, str] = {
    # audio destruction
    "er":    "adestroy",           # earrape
    "boom":  "adestroy",
    "sfx":   "adestroy",
    "bs":    "vibrato",            # bass boost approximation
    "wub":   "vibrato",            # wub bass
    "rv":    "vibrato",            # reverb approximation
    "rvd":   "vibrato",
    "pch":   "multipitch",         # pitch shift
    "atb":   "multipitch",         # autotune approximation
    "vol":   "volume",
    "mus":   "volume",
    "muss":  "volume",
    "musd":  "volume",
    "hf":    "audioequalizer",     # highpass filter
    # visual flip / mirror
    "hflp":  "hflip",
    "vflp":  "vflip",
    "hm":    "mirror",             # horizontal mirror
    "vm":    "avflip",             # vertical audio/video flip
    # color / luma
    "inv":   "invert",
    "nc":    "negate",             # negate color
    "hue":   "ccshue",
    "huec":  "ccshue",             # hue cycle
    "acid":  "huehsv",
    "hs":    "huehsv",
    "fe":    "huehsv",             # filter effect → hue saturation
    "defe":  "invert",             # de-filter
    "df":    "acontrast",          # deepfry
    "ct":    "contrast",
    # motion / spatial
    "zm":    "zoom",
    "wav":   "wave",
    "wava":  "wave",
    "wavs":  "wave",
    "hwav":  "wave",
    "hwava": "wave",
    "hwavs": "wave",
    "ws":    "wave",               # wavesynth
    "shk":   "earthquake",         # shake
    "hypc":  "earthquake",         # hype cycle
    "bndc":  "swirl",              # bend cycle
    "lag":   "jitter",
    "rlag":  "randomjitter",
    "rep":   "tile",               # repeat / tile
    "repu":  "tile",
    "hcp":   "tile",
    "vcp":   "tile",
    "rc":    "rotate",
    # time
    "rev":   "vreverse",
    "vrev":  "vreverse",
    "arev":  "areverse",
    "prev":  "vreverse",
    "sp":    "speed",
    "s":     "trim",
    "e":     "trim",
    "se":    "trim",
    "delf":  "trim",
    "dell":  "trim",
    # text / overlay
    "tt":    "caption",            # text top
    "bt":    "caption",            # bottom text
    "tc":    "caption",
    "bc":    "caption",
    "cap":   "caption",
    "bcap":  "caption",
    "wtm":   "watermark",
    "mt":    "watermark",
    # glitch / TV
    "glch":  "chromashift",
    "ytp":   "chromashift",        # youtube poop style
    "dm":    "tvsim",              # displacement map
    "st":    "tvsim",              # static / TV sim
    # misc
    "shp":   "ffmpeg(-vf unsharp=5:5:1.5:5:5:0.0)",
    "fps":   "ffmpeg(-vf fps=24)",
    "cr":    "ffmpeg(-vf crop=iw*0.8:ih*0.8)",
}

# Effects that look visually interesting and are safe to trigger at random
_RANDOM_POOL: list[str] = [
    "hflip", "vflip", "invert", "negate", "grayscale", "sepia",
    "chromashift", "earthquake", "wave", "swirl", "zoom",
    "tvsim", "jitter", "randomjitter", "ripple", "scroll",
    "acontrast", "adestroy", "huehsv", "ccshue", "mirror",
    "vibrato", "vreverse", "areverse", "wave2", "multipitch2",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _translate_veb_effects(effects_str: str) -> str:
    """Translate comma-separated veb effects to an IHTX comma-separated pipe string.

    Each token may carry an =value suffix that is preserved verbatim.
    """
    parts = [p.strip() for p in effects_str.split(",") if p.strip()]
    translated: list[str] = []
    for part in parts:
        if "=" in part:
            name, params = part.split("=", 1)
            name = name.strip().lower()
            ihtx = VEB_SHORTHANDS.get(name, name)
            translated.append(f"{ihtx}={params}")
        else:
            ihtx = VEB_SHORTHANDS.get(part.lower(), part)
            translated.append(ihtx)
    return ",".join(translated)


def _random_effect_str(n: int | None = None) -> str:
    """Return a comma-joined string of n random effects (default 1–3)."""
    count = n if n is not None else random.randint(1, 3)
    chosen = random.sample(_RANDOM_POOL, min(count, len(_RANDOM_POOL)))
    return ",".join(chosen)


async def _resolve_media_url(message: discord.Message) -> str | None:
    """Return a direct media URL from the message or the message it replies to."""
    if message.attachments:
        return message.attachments[0].url
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.attachments:
                return ref_msg.attachments[0].url
        except Exception:
            pass
    return None


# ── cog ───────────────────────────────────────────────────────────────────────

class VebCog(commands.Cog, name="VEB"):
    """videoeditbot-style effects and random mention processing."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _get_ihtxgen(self) -> commands.Command | None:
        """Retrieve the ihtxgen handler from the Economy cog."""
        economy = self.bot.cogs.get("Economy")
        if economy is None:
            return None
        return getattr(economy, "ihtxgen", None)

    # ── th/veb ───────────────────────────────────────────────────────────────

    @commands.command(name="veb", aliases=["videoeditbot"])
    async def veb(self, ctx: commands.Context, *, effects: str = "") -> None:
        """Apply veb-style effects to attached/replied media.

        Usage:
          th/veb hflip,invert,wave       native IHTX names
          th/veb glch,acid,shk           veb shorthands (glitch, hue-acid, shake)
          th/veb er,pch=1.5              earrape + pitch shift
          th/veb                         random 1–3 effects

        Attach a file or reply to a message that has one.
        """
        ihtxgen = self._get_ihtxgen()
        if ihtxgen is None:
            await ctx.reply("❌ Economy cog not loaded — cannot run effects.", mention_author=False)
            return

        if effects.strip():
            pipe_effects = _translate_veb_effects(effects.strip())
            label = effects.strip()
        else:
            pipe_effects = _random_effect_str()
            label = "(random)"

        await ctx.invoke(
            ihtxgen,
            effect="chaos",
            pipe_effects=pipe_effects,
            repetitions=1,
            duration="vidlen",
            no_trim=False,
            export_fmt="mp4",
        )

    # ── mention → random effects ──────────────────────────────────────────────

    @commands.Cog.listener("on_message")
    async def on_mention_veb(self, message: discord.Message) -> None:
        """Ping the bot with a media attachment (no th/ prefix) → random effects."""
        if message.author.bot:
            return
        if self.bot.user is None or self.bot.user not in message.mentions:
            return

        # Don't intercept actual bot commands — derive prefix from the bot itself
        # so this stays correct if config.json changes the prefix.
        prefix = self.bot.command_prefix
        content = message.content.lstrip()
        if isinstance(prefix, str):
            if content.startswith(prefix):
                return
        elif isinstance(prefix, (list, tuple)):
            if any(content.startswith(p) for p in prefix):
                return

        # Enforce blocklist — same check used by th/ihtx
        from bot.ihtx_bot import blocklist, _check_heavy_limit
        if message.author.id in blocklist:
            return

        # Enforce heavy-command rate limit (charges the user's daily quota)
        ok, reason = _check_heavy_limit(message.author.id)
        if not ok:
            await message.reply(f"⏳ {reason}", mention_author=False)
            return

        # Only fire when there's media to process
        media_url = await _resolve_media_url(message)
        if not media_url:
            return

        ihtxgen = self._get_ihtxgen()
        if ihtxgen is None:
            return

        pipe_effects = _random_effect_str()
        await message.add_reaction("🎬")

        ctx = await self.bot.get_context(message)
        await ctx.invoke(
            ihtxgen,
            effect="chaos",
            pipe_effects=pipe_effects,
            repetitions=1,
            duration="vidlen",
            no_trim=False,
            export_fmt="mp4",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VebCog(bot))
