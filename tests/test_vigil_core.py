import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from vigil.cli import app
from vigil.core import BUILTIN_MODULES, discover


class CoreTest(unittest.TestCase):
    def test_manifest_discovery_reports_errors(self):
        manifests, errors = discover(BUILTIN_MODULES)
        self.assertIn("vigil.census", manifests)
        self.assertEqual(errors, {})
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            text = (BUILTIN_MODULES / "census.yaml").read_text()
            (directory / "a.yaml").write_text(text)
            (directory / "b.yaml").write_text(text)
            (directory / "c.yaml").write_text(text + "id: vigil.another\n")
            (directory / "d.yaml").write_text(
                text.replace("scripts/analyse/", "../")
            )
            manifests, errors = discover(directory)
            self.assertEqual(list(manifests), ["vigil.census"])
            self.assertEqual(set(errors), {"b.yaml", "c.yaml", "d.yaml"})

    def test_case_import_and_evidence_mismatch(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            legacy = directory / "project"
            legacy.mkdir()
            info = '{"name":"Legacy","extra":{"keep":true}}'
            (legacy / "info.json").write_text(info)
            (legacy / "chain_of_custody.log").write_text("original\n")
            database = str(directory / "cases.sqlite")
            options = ["--operator", "Fixture", "--db", database]
            args = ["cases", "import", str(legacy), *options]
            first = runner.invoke(app, args)
            self.assertEqual(first.exit_code, 0, first.output)
            case_id = json.loads(first.output)["id"]
            self.assertEqual(json.loads(runner.invoke(app, args).output)["id"], case_id)
            source = directory / "fixture.raw"
            source.write_bytes(b"synthetic")
            result = runner.invoke(app, ["evidence", "add", case_id, str(source), *options])
            self.assertEqual(result.exit_code, 0, result.output)
            evidence_id = json.loads(result.output)["id"]
            verify = ["evidence", "verify", evidence_id, *options]
            self.assertEqual(runner.invoke(app, verify).exit_code, 0)
            source.write_bytes(b"synthetic changed")
            result = runner.invoke(app, verify)
            self.assertEqual(result.exit_code, 2)
            self.assertFalse(json.loads(result.output)["matches"])
            self.assertEqual((legacy / "info.json").read_text(), info)
            self.assertEqual((legacy / "chain_of_custody.log").read_text(), "original\n")

    def test_terminal_arguments_are_preserved(self):
        path = Path(__file__).resolve().parents[1] / "gui" / "vigil_terminal.py"
        spec = importlib.util.spec_from_file_location("vigil_terminal", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.shutil, "which", side_effect=lambda name: (
            "/usr/bin/gnome-terminal" if name == "gnome-terminal" else None
        )):
            self.assertEqual(
                module.terminal_command(["bash", "path with spaces.sh"]),
                ["/usr/bin/gnome-terminal", "--", "bash", "path with spaces.sh"],
            )
        with patch.object(module.shutil, "which", return_value=None):
            with self.assertRaises(FileNotFoundError):
                module.terminal_command(["bash"])

    def test_census_adapter_preserves_index_and_attributes_execution(self):
        import sqlite3

        from vigil import storage
        from vigil.adapters import query_census

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index = root / "index with spaces.sqlite"
            with sqlite3.connect(index) as connection:
                connection.execute(
                    "CREATE TABLE files(path, size, mime_type, extension_mismatch, content_hash)"
                )
                connection.execute("INSERT INTO files VALUES ('example', 1, 'text/plain', 1, 'hash')")
            original = index.read_bytes()
            state = root / "state.sqlite"
            with storage.database(state) as connection:
                alice = storage.register_operator(connection, "Alice")
                self.assertEqual(storage.register_operator(connection, "Alice"), alice)
                case = storage.create_case(connection, "Fixture", "Alice")
            with patch("vigil.adapters.os.geteuid", return_value=1000):
                self.assertIn("example\t1\ttext/plain", query_census(state, case, "Alice", index))
            self.assertEqual(index.read_bytes(), original)
            with storage.database(state) as connection:
                audit = list(connection.execute(
                    "SELECT operator_id, case_id, action, details FROM audit ORDER BY sequence"
                ))
            self.assertEqual([row["action"] for row in audit],
                             ["case.create", "module.start", "module.success"])
            self.assertTrue(all(row["operator_id"] == alice and row["case_id"] == case for row in audit))
            self.assertEqual(audit[1]["details"], audit[2]["details"])
