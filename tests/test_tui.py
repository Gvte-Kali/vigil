import tempfile
import unittest
from pathlib import Path

from textual.widgets import DataTable, Input, Static
from typer.testing import CliRunner

from vigil import storage
from vigil.cli import app
from vigil.tui import Workspace


class TerminalWorkspaceTest(unittest.IsolatedAsyncioTestCase):
    async def test_case_and_local_evidence_flow_in_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            source = Path(tmp) / "fixture [bold].txt"
            source.write_text("Vigil fixture")
            workspace = Workspace(state, language="en")
            async with workspace.run_test(size=(104, 34)) as pilot:
                await pilot.click("#--content-tab-entity")
                await pilot.pause()
                workspace.query_one("#operator-name", Input).value = "Alice"
                self.assertTrue(await pilot.click("#set-operator"))
                await pilot.pause()
                await pilot.click("#--content-tab-cases")
                await pilot.pause()
                workspace.query_one("#case-name", Input).value = "Example [bold]"
                self.assertTrue(await pilot.click("#create-case"))
                await pilot.pause()
                self.assertEqual(workspace.query_one("#case-table", DataTable).row_count, 1)
                self.assertIsNone(workspace.active_case)
                self.assertTrue(await pilot.click("#activate-case"))
                await pilot.pause()
                self.assertIn("Alice  ·  Example [bold]", str(workspace.query_one("#session", Static).render()))
                await pilot.click("#--content-tab-evidence")
                await pilot.pause()
                workspace.query_one("#evidence-path", Input).value = str(source)
                self.assertTrue(await pilot.click("#add-evidence"))
                await workspace.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(workspace.query_one("#evidence-table", DataTable).row_count, 1)
                self.assertTrue(await pilot.click("#verify-evidence"))
                await workspace.workers.wait_for_complete()
                with storage.database(state) as connection:
                    actions = {r[0] for r in connection.execute("SELECT action FROM audit")}
                self.assertIn("evidence.verify", actions)

    def test_explicit_interface_commands_are_available_without_running_them(self):
        runner = CliRunner()
        for command in ("tui", "gui"):
            result = runner.invoke(app, [command, "--help"])
            self.assertEqual(result.exit_code, 0, result.output)
        result = runner.invoke(app, ["tui"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("interactive terminal", result.output)
