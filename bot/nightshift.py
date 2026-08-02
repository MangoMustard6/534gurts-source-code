"""Procedural Discord horror minigame.

The module intentionally keeps every frame in memory.  Pillow paints the
scene, and the resulting PNG is wrapped in BytesIO for Discord upload.

Load with:
    from bot.nightshift import setup
    await setup(bot)
"""

from __future__ import annotations

import asyncio
import io
import math
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageEnhance

if TYPE_CHECKING:
    from discord import Interaction, Message


WIDTH, HEIGHT = 900, 500
HOUR_SECONDS = 20.0
MAX_POWER = 100.0
DIFFICULTIES = {
    "easy": {
        "label": "Easy",
        "drain": 0.55,
        "threat_chance": 0.45,
        "description": "Slower battery drain and quieter animatronics.",
    },
    "normal": {
        "label": "Normal",
        "drain": 1.0,
        "threat_chance": 1.0,
        "description": "The intended night shift experience.",
    },
    "hard": {
        "label": "Hard",
        "drain": 1.55,
        "threat_chance": 1.8,
        "description": "Faster battery drain and more active animatronics.",
    },
}


def _frame_buffer(image: Image.Image) -> discord.File:
    """Encode a rendered frame without touching the filesystem."""
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    stream.seek(0)
    return discord.File(stream, filename="nightshift.png")


def _base_scene() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), (4, 7, 10))
    return image, ImageDraw.Draw(image)


def _scanline_noise(image: Image.Image, seed: int, strength: int = 30) -> Image.Image:
    """Apply green night vision, scanlines, and deterministic static noise."""
    rng = random.Random(seed)
    image = ImageEnhance.Contrast(image).enhance(1.35)
    pixels = image.load()
    for y in range(HEIGHT):
        line_scale = 0.78 if y % 3 == 0 else 1.0
        for x in range(WIDTH):
            r, g, b = pixels[x, y]
            noise = rng.randint(-strength, strength)
            pixels[x, y] = (
                max(0, min(255, int((r * 0.20 + noise) * line_scale))),
                max(0, min(255, int((g * 1.10 + noise * 2) * line_scale))),
                max(0, min(255, int((b * 0.25 + noise) * line_scale))),
            )
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(0, HEIGHT, 4):
        draw.line((0, y, WIDTH, y), fill=(0, 0, 0, 55), width=1)
    return image


def _draw_eye(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 8) -> None:
    draw.ellipse((x - size, y - size // 2, x + size, y + size // 2), fill=(255, 245, 130))
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 35, 25))


def _draw_threat(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    scale: float,
    color: tuple[int, int, int] = (8, 10, 11),
    eyes_offset: int = 0,
) -> None:
    """Paint a chunky animatronic silhouette from primitive geometry."""
    width = max(20, int(90 * scale))
    height = max(35, int(190 * scale))
    draw.ellipse((x - width // 2, y - height, x + width // 2, y - height // 2), fill=color)
    draw.rounded_rectangle(
        (x - width // 2, y - height // 2, x + width // 2, y + height // 3),
        radius=max(4, int(12 * scale)),
        fill=color,
    )
    draw.polygon(
        [(x - width // 3, y - height), (x - width // 2, y - height - int(35 * scale)),
         (x - width // 8, y - height + int(8 * scale))],
        fill=color,
    )
    draw.polygon(
        [(x + width // 3, y - height), (x + width // 2, y - height - int(35 * scale)),
         (x + width // 8, y - height + int(8 * scale))],
        fill=color,
    )
    eye_y = y - int(height * 0.72)
    eye_x = x + eyes_offset
    _draw_eye(draw, eye_x - max(4, int(13 * scale)), eye_y, max(3, int(7 * scale)))
    _draw_eye(draw, eye_x + max(4, int(13 * scale)), eye_y, max(3, int(7 * scale)))
    draw.arc(
        (x - width // 3, y - int(height * 0.55), x + width // 3, y - int(height * 0.20)),
        10, 170, fill=(90, 20, 20), width=max(1, int(4 * scale)),
    )


def _draw_label(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], fill=(175, 255, 190)) -> None:
    draw.text(xy, text, fill=fill, stroke_width=1, stroke_fill=(0, 25, 10))


def render_office(left_closed: bool, right_closed: bool, power: float, hour: int, seed: int) -> Image.Image:
    """Render the office, desk, two doorways, and a live power gauge."""
    image, draw = _base_scene()
    rng = random.Random(seed)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(13, 16, 20))
    draw.rectangle((70, 50, 830, 405), fill=(25, 27, 31), outline=(75, 78, 82), width=4)
    draw.line((450, 50, 450, 405), fill=(7, 8, 10), width=5)

    # Doorway recesses.
    for left, closed in ((True, left_closed), (False, right_closed)):
        x0, x1 = (85, 265) if left else (635, 815)
        draw.rectangle((x0, 110, x1, 405), fill=(2, 3, 4), outline=(95, 97, 99), width=5)
        if closed:
            draw.rectangle((x0 + 12, 122, x1 - 12, 405), fill=(48, 51, 53), outline=(117, 120, 120), width=3)
            for x in range(x0 + 25, x1 - 10, 25):
                draw.line((x, 125, x, 400), fill=(30, 32, 34), width=3)
            draw.rectangle((x0 + 20, 155, x1 - 20, 177), fill=(93, 26, 25))
            _draw_label(draw, "LOCKED", (x0 + 55, 160), (255, 215, 150))
        else:
            draw.line((x0, 110, x0, 405), fill=(145, 145, 140), width=7)
            draw.line((x1, 110, x1, 405), fill=(145, 145, 140), width=7)
            for _ in range(14):
                px = rng.randint(x0 + 8, x1 - 8)
                py = rng.randint(125, 395)
                draw.point((px, py), fill=(40, 45, 48))
            _draw_label(draw, "OPEN", (x0 + 62, 385), (115, 135, 125))

    # Desk, monitors, fan, and control lights.
    draw.polygon([(180, 405), (720, 405), (790, 500), (110, 500)], fill=(37, 29, 25), outline=(110, 78, 50))
    draw.rectangle((320, 300, 580, 410), fill=(10, 12, 14), outline=(118, 121, 122), width=4)
    draw.rectangle((340, 320, 560, 392), fill=(19, 47, 35), outline=(76, 130, 89))
    draw.line((350, 350, 520, 345), fill=(112, 235, 130), width=2)
    draw.line((350, 360, 480, 372), fill=(70, 172, 98), width=2)
    draw.ellipse((650, 335, 715, 400), outline=(120, 122, 115), width=4)
    draw.line((682, 367, 711, 345), fill=(145, 145, 135), width=3)
    draw.line((682, 367, 655, 345), fill=(145, 145, 135), width=3)
    draw.ellipse((677, 362, 688, 373), fill=(180, 175, 145))
    draw.ellipse((205, 432, 227, 454), fill=(220, 35, 20) if left_closed else (35, 210, 70))
    draw.ellipse((675, 432, 697, 454), fill=(220, 35, 20) if right_closed else (35, 210, 70))

    # Power gauge.
    gauge_x, gauge_y, gauge_w = 25, 25, 190
    draw.rectangle((gauge_x, gauge_y, gauge_x + gauge_w, gauge_y + 26), fill=(10, 13, 15), outline=(160, 165, 160), width=2)
    fill_w = int(gauge_w * max(0.0, power) / MAX_POWER)
    gauge_color = (50, 215, 85) if power > 35 else (230, 170, 35) if power > 15 else (225, 40, 30)
    draw.rectangle((gauge_x + 3, gauge_y + 3, gauge_x + 3 + fill_w, gauge_y + 23), fill=gauge_color)
    _draw_label(draw, f"POWER {max(0, power):05.1f}%", (25, 58), gauge_color)
    _draw_label(draw, f"{12 + hour if hour < 6 else 6} AM", (770, 25), (225, 225, 195))
    _draw_label(draw, "OFFICE // SECURITY DESK", (340, 76), (160, 165, 165))
    return ImageEnhance.Brightness(image).enhance(0.86 if power > 10 else 0.55)


def render_camera(camera: int, threat_positions: dict[str, int], hour: int, power: float, seed: int) -> Image.Image:
    """Render a green-tinted camera feed with perspective, static, and threats."""
    image, draw = _base_scene()
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(16, 29, 21))
    if camera == 1:  # stage
        draw.rectangle((70, 80, 830, 430), fill=(32, 38, 34), outline=(94, 145, 94), width=5)
        draw.rectangle((105, 100, 795, 210), fill=(26, 30, 27), outline=(80, 116, 78), width=3)
        for x in range(140, 780, 50):
            draw.line((x, 105, x - 35, 205), fill=(55, 77, 55), width=2)
        draw.rectangle((125, 295, 775, 430), fill=(23, 28, 25))
        draw.line((125, 295, 775, 295), fill=(88, 127, 82), width=4)
        if threat_positions.get("bear", 0) == 0:
            _draw_threat(draw, 450, 340, 0.42)
    elif camera == 2:  # hallway
        draw.polygon([(250, 420), (650, 420), (535, 120), (365, 120)], fill=(36, 43, 36), outline=(90, 130, 86))
        draw.polygon([(0, 500), (900, 500), (535, 120), (365, 120)], fill=(18, 27, 20))
        for x in (80, 180, 720, 820):
            draw.line((450, 120, x, 480), fill=(63, 98, 65), width=3)
        _draw_label(draw, "HALLWAY // CAM 2", (35, 440), (170, 240, 170))
        if threat_positions.get("rabbit", 0) in (1, 2):
            _draw_threat(draw, 450, 365, 0.60 if threat_positions["rabbit"] == 1 else 0.85)
    else:  # corner / close feed
        draw.rectangle((110, 90, 790, 425), fill=(23, 31, 25), outline=(88, 130, 86), width=5)
        draw.rectangle((160, 120, 300, 410), fill=(13, 19, 15))
        draw.line((300, 120, 500, 420), fill=(80, 115, 76), width=4)
        draw.line((700, 120, 500, 420), fill=(80, 115, 76), width=4)
        if threat_positions.get("bear", 0) >= 1:
            _draw_threat(draw, 480, 430, 1.15 if threat_positions["bear"] == 1 else 1.6, eyes_offset=8)
        if threat_positions.get("rabbit", 0) >= 2:
            _draw_threat(draw, 700, 420, 0.85, color=(12, 14, 13), eyes_offset=-4)
    image = _scanline_noise(image, seed + camera * 101 + hour * 17, strength=26)
    overlay = ImageDraw.Draw(image, "RGBA")
    overlay.rectangle((18, 18, 300, 55), fill=(0, 15, 4, 155))
    _draw_label(overlay, f"CAM 0{camera} // SIGNAL {max(1, int(power))}%", (30, 28))
    return image


def render_jumpscare(seed: int, progress: float = 1.0) -> Image.Image:
    """Paint a full-screen, frame-shifted animatronic jumpscare."""
    image = Image.new("RGB", (WIDTH, HEIGHT), (95, 3, 5))
    draw = ImageDraw.Draw(image)
    rng = random.Random(seed)
    shake = rng.randint(-14, 14)
    cx, cy = WIDTH // 2 + shake, HEIGHT // 2
    _draw_threat(draw, cx, cy + 105, 2.25, color=(5, 4, 4), eyes_offset=rng.randint(-12, 12))
    draw.ellipse((cx - 112, cy - 94, cx - 44, cy - 52), fill=(255, 245, 170))
    draw.ellipse((cx + 44, cy - 94, cx + 112, cy - 52), fill=(255, 245, 170))
    draw.ellipse((cx - 92, cy - 86, cx - 62, cy - 59), fill=(255, 0, 0))
    draw.ellipse((cx + 62, cy - 86, cx + 92, cy - 59), fill=(255, 0, 0))
    for _ in range(80):
        x = rng.randrange(WIDTH)
        y = rng.randrange(HEIGHT)
        draw.line((x, y, x + rng.randint(-35, 35), y + rng.randint(-8, 8)), fill=(210, rng.randint(0, 30), 20), width=2)
    draw.text((WIDTH // 2 - 190, 25), "YOU DIDN'T MAKE IT", fill=(255, 225, 210), stroke_width=3, stroke_fill=(40, 0, 0))
    return ImageEnhance.Contrast(image).enhance(1.0 + progress * 0.7)


@dataclass
class NightState:
    user_id: int
    channel_id: int
    difficulty: str = "normal"
    message: Message | None = None
    hour: int = 0
    started_at: float = field(default_factory=time.monotonic)
    power: float = MAX_POWER
    camera: int | None = None
    left_closed: bool = False
    right_closed: bool = False
    threats: dict[str, int] = field(default_factory=lambda: {"bear": 0, "rabbit": 0})
    ended: bool = False
    result: str = ""
    seed: int = field(default_factory=lambda: random.randrange(1_000_000_000))

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at


class NightShiftView(discord.ui.View):
    def __init__(self, cog: "NightShiftCog", state: NightState):
        super().__init__(timeout=None)
        self.cog = cog
        self.state = state
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = self.state.ended

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message("This night shift belongs to another player.", ephemeral=True)
            return False
        if self.state.ended:
            await interaction.response.send_message("This shift has ended. Start a new `/nightshift`.", ephemeral=True)
            return False
        return True

    async def _action(self, interaction: discord.Interaction, camera: int | None = None, left: bool = False, right: bool = False) -> None:
        if camera is not None:
            self.state.camera = camera
        if left:
            self.state.left_closed = not self.state.left_closed
        if right:
            self.state.right_closed = not self.state.right_closed
        self._sync_buttons()
        embed, file = self.cog.build_message(self.state)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Cam 1", emoji="🎥", style=discord.ButtonStyle.secondary, row=0)
    async def cam1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._action(interaction, camera=1)

    @discord.ui.button(label="Cam 2", emoji="🎥", style=discord.ButtonStyle.secondary, row=0)
    async def cam2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._action(interaction, camera=2)

    @discord.ui.button(label="Cam 3", emoji="🎥", style=discord.ButtonStyle.secondary, row=0)
    async def cam3(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._action(interaction, camera=3)

    @discord.ui.button(label="Office", emoji="🖥️", style=discord.ButtonStyle.primary, row=0)
    async def office(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.state.camera = None
        await self._action(interaction, camera=None)

    @discord.ui.button(label="Toggle Left Door", emoji="🚪", style=discord.ButtonStyle.danger, row=1)
    async def left_door(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._action(interaction, left=True)

    @discord.ui.button(label="Toggle Right Door", emoji="🚪", style=discord.ButtonStyle.danger, row=1)
    async def right_door(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._action(interaction, right=True)


class NightShiftCog(commands.Cog):
    """Interactive, procedural FNAF-inspired night shift game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: dict[int, NightState] = {}
        self.tick_games.start()

    def cog_unload(self) -> None:
        self.tick_games.cancel()

    def build_message(self, state: NightState) -> tuple[discord.Embed, discord.File]:
        if state.result == "jumpscare":
            image = render_jumpscare(state.seed + int(state.elapsed * 20), 1.0)
            title = "NIGHT SHIFT // CAUGHT"
            description = "The office lights died. Something was already inside."
        elif state.result == "won":
            image = render_office(False, False, state.power, 6, state.seed)
            title = "NIGHT SHIFT // 6 AM"
            description = "The doors unlock. Dawn has finally arrived."
        elif state.camera is None:
            image = render_office(state.left_closed, state.right_closed, state.power, state.hour, state.seed)
            title = "NIGHT SHIFT // OFFICE"
            description = "Watch the doors. Save your power. Do not trust the cameras."
        else:
            image = render_camera(state.camera, state.threats, state.hour, state.power, state.seed)
            title = f"NIGHT SHIFT // CAMERA 0{state.camera}"
            description = "The signal hisses. Movement is not always visible."
        embed = discord.Embed(title=title, description=description, color=0x8c1616 if state.result else 0x2d6b3b)
        embed.add_field(name="Power", value=f"{max(0, state.power):.1f}%", inline=True)
        embed.add_field(name="Time", value="6 AM" if state.result == "won" else f"{12 + state.hour if state.hour < 6 else 6} AM", inline=True)
        difficulty = DIFFICULTIES[state.difficulty]
        embed.add_field(name="Difficulty", value=difficulty["label"], inline=True)
        if not state.ended:
            embed.add_field(name="Doors", value=f"L {'SHUT' if state.left_closed else 'OPEN'} · R {'SHUT' if state.right_closed else 'OPEN'}", inline=False)
        embed.set_image(url="attachment://nightshift.png")
        return embed, _frame_buffer(image)

    @commands.hybrid_command(name="nightshift", description="Survive a procedural animatronic night shift.")
    @app_commands.describe(difficulty="Choose how much battery pressure and monster activity you want.")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy — slower drain, fewer monster moves", value="easy"),
        app_commands.Choice(name="Normal — default difficulty", value="normal"),
        app_commands.Choice(name="Hard — faster drain, more monster moves", value="hard"),
    ])
    async def nightshift(self, ctx: commands.Context, difficulty: str = "normal") -> None:
        """Start a procedural animatronic night shift.

        Prefix usage: ``th/nightshift [easy|normal|hard]``.
        """
        difficulty = difficulty.strip().lower()
        if difficulty not in DIFFICULTIES:
            valid = "`, `".join(DIFFICULTIES)
            message = f"Choose a difficulty: `{valid}`. Normal is the default."
            if ctx.interaction:
                await ctx.interaction.response.send_message(message, ephemeral=True)
            else:
                await ctx.reply(message, mention_author=False)
            return
        channel_id = ctx.channel.id
        old = self.games.get(channel_id)
        if old and not old.ended:
            if ctx.interaction:
                await ctx.interaction.response.send_message(
                    "A night shift is already running in this channel.", ephemeral=True
                )
            else:
                await ctx.reply("A night shift is already running in this channel.", mention_author=False)
            return
        state = NightState(user_id=ctx.author.id, channel_id=channel_id, difficulty=difficulty)
        view = NightShiftView(self, state)
        embed, file = self.build_message(state)
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, file=file, view=view)
            state.message = await ctx.interaction.original_response()
        else:
            state.message = await ctx.send(embed=embed, file=file, view=view)
        self.games[channel_id] = state

    @tasks.loop(seconds=1.0)
    async def tick_games(self) -> None:
        for channel_id, state in list(self.games.items()):
            if state.ended or state.message is None:
                continue
            state.hour = min(6, int(state.elapsed / HOUR_SECONDS))
            if state.hour >= 6:
                state.ended = True
                state.result = "won"
                await self._refresh(state)
                continue

            tuning = DIFFICULTIES[state.difficulty]
            camera_cost = 0.055 if state.camera is not None else 0.0
            door_cost = (0.10 if state.left_closed else 0.0) + (0.10 if state.right_closed else 0.0)
            state.power -= (0.12 + camera_cost + door_cost) * tuning["drain"]
            self._move_threats(state)
            if state.power <= 0:
                state.power = 0
                if any(position >= 2 for position in state.threats.values()):
                    state.ended = True
                    state.result = "jumpscare"
            if (state.threats["bear"] >= 3 and not state.left_closed) or (
                state.threats["rabbit"] >= 3 and not state.right_closed
            ):
                state.ended = True
                state.result = "jumpscare"
            await self._refresh(state)

    @tick_games.before_loop
    async def before_tick_games(self) -> None:
        await self.bot.wait_until_ready()

    def _move_threats(self, state: NightState) -> None:
        rng = random.Random(state.seed + int(state.elapsed))
        tuning = DIFFICULTIES[state.difficulty]
        for name, position in state.threats.items():
            chance = (0.055 + state.hour * 0.012) * tuning["threat_chance"]
            if rng.random() < chance:
                state.threats[name] = min(3, position + 1)
            elif rng.random() < 0.025 / tuning["threat_chance"] and position > 0:
                state.threats[name] = position - 1

    async def _refresh(self, state: NightState) -> None:
        if state.message is None:
            return
        view = NightShiftView(self, state)
        embed, file = self.build_message(state)
        try:
            await state.message.edit(embed=embed, attachments=[file], view=view)
        except (discord.NotFound, discord.HTTPException):
            state.ended = True


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NightShiftCog(bot))