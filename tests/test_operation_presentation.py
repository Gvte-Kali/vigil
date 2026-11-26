import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from vigil.external_terminal import prepare_tracked
from vigil.quick_actions import acquisition_command


ROOT = Path(__file__).resolve().parents[1]


class OperationPresentationTest(unittest.TestCase):
    def test_tracked_operation_uses_explicit_interface(self):
        with tempfile.TemporaryDirectory() as temporary:
            for interface, inherited, expected in (("gui", "1", "classic"), ("tui", "", "1")):
                command = [sys.executable, "-c",
                           'import os; print(os.environ.get("VIGIL_EMBEDDED_TERMINAL", "classic"))']
                _, argv = prepare_tracked(command, Path(temporary), {}, interface=interface)
                result = subprocess.run(argv, capture_output=True, text=True, check=True,
                                        env={**os.environ, "VIGIL_EMBEDDED_TERMINAL": inherited})
                self.assertEqual(result.stdout.splitlines()[0], expected)
                raw = acquisition_command("image", interface=interface)
                self.assertEqual(raw[raw.index("--interface") + 1], interface)

    def test_raw_internal_menu_retries_and_returns_distinct_codes(self):
        script = ROOT / "scripts/imager/vigil_acquire_triage.sh"
        with tempfile.TemporaryDirectory() as temporary:
            for text, status in (("wrong\ni\n", 3), ("q\n", 1)):
                result = subprocess.run(["bash", str(script), "triage", temporary, temporary, "Source", "internal"],
                                        input=text, text=True, capture_output=True,
                                        env={**os.environ, "VIGIL_LANG": "en", "NO_COLOR": "1"})
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("disconnect/reconnect triage", result.stderr)
                self.assertIn("list eligible read-only sources", result.stderr)
                if status == 3:
                    self.assertIn("Invalid choice.", result.stderr)

    def test_storage_preflight_reports_group_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            alias = root / "alias"
            alias.symlink_to(root, target_is_directory=True)
            command = ['sh', '-c', '. "$1"; . "$2"; stat() { echo 0:100:755; }; '
                       'vigil_storage_root_check "$3"', 'test',
                       str(ROOT / 'scripts/lib/vigil-terminal.sh'), str(ROOT / 'scripts/lib/vigil-storage-root.sh')]
            for path, expected in ((root, "0:100:755"), (alias, "répertoire réel")):
                result = subprocess.run([*command, str(path)], capture_output=True, text=True,
                                        env={**os.environ, "VIGIL_LANG": "fr"})
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stdout)
