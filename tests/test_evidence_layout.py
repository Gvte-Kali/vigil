import hashlib
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from vigil import evidence_layout, storage
from vigil.case_export import export_case
from vigil.case_import import import_archive
from vigil.destination import Mount


class EvidenceLayoutTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.state = self.root / "state/cases.sqlite"
        with storage.database(self.state) as connection:
            self.case = storage.create_case(connection, "Case", "Alice")
        self.custody = storage.case_storage_directory(self.state, self.case)

    def old_copy(self, evidence_id, path, contents, *, recorded=None):
        target = self.custody / evidence_layout.legacy_path(evidence_id)
        target.parent.mkdir(parents=True)
        target.write_bytes(contents)
        target.chmod(0o400)
        digest = hashlib.sha256(contents if recorded is None else recorded).hexdigest()
        with storage.database(self.state) as connection:
            storage.add_evidence(connection, self.case, path, len(contents), digest, "Alice", evidence_id)
        return target

    def test_exact_filename_distinct_versions_and_archive_round_trip(self):
        source = self.root / "données" / "N° 42.DOC"
        source.parent.mkdir()
        source.write_bytes(b"original")
        first = storage.register_file(self.state, self.case, source, "Alice")
        source.write_bytes(b"updated")
        second = storage.register_file(self.state, self.case, source, "Alice")
        self.assertNotEqual(first["id"], second["id"])
        for row, expected in ((first, b"original"), (second, b"updated")):
            relative = Path(row["relative_path"])
            self.assertTrue(relative.parts[1].startswith("local_"))
            self.assertEqual(relative.parts[2:], source.parts[1:])
            copy = self.custody / relative
            self.assertEqual(copy.read_bytes(), expected)
            self.assertEqual(stat.S_IMODE(copy.stat().st_mode), 0o400)
            self.assertTrue(storage.verify_file(self.state, row["id"], "Alice", use_copy=True)["matches"])
        dest = self.root / "exports"
        dest.mkdir()
        archive = export_case(self.state, self.case, "Alice", dest)
        target = self.root / "new/cases.sqlite"
        imported = import_archive(target, archive.path, "Alice")["case_id"]
        self.assertEqual({r["relative_path"] for r in storage.case_evidence_rows(target, imported)},
                         {first["relative_path"], second["relative_path"]})
        storage.delete_evidence(self.state, self.case, second["id"], "Alice")
        self.assertFalse((self.custody / second["relative_path"]).exists())
        self.assertEqual((self.custody / first["relative_path"]).read_bytes(), b"original")

    def test_legacy_hash_failure_rolls_back_then_valid_migration_keeps_ids(self):
        old = self.old_copy("a" * 32, "/investigation/disk/foo/Épreuve.txt", b"one")
        corrupt = self.old_copy("b" * 32, "/investigation/disk/bar.bin", b"bad", recorded=b"two")
        with self.assertRaisesRegex(ValueError, "integrity check"):
            storage.migrate_evidence_copies(self.state, self.case, "Alice")
        self.assertTrue(old.exists())
        self.assertEqual(list(self.custody.rglob("Épreuve.txt")), [])
        corrupt.chmod(0o600)
        corrupt.write_bytes(b"two")
        corrupt.chmod(0o400)
        self.assertEqual(storage.migrate_evidence_copies(self.state, self.case, "Alice")["migrated"], 2)
        self.assertFalse(old.exists())
        rows = storage.case_evidence_rows(self.state, self.case)
        self.assertEqual({r["id"] for r in rows}, {"a" * 32, "b" * 32})
        self.assertTrue(all(r["relative_path"].startswith("preuves/origine-inconnue_") for r in rows))
        self.assertEqual(storage.migrate_evidence_copies(self.state, self.case, "Alice")["migrated"], 0)

    def test_legacy_archive_import_reconstructs_unknown_source(self):
        evidence_id = "a" * 32
        self.old_copy(evidence_id, "/investigation/source/nested/name.txt", b"legacy")
        dest = self.root / "out"
        dest.mkdir()
        archive = export_case(self.state, self.case, "Alice", dest)
        target = self.root / "restored/cases.sqlite"
        imported = import_archive(target, archive.path, "Alice")["case_id"]
        copy = storage.evidence_copy_path(target, imported, evidence_id)
        self.assertEqual(copy.read_bytes(), b"legacy")
        self.assertIn("origine-inconnue_", str(copy))
        self.assertTrue(str(copy).endswith("/investigation/source/nested/name.txt"))

    def test_rejects_symlinks_and_traversal(self):
        source = self.root / "evidence.txt"
        source.write_text("fixture")
        self.custody.mkdir(parents=True)
        (self.custody / "preuves").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)):
            storage.register_file(self.state, self.case, source, "Alice")
        self.assertEqual(storage.case_evidence_rows(self.state, self.case), [])
        with self.assertRaises(ValueError):
            evidence_layout.validate_path("preuves/source/../file")

    def test_disk_serial_and_partition_are_independent_of_device_name(self):
        root = Path("/investigation/fixture")
        output = json.dumps({"blockdevices": [{
            "type": "part", "partn": 2, "children": [{"type": "disk", "serial": "A-01", "model": "Drive"}],
        }]})
        layouts = []
        for name, mount_id in (("sda2", 10), ("sdc2", 23)):
            record = Mount(mount_id, "8:2", PurePosixPath("/"), root, "ext4", f"/dev/{name}")
            with patch("vigil.evidence_layout.read_mounts", return_value=[record]), \
                 patch("vigil.evidence_layout.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output)):
                layouts.append(evidence_layout.source_layout(root / "Photos/Image.JPG", (str(root), mount_id)))
        self.assertEqual(*layouts)
        self.assertEqual(layouts[0][2], Path("partition-2/Photos/Image.JPG"))
