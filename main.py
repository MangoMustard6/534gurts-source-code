"""
IHTX Bot — entry point for `python3 main.py` or Replit workflow.

Delegates to bot/ihtx_bot.py which contains the full Discord bot.
"""

import os
import sys

def main():
    # Replit sets DISCORD_TOKEN as a secret / env var
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN environment variable not set.", file=sys.stderr)
        print("Set it via Replit Secrets or your shell before running.", file=sys.stderr)
        sys.exit(1)

    # Use uvloop for faster async I/O if available
    try:
        import uvloop
        uvloop.install()
        print("uvloop installed — using fast event loop.")
    except ImportError:
        print("uvloop not available, using default asyncio event loop.")

    # Import and run the bot module
    from bot import ihtx_bot
    ihtx_bot.bot.run(token)


if __name__ == "__main__":
    main()
