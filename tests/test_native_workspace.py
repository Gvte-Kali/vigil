import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.dev import workspace
from vigil import dev_mode, device_manager, session
from vigil.external_terminal import terminal_command
from vigil.images import inspect_raw


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts/post-install/install_native.py"


class NativeWorkspaceTest(unittest.TestCase):
    def test_install_plans_are_cumulative_and_never_write_in_dry_run(self):
        distros = {
            "arch": ("ID=omarchy\nID_LIKE=arch\n", "pacman", "python"),
            "debian": ("ID=parrot\nID_LIKE=debian\n", "apt-get", "python3-venv"),
            "fedora": ("ID=fedora\n", "dnf", "python3-pip"),
            "opensuse": ("ID=opensuse-tumbleweed\nID_LIKE=suse\n", "zypper", "python3-pip"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os_release = root / "os-release"
            venv = root / "spaces and accents é" / "venv"
            for family, (release, manager, python) in distros.items():
                os_release.write_text(release)
                for profile in ("minimal", "forensic", "complet"):
                    with self.subTest(family=family, profile=profile):
                        result = subprocess.run([sys.executable, str(INSTALL), "--os-release", str(os_release),
                                                 "--profile", profile, "--venv", str(venv), "--dry-run",
                                                 "--system-packages"], capture_output=True, text=True, check=True)
                        self.assertIn(f"Distribution: {family}", result.stdout)
                        self.assertIn(f"sudo {manager}", result.stdout)
                        self.assertIn(python, result.stdout)
                        self.assertEqual("sleuthkit" in result.stdout, profile != "minimal")
                        self.assertEqual(".[desktop]" in result.stdout, profile == "complet")
                        self.assertFalse(venv.parent.exists())

    def test_isolated_launch_avoids_supervisor_and_device_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = workspace.environment(root)
            state = root / "state/cases.sqlite"
            with patch.dict(os.environ, env, clear=True), \
                 patch("vigil.session.capture_startup_state") as snapshot, \
                 patch("vigil.session.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as process:
                self.assertEqual(session.supervise([], state=state), 0)
                self.assertEqual(process.call_args.args[0][-1], "vigil.desktop")
                self.assertEqual(session.supervise([], state=state, interface="tui"), 0)
                self.assertEqual(process.call_args.args[0][-1], "vigil.tui")
                snapshot.assert_not_called()
                with self.assertRaisesRegex(ValueError, "own database"):
                    dev_mode.validate(root / "other.sqlite")
                with self.assertRaisesRegex(ValueError, "System action disabled"):
                    device_manager.operate("mount", "/investigation", device="/dev/test")
                state.symlink_to(root / "other.sqlite")
                with self.assertRaisesRegex(ValueError, "own database"):
                    dev_mode.validate(state)

    def test_synthetic_raw_image_and_idempotent_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace.fixtures(root)
            workspace.fixtures(root)
            result = inspect_raw(root / "fixtures/disk.raw")
            self.assertEqual(result["partition_table"], "mbr")
            self.assertEqual(result["partitions"][0]["offset"], 512)
            specimen = root / "fixtures/specimen.txt"
            specimen.write_text("modified")
            with self.assertRaisesRegex(ValueError, "Existing fixture differs"):
                workspace.fixtures(root)
            self.assertEqual(specimen.read_text(), "modified")

    def test_ghostty_keeps_argument_boundaries(self):
        with patch("vigil.external_terminal.shutil.which", return_value="/usr/bin/ghostty"):
            self.assertEqual(terminal_command(["/path with spaces/command", "A B"], "ghostty"),
                             ["/usr/bin/ghostty", "-e", "/path with spaces/command", "A B"])
