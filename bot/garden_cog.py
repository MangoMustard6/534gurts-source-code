"""
GardenCog — Text-based Garden Game for IHTX Bot.

Hybrid commands (slash + th/ prefix):
  /garden   th/garden   — View your plots
  /shop     th/shop     — Browse seeds for sale
  /buy      th/buy      — Buy seeds
  /inventory th/inventory (alias: /inv, th/inv) — Show seeds & harvested crops
  /plant    th/plant    — Plant a seed into a plot
  /water    th/water    — Water a crop before it dies
  /harvest  th/harvest  — Harvest a ready crop
  /sell     th/sell     — Sell harvested crops for coins
  /wait     th/wait     — Fast-forward time so crops can grow
  /scare    th/scare    — Scare off pests before they eat your crop

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
from discord.ext import commands

# ── Crop catalogue ────────────────────────────────────────────────────────────

CROPS: dict[str, dict[str, Any]] = {
    "corn":       {"seed_cost": 10,  "growth_mins": 1,  "sell_price": 15,   "emoji": "🌽"},
    "pumpkin":    {"seed_cost": 25,  "growth_mins": 3,  "sell_price": 45,   "emoji": "🎃"},
    "tomato":     {"seed_cost": 50,  "growth_mins": 5,  "sell_price": 95,   "emoji": "🍅"},
    "blueberry":  {"seed_cost": 100, "growth_mins": 8,  "sell_price": 210,  "emoji": "🫐"},
    "beans":      {"seed_cost": 200, "growth_mins": 12, "sell_price": 450,  "emoji": "🫘"},
    "watermelon": {"seed_cost": 500, "growth_mins": 20, "sell_price": 1200, "emoji": "🍉"},
}

NUM_PLOTS       = 5
EVENT_CHANCE    = 0.15
WATER_PCT       = 0.50   # must water within this fraction of grow time or crop dies
WATER_WARN_PCT  = 0.35   # show 💧 warning after this fraction has elapsed

# ── Data model ────────────────────────────────────────────────────────────────

_DB_PATH = Path("bot/garden_data.json")

_EMPTY_PLOT: dict[str, Any] = {
    "crop":           None,
    "planted_at":     None,
    "watered":        False,
    "water_deadline": None,   # unix ts: must water by here
    "grow_deadline":  None,   # unix ts: ready at here
    "state":          "empty",  # empty | growing | ready | dead | infested
    "golden":         False,
}

_DEFAULT_USER: dict[str, Any] = {
    "coins":        100,
    "seeds":        {"corn": 2},
    "harvested":    {},
    "plots":        None,   # filled in _ensure_user
    "pending_pest": None,   # 0-based plot index with active crow infestation
}


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
        # Migrate: ensure plots list has correct length
        plots = u.setdefault("plots", [])
        while len(plots) < NUM_PLOTS:
            plots.append(copy.deepcopy(_EMPTY_PLOT))
        u.setdefault("pending_pest", None)
        u.setdefault("seeds", {"corn": 2})
        u.setdefault("harvested", {})
        u.setdefault("coins", 100)
        return u

    def save(self, uid: int, data: dict[str, Any]) -> None:
        self._data[str(uid)] = data
        self._save()


_db = GardenDB()

# ── Pure helpers ──────────────────────────────────────────────────────────────

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


def _resolve_crop(name: str) -> str | None:
    n = name.lower().strip()
    for crop in CROPS:
        if n == crop or (crop.startswith(n) and len(n) >= 2):
            return crop
    return None


def _effective_state(plot: dict) -> str:
    """Compute current plot state from timestamps without mutating."""
    stored = plot.get("state", "empty")
    if stored in ("empty", "dead", "infested"):
        return stored
    now = _now()
    if not plot.get("watered") and plot.get("water_deadline") and now > plot["water_deadline"]:
        return "dead"
    if plot.get("grow_deadline") and now >= plot["grow_deadline"]:
        return "ready"
    return "growing"


def _sync_state(plot: dict) -> None:
    """Persist computed state back into the plot dict."""
    plot["state"] = _effective_state(plot)


def _plot_line(idx: int, plot: dict) -> str:
    """Single-line summary for /garden list."""
    state = _effective_state(plot)
    n = idx + 1
    if state == "empty":
        return f"**Plot {n}:** 🌱 Empty"
    crop = plot.get("crop") or "???"
    info = CROPS.get(crop, {})
    em   = info.get("emoji", "🌿")
    name = crop.capitalize()

    if state == "dead":
        return f"**Plot {n}:** 💀 Dead (was {em} {name})"
    if state == "infested":
        return f"**Plot {n}:** 🐦 Infested! ({em} {name}) — use `/scare` / `th/scare` NOW!"
    if state == "ready":
        golden_tag = " ✨ **Golden!**" if plot.get("golden") else ""
        return f"**Plot {n}:** {em} {name} ✅ Ready to Harvest!{golden_tag}"

    # growing
    now       = _now()
    grow_left = max(0.0, plot["grow_deadline"] - now)
    total_s   = info.get("growth_mins", 1) * 60
    elapsed   = total_s - grow_left
    pct       = min(100.0, elapsed / max(1, total_s) * 100)
    bar       = _progress_bar(pct)

    water_warn = ""
    if not plot.get("watered"):
        wdl = plot.get("water_deadline") or 0
        since_plant = _now() - (plot.get("planted_at") or _now())
        if since_plant / max(1, total_s) >= WATER_WARN_PCT:
            water_left = max(0, wdl - _now())
            water_warn = f" 💧 Needs Water! ({_fmt_time(water_left)} left to water)"
        else:
            water_warn = " 💧 Unwatered"

    return f"**Plot {n}:** {em} {name} [{_fmt_time(grow_left)} left] {bar}{water_warn}"


def _shop_lines() -> list[str]:
    rows = []
    rows.append("```")
    rows.append(f"{'Crop':<12} {'Seed':>6} {'Grow':>6} {'Yield':>7}  Emoji")
    rows.append("─" * 44)
    for crop, d in CROPS.items():
        rows.append(
            f"{crop.capitalize():<12} {d['seed_cost']:>5}c {d['growth_mins']:>5}m "
            f"{d['sell_price']:>6}c  {d['emoji']}"
        )
    rows.append("```")
    return rows


# ── Random events ─────────────────────────────────────────────────────────────

def _roll_event(user: dict) -> str | None:
    if random.random() > EVENT_CHANCE:
        return None
    events = ["good_weather", "pest", "golden"]
    event  = random.choice(events)

    if event == "good_weather":
        for plot in user["plots"]:
            if _effective_state(plot) == "growing":
                if plot.get("grow_deadline"):
                    plot["grow_deadline"]  = max(_now(), plot["grow_deadline"]  - 60)
                if plot.get("water_deadline"):
                    plot["water_deadline"] = max(_now(), plot["water_deadline"] - 60)
        return "☀️ **Good Weather!** All crops grew 1 minute faster!"

    if event == "pest":
        growing = [i for i, p in enumerate(user["plots"]) if _effective_state(p) == "growing"]
        if not growing:
            return None
        idx = random.choice(growing)
        user["plots"][idx]["state"] = "infested"
        user["pending_pest"] = idx
        return (
            f"🐦 **Pest Infestation!** Crows landed on Plot {idx + 1}! "
            f"Use `/scare` or `th/scare` NOW or the crop is lost!"
        )

    if event == "golden":
        candidates = [
            i for i, p in enumerate(user["plots"])
            if _effective_state(p) in ("growing", "ready")
        ]
        if not candidates:
            return None
        idx = random.choice(candidates)
        user["plots"][idx]["golden"] = True
        return f"✨ **Golden Harvest!** Plot {idx + 1} will yield double coins on harvest!"

    return None


def _consume_pest(user: dict, scared: bool) -> str | None:
    """Resolve a pending pest. Returns outcome message or None."""
    pest_idx = user.get("pending_pest")
    if pest_idx is None:
        return None
    plot = user["plots"][pest_idx]
    user["pending_pest"] = None
    if scared:
        if plot.get("state") == "infested":
            plot["state"] = "growing"
        return f"👏 You scared the crows away from Plot {pest_idx + 1}! Crop saved!"
    else:
        crop_name = (plot.get("crop") or "crop").capitalize()
        plot["state"] = "dead"
        return f"💀 The crows devoured your **{crop_name}** in Plot {pest_idx + 1}! (You didn't scare them in time)"


# ── Context-aware reply helper ────────────────────────────────────────────────

async def _send(
    ctx: commands.Context,
    *,
    title: str,
    lines: list[str],
    color: int = 0x57F287,
    extra: str | None = None,
) -> None:
    """Send an embed for slash, plain text for prefix."""
    body = "\n".join(lines)
    if extra:
        body += f"\n\n{extra}"
    if ctx.interaction:
        embed = discord.Embed(title=title, description=body, color=color)
        embed.set_footer(text=f"🌻 Garden Game • {ctx.author.display_name}")
        await ctx.send(embed=embed)
    else:
        await ctx.reply(f"**{title}**\n{body}", mention_author=False)


async def _send_error(ctx: commands.Context, msg: str) -> None:
    prefix = ctx.prefix or "th/"
    if ctx.interaction:
        embed = discord.Embed(description=f"⚠️ {msg}", color=0xED4245)
        await ctx.send(embed=embed, ephemeral=True)
    else:
        await ctx.reply(f"⚠️ Context Error: {msg}", mention_author=False)


# ── Cog ───────────────────────────────────────────────────────────────────────

class GardenCog(commands.Cog, name="Garden"):
    """Text-based garden game."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _load(self, uid: int) -> dict[str, Any]:
        return _db.get(uid)

    def _save(self, uid: int, user: dict[str, Any]) -> None:
        _db.save(uid, user)

    def _pre_action(self, user: dict) -> str | None:
        """Called before active (state-changing) actions only.
        Passive commands (/garden, /shop, /inventory) must NOT call this —
        those should never trigger pest-loss so the player can inspect state first.
        Returns pest-loss message if the crop was eaten, or None.
        """
        return _consume_pest(user, scared=False)

    # ── /garden ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="garden", description="View the current state of your garden plots.")
    async def garden(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)
        # Passive command — do NOT consume pending pest here; player must see state first.

        pest_idx = user.get("pending_pest")
        lines = []
        for i, plot in enumerate(user["plots"]):
            lines.append(_plot_line(i, plot))

        lines.append("")
        lines.append(f"💰 **Coins:** {user['coins']:,}")

        extra = None
        if pest_idx is not None:
            extra = f"🐦 **Pest Alert!** Crows are on Plot {pest_idx + 1}! Use `/scare` or `th/scare` now, or your crop will be lost on your next action!"

        self._save(uid, user)
        await _send(ctx, title="🌻 Your Garden", lines=lines, extra=extra)

    # ── /shop ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="shop", description="Browse seeds available for purchase.")
    async def shop(self, ctx: commands.Context) -> None:
        # Passive command — no pest check.
        lines = _shop_lines()
        lines += [
            "",
            "Use `/buy <crop>` or `th/buy <crop>` to purchase seeds.",
        ]
        await _send(ctx, title="🏪 Seed Shop", lines=lines, color=0xFEE75C)

    # ── /buy ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="buy", description="Buy seeds from the shop.")
    @app_commands.describe(crop="Crop seed to buy", amount="How many to buy (default 1)")
    async def buy(self, ctx: commands.Context, crop: str, amount: int = 1) -> None:
        prefix = ctx.prefix or "th/"
        crop_key = _resolve_crop(crop)
        if not crop_key:
            await _send_error(ctx,
                f"Unknown crop `{crop}`. "
                f"Correct usage: `{prefix}buy <crop> [amount]` or `/buy [crop] [amount]`\n"
                f"Available: {', '.join(CROPS)}"
            )
            return
        if amount < 1:
            await _send_error(ctx, "Amount must be at least 1.")
            return

        uid   = ctx.author.id
        user  = self._load(uid)
        pest_loss = self._pre_action(user)

        info       = CROPS[crop_key]
        total_cost = info["seed_cost"] * amount
        if user["coins"] < total_cost:
            await _send_error(ctx,
                f"Not enough coins! Need **{total_cost:,}** but you have **{user['coins']:,}**."
            )
            self._save(uid, user)
            return

        user["coins"] -= total_cost
        seeds = user.setdefault("seeds", {})
        seeds[crop_key] = seeds.get(crop_key, 0) + amount

        event_msg = _roll_event(user)
        self._save(uid, user)

        em = info["emoji"]
        lines = [
            f"Bought **{amount}x {em} {crop_key.capitalize()} Seed{'s' if amount > 1 else ''}** for **{total_cost:,} coins**.",
            f"💰 Remaining coins: **{user['coins']:,}**",
            f"🌱 {crop_key.capitalize()} seeds in inventory: **{seeds[crop_key]}**",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="🛒 Purchase Complete", lines=lines, extra=event_msg)

    # ── /inventory (/inv) ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="Show your seeds and harvested crops.")
    async def inventory(self, ctx: commands.Context) -> None:
        # Passive command — no pest check.
        uid  = ctx.author.id
        user = self._load(uid)

        seeds     = user.get("seeds", {})
        harvested = user.get("harvested", {})

        lines = [f"💰 **Coins:** {user['coins']:,}", ""]
        lines.append("**🌱 Seeds:**")
        if seeds:
            for crop, qty in seeds.items():
                em = CROPS.get(crop, {}).get("emoji", "🌿")
                lines.append(f"  {em} {crop.capitalize()}: **{qty}**")
        else:
            lines.append("  *(none)*")

        lines.append("")
        lines.append("**🧺 Harvested Crops:**")
        if harvested:
            for crop, qty in harvested.items():
                em    = CROPS.get(crop, {}).get("emoji", "🌿")
                price = CROPS.get(crop, {}).get("sell_price", 0)
                lines.append(f"  {em} {crop.capitalize()}: **{qty}** (worth {price * qty:,} coins)")
        else:
            lines.append("  *(none)*")

        extra = None
        if user.get("pending_pest") is not None:
            extra = f"🐦 Pest alert active! Use `/scare` or `th/scare` before your next action!"

        self._save(uid, user)
        await _send(ctx, title="🎒 Inventory", lines=lines, extra=extra)

    # ── /plant ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="plant", description="Plant a seed into a specific plot.")
    @app_commands.describe(crop="Crop to plant", plot="Plot number (1–5)")
    async def plant(self, ctx: commands.Context, crop: str = "", plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not crop or not plot:
            await _send_error(ctx,
                f"Missing arguments. "
                f"Correct usage: `{prefix}plant <crop> <plot_number>` or `/plant [crop] [plot]`"
            )
            return

        crop_key = _resolve_crop(crop)
        if not crop_key:
            await _send_error(ctx, f"Unknown crop `{crop}`. Available: {', '.join(CROPS)}")
            return

        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number. Use 1–{NUM_PLOTS}.")
            return

        if not (1 <= plot_num <= NUM_PLOTS):
            await _send_error(ctx, f"Plot number must be between 1 and {NUM_PLOTS}.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        pest_loss = self._pre_action(user)

        seeds = user.get("seeds", {})
        if seeds.get(crop_key, 0) < 1:
            await _send_error(ctx,
                f"You don't have any **{crop_key.capitalize()} Seeds**. "
                f"Buy some with `{prefix}buy {crop_key}`."
            )
            self._save(uid, user)
            return

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        cur_state = _effective_state(plot_data)

        if cur_state not in ("empty", "dead"):
            await _send_error(ctx,
                f"Plot {plot_num} is not empty (state: **{cur_state}**). "
                f"Harvest or clear it first."
            )
            self._save(uid, user)
            return

        # Plant
        seeds[crop_key] -= 1
        if seeds[crop_key] <= 0:
            del seeds[crop_key]

        now          = _now()
        grow_secs    = CROPS[crop_key]["growth_mins"] * 60
        water_secs   = grow_secs * WATER_PCT

        user["plots"][plot_idx] = {
            "crop":           crop_key,
            "planted_at":     now,
            "watered":        False,
            "water_deadline": now + water_secs,
            "grow_deadline":  now + grow_secs,
            "state":          "growing",
            "golden":         False,
        }

        event_msg = _roll_event(user)
        self._save(uid, user)

        em   = CROPS[crop_key]["emoji"]
        info = CROPS[crop_key]
        lines = [
            f"Planted **{em} {crop_key.capitalize()}** in Plot {plot_num}!",
            f"⏱ Ready in **{_fmt_time(grow_secs)}**.",
            f"💧 Water it within **{_fmt_time(water_secs)}** or it dies.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="🌱 Planted!", lines=lines, color=0x57F287, extra=event_msg)

    # ── /water ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="water", description="Water a crop to keep it alive.")
    @app_commands.describe(plot="Plot number to water (1–5)")
    async def water(self, ctx: commands.Context, plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not plot:
            await _send_error(ctx,
                f"Correct usage: `{prefix}water <plot_number>` or `/water [plot]`"
            )
            return
        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number. Use 1–{NUM_PLOTS}.")
            return
        if not (1 <= plot_num <= NUM_PLOTS):
            await _send_error(ctx, f"Plot number must be between 1 and {NUM_PLOTS}.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        pest_loss = self._pre_action(user)

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        state     = _effective_state(plot_data)

        if state == "empty":
            await _send_error(ctx, f"Plot {plot_num} is empty — nothing to water!")
            self._save(uid, user)
            return
        if state == "dead":
            await _send_error(ctx, f"Plot {plot_num} is already dead. Clear it and replant.")
            self._save(uid, user)
            return
        if state == "ready":
            await _send_error(ctx, f"Plot {plot_num} is ready to harvest — no need to water!")
            self._save(uid, user)
            return
        if state == "infested":
            await _send_error(ctx,
                f"Plot {plot_num} is infested with crows! Scare them first with `{prefix}scare`."
            )
            self._save(uid, user)
            return
        if plot_data.get("watered"):
            await _send_error(ctx, f"Plot {plot_num} is already watered! 💧")
            self._save(uid, user)
            return

        plot_data["watered"] = True
        event_msg = _roll_event(user)
        self._save(uid, user)

        crop = plot_data["crop"]
        em   = CROPS.get(crop, {}).get("emoji", "🌿")
        grow_left = max(0, plot_data["grow_deadline"] - _now())
        lines = [
            f"Watered **{em} {crop.capitalize()}** in Plot {plot_num}! 💧",
            f"Ready in **{_fmt_time(grow_left)}**.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="💧 Watered!", lines=lines, extra=event_msg)

    # ── /harvest ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="harvest", description="Harvest a fully grown crop.")
    @app_commands.describe(plot="Plot number to harvest (1–5)")
    async def harvest(self, ctx: commands.Context, plot: str = "") -> None:
        prefix = ctx.prefix or "th/"
        if not plot:
            await _send_error(ctx,
                f"Correct usage: `{prefix}harvest <plot_number>` or `/harvest [plot]`"
            )
            return
        try:
            plot_num = int(plot)
        except ValueError:
            await _send_error(ctx, f"`{plot}` is not a valid plot number. Use 1–{NUM_PLOTS}.")
            return
        if not (1 <= plot_num <= NUM_PLOTS):
            await _send_error(ctx, f"Plot number must be between 1 and {NUM_PLOTS}.")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        pest_loss = self._pre_action(user)

        plot_idx  = plot_num - 1
        plot_data = user["plots"][plot_idx]
        state     = _effective_state(plot_data)

        if state != "ready":
            msgs = {
                "empty":    "Plot is empty — nothing to harvest.",
                "growing":  f"Crop isn't ready yet! Use `{prefix}garden` to see time remaining.",
                "dead":     "The crop is dead. Clear the plot and replant.",
                "infested": f"Crows are on this plot! Use `{prefix}scare` first.",
            }
            await _send_error(ctx, msgs.get(state, f"Plot {plot_num} is not ready."))
            self._save(uid, user)
            return

        crop   = plot_data["crop"]
        info   = CROPS.get(crop, {})
        em     = info.get("emoji", "🌿")
        golden = plot_data.get("golden", False)

        user["plots"][plot_idx] = copy.deepcopy(_EMPTY_PLOT)

        if golden:
            # Golden Harvest: pay out double coins immediately — no inventory step.
            gold_coins = info.get("sell_price", 0) * 2
            user["coins"] += gold_coins
            event_msg = _roll_event(user)
            self._save(uid, user)
            lines = [
                f"✨ **Golden Harvest!** Harvested **{em} {crop.capitalize()}** from Plot {plot_num}!",
                f"💰 Instantly earned **{gold_coins:,} coins** (2× value) — no selling needed!",
                f"New balance: **{user['coins']:,} coins**.",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="✨ Golden Harvest!", lines=lines, color=0xFFD700, extra=event_msg)
        else:
            # Normal harvest: add to inventory to sell later.
            harvested = user.setdefault("harvested", {})
            harvested[crop] = harvested.get(crop, 0) + 1
            sell_price = info.get("sell_price", 0)
            event_msg = _roll_event(user)
            self._save(uid, user)
            lines = [
                f"Harvested **{em} {crop.capitalize()}** from Plot {plot_num}!",
                f"Added to inventory: **1x {em} {crop.capitalize()}**.",
                f"💰 Sell it with `{prefix}sell {crop}` for **{sell_price:,} coins**.",
            ]
            if pest_loss:
                lines.append(f"\n{pest_loss}")
            await _send(ctx, title="🧺 Harvested!", lines=lines, color=0xFEE75C, extra=event_msg)

    # ── /sell ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="sell", description="Sell harvested crops for coins.")
    @app_commands.describe(crop="Crop to sell", amount="Amount to sell (default: all)")
    async def sell(self, ctx: commands.Context, crop: str = "", amount: Optional[str] = None) -> None:
        prefix = ctx.prefix or "th/"
        if not crop:
            await _send_error(ctx,
                f"Correct usage: `{prefix}sell <crop> [amount]` or `/sell [crop] [amount]`"
            )
            return

        crop_key = _resolve_crop(crop)
        if not crop_key:
            await _send_error(ctx, f"Unknown crop `{crop}`. Available: {', '.join(CROPS)}")
            return

        uid  = ctx.author.id
        user = self._load(uid)
        pest_loss = self._pre_action(user)

        harvested = user.setdefault("harvested", {})
        owned     = harvested.get(crop_key, 0)
        if owned == 0:
            await _send_error(ctx,
                f"You have no harvested **{crop_key.capitalize()}** to sell. "
                f"Grow and harvest some first!"
            )
            self._save(uid, user)
            return

        # Parse amount
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
                await _send_error(ctx,
                    f"You only have **{owned}x {crop_key.capitalize()}** but tried to sell {qty}."
                )
                self._save(uid, user)
                return

        info       = CROPS[crop_key]
        total_gain = info["sell_price"] * qty
        user["coins"] += total_gain
        harvested[crop_key] = owned - qty
        if harvested[crop_key] <= 0:
            del harvested[crop_key]

        event_msg = _roll_event(user)
        self._save(uid, user)

        em = info["emoji"]
        lines = [
            f"Sold **{qty}x {em} {crop_key.capitalize()}** for **{total_gain:,} coins**!",
            f"💰 New balance: **{user['coins']:,} coins**.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="💰 Sold!", lines=lines, color=0x57F287, extra=event_msg)

    # ── /wait ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="wait", description="Simulate time passing so your crops can grow.")
    @app_commands.describe(minutes="Minutes to fast-forward (max 60)")
    async def wait(self, ctx: commands.Context, minutes: float = 1.0) -> None:
        if minutes <= 0:
            await _send_error(ctx, "Minutes must be greater than 0.")
            return
        minutes = min(minutes, 60)
        skip    = minutes * 60

        uid  = ctx.author.id
        user = self._load(uid)
        pest_loss = self._pre_action(user)

        for plot in user["plots"]:
            if plot.get("grow_deadline"):
                plot["grow_deadline"]  -= skip
            if plot.get("water_deadline"):
                plot["water_deadline"] -= skip

        event_msg = _roll_event(user)
        self._save(uid, user)

        lines = [
            f"⏩ Fast-forwarded **{minutes:.1f} minute{'s' if minutes != 1 else ''}**.",
            "Use `th/garden` or `/garden` to check your plot status.",
        ]
        if pest_loss:
            lines.append(f"\n{pest_loss}")
        await _send(ctx, title="⏩ Time Skip", lines=lines, color=0x5865F2, extra=event_msg)

    # ── /scare ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="scare", description="Scare off crows from an infested plot!")
    async def scare(self, ctx: commands.Context) -> None:
        uid  = ctx.author.id
        user = self._load(uid)

        pest_idx = user.get("pending_pest")
        if pest_idx is None:
            lines = ["No crows to scare right now! Your garden is safe. 🕊️"]
            self._save(uid, user)
            await _send(ctx, title="🕊️ All Clear", lines=lines)
            return

        result = _consume_pest(user, scared=True)
        event_msg = _roll_event(user)
        self._save(uid, user)

        lines = [result or "Crows scared off!"]
        await _send(ctx, title="👏 Crows Scared!", lines=lines, color=0x57F287, extra=event_msg)

    # ── Error handlers ────────────────────────────────────────────────────────

    @buy.error
    @plant.error
    @water.error
    @harvest.error
    @sell.error
    @wait.error
    async def _arg_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            prefix = ctx.prefix or "th/"
            cmd    = ctx.command.name if ctx.command else "command"
            await _send_error(ctx,
                f"Invalid arguments. "
                f"Correct usage: `{prefix}{cmd}` or `/{cmd}` — "
                f"use `{prefix}garden` to view your garden."
            )
        else:
            raise error


# ── Welcome embed helper ──────────────────────────────────────────────────────

async def send_welcome(channel: discord.abc.Messageable, user: discord.User | discord.Member) -> None:
    """Send the new-player welcome card."""
    embed = discord.Embed(
        title="🌻 Welcome to the Garden Game!",
        description=(
            f"Hey {user.mention}! You've been given a fresh plot of land. "
            f"Time to grow something amazing.\n\n"
            f"**Your Starting Profile:**\n"
            f"💰 Coins: **100**\n"
            f"🌽 Corn Seeds: **2**\n"
            f"🌱 Plots: **5 empty**\n\n"
            f"**Quick Start:**\n"
            f"1. Plant your seeds → `/plant corn 1` or `th/plant corn 1`\n"
            f"2. Water before they die → `/water 1` or `th/water 1`\n"
            f"3. Check progress → `/garden` or `th/garden`\n"
            f"4. Harvest when ready → `/harvest 1` or `th/harvest 1`\n"
            f"5. Sell for coins → `/sell corn` or `th/sell corn`\n\n"
            f"💡 **Both `/commands` and `th/commands` work identically!**\n"
            f"Run `/shop` or `th/shop` to see all available crops."
        ),
        color=0x57F287,
    )
    embed.set_footer(text="🌻 Garden Game • Good luck, farmer!")
    await channel.send(embed=embed)


# ── Cog setup ─────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GardenCog(bot))
