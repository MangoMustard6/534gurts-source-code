"""
IHTX Bot — self-restarting launcher for `python3 main.py` or Replit workflow.

Spawns bot/_runner.py in a subprocess. If the bot crashes (OOM from FFmpeg,
unhandled exception, etc.) the launcher detects the non-zero exit and
respawns it after a short delay — no Replit workflow restart needed.
"""

import os
import sys
import time
import subprocess


def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("BOT_OWNER_ID"):
        print("ERROR: BOT_OWNER_ID environment variable not set.", file=sys.stderr)
        sys.exit(1)

    delay = 5          # seconds before first restart
    max_delay = 60     # cap backoff at 60 s

    while True:
        print(f"[launcher] Starting bot...", flush=True)
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "bot._runner"],
            env=os.environ.copy(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        try:
            proc.wait()
        except KeyboardInterrupt:
            print("[launcher] Interrupted — shutting down.", flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            break

        code = proc.returncode
        if code == 0:
            print("[launcher] Bot exited cleanly.", flush=True)
            break
        if code == 75:
            print(
                "[launcher] Discord rejected login with HTTP 429. "
                "Stopping; start this workflow manually after the block clears.",
                flush=True,
                file=sys.stderr,
            )
            break

        print(
            f"[launcher] Bot exited with code {code}. "
            f"Restarting in {delay}s...",
            flush=True,
            file=sys.stderr,
        )
        time.sleep(delay)
        delay = min(delay * 2, max_delay)   # exponential backoff


if __name__ == "__main__":
    main()
