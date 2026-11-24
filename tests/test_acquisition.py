import hashlib
import io
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vigil.quick_actions import acquisition_command

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/imager/vigil_acquire.py"
acquisition = runpy.run_path(str(SCRIPT))


class AcquisitionTest(unittest.TestCase):
    def test_verified_image_and_no_overwrite(self):
        data = b"synthetic image data"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_image = acquisition["create_image"]
            from contextlib import redirect_stdout

            with redirect_stdout(io.StringIO()) as progress:
                digest = create_image(io.BytesIO(data), len(data), root, "test.raw")
            self.assertIn("Copie : 100.0 % · 20/20 octets", progress.getvalue())
            self.assertIn("Vérification SHA-256 : 100.0 % · 20/20 octets", progress.getvalue())
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())
            self.assertEqual((root / "test.raw").read_bytes(), data)
            self.assertEqual((root / "test.raw.sha256").read_text(), f"{digest}  test.raw\n")
            with self.assertRaises(FileExistsError):
                create_image(io.BytesIO(b"replacement"), 11, root, "test.raw")
            self.assertEqual((root / "test.raw").read_bytes(), data)

    def test_short_read_cleans_new_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(OSError, "Lecture incomplète"):
                acquisition["create_image"](io.BytesIO(b"short"), 20, root, "short.raw")
            self.assertEqual(list(root.iterdir()), [])

    def test_failed_unmount_never_removes_mountpoint_contents(self):
        external_directory = acquisition["external_directory"]
        globals_ = external_directory.__wrapped__.__globals__
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protected = root / "existing"
            protected.touch()
            disk = {"maj:min": "8:0"}
            partition = {"name": "/dev/test", "fstype": "ext4", "maj:min": "8:1"}
            with patch.dict(globals_, {
                "check_disk": lambda *_: None, "validate_fd": lambda *_: None,
                "block_mode": lambda *_: 0, "disk_sequence": lambda *_: "10",
            }), patch.object(globals_["os"], "open", return_value=42), \
                    patch.object(globals_["os"], "close"), \
                    patch.object(tempfile, "mkdtemp", return_value=tmp), \
                    patch.dict(globals_, {"command": lambda program, *args:
                               (_ for _ in ()).throw(OSError("busy"))
                               if program.endswith("umount") else "/dev/nonexistent"}):
                with self.assertRaisesRegex(OSError, "busy"):
                    with external_directory(disk, "10", partition, (1000, 1000)):
                        self.fail("mount verification must fail for a nonexistent device")
            self.assertTrue(protected.exists())

    def test_gui_uses_private_mount_namespace(self):
        for operation in ("clone", "image"):
            argv = acquisition_command(operation)
            self.assertEqual(argv[:7], [
                "/usr/bin/sudo", "--", "/usr/bin/unshare", "--mount", "--propagation", "private", "--",
            ])
            self.assertIn(operation, argv)


    def test_native_picker_path_is_passed_as_one_argument(self):
        directory = Path("/tmp/vigil image output")
        argv = acquisition_command("image", local_directory=directory)
        self.assertEqual(argv[-2:], ["--local-directory", str(directory)])
        self.assertEqual(acquisition_command("image", external=True)[-1], "--external")
        with self.assertRaises(ValueError):
            acquisition_command("image", local_directory=directory, external=True)

    def test_selection_identifies_disks_and_groups_external_partitions(self):
        from contextlib import redirect_stdout

        part = {
            "name": "/dev/sdz1", "type": "part", "size": 4096, "fstype": "ext4",
            "label": "Fixture", "parttypename": "Linux filesystem", "ro": False,
        }
        disk = {
            "name": "/dev/sdz", "type": "disk", "size": 8192, "model": "USB Fixture",
            "serial": "1234", "tran": "usb", "pttype": "gpt", "ro": True, "children": [part],
        }
        choose = acquisition["choose"]
        with patch("builtins.input", return_value="1"), redirect_stdout(io.StringIO()) as output:
            self.assertIs(choose([disk], "Source"), disk)
            self.assertIs(choose([part], "Destination", parents={part["name"]: disk}), part)
        menu = output.getvalue()
        for expected in ("Modèle : USB Fixture", "Série : 1234", "Table : gpt",
                         "Type : Linux filesystem", "Volume : Fixture", "FS : ext4",
                         "Bloc : RO", "Bloc : RW", "Disque parent : /dev/sdz"):
            self.assertIn(expected, menu)
        self.assertIn("[1] /dev/sdz1", menu)


    def test_palette_is_applied_only_to_interactive_output(self):
        from unittest.mock import Mock

        style = acquisition["terminal_style"]
        terminal = Mock()
        terminal.isatty.return_value = True
        with patch.dict("os.environ", {"TERM": "xterm-256color"}, clear=True):
            self.assertEqual(style("Vigil", "96", stream=terminal), "\033[96mVigil\033[0m")
            self.assertEqual(style("Vigil", "96", stream=io.StringIO()), "Vigil")
        with patch.dict("os.environ", {"TERM": "xterm-256color", "NO_COLOR": ""}, clear=True):
            self.assertEqual(style("Vigil", "96", stream=terminal), "Vigil")

    def test_external_image_requires_a_separate_usb_disk(self):
        from contextlib import redirect_stdout

        run = acquisition["run"]
        source = {"name": "/dev/sdb", "type": "disk", "size": 8192, "tran": "usb",
                  "maj:min": "8:16", "children": [{"name": "/dev/sdb1", "fstype": "ntfs"}]}
        with patch.dict(run.__globals__, {
            "devices": lambda: [source], "idle": lambda _: True, "disk_sequence": lambda _: "42",
            "choose": lambda rows, _: rows[0], "target_disks": lambda *_: [],
        }), patch.dict("os.environ", {"SUDO_UID": "1000", "SUDO_GID": "1000"}), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "disque source /dev/sdb"):
                run("image", "/tmp", external=True)


    def test_target_list_is_refreshed_after_prompt(self):
        from contextlib import redirect_stdout

        target_disks = acquisition["target_disks"]
        source = {"name": "/dev/sdb", "maj:min": "8:16", "type": "disk", "tran": "usb"}
        target = {"name": "/dev/sdc", "maj:min": "8:32", "type": "disk", "tran": "usb"}
        with patch.dict(target_disks.__globals__, {
            "devices": lambda: [source, target], "idle": lambda _: True,
            "check_disk": lambda *_: None,
        }), patch("shutil.which", return_value=None), patch("builtins.input", return_value=""), redirect_stdout(io.StringIO()):
            self.assertEqual(target_disks(source, "42"), [target])
