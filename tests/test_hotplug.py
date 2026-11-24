import io
import json
import runpy
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
            with patch.dict(restore.__globals__, {"ledger": lambda: root, "restore_device": restored.append}):
                restore()
            self.assertEqual(restored, [disk, part])
            self.assertEqual(list(root.iterdir()), [])
