---
name: Discord Entry Point sync workaround
description: How to sync slash commands when the app has a type-4 Entry Point command (error 50240)
---

## Rule
Never use `bot.tree.sync()` or plain `bulk_upsert_global_commands` with only the tree's commands — Discord rejects it with error 50240 if the app has an Entry Point command (type=4, used by Discord Activities / App Launcher).

## The fix: `t!syncslash` command (bot/ihtx_bot.py)
```python
_SYNC_RO = {"application_id", "version"}
_existing = await bot.http.get_global_commands(bot.application_id)
_eps = [{k: v for k, v in c.items() if k not in _SYNC_RO}
        for c in _existing if c.get("type") == 4]
_payload = [cmd.to_dict() for cmd in bot.tree._global_commands.values()]
_payload.extend(_eps)
await bot.http.bulk_upsert_global_commands(bot.application_id, payload=_payload)
```

**Why:** Discord's bulk overwrite endpoint requires ALL global commands be present, including Entry Points. `tree.sync()` strips type=4 commands from its payload. Stripping `application_id` and `version` is required — they are server-assigned read-only fields that Discord rejects on POST.

**How to apply:** Any time new slash commands are added to bot.tree, the bot owner runs `t!syncslash` (aliases: synccmds, synctree, slashsync) in Discord. Do NOT attempt automatic on_ready sync — discord.py swallows exceptions from on_ready coroutines before a try/except can print them, making failures invisible in logs.

## This app's Entry Point
Name: `launch`, type: 4. Keys from Discord: `id, application_id, version, default_member_permissions, type, name, description, dm_permission, contexts, integration_types, nsfw, handler`.
