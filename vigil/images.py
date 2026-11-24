"""Read partition metadata from a regular RAW image without mounting it."""
import hashlib
import os
import stat
import struct
from pathlib import Path

from .storage import file_identity

EXTENDED_MBR = {0x05, 0x0F, 0x85}


def inspect_raw(path: Path, sector_size: int = 512):
    if sector_size not in (512, 4096):
        raise ValueError("sector size must be 512 or 4096")
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("image must be a regular file")
        first = stream.read(512)
        if first.startswith((b"EVF\x09", b"EVF2", b"AFF10", b"LVF\x09")):
            raise ValueError("image is a container; RAW inspection is unavailable")
        partitions = []
        table = "unknown"
        if len(first) == 512 and first[510:] == b"\x55\xaa":
            table = "mbr"
            for index, offset in enumerate(range(446, 510, 16), 1):
                entry = first[offset:offset + 16]
                kind = entry[4]
                if not kind:
                    continue
                if kind == 0xEE or kind in EXTENDED_MBR:
                    raise ValueError("GPT and extended MBR partitions require another reader")
                start, length = struct.unpack_from("<II", entry, 8)
                if entry[0] not in (0, 0x80) or not start or not length:
                    raise ValueError(f"invalid MBR partition {index}")
                end = (start + length) * sector_size
                if end > before.st_size:
                    raise ValueError(f"MBR partition {index} runs past the image")
                partitions.append({
                    "number": index, "type": f"0x{kind:02x}",
                    "offset": start * sector_size, "size": length * sector_size,
                })
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if not (
            file_identity(before) == file_identity(os.fstat(stream.fileno()))
            == file_identity(path.stat(follow_symlinks=False))
        ):
            raise ValueError("image changed during inspection")
    return {"partition_table": table, "sector_size": sector_size,
            "partitions": partitions, "size": before.st_size, "sha256": digest}
