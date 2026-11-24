"""Bounded, inert inspection of registered regular files."""
import mimetypes
import os
import re
import stat

PREVIEW_BYTES = 4096


def inspect_file(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("preview requires a regular file")
        sample = stream.read(PREVIEW_BYTES)
    hex_lines = []
    for start in range(0, len(sample), 16):
        chunk = sample[start:start + 16]
        text = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        hex_lines.append(f"{start:08x}  {chunk.hex(' '):47}  {text}")
    return {
        "size": info.st_size, "mode": stat.filemode(info.st_mode),
        "mtime": info.st_mtime,
        "mime_hint": mimetypes.guess_type(path.name)[0],
        "bytes_read": len(sample),
        "hex": "\n".join(hex_lines),
        "strings": "\n".join(match.decode("ascii") for match in re.findall(rb"[ -~]{4,}", sample)),
    }
