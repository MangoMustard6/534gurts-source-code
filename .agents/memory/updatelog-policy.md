---
name: updatelog-policy
description: Policy for keeping _UPDATELOG in bot/ihtx_bot.py current whenever changes are made to the bot.
---

# Update Log Policy

**Rule:** Every time changes are made to `bot/ihtx_bot.py`, add or update the top entry in `_UPDATELOG` (at the top of the list, before older entries).

**Why:** The user explicitly asked that the update log reflect bot changes. `t!updatelog` (aliases: `t!updates`, `t!changelog`) displays this list to Discord users.

**How to apply:**
- `_UPDATELOG` is at the bottom of `bot/ihtx_bot.py`, just before the `@bot.hybrid_command(name="updatelog" ...)` decorator.
- The list is newest-first. Add a new dict at the top of the list, or append to the current version's bullet lists if the version date matches today.
- Format: `{"version": "vX.Y", "date": "YYYY-MM-DD", "heavy": [...], "fun": [...], "owner": []}` — omit or leave empty lists for categories with no changes.
- Version: increment the minor number (e.g. v1.7 → v1.8) for each session's batch of changes.
- Bullet format: `"**t!commandname** — what changed and why"`
