import hashlib
import io
import json
import os
import stat
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from vigil import storage
from vigil.case_export import export_case
from vigil.case_import import ArchiveError, ArchiveLimits, import_archive, verify_archive
from vigil.cli import app
from vigil.history import case_events
from vigil.reporting import case_pdf_reports, case_report


class CaseImportTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "old" / "cases.sqlite"
        self.target = self.root / "new" / "cases.sqlite"
        self.output = self.root / "out"
        self.output.mkdir()
        with storage.database(self.state) as connection:
            self.case = storage.create_case(connection, "Portable case", "Alice",
                                            reference="R-42", description="Fixture")

    def sample_archive(self, *, missing=False):
        originals = []
        records = []
        for number in range(2):
            original = self.root / f"original-{number}"
            original.write_bytes(f"case contents {number}".encode())
            originals.append(original)
            records.append(storage.register_file(self.state, self.case, original, "Alice"))
        custody = storage.case_storage_directory(self.state, self.case)
        run = custody / "analyses" / "vigil.census-test"
        run.mkdir(parents=True)
        (run / "terminal.log").write_text("fixture log")
        (run / "exit-code").write_text("0")
        (run / "report.pdf").write_bytes(b"%PDF-1.4 fixture")
        with sqlite3.connect(run / "census_fixture.sqlite") as connection:
            connection.execute("CREATE TABLE inventory_meta(id INTEGER, total_files INTEGER)")
            connection.execute("INSERT INTO inventory_meta VALUES (1, 2)")
        if missing:
            storage.evidence_copy_path(self.state, self.case, records[1]["id"]).unlink()
        with storage.database(self.state) as connection:
            storage.audit(connection, "Bob", self.case, "module.success", {"fixture": True})
        case_report(self.state, self.case)
        archive = export_case(self.state, self.case, "Alice", self.output).path / "affaire.tar.gz"
        return archive, originals, records

    def test_custom_archive_name_and_checksum(self):
        result = export_case(self.state, self.case, "Alice", self.root, "Affaire été")
        self.assertEqual(result.path.name, "Affaire été")
        self.assertEqual(result.archive.name, "Affaire été.tar.gz")
        repeated = export_case(self.state, self.case, "Alice", self.root, "Affaire été.TAR.GZ")
        self.assertEqual(repeated.path.name, "Affaire été (2)")
        self.assertEqual(repeated.archive.name, result.archive.name)
        checksum = result.archive.with_name(result.archive.name + ".sha256")
        self.assertEqual(checksum.read_text().strip(),
                         f"{hashlib.sha256(result.archive.read_bytes()).hexdigest()}  {result.archive.name}")
        self.assertEqual(verify_archive(result.path).source_id, self.case)
        with self.assertRaises(ValueError):
            export_case(self.state, self.case, "Alice", self.root, "../ailleurs")

    def test_complete_roundtrip_and_reexport(self):
        archive, originals, records = self.sample_archive()
        for source in originals:
            source.unlink()
        with storage.database(self.target) as connection:
            alice = storage.register_operator(connection, "Alice")
        verified = verify_archive(archive.parent)
        self.assertTrue(verified.sidecar_verified)
        self.assertEqual((verified.evidence_count, verified.missing), (2, 0))
        restored = import_archive(self.target, archive.parent, "Alice", expected_sha256=verified.sha256)
        self.assertEqual(restored["case_id"], self.case)
        self.assertFalse(restored["reused"])
        self.assertTrue(import_archive(self.target, archive, "Alice")["reused"])
        with storage.database(self.target) as connection:
            events = case_events(connection, self.case, limit=None)
            self.assertEqual(events[-1]["action"], "case.archive.import")
            self.assertEqual(events[0]["operator"], "Alice")
            self.assertNotEqual(events[0]["operator_id"], alice)
            self.assertEqual(events[0]["provenance"]["case_id"], self.case)
            self.assertEqual(connection.execute("SELECT reference FROM case_details").fetchone()[0], "R-42")
        for record in records:
            self.assertTrue(storage.verify_file(self.target, record["id"], "Alice")["matches"])
            self.assertEqual(storage.evidence_copy_path(self.target, self.case, record["id"]).stat().st_mode & 0o777, 0o400)
        self.assertEqual(case_pdf_reports(self.target, self.case)[0].read_bytes(), b"%PDF-1.4 fixture")
        custody = storage.case_storage_directory(self.target, self.case)
        self.assertTrue((custody / "analyses/vigil.census-test/terminal.log").is_file())
        self.assertTrue(list((custody / "rapports-json").glob("*/case.json")))
        second = export_case(self.target, self.case, "Alice", self.output).path / "affaire.tar.gz"
        with tarfile.open(second) as tar:
            manifest = json.load(tar.extractfile("affaire.json"))
        self.assertEqual(manifest["audit"][0]["provenance"], events[0]["provenance"])
        self.assertEqual({x["sha256"] for x in manifest["evidence"]}, {x["sha256"] for x in records})
        self.assertEqual(verify_archive(second).coverage, "complete")

    def test_partial_refuses_original_even_if_present_and_conflicts_make_distinct_cases(self):
        archive, _, records = self.sample_archive(missing=True)
        first = import_archive(self.state, archive, "Alice")
        self.assertNotEqual(first["case_id"], self.case)
        self.assertEqual(first["coverage"], "partial")
        with storage.database(self.state) as connection:
            receipt = json.loads(connection.execute(
                "SELECT provenance FROM case_archives WHERE case_id = ?", (first["case_id"],)
            ).fetchone()[0])
        self.assertFalse(storage.evidence_copy_path(
            self.state, first["case_id"], receipt["evidence_ids"][records[1]["id"]]).exists())
        with self.assertRaisesRegex(ValueError, "unavailable"):
            storage.verify_file(self.state, receipt["evidence_ids"][records[1]["id"]], "Alice")
        with storage.database(self.state) as connection:
            storage.delete_case(connection, first["case_id"], "Alice")
        with self.assertRaisesRegex(ArchiveError, "conflict"):
            import_archive(self.state, archive, "Alice")

    def test_legacy_import_and_packaged_legacy_files_survive_transfer(self):
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "info.json").write_text('{"name": "Legacy fixture"}')
        (legacy / "rapport_fixture.pdf").write_bytes(b"%PDF legacy")
        cli = CliRunner()
        result = cli.invoke(app, ["cases", "import", str(legacy), "--operator", "Alice",
                                  "--db", str(self.state)])
        self.assertEqual(result.exit_code, 0, result.output)
        identifier = json.loads(result.stdout)["id"]
        initial = export_case(self.state, identifier, "Alice", self.output).path
        restored = import_archive(self.target, initial, "Alice")
        self.assertTrue(restored["legacy"])
        custody = storage.case_storage_directory(self.target, identifier)
        self.assertEqual((custody / "projet-v1/info.json").read_text(), '{"name": "Legacy fixture"}')
        self.assertTrue(case_pdf_reports(self.target, identifier))
        renewed = export_case(self.target, identifier, "Alice", self.output).path
        with tarfile.open(renewed / "affaire.tar.gz") as tar:
            names = tar.getnames()
        self.assertIn("projet-v1/info.json", names)
        self.assertNotIn("resultats/projet-v1/info.json", names)

    def repack(self, source, filename, transform):
        target = self.root / filename
        with tarfile.open(source) as original, tarfile.open(target, "w:gz") as output:
            for member, content in transform([
                (member, original.extractfile(member).read() if member.isfile() else None) for member in original
            ]):
                output.addfile(member, io.BytesIO(content) if content is not None else None)
        return target

    def test_v2_and_cli(self):
        archive, _, _ = self.sample_archive()

        def to_v2(entries):
            for member, content in entries:
                if member.name == "affaire.json":
                    data = json.loads(content)
                    data["schema_version"] = 2
                    for key in ("members", "vigil_version", "audit_cutoff", "source_archive"):
                        data.pop(key)
                    content = json.dumps(data).encode()
                    member.size = len(content)
                    digest = hashlib.sha256(content).hexdigest().encode()
                if member.name == "SHA256SUMS":
                    content = b"\n".join(digest + b"  affaire.json" if line.endswith(b"  affaire.json") else line
                                          for line in content.split(b"\n"))
                yield member, content

        compatible = self.repack(archive, "old.tar.gz", to_v2)
        cli = CliRunner()
        verified = cli.invoke(app, ["cases", "verify-archive", str(compatible)])
        self.assertEqual(verified.exit_code, 0, verified.output)
        self.assertEqual(json.loads(verified.stdout)["schema_version"], 2)
        result = cli.invoke(app, ["cases", "import-archive", str(compatible), "--operator", "Alice",
                                  "--db", str(self.target)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout)["case_id"], self.case)

    def test_dangerous_members_corruption_and_quotas_leave_no_case(self):
        archive, _, _ = self.sample_archive()
        for name, kind in (("../outside", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("resultats/link", tarfile.SYMTYPE), ("resultats/hard", tarfile.LNKTYPE),
                           ("resultats/fifo", tarfile.FIFOTYPE), ("affaire.json", tarfile.REGTYPE)):
            with self.subTest(name=name):
                member = tarfile.TarInfo(name)
                member.type = kind
                bad = self.repack(archive, "malformed.tar.gz", lambda entries: entries + [(member, b"")])
                with self.assertRaisesRegex(ArchiveError, "dangerous"):
                    import_archive(self.target, bad, "Alice")
        corrupt = self.repack(archive, "bad_hash.tar.gz", lambda entries: [
            (member, b"x" * len(content)) if member.name == "affaire.json" else (member, content)
            for member, content in entries
        ])
        with self.assertRaisesRegex(ArchiveError, "mismatch"):
            verify_archive(corrupt)
        truncated = self.root / "truncated.tar.gz"
        truncated.write_bytes(archive.read_bytes()[:-12])
        with self.assertRaises(ArchiveError):
            verify_archive(truncated)
        with self.assertRaisesRegex(ArchiveError, "limit|budget"):
            verify_archive(archive, limits=ArchiveLimits(expanded=1))
        self.assertFalse(self.target.exists())
        self.assertFalse(list((self.target.parent / "legacy-custody").iterdir()))

    def test_sidecar_mismatch_and_late_export_change(self):
        archive, _, _ = self.sample_archive()
        sidecar = archive.with_name("affaire.tar.gz.sha256")
        sidecar.write_text("0" * 64 + "  affaire.tar.gz\n")
        with self.assertRaisesRegex(ArchiveError, "external archive SHA-256 mismatch"):
            verify_archive(archive)
        from vigil.case_export import archive_file

        def changed(tar, path, name):
            digest = archive_file(tar, path, name)
            if path.name == "terminal.log":
                path.write_text("changed after compression")
            return digest

        with patch("vigil.case_export.archive_file", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "case files changed"):
                export_case(self.state, self.case, "Alice", self.output)
        self.assertEqual(len(list(self.output.iterdir())), 1)

    def test_disk_sql_and_publication_failures_leave_no_case(self):
        archive, _, _ = self.sample_archive()
        with patch("vigil.case_import.shutil.disk_usage", return_value=type("Usage", (), {"free": 0})()):
            with self.assertRaisesRegex(ArchiveError, "staging space"):
                import_archive(self.target, archive, "Alice")
        self.assertFalse(self.target.exists())

        for error in (sqlite3.OperationalError("locked"), KeyboardInterrupt()):
            with patch("vigil.case_import.restore_history", side_effect=error):
                with self.assertRaises(type(error)):
                    import_archive(self.target, archive, "Alice")

        real_fsync = os.fsync

        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode) and Path(os.readlink(f"/proc/self/fd/{fd}")).name == "legacy-custody":
                raise OSError("simulated publication failure")
            return real_fsync(fd)

        with patch("vigil.case_import.os.fsync", side_effect=fail_directory):
            with self.assertRaisesRegex(OSError, "publication failure"):
                import_archive(self.target, archive, "Alice")
        with storage.database(self.target) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM cases").fetchone()[0], 0)
        self.assertFalse(list((self.target.parent / "legacy-custody").iterdir()))
