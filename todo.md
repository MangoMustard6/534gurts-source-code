# IHTX Audio & Video Filter Subsystem Migration

## Task 1: Remove Rule34 (t!r34) References [x]
- No Rule34 command, API routes, or references found in the codebase. Already clean.

## Task 2: Convert Real G-Major 4 to TypeScript Command [x]
- [x] Create `artifacts/discord-bot/src/commands/realgmajor4.ts` — production-ready TS command using discord.js + child process streams
- [x] Register command in `artifacts/discord-bot/src/index.ts` — add import and switch case
- [x] Add `REALGM4_MS` timeout to `artifacts/discord-bot/src/config.ts`
- [x] Remove `realgmajor4` command, aliases, `_run_realmajor4` function, and pipe effect references from `bot/ihtx_bot.py`
- [x] Remove `realgmajor4/realgm4/rgm4` from `HEAVY_COMMANDS` set in `bot/ihtx_bot.py`
- [x] Remove `realgmajor4/realgm4/rgm4` from `PIPE_EFFECT_NAMES` set in `bot/ihtx_bot.py`
- [x] Update `artifacts/discord-bot/src/commands/help.ts` — replace realgm4 pipe mention, add new command entry

## Task 3: Integrate RandomJitter into effects.ts [x]
- [x] Create `artifacts/discord-bot/src/effects.ts` — reusable effect functions module with `applyRandomJitter`
- [x] Integrate jitter logic using the exact pixel matrix calculation from the legacy source
- [x] Add `randomjitter` pipe effect to Python IHTX framework (PIPE_EFFECT_NAMES + handler)
- [x] Update help text to reference `randomjitter` pipe effect name

## Task 4: Cleanup & Verification [x]
- [x] Verify all TypeScript files compile correctly (typecheck)
- [x] Update command list log in `index.ts` ready message
- [x] Create PR branch and push changes — PR #26 created
