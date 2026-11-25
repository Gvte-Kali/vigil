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
    def test_supervisor_publishes_report_after_an_abnormal_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with patch.multiple(session, HELPER=Path(tmp) / "missing-helper"), \
                    patch("vigil.session.os.geteuid", return_value=1000), \
                    patch("vigil.session.default_database", return_value=state), \
                    patch("vigil.session.mount_check", return_value={"status": "clear"}), \
                    patch("vigil.session.subprocess.Popen") as popen, \
                    patch("vigil.session.launch_terminal") as terminal:
                popen.return_value.pid = 1234
                popen.return_value.wait.return_value = -11
                self.assertEqual(session.supervise([]), 139)
            path = Path(terminal.call_args.args[0][-1])
            report = json.loads(path.read_text())
            self.assertEqual(report["exit_status"], -11)
            self.assertEqual(report["hotplug"]["status"], "not_installed")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_crash_report_offers_scoped_retry_and_waits_for_enter(self):
        report = {"exit_status": -11, "error": "", "language": "en",
                  "mounts": {"status": "clear"}, "hotplug": {"status": "unavailable"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            with patch("vigil.session.HELPER", Path(__file__)), patch("vigil.session.show_logo"), \
                    patch("builtins.input", side_effect=["r", ""]) as prompt, \
                    patch("vigil.session.subprocess.run", return_value=subprocess.CompletedProcess(
                        [], 0, stdout='{"status":"complete","devices":[]}',
                    )) as command, redirect_stdout(io.StringIO()) as output:
                session.show_report(report, path, interactive=True)
            self.assertEqual(command.call_args.args[0][-1], "recover")
            self.assertEqual(prompt.call_count, 2)
            self.assertIn("Unexpected exit (signal 11)", output.getvalue())
            self.assertIn("Press Enter", prompt.call_args.args[0])
            self.assertEqual(json.loads(path.read_text())["recovery_retry"]["status"], "complete")
