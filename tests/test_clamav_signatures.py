import io
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
import json
import os
import select
import subprocess
from pathlib import Path
import tempfile
import sys
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from vigil import clamav, storage
from vigil.adapters import analysis_command
from vigil.cli import app
from vigil.quick_actions import legacy_mount_command, scan_command, update_command


def database_file(path, version, release):
    header = f"ClamAV-VDB:fixture:{version}:1:99:digest:signature:fixture:{int(release.timestamp())}"
    path.write_bytes(header.encode().ljust(512, b" ") + b"fixture")


class ClamAVSignaturesTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.now = datetime.now(UTC)
        self.state = self.root / "profile/cases.sqlite"
        self.profile = clamav.signatures_path(self.state)
        self.system = self.root / "system"
        self.commands = self.root / "commands.log"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.install(self.profile, 42, self.now)
        self.install(self.system, 900, self.now - timedelta(days=20))
        self.fake("clamscan", """#!/bin/sh
printf '%s\\n' "$*" >> "$CLAM_TEST_COMMANDS"
[ "$1" = --database ] && [ -f "$2/main.cvd" ] && [ -f "$2/daily.cvd" ] || exit 2
if [ "$3" = --version ]; then printf '%s\\n' 'ClamAV 1.4.3/900/system fixture'; fi
""")
        p = patch.dict(os.environ, {"PATH": f"{self.bin}:{os.environ['PATH']}",
                                    "CLAM_TEST_COMMANDS": str(self.commands),
                                    "CLAM_TEST_SYSTEM_DB": str(self.system)})
        p.start()
        self.addCleanup(p.stop)

    def fake(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o700)
        return path

    def install(self, directory, version, release):
        directory.mkdir(parents=True, exist_ok=True)
        database_file(directory / "main.cvd", 1, release)
        database_file(directory / "daily.cvd", version, release)

    def test_profile_beats_a_different_system_database_in_all_builders(self):
        with storage.database(self.state) as connection:
            case = storage.create_case(connection, "Case", "Alice")
        env = f"VIGIL_CLAMAV_DB_DIR={self.profile}"
        self.assertIn(env, legacy_mount_command("scan", self.state, case, "Case", "Alice", run_id="1" * 32))
        self.assertIn(env, analysis_command(self.state, case, "Alice", "vigil.clamav"))
        target = self.root / "study.txt"
        target.touch()
        self.assertIn(str(self.profile), scan_command(target, self.state))
        result = CliRunner().invoke(app, ["antivirus", "scan", str(target), "--db", str(self.state)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Daily: 42", result.output)
        commands = self.commands.read_text().splitlines()
        self.assertGreaterEqual(len(commands), 3)
        self.assertTrue(all("--database " + str(self.profile) in cmd for cmd in commands))
        self.assertNotIn(str(self.system), self.commands.read_text())

    def test_missing_and_incomplete_profile_do_not_run_the_system_scanner(self):
        with self.assertRaisesRegex(ValueError, "missing or unreadable"):
            clamav.signature_status(self.profile / "missing")
        (self.profile / "main.cvd").unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete or ambiguous"):
            clamav.signature_status(self.profile)
        self.assertFalse(self.commands.exists())

    def test_stale_requires_explicit_offline_and_records_that_choice(self):
        self.install(self.profile, 42, self.now - timedelta(days=8))
        log = self.root / "scan.json"
        with redirect_stdout(io.StringIO()), patch("vigil.clamav.sys.stdin.isatty", return_value=False):
            with self.assertRaisesRegex(ValueError, "--offline"):
                clamav.prepare_scan(self.profile, log=log)
            self.assertFalse(json.loads(log.read_text())["offline"])
            status = clamav.prepare_scan(self.profile, offline=True, log=log)
        self.assertEqual(status["freshness"], "stale")
        self.assertTrue(json.loads(log.read_text())["offline"])

    def test_freshclam_result_is_loaded_and_verified_by_the_same_scanner(self):
        database_file(self.root / "new.cvd", 43, self.now)
        self.fake("freshclam", f"""#!/bin/sh
[ "$1" = '--config-file={self.profile}/vigil-freshclam.conf' ] || exit 3
if [ "$2" = --version ]; then exit 0; fi
[ "$2" = '--datadir={self.profile}' ] || exit 4
cp '{self.root / "new.cvd"}' '{self.profile / "daily.cvd"}'
echo 'WARNING: Your ClamAV installation is OUTDATED!'
echo 'daily.cvd updated (version: 43, sigs: 100, f-level: 90, builder: fixture)'
""")
        with redirect_stdout(io.StringIO()):
            status = clamav.update_signatures(self.profile, update_command(self.state))
        self.assertEqual(status["daily_version"], 43)
        self.assertEqual(clamav.signature_status(self.profile)["engine_update"], "outdated")
        self.assertEqual(clamav.signature_status(self.system)["daily_version"], 900)
        self.fake("freshclam", """#!/bin/sh
if [ "$2" = --version ]; then exit 0; fi
echo 'daily.cvd updated (version: 44, sigs: 100, f-level: 90, builder: fixture)'
""")
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "revisions disagree"):
            clamav.update_signatures(self.profile, update_command(self.state))


    def test_package_plans_are_scoped_and_never_partially_upgrade_arch(self):
        packages = ["clamav", "libclamav12"]
        apt = clamav.engine_upgrade_plan("debian", packages)
        self.assertEqual(apt[1], ("apt-get", "install", "--only-upgrade", "--", *packages))
        self.assertEqual(clamav.engine_upgrade_plan("fedora", packages)[0][-2:], tuple(packages))
        self.assertEqual(clamav.engine_upgrade_plan("opensuse", packages)[1][-2:], tuple(packages))
        self.assertEqual(clamav.engine_upgrade_plan("arch", packages), [])

    def test_network_and_admin_errors_are_classified(self):
        for message, diagnostic in (("Could not resolve host", "DNS"),
                                    ("SSL certificate failure", "TLS"),
                                    ("Could not acquire lock", "verrouillé"),
                                    ("user is not in the sudoers file", "refusée"),
                                    ("Download interrupted", "interrompu")):
            with self.subTest(message=message):
                with redirect_stdout(io.StringIO()), patch.dict(os.environ, {"VIGIL_LANG": "fr"}):
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        clamav.checked_update_step([sys.executable, "-c", f"print({message!r}); raise SystemExit(1)"])

    def test_activation_rollback_on_incompatible_database_and_interrupt(self):
        candidate = self.root / "candidate"
        original = (self.profile / "daily.cvd").read_bytes()
        for error in (ValueError("incompatible engine"), KeyboardInterrupt()):
            self.install(candidate, 43, self.now)
            validated = clamav.signature_status(candidate)
            with clamav.signature_lock(self.profile), \
                 patch("vigil.clamav.signature_status", side_effect=[validated, error]):
                with self.assertRaises(type(error)):
                    clamav.publish_signatures(self.profile, candidate)
            self.assertEqual((self.profile / "daily.cvd").read_bytes(), original)
            self.assertEqual(list(self.profile.glob(".rollback-*")), [])

    def test_usb_rejects_corrupted_cvd_and_untrusted_cld(self):
        usb = self.root / "usb"
        usb.mkdir()
        candidate = self.root / "candidate"
        candidate.mkdir()
        for name in ("main.cvd", "daily.cvd", "bytecode.cld"):
            database_file(usb / name, 7, self.now)
        self.fake("sigtool", """#!/bin/sh
case "$2" in
    */main.cvd) echo "Version: 7"; echo "Build time: fixture"; echo "Verification OK." ;;
    *) echo "Corrupt"; exit 1 ;;
esac
""")

        @contextmanager
        def open_fixture(path, *_):
            with path.open("rb") as stream:
                yield stream.fileno()

        resources = [{"zone": "/investigation", "mountpoint": str(usb), "verified": True}]
        with patch("vigil.device_manager.status", return_value=resources), \
             patch("vigil.inspection.investigation_mounts", return_value={str(usb): 42}), \
             patch("vigil.inspection.open_evidence_path", side_effect=open_fixture), \
             patch("vigil.inspection.list_evidence_directory",
                   return_value=[(path.name, False) for path in usb.iterdir()]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(clamav.usb_candidates(candidate), {"main.cvd": 7})
        self.assertEqual({item.name for item in candidate.iterdir()}, {"main.cvd"})

    def test_update_lock_respects_an_active_scan(self):
        with clamav.signature_lock(self.profile, shared=True):
            with self.assertRaisesRegex(ValueError, "already active"):
                with patch.dict(os.environ, {"VIGIL_LANG": "en"}), clamav.signature_lock(self.profile):
                    self.fail("update lock acquired while scanner was active")


    def test_network_failure_reports_partial_if_signatures_were_updated(self):
        current = clamav.signature_status(self.profile)
        with patch("vigil.linux_distribution.identify", return_value="debian"), \
             patch("vigil.clamav.installed_clamav", return_value=["clamav"]), \
             patch("vigil.clamav.executable", return_value="/usr/bin/apt-get"), \
             patch("vigil.clamav.previous_status", return_value=current), \
             patch("vigil.clamav.checked_update_step", side_effect=ValueError("DNS")), \
             patch("vigil.clamav.refresh_signatures", return_value=current), \
             patch.dict(os.environ, {"VIGIL_LANG": "en"}), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(clamav.online_update(self.profile), 2)
            self.assertIn("Result: partial", output.getvalue())


    def test_package_manager_prompt_is_visible_before_it_receives_a_reply(self):
        manager = "print('Continue? [Y/n] ', end='', flush=True); assert input() == 'n'"
        runner = "from vigil.clamav import checked_update_step; import sys; checked_update_step(sys.argv[1:])"
        with subprocess.Popen([sys.executable, "-c", runner, sys.executable, "-c", manager],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            try:
                visible, _, _ = select.select([process.stdout], [], [], 5)
                self.assertTrue(visible, "Prompt was buffered while the child waited for input")
                self.assertIn(b"Continue? [Y/n] ", os.read(process.stdout.fileno(), 256))
                process.communicate(b"n\n", timeout=5)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.kill()
