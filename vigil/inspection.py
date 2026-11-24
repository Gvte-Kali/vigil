"""Bounded, inert inspection of registered regular files."""
import mimetypes
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path

PREVIEW_BYTES = 4096


def investigation_mounts():
    roots = {}
    with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
        for line in stream:
            fields = line.split(" - ", 1)[0].split()
            target = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), fields[4])
            if target == "/investigation" or target.startswith("/investigation/"):
                # Ambiguous stacked mounts are excluded even if both are read-only.
                roots[target] = (int(fields[0]) if target not in roots
                                 and "ro" in fields[5].split(",") else None)
    return {target: mount_id for target, mount_id in roots.items() if mount_id is not None}


@contextmanager
def open_evidence_path(path, root, mount_id, *, directory=False):
    path, root = Path(path), Path(root)
    relative = path.relative_to(root)
    if not root.is_absolute() or ".." in path.parts:
        raise ValueError("invalid evidence path")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open("/", flags | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:], 2):
            is_directory = directory or index < len(path.parts) or not relative.parts
            entry_flags = flags | os.O_DIRECTORY if is_directory else os.O_PATH | os.O_NOFOLLOW
            next_fd = os.open(part, entry_flags,
                              dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
            if index >= len(root.parts):
                details = Path(f"/proc/self/fdinfo/{descriptor}").read_text(encoding="ascii")
                actual_mount = re.search(r"^mnt_id:\s*(\d+)$", details, re.MULTILINE)
                if (not actual_mount or int(actual_mount[1]) != mount_id
                        or not os.fstatvfs(descriptor).f_flag & os.ST_RDONLY):
                    raise ValueError("evidence mount changed or is not read-only")
        if not directory and not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("preview requires a regular file")
        yield descriptor
    finally:
        os.close(descriptor)


def list_evidence_directory(path, root, mount_id):
    with open_evidence_path(path, root, mount_id, directory=True) as descriptor:
        with os.scandir(descriptor) as entries:
            rows = []
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    rows.append((entry.name, True))
                elif entry.is_file(follow_symlinks=False):
                    rows.append((entry.name, False))
    return sorted(rows, key=lambda row: (not row[1], row[0].casefold(), row[0]))


def inspect_file(path, *, mount=None):
    if mount is not None:
        with open_evidence_path(path, *mount) as source:
            return _inspect_descriptor(path, os.open(f"/proc/self/fd/{source}", os.O_RDONLY | os.O_CLOEXEC))
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    return _inspect_descriptor(path, descriptor)


def _inspect_descriptor(path, descriptor):
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
