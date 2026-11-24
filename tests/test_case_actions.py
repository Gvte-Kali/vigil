import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from vigil import storage
from vigil.adapters import analysis_command
from vigil.core import BUILTIN_MODULES, discover

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/analyse"


class CaseActionsTest(unittest.TestCase):
    def test_remove_copy_and_audit_without_touching_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "cases.sqlite"
            original = root / "source"
            original.write_bytes(b"fixture")
            with storage.database(state) as db:
                one = storage.create_case(db, "First", "Alice")
                two = storage.create_case(db, "Second", "Alice")
            record = storage.register_file(state, one, original, "Alice")
            copy = storage.evidence_copy_path(state, one, record["id"])
            with self.assertRaises(ValueError):
                storage.delete_evidence(state, two, record["id"], "Alice")
            self.assertTrue(copy.is_file())
            storage.delete_evidence(state, one, record["id"], "Alice")
            self.assertFalse(copy.exists())
            self.assertEqual(original.read_bytes(), b"fixture")
            with storage.database(state) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM evidence").fetchone()[0], 0)
                row = db.execute("SELECT details FROM audit WHERE action = 'evidence.delete'").fetchone()
                self.assertEqual(json.loads(row[0])["sha256"], record["sha256"])

    def test_builtin_commands_bind_case_and_allocate_distinct_result_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with storage.database(state) as db:
                case = storage.create_case(db, "Fixture", "Alice")
            manifests, _ = discover(BUILTIN_MODULES)
            paths = set()
            for name, manifest in manifests.items():
                argv = analysis_command(state, case, "Alice", name)
                self.assertIn("VIGIL_LEGACY_PROJECT=Fixture", argv)
                self.assertIn("VIGIL_ACTIVE_USER=Alice", argv)
                self.assertIn("VIGIL_CASE_ANALYSIS=1", argv)
                script = Path(argv[argv.index("--json-out") - 1])
                self.assertEqual(script.name, Path(manifest.entrypoint).name)
                output = Path(argv[argv.index("--json-out") + 1])
                self.assertEqual(output.parent.name, "analyses")
                paths.add(output)
            self.assertEqual(len(paths), len(manifests))
            with self.assertRaises(ValueError):
                analysis_command(state, case, "Alice", "vigil.unknown")

    def test_legacy_archives_adapter_uses_validated_fixture_and_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts/analyse"
            scripts.mkdir(parents=True)
            shutil.copy(SCRIPTS / "vigil_case_analysis.sh", scripts)
            source = root / "fixture"
            source.mkdir()
            (source / "note.txt").write_text("synthetic fixture")
            (scripts / "vigil_census_mount_guard.py").write_text(
                f"import sys\nsys.stdout.buffer.write({os.fsencode(source) + bytes([0])!r})\n")
            output = root / "results"
            output.mkdir()
            result = subprocess.run(
                ["/usr/bin/bash", str(SCRIPTS / "vigil_archives.sh"),
                 "--no-pdf", "--json-out", str(output)],
                env={**os.environ, "TERM": "dumb", "VIGIL_BASE": tmp,
                     "VIGIL_CASE_ANALYSIS": "1", "VIGIL_LEGACY_PROJECT": "Fixture",
                     "VIGIL_ACTIVE_USER": "Alice", "VIGIL_LEGACY_CASE_DIR": str(output),
                     "VIGIL_ANALYSIS_RESULTS": str(output)},
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads((output / "vigil_archives.json").read_text())
            self.assertEqual(payload["total_files"], 1)
