"""
py: engine — sandboxed Python code block.

Usage inside a tag:
    {py:
        result = int(args.split()[0]) * 2
        print(f"Double: {result}")
    }

- Only a safe subset of builtins is available.
- `args`, `user`, `server`, `channel`, `mention` are injected as globals.
- No imports, no file I/O, no network, no subprocess.
- Runs in a thread executor with a hard 5-second timeout.
- stdout is captured and returned as the block's text output.
"""

import asyncio
import io
import sys
from concurrent.futures import ThreadPoolExecutor

from . import BaseEngine, EngineResult

_SAFE_BUILTINS = {
    "__build_class__": __build_class__,
    "__name__": "__tag__",
    # Core types
    "bool": bool, "bytes": bytes, "bytearray": bytearray,
    "complex": complex, "dict": dict, "float": float, "frozenset": frozenset,
    "int": int, "list": list, "memoryview": memoryview, "range": range,
    "set": set, "slice": slice, "str": str, "tuple": tuple,
    # Builtins
    "abs": abs, "all": all, "any": any, "bin": bin, "callable": callable,
    "chr": chr, "divmod": divmod, "enumerate": enumerate, "filter": filter,
    "format": format, "hash": hash, "hex": hex, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len, "map": map,
    "max": max, "min": min, "next": next, "oct": oct, "ord": ord,
    "pow": pow, "print": print, "repr": repr, "reversed": reversed,
    "round": round, "sorted": sorted, "sum": sum, "type": type, "zip": zip,
    # Constants
    "True": True, "False": False, "None": None,
    # Safe exceptions
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError, "StopIteration": StopIteration,
    "AttributeError": AttributeError, "RuntimeError": RuntimeError,
    "NotImplementedError": NotImplementedError, "ArithmeticError": ArithmeticError,
    "ZeroDivisionError": ZeroDivisionError, "OverflowError": OverflowError,
}

_BLOCKED_PATTERNS = (
    "import ", "__import__", "open(", "exec(", "eval(", "compile(",
    "__class__", "__bases__", "__subclasses__", "__mro__", "__globals__",
    "__builtins__", "globals(", "locals(", "vars(", "dir(",
    "os.", "sys.", "subprocess", "socket", "shutil", "pathlib",
    "ctypes", "pickle", "marshal", "code.", "inspect",
)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pyscript")
_MAX_OUTPUT = 1000


def _run_sandboxed(code: str, tag_ctx: dict) -> tuple:
    """Execute code in restricted globals; return (stdout_str, error_str)."""
    buf = io.StringIO()
    safe_globals = dict(_SAFE_BUILTINS)
    safe_globals.update({
        "args": tag_ctx.get("args", ""),
        "user": tag_ctx.get("user", ""),
        "server": tag_ctx.get("server", ""),
        "channel": tag_ctx.get("channel", ""),
        "mention": tag_ctx.get("mention", ""),
    })
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        compiled = compile(code, "<tag:py>", "exec")
        exec(compiled, safe_globals, {})  # noqa: S102
        output = buf.getvalue()
        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + "\n… (truncated)"
        return output.strip(), ""
    except SyntaxError as exc:
        return "", f"SyntaxError: {exc}"
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"
    finally:
        sys.stdout = old_stdout


class PyScriptEngine(BaseEngine):
    name = "py"

    async def execute(self, content: str, ctx, tag_ctx: dict) -> EngineResult:
        code_lower = content.lower()
        for pattern in _BLOCKED_PATTERNS:
            if pattern in code_lower:
                safe = pattern.strip().rstrip("(").rstrip(".")
                return EngineResult(
                    error=f"py: `{safe}` is not allowed in tag scripts"
                )

        loop = asyncio.get_running_loop()
        try:
            output, error = await asyncio.wait_for(
                loop.run_in_executor(_executor, _run_sandboxed, content, tag_ctx),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            return EngineResult(error="py: timed out (5 s limit)")

        if error:
            return EngineResult(error=f"py: {error}")

        return EngineResult(text=output)
