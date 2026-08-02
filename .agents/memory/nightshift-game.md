---
name: Night Shift game
description: Architecture and rendering constraints for the procedural Discord horror minigame.
---

`/nightshift` is a Python-only interactive Discord game. Its visual frames are
painted with Pillow and streamed through `BytesIO`; it must not depend on
external image assets or filesystem frame output.

**Why:** The game requires deterministic, self-contained visuals while keeping
Discord updates in one message instead of creating a media-file pipeline.

**How to apply:** Keep game state isolated per channel/player, gate component
interactions to the initiating user, and update the existing message with a
fresh attachment whenever camera, door, power, threat, or ending state changes.