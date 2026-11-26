import errno
import importlib.machinery
import importlib.util
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/privileged/vigil-mount"
LOADER = importlib.machinery.SourceFileLoader("vigil_mount_test_module", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
HELPER = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(HELPER)


class MountPolicyTest(unittest.TestCase):
    def test_ioctl_and_mount_errors_include_the_failed_operation(self):
        with patch.object(HELPER.fcntl, "ioctl", side_effect=OSError(errno.EINVAL, "Invalid argument")):
            with self.assertRaisesRegex(OSError, "set partition fixture RO: Invalid argument"):
                HELPER.block_ioctl(3, HELPER.BLOCK_RO_SET, bytes(4), "set partition fixture RO")
        with patch.object(HELPER.ctypes, "get_errno", return_value=errno.EINVAL):
            with self.assertRaisesRegex(OSError, "mount ext4 ro,noload: Invalid argument"):
                HELPER.checked_call(-1, "mount ext4 ro,noload")

    def test_target_permission_error_identifies_path_and_mode(self):
        with self.assertRaisesRegex(ValueError, r"/investigation:.*uid=1000, mode=0775"):
            HELPER.check_root_owned(SimpleNamespace(st_uid=1000, st_mode=0o775),
                                    Path("/investigation"))
        HELPER.check_root_owned(SimpleNamespace(st_uid=0, st_mode=0o755),
                                Path("/investigation"))

    def test_selection_requires_explicit_confirmation(self):
        options = [(Path("/dev/disk/by-id/usb-fixture-part1"), "8:1")]
        with patch.object(HELPER, "candidates", return_value=options), \
                patch.object(HELPER.sys.stdin, "isatty", return_value=True), \
                patch("builtins.print"), patch("builtins.input", side_effect=["r", "1", "OUI"]):
            self.assertEqual(HELPER.select_source(), options[0])
        with patch.object(HELPER, "candidates", return_value=options), \
                patch.object(HELPER.sys.stdin, "isatty", return_value=True), \
                patch("builtins.print"), patch("builtins.input", side_effect=["1", ""]):
            with self.assertRaisesRegex(ValueError, "cancelled"):
                HELPER.select_source()

    def test_usb_partition_rejects_disk_without_usb_ancestry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disk = root / "internal" / "sda"
            partition = disk / "sda1"
            partition.mkdir(parents=True)
            (partition / "partition").touch()
            (root / "8:1").symlink_to(partition)
            with patch.object(HELPER, "SYS_BLOCK", root):
                with self.assertRaisesRegex(ValueError, "not attached through USB"):
                    HELPER.usb_partition("8:1")

    def test_refuses_regular_file_and_foreign_mount(self):
        with tempfile.TemporaryFile() as stream:
            with self.assertRaisesRegex(ValueError, "not a block device"):
                HELPER.require_ro_partition(stream.fileno())
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "receipt"
            receipt.write_text("20 8:1\n")
            records = [("21", "8:2", "/investigation", ["ro"], "ext4")]
            with patch.object(HELPER, "mounts", return_value=records), \
                    patch.object(HELPER, "LIBC") as libc:
                with self.assertRaisesRegex(ValueError, "not created by Vigil"):
                    HELPER.unmount_partition(receipt)
                libc.umount2.assert_not_called()
                self.assertTrue(receipt.exists())
