---
name: VEB mention trigger
description: Behavior boundary between explicit VEB commands and passive Discord message listeners.
---

VEB random pipe effects are invoked through explicit `th/veb` commands only.
Mentioning the bot while replying to media must not automatically start processing.

**Why:** Passive mention processing is easy to confuse with ordinary media-reply
handling and can unexpectedly consume heavy-command quota or generate effects.

**How to apply:** Preserve media resolution for explicit commands, but do not
reintroduce an `on_message` listener that routes bot mentions into `ihtxgen`.