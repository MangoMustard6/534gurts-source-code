"""The slash-command block/thread check must actually be installed on the tree.

``@bot.tree.interaction_check`` used to be a decorator by mistake: that method is
meant to be overridden, so the decorator called it with the function as its
argument and installed nothing.  Blocked users and channels were therefore not
stopped on slash commands.
"""

import asyncio
import os
import types
from unittest.mock import MagicMock

import pytest

discord = pytest.importorskip("discord")

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("BOT_OWNER_ID", "1")

from bot import ihtx_bot  # noqa: E402


class _Response:
    def __init__(self):
        self.sent = []

    def is_done(self):
        return bool(self.sent)

    async def send_message(self, *args, **kwargs):
        self.sent.append((args, kwargs))


def _interaction(user_id=4242, channel_id=777, name="someone", channel="default", command_name="zz_probe"):
    if channel == "default":
        channel = types.SimpleNamespace(id=channel_id)  # not a Thread: no join attempt
    return types.SimpleNamespace(
        user=types.SimpleNamespace(id=user_id, name=name),
        channel=channel,
        response=_Response(),
        # extra fields used when the interaction goes through the real tree
        type=discord.InteractionType.application_command,
        data={"type": 1, "name": command_name, "options": [], "resolved": {}},
        guild_id=None, guild=None, client=ihtx_bot.bot, command_failed=False,
        namespace=None, command=None, _state=MagicMock(),
    )


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(ihtx_bot, "blocklist", set())
    monkeypatch.setattr(ihtx_bot, "channel_blocks", set())
    monkeypatch.setattr(ihtx_bot, "owner_ids", {1})
    monkeypatch.setattr(ihtx_bot, "_is_timed_blocked", lambda user_id: False)


def _check(interaction):
    return asyncio.run(ihtx_bot._slash_global_check(interaction))


def test_the_check_is_installed_on_the_tree():
    assert ihtx_bot.bot.tree.interaction_check is ihtx_bot._slash_global_check
    assert asyncio.iscoroutinefunction(ihtx_bot._slash_global_check)


def test_normal_user_is_allowed():
    interaction = _interaction()
    assert _check(interaction) is True
    assert interaction.response.sent == []


def test_blocked_user_is_refused_privately(monkeypatch):
    monkeypatch.setattr(ihtx_bot, "blocklist", {4242})
    interaction = _interaction()
    assert _check(interaction) is False
    (args, kwargs), = interaction.response.sent
    assert "blocked" in args[0] and kwargs == {"ephemeral": True}


def test_timed_blocked_user_is_refused(monkeypatch):
    monkeypatch.setattr(ihtx_bot, "_is_timed_blocked", lambda user_id: user_id == 4242)
    assert _check(_interaction()) is False


def test_owner_is_never_blocked(monkeypatch):
    monkeypatch.setattr(ihtx_bot, "blocklist", {1})
    assert _check(_interaction(user_id=1)) is True


def test_blocked_channel_is_refused_but_not_for_owners(monkeypatch):
    monkeypatch.setattr(ihtx_bot, "channel_blocks", {777})
    assert _check(_interaction(channel_id=777)) is False
    assert _check(_interaction(user_id=1, channel_id=777)) is True


def test_missing_channel_is_fine():
    """User-installed commands and DMs can arrive with no channel."""
    assert _check(_interaction(channel=None)) is True


def test_blocked_user_command_does_not_run_through_the_real_tree(monkeypatch):
    """End to end: the tree must skip the command callback for a blocked user."""
    ran = []

    async def probe(interaction: discord.Interaction):
        ran.append(interaction.user.id)

    command = discord.app_commands.Command(name="zz_probe", description="probe", callback=probe)
    ihtx_bot.bot.tree.add_command(command)
    try:
        monkeypatch.setattr(ihtx_bot, "blocklist", {4242})
        blocked = _interaction(user_id=4242)
        asyncio.run(ihtx_bot.bot.tree._call(blocked))
        assert ran == [] and blocked.command_failed is True

        allowed = _interaction(user_id=5000)
        asyncio.run(ihtx_bot.bot.tree._call(allowed))
        assert ran == [5000]
    finally:
        ihtx_bot.bot.tree.remove_command("zz_probe")
