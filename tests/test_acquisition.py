import hashlib
import io
import runpy
import subprocess
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
            self.assertIn("Copie 100.0 % · 20.0 o / 20.0 o (20/20 octets)", progress.getvalue())
            self.assertIn("Vérification SHA-256 100.0 % · 20.0 o / 20.0 o (20/20 octets)", progress.getvalue())
            lines = progress.getvalue()
            self.assertLess(lines.index("Copie 100.0 %"), lines.index("Synchronisation des écritures"))
            self.assertLess(lines.index("Synchronisation des écritures"), lines.index("Relecture de la destination"))
            self.assertLess(lines.index("Relecture de la destination"), lines.index("Vérification SHA-256 100.0 %"))
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

    def test_acquisition_partition_uses_mount_menu_and_selection(self):
        library = SCRIPT.parents[1] / "lib"
        row = "part|sdz1|4G|USB Fixture|ext4|Fixture|GPT data|sdz"
        args = ["/usr/bin/bash", "-c", """
            . "$1/vigil-terminal.sh"
            . "$1/vigil-device-triage.sh"
            declare -A PARENT_SIZE=([sdz]=8G) PARENT_MODEL=([sdz]='USB Fixture')
            declare -A DEVICE_ACCESS=([sdz1]=RW)
            USB_DEVICES=("$2")
            DEVICE_NUM=1
            display_usb_devices "Partition USB de destination"
            select_usb_device "de destination"
        """, "fixture", str(library), row]
        mount = subprocess.run(args, input="9\n1\n", capture_output=True, text=True, check=True)
        bridge = SCRIPT.with_name("vigil_acquire_triage.sh")
        with tempfile.TemporaryDirectory() as tmp:
            target = ["/usr/bin/bash", str(bridge), "select", tmp,
                      "Partition USB de destination", "de destination", row + "|RW|8G|USB Fixture"]
            result = subprocess.run(target, input="9\n1\n", capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "0\n")
            self.assertTrue(result.stderr.endswith(mount.stdout))
            for word, status in (("r", 2), ("q", 1)):
                result = subprocess.run(target, input=f"{word}\n", capture_output=True, text=True)
                self.assertEqual(result.returncode, status)
                self.assertEqual(result.stdout, "")

    def test_shared_usb_triage_keeps_baseline_port_and_serial_exclusions(self):
        library = SCRIPT.parents[1] / "lib"
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(["/usr/bin/bash", "-u", "-c", """
                . "$1/vigil-terminal.sh"
                . "$1/vigil-device-triage.sh"
                TRIAGE_DIR=$2
                USB_WHITELIST_FILE=$2/whitelist.txt
                USB_BLACKLIST_FILE=$2/blacklist.txt
                log_action() { :; }
                sleep() { :; }
                usb_snapshot() {
                    if [[ -f "$TRIAGE_DIR/after" ]]; then
                        printf '%s\n' '1:8|99-1|1234|5678|||keyboard' \
                            '1:9|99-2|1234|5678|||mouse' '1:10|99-3|1234|5678|||drive'
                    else
                        printf '%s\n' '1:2|99-1|1234|5678|||original-keyboard' \
                            '1:3|99-4|1234|5678|||mouse'
                        touch "$TRIAGE_DIR/after"
                    fi
                }
                run_usb_triage Source
            """, "fixture", str(library), tmp],
                input="\n\n", text=True, capture_output=True, check=True)
            self.assertIn("Baseline USB enregistrée", result.stdout)
            self.assertEqual((Path(tmp) / "usb_new.txt").read_text(), "1:10|99-3|1234|5678|||drive\n")

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

    def test_targets_filter_source_busy_disks_and_incompatible_capacity(self):
        options = acquisition["disk_options"]
        source = {"name": "/dev/sdb", "maj:min": "8:16", "type": "disk", "tran": "usb", "size": 8192}
        same_path = dict(source, **{"maj:min": "8:17"})
        small = dict(source, name="/dev/sdc", size=4096, **{"maj:min": "8:32"})
        busy = dict(source, name="/dev/sdd", **{"maj:min": "8:48"})
        good = {"name": "/dev/sde1", "type": "part", "size": 16384, "fstype": "ext4"}
        tiny = dict(good, name="/dev/sde2", size=1024)
        bad_fs = dict(good, name="/dev/sde3", fstype="iso9660")
        target = dict(source, name="/dev/sde", size=32768, children=[good, tiny, bad_fs],
                      **{"maj:min": "8:64"})
        with patch.dict(options.__globals__, {
            "devices": lambda: [source, same_path, small, busy, target],
            "idle": lambda row: row is not busy, "filesystem": lambda row: row["fstype"],
            "triaged_disk": lambda *_: True, "disk_sequence": lambda _: "43",
            "check_disk": lambda disk, seq: self.assertEqual((disk, seq), (source, "42")),
        }):
            self.assertEqual(list(options({"fixture"}, source=source, sequence="42")),
                             [(target, None, "43")])
            self.assertEqual(list(options({"fixture"}, source=source, sequence="42", image=True)),
                             [(target, good, "43")])

    def test_refresh_rebuilds_candidates_and_returns_latest_identity(self):
        choose = acquisition["choose"]
        old = {"name": "/dev/sdb", "type": "disk", "size": 8192, "ro": True}
        current = dict(old, name="/dev/sdc")
        responses = iter([subprocess.CompletedProcess([], 2, ""), subprocess.CompletedProcess([], 0, "0")])
        inventories = iter([[(old, None, "42")], [(current, None, "43")]])
        prompts = []

        def triage_command(*args):
            prompts.append(args[-1])
            return next(responses)

        with patch.dict(choose.__globals__, {"triage_command": triage_command}):
            self.assertEqual(choose(lambda: next(inventories), "Source", "source", "/tmp"),
                             (current, None, "43"))
        self.assertIn("sdb", prompts[0])
        self.assertIn("sdc", prompts[1])

    def test_usb_triage_refuses_a_composite_device(self):
        inspect_usb = acquisition["inspect_usb"]
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "1-2"
            interface = device / "1-2:1.0"
            interface.mkdir(parents=True)
            for name, value in {"authorized": "1", "busnum": "1", "devnum": "3"}.items():
                (device / name).write_text(value)
            (interface / "bInterfaceClass").write_text("08")
            self.assertEqual(inspect_usb(device), ("1-2", "1", "3"))
            hid = device / "1-2:1.1"
            hid.mkdir()
            (hid / "bInterfaceClass").write_text("03")
            with self.assertRaisesRegex(ValueError, "HID détectée"):
                inspect_usb(device)


    def test_tty_progress_redraws_and_non_tty_has_no_control_sequences(self):
        from contextlib import redirect_stdout
        import vigil_progress

        class PseudoTerminal(io.StringIO):
            def isatty(self):
                return True

        class PlainStream(io.StringIO):
            def isatty(self):
                return False

        for stream in (PseudoTerminal(), PlainStream()):
            with self.subTest(tty=stream.isatty()), redirect_stdout(stream), \
                    patch.dict("os.environ", {"TERM": "xterm-256color"}, clear=True), \
                    patch.object(vigil_progress.time, "monotonic", side_effect=[0, 6, 12]):
                progress = vigil_progress.Progress("Copie", 10000)
                progress.update(9999)
                progress.update(10000)
            rendered = stream.getvalue()
            self.assertIn("99.9 %", rendered)
            self.assertIn("100.0 %", rendered)
            self.assertEqual(chr(13) in rendered, stream.isatty())
            self.assertEqual(chr(27) in rendered, stream.isatty())
            self.assertEqual(rendered.count(chr(10)), 1 if stream.isatty() else 2)

    def test_non_tty_sync_has_no_spinner_or_estimate(self):
        from contextlib import redirect_stdout
        import vigil_progress

        with redirect_stdout(io.StringIO()) as stream:
            with vigil_progress.indeterminate("Synchronisation"):
                pass
        self.assertEqual(stream.getvalue(), "\nSynchronisation…\n")
