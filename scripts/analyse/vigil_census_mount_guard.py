#!/usr/bin/env python3
"""List validated Linux block mounts for an automatic case census."""
import os
import re
import stat
import sys
from pathlib import Path

TARGET = "/investigation"
ESCAPED = re.compile(r"\\([0-7]{3})")


def decode(value):
    return ESCAPED.sub(lambda match: chr(int(match[1], 8)), value)


def mount_records(lines):
    for line in lines:
        left, _, right = line.partition(" - ")
        fields, filesystem = left.split(), right.split()
        if len(fields) < 6 or len(filesystem) < 3:
            raise ValueError("unexpected mountinfo record")
        target = decode(fields[4])
        if target == TARGET or target.startswith(TARGET + "/"):
            yield fields[2], target, fields[5].split(","), decode(filesystem[1])


def validate_mounts(records, block_path=Path("/sys/dev/block")):
    targets = []
    for identity, target, options, source in records:
        if target in targets or "ro" not in options or "rw" in options:
            raise ValueError(f"{target}: ambiguous mount or mount not read-only")
        info = Path(source).stat()
        if not stat.S_ISBLK(info.st_mode):
            raise ValueError(f"{target}: source is not a block device")
        if identity != f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}":
            raise ValueError(f"{target}: source does not match the mounted device")
        node = (block_path / identity).resolve(strict=True)
        devices = [node]
        if (node / "partition").is_file():
            devices.append(node.parent)
        for device in devices:
            if (device / "ro").read_text(encoding="ascii").strip() != "1":
                raise ValueError(f"{target}: /dev/{device.name} lacks block read-only protection")
        targets.append(target)
    if not targets:
        raise ValueError("no mount under /investigation")
    return targets


def main():
    try:
        with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
            records = list(mount_records(stream))
        if sys.argv[1:] == ["--before-mount"]:
            if records:
                raise ValueError("/investigation already contains a mount; unmount before starting")
        else:
            for target in validate_mounts(records):
                sys.stdout.buffer.write(os.fsencode(target) + b"\0")
    except (OSError, ValueError) as error:
        print(f"Recensement automatique / Automatic census: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
