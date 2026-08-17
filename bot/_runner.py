"""
bot/_runner.py — spawned by main.py launcher.
Runs the IHTX bot directly; exits naturally (non-zero) on crash so the
launcher can detect and restart it.
"""

import sys
import os

# Use uvloop for faster async I/O if available
try:
    import uvloop
    uvloop.install()
    print("uvloop installed — using fast event loop.", flush=True)
except ImportError:
    print("uvloop not available, using default asyncio event loop.", flush=True)

from bot import ihtx_bot


try:
    ihtx_bot.bot.run(os.environ["DISCORD_TOKEN"], reconnect=True)
except Exception as exc:
    # A global Discord login block is not a recoverable bot crash. Let the
    # launcher fail closed instead of retrying every few seconds and extending
    # the block.
    try:
        import discord
    except ImportError:
        discord = None

    if discord is not None and isinstance(exc, discord.HTTPException) and exc.status == 429:
        print(
            "[runner] Discord returned HTTP 429 during login; "
            "stopping without automatic retry.",
            flush=True,
            file=sys.stderr,
        )
        raise SystemExit(75)
    raise
