---
name: File export and owner shell
description: Durable design constraints for attachment JSON exports and the bot's owner-only shell utility.
---

Attachment export and shell execution are separate cogs and separate commands. Export uses a parser registry with raw base64 fallback; the shell utility is owner-only, asynchronously executed, time-limited, and audit-logged.

**Why:** File parsing is a bounded data transformation, while shell execution is a powerful administrative capability that needs a distinct audit and access boundary.

**How to apply:** Add new export formats to the parser registry, keep the shared owner registry as the authority, and support exact `!export`/`!bash` spellings through listeners rather than enabling `!` for every bot command.