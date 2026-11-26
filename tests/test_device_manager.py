import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from vigil import device_manager
from vigil.cli import app
from vigil.system_info import mount_records

class DeviceManagerTest(unittest.TestCase):
    def test_shared_jobs_exclude_mutation_and_keep_kernel_mount_state_for_shutdown(self):
        with device_manager.device_lease(shared=True):
            with device_manager.device_lease(shared=True):
                with self.assertRaises(device_manager.DeviceBusy):
                    with device_manager.device_lease():
                        self.fail("exclusive lease granted during a reader")
        with device_manager.device_lease():
            with self.assertRaises(device_manager.DeviceBusy):
                with device_manager.device_lease(shared=True):
                    self.fail("shared lease granted during mutation")

    def test_shell_backend_uses_inherited_lease(self):
        result = device_manager.run_job([
            "/usr/bin/bash", "-uc",
            '. scripts/lib/vigil-device-ops.sh; vigil_device_begin',
        ])
        self.assertEqual(result, 0)

    def test_mutation_refuses_occupied_zone_and_direct_storage_requires_confirmation(self):
        mounts = [{"zone": "/investigation", "mountpoint": "/investigation/x"}]
        with tempfile.TemporaryDirectory() as directory, patch.object(
            device_manager, "default_database", return_value=Path(directory) / "cases.sqlite",
        ), patch.object(device_manager, "mounted_resources", return_value=mounts), patch.object(
            device_manager, "_run",
        ) as run:
            with self.assertRaisesRegex(ValueError, "Zone occup"):
                device_manager.operate("mount", "investigation", device="/dev/sdz1")
            with self.assertRaisesRegex(ValueError, "confirm-write"):
                device_manager.operate("mount", "stockage", device="/dev/sdz1")
            run.assert_not_called()

    def test_direct_unmount_refuses_unmanaged_or_nested_mount(self):
        root = {"zone": "/stockage", "mountpoint": "/stockage", "mount_id": 2}
        child = {"zone": "/stockage", "mountpoint": "/stockage/disk", "mount_id": 3}
        with tempfile.TemporaryDirectory() as directory, patch.object(
            device_manager, "default_database", return_value=Path(directory) / "cases.sqlite",
        ), patch.object(device_manager, "mounted_resources", return_value=[root, child]), patch.object(
            device_manager, "_run",
        ) as run:
            for target in ("/etc", "/stockage"):
                with self.assertRaisesRegex(ValueError, "Target missing, ambiguous or has submounts"):
                    device_manager.operate("unmount", "stockage", target=target)
            run.assert_not_called()

    def test_status_rejects_ambiguous_mounts_and_wrong_protections(self):
        records = list(mount_records([
            "5 2 8:1 / /investigation/a rw - ext4 /dev/sdz1 rw",
            "6 2 8:2 / /stockage/disk ro - ext4 /dev/sdz2 ro",
            "7 2 8:3 / /stockage/disk rw - ext4 /dev/sdz3 rw",
            "8 2 8:4 / /stockage-old rw - ext4 /dev/sdz4 rw",
        ]))
        with patch.object(device_manager, "mounted_resources", return_value=records):
            status = device_manager.status()
        self.assertEqual(len(status), 3)
        self.assertFalse(any(row["verified"] for row in status))
        self.assertIn("Unexpected mount protection", status[0]["error"])
        self.assertTrue(all("Ambiguous mount" in row["error"] for row in status[1:]))

    def test_analysis_passes_verified_context_while_holding_read_lease(self):
        resources = [{"zone": "/investigation", "mountpoint": "/investigation/test", "verified": True}]
        code = (
            "import json, os; print(json.loads(os.environ['VIGIL_DEVICE_CONTEXT'])[0]['mountpoint'])"
        )
        with patch.object(device_manager, "status", return_value=resources), patch.object(
            device_manager.subprocess, "run", wraps=subprocess.run,
        ) as run:
            self.assertEqual(device_manager.run_job(["/usr/bin/python3", "-c", code], analysis=True), 0)
            self.assertEqual(json.loads(run.call_args.kwargs["env"]["VIGIL_DEVICE_CONTEXT"]), resources)

    def test_cli_returns_json_with_no_terminal(self):
        runner = CliRunner()
        with patch.object(device_manager, "mounted_resources", return_value=[]):
            result = runner.invoke(app, ["devices", "status"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(result.stdout), {"mounts": []})
            failure = runner.invoke(app, ["devices", "verify", "--target", "/investigation/absent"])
            self.assertEqual(failure.exit_code, 1, failure.output)
            self.assertFalse(json.loads(failure.stdout)["verified"])
        refusal = runner.invoke(app, ["devices", "mount", "--zone", "stockage", "--device", "/dev/sdz1"])
        self.assertEqual(refusal.exit_code, 1, refusal.output)
        self.assertIn("confirm-write", json.loads(refusal.stdout)["error"])
