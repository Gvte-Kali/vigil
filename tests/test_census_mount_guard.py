import runpy
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/analyse/vigil_census_mount_guard.py"
guard = SimpleNamespace(**runpy.run_path(str(SOURCE)))


class CensusMountGuardTest(unittest.TestCase):
    def test_only_investigation_mounts_are_selected(self):
        records = list(guard.mount_records([
            "30 1 8:1 / /investigation/disk\\0401 ro - ext4 /dev/sda1 ro",
            "31 1 8:2 / /investigation-old rw - ext4 /dev/sda2 rw",
        ]))
        self.assertEqual(records, [("8:1", "/investigation/disk 1", ["ro"], "/dev/sda1")])

    def test_requires_matching_block_device_and_parent_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            partition = root / "sda" / "sda1"
            partition.mkdir(parents=True)
            (partition / "partition").touch()
            (partition / "ro").write_text("1\n")
            (partition / "dev").write_text("8:1\n")
            (partition / "size").write_text("1024\n")
            (partition.parent / "diskseq").write_text("5\n")
            parent_mode = partition.parent / "ro"
            parent_mode.write_text("0\n")
            (root / "8:1").symlink_to(partition)
            record = ("8:1", "/investigation/device", ["ro"], "/dev/sda1")
            device = SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=2049)
            original = Path.stat

            def stat_fixture(path, *args, **kwargs):
                return device if str(path) == "/dev/sda1" else original(path, *args, **kwargs)

            with patch.object(Path, "stat", stat_fixture):
                with self.assertRaisesRegex(ValueError, "Unexpected block protection"):
                    guard.validate_mounts([record], root)
                parent_mode.write_text("1\n")
                self.assertEqual(guard.validate_mounts([record], root), ["/investigation/device"])
                with self.assertRaisesRegex(ValueError, "block device identity changed"):
                    guard.validate_mounts([("8:2", *record[1:])], root)
