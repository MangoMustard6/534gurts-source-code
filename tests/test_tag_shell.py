import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot.tags.engines.bash_engine import BashEngine
from bot.tags.parser import parse


class ShellTagParsingTests(unittest.TestCase):
    def test_sh_block_resolves_tag_vars_and_preserves_bash_vars(self):
        text, blocks = parse(
            r"{sh:printf '%s' \"${FILE_1##*.}\"; echo {username}}",
            {"username": "Ada"},
        )

        self.assertEqual(text, "")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["engine"], "bash")
        self.assertIn("${FILE_1##*.}", blocks[0]["content"])
        self.assertIn("Ada", blocks[0]["content"])


class ShellTagExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_cannot_run_shell_from_non_owner_authored_tag(self):
        ctx = SimpleNamespace(author=SimpleNamespace(id=42))
        fake_bot = SimpleNamespace(owner_ids={42})

        with patch.dict(sys.modules, {"bot.ihtx_bot": fake_bot}):
            result = await BashEngine().execute(
                "echo should-not-run",
                ctx,
                {"tag_owner_id": 99},
            )

        self.assertEqual(
            result.error,
            "bash: only bot-owner-authored tags may run shell code",
        )

    async def test_non_owner_cannot_run_shell_from_owner_authored_tag(self):
        ctx = SimpleNamespace(author=SimpleNamespace(id=99))
        fake_bot = SimpleNamespace(owner_ids={42})

        with patch.dict(sys.modules, {"bot.ihtx_bot": fake_bot}):
            result = await BashEngine().execute(
                "echo should-not-run",
                ctx,
                {"tag_owner_id": 42},
            )

        self.assertEqual(result.error, "bash: restricted to bot owners")

    async def test_owner_tag_can_run_shell_and_find_installed_binaries(self):
        ctx = SimpleNamespace(author=SimpleNamespace(id=42))
        fake_bot = SimpleNamespace(owner_ids={42})

        with patch.dict(sys.modules, {"bot.ihtx_bot": fake_bot}):
            result = await BashEngine().execute(
                "type -P ffmpeg",
                ctx,
                {"tag_owner_id": 42},
            )

        self.assertFalse(result.error)
        self.assertIn("/ffmpeg", result.text)


if __name__ == "__main__":
    unittest.main()
