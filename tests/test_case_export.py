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
                connection.execute("PRAGMA user_version = 1")
            with storage.database(state) as connection:
                self.assertEqual(storage.require_active_case(connection, case)["name"], "Version one case")
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
