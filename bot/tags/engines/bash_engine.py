"""
bash: engine — execute a shell command and return stdout.

Aliases: bash, sh

SECURITY: Restricted to bot owners only.

Limits:
  Timeout : 300 seconds
  Output  : 4 000 characters max
  Stderr  : merged into stdout

Usage (prefix syntax):
    sh:
    echo Hello World

    bash:
    date +"%Y-%m-%d"

Usage (brace syntax):
    {bash:echo Hello World}
"""

import asyncio
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from . import BaseEngine, EngineResult

_TIMEOUT = 300.0
_MAX_OUTPUT = 4_000
_MAX_INPUT_BYTES = 150 * 1024 * 1024

# Older saved media tags commonly start with `load {iv}`. That directive
# belongs to ImageScript/MediaScript, but those tags were sometimes stored as
# Bash blocks and then leaked into the shell as a literal `load` command.
_LOAD_LINE_RE = re.compile(r"^\s*load(?:_attachment)?(?:\s+(\S+))?(?:\s+\w+)?\s*$", re.IGNORECASE)


class BashEngine(BaseEngine):
    name = "bash"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        try:
            from bot.ihtx_bot import owner_ids
            is_owner = ctx.author.id in owner_ids
        except Exception:
            is_owner = False

        if not is_owner:
            return EngineResult(error="bash: restricted to bot owners")

        cmd = content.strip()
        if not cmd:
            return EngineResult(error="bash: no command provided")

        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        try:
            # Brace blocks inside a Bash script are tag syntax, not Bash
            # syntax. The outer parser extracts `{sh:...}` as one engine
            # block, so resolve the inner `{iv}`, `{arg:0}`, `{arg:5+}`, etc.
            # here before handing the script to Bash.
            from bot.tags.parser import resolve_blocks, resolve_variables

            cmd = resolve_variables(cmd, tag_ctx)
            cmd, _ = resolve_blocks(cmd, tag_ctx)

            # Translate the legacy media preamble into the FILE_1 convention
            # used by the IHTX Bash tags. The `load` line must never reach
            # Bash: it is a tag-engine directive, not a shell builtin.
            lines = cmd.splitlines()
            load_index = next(
                (i for i, line in enumerate(lines) if _LOAD_LINE_RE.match(line)),
                None,
            )
            env = os.environ.copy()
            if load_index is not None:
                load_match = _LOAD_LINE_RE.match(lines[load_index])
                source_url = (load_match.group(1) if load_match else "") or tag_ctx.get("iv", "")
                if not source_url or not source_url.lower().startswith(("http://", "https://")):
                    return EngineResult(error="bash: load requires an attachment or http(s) URL")

                suffix = Path(urlparse(source_url).path).suffix[:10] or ".bin"
                temp_dir = tempfile.TemporaryDirectory(prefix="tag-bash-")
                input_path = os.path.join(temp_dir.name, f"input{suffix}")
                timeout = aiohttp.ClientTimeout(total=60)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(source_url) as response:
                        if response.status != 200:
                            return EngineResult(error=f"bash: load failed (HTTP {response.status})")
                        size = 0
                        with open(input_path, "wb") as output:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                size += len(chunk)
                                if size > _MAX_INPUT_BYTES:
                                    return EngineResult(error="bash: loaded file exceeds 150 MB")
                                output.write(chunk)
                env["FILE_1"] = input_path
                lines.pop(load_index)
                cmd = "\n".join(lines).strip()
                if not cmd:
                    return EngineResult(error="bash: no command provided after load")

            # FFmpeg writes a large build/configuration banner to stderr
            # before doing any work. Since stderr is intentionally merged into
            # the tag result, hide that banner while preserving real errors.
            # A shell function covers every ffmpeg invocation in the script,
            # including commands inside loops and conditionals.
            cmd = 'ffmpeg() { command ffmpeg -hide_banner -loglevel error "$@"; }\n' + cmd

            # Do not use create_subprocess_shell here: Python delegates that
            # API to /bin/sh, even though this engine is explicitly called
            # "bash". That makes valid Bash tag content fail with errors such
            # as "/bin/sh: load: not found" and breaks Bash-only syntax.
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-lc",
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        except asyncio.TimeoutError:
            return EngineResult(error=f"bash: command timed out ({_TIMEOUT:.0f}s)")
        except Exception as exc:
            return EngineResult(error=f"bash: {exc}")
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

        text = out.decode("utf-8", errors="replace").strip()
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + f"\n… (truncated to {_MAX_OUTPUT} chars)"

        return EngineResult(text=text or "(no output)")
