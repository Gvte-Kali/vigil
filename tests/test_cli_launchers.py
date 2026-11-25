import os
import pty
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from vigil.cli import app


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "scripts/lib/vigil-launchers.sh"



class CliLaunchersTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.site, self.local, self.system, self.home = (
            root / name for name in ("site", "local-bin", "sys-bin", "home")
        )
        self.site_bin = self.site / ".venv/bin"
        self.user_bin = self.home / ".local/bin"
        self.desktop = root / "vigil.desktop"
        self.env = {**os.environ, "HOME": str(self.home),
                    "PATH": f"{self.user_bin}:{self.system}:{self.local}:/usr/bin:/bin"}
        for path in (self.local, self.system, self.site_bin, self.user_bin):
            path.mkdir(parents=True)
        launcher = self.site / "scripts/post-install/vigil-qt"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("#!/bin/sh\n# Vigil Qt launcher fixture\nexit 0\n")
        self.state = self.site / "data/state/cases.sqlite"
        self.state.parent.mkdir(parents=True)
        self.state.write_bytes(b"untouched database fixture")

        python = self.site_bin / "python"
        python.write_text("#!/bin/sh\nexit 0\n")
        python.chmod(0o755)
        self.wrapper("vigil", "cli", "main")
        self.wrapper("vigil-gui", "session", "main")
        # The tests run the generated wrapper against an interpreter fixture.
        # Real installed entry points are exercised separately in the packaging smoke test.

    def wrapper(self, name, module, function):
        path = self.site_bin / name
        path.write_text(
            f"#!{self.site_bin}/python\n"
            "# -*- coding: utf-8 -*-\nimport re\nimport sys\n"
            f"from vigil.{module} import {function}\nif __name__ == '__main__':\n"
            "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
            f"    sys.exit({function}())\n"
        )
        path.chmod(0o755)

    def shell(self, command="vigil_publish_launchers"):
        return subprocess.run([
            "/bin/bash", "-c", '. "$1"; sudo() { "$@"; }; "$2" "${@:3}"',
            "fixture", str(LIBRARY), command, str(self.site), str(self.local),
            str(self.system), str(self.desktop),
        ], capture_output=True, text=True, env=self.env, timeout=10)

    def test_clean_and_idempotent_site_links(self):
        for _ in range(2):
            result = self.shell()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.local / "vigil").resolve(), self.site_bin / "vigil")
            self.assertFalse((self.local / "vigil2").exists())
            self.assertEqual((self.local / "vigil-gui").resolve(), self.site / "scripts/post-install/vigil-qt")
            self.assertEqual(self.state.read_bytes(), b"untouched database fixture")

    def test_removes_owned_legacy_entries_and_migrates_desktop(self):
        self.wrapper("vigil2", "cli", "app")
        self.wrapper("vigil2-gui", "desktop", "main")
        (self.system / "vigil2").symlink_to(self.site_bin / "vigil2")
        (self.user_bin / "vigil").symlink_to(self.site / "gui/vigil_main_gui.py")
        (self.system / "vigil").symlink_to(self.site / "scripts/Vigil-CLI/vigil")
        (self.local / "vigil").symlink_to(self.site / "scripts/post-install/vigil-qt")
        self.desktop.write_text(f"[Desktop Entry]\nName=Vigil\nType=Application\nExec={self.local}/vigil\n")
        foreign = self.local / "vigil2"
        foreign.write_text("third-party program")
        result = self.shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("third-party", result.stderr)
        self.assertEqual(foreign.read_text(), "third-party program")
        for old in (self.site_bin / "vigil2", self.site_bin / "vigil2-gui", self.system / "vigil2",
                    self.system / "vigil", self.user_bin / "vigil"):
            self.assertFalse(os.path.lexists(old))
        self.assertIn(f"Exec={self.local}/vigil-gui", self.desktop.read_text())
        self.assertEqual(self.state.read_bytes(), b"untouched database fixture")

    def test_foreign_vigil_is_left_untouched(self):
        foreign = self.system / "vigil"
        foreign.write_text("#!/bin/sh\nexit 0\n")
        foreign.chmod(0o755)
        before = foreign.read_bytes()
        result = self.shell()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(foreign), result.stderr)
        self.assertEqual(foreign.read_bytes(), before)
        self.assertFalse(os.path.lexists(self.local / "vigil"))

    def test_foreign_gui_launcher_blocks_migration(self):
        foreign = self.local / "vigil-gui"
        foreign.write_text("third-party launcher")
        result = self.shell()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(foreign), result.stderr)
        self.assertEqual(foreign.read_text(), "third-party launcher")
        self.assertFalse(os.path.lexists(self.local / "vigil"))

    def test_help_version_and_command_families(self):
        runner = CliRunner()
        for arguments in (["--help"], ["--version"], ["modules", "list"],
                          ["cases", "--help"], ["evidence", "--help"], ["doctor"]):
            result = runner.invoke(app, arguments)
            self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Usage: vigil", runner.invoke(app, ["--help"]).output)
        self.assertIn("Vigil 2.", runner.invoke(app, ["--version"]).output)

    def test_existing_cli_entry_point_shows_logo_before_help(self):
        # An editable install keeps the original launcher after a git pull.
        for arguments, status in (([], 2), (["--help"], 0), (["cases", "--help"], 0)):
            with self.subTest(arguments=arguments):
                master, terminal = pty.openpty()
                try:
                    result = subprocess.run(
                        [sys.executable, "-c", "from vigil.cli import app; app()", *arguments],
                        cwd=ROOT, env={**self.env, "TERM": "xterm", "NO_COLOR": "1"},
                        stdout=terminal, stderr=terminal, timeout=10,
                    )
                    output = os.read(master, 4096).decode()
                finally:
                    os.close(terminal)
                    os.close(master)
                self.assertEqual(result.returncode, status)
                self.assertTrue(output.startswith("Vigil\r\n"), output)
                self.assertIn("Usage:", output)
