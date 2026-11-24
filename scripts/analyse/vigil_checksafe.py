"""Read validated, single-column checksafe TSV databases."""
import hashlib
import os
import re
import stat

MAX_DATABASE_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 500_000
MAX_ROW_BYTES = 4096
SHA1_HEX = re.compile(r"[0-9a-fA-F]{40}")


def load_database(path, column):
    """Return None for a missing database. Reject an invalid database in full."""
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None

    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_DATABASE_BYTES:
            raise ValueError("fichier non régulier ou base trop volumineuse")
        expected_header = column.encode("ascii")
        header = stream.readline(MAX_ROW_BYTES + 1)
        if header.removesuffix(b"\n").removesuffix(b"\r") != expected_header:
            raise ValueError(f"en-tête attendu : {column}")
        total = len(header)
        entries = set()
        for number in range(1, MAX_RECORDS + 2):
            line = stream.readline(MAX_ROW_BYTES + 1)
            if not line:
                return entries
            total += len(line)
            if len(line) > MAX_ROW_BYTES or total > MAX_DATABASE_BYTES or number > MAX_RECORDS:
                raise ValueError("limite de taille ou de lignes dépassée")
            value = line.removesuffix(b"\n").removesuffix(b"\r").decode("utf-8")
            if column == "sha1":
                if not SHA1_HEX.fullmatch(value):
                    raise ValueError(f"SHA-1 invalide à la ligne {number + 1}")
                entries.add(bytes.fromhex(value))
            else:
                if (not value or value in {".", ".."} or "/" in value
                        or any(ord(character) < 32 or ord(character) == 127
                               for character in value)):
                    raise ValueError(f"nom invalide à la ligne {number + 1}")
                entries.add(value.lower())


def is_safe(path, names, signatures):
    """Apply the historical basename gate followed by SHA-1 membership."""
    if not signatures or (names is not None and os.path.basename(path).lower() not in names):
        return False
    try:
        with open(path, "rb") as stream:
            digest = hashlib.sha1()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return False
    return digest.digest() in signatures
