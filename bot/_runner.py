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

ihtx_bot.bot.run(os.environ["DISCORD_TOKEN"], reconnect=True)
