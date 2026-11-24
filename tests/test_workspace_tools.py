import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vigil.core import discover
from vigil.inspection import PREVIEW_BYTES, inspect_file, list_evidence_directory
from vigil.module_scaffold import create_module_draft
from vigil.quick_actions import legacy_mount_command, storage_command, update_command
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
                wrapper = argv[argv.index("-c") + 1]
                self.assertEqual(wrapper.count("VIGIL_CASE_CENSUS=1"), 2 if action == "mount" else 0)
                if action == "mount":
                    self.assertIn('VIGIL_CASE_CENSUS=1 /usr/bin/bash "$@"', wrapper)
            self.assertFalse((root / "active_project").exists())

    def test_storage_commands_use_legacy_scripts_with_qt_operator_and_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            mount = storage_command("mount", state, "", "", "Alice")
            self.assertIn("VIGIL_QT_STORAGE=1", mount)
            self.assertIn("VIGIL_ACTIVE_USER=Alice", mount)
            self.assertIn("VIGIL_LEGACY_PROJECT=(no-project)", mount)
            self.assertIn(f"VIGIL_LEGACY_CASE_DIR={state.parent / 'storage-operations'}", mount)
            self.assertEqual(Path(mount[-1]).name, "vigil_stockage_mount.sh")
            case_id = "b" * 32
            unmount = storage_command("unmount", state, case_id, "Case", "Alice")
            self.assertIn(f"VIGIL_LEGACY_CASE_DIR={state.parent / 'legacy-custody' / case_id}", unmount)
            self.assertEqual(Path(unmount[-1]).name, "vigil_stockage_umount.sh")
            self.assertFalse((state.parent / "active_user").exists())

    def test_antivirus_reuses_dedicated_case_and_isolates_run_outputs(self):
        from vigil.storage import antivirus_case, create_case, database

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "cases.sqlite"
            with database(state) as connection:
                other = create_case(connection, "Investigation", "Alice")
                case = antivirus_case(connection, "Alice")
                self.assertNotEqual(other, case)
                self.assertEqual(antivirus_case(connection, "Bob"), case)
            run = "c" * 32
            argv = legacy_mount_command("scan", state, case, "Scan antivirus", "Bob", run_id=run)
            self.assertIn("VIGIL_LEGACY_PROJECT=Scan antivirus", argv)
            self.assertIn(f"VIGIL_LEGACY_SCAN_DIR={root / 'legacy-custody' / case / ('scan-' + run)}", argv)
            self.assertEqual(argv[-4:], ["--user", "Bob", "--log", "--pdf"])
            self.assertFalse(any("VIGIL_CASE_CENSUS" in item for item in argv))

    def test_explorer_batch_deduplicates_and_preserves_baseline(self):
        from vigil.storage import create_case, database, process_explorer_selection

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "cases.sqlite"
            with database(state) as connection:
                case = create_case(connection, "Investigation", "Alice")
            target = root / "note.txt"
            target.write_text("first")
            source = (str(target), None, False)
            missing = (str(root / "missing"), None, False)
            rows, errors = process_explorer_selection(
                state, case, "Alice", [source, source, missing], register=True)
            self.assertEqual([row[2] for row in rows], ["added"])
            self.assertEqual([row[0] for row in errors], [missing[0]])
            original = rows[0][1]
            target.write_text("changed")
            rows, _ = process_explorer_selection(state, case, "Alice", [source], register=True)
            self.assertEqual(rows[0][2], "existing")
            rows, _ = process_explorer_selection(state, case, "Alice", [source], register=False)
            self.assertEqual(rows[0][2:], ("changed", [original]))
            with database(state) as connection:
                self.assertEqual(connection.execute("SELECT sha256 FROM evidence").fetchall()[0][0], original)

    def test_mounted_explorer_requires_a_read_only_matching_mount_and_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "hello.txt"
            target.write_text("synthetic content", encoding="ascii")
            (root / "alias").symlink_to(target)
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                info = Path(f"/proc/self/fdinfo/{descriptor}").read_text()
                mount_id = int(next(line.split()[1] for line in info.splitlines()
                                    if line.startswith("mnt_id:")))
            finally:
                os.close(descriptor)
            with patch("vigil.inspection.os.fstatvfs", return_value=SimpleNamespace(f_flag=0)):
                with self.assertRaises(ValueError):
                    list_evidence_directory(root, root, mount_id)
            with patch("vigil.inspection.os.fstatvfs", return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
                self.assertEqual(list_evidence_directory(root, root, mount_id), [("hello.txt", False)])
                self.assertEqual(inspect_file(target, mount=(root, mount_id))["strings"], "synthetic content")
                with self.assertRaises(ValueError):
                    inspect_file(root / "alias", mount=(root, mount_id))
                with self.assertRaises(ValueError):
                    list_evidence_directory(root, root, mount_id + 1)

    def test_tracked_external_command_reports_operation_exit(self):
        import subprocess
        import sys
        from vigil.external_terminal import launch_tracked, terminal_command

        with tempfile.TemporaryDirectory() as tmp, patch("vigil.external_terminal.launch_terminal") as launch:
            run = launch_tracked([sys.executable, "-c", "raise SystemExit(7)"],
                                 Path(tmp), {"operation": "fixture", "operator": "Alice"}, "kitty")
            self.assertIsNone(run.status())
            args = launch.call_args.args[0]
            self.assertEqual(subprocess.run(args, capture_output=True, timeout=5).returncode, 7)
            self.assertEqual(run.status(), 7)
        with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-1"}, clear=True), \
                patch("vigil.external_terminal.shutil.which",
                      side_effect=lambda name: f"/fixture/{name}" if name in {"foot", "xterm"} else None):
            self.assertEqual(terminal_command(["/bin/echo", "path with spaces"], "xterm"),
                             ["/fixture/foot", "/bin/echo", "path with spaces"])

    def test_external_action_keeps_exit_error_visible(self):
        import subprocess

        from vigil.external_terminal import launch_action

        with patch("vigil.external_terminal.launch_terminal") as launch:
            launch_action(["/usr/bin/bash", "-c", "echo fixture-error >&2; exit 2"])
        result = subprocess.run(
            launch.call_args.args[0], input="\n", text=True, capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("fixture-error", result.stderr)
        self.assertIn("Exit code: 2", result.stdout)

    def test_quick_scan_mount_targets_include_nested_paths_and_decode_spaces(self):
        import subprocess

        helper = Path(__file__).resolve().parents[1] / "scripts/clamav/vigil_scan_mounts.sh"
        code = r"""
source "$1"
findmnt() {
    printf '%s\n' /investigation '/investigation/disk/part\x20one' /investigation-old /stockage
}
read_investigation_mounts /investigation
printf '%s\n' "${INVESTIGATION_MOUNTS[@]}"
"""
        result = subprocess.run(["bash", "-c", code, "fixture", str(helper)],
                                text=True, capture_output=True, check=True, timeout=5)
        self.assertEqual(result.stdout.splitlines(), ["/investigation", "/investigation/disk/part one"])

    def test_site_launcher_state_is_separate_from_development(self):
        with patch.dict("os.environ", {
            "VIGIL_STATE_DIR": "/opt/vigil/data/state", "XDG_STATE_HOME": "/tmp/development",
        }):
            self.assertEqual(default_database(), Path("/opt/vigil/data/state/cases.sqlite"))

    def test_checkout_under_opt_uses_site_state_even_with_xdg(self):
        with patch("vigil.storage.__file__", "/opt/vigil/vigil/storage.py"), \
                patch.dict("os.environ", {"VIGIL_STATE_DIR": "", "XDG_STATE_HOME": "/tmp/dev"}):
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
