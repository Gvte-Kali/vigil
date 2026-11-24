import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vigil.core import discover
from vigil.inspection import PREVIEW_BYTES, inspect_file
from vigil.module_scaffold import create_module_draft
from vigil.quick_actions import legacy_mount_command, update_command
from vigil.storage import default_database


class WorkspaceToolsTest(unittest.TestCase):
    def test_historical_mount_uses_case_id_without_modifying_global_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = "a" * 32
            for action, script in (("mount", "vigil_usb_mount.sh"), ("unmount", "vigil_usb_umount.sh")):
                argv = legacy_mount_command(action, root / "cases.sqlite", case, "../case", "Alice")
                self.assertIn("VIGIL_LEGACY_PROJECT=../case", argv)
                self.assertIn(f"VIGIL_LEGACY_CASE_DIR={root / 'legacy-custody' / case}", argv)
                self.assertEqual(Path(argv[-1]).name, script)
            self.assertFalse((root / "active_project").exists())

    def test_site_launcher_state_is_separate_from_development(self):
        with patch.dict("os.environ", {
            "VIGIL_STATE_DIR": "/opt/vigil/data/state", "XDG_STATE_HOME": "/tmp/development",
        }):
            self.assertEqual(default_database(), Path("/opt/vigil/data/state/cases.sqlite"))

    def test_refresh_config_ignores_stale_configuration_and_handles_spaces(self):
        with tempfile.TemporaryDirectory(prefix="vigil test ") as tmp:
            directory = Path(tmp)
            signatures = directory / "clamav"
            signatures.mkdir()
            old = signatures / "freshclam.conf"
            old.write_text("Example\n")
            with patch("vigil.quick_actions.tool", return_value="/usr/bin/freshclam"):
                command = update_command(directory / "vigil.sqlite")
                update_command(directory / "vigil.sqlite")
            self.assertEqual(old.read_text(), "Example\n")
            config = signatures / "vigil-freshclam.conf"
            self.assertEqual(command[1], f"--config-file={config}")
            self.assertIn(f'DatabaseDirectory "{signatures}"', config.read_text())

    def test_preview_is_bounded_and_rejects_symbolic_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "fixture.txt"
            content = b"visible\x00" + b"x" * PREVIEW_BYTES + b"outside"
            file.write_bytes(content)
            preview = inspect_file(file)
            self.assertEqual(preview["bytes_read"], PREVIEW_BYTES)
            self.assertIn("visible", preview["strings"])
            self.assertNotIn("outside", preview["strings"])
            self.assertEqual(file.read_bytes(), content)
            link = file.with_name("link")
            link.symlink_to(file)
            with self.assertRaises(OSError):
                inspect_file(link)

    def test_draft_passes_manifest_validation_and_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.sqlite"
            target = create_module_draft(state, "fixture")
            manifests, errors = discover(target)
            self.assertIn("local.fixture", manifests)
            self.assertEqual(errors, {})
            with self.assertRaises(FileExistsError):
                create_module_draft(state, "fixture")
