import io
import json
import runpy
import subprocess
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/privileged/vigil-hotplug"
hotplug = runpy.run_path(str(SCRIPT))


class HotplugTest(unittest.TestCase):
    def test_stale_session_token_is_discarded(self):
        active = hotplug["active"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            token = root / "1234"
            token.write_text("1000 123\n")
            with patch.dict(active.__globals__, {"SESSIONS": root,
                                                 "process_identity": lambda _: "1000 456"}):
                self.assertFalse(active())
            self.assertFalse(token.exists())

    def test_protection_failure_still_blocks_udisks_automount(self):
        protect = hotplug["protect"]
        with patch.dict(protect.__globals__, {"active": lambda: True, "state_lock": nullcontext}), \
                patch("os.open", side_effect=OSError("fixture failure")), \
                patch("sys.stderr", new=io.StringIO()), redirect_stdout(io.StringIO()) as output:
            protect("/dev/test", "8", "0")
        self.assertIn("VIGIL_HOTPLUG=1", output.getvalue())
        self.assertIn("VIGIL_HOTPLUG_RO=0", output.getvalue())


    def test_cleanup_restores_disks_before_partitions(self):
        restore = hotplug["restore_devices"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disk = {"device": "/dev/sdz", "partition": False}
            part = {"device": "/dev/sdz1", "partition": True}
            (root / "part").write_text(json.dumps(part))
            (root / "disk").write_text(json.dumps(disk))
            restored = []
            def absent(record):
                restored.append(record)
                return "absent"

            with patch.dict(restore.__globals__, {"ledger": lambda: root, "restore_device": absent}):
                restore()
            self.assertEqual(restored, [disk, part])
            self.assertEqual(list(root.iterdir()), [])


    def test_cleanup_keeps_receipt_for_unverified_udev_and_retries(self):
        cleanup = hotplug["cleanup"]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            record = directory / "disk"
            record.write_text(json.dumps({"device": "/dev/test", "partition": False,
                                          "mode": 0, "node": "/sys/devices/test"}))
            with patch.dict(cleanup.__globals__, {
                "state_lock": nullcontext, "active": lambda: False, "ledger": lambda: directory,
                "restore_device": lambda _: "restored",
            }), patch("subprocess.run") as run:
                run.return_value.stdout = "VIGIL_HOTPLUG_OWNS_IGNORE=1\n"
                self.assertEqual(cleanup()["devices"][0]["state"], "unverified")
                self.assertTrue(record.exists())
                run.return_value.stdout = ""
                self.assertEqual(cleanup()["devices"][0]["state"], "restored")
                self.assertFalse(record.exists())

    def test_cleanup_does_not_restore_during_another_session(self):
        cleanup = hotplug["cleanup"]
        with patch.dict(cleanup.__globals__, {"state_lock": nullcontext, "active": lambda: True}):
            self.assertEqual(cleanup(), {"status": "other_session", "devices": []})

    def test_startup_explains_protection_before_sudo_prompt(self):
        scripts = SCRIPT.parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lib").mkdir()
            (root / "lib/vigil-terminal.sh").write_bytes((scripts / "lib/vigil-terminal.sh").read_bytes())
            (root / "post-install").mkdir()
            script = root / "post-install/activate-hotplug.sh"
            # Keep the success branch runnable with a shell function replacing sudo.
            startup = (scripts / "post-install/activate-hotplug.sh").read_text().replace(
                "/usr/bin/sudo --", "mock_sudo --"
            ).replace("set -eu", "set -eu\nmock_sudo() { echo MOCK_SUDO; }")
            script.write_text(startup)
            result = subprocess.run(["/bin/sh", str(script), "123"], capture_output=True,
                                    text=True, check=True, timeout=5)
            output = result.stdout
            self.assertEqual(output.splitlines()[0], "Vigil")
            self.assertLess(output.index("FR — Autorisez sudo"), output.index("MOCK_SUDO"))
            self.assertLess(output.index("EN — Authorise sudo"), output.index("MOCK_SUDO"))
            self.assertIn("Protection enabled.", output)
            self.assertNotIn(chr(27), output)
