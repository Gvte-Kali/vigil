import io
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
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
        with patch.dict(protect.__globals__, {"active": lambda: True}), \
                patch("os.open", side_effect=OSError("fixture failure")), \
                patch("sys.stderr", new=io.StringIO()), redirect_stdout(io.StringIO()) as output:
            protect("/dev/test", "8", "0")
        self.assertIn("UDISKS_IGNORE=1", output.getvalue())
        self.assertIn("VIGIL_HOTPLUG_RO=0", output.getvalue())
