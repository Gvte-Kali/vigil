import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vigil.shutdown_state import ShutdownBlocked, capture_startup_state, check_shutdown_state, read_block_modes

EMPTY_ZONES = {"/investigation": [], "/stockage": []}


class ShutdownStateTest(unittest.TestCase):
    def test_capture_includes_partition_and_parent_disk_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disk = root / "sda"
            part = disk / "sda1"
            part.mkdir(parents=True)
            (disk / "diskseq").write_text("8\n")
            for node, number, flag in ((disk, "8:0", "0"), (part, "8:1", "1")):
                (node / "dev").write_text(number)
                (node / "ro").write_text(flag)
            (part / "partition").write_text("1")
            block = root / "class"
            block.mkdir()
            (block / "sda").symlink_to(disk)
            (block / "sda1").symlink_to(part)
            modes = read_block_modes(block)
            self.assertEqual(modes["sda1"]["disk_sequence"], "8")
            self.assertEqual(modes["sda"]["mode"], "rw")
            self.assertEqual(modes["sda1"]["mode"], "ro")
            with patch("vigil.shutdown_state.read_block_modes", return_value=modes), \
                    patch("vigil.shutdown_state.read_zones", return_value=EMPTY_ZONES):
                baseline, path = capture_startup_state(root / "cases.sqlite")
            self.assertEqual(json.loads(path.read_text())["block_devices"], baseline)

    def test_shutdown_checks_only_the_two_mount_zones(self):
        for zone, target in (("/stockage", "/stockage/volume"), ("/investigation", "/investigation")):
            mounted = {**EMPTY_ZONES, zone: [(target, "/dev/sdb1", "ext4", "ro")]}
            with self.subTest(target=target), patch("vigil.shutdown_state.read_zones", return_value=mounted):
                with self.assertRaisesRegex(ShutdownBlocked, target):
                    check_shutdown_state()

        with patch("vigil.shutdown_state.read_zones", return_value=EMPTY_ZONES), \
                patch("vigil.shutdown_state.read_block_modes") as read_modes:
            check_shutdown_state()
            read_modes.assert_not_called()
