"""Slash versions of prefix commands (bot/slash_bridge.py)."""

import asyncio
import re
import types
from unittest.mock import MagicMock

import pytest

discord = pytest.importorskip("discord")
from discord import app_commands  # noqa: E402
from discord.ext import commands  # noqa: E402

from bot import prefix_notice, slash_bridge  # noqa: E402


class _Response:
    def __init__(self):
        self.done = False
        self.log = []

    def is_done(self):
        return self.done

    async def defer(self, **kw):
        self.done = True
        self.log.append(("defer", kw))

    async def send_message(self, *a, **kw):
        self.done = True
        self.log.append(("response", a, kw))


class _Followup:
    def __init__(self, log):
        self.log = log

    async def send(self, *a, **kw):
        self.log.append(("followup", a, kw))
        return MagicMock()


def _interaction(bot, sub, **options):
    channel = MagicMock()
    channel.id = 555
    channel.type = discord.ChannelType.text
    channel.guild = None
    response = _Response()
    return types.SimpleNamespace(
        client=bot, command=sub, data={"type": 1, "name": sub.name}, message=None, id=999,
        channel_id=555, channel=channel, _state=MagicMock(), guild_id=None,
        user=types.SimpleNamespace(id=42, name="u", bot=False, mention="<@42>", display_name="U"),
        namespace=list(options.items()), response=response, followup=_Followup(response.log),
        is_expired=lambda: False, command_failed=False, permissions=None,
    )


@pytest.fixture
def bot(monkeypatch):
    b = commands.Bot(command_prefix="th>", intents=discord.Intents.default(), help_command=None)
    seen = {}

    @b.command(name="echo")
    async def echo(ctx, count: int, label: str = "none", *rest: str):
        """Echo the arguments back."""
        seen["echo"] = (count, label, rest, ctx.command.name)
        await ctx.reply(f"{count} {label} {list(rest)}")

    @b.command(name="grab")
    async def grab(ctx, *, args: str = ""):
        """Read an attachment, react to the message, then reply."""
        seen["files"] = [a.filename for a in ctx.message.attachments]
        seen["reference"] = ctx.message.reference
        seen["react"] = await ctx.message.add_reaction("ok")
        await ctx.reply(f"args={args!r}")

    @b.command(name="stripme")
    async def stripme(ctx, target_raw: str = "", hours_raw: str = ""):
        seen["stripme"] = (target_raw, hours_raw)

    @b.command(name="secret")
    @commands.check(lambda ctx: False)
    async def secret(ctx):
        seen["secret"] = True

    @b.command(name="boom")
    async def boom(ctx):
        raise RuntimeError("kaboom")

    @b.command(name="plainone")
    async def plainone(ctx):
        """Unlisted command: lands in /misc automatically."""

    @b.group(name="box", invoke_without_command=True)
    async def box(ctx, name: str = ""):
        """Box root."""

    @box.command(name="open")
    async def box_open(ctx, item: str):
        """Open an item."""
        seen["box"] = item

    monkeypatch.setattr(slash_bridge, "GROUPS", {
        "demo": ("Demo group", ["echo", "grab", "stripme", "secret", "boom"]),
        "box": ("Boxes", ["box", "box open"]),
    })
    monkeypatch.setattr(prefix_notice, "SLASH_PATHS", {})
    b._seen = seen
    slash_bridge.register(b)
    return b


def _sub(bot, group, name):
    return bot.tree.get_command(group).get_command(name)


def _run(bot, group, name, **options):
    sub = _sub(bot, group, name)
    interaction = _interaction(bot, sub, **options)
    asyncio.run(sub._callback(interaction, **options))
    return interaction.response.log


# ── registration ──────────────────────────────────────────────────────────────

def test_groups_subcommands_and_misc_fallback(bot):
    assert {c.name for c in bot.tree.get_commands()} == {"demo", "box", "misc"}
    assert {c.name for c in bot.tree.get_command("demo").commands} == {"echo", "grab", "stripme", "secret", "boom"}
    assert [c.name for c in bot.tree.get_command("misc").commands] == ["plainone"]


def test_prefix_group_root_and_subcommands(bot):
    assert {c.name for c in bot.tree.get_command("box").commands} == {"box", "open"}
    assert [p.name for p in _sub(bot, "box", "open").parameters] == ["item"]


def test_options_come_from_the_prefix_signature(bot):
    echo = {p.name: (p.type, p.required) for p in _sub(bot, "demo", "echo").parameters}
    assert echo["count"] == (discord.AppCommandOptionType.integer, True)
    assert echo["label"][1] is False and echo["rest"][1] is False
    grab = {p.name: p.type for p in _sub(bot, "demo", "grab").parameters}
    assert grab["file"] == discord.AppCommandOptionType.attachment
    assert _sub(bot, "demo", "echo").description == "Echo the arguments back."


def test_every_payload_is_valid_for_discord(bot):
    for group in bot.tree.get_commands():
        for sub in group.commands:
            data = sub.to_dict(bot.tree)
            assert 1 <= len(data["description"]) <= 100
            required_done = False
            for opt in data.get("options", []):
                assert re.fullmatch(r"[-_\w]{1,32}", opt["name"]) and opt["name"] == opt["name"].lower()
                assert 1 <= len(opt["description"]) <= 100
                if not opt.get("required"):
                    required_done = True
                assert not (opt.get("required") and required_done), "required option after optional one"


def test_option_names_are_tidied_but_mapped_back(bot):
    sub = _sub(bot, "demo", "stripme")
    assert [p.name for p in sub.parameters] == ["target", "hours"]
    _run(bot, "demo", "stripme", target="123", hours="2")
    assert bot._seen["stripme"] == ("123", "2")


def test_slash_paths_feed_the_prefix_notice(bot):
    assert prefix_notice.SLASH_PATHS["echo"] == "/demo echo"
    assert prefix_notice.SLASH_PATHS["box open"] == "/box open"


# ── invoking ──────────────────────────────────────────────────────────────────

def test_invocation_reuses_the_prefix_code_and_defers(bot):
    log = _run(bot, "demo", "echo", count=3, label="L", rest='a "b c" d')
    assert bot._seen["echo"] == (3, "L", ("a", "b c", "d"), "echo")
    assert log[0][0] == "defer"
    assert log[-1][0] == "followup" and "3 L ['a', 'b c', 'd']" in log[-1][2]["content"]


def test_omitted_options_use_the_command_defaults(bot):
    _run(bot, "demo", "echo", count=1)
    assert bot._seen["echo"][:3] == (1, "none", ())


def test_uploaded_file_reaches_ctx_message_attachments(bot):
    att = discord.Attachment(data={"id": 1, "filename": "clip.mp4", "size": 10,
                                   "url": "https://x/clip.mp4", "proxy_url": "https://x/clip.mp4"},
                             state=MagicMock())
    _run(bot, "demo", "grab", args="5 10", file=att)
    assert bot._seen["files"] == ["clip.mp4"]
    assert bot._seen["reference"] is None
    assert bot._seen["react"] is None, "reactions on the synthetic message must be no-ops"


def test_failed_checks_stop_the_command_with_a_private_message(bot):
    log = _run(bot, "demo", "secret")
    assert "secret" not in bot._seen
    assert log == [("response", ("❌ You can't use this command here.",), {"ephemeral": True})]


def test_errors_go_through_command_error_handler(bot):
    errors = []

    @bot.event
    async def on_command_error(ctx, error):
        errors.append(error)

    async def go():
        bot.loop = asyncio.get_running_loop()  # an unstarted bot has no loop to dispatch on
        sub = _sub(bot, "demo", "boom")
        await sub._callback(_interaction(bot, sub))
        await asyncio.sleep(0.05)

    asyncio.run(go())
    assert len(errors) == 1 and isinstance(errors[0], commands.CommandInvokeError)
    assert isinstance(errors[0].original, RuntimeError)


def test_register_is_idempotent(bot):
    before = len(bot.tree.get_commands())
    slash_bridge.register(bot)
    assert len(bot.tree.get_commands()) == before
