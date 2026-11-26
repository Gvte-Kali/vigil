import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/analyse"


class PartialCensusTest(unittest.TestCase):
    def test_index_preserves_find_diagnostics_with_or_without_readable_files(self):
        writer = (SCRIPTS / "vigil_census.sh").read_text().split(
            "<<'PYCENSUS'\n", 1
        )[1].split("\nPYCENSUS\n", 1)[0]
        for readable in (True, False):
            with self.subTest(readable=readable), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                find_log = root / "find.log"
                message = "find: '/investigation/test/broken': Input/output error"
                find_log.write_text(message + "\n", encoding="utf-8")
                raw, mime, encoding, result = (root / name for name in ("raw", "mime", "encoding", "result"))
                raw.write_text("/investigation/test/ok.txt\t5\t\t\t\t\t644\t0\t0\n" if readable else "")
                mime.write_text("text/plain\n" if readable else "")
                encoding.write_text("us-ascii\n" if readable else "")
                subprocess.run(
                    [sys.executable, "-", str(raw), str(mime), str(encoding),
                     str(result), "date", "Alice", "Test", "Lab", tmp,
                     "/investigation", "/stockage", "0", "0", "test",
                     "", "0", str(SCRIPTS), "fixture", str(find_log), "1"],
                    input=writer, text=True, check=True, capture_output=True, timeout=10,
                )
                summary = json.loads(result.read_text())
                with sqlite3.connect(summary["db_path"]) as db:
                    self.assertEqual(db.execute(
                        "SELECT scan_status, error_count, find_exit_code FROM inventory_meta"
                    ).fetchone(), ("partial", 1, 1))
                    self.assertEqual(db.execute(
                        "SELECT stage, message FROM inventory_errors"
                    ).fetchall(), [("find", message)])
                    self.assertEqual(db.execute("SELECT path FROM files").fetchall(),
                                     [("/investigation/test/ok.txt",)] if readable else [])
