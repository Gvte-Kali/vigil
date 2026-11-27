"""Non-privileged syntax and language regression checks for maintenance and USB scripts."""
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATHS = (
    "scripts/lib/vigil-terminal.sh",
    "scripts/lib/vigil-device-select.sh",
    "scripts/lib/vigil-device-ops.sh",
    "scripts/lib/vigil-device-triage.sh",
    "scripts/post-install/post_install_vigil.sh",
    "scripts/post-install/uninstall.sh",
    "scripts/analyse/vigil_usb_mount.sh",
    "scripts/analyse/vigil_usb_umount.sh",
    "scripts/stockage/vigil_stockage_mount.sh",
    "scripts/stockage/vigil_stockage_umount.sh",
)


@unittest.skipUnless(shutil.which("bash"), "bash not installed")
class ScriptLocalizationTest(unittest.TestCase):
    def test_bash_syntax(self):
        for name in SCRIPT_PATHS:
            with self.subTest(script=name):
                result = subprocess.run(
                    ["bash", "-n", str(ROOT / name)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_language_selection_for_messages(self):
        command = (
            'source "$1"; '
            'VIGIL_LANG=en; '
            'vigil_text "Bonjour" "Hello"; '
            'printf "\\n"; '
            'VIGIL_LANG=fr; '
            'vigil_text "Bonjour" "Hello"; '
            'printf "\\n"'
        )
        result = subprocess.run(
            ["bash", "-c", command, "_",
             str(ROOT / "scripts/lib/vigil-terminal.sh")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["Hello", "Bonjour"])


if __name__ == "__main__":
    unittest.main()
