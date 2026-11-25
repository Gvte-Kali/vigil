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
                await pilot.click("#nav-entity")
                await pilot.pause()
                workspace.query_one("#operator-name", Input).value = "Alice"
                workspace.query_one("#set-operator").scroll_visible(immediate=True)
                await pilot.pause()
                self.assertTrue(await pilot.click("#set-operator"))
                await pilot.pause()
                await pilot.click("#nav-cases")
                await pilot.pause()
                self.assertTrue(await pilot.click("#create-case"))
                workspace.screen.query_one("#field-name", Input).value = "Example [bold]"
                self.assertTrue(await pilot.click("#confirm"))
                await workspace.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(workspace.query_one("#case-table", DataTable).row_count, 1)
                self.assertIsNone(workspace.active_case)
                self.assertTrue(await pilot.click("#activate-case"))
                await pilot.pause()
                self.assertIn("Alice\nExample [bold]", str(workspace.query_one("#session", Static).render()))
                await pilot.click("#--content-tab-evidence")
                await pilot.pause()
                workspace.screen.query_one("#evidence-path", Input).value = str(source)
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

    async def test_shell_navigation_and_tabs_match_workspace_order(self):
        from textual.widgets import Button, TabPane

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / "cases.sqlite", language="fr", operator="Alice")
            async with workspace.run_test(size=(100, 32)) as pilot:
                self.assertEqual([button.id for button in workspace.query("#sidebar Button")],
                                 ["nav-dashboard", "nav-cases", "nav-quick", "nav-entity", "nav-catalogue"])
                self.assertEqual([pane.id for pane in workspace.query("#workspace-tabs TabPane")],
                                 ["sources", "explorer", "evidence", "analyses", "history", "reports", "export"])
                self.assertTrue(await pilot.click("#language"))
                await pilot.pause()
                self.assertEqual(str(workspace.query_one("#nav-cases", Button).label), "Current case")
                await pilot.resize_terminal(76, 25)
                await pilot.click("#sidebar-toggle")
                self.assertTrue(workspace.query_one("#sidebar").has_class("compact"))
                await pilot.pause(0.3)
                await pilot.press("enter")
                await pilot.pause()
                self.assertFalse(workspace.query_one("#sidebar").has_class("compact"))
                self.assertTrue(await pilot.click("#nav-quick"))
                self.assertEqual(workspace.current_page, "quick")
                self.assertEqual([button.id for button in workspace.query("#acquisition-group Button")],
                                 ["clone", "raw"])

    async def test_embedded_terminal_disables_visible_echo_for_secret_prompt(self):
        import sys

        from textual.widgets import Button
        from vigil.tui_screens import Operation

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / "cases.sqlite", language="en", operator="Alice")
            async with workspace.run_test(size=(90, 28)) as pilot:
                operation = Operation("Fixture", workspace.tr, [sys.executable, "-c", """
import sys, termios
fd = sys.stdin.fileno()
attrs = termios.tcgetattr(fd)
attrs[3] &= ~termios.ECHO
termios.tcsetattr(fd, termios.TCSANOW, attrs)
print('Secret: ', end='', flush=True)
assert input() == 'fixture-secret'
print('Copied', flush=True)
"""], "en")
                workspace.push_screen(operation)
                await pilot.pause(0.35)
                field = operation.query_one(Input)
                self.assertTrue(field.password)
                field.value = "fixture-secret"
                await pilot.press("enter")
                await workspace.workers.wait_for_complete()
                self.assertEqual(operation.status, 0)
                self.assertFalse(operation.query_one("#operation-close", Button).disabled)

    async def test_action_cards_reflow_and_header_remains_compact(self):
        from textual.widgets import Button
        from vigil.tui_widgets import ActionCard, icon
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / "cases.sqlite", operator="Alice")
            async with workspace.run_test(size=(120, 32)) as pilot:
                self.assertTrue(await pilot.click("#nav-quick"))
                cards = list(workspace.query("#antivirus-group ActionCard"))
                self.assertEqual(len(cards), 3)
                self.assertTrue(all(isinstance(card, ActionCard) for card in cards))
                group = workspace.query_one("#antivirus-group")
                self.assertLess(group.query_one(".heading").region.y, group.query_one(".section-description").region.y)
                self.assertLess(group.query_one(".section-description").region.y, cards[0].region.y)
                for width, height, columns in ((120, 32, 3), (80, 24, 2), (46, 20, 1), (120, 32, 3)):
                    await pilot.resize_terminal(width, height)
                    await pilot.pause()
                    self.assertEqual(workspace.query_one("#header").region.height, 8)
                    self.assertEqual(len({card.region.x for card in cards}), columns)
                    self.assertTrue(all(0 < card.region.width <= 30 for card in cards))
                cards[0].focus()
                await pilot.pause()
                self.assertIs(workspace.focused, cards[0])
                self.assertEqual(workspace.query_one("#quick-scan", Button).label.plain, "Scan antivirus")
                with patch.dict("os.environ", {"VIGIL_ASCII": "1"}):
                    self.assertTrue(icon("scan").isascii())

    async def test_supervised_start_requests_protection_without_opening_old_reports(self):
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / "cases.sqlite", language="en", operator="Alice")
            async with workspace.run_test(size=(90, 30)) as pilot:
                with patch.dict("os.environ", {"VIGIL_SESSION_GUARD": "12345", "VIGIL_SESSION_PENDING": '["old"]'}), \
                        patch("vigil.tui.Path.is_file", return_value=True), \
                        patch.object(workspace, "launch_workflow", AsyncMock()) as launch:
                    await workspace.offer_protection()
                    launch.assert_awaited_once_with("protect", {}, None, "Alice")
                await pilot.pause()

    async def test_operation_progress_is_separated_by_stage(self):
        import sys

        from textual.widgets import ProgressBar
        from vigil.tui_screens import Operation, TerminalLines

        lines = TerminalLines()
        self.assertEqual(lines.feed("old\r"), [])
        self.assertEqual(lines.feed("new\r"), [])
        self.assertEqual(lines.feed("\n"), ["new"])
        self.assertEqual(lines.feed("prompt"), [])
        self.assertEqual(lines.pending, "prompt")

        script = """
import json
for stage, percent in [('Copie', 50), ('Copie', 100), ('Vérification SHA-256', 40)]:
    print(chr(30) + 'VIGIL_PROGRESS ' + json.dumps({'stage': stage, 'percent': percent}), flush=True)
print('résultat conservé')
"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / "cases.sqlite", operator="Alice")
            async with workspace.run_test(size=(80, 24)) as pilot:
                operation = Operation("Fixture", workspace.tr, [sys.executable, "-c", script], "fr")
                await workspace.push_screen(operation)
                await pilot.pause()
                await workspace.workers.wait_for_complete()
                self.assertEqual(operation.status, 0)
                self.assertEqual(list(operation.stages), ["Copie", "Vérification SHA-256"])
                self.assertEqual([stage.query_one(ProgressBar).progress for stage in operation.stages.values()],
                                 [100, 40])
