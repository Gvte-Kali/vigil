import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from textual.widgets import DataTable, Input, Static

from vigil.destination import Mount, on_investigation
from vigil.tui import Workspace
from vigil.tui_picker import FileSystemPicker, PickerOptions


class PickerTest(unittest.IsolatedAsyncioTestCase):
    async def test_open_filter_and_keyboard_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "folder"
            folder.mkdir()
            image = folder / "disk.RAW"
            image.touch()
            (folder / "discard.txt").touch()
            (folder / ".hidden.raw").touch()
            workspace = Workspace(root / "cases.sqlite", language="en", operator="Alice")
            result = []
            async with workspace.run_test(size=(76, 23)) as pilot:
                picker = FileSystemPicker("Image", workspace.tr, PickerOptions("open", (".raw",)), initial=root)
                await workspace.push_screen(picker, result.append)
                await pilot.pause()
                table = picker.query_one(DataTable)
                self.assertEqual(table.row_count, 1)
                self.assertTrue(await pilot.click(table, offset=(3, 1)))
                self.assertEqual(picker.current, root)
                self.assertTrue(await pilot.click(table, offset=(3, 1), times=2))
                await pilot.pause()
                self.assertEqual(picker.current, folder)
                self.assertEqual(table.row_count, 1)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(result, [image])

    async def test_save_preserves_name_and_refuses_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "disk.raw"
            target.touch()
            workspace = Workspace(root / "cases.sqlite", language="en", operator="Alice")
            result = []
            async with workspace.run_test(size=(100, 32)) as pilot:
                picker = FileSystemPicker("Save", workspace.tr, PickerOptions("save", (".raw",), acquisition=True),
                                          initial=target)
                await workspace.push_screen(picker, result.append)
                await pilot.pause()
                self.assertIn("Available", str(picker.query_one("#picker-meta", Static).render()))
                self.assertTrue(await pilot.click("#picker-confirm"))
                await pilot.pause()
                self.assertEqual(result, [])
                self.assertIn("already exists", str(picker.query_one("#picker-error", Static).render()))
                field = picker.query_one("#picker-name", Input)
                field.value = "new.raw"
                field.focus()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(result, [root / "new.raw"])
                self.assertFalse((root / "new.raw").exists())

    def test_investigation_aliases_are_rejected(self):
        root = Mount(1, "0:42", PurePosixPath("/"), Path("/"), "tmpfs", "tmpfs")
        evidence = Mount(2, "8:17", PurePosixPath("/"), Path("/investigation/evidence"), "ext4", "/dev/sdb1")
        alias = Mount(3, "8:17", PurePosixPath("/subfolder"), Path("/mnt/evidence"), "ext4", "/dev/sdb1")
        bind = Mount(4, "0:42", PurePosixPath("/investigation/dir"), Path("/mnt/bind"), "tmpfs", "tmpfs")
        mounts = [root, evidence, alias, bind]
        self.assertTrue(on_investigation(Path("/mnt/evidence/export"), alias, mounts))
        self.assertTrue(on_investigation(Path("/mnt/bind/export"), bind, mounts))
        self.assertFalse(on_investigation(Path("/mnt/other"), root, mounts))

    async def test_quit_confirmation_and_dashboard_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / "cases.sqlite", language="en", operator="Alice")
            mounts = [{"mountpoint": "/stockage/test", "path": "/dev/test", "mount_mode": "rw", "verified": True}]
            with patch("vigil.tui.check_shutdown_state") as shutdown:
                async with workspace.run_test(size=(90, 28)) as pilot:
                    with patch("vigil.tui.device_manager.status", return_value=mounts), \
                         patch("vigil.tui.device_manager.inventory", return_value=[{"name": "test-disk", "ro": 1}]):
                        await pilot.pause(3.5)
                    self.assertIn("/stockage/test", str(workspace.query_one("#mount-summary", Static).render()))
                    self.assertEqual(workspace.query_one("#disk-tree").root.children[0].label.plain, "test-disk · — · RO")
                    self.assertTrue(await pilot.click("#quit"))
                    self.assertTrue(await pilot.click("#cancel"))
                    shutdown.assert_not_called()
                    await pilot.press("ctrl+q")
                    self.assertTrue(await pilot.click("#confirm"))
                shutdown.assert_called_once_with()
                self.assertFalse(workspace.is_running)
