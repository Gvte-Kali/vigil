import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from vigil import session


class SessionTest(unittest.TestCase):
    def test_supervisor_publishes_report_after_exit_or_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with patch.multiple(session, HELPER=Path(tmp) / "missing-helper"), \
                    patch("vigil.session.os.geteuid", return_value=1000), \
                    patch("vigil.session.default_database", return_value=state), \
                    patch("vigil.session.capture_startup_state", return_value=({}, state.parent / "snapshot.json")), \
                    patch("vigil.session.mount_check", return_value={"status": "clear"}), \
                    patch("vigil.session.subprocess.Popen") as popen, \
                    patch("vigil.session.launch_terminal") as terminal:
                popen.return_value.pid = 1234
                for status in (0, 1, -11, -15, -9):
                    with self.subTest(status=status):
                        popen.return_value.wait.return_value = status
                        self.assertEqual(session.supervise([]), status if status >= 0 else 128 - status)
                        path = Path(terminal.call_args.args[0][-1])
                        report = json.loads(path.read_text())
                        self.assertEqual(report["exit_status"], status)
                        self.assertTrue(report["snapshot"].endswith("snapshot.json"))
                        self.assertEqual(report["hotplug"]["status"], "not_installed")
                        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_crash_report_offers_scoped_retry_and_waits_for_enter(self):
        report = {"exit_status": -11, "error": "", "language": "en",
                  "mounts": {"status": "clear"}, "hotplug": {"status": "unavailable"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            with patch("vigil.session.HELPER", Path(__file__)), patch("vigil.session.show_logo"), \
                    patch("builtins.input", side_effect=["r", ""]) as prompt, \
                    patch("vigil.session.mount_check", return_value={"status": "clear"}), \
                    patch("vigil.session.subprocess.run", return_value=subprocess.CompletedProcess(
                        [], 0, stdout='{"status":"complete","devices":[]}',
                    )) as command, redirect_stdout(io.StringIO()) as output:
                session.show_report(report, path, interactive=True)
            self.assertEqual(command.call_args.args[0][-1], "recover")
            self.assertEqual(prompt.call_count, 2)
            self.assertIn("Unexpected exit (signal 11)", output.getvalue())
            self.assertIn("Press Enter", prompt.call_args.args[0])
            self.assertEqual(json.loads(path.read_text())["recovery_retry"]["status"], "complete")


    def test_stale_and_corrupt_journals_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, contents in {
                "stale": '{"status":"open","pid":123,"owner":"123-999.json"}',
                "live": '{"status":"open","pid":456,"owner":"456-10.json"}',
                "closed": '{"status":"closed"}',
                "bad": "{",
            }.items():
                (root / f"{name}.json").write_text(contents)
            with patch("vigil.session.receipt_path", side_effect=lambda pid: root / f"{pid}-10.json"):
                self.assertEqual(set(session.pending_sessions(root)), {"stale.json", "bad.json"})

    def test_previous_session_is_closed_only_after_verified_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            identifier = "a" * 32
            journal = session.session_record(state, identifier)
            session.write_state(journal, {"status": "open", "pid": 12, "session": identifier})
            candidates = [journal.name]
            with patch("vigil.session.HELPER", Path(__file__)), \
                    patch("vigil.session.sys.stdin.isatty", return_value=True), \
                    patch("vigil.session.check_shutdown_state") as check, \
                    patch("vigil.session.subprocess.run") as command:
                command.return_value.returncode = 1
                self.assertEqual(session.recover_before_startup(state, candidates, terminal_workspace=True),
                                 candidates)
                command.return_value.returncode = 0
                self.assertEqual(session.recover_before_startup(state, candidates, terminal_workspace=True), [])
                self.assertEqual(check.call_count, 3)
            self.assertTrue(json.loads(journal.read_text())["recovered_at_startup"])

    def test_recovery_rejects_unverified_devices(self):
        outcome = {"status": "complete", "devices": [{"state": "unverified"}]}
        with patch("vigil.session.restore_system", return_value=outcome), \
                patch("vigil.session.check_shutdown_state"), redirect_stdout(io.StringIO()):
            self.assertEqual(session.startup_recovery_command(), 1)

    def test_independently_running_writer_holds_session_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "test"
            directory.mkdir()
            (directory / "context.json").write_text('{"vigil_session":"test","operation":"clone"}')
            (directory / "started.json").write_text(
                '{"pid":12,"start":"123","child":{"pid":24,"start":"521"}}'
            )
            with patch("vigil.external_operation.process_start", side_effect=lambda pid: "521" if pid == 24 else "999"):
                self.assertEqual(session.active_runs(root, "test"), ["clone"])
                (directory / "result.json").write_text('{"exit_code":0}')
                self.assertEqual(session.active_runs(root, "test"), [])

    def test_detached_terminal_tries_another_emulator_after_failure(self):
        from vigil import external_terminal

        with patch.object(external_terminal, "terminal_commands", return_value=iter([["first"], ["next"]])), \
                patch.object(external_terminal.subprocess, "Popen") as popen:
            popen.return_value.wait.side_effect = [1, subprocess.TimeoutExpired("next", 0.25)]
            external_terminal.launch_terminal(["fixture"], detached=True)
        self.assertEqual([call.args[0] for call in popen.call_args_list], [["first"], ["next"]])
        self.assertTrue(all(call.kwargs["start_new_session"] for call in popen.call_args_list))
