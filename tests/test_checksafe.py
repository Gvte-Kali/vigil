import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ANALYSE_DIR = Path(__file__).resolve().parents[1] / "scripts" / "analyse"
sys.path.insert(0, str(ANALYSE_DIR))
import vigil_checksafe


class ChecksafeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.names = self.directory / "files.safe.name.tsv"
        self.hashes = self.directory / "files.safe.hash.tsv"
        self.evidence = self.directory / "example.bin"
        self.evidence.write_bytes(b"example")
        self.digest = hashlib.sha1(b"example").hexdigest()

    def test_valid_databases_preserve_historical_membership(self):
        self.names.write_bytes(b"name\r\nEXAMPLE.BIN\r\n")
        self.hashes.write_text(f"sha1\n{self.digest.upper()}\n", encoding="utf-8")
        names = vigil_checksafe.load_database(self.names, "name")
        hashes = vigil_checksafe.load_database(self.hashes, "sha1")
        self.assertTrue(vigil_checksafe.is_safe(self.evidence, names, hashes))
        self.assertTrue(vigil_checksafe.is_safe(self.evidence, None, hashes))
        self.assertFalse(vigil_checksafe.is_safe(self.evidence, set(), hashes))
        self.assertFalse(vigil_checksafe.is_safe(self.evidence, names, None))

    def test_invalid_rows_and_file_types_are_rejected(self):
        for invalid in (b"wrong\n", b"name\n../file\n", b"name\nfile\textra\n",
                        b"name\n\xff\n", b"name\n" + b"x" * 4097):
            with self.subTest(invalid=invalid[:20]):
                self.names.write_bytes(invalid)
                with self.assertRaises(ValueError):
                    vigil_checksafe.load_database(self.names, "name")
        self.hashes.symlink_to(self.names)
        with self.assertRaises(OSError):
            vigil_checksafe.load_database(self.hashes, "sha1")

    def test_record_cap_counts_duplicate_rows(self):
        self.names.write_text("name\nfirst\nfirst\n", encoding="utf-8")
        with patch.object(vigil_checksafe, "MAX_RECORDS", 1):
            with self.assertRaises(ValueError):
                vigil_checksafe.load_database(self.names, "name")

    def test_census_disables_filter_on_invalid_name_database(self):
        census = (ANALYSE_DIR / "vigil_census.sh").read_text(encoding="utf-8")
        block = census.split("# --- checksafe :", 1)[1].split("\n", 1)[1]
        block = block.split("# --- Marquage des doublons", 1)[0]
        self.hashes.write_text(f"sha1\n{self.digest}\n", encoding="utf-8")
        self.names.write_bytes(b"name\ninvalid/path\n")
        scope = {
            "os": os,
            "sys": sys,
            "do_checksafe": True,
            "stockage_dir": self.directory,
            "records": [{"path": self.evidence}],
            "is_safe": vigil_checksafe.is_safe,
            "load_database": vigil_checksafe.load_database,
        }
        exec(block, scope)
        self.assertFalse(scope["checksafe_active"])
        self.assertEqual(scope["safe_filtered_count"], 0)
        self.assertEqual(len(scope["checksafe_errors"]), 1)
