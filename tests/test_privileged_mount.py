import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/privileged/vigil-mount"
LOADER = importlib.machinery.SourceFileLoader("vigil_mount_test_module", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
HELPER = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(HELPER)


class MountPolicyTest(unittest.TestCase):
    def test_refuses_unapproved_name_and_symlink_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval = root / "approved-partition"
            approval.write_text("../../sda1\n")
            with patch.object(HELPER, "APPROVAL", approval), \
                    patch.object(HELPER, "check_root_owned"):
                with self.assertRaisesRegex(ValueError, "partition name"):
                    HELPER.approved_source()
                approval.rename(root / "other")
                approval.symlink_to(root / "other")
                with self.assertRaises(OSError):
                    HELPER.approved_source()

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
