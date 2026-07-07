"""
TagCog — discord.py Cog providing the full tag system.

All commands live under the `t!tag` group (alias: `t!tags`).
Direct invocation: `t!tag <name> [args...]`
"""

import io
import logging
import math
import random
import re
import textwrap
from datetime import datetime, timezone

import discord
from discord.ext import commands

from .storage import TagStorage
from .parser import parse, build_context, detect_engines, ENGINE_DISPLAY_NAMES
from . import engines

log = logging.getLogger(__name__)

MAX_TAG_NAME = 64
MAX_TAG_CONTENT = 4000
TAGS_PER_PAGE = 15

_RESERVED = frozenset({
    "create", "add", "new", "edit", "update", "delete", "remove", "del",
    "info", "list", "ls", "all", "search", "find", "alias", "unalias",
    "raw", "transfer", "stats", "help", "rename", "perms",
})

storage = TagStorage()


def _detect_type(content: str) -> tuple[str, list[str]]:
    """Return (type_label, list_of_display_engine_names) for the tag content."""
    engines_found = detect_engines(content)
    names = [ENGINE_DISPLAY_NAMES.get(e, e.title()) for e in engines_found]
    if not names:
        return "Text", []
    if len(names) == 1:
        return "Script", names
    return "Mixed Scripts", names


def _is_bot_owner(bot: commands.Bot, user_id: int) -> bool:
    try:
        from bot.ihtx_bot import owner_ids
        return user_id in owner_ids
    except Exception:
        return False


def _audit(action: str, executor: discord.Member, tag: dict):
    """Log when a bot owner takes action on another user's tag."""
    if executor.id == tag.get("owner_id"):
        return
    ts = datetime.now(timezone.utc).isoformat()
    log.warning(
        "[TAG AUDIT] action=%s executor=%s(%d) tag_owner=%d tag=%s ts=%s",
        action, executor.name, executor.id, tag.get("owner_id", 0),
        tag.get("name", "?"), ts,
    )


def _can_use(tag: dict, member: discord.Member) -> bool:
    if member.id in tag.get("denied_users", []):
        return False
    allowed = tag.get("allowed_roles", [])
    if not allowed:
        return True
    return bool({r.id for r in member.roles} & set(allowed))


def _valid_name(name: str) -> bool:
    return bool(name) and name.replace("-", "").replace("_", "").isalnum()


class TagCog(commands.Cog, name="Tags"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _owner(self, ctx: commands.Context) -> bool:
        return _is_bot_owner(self.bot, ctx.author.id)

    # ── Group root — invoke a tag OR dispatch to subcommand ────────────────

    @commands.group(name="tag", aliases=["tags"], invoke_without_command=True)
    async def tag(self, ctx: commands.Context, name: str = None, *, args: str = ""):
        """Invoke a tag by name, or use a subcommand."""
        if name is None:
            return await ctx.reply(
                "Usage: `t!tag <name> [args]`\n"
                "Run `t!tag help` to see all subcommands."
            )
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tag = await storage.get(ctx.guild.id, name.lower())
        if tag is None:
            return await ctx.reply(
                embed=discord.Embed(description=f"❌ Tag `{name}` not found.", color=discord.Color.red())
            )

        if isinstance(ctx.author, discord.Member):
            if not _can_use(tag, ctx.author) and not self._owner(ctx):
                return await ctx.reply(
                    embed=discord.Embed(description="❌ You don't have permission to use this tag.", color=discord.Color.red())
                )

        tag_ctx = build_context(ctx, args)
        text, engine_blocks = parse(tag["content"], tag_ctx)

        files: list[discord.File] = []
        embeds: list[discord.Embed] = []
        errors: list[str] = []
        extra_texts: list[str] = []

        for block in engine_blocks:
            engine = engines.get(block["engine"])
            if engine is None:
                errors.append(f"Unknown engine: `{block['engine']}`")
                continue
            result = await engine.execute(block["content"], ctx, tag_ctx)
            if result.error:
                errors.append(result.error)
            else:
                files.extend(result.files)
                if result.text:
                    extra_texts.append(result.text)
                if result.embed is not None:
                    embeds.append(result.embed)

        parts = [text] + extra_texts
        final = "\n".join(p for p in parts if p).strip()
        if errors:
            final = (final + "\n" + "\n".join(f"⚠️ {e}" for e in errors)).strip()

        if not final and not files and not embeds:
            return await ctx.reply("*(tag produced no output)*")

        if len(final) > 2000:
            final = final[:1997] + "…"

        send_kwargs: dict = {}
        if final:
            send_kwargs["content"] = final
        if embeds:
            send_kwargs["embeds"] = embeds[:10]
        if files:
            send_kwargs["files"] = files

        await ctx.reply(**send_kwargs)
        await storage.increment_uses(ctx.guild.id, name.lower())

    # ── Create ─────────────────────────────────────────────────────────────

    @tag.command(name="create", aliases=["add", "new"])
    async def tag_create(self, ctx: commands.Context, name: str, *, content: str):
        """Create a new tag."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be created in servers.")

        name = name.lower().strip()
        if len(name) > MAX_TAG_NAME:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Name too long (max {MAX_TAG_NAME} chars).", color=discord.Color.red()))
        if not _valid_name(name):
            return await ctx.reply(embed=discord.Embed(description="❌ Tag name may only contain letters, numbers, hyphens, and underscores.", color=discord.Color.red()))
        if name in _RESERVED:
            return await ctx.reply(embed=discord.Embed(description=f"❌ `{name}` is a reserved subcommand name.", color=discord.Color.red()))
        if len(content) > MAX_TAG_CONTENT:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Content too long (max {MAX_TAG_CONTENT} chars).", color=discord.Color.red()))

        ok = await storage.create(ctx.guild.id, name, content, ctx.author.id)
        if not ok:
            # Allow upsert if the user owns the tag
            existing = await storage.get(ctx.guild.id, name)
            if existing and (existing["owner_id"] == ctx.author.id or self._owner(ctx)):
                result = await storage.edit(ctx.guild.id, name, content, ctx.author.id, self._owner(ctx))
                if result == "ok":
                    return await ctx.reply(embed=discord.Embed(description=f"✅ Tag `{name}` updated.", color=discord.Color.green()))
            return await ctx.reply(embed=discord.Embed(description=f"❌ Tag `{name}` already exists.", color=discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=f"✅ Tag `{name}` created.", color=discord.Color.green()))

    # ── Force-remove (owner only) ──────────────────────────────────────────

    @tag.command(name="forceremove", aliases=["forcedelete", "forcedel", "fr"])
    async def tag_forceremove(self, ctx: commands.Context, name: str):
        """Force-delete any tag (bot owner only)."""
        if not self._owner(ctx):
            return await ctx.reply(embed=discord.Embed(description="❌ Bot owner only.", color=discord.Color.red()))
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tag = await storage.get(ctx.guild.id, name.lower())
        if tag:
            _audit("forceremove", ctx.author, tag)

        result = await storage.delete(ctx.guild.id, name.lower(), ctx.author.id, True)
        msgs = {
            "ok":        (f"✅ Tag `{name}` force-deleted.", discord.Color.green()),
            "not_found": (f"❌ Tag `{name}` not found.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    # ── Edit ───────────────────────────────────────────────────────────────

    @tag.command(name="edit", aliases=["update"])
    async def tag_edit(self, ctx: commands.Context, name: str, *, content: str):
        """Edit a tag you own (or any tag if you're a bot owner)."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be edited in servers.")
        if len(content) > MAX_TAG_CONTENT:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Content too long (max {MAX_TAG_CONTENT} chars).", color=discord.Color.red()))

        tag = await storage.get(ctx.guild.id, name.lower())
        is_owner = self._owner(ctx)

        if tag and is_owner:
            _audit("edit", ctx.author, tag)

        result = await storage.edit(ctx.guild.id, name.lower(), content, ctx.author.id, is_owner)
        msgs = {
            "ok":        (f"✅ Tag `{name}` updated.", discord.Color.green()),
            "not_found": (f"❌ Tag `{name}` not found.", discord.Color.red()),
            "not_owner": ("❌ You don't own this tag.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    # ── Delete ─────────────────────────────────────────────────────────────

    @tag.command(name="delete", aliases=["remove", "del"])
    async def tag_delete(self, ctx: commands.Context, name: str):
        """Delete a tag you own (or any tag if you're a bot owner)."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be deleted in servers.")

        tag = await storage.get(ctx.guild.id, name.lower())
        is_owner = self._owner(ctx)

        if tag and is_owner:
            _audit("delete", ctx.author, tag)

        result = await storage.delete(ctx.guild.id, name.lower(), ctx.author.id, is_owner)
        msgs = {
            "ok":        (f"✅ Tag `{name}` deleted.", discord.Color.green()),
            "not_found": (f"❌ Tag `{name}` not found.", discord.Color.red()),
            "not_owner": ("❌ You don't own this tag.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    # ── Info ───────────────────────────────────────────────────────────────

    @tag.command(name="info")
    async def tag_info(self, ctx: commands.Context, name: str):
        """Show metadata about a tag."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tag = await storage.get(ctx.guild.id, name.lower())
        if tag is None:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Tag `{name}` not found.", color=discord.Color.red()))

        owner = self.bot.get_user(tag["owner_id"])
        owner_str = owner.mention if owner else f"<@{tag['owner_id']}>"

        def _fmt_ts(iso: str) -> str:
            try:
                dt = datetime.fromisoformat(iso)
                return f"<t:{int(dt.timestamp())}:R>"
            except Exception:
                return "unknown"

        created_str = _fmt_ts(tag.get("created_at", ""))
        edited_str = _fmt_ts(tag.get("edited_at", tag.get("created_at", "")))

        tag_type, tag_engines = _detect_type(tag["content"])
        content_len = len(tag["content"])

        embed = discord.Embed(title=f"Tag: {tag['name']}", color=0x5865F2)
        embed.add_field(name="Owner", value=owner_str, inline=True)
        embed.add_field(name="Uses", value=str(tag.get("uses", 0)), inline=True)
        embed.add_field(name="Type", value=tag_type, inline=True)
        if tag_engines:
            eng_label = "Engine" if len(tag_engines) == 1 else "Engines"
            embed.add_field(name=eng_label, value="\n".join(tag_engines), inline=True)
        embed.add_field(name="Created", value=created_str, inline=True)
        embed.add_field(name="Last Edited", value=edited_str, inline=True)
        embed.add_field(name="Content Length", value=f"{content_len} chars", inline=True)

        aliases = tag.get("aliases", [])
        if aliases:
            embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in aliases), inline=False)

        allowed_roles = tag.get("allowed_roles", [])
        denied_users = tag.get("denied_users", [])
        if allowed_roles:
            embed.add_field(name="Allowed roles", value=" ".join(f"<@&{r}>" for r in allowed_roles), inline=False)
        if denied_users:
            embed.add_field(name="Denied users", value=" ".join(f"<@{u}>" for u in denied_users), inline=False)

        preview = tag["content"]
        if len(preview) > 120:
            preview = preview[:120] + "…"
        embed.add_field(name="Content preview", value=f"```\n{preview}\n```", inline=False)
        await ctx.reply(embed=embed)

    # ── List ───────────────────────────────────────────────────────────────

    @tag.command(name="list", aliases=["ls", "all"])
    async def tag_list(self, ctx: commands.Context, page: int = 1):
        """List all tags in this server. Paginated."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tags = await storage.list_tags(ctx.guild.id)
        if not tags:
            return await ctx.reply("No tags yet. Create one with `t!tag create <name> <content>`.")

        total = math.ceil(len(tags) / TAGS_PER_PAGE)
        page = max(1, min(page, total))
        chunk = tags[(page - 1) * TAGS_PER_PAGE : page * TAGS_PER_PAGE]

        embed = discord.Embed(
            title=f"Tags — {ctx.guild.name}",
            description=", ".join(f"`{t['name']}`" for t in chunk),
            color=0x5865F2,
        )
        embed.set_footer(text=f"Page {page}/{total} · {len(tags)} total tags")
        await ctx.reply(embed=embed)

    # ── Random ─────────────────────────────────────────────────────────────

    @tag.command(name="random", aliases=["rand"])
    async def tag_random(self, ctx: commands.Context):
        """Run a randomly picked tag and show its name."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tags = await storage.list_tags(ctx.guild.id)
        if not tags:
            return await ctx.reply("No tags in this server yet.")

        chosen = random.choice(tags)
        name = chosen["name"]
        tag_ctx = build_context(ctx, "")
        text, engine_blocks = parse(chosen["content"], tag_ctx)

        files: list[discord.File] = []
        embeds: list[discord.Embed] = []
        extra_texts: list[str] = []
        errors: list[str] = []

        for block in engine_blocks:
            engine = engines.get(block["engine"])
            if engine is None:
                continue
            result = await engine.execute(block["content"], ctx, tag_ctx)
            if result.error:
                errors.append(result.error)
            else:
                files.extend(result.files)
                if result.text:
                    extra_texts.append(result.text)
                if result.embed is not None:
                    embeds.append(result.embed)

        parts = [f"🎲 Running tag `{name}`", text] + extra_texts
        final = "\n".join(p for p in parts if p).strip()
        if errors:
            final = (final + "\n" + "\n".join(f"⚠️ {e}" for e in errors)).strip()
        if len(final) > 2000:
            final = final[:1997] + "…"

        send_kwargs: dict = {}
        if final:
            send_kwargs["content"] = final
        if embeds:
            send_kwargs["embeds"] = embeds[:10]
        if files:
            send_kwargs["files"] = files

        await ctx.reply(**send_kwargs)
        await storage.increment_uses(ctx.guild.id, name)

    # ── Search ─────────────────────────────────────────────────────────────

    @tag.command(name="search", aliases=["find"])
    async def tag_search(self, ctx: commands.Context, *, query: str):
        """Search tags by name or content."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        results = await storage.search_tags(ctx.guild.id, query)
        if not results:
            return await ctx.reply(f"No tags match `{query}`.")

        results = results[:25]
        embed = discord.Embed(
            title=f"Search: '{query}'",
            description=", ".join(f"`{t['name']}`" for t in results),
            color=0x5865F2,
        )
        embed.set_footer(text=f"{len(results)} result(s)")
        await ctx.reply(embed=embed)

    # ── Raw ────────────────────────────────────────────────────────────────

    @tag.command(name="raw")
    async def tag_raw(self, ctx: commands.Context, name: str):
        """Show the unparsed source content of a tag."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tag = await storage.get(ctx.guild.id, name.lower())
        if tag is None:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Tag `{name}` not found.", color=discord.Color.red()))

        content = tag["content"]
        embed = discord.Embed(title="📄 Raw Tag Source", color=0x5865F2)
        embed.set_footer(text=f"tag: {tag['name']} · {len(content)} chars")

        # Fits in one embed description
        if len(content) <= 3900:
            block = content.replace("```", "`\u200b`\u200b`")  # break any backtick runs
            embed.description = f"```\n{block}\n```"
            return await ctx.reply(embed=embed)

        # Too long — upload as a .txt file
        embed.description = "Content too long to display inline — see attached file."
        await ctx.reply(
            embed=embed,
            file=discord.File(
                io.BytesIO(content.encode("utf-8")),
                filename=f"{tag['name']}.txt",
            ),
        )

    # ── Alias / Unalias ────────────────────────────────────────────────────

    @tag.command(name="alias")
    async def tag_alias(self, ctx: commands.Context, new_alias: str, existing_name: str):
        """Add an alias for an existing tag: t!tag alias <new> <existing>"""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        new_alias = new_alias.lower().strip()
        if not _valid_name(new_alias):
            return await ctx.reply(embed=discord.Embed(description="❌ Alias may only contain letters, numbers, hyphens, and underscores.", color=discord.Color.red()))

        result = await storage.add_alias(ctx.guild.id, existing_name.lower(), new_alias, ctx.author.id, self._owner(ctx))
        msgs = {
            "ok":        (f"✅ Alias `{new_alias}` → `{existing_name}` added.", discord.Color.green()),
            "not_found": (f"❌ Tag `{existing_name}` not found.", discord.Color.red()),
            "not_owner": ("❌ You don't own this tag.", discord.Color.red()),
            "conflict":  (f"❌ `{new_alias}` is already a tag or alias.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    @tag.command(name="unalias")
    async def tag_unalias(self, ctx: commands.Context, alias: str):
        """Remove an alias you own."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        result = await storage.remove_alias(ctx.guild.id, alias.lower(), ctx.author.id, self._owner(ctx))
        msgs = {
            "ok":        (f"✅ Alias `{alias}` removed.", discord.Color.green()),
            "not_found": (f"❌ Alias `{alias}` not found.", discord.Color.red()),
            "not_owner": ("❌ You don't own the tag this alias belongs to.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    # ── Transfer ───────────────────────────────────────────────────────────

    @tag.command(name="transfer")
    async def tag_transfer(self, ctx: commands.Context, name: str, new_owner: discord.Member):
        """Transfer ownership of a tag to another server member."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        result = await storage.transfer(ctx.guild.id, name.lower(), new_owner.id, ctx.author.id, self._owner(ctx))
        msgs = {
            "ok":        (f"✅ Tag `{name}` transferred to {new_owner.mention}.", discord.Color.green()),
            "not_found": (f"❌ Tag `{name}` not found.", discord.Color.red()),
            "not_owner": ("❌ You don't own this tag.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    # ── Rename ─────────────────────────────────────────────────────────────

    @tag.command(name="rename")
    async def tag_rename(self, ctx: commands.Context, old_name: str, new_name: str):
        """Rename a tag you own."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        new_name = new_name.lower().strip()
        if not _valid_name(new_name):
            return await ctx.reply(embed=discord.Embed(description="❌ Tag name may only contain letters, numbers, hyphens, and underscores.", color=discord.Color.red()))
        if len(new_name) > MAX_TAG_NAME:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Name too long (max {MAX_TAG_NAME} chars).", color=discord.Color.red()))
        if new_name in _RESERVED:
            return await ctx.reply(embed=discord.Embed(description=f"❌ `{new_name}` is a reserved subcommand name.", color=discord.Color.red()))

        tag = await storage.get(ctx.guild.id, old_name.lower())
        is_owner = self._owner(ctx)
        if tag and is_owner:
            _audit("rename", ctx.author, tag)

        result = await storage.rename(ctx.guild.id, old_name.lower(), new_name, ctx.author.id, is_owner)
        msgs = {
            "ok":        (f"✅ Tag `{old_name}` renamed to `{new_name}`.", discord.Color.green()),
            "not_found": (f"❌ Tag `{old_name}` not found.", discord.Color.red()),
            "not_owner": ("❌ You don't own this tag.", discord.Color.red()),
            "conflict":  (f"❌ `{new_name}` already exists.", discord.Color.red()),
        }
        txt, color = msgs.get(result, (f"❌ {result}", discord.Color.red()))
        await ctx.reply(embed=discord.Embed(description=txt, color=color))

    # ── Stats ──────────────────────────────────────────────────────────────

    @tag.command(name="stats")
    async def tag_stats(self, ctx: commands.Context):
        """Show tag statistics for this server."""
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        s = await storage.stats(ctx.guild.id)
        embed = discord.Embed(title=f"Tag Stats — {ctx.guild.name}", color=0x5865F2)
        embed.add_field(name="Tags", value=str(s["total_tags"]), inline=True)
        embed.add_field(name="Aliases", value=str(s["total_aliases"]), inline=True)
        embed.add_field(name="Total uses", value=str(s["total_uses"]), inline=True)

        if s["top_tags"]:
            top = "\n".join(f"`{t['name']}` — {t.get('uses', 0)} uses" for t in s["top_tags"])
            embed.add_field(name="Top tags", value=top, inline=False)

        await ctx.reply(embed=embed)

    # ── Perms ──────────────────────────────────────────────────────────────

    @tag.command(name="perms")
    async def tag_perms(self, ctx: commands.Context, name: str, *, options: str = ""):
        """
        View or modify tag permissions.

        View:        `t!tag perms <name>`
        Allow roles: `t!tag perms <name> allow @Role1 @Role2`
        Open to all: `t!tag perms <name> everyone`
        Deny user:   `t!tag perms <name> deny @User`
        Un-deny:     `t!tag perms <name> undeny @User`
        """
        if ctx.guild is None:
            return await ctx.reply("Tags can only be used in servers.")

        tag = await storage.get(ctx.guild.id, name.lower())
        if tag is None:
            return await ctx.reply(embed=discord.Embed(description=f"❌ Tag `{name}` not found.", color=discord.Color.red()))

        if not options:
            allowed = tag.get("allowed_roles", [])
            denied = tag.get("denied_users", [])
            embed = discord.Embed(title=f"Permissions: {tag['name']}", color=0x5865F2)
            embed.add_field(name="Allowed roles", value=" ".join(f"<@&{r}>" for r in allowed) or "Everyone", inline=False)
            if denied:
                embed.add_field(name="Denied users", value=" ".join(f"<@{u}>" for u in denied), inline=False)
            return await ctx.reply(embed=embed)

        if not self._owner(ctx) and tag["owner_id"] != ctx.author.id:
            return await ctx.reply(embed=discord.Embed(description="❌ You don't own this tag.", color=discord.Color.red()))

        parts = options.strip().split(None, 1)
        mode = parts[0].lower()
        allowed_roles = list(tag.get("allowed_roles", []))
        denied_users = list(tag.get("denied_users", []))

        if mode == "everyone":
            allowed_roles = []
        elif mode == "allow":
            role_ids = [r.id for r in ctx.message.role_mentions]
            if not role_ids:
                return await ctx.reply(embed=discord.Embed(description="❌ Mention at least one @Role.", color=discord.Color.red()))
            allowed_roles = role_ids
        elif mode == "deny":
            user_ids = [u.id for u in ctx.message.mentions]
            if not user_ids:
                return await ctx.reply(embed=discord.Embed(description="❌ Mention at least one @User.", color=discord.Color.red()))
            denied_users = list(set(denied_users) | set(user_ids))
        elif mode == "undeny":
            user_ids = {u.id for u in ctx.message.mentions}
            denied_users = [u for u in denied_users if u not in user_ids]
        else:
            return await ctx.reply(embed=discord.Embed(description="❌ Unknown mode. Use `allow @Role`, `everyone`, `deny @User`, or `undeny @User`.", color=discord.Color.red()))

        result = await storage.set_perms(ctx.guild.id, name.lower(), allowed_roles, denied_users, ctx.author.id, self._owner(ctx))
        if result == "ok":
            await ctx.reply(embed=discord.Embed(description=f"✅ Permissions updated for tag `{name}`.", color=discord.Color.green()))
        else:
            await ctx.reply(embed=discord.Embed(description=f"❌ {result}", color=discord.Color.red()))

    # ── t! shorthand ───────────────────────────────────────────────────────

    @commands.command(name="t")
    async def tag_shortcut(self, ctx: commands.Context, name: str = None, *, args: str = ""):
        """Shorthand for t!tag <name> [args]. e.g. t!t hello world"""
        if name is None:
            return await ctx.reply("Usage: `t!t <tagname> [args]`  (shorthand for `t!tag <name> [args]`)")
        await ctx.invoke(self.tag, name=name, args=args)

    # ── Help ───────────────────────────────────────────────────────────────

    @tag.command(name="help")
    async def tag_help(self, ctx: commands.Context):
        """Show the full tag system reference."""
        embed = discord.Embed(
            title="Tag System Reference",
            description=(
                "Create and invoke reusable, scriptable tags.\n"
                "Prefix: `t!tag` (alias: `t!tags`) · Shorthand: `t!t <name> [args]`"
            ),
            color=0x5865F2,
        )
        embed.add_field(
            name="Commands",
            value=textwrap.dedent("""\
                `t!tag <name> [args]` / `t!t <name> [args]` — invoke a tag
                `t!tag create <name> <content>` — create (or edit your own)
                `t!tag edit <name> <content>` — edit (owner)
                `t!tag delete <name>` — delete (owner)
                `t!tag rename <old> <new>` — rename
                `t!tag raw <name>` — see raw source
                `t!tag info <name>` — metadata + type
                `t!tag list [page]` — list all tags
                `t!tag search <query>` — search by name/content
                `t!tag stats` — server statistics
                `t!tag random` — run a random tag
                `t!tag alias <new> <existing>` — add alias
                `t!tag unalias <alias>` — remove alias
                `t!tag transfer <name> @user` — transfer ownership
                `t!tag perms <name> [options]` — manage permissions
                `t!tag forceremove <name>` — delete any tag *(owner only)*\
            """),
            inline=False,
        )
        embed.add_field(
            name="Variables",
            value=textwrap.dedent("""\
                `{user}` · `{username}` · `{userid}` · `{mention}` · `{nickname}`
                `{avatar}` · `{server}` · `{serverid}` · `{channel}` · `{channelid}`
                `{args}` · `{arg:0}` `{arg:1}` … (0-indexed) · `{arg:*}` (all) · `{argslen}`
                `{args.1}` `{args.2}` … (1-indexed legacy)\
            """),
            inline=False,
        )
        embed.add_field(
            name="Inline functions",
            value=textwrap.dedent("""\
                `{math:1+2}` · `{math:{get:#}+1}` — arithmetic (resolves inner blocks)
                `{if:a|=|b|then:yes|else:no}` — conditional (ops: = != > < >= <=)
                `{random:1:100}` / `{range:1|100}` — random int (use `.` for float)
                `{choose:red|blue|green}` — random choice
                `{get:var}` — read a stored variable
                `{upper:x}` · `{lower:x}` · `{title:x}` · `{reverse:x}` · `{len:x}`
                `{repeat:3|text}` / `{repeat:3:text}` · `{slice:0|5|text}`
                `{substring:text|start}` · `{substring:text|start|end}`
                `{indexof:needle|haystack}` — returns index (-1 if not found)\
            """),
            inline=False,
        )
        embed.add_field(
            name="{set:var|value}",
            value=(
                "Store a value in a named variable (persists for the tag's lifetime).\n"
                "`{set:#|0}` → sets `#` to `0`. Value may contain nested blocks.\n"
                "Read back with `{get:var}`. Works inside `{foreach:}` loops."
            ),
            inline=False,
        )
        embed.add_field(
            name="{foreach:N|template}  /  {foreach:template|i1|i2|i3}",
            value=textwrap.dedent("""\
                **Count loop:** repeat template N times (max 50), re-evaluating each iteration.
                `{set:#|0}{foreach:3|{set:#|{math:{get:#}+1}}[a{get:#}]}` → `[a1][a2][a3]`
                **Item loop:** apply template to each `|`-separated item; `@` = current item.
                `{foreach:pitch=@|0|3|7}` → `pitch=0` / `pitch=3` / `pitch=7`
                Custom separator: prefix template with `sep~` e.g. `{foreach:;~pitch=@|0|3|7}`\
            """),
            inline=False,
        )
        embed.add_field(
            name="{tag:name}  /  {tagname}",
            value=(
                "Inline-run another tag and insert its text output.\n"
                "`{tag:invert}` or just `{invert}` (unknown variables auto-become tag lookups).\n"
                "Nesting limit: 3 levels."
            ),
            inline=False,
        )
        embed.add_field(
            name="Script prefix syntax (multiline blocks)",
            value=textwrap.dedent("""\
                Start a line with `engine:` alone to open a script block.
                Everything after it (until the next prefix) runs in that engine.
                ```
                tagscript:
                Hello {user}, you rolled {random:1:100}!

                iscript:
                caption=hello

                mediascript:
                speed=2
                ```
                **Aliases:** `tagscript`/`tscript` · `iscript`/`imagescript` · `mediascript`/`mscript` · `py`/`python` · `bash`/`sh` · `js`/`javascript`
                **Execution order:** Set → ForEach → Tag → TagScript → ImageScript → MediaScript → Python → Bash → JS\
            """),
            inline=False,
        )
        embed.add_field(
            name="{tagscript:…}  /  {tscript:…}",
            value="Re-evaluate content as TagScript (variables, math, conditionals). Inline version of the `tagscript:` prefix block.",
            inline=False,
        )
        embed.add_field(
            name="{js:…}  *(owner only)*",
            value="Run Node.js (ESM) code and return stdout. 5 s timeout, 4 000 char output limit.",
            inline=False,
        )
        embed.add_field(
            name="{bash:…}  /  {sh:…}  *(owner only)*",
            value="Run a shell command and return stdout. 5 s timeout, 4 000 char output limit.",
            inline=False,
        )
        embed.add_field(
            name="{attach:URL}",
            value="Download and send a file from an http/https URL (max 8 MB).",
            inline=False,
        )
        embed.add_field(
            name="{text:<source>}",
            value=textwrap.dedent("""\
                Load and return text content. Sources:
                `{text:Hello World}` — inline text
                `{text:attachment}` — attached .txt / .md / .csv / .log / .json / .yaml file
                `{text:reply}` — attachment from replied-to message
                `{text:https://example.com/file.txt}` — download from URL
                Max 1 MB · 5 000 lines · 50 000 chars.\
            """),
            inline=False,
        )
        embed.add_field(
            name="{eval:<tagscript>}",
            value=textwrap.dedent("""\
                Re-parse content as TagScript after resolving sub-engines.
                `{eval:{text:attachment}}` — load file then execute it as a tag
                `{eval:Hello {user}}` — resolve variables inside dynamic content
                Nesting depth limit: 3.\
            """),
            inline=False,
        )
        embed.add_field(
            name="{embedjson:{…}}",
            value=(
                "Build a Discord embed from JSON.\n"
                "Fields: `title` `description` `url` `color` `timestamp` "
                "`footer` `author` `thumbnail` `image` `fields`\n"
                "Example: `{embedjson:{\"title\":\"Hello\",\"color\":5765000}}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="{ihtx:reps dur noTrim fmt effects}",
            value=(
                "Run the IHTX effect chain on the attached file.\n"
                "Example: `{ihtx:1 10 false mp4 huehsv,negate,speed=1.5}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="{iscript:…} — image processing",
            value=textwrap.dedent("""\
                `load_attachment` / `load URL`
                `blur N` · `sharpen N` · `grayscale` · `negate` · `sepia`
                `brightness N` · `contrast N` · `rotate DEG`
                `resize WxH` · `thumbnail WxH` · `flip` · `flop`
                `pixelate N` · `output jpg|png|gif|webp`\
            """),
            inline=False,
        )
        embed.add_field(
            name="{mediascript:…} — media processing",
            value=textwrap.dedent("""\
                `load_attachment` / `load URL`
                `scale WxH` · `fps N` · `trim START END` · `speed FACTOR`
                `volume LEVEL` · `strip_audio` · `reverse` · `grayscale`
                `rotate DEG` · `loop N` · `fade_in S` · `fade_out S`
                `gif` · `output mp4|gif|mp3|webm|wav`\
            """),
            inline=False,
        )
        embed.add_field(
            name="Permissions",
            value=textwrap.dedent("""\
                **Create** — everyone (re-create your own tag = edit)
                **Edit / Delete / Rename** — tag creator · bot owner
                **Bot owner** overrides all ownership checks and is audit-logged.\
            """),
            inline=False,
        )
        await ctx.reply(embed=embed)
