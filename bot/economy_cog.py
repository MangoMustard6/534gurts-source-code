"""
EconomyCog — Server Economy, RPG Inventory & Fun Commands for IHTX Bot.

Commands (all hybrid — work as text prefix roxi  AND slash /):
  /profile [user]   — Rich profile card with Edit Bio modal + Inventory view
  /ihtxgen          — Slash-native roxi ihtx pipeline with live embed feedback
  /slot             — Slot machine (777 → +200 XP), 1-hour cooldown

Data persistence: JSON file at bot/economy_data.json (zero external deps).
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Weather fun facts — shown in the processing embed while FFmpeg runs
# ---------------------------------------------------------------------------

WEATHER_FUN_FACTS: list[str] = [
    "A bolt of lightning is about 5× hotter than the surface of the Sun.",
    "The world's heaviest hailstone weighed 1.02 kg and fell in Bangladesh in 1986.",
    "Fog is simply a cloud that forms at ground level.",
    "The fastest wind ever recorded was 408 km/h during Typhoon Olivia in 1996.",
    "Snow isn't actually white — ice crystals are translucent but scatter light to look white.",
    "Raindrops aren't teardrop-shaped — they look more like tiny hamburger buns.",
    "The US gets about 1,200 tornadoes per year, more than anywhere else on Earth.",
    "A single thunderstorm can pack as much energy as 10 atomic bombs.",
    "Lightning strikes Earth about 100 times every second.",
    "The wettest spot on Earth is Mawsynram, India, with ~11,871 mm of rain per year.",
    "A blizzard needs winds ≥ 56 km/h and visibility under 400 m to officially qualify.",
    "The coldest temp ever recorded was −89.2 °C at Vostok Station, Antarctica, in 1983.",
    "The hottest air temp ever recorded in shade was 56.7 °C in Death Valley in 1913.",
    "A rainbow is actually a full circle — the ground hides the bottom half.",
    "Very cold air holds almost no moisture, so heavy snowfall rarely happens below −29 °C.",
    "A cubic mile of fog contains less than a gallon of liquid water.",
    "Thundersnow is real — a snowstorm with lightning and thunder embedded inside it.",
    "Neptune has the fastest winds in the solar system: over 2,000 km/h.",
    "Hurricane winds can extend 400–500 km outward from the storm centre.",
    "The eye of a hurricane is completely calm and can be sunny and clear.",
    "Heat lightning doesn't exist — it's just regular lightning too far away to hear.",
    "Ball lightning is a poorly understood phenomenon where glowing plasma orbs float through air.",
    "The smell of rain is called petrichor, from soil oils and actinomycetes bacteria.",
    "Cloud-to-ground lightning always has an upward return stroke from the ground.",
    "Antarctica is the driest, windiest, and coldest continent on Earth.",
    "A hurricane can dump 2.4 trillion gallons of rain in a single day.",
    "Wind makes no sound on its own — it's only audible when moving past objects.",
    "Cirrus cloud ice crystals can be needles, plates, or hollow hexagonal columns.",
    "El Niño can shift global weather patterns for months or even years.",
    "The Coriolis effect is why Northern Hemisphere hurricanes spin counter-clockwise.",
    "Virga is precipitation that falls from clouds but evaporates before hitting the ground.",
    "Mammatus clouds are rare, pouch-shaped formations hanging beneath thunderstorm anvils.",
    "The Aurora Borealis happens when solar wind interacts with Earth's magnetic field.",
    "Snow can fall above 0 °C if the air is dry enough for the flakes to survive descent.",
    "The deadliest weather disaster in history was China's 1931 flood — up to 4 million deaths.",
    "A waterspout is simply a tornado that forms over water.",
    "Dust devils are rotating columns of dust-filled air caused by hot ground heating air unevenly.",
    "The Great Blizzard of 1888 buried New York City under 50 cm of snow in 36 hours.",
    "Category 5 hurricanes sustain winds over 252 km/h.",
    "Frost forms only when the surface drops below the dew point AND below 0 °C.",
    "Clouds can weigh millions of tonnes yet stay airborne because their droplets are microscopic.",
    "Supercell thunderstorms are rotating and can last for hours, sometimes spawning multiple tornadoes.",
    "The Beaufort Scale has 13 levels, from 0 (dead calm) to 12 (hurricane force).",
    "Monsoon rains dump about 80% of India's annual rainfall in just 4 months.",
    "Global lightning networks track over 40 million cloud-to-ground strikes per year.",
    "Haboobs are massive wall-like dust storms common in the Sahara, Middle East, and US Southwest.",
    "The highest recorded tornado reached approximately 12 km into the atmosphere.",
    "Rainbows can be seen as full circles from an airplane.",
    "Lake-effect snow forms when cold air passes over warm lake water, picking up moisture rapidly.",
    "Some Antarctic regions have gone over 2 million years without rain — the driest places on Earth.",
]

# ---------------------------------------------------------------------------
# Economy database — lightweight JSON store
# ---------------------------------------------------------------------------

_DB_PATH = Path("bot/economy_data.json")

_DEFAULT_USER: dict[str, Any] = {
    "wallet": 100,
    "bank": 0,
    "xp": 0,
    "bio": "No bio set.",
    "inventory": [],
}

_MOCK_SEED: dict[str, Any] = {}


class EconomyDB:
    """Thread-safe (asyncio-level) JSON database for user economy profiles."""

    def __init__(self, path: Path = _DB_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            if self._path.exists():
                with self._path.open("r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            else:
                self._data = dict(_MOCK_SEED)
        except Exception:
            self._data = dict(_MOCK_SEED)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        tmp.replace(self._path)

    def _profile(self, user_id: int) -> dict[str, Any]:
        key = str(user_id)
        if key not in self._data:
            self._data[key] = dict(_DEFAULT_USER)
        return self._data[key]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, user_id: int) -> dict[str, Any]:
        return dict(self._profile(user_id))

    def set_bio(self, user_id: int, bio: str) -> None:
        self._profile(user_id)["bio"] = bio[:300]
        self._save()

    def add_xp(self, user_id: int, amount: int) -> int:
        p = self._profile(user_id)
        p["xp"] = max(0, p.get("xp", 0) + amount)
        self._save()
        return p["xp"]

    def add_wallet(self, user_id: int, amount: int) -> int:
        p = self._profile(user_id)
        p["wallet"] = max(0, p.get("wallet", 0) + amount)
        self._save()
        return p["wallet"]

    def add_inventory_item(self, user_id: int, item: str) -> None:
        p = self._profile(user_id)
        inv: list[str] = p.setdefault("inventory", [])
        inv.append(item)
        self._save()

    def level_from_xp(self, xp: int) -> int:
        """Simple formula: level = floor(sqrt(xp / 50))."""
        return max(1, int(math.sqrt(max(0, xp) / 50)))


# Module-level singleton
db = EconomyDB()


# ---------------------------------------------------------------------------
# UI — Bio Edit Modal
# ---------------------------------------------------------------------------

class BioModal(discord.ui.Modal, title="Edit Your Profile Bio"):
    bio_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Bio",
        style=discord.TextStyle.paragraph,
        placeholder="Write something about yourself…",
        min_length=1,
        max_length=300,
        required=True,
    )

    def __init__(self, target_id: int) -> None:
        super().__init__()
        self._target_id = target_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        new_bio = self.bio_input.value.strip()
        db.set_bio(self._target_id, new_bio)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"✅ Bio updated!\n> {new_bio}",
                color=0x57F287,
            ),
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# UI — Profile View (Edit Bio button + View Inventory button)
# ---------------------------------------------------------------------------

class ProfileView(discord.ui.View):
    def __init__(
        self,
        target: discord.User | discord.Member,
        author: discord.User | discord.Member,
        original_embed: discord.Embed,
    ) -> None:
        super().__init__(timeout=120)
        self._target = target
        self._author = author
        self._original_embed = original_embed
        self._showing_inventory = False

        # Only the profile owner can edit the bio
        if author.id != target.id:
            self.edit_bio_btn.disabled = True
            self.edit_bio_btn.label = "Edit Bio (owner only)"

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="✏️ Edit Bio", style=discord.ButtonStyle.secondary)
    async def edit_bio_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self._author.id:
            await interaction.response.send_message(
                "❌ Only the profile owner can edit their bio.", ephemeral=True
            )
            return
        await interaction.response.send_modal(BioModal(self._target.id))

    @discord.ui.button(label="🎒 View Inventory", style=discord.ButtonStyle.primary)
    async def view_inventory_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        self._showing_inventory = not self._showing_inventory

        if self._showing_inventory:
            button.label = "📊 View Stats"
            button.style = discord.ButtonStyle.success

            profile = db.get(self._target.id)
            inv: list[str] = profile.get("inventory", [])

            embed = discord.Embed(
                title=f"🎒 {self._target.display_name}'s Inventory",
                color=0xE67E22,
            )
            embed.set_thumbnail(url=self._target.display_avatar.url)
            if inv:
                chunks: list[str] = []
                for i, item in enumerate(inv[-25:], 1):
                    chunks.append(f"`{i}.` {item}")
                embed.description = "\n".join(chunks)
                embed.set_footer(text=f"{len(inv)} item(s) total")
            else:
                embed.description = "_Inventory is empty._"
        else:
            button.label = "🎒 View Inventory"
            button.style = discord.ButtonStyle.primary
            embed = self._original_embed

        await interaction.edit_original_response(embed=embed, view=self)


# ---------------------------------------------------------------------------
# UI — Slot result view (re-spin button, disabled after win)
# ---------------------------------------------------------------------------

_SLOT_SYMBOLS: list[str] = ["🍒", "🍊", "🍋", "🍇", "⭐", "🔔", "7️⃣"]
_SLOT_JACKPOT = "7️⃣"


def _spin_slots() -> tuple[str, str, str]:
    return (
        random.choice(_SLOT_SYMBOLS),
        random.choice(_SLOT_SYMBOLS),
        random.choice(_SLOT_SYMBOLS),
    )


def _slots_embed(
    s1: str,
    s2: str,
    s3: str,
    *,
    user: discord.User | discord.Member,
    xp_total: int | None = None,
    win: bool = False,
    jackpot: bool = False,
) -> discord.Embed:
    color = 0xF1C40F if jackpot else (0x57F287 if win else 0xED4245)
    title = "🎰 JACKPOT — 777! 🎰" if jackpot else ("🎰 Winner!" if win else "🎰 Slot Machine")
    embed = discord.Embed(title=title, color=color)
    embed.description = (
        f"╔══════════════╗\n"
        f"║  {s1}  {s2}  {s3}  ║\n"
        f"╚══════════════╝"
    )
    if jackpot and xp_total is not None:
        embed.add_field(name="🏆 Jackporoxi ", value=f"+200 XP awarded!\nTotal XP: **{xp_total}**", inline=False)
    elif win:
        embed.add_field(name="🎉 Match!", value="Two matching symbols — keep spinning!", inline=False)
    else:
        embed.add_field(name="😔 No match", value="Better luck next time!", inline=False)
    embed.set_footer(text=f"{user.display_name} · 1-hour cooldown")
    return embed


# ---------------------------------------------------------------------------
# Main Cog
# ---------------------------------------------------------------------------

class EconomyCog(commands.Cog, name="Economy"):
    """Server economy, RPG inventory, and fun commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ready_at = time.time()

    # -----------------------------------------------------------------------
    # /profile
    # -----------------------------------------------------------------------

    @commands.hybrid_command(
        name="profile",
        description="View a user's economy profile card.",
    )
    @app_commands.describe(user="The user whose profile to view (defaults to you).")
    async def profile(
        self,
        ctx: commands.Context,
        user: Optional[discord.Member] = None,
    ) -> None:
        target: discord.User | discord.Member = user or ctx.author
        profile_data = db.get(target.id)

        wallet: int = profile_data.get("wallet", 0)
        bank: int = profile_data.get("bank", 0)
        xp: int = profile_data.get("xp", 0)
        bio: str = profile_data.get("bio", "No bio set.")
        inv: list[str] = profile_data.get("inventory", [])
        level: int = db.level_from_xp(xp)

        embed = discord.Embed(
            title=f"👤 {target.display_name}'s Profile",
            description=f"*{bio}*",
            color=0x5865F2,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💵 Wallet", value=f"`${wallet:,}`", inline=True)
        embed.add_field(name="🏦 Bank", value=f"`${bank:,}`", inline=True)
        embed.add_field(name="⭐ Level", value=f"`{level}` *(XP: {xp:,})*", inline=True)
        embed.add_field(name="🎒 Inventory", value=f"`{len(inv)} item(s)`", inline=True)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )

        view = ProfileView(target=target, author=ctx.author, original_embed=embed)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # -----------------------------------------------------------------------
    # /ihtxgen — slash-native IHTX pipeline with live embed feedback
    # -----------------------------------------------------------------------

    async def _preset_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            from bot.ihtx_bot import PRESET_FILTERS
            presets = list(PRESET_FILTERS.keys())
        except Exception:
            presets = ["chaos", "glitch", "shake", "rainbow", "static", "melt", "corrupt"]
        choices = [
            app_commands.Choice(name=p.title(), value=p)
            for p in presets
            if current.lower() in p.lower()
        ]
        return choices[:25]

    async def _pipe_effect_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        COMBOS = [
            "huehsv 0.5", "negate", "hflip", "vflip", "grayscale", "sepia",
            "swirl=90", "speed=2", "volume=2", "multipitch=1|6|7",
            "huehsv 0.5,negate", "negate,hflip", "grayscale,speed=0.5",
            "multipitch=1|6|7,negate", "huehsv 0.5,multipitch=1|6|7",
            "invert,speed=0.5", "sepia,swirl=45", "channelblend,negate",
        ]
        try:
            from bot.ihtx_bot import PIPE_EFFECT_NAMES
            extra = [n for n in sorted(PIPE_EFFECT_NAMES) if n not in COMBOS]
        except Exception:
            extra = []
        all_opts = COMBOS + extra
        matches = [o for o in all_opts if current.lower() in o.lower()] if current else all_opts
        return [app_commands.Choice(name=o[:100], value=o[:100]) for o in matches[:25]]

    @commands.hybrid_command(
        name="ihtxgen",
        description="Run an IHTX FFmpeg effect on media with live embed feedback.",
    )
    @app_commands.describe(
        effect="Preset (chaos, glitch, melt, …), or type your own pipe effects directly (e.g. negate,huehsv=0.5). Autocomplete available.",
        url="Direct URL to a media file (alternative to attaching).",
        attachment="Attach a video or image (slash only).",
        pipe_effects="Type any pipe effects freely (e.g. huehsv 0.5,negate,multipitch=1|6|7). No preset required.",
        repetitions="Export repetitions for pipe mode (default 1, max 100).",
        duration="Seconds or awk expr for pipe mode, e.g. 5 or vidlen/2 (default: full video).",
        no_trim="Skip trim in pipe mode.",
        export_fmt="Output container for pipe mode: mp4 (default), mkv, mov, avi.",
        output_fmt="Required final output container after the intermediate format, e.g. mp4 then mov.",
    )
    @app_commands.autocomplete(effect=_preset_autocomplete)
    async def ihtxgen(
        self,
        ctx: commands.Context,
        effect: str = "chaos",
        url: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
        pipe_effects: Optional[str] = None,
        repetitions: int = 1,
        duration: str = "vidlen",
        no_trim: bool = False,
        export_fmt: str = "mov",
        output_fmt: str = "",
    ) -> None:
        use_pipe = bool(pipe_effects and pipe_effects.strip())
        if use_pipe and not output_fmt.strip():
            await ctx.reply(
                "❌ `output_fmt` is required in pipe mode and must be one of: "
                "`mp4`, `mov`, `mkv`, `mxf`, or `avi`.",
                ephemeral=True,
            )
            return

        try:
            from bot.ihtx_bot import (
                PRESET_FILTERS,
                SUPPORTED_EXTENSIONS,
                VIDEO_EXTENSIONS,
                MAX_FILE_SIZE,
                CATBOX_THRESHOLD,
                get_output_ext,
                run_ffmpeg,
                _upload_to_catbox,
                _ffprobe_video_info,
                _ffprobe_duration,
                _run_ihtx_tagscript_workflow,
                _pipe_effects_label,
                _parse_ihtx_custom_args,
                _last_exports,
            )
        except ImportError as exc:
            await ctx.reply(f"❌ Internal error importing IHTX pipeline: `{exc}`", ephemeral=True)
            return

        if not use_pipe:
            effect_lower = effect.lower().strip()
            if effect_lower in PRESET_FILTERS:
                effect = effect_lower
            else:
                # Try full roxi ihtx custom-syntax string in the effect field
                # e.g. "10 0.483 - mp4 huehsv 0.5;negate;multipitch=1|6|7"
                _custom_parsed = _parse_ihtx_custom_args(effect.strip())
                if _custom_parsed is not None:
                    _c_reps, _c_dur, _c_notrim, _c_fmt, _c_output_fmt, _c_pe = _custom_parsed
                    repetitions = _c_reps
                    duration = _c_dur
                    no_trim = _c_notrim.lower() in {"true", "yes", "+"}
                    export_fmt = _c_fmt or "mov"
                    output_fmt = _c_output_fmt
                    pipe_effects = _c_pe
                    use_pipe = True
                elif effect.strip() and not effect.strip().split()[0][:1].isdigit():
                    # Shorthand pipe-effects mode: the effect field isn't a known
                    # preset, doesn't start with a digit (which would indicate the
                    # full "<reps> <dur> <noTrim> <fmt> <effects>" syntax), so treat
                    # the whole string as pipe effects with defaults (1 rep, full
                    # video duration, mp4). Mirrors the roxi ihtx prefix shorthand.
                    #   /ihtxgen effect:negate,huehsv=0.5
                    #   /ihtxgen effect:ffmpeg(-vf huesaturation=saturation=1:strength=100)
                    pipe_effects = effect.strip()
                    repetitions = 1
                    duration = "vidlen"
                    no_trim = False
                    export_fmt = "mov"
                    use_pipe = True
                else:
                    preset_list = ", ".join(f"`{p}`" for p in sorted(PRESET_FILTERS.keys()))
                    await ctx.reply(
                        embed=discord.Embed(
                            title="❌ Unknown Preset or Invalid Syntax",
                            description=(
                                f"**Presets:** {preset_list}\n\n"
                                "**Pipe-effects shorthand** *(1 rep, full duration, mp4)*:\n"
                                "`roxi ihtx <pipe effects>` or `/ihtxgen effect:<pipe effects>`\n"
                                "Example: `roxi ihtx ffmpeg(-vf huesaturation=saturation=1:strength=100)`\n"
                                "Example: `roxi ihtx negate,huehsv=0.5`\n\n"
                                "**Full custom syntax:**\n"
                                 "`<exports> <duration> <no_trim> <format> <output_format> <pipe effects>`\n"
                                 "Example: `10 0.483 - mp4 huehsv 0.5;negate;multipitch=1|6|7`\n"
                                 "Example with final conversion: `10 0.4 - mp4 mov huehsv=0.5`\n\n"
                                "Or use the dedicated `pipe_effects:` parameter alongside `effect:`."
                            ),
                            color=0xED4245,
                        ),
                        ephemeral=True,
                    )
                    return

        # Resolve media: slash attachment > url param > message attachment > reply attachment
        media_url: Optional[str] = None
        media_filename: str = "input"
        media_size: int = 0

        if attachment is not None:
            media_url = attachment.proxy_url or attachment.url
            media_filename = attachment.filename
            media_size = attachment.size
        elif url:
            media_url = url
            media_filename = url.split("?")[0].split("/")[-1] or "input.mp4"
            media_size = 0
        elif ctx.message and ctx.message.attachments:
            a = ctx.message.attachments[0]
            media_url = a.proxy_url or a.url
            media_filename = a.filename
            media_size = a.size
        elif ctx.message and ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    a = ref.attachments[0]
                    media_url = a.url
                    media_filename = a.filename
                    media_size = a.size
            except Exception:
                pass

        if not media_url:
            await ctx.reply(
                embed=discord.Embed(
                    title="📎 No Media Provided",
                    description=(
                        "Attach a file, provide a `url:` parameter, or reply to a message with media.\n\n"
                        + (
                            f"**Pipe effects:** `{pipe_effects}`\n"
                            if use_pipe else
                            f"**Effect:** `{effect}`\n"
                        )
                        + "**Usage:** `/ihtxgen` with an attachment or `url:`"
                    ),
                    color=0xFEE75C,
                ),
                ephemeral=True,
            )
            return

        if media_size > MAX_FILE_SIZE:
            await ctx.reply(
                embed=discord.Embed(
                    description=f"❌ File too large (max 25 MB, got {media_size / 1024 / 1024:.1f} MB).",
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return

        suffix = Path(media_filename).suffix.lower() or ".mp4"
        if suffix not in SUPPORTED_EXTENSIONS:
            await ctx.reply(
                embed=discord.Embed(
                    description=f"❌ Unsupported file type `{suffix}`.",
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return

        is_video = suffix in VIDEO_EXTENSIONS

        if use_pipe and not is_video:
            await ctx.reply(
                embed=discord.Embed(
                    description="❌ Pipe effects mode requires video input (not images or GIFs).",
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return

        out_ext = get_output_ext(suffix, is_video)
        if not use_pipe:
            preset_out_ext = PRESET_FILTERS.get(effect, {}).get("output_ext")
            if preset_out_ext:
                out_ext = preset_out_ext

        # Build header for the live embed
        if use_pipe:
            _pe_label = _pipe_effects_label(pipe_effects)
            _dur_str = duration if duration != "vidlen" else "full video"
            _header = (
                f"**Duration:** `{_dur_str}` · **Format:** `{export_fmt}`"
                + (f" → **Output:** `{output_fmt}`" if output_fmt else "")
                + (f" · **No trim:** yes" if no_trim else "")
                + (f" · **Reps:** ×{repetitions}" if repetitions != 1 else "")
                + f"\n**File:** `{media_filename}`"
            )
        else:
            _header = f"**Effect:** `{effect}`\n**File:** `{media_filename}`"

        _fun_fact = random.choice(WEATHER_FUN_FACTS)
        _start_time = time.monotonic()
        _user_tag = str(ctx.author)
        _avatar_url = ctx.author.display_avatar.url
        _IHTX_COLOR = 0x001080
        _IHTX_FOOTER_ICON = "https://file.garden/akpXUy7cShbwSW4u/shake.68003989.gif"

        def _make_base_embed(color: int = _IHTX_COLOR) -> discord.Embed:
            e = discord.Embed(color=color, timestamp=discord.utils.utcnow())
            e.set_author(name=_user_tag, icon_url=_avatar_url)
            e.set_footer(text="th/ihtx is ready!", icon_url=_IHTX_FOOTER_ICON)
            return e

        loading_embed = _make_base_embed()
        loading_embed.add_field(name="Status:", value="⏳ Downloading and processing your media…", inline=False)
        loading_embed.add_field(name="🌤️ Weather Fact:", value=_fun_fact, inline=False)
        status_msg = await ctx.reply(embed=loading_embed, mention_author=False)

        async def _update(status: str, color: int = _IHTX_COLOR) -> None:
            e = _make_base_embed(color)
            e.add_field(name="Status:", value=status, inline=False)
            if color == _IHTX_COLOR:
                e.add_field(name="🌤️ Weather Fact:", value=_fun_fact, inline=False)
            try:
                await status_msg.edit(embed=e)
            except Exception:
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, f"input{suffix}")
            out_final_ext = f".{(output_fmt or export_fmt).lstrip('.')}" if use_pipe else out_ext
            output_path = os.path.join(tmpdir, f"output{out_final_ext}")

            # Download
            try:
                await _update("⬇️ Downloading media…")
                async with __import__("aiohttp").ClientSession() as session:
                    async with session.get(media_url) as resp:
                        if resp.status != 200:
                            await _update(f"❌ Failed to download media (HTTP {resp.status}).", 0xED4245)
                            return
                        data = await resp.read()
                with open(input_path, "wb") as fh:
                    fh.write(data)
            except Exception as exc:
                await _update(f"❌ Download failed: `{exc}`", 0xED4245)
                return

            # Process — with a background ticker showing elapsed seconds
            loop = asyncio.get_event_loop()
            _done_evt = asyncio.Event()
            _halfway_evt = asyncio.Event()

            def _on_progress(completed: int, total: int) -> None:
                if total > 0 and completed / total >= 0.5:
                    loop.call_soon_threadsafe(_halfway_evt.set)

            async def _halfway_notice() -> None:
                await _halfway_evt.wait()
                await ctx.send(
                    f"{ctx.author.mention} ⏳ **th/ihtx** is halfway done generating your IHTX."
                )

            async def _tick() -> None:
                while not _done_evt.is_set():
                    elapsed = int(time.monotonic() - _start_time)
                    if use_pipe:
                        _phase = f"🔧 Running pipe effects…\n⏱️ **{elapsed}s elapsed**"
                    else:
                        _phase = f"🔧 Running FFmpeg `{effect}` preset…\n⏱️ **{elapsed}s elapsed**"
                    await _update(_phase)
                    try:
                        await asyncio.wait_for(_done_evt.wait(), timeout=4.0)
                    except asyncio.TimeoutError:
                        pass

            _tick_task = asyncio.create_task(_tick())
            _halfway_notice_task = asyncio.create_task(_halfway_notice())
            try:
                if use_pipe:
                    ok, err = await loop.run_in_executor(
                        None, _run_ihtx_tagscript_workflow,
                        input_path, output_path,
                        repetitions, duration,
                        "true" if no_trim else "-",
                        export_fmt.lstrip(".") or "mov",
                output_fmt.lstrip("."),
                        pipe_effects,
                        _on_progress,
                    )
                else:
                    ok, err = await loop.run_in_executor(
                        None, run_ffmpeg, input_path, output_path, effect, is_video
                    )
            finally:
                _done_evt.set()
                _tick_task.cancel()
                try:
                    await _tick_task
                except asyncio.CancelledError:
                    pass
                # Give a very fast job one event-loop turn to deliver the
                # halfway callback before deciding there is no notice to send.
                await asyncio.sleep(0)
                if _halfway_evt.is_set():
                    try:
                        await _halfway_notice_task
                    except asyncio.CancelledError:
                        pass
                else:
                    _halfway_notice_task.cancel()
                    try:
                        await _halfway_notice_task
                    except asyncio.CancelledError:
                        pass

            if not ok:
                await _update(f"❌ FFmpeg failed:\n```\n{err[-1200:]}\n```", 0xED4245)
                return

            # Sidecar mp4 render path (written by _run_ihtx_tagscript_workflow when
            # export fmt is mkv or mxf — produced alongside the requested format).
            _render_mp4 = output_path + ".render.mp4"
            _has_render = os.path.exists(_render_mp4)

            # Persist the last export for th/lexg re-use.
            os.makedirs("output", exist_ok=True)
            last_export_ext = out_final_ext
            last_export_path = os.path.abspath(f"output/lastexport_{ctx.author.id}{last_export_ext}")
            try:
                shutil.copy2(output_path, last_export_path)
                _last_exports[ctx.author.id] = {
                    "path": last_export_path,
                    "filename": media_filename,
                    "is_video": is_video,
                    "suffix": suffix,
                    "ext": last_export_ext,
                    "duration": _ffprobe_duration(output_path),
                    "timestamp": time.time(),
                }
                with open(f"output/lastexport_{ctx.author.id}.json", "w") as f:
                    json.dump(_last_exports[ctx.author.id], f)
            except Exception as exc:
                print(f"[lexg] failed to persist last export: {exc}")

            out_size = os.path.getsize(output_path)

            # Probe metadata
            try:
                vinfo = _ffprobe_video_info(output_path)
                w, h = int(vinfo["width"]), int(vinfo["height"])
                fr_raw = vinfo.get("r_frame_rate", "")
                try:
                    fn, fd = fr_raw.split("/")
                    fps_str = f"{float(fn) / float(fd):.2f} fps"
                except Exception:
                    fps_str = "N/A"
                gcd = math.gcd(w, h) if w and h else 1
                res_str = f"{w}×{h}" if w and h else "N/A"
                ar_str = f"{w // gcd}:{h // gcd}" if gcd else "N/A"
            except Exception:
                res_str = ar_str = fps_str = "N/A"

            size_mb = out_size / (1024 * 1024)

            if out_size > CATBOX_THRESHOLD:
                await _update("⬆️ Output exceeds 8 MB — uploading to Catbox…")
                catbox_url = await _upload_to_catbox(output_path)
                if catbox_url:
                    _elapsed = time.monotonic() - _start_time
                    _size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{out_size / 1024:.2f} KB"
                    result_embed = _make_base_embed()
                    result_embed.add_field(name="Resolution:", value=f"{res_str} ({ar_str}) · {fps_str}", inline=True)
                    if use_pipe:
                        _dur_label = duration if duration != "vidlen" else "full video"
                        result_embed.add_field(
                            name="​",
                            value=f"✅ IHTX Command — `powers={repetitions}` `notrim={str(no_trim).lower()}` `duration={_dur_label}`",
                            inline=False,
                        )
                    result_embed.add_field(
                        name="Reminder:",
                        value="Make sure you use `.t sync+` or `.t sync+ alt` afterwards to make sure the video is synced to the audio",
                        inline=False,
                    )
                    result_embed.add_field(
                        name="File Info:",
                        value=f"{_size_str} (Catbox), took {_elapsed:.2f} seconds\n🔗 [Download]({catbox_url})\n`{catbox_url}`",
                        inline=False,
                    )
                    await status_msg.edit(embed=result_embed)
                else:
                    await _update("❌ Output too large for Discord and Catbox upload failed.", 0xED4245)
                if _has_render:
                    _render_stem = Path(media_filename).stem
                    _render_fn = f"ihtx_pipe_{_render_stem}_render.mp4"
                    _render_size = os.path.getsize(_render_mp4)
                    if _render_size <= CATBOX_THRESHOLD:
                        await ctx.send(content="🎬 MP4 render:", file=discord.File(_render_mp4, filename=_render_fn))
                    else:
                        _cb2 = await _upload_to_catbox(_render_mp4)
                        if _cb2:
                            await ctx.send(f"🎬 MP4 render: {_cb2}")
                return

            stem = Path(media_filename).stem
            out_filename = f"534gurts_ihtx_{'pipe' if use_pipe else effect}{out_final_ext}"
            _elapsed = time.monotonic() - _start_time
            _size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{out_size / 1024:.2f} KB"
            result_embed = _make_base_embed()
            result_embed.add_field(name="Resolution:", value=f"{res_str} ({ar_str}) · {fps_str}", inline=True)
            if use_pipe:
                _dur_label = duration if duration != "vidlen" else "full video"
                result_embed.add_field(
                    name="​",
                    value=f"✅ IHTX Command — `powers={repetitions}` `notrim={str(no_trim).lower()}` `duration={_dur_label}`",
                    inline=False,
                )
            result_embed.add_field(
                name="Reminder:",
                value="Make sure you use `.t sync+` or `.t sync+ alt` afterwards to make sure the video is synced to the audio",
                inline=False,
            )
            result_embed.add_field(
                name="File Info:",
                value=f"{_size_str}, took {_elapsed:.2f} seconds",
                inline=False,
            )
            # Only embed images inline — Discord can't play video inside set_image().
            # For video outputs, attach without set_image so Discord renders a native player.
            _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
            if out_final_ext.lower() in _IMAGE_EXTS:
                result_embed.set_image(url=f"attachment://{out_filename}")
            try:
                await status_msg.edit(
                    embed=result_embed,
                    attachments=[discord.File(output_path, filename=out_filename)],
                )
            except discord.HTTPException:
                await status_msg.edit(embed=result_embed)
                await ctx.send(file=discord.File(output_path, filename=out_filename))
            if _has_render:
                _render_stem = Path(media_filename).stem
                _render_fn = f"ihtx_pipe_{_render_stem}_render.mp4"
                _render_size = os.path.getsize(_render_mp4)
                if _render_size <= CATBOX_THRESHOLD:
                    await ctx.send(content="🎬 MP4 render:", file=discord.File(_render_mp4, filename=_render_fn))
                else:
                    _cb2 = await _upload_to_catbox(_render_mp4)
                    if _cb2:
                        await ctx.send(f"🎬 MP4 render: {_cb2}")

    # -----------------------------------------------------------------------
    # roxi ihtx / roxi effect / roxi destroy — prefix-only alias that consumes the
    # full rest of the message as one string, avoiding discord.py's per-token
    # argument parsing (which breaks the "1 5 - mp4 negate" custom syntax).
    # -----------------------------------------------------------------------

    @commands.command(name="ihtx", aliases=["effect", "destroy"])
    async def ihtx_prefix(self, ctx: commands.Context, *, args: str = "") -> None:
        """Prefix alias for /ihtxgen — handles both preset names and the full
        custom syntax: <exports> <duration> <no_trim> <fmt> <pipe_effects>"""
        try:
            from bot.ihtx_bot import _parse_ihtx_custom_args, PRESET_FILTERS
        except ImportError as exc:
            await ctx.reply(f"❌ Internal import error: `{exc}`")
            return

        args = args.strip()
        parsed = _parse_ihtx_custom_args(args) if args else None

        if parsed is not None:
            reps, dur, notrim, fmt, output_fmt, pe = parsed
            await ctx.invoke(
                self.ihtxgen,
                effect="chaos",
                pipe_effects=pe,
                repetitions=reps,
                duration=dur,
                no_trim=notrim.lower() in {"true", "yes"},
                export_fmt=fmt or "mov",
                output_fmt=output_fmt,
            )
        else:
            first = (args.split()[0] if args else "").lower()
            # Shorthand pipe-effects mode: if the arg doesn't start with a digit
            # (which would indicate the full "<reps> <dur> <noTrim> <fmt> <effects>"
            # syntax) and isn't a known preset name, treat the entire string as
            # pipe effects with defaults (1 rep, full video duration, mp4).
            # This lets users write:
            #   roxi ihtx ffmpeg(-vf huesaturation=saturation=1:strength=100)
            #   roxi ihtx negate,huehsv=0.5
            #   roxi ihtx ffmpeg(-vf negate),speed=0.5
            if args and not first[:1].isdigit() and first not in PRESET_FILTERS:
                await ctx.invoke(
                    self.ihtxgen,
                    effect="chaos",
                    pipe_effects=args,
                    repetitions=1,
                    duration="vidlen",
                    no_trim=False,
                    export_fmt="mov",
                )
            else:
                await ctx.invoke(self.ihtxgen, effect=first or "chaos")

    # -----------------------------------------------------------------------
    # roxi math — evaluate a math expression (no eval/exec, recursive-descent)
    # -----------------------------------------------------------------------

    @commands.command(name="math", aliases=["calc"])
    async def math_cmd(self, ctx: commands.Context, *, expression: str) -> None:
        """Evaluate a math expression safely.

        Usage: th/math <expression>
        Example: th/math 2+2*3
                 th/math (10^2)/4 + 5
        """
        from bot.tags.parser import _safe_math
        result = _safe_math(expression.strip())
        if result.startswith("[math error"):
            await ctx.reply(f"❌ {result}", mention_author=False)
        else:
            await ctx.reply(f"🧮 `{expression.strip()}` = `{result}`", mention_author=False)

    # -----------------------------------------------------------------------
    # roxi nparisonffmpeg — standalone iterative xstack grid command
    # -----------------------------------------------------------------------

    @commands.command(name="nparisonffmpeg", aliases=["nparison"])
    async def nparisonffmpeg_cmd(self, ctx: commands.Context, *, args: str = "") -> None:
        """Apply an FFmpeg filter N×M times and xstack all versions into a grid.

        Usage: th/nparisonffmpeg <grid> <ffmpeg args>
        Example: th/nparisonffmpeg 2x2 -vf negate
                 th/nparisonffmpeg 2x3 -vf hue=h=90
        Attach a video or reply to one.  Max grid: 4×4 (16 cells).
        """
        import shlex as _shlex
        from bot.ihtx_bot import (
            _run_nparisonffmpeg,
            _upload_to_catbox,
            _ffprobe_video_info,
            MAX_FILE_SIZE,
            CATBOX_THRESHOLD,
        )

        # Parse args: first token is grid (NxM), rest are ffmpeg args
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            await ctx.reply(
                embed=discord.Embed(
                    title="❌ Usage",
                    description=(
                        "**`roxi nparisonffmpeg <grid> <ffmpeg args>`**\n\n"
                        "Example: `roxi nparisonffmpeg 2x2 -vf negate`\n"
                        "Attach a video or reply to a message containing one."
                    ),
                    color=0xED4245,
                ),
                mention_author=False,
            )
            return

        grid_str = parts[0].lower()
        ffmpeg_args_str = parts[1].strip()

        try:
            gp = grid_str.split("x")
            gridx = int(gp[0])
            gridy = int(gp[1])
        except (IndexError, ValueError):
            await ctx.reply(
                embed=discord.Embed(
                    description=f"❌ Invalid grid `{grid_str}` — use `NxM` format, e.g. `2x2`.",
                    color=0xED4245,
                ),
                mention_author=False,
            )
            return

        if gridx < 1 or gridy < 1 or gridx * gridy < 2:
            await ctx.reply(
                embed=discord.Embed(
                    description="❌ Grid must have at least 2 cells (e.g. `1x2`, `2x2`).",
                    color=0xED4245,
                ),
                mention_author=False,
            )
            return

        if gridx * gridy > 16:
            await ctx.reply(
                embed=discord.Embed(
                    description=f"❌ Grid too large ({gridx * gridy} cells) — max 16 (e.g. `4x4`).",
                    color=0xED4245,
                ),
                mention_author=False,
            )
            return

        try:
            user_args = _shlex.split(ffmpeg_args_str)
        except ValueError as exc:
            await ctx.reply(
                embed=discord.Embed(
                    description=f"❌ Invalid FFmpeg args: `{exc}`",
                    color=0xED4245,
                ),
                mention_author=False,
            )
            return

        # Resolve media
        media_url: str | None = None
        media_filename = "input.mp4"
        if ctx.message.attachments:
            a = ctx.message.attachments[0]
            media_url = a.url
            media_filename = a.filename
        elif ctx.message.reference:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments:
                    a = ref.attachments[0]
                    media_url = a.url
                    media_filename = a.filename
            except Exception:
                pass

        if not media_url:
            await ctx.reply(
                embed=discord.Embed(
                    description="❌ Attach a video or reply to a message containing one.",
                    color=0xED4245,
                ),
                mention_author=False,
            )
            return

        _IHTX_COLOR = 0x001080
        _IHTX_FOOTER_ICON = "https://files.catbox.moe/4snvbu.gif"
        _user_tag = str(ctx.author)
        _avatar_url = ctx.author.display_avatar.url
        _start_time = time.monotonic()

        def _make_embed(color: int = _IHTX_COLOR) -> discord.Embed:
            e = discord.Embed(color=color, timestamp=discord.utils.utcnow())
            e.set_author(name=_user_tag, icon_url=_avatar_url)
            e.set_footer(text="nparisonffmpeg", icon_url=_IHTX_FOOTER_ICON)
            return e

        loading = _make_embed()
        loading.add_field(name="Status:", value="⏳ Downloading media…", inline=False)
        loading.add_field(name="Grid:", value=f"`{grid_str}` ({gridx * gridy} cells)", inline=True)
        loading.add_field(name="Args:", value=f"`{ffmpeg_args_str[:200]}`", inline=True)
        status_msg = await ctx.reply(embed=loading, mention_author=False)

        async def _update(text: str, color: int = _IHTX_COLOR) -> None:
            e = _make_embed(color)
            e.add_field(name="Status:", value=text, inline=False)
            try:
                await status_msg.edit(embed=e)
            except Exception:
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            suffix = Path(media_filename).suffix.lower() or ".mp4"
            input_path = os.path.join(tmpdir, f"input{suffix}")
            output_path = os.path.join(tmpdir, "nparison_out.mov")

            # Download
            try:
                async with __import__("aiohttp").ClientSession() as session:
                    async with session.get(media_url) as resp:
                        if resp.status != 200:
                            await _update(f"❌ Download failed (HTTP {resp.status}).", 0xED4245)
                            return
                        data = await resp.read()
                with open(input_path, "wb") as fh:
                    fh.write(data)
            except Exception as exc:
                await _update(f"❌ Download error: `{exc}`", 0xED4245)
                return

            # Process
            loop = asyncio.get_event_loop()
            _done = asyncio.Event()

            async def _tick() -> None:
                while not _done.is_set():
                    elapsed = int(time.monotonic() - _start_time)
                    await _update(
                        f"🔧 Building `{grid_str}` grid…\n⏱️ **{elapsed}s elapsed**"
                    )
                    try:
                        await asyncio.wait_for(_done.wait(), timeout=4.0)
                    except asyncio.TimeoutError:
                        pass

            tick_task = asyncio.create_task(_tick())
            try:
                ok, err = await loop.run_in_executor(
                    None, _run_nparisonffmpeg,
                    input_path, output_path, gridx, gridy, user_args,
                )
            except Exception as exc:
                import traceback
                ok, err = False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            finally:
                _done.set()
                tick_task.cancel()
                try:
                    await tick_task
                except asyncio.CancelledError:
                    pass

            if not ok:
                await _update(f"❌ nparisonffmpeg failed:\n```\n{err[-1200:]}\n```", 0xED4245)
                return

            out_size = os.path.getsize(output_path)
            elapsed = time.monotonic() - _start_time
            size_str = (
                f"{out_size / 1048576:.2f} MB" if out_size >= 1048576
                else f"{out_size / 1024:.2f} KB"
            )

            try:
                vinfo = _ffprobe_video_info(output_path)
                w, h = int(vinfo["width"]), int(vinfo["height"])
                res_str = f"{w}×{h}"
            except Exception:
                res_str = "N/A"

            result_embed = _make_embed()
            result_embed.add_field(name="Grid:", value=f"`{grid_str}`", inline=True)
            result_embed.add_field(name="Args:", value=f"`{ffmpeg_args_str[:200]}`", inline=True)
            result_embed.add_field(name="Resolution:", value=res_str, inline=True)
            result_embed.add_field(
                name="File Info:",
                value=f"{size_str}, took {elapsed:.2f}s",
                inline=False,
            )

            stem = Path(media_filename).stem
            out_filename = f"534gurts_nparison_{grid_str}.mov"

            if out_size > CATBOX_THRESHOLD:
                await _update("⬆️ Output exceeds 8 MB — uploading to Catbox…")
                catbox_url = await _upload_to_catbox(output_path)
                if catbox_url:
                    result_embed.add_field(
                        name="Download:",
                        value=f"🔗 [Catbox]({catbox_url})\n`{catbox_url}`",
                        inline=False,
                    )
                    await status_msg.edit(embed=result_embed)
                else:
                    await _update("❌ Output too large for Discord and Catbox upload failed.", 0xED4245)
                return

            try:
                await status_msg.edit(
                    embed=result_embed,
                    attachments=[discord.File(output_path, filename=out_filename)],
                )
            except discord.HTTPException:
                await status_msg.edit(embed=result_embed)
                await ctx.send(file=discord.File(output_path, filename=out_filename))

    # -----------------------------------------------------------------------
    # /ping and /status — latency and health
    # -----------------------------------------------------------------------

    @commands.hybrid_command(
        name="ping",
        description="Check the bot's WebSocket latency and message round-trip times.",
    )
    async def ping(self, ctx: commands.Context) -> None:
        import datetime
        ws_ms = round(self.bot.latency * 1000)
        bar = "🟢" if ws_ms < 150 else ("🟡" if ws_ms < 400 else "🔴")
        color = 0x57F287 if ws_ms < 150 else (0xFEE75C if ws_ms < 400 else 0xED4245)

        if ctx.interaction:
            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"{bar} **WebSocket:** {ws_ms} ms",
                color=color,
            )
            await ctx.reply(embed=embed, mention_author=False)
        else:
            now = datetime.datetime.now(datetime.timezone.utc)
            receive_ms = (now - ctx.message.created_at).total_seconds() * 1000
            send_start = time.perf_counter()
            msg = await ctx.reply("🏓 Pong!")
            send_ms = (time.perf_counter() - send_start) * 1000
            total_ms = receive_ms + send_ms
            embed = discord.Embed(
                title="🏓 Pong!",
                color=color,
            )
            embed.add_field(name=f"{bar} WebSocket", value=f"**{ws_ms} ms**", inline=True)
            embed.add_field(name="📨 Receive", value=f"**{receive_ms:.0f} ms**", inline=True)
            embed.add_field(name="📤 Send", value=f"**{send_ms:.0f} ms**", inline=True)
            embed.add_field(name="⏱️ Total", value=f"**{total_ms:.0f} ms**", inline=True)
            await msg.edit(content=None, embed=embed)

    @commands.hybrid_command(
        name="status",
        description="Show bot status, latency, uptime, and server stats.",
    )
    async def status(self, ctx: commands.Context) -> None:
        latency_ms = round(self.bot.latency * 1000)
        bar = "🟢" if latency_ms < 150 else ("🟡" if latency_ms < 400 else "🔴")

        uptime_s = int(time.time() - self._ready_at)
        days, rem = divmod(uptime_s, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        uptime_str = " ".join(parts)

        guild_count = len(self.bot.guilds)
        user_count = sum(g.member_count or 0 for g in self.bot.guilds)

        embed = discord.Embed(title="📊 Bot Status", color=0x5865F2)
        embed.add_field(name="🏓 Latency", value=f"{bar} **{latency_ms} ms**", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="‎", value="‎", inline=True)
        embed.add_field(name="🌐 Servers", value=f"`{guild_count}`", inline=True)
        embed.add_field(name="👥 Users", value=f"`{user_count:,}`", inline=True)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.reply(embed=embed, mention_author=False)

    # -----------------------------------------------------------------------
    # /slot — Slot machine with 1-hour cooldown and 777 jackpot
    # -----------------------------------------------------------------------

    @commands.hybrid_command(
        name="jackpot",
        description="Spin the slot machine! Hit 777 to win 200 XP. (1-hour cooldown)",
    )
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def jackpot(self, ctx: commands.Context) -> None:
        s1, s2, s3 = _spin_slots()

        is_jackpot = s1 == s2 == s3 == _SLOT_JACKPOT
        two_match = (s1 == s2 or s2 == s3 or s1 == s3) and not is_jackpot
        win = is_jackpot or two_match

        xp_total: Optional[int] = None
        if is_jackpot:
            xp_total = db.add_xp(ctx.author.id, 200)

        embed = _slots_embed(
            s1, s2, s3,
            user=ctx.author,
            xp_total=xp_total,
            win=win,
            jackpot=is_jackpot,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @jackpot.error
    async def jackpot_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            remaining = error.retry_after
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)

            time_parts: list[str] = []
            if minutes:
                time_parts.append(f"**{minutes}m**")
            if seconds or not minutes:
                time_parts.append(f"**{seconds}s**")
            time_str = " ".join(time_parts)

            embed = discord.Embed(
                title="⏳ Slot Machine on Cooldown",
                description=(
                    f"You already spun the slots recently!\n\n"
                    f"Come back in {time_str}."
                ),
                color=0xFEE75C,
            )
            embed.set_footer(text="Cooldown: 1 hour per spin")

            if ctx.interaction:
                await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.reply(embed=embed, mention_author=False, delete_after=20)
        else:
            raise error


# ---------------------------------------------------------------------------
# Cog setup
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))
