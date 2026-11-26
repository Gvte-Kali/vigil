import selectors
import sys
import tempfile
import unittest
from pathlib import Path

from vigil.runner import TerminalProcess


class RunnerTest(unittest.TestCase):
    def test_interactive_controlling_terminal(self):
        code = (
            'import os; fd = os.open("/dev/tty", os.O_RDONLY); '
            'print("size:", os.get_terminal_size(fd).columns); '
            'print("response:", input("name? "))'
        )
        with tempfile.TemporaryDirectory() as tmp, TerminalProcess(
            [sys.executable, "-c", code], Path(tmp), {"TERM": "xterm"}
        ) as terminal, selectors.DefaultSelector() as selector:
            selector.register(terminal.master, selectors.EVENT_READ)
            output = b""
            for _ in range(10):
                self.assertTrue(selector.select(timeout=2))
                output += terminal.read()
                if b"name? " in output:
                    break
            self.assertIn(b"size: 80", output)
            self.assertIn(b"name? ", output)
            terminal.write(b"fixture\n")
            for _ in range(10):
                self.assertTrue(selector.select(timeout=2))
                output += terminal.read()
                if b"response: fixture" in output:
                    break
            self.assertIn(b"response: fixture", output)
            self.assertEqual(terminal.process.wait(timeout=2), 0)

    def test_cancel_reaps_child(self):
        with tempfile.TemporaryDirectory() as tmp, TerminalProcess(
            [sys.executable, "-c", "import time; time.sleep(60)"], Path(tmp), {}
        ) as terminal:
            self.assertLess(terminal.cancel(), 0)
