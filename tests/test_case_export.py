import hashlib
import json
import stat
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from vigil import storage
from vigil.case_export import export_case
from vigil.case_removal import purge_case
from vigil.reporting import case_report


class CaseExportTest(unittest.TestCase):
    def test_evidence_copy_and_archive_after_source_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state" / "cases.sqlite"
            source = root / "source.sh"
            source.write_bytes(b"synthetic evidence")
            source.chmod(0o755)
            with storage.database(state) as connection:
                case = storage.create_case(connection, "Synthetic case", "Alice")

            record = storage.register_file(state, case, source, "Alice")
            copy = storage.evidence_copy_path(state, case, record["id"])
            self.assertEqual(copy.read_bytes(), source.read_bytes())
            self.assertEqual(stat.S_IMODE(copy.stat().st_mode), 0o400)
            source.unlink()
            self.assertTrue(storage.verify_file(state, record["id"], "Alice", use_copy=True)["matches"])

            output = export_case(state, case, "Alice", root).path
            archive_path = output / "affaire.tar.gz"
            self.assertEqual((output / "affaire.tar.gz.sha256").read_text().split()[0],
                             hashlib.sha256(archive_path.read_bytes()).hexdigest())
            with tarfile.open(archive_path) as archive:
                metadata = json.load(archive.extractfile("affaire.json"))
                name = metadata["evidence"][0]["archive_path"]
                self.assertEqual(archive.getmember(name).mode, 0o400)
                self.assertEqual(archive.extractfile(name).read(), b"synthetic evidence")
                self.assertIn(record["sha256"], archive.extractfile("SHA256SUMS").read().decode())
            copy.unlink()
            partial = export_case(state, case, "Alice", root)
            self.assertEqual(partial.missing, (str(source),))
            with tarfile.open(partial.path / "affaire.tar.gz") as archive:
                metadata = json.load(archive.extractfile("affaire.json"))
                self.assertEqual(metadata["coverage"], "partial")
                row = metadata["evidence"][0]
                self.assertEqual(row["copy_status"], "missing")
                self.assertIsNone(row["archive_path"])
                self.assertEqual(row["sha256"], record["sha256"])
            self.assertEqual(set(root.glob("affaire-*")), {output, partial.path})
            self.assertFalse(list(root.glob(".vigil-export-*")))


    def test_case_deletion_keeps_custody_and_rejects_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "cases.sqlite"
            source = root / "original"
            source.write_bytes(b"fixture")
            with storage.database(state) as connection:
                case = storage.create_case(connection, "Fixture", "Alice")
            record = storage.register_file(state, case, source, "Alice")
            with storage.database(state) as connection:
                storage.delete_case(connection, case, "Alice")
                self.assertIsNotNone(connection.execute(
                    "SELECT 1 FROM audit WHERE case_id = ? AND action = 'case.delete'", (case,)
                ).fetchone())
            self.assertTrue(storage.evidence_copy_path(state, case, record["id"]).is_file())
            self.assertTrue(source.is_file())
            with self.assertRaisesRegex(ValueError, "unknown or deleted case"):
                export_case(state, case, "Alice", root)


    def test_version_one_database_migrates_without_losing_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with storage.database(state) as connection:
                case = storage.create_case(connection, "Version one case", "Alice")
            with sqlite3.connect(state) as connection:
                connection.execute("DROP TABLE deleted_cases")
                connection.execute("DROP TABLE case_directories")
                connection.execute("DROP TABLE case_details")
                connection.execute("DROP TABLE archive_events")
                connection.execute("DROP TABLE archive_operators")
                connection.execute("DROP TABLE case_archives")
                connection.execute("PRAGMA user_version = 1")
            with storage.database(state) as connection:
                self.assertEqual(storage.require_active_case(connection, case)["name"], "Version one case")
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 5)


    def test_existing_case_directory_is_renamed_without_losing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with storage.database(state) as connection:
                first = storage.create_case(connection, "Équipe / 42", "Alice")
                second = storage.create_case(connection, "Equipe 42", "Alice")
            with sqlite3.connect(state) as connection:
                connection.execute("DROP TABLE case_directories")
                connection.execute("DROP TABLE case_details")
                connection.execute("DROP TABLE archive_events")
                connection.execute("DROP TABLE archive_operators")
                connection.execute("DROP TABLE case_archives")
                connection.execute("PRAGMA user_version = 2")
            previous = state.parent / "legacy-custody" / first
            previous.mkdir(parents=True)
            original = previous / "fixture"
            original.write_bytes(b"case contents")
            original.chmod(0o400)
            renamed = storage.case_storage_directory(state, first)
            self.assertEqual(renamed.name, "Equipe_42")
            self.assertEqual((renamed / "fixture").read_bytes(), b"case contents")
            self.assertEqual((renamed / "fixture").stat().st_mode & 0o777, 0o400)
            self.assertFalse(previous.exists())
            self.assertEqual(storage.case_storage_directory(state, first), renamed)
            self.assertEqual(storage.case_storage_directory(state, second).name, "Equipe_42_2")

    def test_manager_reads_published_metadata_without_opening_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with storage.database(state) as connection:
                case = storage.create_case(connection, "Metrics", "Alice")
            directory = storage.case_storage_directory(state, case)
            run = directory / "analyses" / "vigil.census-fixture"
            run.mkdir(parents=True)
            (run / "exit-code").write_text("0\n")
            with sqlite3.connect(run / "census_fixture.sqlite") as connection:
                connection.execute("CREATE TABLE inventory_meta(id INTEGER, total_files INTEGER)")
                connection.execute("INSERT INTO inventory_meta VALUES (1, 42)")
            reports = directory / "rapports"
            reports.mkdir()
            (reports / "fixture.pdf").touch()
            self.assertEqual(storage.case_manager_artifacts(state, case, "Metrics"), {
                "path": str(directory), "inventory": 42, "analyses": 1, "reports": 1,
            })

    def test_purge_removes_only_selected_local_case_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "db" / "cases.sqlite"
            legacy = root / "legacy-original"
            legacy.mkdir()
            source = legacy / "source"
            source.write_bytes(b"fixture")
            with storage.database(state) as connection:
                case = storage.create_case(connection, "Imported", "Alice", legacy_path=str(legacy))
                other = storage.create_case(connection, "Other", "Alice")
            record = storage.register_file(state, case, source, "Alice")
            copy = storage.evidence_copy_path(state, case, record["id"])
            local_report = case_report(state, case)
            other_report = case_report(state, other)
            exported = export_case(state, case, "Alice", root).path

            self.assertEqual(purge_case(state, case), [])
            self.assertFalse(copy.exists())
            self.assertFalse(local_report.exists())
            self.assertTrue(other_report.is_dir())
            self.assertTrue(exported.is_dir())
            self.assertEqual(source.read_bytes(), b"fixture")
            with storage.database(state) as connection:
                self.assertEqual(connection.execute("SELECT id FROM cases").fetchone()[0], other)
                self.assertIsNone(connection.execute(
                    "SELECT 1 FROM audit WHERE case_id = ?", (case,)).fetchone())
