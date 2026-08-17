---
name: BOT_OWNER_ID required policy
description: User requires BOT_OWNER_ID to always be a mandatory secret with no hardcoded default, in this and all future bot projects.
---

# BOT_OWNER_ID Required Policy

**Rule:** `BOT_OWNER_ID` must always be a required secret — never use a hardcoded default Discord user ID as a fallback.

**Why:** The user explicitly requested this. A hardcoded owner ID is a security risk (wrong person gets owner perms) and a maintenance hazard across forks/copies.

**How to apply:**
- Python bots: read `os.environ.get("BOT_OWNER_ID")`, check it is truthy, and `sys.exit(1)` with a clear error if missing. Never pass a default to `.get()`.
- TypeScript bots: read `process.env.BOT_OWNER_ID`, check it is truthy immediately at startup (alongside the token check), and `process.exit(1)` if missing.
- Always list `BOT_OWNER_ID` as a required secret in `replit.md`.
- Request it via `requestSecrets` when setting up secrets for the user.
