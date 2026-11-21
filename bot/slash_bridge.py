"""Slash versions of the prefix commands.

Prefix commands stop working in January 2027, so every prefix-only command also
gets a slash command.  Nothing is duplicated: each slash command is generated
from the live prefix command and calls the *same callback* through a context
built from the interaction (``commands.Context.from_interaction``), the same
way ``audio_cog`` already does.

    /effects trim args:5 15 file:<upload>   ->   th>trim 5 15  (+ attachment)

How a prefix command becomes a slash command
--------------------------------------------
* Commands are grouped (``/effects``, ``/edit``, ``/sound`` ...) so the bot stays
  far below Discord's 100 global command limit; ``GROUPS`` lists the layout.
  Prefix commands that are in no group land in ``/misc`` automatically.
* Parameters come from the callback's signature: ``str``/``int``/``float``/
  ``bool``/``Member``/``User``/``TextChannel`` map to native slash options,
  ``*args`` becomes one text option, anything else falls back to text.
* Commands that read attachments get ``file`` (and ``file2`` where the command
  reads a second one).  Replying to a message is not possible in slash, so a
  URL in ``args`` or an uploaded ``file`` is used instead.
* Before running, the same global/cog/command checks as the prefix command
  (blocks, owner-only, heavy-command limits ...) are evaluated.
* Errors go through the bot's normal ``on_command_error`` handler.

Commands that already have a slash form (hybrid commands, ``/export``,
``/audio`` ...) are skipped.  A command that cannot be bridged is logged and
skipped; it never prevents the bot from starting.
"""

from __future__ import annotations

import inspect
import shlex
import types
import typing
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import prefix_notice

TAG = "[slash-bridge]"
MAX_SUBCOMMANDS = 25        # Discord: subcommands per group
MAX_TOP_LEVEL = 100         # Discord: global slash commands

# group name -> (description, [prefix command qualified names])
GROUPS: dict[str, tuple[str, list[str]]] = {
    "effects": (
        "Visual effects, previews and pipelines",
        [
            "invlum", "pipetest", "preview1280", "oppositep1280",
            "preview1280with640x360resize", "preview1280what", "ihtxffmpeg",
            "ffmpeg", "ffmpegprocess", "huehsv", "swirl", "freakzingatesteffect",
            "tvsim", "folkvalley", "ihtx", "nparisonffmpeg", "veb", "mirror",
            "random", "randomlist", "undo", "lexg",
        ],
    ),
    "library": (
        "Effect presets and the user effect library",
        [
            "presets", "listeffects", "submiteffect", "deleteeffect",
            "guesseffect", "effectconfig",
        ],
    ),
    "edit": (
        "Trim, join, resize and other media editing",
        [
            "trim", "stretch_to_length", "repeat", "concatenate", "join",
            "addsource", "png2lut", "lut2png", "syncaudio", "crop", "resize",
            "klaskycsupo", "klaskysource",
        ],
    ),
    "sound": (
        "Audio effects, pitch tools and vocoders",
        [
            "multipitch", "pitchtransition", "soundstretchmultipitch", "ihtxsap",
            "multipitch_bungee", "autotune", "vocoder", "sidechaingate_vocoder",
            "ytpmvscan", "bytebeat",
        ],
    ),
    "files": (
        "Download and upload media",
        ["youtubedownload", "download", "catbox", "uguu"],
    ),
    "fun": (
        "Fun commands",
        [
            "funfact", "8ball", "coinflip", "roll", "rps", "choose", "rate",
            "slots", "math",
        ],
    ),
    "games": (
        "Games, levels and leaderboards",
        [
            "hangman", "blackjack", "tictactoe", "numguess", "scramble",
            "typerace", "mathquiz", "trivia", "level", "leaderboard",
        ],
    ),
    "bot": (
        "Help, status and AI chat",
        ["ihtxhelp", "uptime", "invite", "chat", "clearchat", "usage"],
    ),
    "blocks": (
        "Block users, channels and keywords (owner)",
        [
            "block", "unblock", "blockuser", "unblockuser", "blockchannel",
            "unblockchannel", "keywordblock", "keywordblockremove",
            "keywordblockmsg",
        ],
    ),
    "autoreply": (
        "Configure auto replies (owner)",
        [
            "autoreply", "removeautoreply", "removearmentions", "autoreplies",
            "autoreply2", "autoreply2list", "removear2mentions", "blockarchannel",
        ],
    ),
    "owner": (
        "Owner and admin tools",
        [
            "setactivity", "sendmsg", "set", "listservers", "listchannels",
            "syncslash", "setlimit", "resetlimit", "say", "sayembed", "bash",
        ],
    ),
    "tag": (
        "Create and use tags",
        [
            "tag", "tag create", "tag edit", "tag delete", "tag forceremove",
            "tag info", "tag list", "tag random", "tag search", "tag raw",
            "tag alias", "tag unalias", "tag transfer", "tag rename",
            "tag stats", "tag perms", "tag help",
        ],
    ),
}

# Prefix commands that must not be bridged (already have a slash form, or are
# only aliases of something that does).
SKIP: set[str] = {"audio", "put", "replace", "export", "t", "convert"}

# Slash name overrides (prefix qualified name -> slash subcommand name).
RENAME: dict[str, str] = {"tag": "show"}

# Source markers meaning "this command reads a file the user attached".
_FILE_MARKERS = ("attachments", "message.reference", "_resolve_media_source", "_groq_media_content")
# ...and a marker for commands that read a second attached file.
_SECOND_FILE_MARKERS = ("attachments[1]",)

_ARGS_DESC = "Arguments, exactly as you would type them after the prefix command (see /bot ihtxhelp)"
_FILE_DESC = "Media file to use (or put a URL in args)"
_FILE2_DESC = "Second media file"


# ───────────────────────────────────────────────────────────────────────────
# Slash-side message tweaks
# ───────────────────────────────────────────────────────────────────────────

class _SlashMessage(discord.Message):
    """Stand-in class for the synthetic message of a slash invocation.

    discord.py builds a message object for slash contexts, but it does not
    exist on Discord's side.  Prefix commands that react to or delete the
    invoking message would fail (or wrongly report an error), so those calls
    are no-ops here.  ``__slots__`` stays empty so the instance's class can be
    swapped in place.
    """

    __slots__ = ()

    async def add_reaction(self, emoji) -> None:  # noqa: D401
        return None

    async def remove_reaction(self, emoji, member) -> None:
        return None

    async def clear_reactions(self) -> None:
        return None

    async def delete(self, *, delay: Optional[float] = None) -> None:
        return None


# ───────────────────────────────────────────────────────────────────────────
# Signature -> slash parameters
# ───────────────────────────────────────────────────────────────────────────

_NATIVE = (str, int, float, bool)
_DISCORD_TYPES = (
    discord.Member, discord.User, discord.Role, discord.TextChannel,
    discord.VoiceChannel, discord.Attachment,
)


def _slash_type(annotation: Any) -> Any:
    """Map a prefix-command annotation to something slash options support."""
    if annotation is inspect.Parameter.empty:
        return str
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, getattr(types, "UnionType", typing.Union)):
        inner = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _slash_type(inner[0]) if len(inner) == 1 else str
    if origin is typing.Literal:
        return annotation
    if annotation in _NATIVE:
        return annotation
    if isinstance(annotation, type) and issubclass(annotation, _DISCORD_TYPES):
        return annotation
    return str


class _Spec:
    """One slash option derived from one prefix-command parameter."""

    __slots__ = ("name", "slash", "type", "required", "default", "kind", "description")

    def __init__(self, name, type_, required, default, kind, description):
        self.name = name          # the prefix command's parameter name
        self.slash = name         # the option name users see (may be tidied)
        self.type = type_
        self.required = required
        self.default = default
        self.kind = kind
        self.description = description


def _clip(text: str, limit: int = 100) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _describe_param(name: str, kind) -> str:
    if kind is inspect.Parameter.VAR_POSITIONAL:
        return _ARGS_DESC
    if name == "args":
        return _ARGS_DESC
    return _clip(name.replace("_", " ").capitalize())


def _command_source(cmd: commands.Command) -> str:
    try:
        return inspect.getsource(cmd.callback)
    except (OSError, TypeError):
        return ""


def _specs_for(cmd: commands.Command) -> list[_Spec]:
    """Slash options for ``cmd``: required ones first, as Discord requires."""
    specs: list[_Spec] = []
    for name, param in cmd.clean_params.items():
        required = param.default is inspect.Parameter.empty
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            specs.append(_Spec(name, str, False, None, param.kind, _ARGS_DESC))
            continue
        ann = param.annotation
        origin = typing.get_origin(ann)
        if origin in (typing.Union, getattr(types, "UnionType", typing.Union)) and type(None) in typing.get_args(ann):
            required = False
        default = None if required or param.default is inspect.Parameter.empty else param.default
        specs.append(_Spec(name, _slash_type(ann), required, default, param.kind,
                           _describe_param(name, param.kind)))

    source = _command_source(cmd)
    if any(m in source for m in _FILE_MARKERS):
        taken = {s.name for s in specs}
        file_name = "file" if "file" not in taken else "upload"
        specs.append(_Spec(file_name, discord.Attachment, False, None, None, _FILE_DESC))
        if any(m in source for m in _SECOND_FILE_MARKERS):
            specs.append(_Spec(file_name + "2", discord.Attachment, False, None, None, _FILE2_DESC))

    # Tidy option names such as ``target_raw`` -> ``target`` (never on a clash).
    used = {s.name for s in specs}
    for s in specs:
        for suffix in ("_raw", "_str"):
            short = s.name[: -len(suffix)] if s.name.endswith(suffix) else ""
            if short and short not in used:
                s.slash = short
                used.add(short)
                break

    specs.sort(key=lambda s: not s.required)  # stable: keeps relative order
    return specs


def _description_for(cmd: commands.Command) -> str:
    doc = (cmd.help or cmd.description or cmd.brief or "").strip()
    first = doc.splitlines()[0].strip() if doc else ""
    return _clip(first or f"Run the {cmd.qualified_name} command")


# ───────────────────────────────────────────────────────────────────────────
# Running a prefix command from a slash interaction
# ───────────────────────────────────────────────────────────────────────────

def _split_var_args(text: Optional[str]) -> list[str]:
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:  # unbalanced quotes
        return text.split()


def _call_arguments(cmd: commands.Command, specs: list[_Spec], values: dict[str, Any]):
    """Build ``(args, kwargs)`` for ``ctx.invoke`` from the slash option values."""
    positional: list[Any] = []
    var_args: list[str] = []
    kwargs: dict[str, Any] = {}
    slash_name = {s.name: s.slash for s in specs}

    for name, param in cmd.clean_params.items():
        value = values.get(slash_name.get(name, name))
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            var_args = _split_var_args(value)
            continue
        if value is None:  # option left out: fall back to the command's own default
            value = None if param.default is inspect.Parameter.empty else param.default
        if param.kind is inspect.Parameter.KEYWORD_ONLY:
            kwargs[name] = value
        else:  # always valid positionally, and keeps order when ``*args`` follows
            positional.append(value)
    return positional + var_args, kwargs


async def _run(
    bot: commands.Bot,
    cmd: commands.Command,
    specs: list[_Spec],
    path: str,
    interaction: discord.Interaction,
    values: dict[str, Any],
) -> None:
    ctx = await commands.Context.from_interaction(interaction)
    ctx.command = cmd  # the prefix command, so checks and handlers see its real name
    try:
        ctx.message.__class__ = _SlashMessage
    except TypeError:  # layout mismatch on an unexpected discord.py version
        pass

    # Same checks as the prefix command: blocks, owner-only, heavy limits ...
    try:
        allowed = await cmd.can_run(ctx)
    except commands.CommandError:
        allowed = False
    except Exception as exc:
        print(f"{TAG} check error in {path}: {type(exc).__name__}: {exc}")
        allowed = False
    if not allowed:
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ You can't use this command here.", ephemeral=True)
        return

    if not interaction.response.is_done():
        await ctx.defer()

    try:
        # The bot's before_invoke hook (thread access for prefix commands).
        before = getattr(bot, "_before_invoke", None)
        if before is not None:
            await before(ctx)
        args, kwargs = _call_arguments(cmd, specs, values)
        await ctx.invoke(cmd, *args, **kwargs)
    except Exception as exc:
        # Reuse the bot's own error formatting (on_command_error).
        bot.dispatch("command_error", ctx, commands.CommandInvokeError(exc))


# ───────────────────────────────────────────────────────────────────────────
# Building the app commands
# ───────────────────────────────────────────────────────────────────────────

def _build_subcommand(
    bot: commands.Bot, cmd: commands.Command, slash_name: str, path: str
) -> app_commands.Command:
    specs = _specs_for(cmd)

    async def callback(interaction: discord.Interaction, **values: Any) -> None:
        await _run(bot, cmd, specs, path, interaction, values)

    params = [inspect.Parameter("interaction", inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                annotation=discord.Interaction)]
    for s in specs:
        if s.required:
            params.append(inspect.Parameter(s.slash, inspect.Parameter.KEYWORD_ONLY, annotation=s.type))
        else:
            params.append(inspect.Parameter(s.slash, inspect.Parameter.KEYWORD_ONLY,
                                            annotation=typing.Optional[s.type], default=None))
    callback.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    callback.__name__ = callback.__qualname__ = f"slash_{slash_name}"
    callback.__discord_app_commands_param_description__ = {s.slash: s.description for s in specs}  # type: ignore[attr-defined]

    return app_commands.Command(name=slash_name, description=_description_for(cmd), callback=callback)


def _lookup(bot: commands.Bot, qualified: str) -> Optional[commands.Command]:
    return bot.get_command(qualified)


def register(bot: commands.Bot) -> dict[str, str]:
    """Add slash groups for every bridgeable prefix command to ``bot.tree``.

    Safe to call more than once.  Returns ``{prefix command: slash path}`` and
    also records it in :data:`bot.prefix_notice.SLASH_PATHS` so the shutdown
    notice can point users at the right slash command.
    """
    if getattr(bot, "_slash_bridge_registered", False):
        return dict(prefix_notice.SLASH_PATHS)

    existing = {c.name for c in bot.tree.get_commands()}
    assigned: set[str] = set()
    plan: dict[str, tuple[str, list[str]]] = {g: (d, list(n)) for g, (d, n) in GROUPS.items()}

    # Prefix commands nobody listed still get a slash form, under /misc.
    listed = {n for _, names in GROUPS.values() for n in names}
    extras = sorted(
        c.qualified_name
        for c in bot.walk_commands()
        if c.qualified_name not in listed
        and c.qualified_name not in SKIP
        and c.name not in SKIP
        and not isinstance(c, commands.HybridCommand)
        and c.parent is None
        and c.name not in existing
    )
    if extras:
        plan["misc"] = ("Other commands", extras)

    skipped: list[str] = []
    for group_name, (group_desc, names) in plan.items():
        if group_name in existing:
            print(f"{TAG} slash group /{group_name} already exists; skipping its {len(names)} command(s)")
            continue
        group = app_commands.Group(name=group_name, description=_clip(group_desc))
        for qualified in names:
            if qualified in SKIP or qualified in assigned:
                continue
            cmd = _lookup(bot, qualified)
            if cmd is None:
                print(f"{TAG} /{group_name}: prefix command {qualified!r} not found")
                continue
            if isinstance(cmd, commands.HybridCommand):
                continue  # already a slash command
            if len(group.commands) >= MAX_SUBCOMMANDS:
                skipped.append(qualified)
                continue
            slash_name = RENAME.get(qualified, cmd.name).lower()
            path = f"/{group_name} {slash_name}"
            try:
                group.add_command(_build_subcommand(bot, cmd, slash_name, path))
            except Exception as exc:
                print(f"{TAG} could not bridge {qualified!r}: {type(exc).__name__}: {exc}")
                continue
            prefix_notice.SLASH_PATHS[cmd.qualified_name] = path
            assigned.add(qualified)
        if group.commands:
            bot.tree.add_command(group)

    if skipped:
        print(f"{TAG} no room for {len(skipped)} command(s): {', '.join(skipped)}")
    top = len(bot.tree.get_commands())
    print(f"{TAG} {len(assigned)} prefix command(s) now have slash versions ({top} top-level slash commands)")
    if top > MAX_TOP_LEVEL:
        print(f"{TAG} WARNING: {top} top-level commands exceeds Discord's limit of {MAX_TOP_LEVEL}")
    bot._slash_bridge_registered = True  # type: ignore[attr-defined]
    return dict(prefix_notice.SLASH_PATHS)
