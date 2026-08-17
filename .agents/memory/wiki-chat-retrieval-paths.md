---
name: Wiki chat retrieval paths
description: Logo Editing Wiki context must be attached to every AI response path.
---

Logo Editing Wiki retrieval is required in both direct chat and `autoreply2` responses. Named-page lookup should happen even when the question contains command words such as `th/mp2` or preset terminology.

**Why:** The direct chat path had wiki context, but autoreply2 only received the built-in command reference, causing it to answer named wiki effects with unrelated IHTX presets.

**How to apply:** When changing chatbot prompts or retrieval, inspect every Groq/Gemini message construction path and test a named page such as “G Major 74” through each one.

Named-effect lookups should search pages directly before crawling categories; reserve recursive indexing for explicit category-browsing questions.

**Why:** A category crawl could delay autoreply2 long enough to look like Discord failed to render the response.

**How to apply:** Keep direct page retrieval on the fast path and put bounded timeouts around category indexing.