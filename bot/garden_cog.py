"""
GardenCog — Text-based Garden Game for IHTX Bot.

Hybrid commands (slash + th/ prefix):
  /garden   th/garden              — View your plots, pets, and active boosters
  /shop     th/shop                — Browse seeds, saplings, boosters, and pet eggs
  /buy      th/buy <item> [amt]    — Buy items
  /inventory th/inventory (inv)   — Show full inventory
  /plant    th/plant <crop> <plot> — Plant a seed or sapling
  /water    th/water <plot>        — Water a plot
  /use      th/use <booster> <plot>— Apply a booster to a plot (scarecrow: no plot arg)
  /pet      th/pet equip <name>    — Equip a pet (max 1)
  /harvest  th/harvest <plot>      — Harvest a ready crop/fruit
  /scare    th/scare               — Scare off pests
  /sell     th/sell <crop> [amt]   — Sell harvested crops/fruit
  /wait     th/wait <minutes>      — Fast-forward time

Data: bot/garden_data.json
"""

from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ── Crop catalogue ─────────────────────────────────────────────────────────────

CROPS: dict[str, dict[str, Any]] = {
    "corn":       {"seed_cost": 10,  "growth_mins": 1,  "sell_price": 15,   "emoji": "🌽", "item_type": "crop"},
    "pumpkin":    {"seed_cost": 25,  "growth_mins": 3,  "sell_price": 45,   "emoji": "🎃", "item_type": "crop"},
    "tomato":     {"seed_cost": 50,  "growth_mins": 5,  "sell_price": 95,   "emoji": "🍅", "item_type": "crop"},
    "blueberry":  {"seed_cost": 100, "growth_mins": 8,  "sell_price": 210,  "emoji": "🫐", "item_type": "crop"},
    "beans":      {"seed_cost": 200, "growth_mins": 12, "sell_price": 450,  "emoji": "🫘", "item_type": "crop"},
    "watermelon": {"seed_cost": 500, "growth_mins": 20, "sell_price": 1200, "emoji": "🍉", "item_type": "crop"},
}

# ── Fruit tree catalogue ───────────────────────────────────────────────────────

TREES: dict[str, dict[str, Any]] = {
    "orange": {"seed_cost": 800,  "growth_mins": 30, "sell_price": 2100, "emoji": "🍊", "item_type": "tree"},
    "apple":  {"seed_cost": 1500, "growth_mins": 45, "sell_price": 4200, "emoji": "🍎", "item_type": "tree"},
    "mango":  {"seed_cost": 3000, "growth_mins": 60, "sell_price": 9000, "emoji": "🥭", "item_type": "tree"},
}

# ── Booster items ──────────────────────────────────────────────────────────────

BOOSTERS: dict[str, dict[str, Any]] = {
    "speed_fertilizer": {"cost": 30, "emoji": "⚡", "description": "Reduces remaining grow time of a plot by 50%"},
    "auto_waterer":     {"cost": 50, "emoji": "🚿", "description": "Keeps one plot perfectly watered until harvested"},
    "scarecrow":        {"cost": 80, "emoji": "🪚", "description": "Protects the entire garden from pests for 3 /wait turns"},
}

# ── Pets ───────────────────────────────────────────────────────────────────────

PETS: dict[str, dict[str, Any]] = {
    "farm_dog":   {"cost": 300,  "emoji": "🐕", "description": "100% pest protection — auto-scares all pests"},
    "lucky_cat":  {"cost": 500,  "emoji": "🐈", "description": "+15% chance to double coin yields on every harvest"},
    "mole_buddy": {"cost": 750,  "emoji": "🐾", "description": "Reduces all crop/tree growth times by 20%"},
}

# ── Constants ──────────────────────────────────────────────────────────────────

NUM_PLOTS        = 3       # starting plots for new players
EVENT_CHANCE     = 0.15
WATER_PCT        = 0.50    # must water within this fraction of grow time or crop dies
WATER_WARN_PCT   = 0.35    # show 💧 warning after this fraction elapsed
LUCKY_CAT_CHANCE = 0.15    # Lucky Cat: chance to double harvest coins
MOLE_BUDDY_SPEED = 0.80    # Mole Buddy: growth time multiplier (×0.8 = 20% faster)

# ── Data model ─────────────────────────────────────────────────────────────────

_DB_PATH = Path("bot/garden_data.json")

_EMPTY_PLOT: dict[str, Any] = {
    "crop":           None,
    "item_type":      "crop",    # "crop" | "tree"
    "planted_at":     None,
    "watered":        False,
    "auto_watered":   False,     # True when Auto-Waterer is active on this plot
    "water_deadline": None,
    "grow_deadline":  None,
    "state":          "empty",   # empty | growing | ready | dead | infested
    "golden":         False,
    "ping_at":        None,
    "notify_halfway": False,
}

_DEFAULT_USER: dict[str, Any] = {
    "coins":            100,
    "seeds":            {"corn": 2},
    "saplings":         {},      # tree saplings
    "harvested":        {},      # harvested crops/fruits ready to sell
    "boosters":         {},      # booster items in inventory
    "pet_eggs":         {},      # unhatched pet eggs
    "equipped_pet":     None,    # active pet key or None
    "scarecrow_turns":  0,       # remaining /wait turns of scarecrow protection
    "plots":            None,    # filled in get()
    "pending_pest":     None,    # 0-based plot index with active infestation
    "notify_channel_id": None,
}


def _all_items() -> dict[str, dict]:
    """Merged lookup table for all plantable/sellable items."""
    return {**CROPS, **TREES}


class GardenDB:
    """Atomic JSON store for garden game state."""

    def __init__(self, path: Path = _DB_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                with self._path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp.replace(self._path)

    def get(self, uid: int) -> dict[str, Any]:
        key = str(uid)
        if key not in self._data:
            u = copy.deepcopy(_DEFAULT_USER)
            u["plots"] = [copy.deepcopy(_EMPTY_PLOT) for _ in range(NUM_PLOTS)]
            self._data[key] = u
            self._save()
        u = self._data[key]
        # Migrate: ensure plots list has at least NUM_PLOTS entries
        plots = u.setdefault("plots", [])
        while len(plots) < NUM_PLOTS:
            plots.append(copy.deepcopy(_EMPTY_PLOT))
        # Migrate: ensure all plot fields exist
        for p in plots:
            p.setdefault("ping_at", None)
            p.setdefault("notify_halfway", False)
            p.setdefault("item_type", "crop")
            p.setdefault("auto_watered", False)
        # Migrate: ensure all user fields exist
        u.setdefault("pending_pest", None)
        u.setdefault("seeds", {"corn": 2})
        u.setdefault("saplings", {})
        u.setdefault("harvested", {})
        u.setdefault("boosters", {})
        u.setdefault("pet_eggs", {})
        u.setdefault("equipped_pet", None)
        u.setdefault("scarecrow_turns", 0)
        u.setdefault("coins", 100)
        u.setdefault("notify_channel_id", None)
        return u

    def save(self, uid: int, data: dict[str, Any]) -> None:
        self._data[str(uid)] = data
        self._save()

    def iter_all(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._data.items())

    def flush(self) -> None:
        self._save()


_db = GardenDB()

# ── Pure helpers ───────────────────────────────────────────────────────────────

def _now() -> float:
    return time.time()


def _progress_bar(pct: float, width: int = 8) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    return f"[{'▰' * filled}{'▱' * (width - filled)}] {pct:.0f}%"


def _fmt_time(secs: float) -> str:
    secs = max(0, int(secs))
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    return f"{m}m {s}s" if s else f"{m}m"


def _item_info(name: str) -> dict:
    """Look up item in CROPS or TREES."""
    return CROPS.get(name) or TREES.get(name) or {}


def _resolve_plantable(name: str) -> tuple[str, str] | None:
    """Returns (key, 'crop'|'tree') or None."""
    n = name.lower().strip()
    for key in CROPS:
        if n == key or (key.startswith(n) and len(n) >= 2):
            return (key, "crop")
    for key in TREES:
        if n == key or (key.startswith(n) and len(n) >= 2):
            return (key, "tree")
    return None


def _resolve_sellable(name: str) -> str | None:
    """Returns item key from CROPS or TREES, or None."""
    result = _resolve_plantable(name)
    return result[0] if result else None


def _resolve_booster(name: str) -> str | None:
    n = name.lower().strip().replace(" ", "_").replace("-", "_")
    aliases: dict[str, str] = {
        "speed": "speed_fertilizer", "sf": "speed_fertilizer",
        "fertilizer": "speed_fertilizer", "fert": "speed_fertilizer",
        "auto": "auto_waterer", "aw": "auto_waterer",
        "waterer": "auto_waterer", "autowaterer": "auto_waterer",
        "scarecrow": "scarecrow", "sc": "scarecrow", "crow": "scarecrow",
    }
    if n in aliases:
        return aliases[n]
    for b in BOOSTERS:
        if n == b or b.startswith(n):
            return b
    return None


def _resolve_pet(name: str) -> str | None:
    n = name.lower().strip().replace(" ", "_").replace("-", "_")
    aliases: dict[str, str] = {
        "dog": "farm_dog", "farmdog": "farm_dog", "farm": "farm_dog",
        "cat": "lucky_cat", "luckycat": "lucky_cat", "lucky": "lucky_cat",
        "mole": "mole_buddy", "molebuddy": "mole_buddy", "buddy": "mole_buddy",
    }
    if n in aliases:
        return aliases[n]
    for p in PETS:
        if n == p or p.startswith(n):
            return p
    return None


def _effective_state(plot: dict) -> str:
    """Compute current plot state from timestamps without mutating."""
    stored = plot.get("state", "empty")
    if stored in ("empty", "dead", "infested"):
        return stored
    now = _now()
    # Auto-watered plots never die from lack of water
    if (not plot.get("watered") and not plot.get("auto_watered")
            and plot.get("water_deadline") and now > plot["water_deadline"]):
        return "dead"
    if plot.get("grow_deadline") and now >= plot["grow_deadline"]:
        return "ready"
    return "growing"


def _sync_state(plot: dict) -> None:
    plot["state"] = _effective_state(plot)


def _plot_line(idx: int, plot: dict) -> str:
    """Single-line summary for /garden list."""
    state = _effective_state(plot)
    n = idx + 1
    if state == "empty":
        return f"**Plot {n}:** 🌱 Empty"

    crop = plot.get("crop") or "???"
    info = _item_info(crop)
    em   = info.get("emoji", "🌿")
    label = crop.capitalize()
    is_tree = plot.get("item_type") == "tree"
    type_tag = " 🌳" if is_tree else ""

    if state == "dead":
        return f"**Plot {n}:** 💀 Dead (was {em} {label})"
    if state == "infested":
        return f"**Plot {n}:** 🐦 **Infested!** ({em} {label}) — `/scare` or `th/scare` NOW!"
    if state == "ready":
        golden_tag = " ✨ **Golden!**" if plot.get("golden") else ""
        return f"**Plot {n}:** {em} {label}{type_tag} ✅ Ready to Harvest!{golden_tag}"

    # growing
    now       = _now()
    grow_left = max(0.0, plot["grow_deadline"] - now)
    total_s   = info.get("growth_mins", 1) * 60
    elapsed   = total_s - grow_left
    pct       = min(100.0, elapsed / max(1, total_s) * 100)
    bar       = _progress_bar(pct)

    water_tag = ""
    if plot.get("auto_watered"):
        water_tag = " 🚿 Auto-Watered"
    elif not plot.get("watered"):
        wdl = plot.get("water_deadline") or 0
        since_plant = _now() - (plot.get("planted_at") or _now())
        if since_plant / max(1, total_s) >= WATER_WARN_PCT:
            water_left = max(0, wdl - _now())
            water_tag = f" 💧 **Needs Water!** ({_fmt_time(water_left)} left)"
        else:
            water_tag = " 💧 Unwatered"

    return f"**Plot {n}:** {em} {label}{type_tag} [{_fmt_time(grow_left)} left] {bar}{water_tag}"


def _shop_lines() -> list[str]:
    lines: list[str] = []

    lines.append("**🌾 Seeds (Standard Plots)**")
    lines.append("```")
    lines.append(f"{'Crop':<12} {'Cost':>6} {'Grow':>6} {'Yield':>7}  Emoji")
    lines.append("─" * 46)
    for key, d in CROPS.items():
        lines.append(
            f"{key.capitalize():<12} {d['seed_cost']:>5}c {d['growth_mins']:>5}m "
            f"{d['sell_price']:>6}c  {d['emoji']}"
        )
    lines.append("```")

    lines.append("**🌳 Fruit Tree Saplings (High-Yield)**")
    lines.append("```")
    lines.append(f"{'Tree':<12} {'Cost':>6} {'Grow':>6} {'Yield':>7}  Emoji")
    lines.append("─" * 46)
    for key, d in TREES.items():
        lines.append(
            f"{key.capitalize():<12} {d['seed_cost']:>5}c {d['growth_mins']:>5}m "
            f"{d['sell_price']:>6}c  {d['emoji']}"
        )
    lines.append("```")

    lines.append("**⚡ Booster Items (Single-Use)**")
    lines.append("```")
    for key, d in BOOSTERS.items():
        display = key.replace("_", " ").title()
        lines.append(f"{d['emoji']} {display:<22} {d['cost']:>4}c — {d['description']}")
    lines.append("```")

    lines.append("**🥚 Pet Eggs (Permanent Passive Buffs)**")
    lines.append("```")
    for key, d in PETS.items():
        display = key.replace("_", " ").title() + " Egg"
        lines.append(f"{d['emoji']} {display:<26} {d['cost']:>4}c — {d['description']}")
    lines.append("```")

    lines.append("Use `th/buy <item>` or `/buy <item>` to purchase. Max 1 pet equipped.")
    return lines


# ── Random events ──────────────────────────────────────────────────────────────

def _roll_event(user: dict, uid: int) -> tuple[str | None, str | None]:
    """Roll a random event. Returns (display_msg, ping_msg).
    ping_msg is set when a pest occurs with no protection and must be sent
    as literal text so Discord delivers the notification ping."""
    if random.random() > EVENT_CHANCE:
        return None, None

    events = ["good_weather", "pest", "golden"]
    event  = random.choice(events)

    if event == "good_weather":
        for plot in user["plots"]:
            if _effective_state(plot) == "growing":
                if plot.get("grow_deadline"):
                    plot["grow_deadline"]  = max(_now(), plot["grow_deadline"]  - 60)
                if plot.get("water_deadline"):
                    plot["water_deadline"] = max(_now(), plot["water_deadline"] - 60)
        return "☀️ **Good Weather!** All crops grew 1 minute faster!", None

    if event == "pest":
        growing = [i for i, p in enumerate(user["plots"]) if _effective_state(p) == "growing"]
        if not growing:
            return None, None
        idx  = random.choice(growing)
        plot = user["plots"][idx]
        crop = plot.get("crop") or "crop"
        info = _item_info(crop)
        em   = info.get("emoji", "🌿")
        is_tree = plot.get("item_type") == "tree"
        pest_name = "Fruit Flies" if is_tree else "Crows"

        # Farm Dog auto-scares
        if user.get("equipped_pet") == "farm_dog":
            return (
                f"🐕 **Farm Dog** chased away {pest_name} from Plot {idx + 1}! Your {em} is safe! 🐾",
                None,
            )

        # Scarecrow protection
        sc_turns = user.get("scarecrow_turns", 0)
        if sc_turns > 0:
            user["scarecrow_turns"] = sc_turns - 1
            remaining = user["scarecrow_turns"]
            return (
                f"🪚 **Scarecrow** kept {pest_name} away from Plot {idx + 1}! "
                f"({remaining} turn{'s' if remaining != 1 else ''} remaining)",
                None,
            )

        # No protection — set infested and send ping
        user["plots"][idx]["state"] = "infested"
        user["pending_pest"] = idx
        pest_msg = (
            f"🐦 **Pest Infestation!** {pest_name} have attacked Plot {idx + 1}! "
            f"Use `/scare` or `th/scare` NOW or your {em} {crop.capitalize()} will be destroyed!"
        )
        ping_msg = (
            f"🚨 **PING!** <@{uid}> **PEST ALERT!** 🚨 "
            f"{pest_name} have infested Plot {idx + 1}! "
            f"You must run `/scare` or `th/scare` on your very next turn, "
            f"or your crop will be eaten and completely destroyed!"
        )
        return pest_msg, ping_msg

    if event == "golden":
        candidates = [
            i for i, p in enumerate(user["plots"])
            if _effective_state(p) in ("growing", "ready")
        ]
        if not candidates:
            return None, None
        idx = random.choice(candidates)
        user["plots"][idx]["golden"] = True
        return f"✨ **Golden Harvest!** Plot {idx + 1} will yield double coins on harvest!", None

    return None, None


def _consume_pest(user: dict, scared: bool) -> str | None:
    pest_idx = user.get("pending_pest")
    if pest_idx is None:
        return None
    plot = user["plots"][pest_idx]
    user["pending_pest"] = None
    if scared:
        if plot.get("state") == "infested":
            plot["state"] = "growing"
        return f"👏 You scared the pests away from Plot {pest_idx + 1}! Crop saved!"
    else:
        crop_name = (plot.get("crop") or "crop").capitalize()
        plot["state"] = "dead"
        return f"💀 The pests destroyed your **{crop_name}** in Plot {pest_idx + 1}!"


# ── Context-aware reply helper ─────────────────────────────────────────────────

async def _send(
    ctx: commands.Context,
    *,
    title: str,
    lines: list[str],
    color: int = 0x57F287,
    extra: str | None = None,
    ping_msg: str | None = None,
) -> None:
    """Send an embed for slash, plain text for prefix.
    ping_msg is sent as raw content so Discord actually delivers the mention ping."""
    body = "\n".join(lines)
    if extra:
        body += f"\n\n{extra}"
    if ctx.interaction:
        embed = discord.Embed(title=title, description=body, color=color)
        embed.set_footer(text=f"🌻 Garden Game • {ctx.author.display_name}")
        if ping_msg:
            await ctx.send(content=ping_msg, embed=embed)
        else:
            await ctx.send(embed=embed)
    else:
        content = f"**{title}**\n{body}"
        if ping_msg:
            content = f"{ping_msg}\n{content}"
        await ctx.reply(content, mention_author=False)


async def _send_error(ctx: commands.Context, msg: str) -> None:
    if ctx.interaction:
        embed = discord.Embed(description=f"⚠️ {msg}", color=0xED4245)
        await ctx.send(embed=embed, ephemeral=True)
    else:
        await ctx.reply(f"⚠️ {msg}", mention_author=False)


# ── Cog ────────────────────────────────────────────────────────────────────────

class GardenCog(commands.Cog, name="Garden"):
    """Text-based garden game."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ping_loop.start()

    def cog_unload(self) -> None:
        self._ping_loop.cancel()

    # ── Background halfway-ping loop ──────────────────────────────────────────

    @tasks.loop(seconds=20)
    async def _ping_loop(self) -> None:
        now     = _now()
        changed = False

        for uid_str, user in _db.iter_all():
            uid_int    = int(uid_str)
            channel_id = user.get("notify_channel_id")
            user_dirty = False

            for i, plot in enumerate(user.get("plots", [])):
                if plot.get("notify_halfway"):
                    continue
                ping_at = plot.get("ping_at")
                if not ping_at or now < ping_at:
                    continue

                state = _effective_state(plot)
                if state != "growing":
                    plot["notify_halfway"] = True
                    user_dirty = True
                    continue

                crop      = plot.get("crop") or "crop"
                info      = _item_info(crop)
                em        = info.get("emoji", "🌿")
                grow_left = max(0.0, (plot.get("grow_deadline") or now) - now)

                msg = (
                    f"🌱 <@{uid_int}> your **{em} {crop.capitalize()}** "
                    f"in **Plot {i + 1}** is halfway through growing!\n"
                    f"⏱ Ready in about **{_fmt_time(grow_left)}**."
                )
                if not plot.get("watered") and not plot.get("auto_watered"):
                    msg += (
                        f"\n💧 **It still needs water!** "
                        f"Run `th/water {i + 1}` or `/water {i + 1}` before it dies."
                    )

                sent = False
                if channel_id:
                    try:
                        ch = self.bot.get_channel(channel_id)
                        if ch is None:
                            ch = await self.bot.fetch_channel(channel_id)
                        await ch.send(msg)
                        sent = True
                    except Exception:
                        pass

                if not sent:
                    try:
                        u_obj = self.bot.get_user(uid_int) or await self.bot.fetch_user(uid_int)
                        await u_obj.send(msg)
                        sent = True
                    except Exception:
                        pass

                if sent:
                    plot["notify_halfway"] = True
                    user_dirty = True

            if user_dirty:
                changed = True

        if changed:
            _db.flush()

    @_ping_loop.before_loop
    async def _before_ping_loop(self) -> None:
        await self.bot.wait_until_ready()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load(self, uid: int) -> dict[str, Any]:
        return _db.get(uid)

    def _save(self, uid: int, user: dict[str, Any]) -> None:
        _db.save(uid, user)

    def _record_channel(self, user: dict, ctx: commands.Context) -> None:
        if hasattr(ctx, "channel") and ctx.channel:
            user["notify_channel_id"] = ctx.channel.id

    def _pre_action(self, user: dict, uid: int) -> tuple[str | None, str | None]:
        """Resolve any pending pest before a state-changing action.
        Returns (loss_msg, None) — pests already resolved don't trigger a new ping."""
        loss = _consume_pest(user, scared=False)
        return loss, None

    # ── /garden ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="garden", description="View the current state of your garden plots.")
    async def garden(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)

        pest_idx = user.get("pending_pest")
        lines = []
        for i, plot in enumerate(user["plots"]):
            lines.append(_plot_line(i, plot))

        lines.append("")
        lines.append(f"💰 **Coins:** {user['coins']:,}")

        # Active pet
        pet_key = user.get("equipped_pet")
        if pet_key and pet_key in PETS:
            pd = PETS[pet_key]
            lines.append(f"{pd['emoji']} **Pet:** {pet_key.replace('_',' ').title()} — {pd['description']}")

        # Scarecrow turns
        sc = user.get("scarecrow_turns", 0)
        if sc > 0:
            lines.append(f"🪚 **Scarecrow:** {sc} turn{'s' if sc != 1 else ''} of protection remaining")

        extra = None
        if pest_idx is not None:
            extra = (
                f"🐦 **Pest Alert!** Pests are on Plot {pest_idx + 1}! "
                f"Use `/scare` or `th/scare` now — next action will destroy the crop!"
            )

        self._save(uid, user)
        await _send(ctx, title="🌻 Your Garden", lines=lines, extra=extra)

    # ── /shop ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="shop", description="Browse seeds, saplings, boosters, and pet eggs.")
    async def shop(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        self._save(uid, user)
        lines = _shop_lines()
        await _send(ctx, title="🏪 Garden Shop", lines=lines, color=0xFEE75C)

    # ── /buy ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="buy", description="Buy seeds, saplings, boosters, or pet eggs.")
    @app_commands.describe(item="Item to buy", amount="How many to buy (default 1)")
    async def buy(self, ctx: commands.Context, item: str, amount: int = 1) -> None:
        prefix = ctx.prefix or "th/"
        if amount < 1:
            await _send_error(ctx, "Amount must be at least 1.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        pest_loss, _ = self._pre_action(user, uid)

        n = item.lower().strip()

        # ── Crops ──
        plantable = _resolve_plantable(n)
        if plantable:
            key, kind = plantable
            info = _item_info(key)
            cost_each = info["seed_cost"]
            total_cost = cost_each * amount
            if user["coins"] < total_cost:
                await _send_error(ctx, f"Need **{total_cost:,}c** — you have **{user['coins']:,}c**.")
                self._save(uid, user)
                return
            user["coins"] -= total_cost
            if kind == "crop":
                seeds = user.setdefault("seeds", {})
                seeds[key] = seeds.get(key, 0) + amount
                inv_count = seeds[key]
                label = f"{info['emoji']} {key.capitalize()} Seed{'s' if amount > 1 else ''}"
            else:
                saps = user.setdefault("saplings", {})
                saps[key] = saps.get(key, 0) + amount
                inv_count = saps[key]
                label = f"{info['emoji']} {key.capitalize()} Sapling{'s' if amount > 1 else ''}"
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                f"Bought **{amount}x {label}** for **{total_cost:,}c**.",
                f"💰 Remaining: **{user['coins']:,}c** | Inventory: **{inv_count}**",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="🛒 Purchased!", lines=lines, extra=event_msg, ping_msg=ping_msg)
            return

        # ── Boosters ──
        booster_key = _resolve_booster(n)
        if booster_key:
            info = BOOSTERS[booster_key]
            total_cost = info["cost"] * amount
            if user["coins"] < total_cost:
                await _send_error(ctx, f"Need **{total_cost:,}c** — you have **{user['coins']:,}c**.")
                self._save(uid, user)
                return
            user["coins"] -= total_cost
            bst = user.setdefault("boosters", {})
            bst[booster_key] = bst.get(booster_key, 0) + amount
            label = f"{info['emoji']} {booster_key.replace('_',' ').title()}"
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                f"Bought **{amount}x {label}** for **{total_cost:,}c**.",
                f"💰 Remaining: **{user['coins']:,}c** | In bag: **{bst[booster_key]}**",
                f"Use it with `{prefix}use {booster_key.replace('_',' ')} <plot>` or `/use`.",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="🛒 Purchased!", lines=lines, extra=event_msg, ping_msg=ping_msg)
            return

        # ── Pet eggs ──
        pet_key = _resolve_pet(n)
        if pet_key:
            info = PETS[pet_key]
            total_cost = info["cost"] * amount
            if user["coins"] < total_cost:
                await _send_error(ctx, f"Need **{total_cost:,}c** — you have **{user['coins']:,}c**.")
                self._save(uid, user)
                return
            user["coins"] -= total_cost
            eggs = user.setdefault("pet_eggs", {})
            eggs[pet_key] = eggs.get(pet_key, 0) + amount
            label = f"{info['emoji']} {pet_key.replace('_',' ').title()} Egg"
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                f"Bought **{amount}x {label}** for **{total_cost:,}c**!",
                f"💰 Remaining: **{user['coins']:,}c**",
                f"Equip it with `{prefix}pet equip {pet_key.replace('_',' ')}` or `/pet`.",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="🛒 Purchased!", lines=lines, extra=event_msg, ping_msg=ping_msg)
            return

        all_names = list(CROPS) + list(TREES) + list(BOOSTERS) + list(PETS)
        await _send_error(ctx,
            f"Unknown item `{item}`. "
            f"See `{prefix}shop` for available items."
        )
        self._save(uid, user)

    # ── /inventory (/inv) ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="Show your full inventory.")
    async def inventory(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)

        seeds     = user.get("seeds", {})
        saplings  = user.get("saplings", {})
        harvested = user.get("harvested", {})
        boosters  = user.get("boosters", {})
        pet_eggs  = user.get("pet_eggs", {})
        pet_key   = user.get("equipped_pet")

        lines = [f"💰 **Coins:** {user['coins']:,}", ""]

        lines.append("**🌱 Seeds:**")
        if seeds:
            for key, qty in seeds.items():
                em = CROPS.get(key, {}).get("emoji", "🌿")
                lines.append(f"  {em} {key.capitalize()} Seed: **{qty}**")
        else:
            lines.append("  *(none)*")

        lines.append("")
        lines.append("**🌳 Saplings:**")
        if saplings:
            for key, qty in saplings.items():
                em = TREES.get(key, {}).get("emoji", "🌿")
                lines.append(f"  {em} {key.capitalize()} Sapling: **{qty}**")
        else:
            lines.append("  *(none)*")

        lines.append("")
        lines.append("**🧺 Harvested (ready to sell):**")
        if harvested:
            for key, qty in harvested.items():
                info = _item_info(key)
                em   = info.get("emoji", "🌿")
                price = info.get("sell_price", 0)
                lines.append(f"  {em} {key.capitalize()}: **{qty}** (≈ {price * qty:,}c)")
        else:
            lines.append("  *(none)*")

        lines.append("")
        lines.append("**⚡ Boosters:**")
        if boosters:
            for key, qty in boosters.items():
                em = BOOSTERS.get(key, {}).get("emoji", "⚡")
                lines.append(f"  {em} {key.replace('_',' ').title()}: **{qty}**")
        else:
            lines.append("  *(none)*")

        lines.append("")
        lines.append("**🥚 Pet Eggs:**")
        if pet_eggs:
            for key, qty in pet_eggs.items():
                em = PETS.get(key, {}).get("emoji", "🥚")
                lines.append(f"  {em} {key.replace('_',' ').title()} Egg: **{qty}**")
        else:
            lines.append("  *(none)*")

        lines.append("")
        lines.append("**🐾 Equipped Pet:**")
        if pet_key and pet_key in PETS:
            pd = PETS[pet_key]
            lines.append(f"  {pd['emoji']} {pet_key.replace('_',' ').title()} — {pd['description']}")
        else:
            lines.append("  *(none — use `th/pet equip <name>` to equip)*")

        sc = user.get("scarecrow_turns", 0)
        if sc > 0:
            lines.append(f"\n🪚 **Scarecrow:** {sc} turn{'s' if sc != 1 else ''} of garden protection active")

        extra = None
        if user.get("pending_pest") is not None:
            extra = "🐦 **Pest alert active!** Use `/scare` or `th/scare` before your next action!"

        self._save(uid, user)
        await _send(ctx, title="🎒 Inventory", lines=lines, extra=extra)

    # ── /plant ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="plant", description="Plant a seed or sapling into a specific plot.")
    @app_commands.describe(crop="Crop or tree to plant", plot="Plot number")
    async def plant(self, ctx: commands.Context, crop: str = "", plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not crop or not plot:
            await _send_error(ctx,
                f"Usage: `{prefix}plant <crop/tree> <plot>` or `/plant [crop] [plot]`"
            )
            return

        plantable = _resolve_plantable(crop)
        if not plantable:
            await _send_error(ctx,
                f"Unknown item `{crop}`. "
                f"Crops: {', '.join(CROPS)} | Trees: {', '.join(TREES)}"
            )
            return
        crop_key, kind = plantable

        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number.")
            return

        num_plots = len(self._load(ctx.author.id)["plots"])
        if not (1 <= plot_num <= num_plots):
            await _send_error(ctx, f"Plot number must be between 1 and {num_plots}.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        pest_loss, _ = self._pre_action(user, uid)

        # Check inventory
        if kind == "crop":
            inv = user.get("seeds", {})
            inv_label = "Corn Seed" if crop_key == "corn" else f"{crop_key.capitalize()} Seed"
        else:
            inv = user.get("saplings", {})
            inv_label = f"{crop_key.capitalize()} Sapling"

        if inv.get(crop_key, 0) < 1:
            await _send_error(ctx,
                f"You don't have any **{inv_label}**. "
                f"Buy one with `{prefix}buy {crop_key}`."
            )
            self._save(uid, user)
            return

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        cur_state = _effective_state(plot_data)

        if cur_state not in ("empty", "dead"):
            await _send_error(ctx,
                f"Plot {plot_num} is not empty (state: **{cur_state}**). Harvest or clear it first."
            )
            self._save(uid, user)
            return

        # Consume seed/sapling
        inv[crop_key] -= 1
        if inv[crop_key] <= 0:
            del inv[crop_key]

        now        = _now()
        info       = _item_info(crop_key)
        grow_secs  = info["growth_mins"] * 60

        # Mole Buddy speed bonus
        if user.get("equipped_pet") == "mole_buddy":
            grow_secs = grow_secs * MOLE_BUDDY_SPEED

        water_secs = grow_secs * WATER_PCT

        user["plots"][plot_idx] = {
            "crop":           crop_key,
            "item_type":      kind,
            "planted_at":     now,
            "watered":        False,
            "auto_watered":   False,
            "water_deadline": now + water_secs,
            "grow_deadline":  now + grow_secs,
            "state":          "growing",
            "golden":         False,
            "ping_at":        now + grow_secs / 2,
            "notify_halfway": False,
        }

        event_msg, ping_msg = _roll_event(user, uid)
        self._save(uid, user)

        em       = info["emoji"]
        type_tag = " Sapling" if kind == "tree" else " Seed"
        mole_tag = " *(Mole Buddy: 20% faster!)*" if user.get("equipped_pet") == "mole_buddy" else ""
        lines = [
            f"Planted **{em} {crop_key.capitalize()}{type_tag}** in Plot {plot_num}!{mole_tag}",
            f"⏱ Ready in **{_fmt_time(grow_secs)}**.",
            f"💧 Water it within **{_fmt_time(water_secs)}** or it dies.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="🌱 Planted!", lines=lines, color=0x57F287, extra=event_msg, ping_msg=ping_msg)

    # ── /water ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="water", description="Water a crop to keep it alive.")
    @app_commands.describe(plot="Plot number to water")
    async def water(self, ctx: commands.Context, plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not plot:
            await _send_error(ctx, f"Usage: `{prefix}water <plot>` or `/water [plot]`")
            return
        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)

        num_plots = len(user["plots"])
        if not (1 <= plot_num <= num_plots):
            await _send_error(ctx, f"Plot number must be between 1 and {num_plots}.")
            return

        pest_loss, _ = self._pre_action(user, uid)

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        state     = _effective_state(plot_data)

        if state == "empty":
            await _send_error(ctx, f"Plot {plot_num} is empty — nothing to water!")
            self._save(uid, user)
            return
        if state == "dead":
            await _send_error(ctx, f"Plot {plot_num} is dead. Clear and replant.")
            self._save(uid, user)
            return
        if state == "ready":
            await _send_error(ctx, f"Plot {plot_num} is ready to harvest — no watering needed!")
            self._save(uid, user)
            return
        if state == "infested":
            await _send_error(ctx, f"Plot {plot_num} is infested! Scare them first with `{prefix}scare`.")
            self._save(uid, user)
            return
        if plot_data.get("auto_watered"):
            await _send_error(ctx, f"Plot {plot_num} has an Auto-Waterer — it's always watered! 🚿")
            self._save(uid, user)
            return
        if plot_data.get("watered"):
            await _send_error(ctx, f"Plot {plot_num} is already watered! 💧")
            self._save(uid, user)
            return

        plot_data["watered"] = True
        event_msg, ping_msg = _roll_event(user, uid)
        self._save(uid, user)

        crop      = plot_data["crop"]
        em        = _item_info(crop).get("emoji", "🌿")
        grow_left = max(0, plot_data["grow_deadline"] - _now())
        lines = [
            f"Watered **{em} {crop.capitalize()}** in Plot {plot_num}! 💧",
            f"⏱ Ready in **{_fmt_time(grow_left)}**.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="💧 Watered!", lines=lines, extra=event_msg, ping_msg=ping_msg)

    # ── /use ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="use", description="Apply a booster item to a plot.")
    @app_commands.describe(booster="Booster to use (speed_fertilizer, auto_waterer, scarecrow)", plot="Plot number (not needed for scarecrow)")
    async def use(self, ctx: commands.Context, booster: str = "", plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not booster:
            await _send_error(ctx,
                f"Usage: `{prefix}use <booster> [plot]` or `/use [booster] [plot]`\n"
                f"Boosters: `speed_fertilizer`, `auto_waterer`, `scarecrow`"
            )
            return

        booster_key = _resolve_booster(booster)
        if not booster_key:
            await _send_error(ctx,
                f"Unknown booster `{booster}`. Valid: `speed_fertilizer`, `auto_waterer`, `scarecrow`."
            )
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        pest_loss, _ = self._pre_action(user, uid)

        bst = user.setdefault("boosters", {})
        if bst.get(booster_key, 0) < 1:
            bname = booster_key.replace("_", " ").title()
            await _send_error(ctx,
                f"You don't have any **{bname}**. Buy one with `{prefix}buy {booster_key.replace('_',' ')}`."
            )
            self._save(uid, user)
            return

        # ── Scarecrow: whole-garden, no plot arg needed ──
        if booster_key == "scarecrow":
            bst[booster_key] -= 1
            if bst[booster_key] <= 0:
                del bst[booster_key]
            user["scarecrow_turns"] = user.get("scarecrow_turns", 0) + 3
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                "🪚 **Scarecrow deployed!** Your garden is protected from pests for **3 /wait turns**.",
                f"Active turns: **{user['scarecrow_turns']}**",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="🪚 Scarecrow Placed!", lines=lines, color=0x5865F2, extra=event_msg, ping_msg=ping_msg)
            return

        # ── Plot-targeted boosters ──
        if not plot:
            await _send_error(ctx, f"`{booster_key.replace('_',' ').title()}` requires a plot number.")
            return
        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number.")
            return

        num_plots = len(user["plots"])
        if not (1 <= plot_num <= num_plots):
            await _send_error(ctx, f"Plot number must be between 1 and {num_plots}.")
            return

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        state     = _effective_state(plot_data)

        if state not in ("growing", "infested"):
            await _send_error(ctx, f"Plot {plot_num} must be actively growing to apply a booster.")
            self._save(uid, user)
            return

        bst[booster_key] -= 1
        if bst[booster_key] <= 0:
            del bst[booster_key]

        if booster_key == "speed_fertilizer":
            now        = _now()
            grow_left  = max(0, plot_data["grow_deadline"] - now)
            cut        = grow_left * 0.50
            plot_data["grow_deadline"]  -= cut
            if plot_data.get("water_deadline"):
                plot_data["water_deadline"] = min(plot_data["water_deadline"], plot_data["grow_deadline"])
            if plot_data.get("ping_at"):
                plot_data["ping_at"] -= cut / 2
            crop      = plot_data["crop"]
            em        = _item_info(crop).get("emoji", "🌿")
            new_left  = max(0, plot_data["grow_deadline"] - now)
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                f"⚡ **Speed Fertilizer applied** to Plot {plot_num}!",
                f"Remaining grow time cut by 50% — {em} {crop.capitalize()} ready in **{_fmt_time(new_left)}**!",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="⚡ Fertilized!", lines=lines, color=0xFEE75C, extra=event_msg, ping_msg=ping_msg)

        elif booster_key == "auto_waterer":
            plot_data["auto_watered"] = True
            plot_data["watered"]      = True   # counts as watered too
            crop = plot_data["crop"]
            em   = _item_info(crop).get("emoji", "🌿")
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                f"🚿 **Auto-Waterer installed** on Plot {plot_num}!",
                f"{em} {crop.capitalize()} will stay perfectly watered until harvested.",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="🚿 Auto-Waterer Installed!", lines=lines, color=0x3498DB, extra=event_msg, ping_msg=ping_msg)

    # ── /pet ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="pet", description="Manage your pets. Usage: th/pet equip <pet_name>")
    @app_commands.describe(action="Action to perform: equip", pet_name="Pet name to equip")
    async def pet(self, ctx: commands.Context, action: str = "", pet_name: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if action.lower() != "equip" or not pet_name:
            await _send_error(ctx,
                f"Usage: `{prefix}pet equip <pet_name>` or `/pet equip <name>`\n"
                f"Available pets: `farm_dog`, `lucky_cat`, `mole_buddy`"
            )
            return

        pet_key = _resolve_pet(pet_name)
        if not pet_key:
            await _send_error(ctx,
                f"Unknown pet `{pet_name}`. Valid: `farm_dog`, `lucky_cat`, `mole_buddy`."
            )
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)

        eggs = user.setdefault("pet_eggs", {})
        if eggs.get(pet_key, 0) < 1:
            pd = PETS[pet_key]
            await _send_error(ctx,
                f"You don't own a **{pd['emoji']} {pet_key.replace('_',' ').title()} Egg**. "
                f"Buy one with `{prefix}buy {pet_key.replace('_',' ')}`."
            )
            self._save(uid, user)
            return

        # Hatch the egg and equip
        eggs[pet_key] -= 1
        if eggs[pet_key] <= 0:
            del eggs[pet_key]
        user["equipped_pet"] = pet_key

        pd = PETS[pet_key]
        self._save(uid, user)
        lines = [
            f"{pd['emoji']} **{pet_key.replace('_',' ').title()}** is now your active companion!",
            f"Passive: {pd['description']}",
            f"*(You can only have 1 pet equipped at a time)*",
        ]
        await _send(ctx, title=f"{pd['emoji']} Pet Equipped!", lines=lines, color=0xE91E63)

    # ── /harvest ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="harvest", description="Harvest a fully grown crop or fruit.")
    @app_commands.describe(plot="Plot number to harvest")
    async def harvest(self, ctx: commands.Context, plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not plot:
            await _send_error(ctx, f"Usage: `{prefix}harvest <plot>` or `/harvest [plot]`")
            return
        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)

        num_plots = len(user["plots"])
        if not (1 <= plot_num <= num_plots):
            await _send_error(ctx, f"Plot number must be between 1 and {num_plots}.")
            return

        pest_loss, _ = self._pre_action(user, uid)

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        state     = _effective_state(plot_data)

        if state != "ready":
            msgs = {
                "empty":    "Plot is empty — nothing to harvest.",
                "growing":  f"Crop isn't ready yet! Use `{prefix}garden` to check progress.",
                "dead":     "The crop is dead. Clear the plot and replant.",
                "infested": f"Pests are on this plot! Use `{prefix}scare` first.",
            }
            await _send_error(ctx, msgs.get(state, f"Plot {plot_num} is not ready."))
            self._save(uid, user)
            return

        crop   = plot_data["crop"]
        info   = _item_info(crop)
        em     = info.get("emoji", "🌿")
        golden = plot_data.get("golden", False)

        user["plots"][plot_idx] = copy.deepcopy(_EMPTY_PLOT)

        if golden:
            gold_coins = info.get("sell_price", 0) * 2
            user["coins"] += gold_coins
            event_msg, ping_msg = _roll_event(user, uid)
            self._save(uid, user)
            lines = [
                f"✨ **Golden Harvest!** Harvested **{em} {crop.capitalize()}** from Plot {plot_num}!",
                f"💰 Instantly earned **{gold_coins:,}c** (2× value)!",
                f"New balance: **{user['coins']:,}c**",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="✨ Golden Harvest!", lines=lines, color=0xFFD700, extra=event_msg, ping_msg=ping_msg)
        else:
            harvested  = user.setdefault("harvested", {})
            sell_price = info.get("sell_price", 0)

            # Lucky Cat: 15% chance to double
            lucky_bonus = (
                user.get("equipped_pet") == "lucky_cat"
                and random.random() < LUCKY_CAT_CHANCE
            )
            if lucky_bonus:
                lucky_coins = sell_price * 2
                user["coins"] += lucky_coins
                event_msg, ping_msg = _roll_event(user, uid)
                self._save(uid, user)
                lines = [
                    f"🐈 **Lucky Cat bonus!** Harvested **{em} {crop.capitalize()}** from Plot {plot_num}!",
                    f"💰 Lucky double yield — earned **{lucky_coins:,}c** instantly!",
                    f"New balance: **{user['coins']:,}c**",
                ]
                if pest_loss:
                    lines.append(f"\n{pest_loss}")
                await _send(ctx, title="🐈 Lucky Harvest!", lines=lines, color=0xFFD700, extra=event_msg, ping_msg=ping_msg)
            else:
                harvested[crop] = harvested.get(crop, 0) + 1
                event_msg, ping_msg = _roll_event(user, uid)
                self._save(uid, user)
                lines = [
                    f"Harvested **{em} {crop.capitalize()}** from Plot {plot_num}!",
                    f"Added to inventory — sell with `{prefix}sell {crop}` for **{sell_price:,}c**.",
                ]
                if pest_loss:
                    lines.append(f"\n{pest_loss}")
                await _send(ctx, title="🧺 Harvested!", lines=lines, color=0xFEE75C, extra=event_msg, ping_msg=ping_msg)

    # ── /sell ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="sell", description="Sell harvested crops or fruits for coins.")
    @app_commands.describe(crop="Crop/fruit to sell", amount="Amount to sell (default: all)")
    async def sell(self, ctx: commands.Context, crop: str = "", amount: Optional[str] = None) -> None:
        prefix = ctx.prefix or "th/"
        if not crop:
            await _send_error(ctx, f"Usage: `{prefix}sell <crop/fruit> [amount]` or `/sell [crop] [amount]`")
            return

        crop_key = _resolve_sellable(crop)
        if not crop_key:
            await _send_error(ctx, f"Unknown item `{crop}`. Available: {', '.join({**CROPS, **TREES})}")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        pest_loss, _ = self._pre_action(user, uid)

        harvested = user.setdefault("harvested", {})
        owned     = harvested.get(crop_key, 0)
        if owned == 0:
            await _send_error(ctx,
                f"You have no harvested **{crop_key.capitalize()}** to sell. Grow and harvest some first!"
            )
            self._save(uid, user)
            return

        if amount is None or amount.lower() == "all":
            qty = owned
        else:
            try:
                qty = int(amount)
            except ValueError:
                await _send_error(ctx, f"`{amount}` is not a valid amount.")
                self._save(uid, user)
                return
            if qty < 1:
                await _send_error(ctx, "Amount must be at least 1.")
                self._save(uid, user)
                return
            if qty > owned:
                await _send_error(ctx, f"You only have **{owned}x {crop_key.capitalize()}** — can't sell {qty}.")
                self._save(uid, user)
                return

        info       = _item_info(crop_key)
        total_gain = info.get("sell_price", 0) * qty
        user["coins"] += total_gain
        harvested[crop_key] = owned - qty
        if harvested[crop_key] <= 0:
            del harvested[crop_key]

        em = info.get("emoji", "🌿")
        event_msg, ping_msg = _roll_event(user, uid)
        self._save(uid, user)
        lines = [
            f"Sold **{qty}x {em} {crop_key.capitalize()}** for **{total_gain:,}c**!",
            f"💰 New balance: **{user['coins']:,}c**.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="💰 Sold!", lines=lines, color=0x57F287, extra=event_msg, ping_msg=ping_msg)

    # ── /wait ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="wait", description="Simulate time passing so crops can grow.")
    @app_commands.describe(minutes="Minutes to fast-forward (max 60)")
    async def wait(self, ctx: commands.Context, minutes: float = 1.0) -> None:
        if minutes <= 0:
            await _send_error(ctx, "Minutes must be greater than 0.")
            return
        minutes = min(minutes, 60)
        skip    = minutes * 60

        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        pest_loss, _ = self._pre_action(user, uid)

        for plot in user["plots"]:
            if plot.get("grow_deadline"):
                plot["grow_deadline"]  -= skip
            if plot.get("water_deadline"):
                plot["water_deadline"] -= skip
            if plot.get("ping_at"):
                plot["ping_at"] -= skip

        # Decrement scarecrow turns
        sc = user.get("scarecrow_turns", 0)
        if sc > 0:
            user["scarecrow_turns"] = max(0, sc - 1)

        event_msg, ping_msg = _roll_event(user, uid)
        self._save(uid, user)

        sc_after = user.get("scarecrow_turns", 0)
        sc_note  = ""
        if sc > 0:
            if sc_after == 0:
                sc_note = "\n🪚 Scarecrow protection has **expired**."
            else:
                sc_note = f"\n🪚 Scarecrow: **{sc_after} turn{'s' if sc_after != 1 else ''}** of protection remaining."

        lines = [
            f"⏩ Fast-forwarded **{minutes:.1f} minute{'s' if minutes != 1 else ''}**.",
            f"Use `th/garden` or `/garden` to check your plots.{sc_note}",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="⏩ Time Skip", lines=lines, color=0x5865F2, extra=event_msg, ping_msg=ping_msg)

    # ── /scare ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="scare", description="Scare off pests from your garden!")
    async def scare(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)

        pest_idx = user.get("pending_pest")
        if pest_idx is None:
            lines = ["No pests to scare right now! Your garden is safe. 🕊️"]
            self._save(uid, user)
            await _send(ctx, title="🕊️ All Clear", lines=lines)
            return

        result    = _consume_pest(user, scared=True)
        event_msg, ping_msg = _roll_event(user, uid)
        self._save(uid, user)

        lines = [result or "Pests scared off!"]
        await _send(ctx, title="👏 Pests Scared!", lines=lines, color=0x57F287, extra=event_msg, ping_msg=ping_msg)

    # ── Error handlers ────────────────────────────────────────────────────────

    @buy.error
    @plant.error
    @water.error
    @use.error
    @harvest.error
    @sell.error
    @wait.error
    async def _arg_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            prefix = ctx.prefix or "th/"
            cmd    = ctx.command.name if ctx.command else "command"
            await _send_error(ctx,
                f"Invalid arguments for `{prefix}{cmd}`. Use `{prefix}shop` to see what's available."
            )
        else:
            raise error


# ── /leaderboard ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Show the top garden earners.")
    async def leaderboard(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)
        self._record_channel(user, ctx)
        self._save(uid, user)

        all_users = _db.iter_all()

        rows: list[tuple[int, int, str]] = []
        for uid_str, udata in all_users:
            coins    = udata.get("coins", 0)
            earned   = coins
            # Add value of harvested items not yet sold
            for key, qty in udata.get("harvested", {}).items():
                earned += _item_info(key).get("sell_price", 0) * qty
            rows.append((earned, int(uid_str), uid_str))

        rows.sort(reverse=True)
        top = rows[:10]

        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for rank, (wealth, entry_uid, uid_str) in enumerate(top, 1):
            medal = medals[rank - 1] if rank <= 3 else f"**#{rank}**"
            # Try to get a display name from the bot cache
            member = ctx.guild.get_member(entry_uid) if ctx.guild else None
            if member:
                name = member.display_name
            else:
                user_obj = self.bot.get_user(entry_uid)
                name = user_obj.display_name if user_obj else f"Player {uid_str[-4:]}"
            you = " ← you" if entry_uid == ctx.author.id else ""
            lines.append(f"{medal} **{name}** — {wealth:,}c{you}")

        if not lines:
            lines.append("No players yet — be the first to start farming!")

        # Show caller's rank if not in top 10
        caller_rank = next((i + 1 for i, (_, u, _) in enumerate(rows) if u == ctx.author.id), None)
        extra = None
        if caller_rank and caller_rank > 10:
            caller_wealth = rows[caller_rank - 1][0]
            extra = f"Your rank: **#{caller_rank}** — {caller_wealth:,}c"

        await _send(ctx, title="🏆 Garden Leaderboard", lines=lines, color=0xFFD700, extra=extra)


# ── Welcome embed helper ───────────────────────────────────────────────────────

async def send_welcome(channel: discord.abc.Messageable, user: discord.User | discord.Member) -> None:
    embed = discord.Embed(
        title="🌻 Welcome to the Garden Game!",
        description=(
            f"Hey {user.mention}! Your farm is ready. Time to grow something amazing!\n\n"
            f"**Starting Profile:**\n"
            f"💰 Coins: **100** | 🌽 Corn Seeds: **2** | 🌱 Plots: **3 empty**\n\n"
            f"**Quick Start:**\n"
            f"1. `/plant corn 1` or `th/plant corn 1` — plant your first seed\n"
            f"2. `/water 1` or `th/water 1` — water it within 30 s or it dies\n"
            f"3. `/wait 1` or `th/wait 1` — skip time to grow\n"
            f"4. `/harvest 1` or `th/harvest 1` — collect your crop\n"
            f"5. `/sell corn` or `th/sell corn` — cash in\n\n"
            f"**New: Trees 🌳 · Boosters ⚡ · Pets 🐾**\n"
            f"Run `/shop` or `th/shop` to see everything available!\n\n"
            f"💡 Both `/commands` and `th/commands` work identically!"
        ),
        color=0x57F287,
    )
    embed.set_footer(text="🌻 Garden Game • Good luck, farmer!")
    await channel.send(embed=embed)


# ── Cog setup ──────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GardenCog(bot))
