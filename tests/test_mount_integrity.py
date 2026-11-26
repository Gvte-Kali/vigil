import importlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/analyse"
with patch("sys.path", [str(SCRIPTS), *sys.path]):
    integrity = importlib.import_module("vigil_mount_integrity")


class MountIntegrityTest(unittest.TestCase):
    def test_tree_digest_uses_relative_paths_and_content(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(integrity, "require_mount"):
            root = Path(tmp)
            (root / "one").mkdir()
            (root / "two").mkdir()
            for folder in ("one", "two"):
                (root / folder / "regular").write_bytes(b"same")
                (root / folder / "ignored").symlink_to("/nonexistent")
            before = integrity.tree_digest(root / "one", "42")
            self.assertEqual(before, integrity.tree_digest(root / "two", "43"))
            self.assertEqual(before[1], 1)
            (root / "two" / "regular").write_bytes(b"else")
            self.assertNotEqual(before, integrity.tree_digest(root / "two", "43"))

    def test_reference_is_per_mount_and_read_failure_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(StringIO()):
            root = Path(tmp)
            one, two = "/investigation/sdb/sdb1", "/investigation/sdb/sdb2"
            with patch.object(integrity, "mount_identity", side_effect=lambda path: ["boot", path]), \
                    patch.object(integrity, "tree_digest", side_effect=[("a", 1), ("b", 1), ("a", 1), ("changed", 1)]):
                self.assertEqual(integrity.check("record", one, root), 0)
                self.assertEqual(integrity.check("record", two, root), 0)
                self.assertEqual(integrity.check("verify", one, root), 0)
                self.assertEqual(integrity.check("verify", two, root), 2)
                self.assertEqual(len(list(root.glob("integrity-*.json"))), 2)
            with patch.object(integrity, "mount_identity", return_value=["boot", one]), \
                    patch.object(integrity, "tree_digest", side_effect=OSError("fixture I/O error")):
                with self.assertRaisesRegex(OSError, "fixture I/O"):
                    integrity.check("verify", one, root)
