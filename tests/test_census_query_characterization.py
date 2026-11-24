"""Exercise the existing census query CLI on synthetic SQLite data."""
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts" / "analyse" / "vigil_census_query.py"
)


class CensusQueryTest(unittest.TestCase):
    def test_mime_and_extension_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "census.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE files (path, size, mime_type,"
                    " extension_mismatch, content_hash, extension)"
                )
                connection.executemany(
                    "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        ("/fixture/a.jpg", 11, "image/jpeg", 0, "digest-a", ".jpg"),
                        ("/fixture/b.png", 22, "image/png", 0, "digest-b", ".png"),
                    ],
                )
            result = self.run_query(database, "--mime", "image/", "--extension", "JPG")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "/fixture/a.jpg\t11\timage/jpeg\t0\tdigest-a\n")

    def test_rejects_missing_filter_and_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "missing.sqlite"
            self.assertEqual(self.run_query(database).returncode, 2)
            self.assertEqual(self.run_query(database, "--mismatched").returncode, 1)
            self.assertFalse(database.exists())

    @staticmethod
    def run_query(database, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--index", str(database), *arguments],
            capture_output=True,
            text=True,
            timeout=10,
        )
