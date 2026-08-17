---
name: Night Shift difficulty
description: Difficulty behavior for the interactive Night Shift game.
---

Night Shift supports `easy`, `normal`, and `hard` in both hybrid command forms.
Normal is the default; Easy reduces battery and threat pressure, while Hard
increases both.

**Why:** The game should be approachable for casual players without removing
the intended challenge or requiring separate game implementations.

**How to apply:** Keep difficulty validation shared between prefix and slash
invocations, show the selected mode in the embed, and scale resource drain and
threat movement from the difficulty configuration.