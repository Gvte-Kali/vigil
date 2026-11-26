import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vigil.desktop_integration import checked_descriptor, graphical_user, prepare_view, reveal_in_file_manager


class DesktopIntegrationTest(unittest.TestCase):
    def test_viewing_copy_is_distinct_read_only_and_keeps_original_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = Path(tmp) / "case"
            scope.mkdir()
            source = scope / "contenu"
            source.write_bytes(b"synthetic text")
            source.chmod(0o400)
            before = source.stat()
            copy = prepare_view(Path(tmp) / "cases.sqlite", source, "note & spaces.txt", scope=scope)
            self.assertNotEqual(source, copy)
            self.assertTrue(copy.is_relative_to(Path(tmp) / "viewing-copies"))
            self.assertEqual(copy.read_bytes(), b"synthetic text")
            self.assertEqual(copy.stat().st_mode & 0o777, 0o400)
            self.assertEqual(source.stat().st_mtime_ns, before.st_mtime_ns)

    def test_executable_magic_and_symlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            scope = Path(tmp) / "case"
            scope.mkdir()
            source = scope / "note.txt"
            source.write_bytes(b"\x7fELFsynthetic")
            with self.assertRaisesRegex(ValueError, "Executable"):
                prepare_view(state, source, source.name, scope=scope)
            link = scope / "link.txt"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                prepare_view(state, link, link.name, scope=scope)
            with self.assertRaises(FileNotFoundError):
                with checked_descriptor(scope / "missing.txt", scope=scope):
                    self.fail("missing file opened")
            self.assertFalse((state.parent / "viewing-copies").exists())

    def test_reveal_is_optional_and_root_cannot_open_a_graphical_application(self):
        with patch("vigil.desktop_integration.shutil.which", return_value=None):
            self.assertFalse(reveal_in_file_manager(Path("/tmp/fixture")))
        with patch("vigil.desktop_integration.os.geteuid", return_value=0), \
                patch.dict("os.environ", {"WAYLAND_DISPLAY": "fixture"}):
            self.assertFalse(graphical_user())
