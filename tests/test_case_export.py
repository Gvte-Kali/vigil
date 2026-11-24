import hashlib
import json
import stat
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

            output = export_case(state, case, "Alice", root)
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
            with self.assertRaisesRegex(ValueError, "evidence copy missing"):
                export_case(state, case, "Alice", root)
            self.assertEqual(list(root.glob("affaire-*")), [output])
            self.assertFalse(list(root.glob(".vigil-export-*")))
