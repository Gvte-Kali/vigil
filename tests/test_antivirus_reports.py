import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vigil.antivirus_reports import antivirus_reports, delete_antivirus_report, publish_report, report_name, scan_summary
from vigil.storage import antivirus_case, case_storage_directory, database


START = "2026-11-26T14:22:35+01:00"
ROOT = Path(__file__).resolve().parents[1]


def fixture(run, *, text="", expected=1, errors=0, infected=0):
    run.mkdir(parents=True, exist_ok=True)
    (run / "usb-triage.json").write_text(
        '{"hid_count":0,"baseline_count":1,"after_count":2,"new_count":1,"block_fail_count":0}'
    )
    (run / "support.txt").write_text("Support synthétique")
    (run / "scan-coverage.tsv").write_text(f"{expected} {errors}\n")
    (run / "clamav_fixture_20261126_142235.log").write_text(
        f"{text}\n----------- SCAN SUMMARY -----------\nScanned files: 1\nInfected files: {infected}\n"
    )


def fake_generator(pdf, *_):
    pdf.write_bytes(b"%PDF-1.4 fixture")


class AntivirusReportsTest(unittest.TestCase):
    def test_name_validation(self):
        self.assertEqual(report_name("", START), "rapport_antivirus_2026-11-26_14-22-35.pdf")
        self.assertEqual(report_name("Rapport équipe A", START), "Rapport équipe A.pdf")
        self.assertEqual(report_name("Original.PDF", START), "Original.PDF")
        for name in ("../escape", "a/b.pdf", "a\\b", ".hidden", "a\nb", "x" * 250):
            with self.subTest(name=name), self.assertRaises(ValueError):
                report_name(name, START)

    def test_integrity_of_result_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            fixture(run, infected=1, errors=1, text="/fixture.exe: FixtureSignature FOUND")
            summary = scan_summary(run, 0, 0)
            self.assertEqual((summary["status"], summary["threats"]), ("complete", 1))
            fixture(run, expected=3, text="WARNING: encrypted archive, skipped")
            summary = scan_summary(run, 0, 0)
            self.assertEqual(summary["status"], "partial")
            self.assertTrue(any("skipped" in issue for issue in summary["issues"]))
            pdf, status = publish_report(run, "Rapport équipe", START, "Alice", "", fake_generator, 0, 0)
            self.assertEqual(status, "partial")
            self.assertEqual(pdf.name, "Rapport équipe.pdf")
            with self.assertRaises(FileExistsError):
                publish_report(run, "Rapport équipe", START, "Alice", "", fake_generator, 0, 0)
            self.assertEqual(pdf.read_bytes(), b"%PDF-1.4 fixture")
            next_run = run / "next"
            next_run.mkdir()
            self.assertEqual(scan_summary(next_run, 125, 1)["status"], "failed")
            self.assertIsNone(scan_summary(next_run, 125, 1)["threats"])

    def test_catalogue_uses_recorded_metadata_and_leaves_legacy_result_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cases.sqlite"
            with database(state) as connection:
                case = antivirus_case(connection, "Alice")
            custody = case_storage_directory(state, case)
            run = custody / "scan-1"
            fixture(run)
            publish_report(run, "Personnalisé", START, "Alice", "", fake_generator, 0, 0)
            legacy = custody / "scan-2"
            legacy.mkdir()
            (legacy / "rapport_clamav_historique.pdf").write_bytes(b"%PDF")
            reports = antivirus_reports(state)
            self.assertEqual([(report.path.name, report.status) for report in reports],
                             [("Personnalisé.pdf", "complete"), ("rapport_clamav_historique.pdf", "unknown")])
            self.assertIsNone(reports[1].started)
            self.assertIsNone(reports[1].threats)

    @unittest.skipUnless(importlib.util.find_spec("reportlab"), "ReportLab unavailable")
    def test_full_script_publishes_one_report_and_retains_technical_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            scripts = base / "scripts"
            for name in ("clamav", "analyse", "lib"):
                (scripts / name).mkdir(parents=True)
            full = scripts / "clamav/vigil_clamav_full_scan.sh"
            shutil.copyfile(ROOT / "scripts/clamav/vigil_clamav_full_scan.sh", full)
            (base / "vigil").symlink_to(ROOT / "vigil")
            shutil.copyfile(ROOT / "scripts/lib/vigil-terminal.sh", scripts / "lib/vigil-terminal.sh")
            (scripts / "lib/vigil-device-ops.sh").write_text("vigil_device_begin() { :; }\n")
            (scripts / "clamav/vigil_scan_mounts.sh").write_text(
                "read_investigation_mounts() { INVESTIGATION_MOUNTS=(/investigation/synthetic); }\n"
            )
            (scripts / "analyse/vigil_usb_mount.sh").write_text(
                """echo '{"baseline_count":0,"after_count":1,"new_count":1,"hid_count":0}' > "$VIGIL_MOUNT_TRIAGE_JSON_OUT"
"""
            )
            (scripts / "analyse/vigil_usb_umount.sh").write_text("exit 0\n")
            (scripts / "clamav/vigil_clamav_scan.sh").write_text(
                r"""run="$VIGIL_ANTIVIRUS_REPORT_RUN"
echo '2 0' > "$run/scan-coverage.tsv"
printf '%s\n' '----------- SCAN SUMMARY -----------' 'Scanned files: 1' 'Infected files: 0' > "$run/clamav_fixture.log"
"""
            )
            run = base / "scan-fixture"
            run.mkdir()
            result = subprocess.run(
                ["bash", str(full), "--user", "Alice", "--report-name", "Rapport de test"],
                capture_output=True, text=True, env={**os.environ, "TERM": "dumb", "VIGIL_LANG": "fr",
                    "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}",
                    "VIGIL_BASE": str(base), "VIGIL_LEGACY_SCAN_DIR": str(run)},
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual([path.name for path in run.glob("*.pdf")], ["Rapport de test.pdf"])
            self.assertTrue((run / "usb-triage.json").is_file())
            self.assertTrue((run / "clamav_fixture.log").is_file())

    @unittest.skipUnless(importlib.util.find_spec("reportlab"), "ReportLab unavailable")
    def test_real_pdf_has_ordered_sections_and_no_success_on_partial_scan(self):
        generator = ROOT / "scripts/pdf/vigil_pdf.py"
        spec = importlib.util.spec_from_file_location("vigil_pdf", generator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            fixture(run, expected=2)
            (run / "clamav-signatures.json").write_text(json.dumps({
                "engine": "ClamAV 1.4.3", "engine_update": "outdated", "directory": "/profile/clamav",
                "daily_version": 42, "daily_published": START, "age_hours": 192, "freshness": "stale",
                "offline": True,
            }))
            target, status = publish_report(run, "Rapport", START, "Alice", "Fixture",
                                            module.build_antivirus_report, 0, 0)
            self.assertEqual(status, "partial")
            self.assertTrue(target.read_bytes().startswith(b"%PDF-"))
            self.assertEqual(list(run.glob("*.pdf")), [target])
            if shutil.which("pdftotext"):
                contents = subprocess.check_output(["pdftotext", str(target), "-"], text=True)
                titles = ["Identification du support", "Triage USB", "Analyse antivirus ClamAV",
                          "Fichiers ignorés, erreurs et limites", "Conclusion et statut final"]
                positions = [contents.index(title) for title in titles]
                self.assertEqual(positions, sorted(positions))
                self.assertIn("Scan incomplet", contents)
                self.assertIn("/profile/clamav", contents)
                self.assertIn("192 h", contents)
                self.assertNotIn("AUCUNE MENACE DÉTECTÉE", contents)


    def test_expected_empty_files_account_for_the_gap_but_symlinks_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            log = ("/investigation/example/a.txt: Empty file\n"
                   "/investigation/example/b.txt: Empty file\n"
                   "/investigation/example/link: Symbolic link\n"
                   "/investigation/example/fixture: Example FOUND")
            fixture(run, expected=3, infected=1, errors=1, text=log)
            summary = scan_summary(run, 0, 0)
            self.assertEqual((summary["status"], summary["threats"], summary["empty_files"]),
                             ("complete", 1, 2))
            fixture(run, expected=4, infected=1, errors=1, text=log)
            self.assertEqual(scan_summary(run, 0, 0)["status"], "partial")

    def test_delete_removes_only_catalogue_pdf_and_prevents_resync(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "cases.sqlite"
            with database(state) as connection:
                case = antivirus_case(connection, "Alice")
            custody = case_storage_directory(state, case)
            current, legacy = custody / "scan-current", custody / "scan-legacy"
            fixture(current)
            fixture(legacy)
            modern, _ = publish_report(current, "Recent", START, "Alice", "", fake_generator, 0, 0)
            old = legacy / "rapport_clamav_old.pdf"
            old.write_bytes(b"%PDF")
            unrelated = legacy / "triage_usb.pdf"
            unrelated.write_bytes(b"%PDF")
            rows = antivirus_reports(state)
            mirror = custody / "rapports" / current.name / modern.name
            self.assertTrue(mirror.is_file())
            delete_antivirus_report(state, next(row.path for row in rows if row.path.name == old.name))
            delete_antivirus_report(state, modern)
            self.assertEqual(antivirus_reports(state), [])
            self.assertFalse(old.exists())
            self.assertFalse(modern.exists())
            self.assertFalse(mirror.exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue((current / "antivirus-report.json").is_file())
            self.assertTrue(any(current.glob("clamav_*.log")))
            with self.assertRaises(ValueError):
                delete_antivirus_report(state, unrelated)
