---
name: Gradientmap cross-bot implementation
description: How `gradientmap`/`gmap` is implemented in both Python and TypeScript bots, and the FFmpeg filtergraph shape it requires.
---

Both bots share the same `gradientmap`/`gmap` syntax and color-stop model (`ColorStop` = R, G, B, optional A, optional pos).

**Python bot (`bot/ihtx_bot.py`)**
- The effect is registered in `PIPE_EFFECT_NAMES` and handled inside `_apply_pipe_effects`.
- Color-stop params must be added to the per-call `_RAW_ARG_EFFECTS` set so they skip `_preprocess_param` math expansion. Without this, comma/colon-separated color values like `0,0,0` get collapsed by the math parser.
- The FFmpeg graph is a `-filter_complex` (not `-vf`) that splits the input into three branches, applies grayscale+curves per channel, merges the alpha branch, and overlays the colored result back onto the original. It must end with a named output label and an explicit `format=yuv420p` conversion, e.g. `...overlay,format=yuv420p[v]` and `-map "[v]"`.

**TypeScript bot (`artifacts/discord-bot/src/commands/gradientmap.ts`)**
- The same filtergraph shape is used, but earlier code incorrectly passed it to `-vf` (which only accepts a single-chain filter). It must use `-filter_complex` with `-map "[v]"`.
- Curve values contain spaces, so they must be quoted inside the filter string: `curves=r='...':g='...':b='...'`.

**Why this matters:** A filtergraph that uses `split`, `alphamerge`, and `overlay` is inherently multi-input. Using `-vf` or omitting the named `[v]` output / final yuv420p conversion makes FFmpeg fail with "No filters specified", "Output with label 'v' does not exist", or similar graph errors.
