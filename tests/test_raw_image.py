import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from vigil.images import inspect_raw


class RawImageTest(unittest.TestCase):
    def test_inspects_synthetic_mbr_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.raw"
            data = bytearray(2048)
            data[510:512] = b"\x55\xaa"
            data[450] = 0x83
            struct.pack_into("<II", data, 454, 1, 2)
            path.write_bytes(data)
            result = inspect_raw(path)
            self.assertEqual(
                result["partitions"],
                [{"number": 1, "type": "0x83", "offset": 512, "size": 1024}],
            )
            self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(path.read_bytes(), data)
            struct.pack_into("<II", data, 454, 1, 8)
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "runs past"):
                inspect_raw(path)
            data[450] = 0xEE
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "GPT"):
                inspect_raw(path)
