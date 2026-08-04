---
name: Multiple prefix dispatch
description: Message-event dispatch requirement when the bot supports multiple command prefixes.
---

When `commands.Bot` is configured with multiple prefixes, any custom `on_message` gate that decides whether to call `process_commands` must check all configured prefixes, not only the legacy primary prefix.

**Why:** A command can be registered and visible in the bot registry yet never run if the message event returns early for its prefix.

**How to apply:** Keep the prefix list centralized and use `any(message.content.startswith(prefix) for prefix in prefixes)` in dispatch gates.