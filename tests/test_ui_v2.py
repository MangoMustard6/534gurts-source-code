"""Components V2 helpers: embed -> LayoutView conversion and the shutdown notice."""

import asyncio
import datetime
import types

import pytest

discord = pytest.importorskip("discord")
from discord import ui  # noqa: E402
from discord.ext import commands  # noqa: E402
from discord.ext.commands.view import StringView  # noqa: E402

if not hasattr(ui, "LayoutView"):  # Components V2 needs discord.py 2.6+
    pytest.skip("discord.py without Components V2", allow_module_level=True)

from bot import prefix_notice as pn  # noqa: E402
from bot.ui_v2 import MAX_TEXT, add_notice, embed_fits, embed_payload, embed_to_layout  # noqa: E402

TEXT_DISPLAY = 10
CONTAINER = 17


def _texts(view):
    """Every text block in the layout, including those nested in sections."""
    def walk(components):
        for c in components:
            if c["type"] == TEXT_DISPLAY:
                yield c["content"]
            yield from walk(c.get("components", []))
            if "accessory" in c:
                yield from walk([c["accessory"]])
    return list(walk(view.to_components()))


def _text_len(view):
    def walk(items):
        total = 0
        for item in items:
            if isinstance(item, ui.TextDisplay):
                total += len(item.content)
            total += walk(getattr(item, "children", ()) or ())
        return total
    return walk(view.children)


# ── embed -> layout ───────────────────────────────────────────────────────────

def test_rich_embed_becomes_a_container():
    e = discord.Embed(title="Hello", url="https://example.com", description="desc", colour=0x5865F2,
                      timestamp=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))
    e.set_author(name="Author")
    e.add_field(name="A", value="1")
    e.add_field(name="B", value="2")
    e.set_thumbnail(url="https://example.com/t.png")
    e.set_image(url="https://example.com/i.png")
    e.set_footer(text="foot")

    comps = embed_to_layout(e, notice="NOTICE").to_components()
    assert [c["type"] for c in comps] == [CONTAINER]
    assert comps[0]["accent_color"] == 0x5865F2
    joined = "\n".join(_texts(embed_to_layout(e, notice="NOTICE")))
    for part in ("[Hello](https://example.com)", "desc", "**A**\n1", "**B**\n2", "foot", "NOTICE"):
        assert part in joined


def test_empty_and_description_only_embeds_render():
    assert embed_to_layout(discord.Embed()).to_components()
    assert _texts(embed_to_layout(discord.Embed(description="❌ nope")))[0] == "❌ nope"


def test_huge_embed_stays_within_discord_limits():
    big = discord.Embed(title="T" * 200, description="d" * 4096)
    for i in range(25):
        big.add_field(name=f"f{i}", value="v" * 1000)
    big.set_footer(text="f" * 300)
    view = embed_to_layout(big, notice="N" * 150)
    assert _text_len(view) <= MAX_TEXT
    assert "**f0**" in "\n".join(_texts(view)), "a long description must not hide every field"


# ── embed_payload ─────────────────────────────────────────────────────────────

def test_payload_uses_v2_for_short_embeds_and_blocks_mass_pings():
    payload = embed_payload(discord.Embed(description="@everyone hi"))
    assert set(payload) == {"view", "allowed_mentions"}
    assert isinstance(payload["view"], ui.LayoutView)
    mentions = payload["allowed_mentions"]
    assert not mentions.everyone and not mentions.users and not mentions.roles
    assert mentions.replied_user is True


def test_payload_falls_back_to_classic_embed_instead_of_clipping():
    long_embed = discord.Embed(title="Help", description="d" * 500)
    for i in range(20):
        long_embed.add_field(name=f"cmd{i}", value="v" * 200)  # legal embed, too long for V2
    assert not embed_fits(long_embed)
    payload = embed_payload(long_embed)
    assert payload == {"embed": long_embed}


# ── add_notice ────────────────────────────────────────────────────────────────

def test_add_notice_appends_inside_the_container():
    view = embed_to_layout(discord.Embed(description="hi", colour=1))
    assert add_notice(view, "prefix notice")
    assert _texts(view)[-1] == "-# prefix notice"


def test_add_notice_refuses_when_it_would_not_fit():
    view = embed_to_layout(discord.Embed(description="x" * 3990))
    before = _text_len(view)
    assert add_notice(view, "n" * 50) is False
    assert _text_len(view) == before


# ── NoticeContext (prefix shutdown notice) ────────────────────────────────────

@pytest.fixture
def sent(monkeypatch):
    log = []

    async def rec(self, content=None, **kw):
        log.append((content, kw))
        return "message"

    monkeypatch.setattr(commands.Context, "send", rec)
    monkeypatch.setattr(commands.Context, "reply", rec)
    monkeypatch.setitem(pn.SLASH_PATHS, "trim", "/edit trim")
    return log


def _ctx(command="trim", interaction=None):
    async def callback(ctx):
        pass

    bot = commands.Bot(command_prefix="th>", intents=discord.Intents.default())
    cmd = commands.Command(callback, name=command) if command else None
    msg = types.SimpleNamespace(_state=None, channel=None, author=None, guild=None)
    return pn.NoticeContext(message=msg, bot=bot, view=StringView(""), prefix="th>", command=cmd,
                            invoked_with=command, interaction=interaction)


def test_notice_goes_into_a_v2_layout(sent):
    view = embed_to_layout(discord.Embed(description="hi"))
    asyncio.run(_ctx().reply(view=view))
    last = _texts(view)[-1]
    assert "/edit trim" in last and "January 2027" in last


def test_notice_extends_a_classic_embed_footer(sent):
    embed = discord.Embed(description="x").set_footer(text="orig", icon_url="https://x/y.png")
    asyncio.run(_ctx().reply(embed=embed))
    assert embed.footer.text.startswith("orig\n") and "/edit trim" in embed.footer.text
    assert embed.footer.icon_url == "https://x/y.png"


def test_notice_is_added_to_plain_content_and_file_only_replies(sent):
    asyncio.run(_ctx().reply("hello"))
    assert sent[-1][0].startswith("hello\n-# ⚠️") and "`th>`" in sent[-1][0]
    asyncio.run(_ctx().reply(file="F"))
    assert sent[-1][0].startswith("-# ⚠️")


def test_notice_only_on_the_first_reply_of_an_invocation(sent):
    ctx = _ctx()
    asyncio.run(ctx.reply("one"))
    asyncio.run(ctx.send("two"))
    assert "⚠️" in sent[0][0] and sent[1][0] == "two"


def test_no_notice_for_slash_or_unknown_commands(sent):
    asyncio.run(_ctx(interaction=object()).reply("hello"))
    asyncio.run(_ctx(command=None).reply("hello"))
    assert [c for c, _ in sent] == ["hello", "hello"]


def test_notice_without_a_known_slash_path_is_generic(sent):
    asyncio.run(_ctx(command="zzz").reply("hi"))
    assert "slash (`/`) commands instead" in sent[-1][0]
