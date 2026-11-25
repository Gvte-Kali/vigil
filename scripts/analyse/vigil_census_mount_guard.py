#!/usr/bin/env python3
"""List mounts whose identity and RO protections were verified by Vigil Core."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vigil.device_manager import verify_resource
from vigil.system_info import decode_mount as decode
from vigil.system_info import mount_records as core_mount_records


def mount_records(lines):
    for row in core_mount_records(lines):
        if row["zone"] == "/investigation":
            yield row["major_minor"], row["mountpoint"], row["mode"], row["path"]


def validate_mounts(records, block_path=Path("/sys/dev/block"), *, expected=None):
    targets = []
    if expected is not None:
        expected = {row["mountpoint"]: row for row in expected}
    for identity, target, options, source in records:
        if target in targets:
            raise ValueError(f"{target}: ambiguous mount / montage ambigu")
        verified = verify_resource({
            "zone": "/investigation", "major_minor": identity, "mountpoint": target,
            "mode": options, "path": source,
        }, block_path=block_path)
        if not verified["verified"]:
            raise ValueError(f"{target}: {verified['error']}")
        if expected is not None:
            previous = expected.get(target, {})
            if any(previous.get(key) != verified[key] for key in ("major_minor", "disk_sequence", "path")):
                raise ValueError(f"{target}: device context changed / contexte périphérique modifié")
        targets.append(target)
    if not targets or expected is not None and set(targets) != set(expected):
        raise ValueError("Investigation mounts changed or missing / montages d’investigation modifiés ou absents")
    return targets


def main():
    try:
        with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
            records = list(mount_records(stream))
        if sys.argv[1:] == ["--before-mount"]:
            if records:
                raise ValueError("/investigation already contains a mount; unmount before starting")
        else:
            context = os.environ.get("VIGIL_DEVICE_CONTEXT")
            for target in validate_mounts(records, expected=json.loads(context) if context else None):
                sys.stdout.buffer.write(os.fsencode(target) + b"\0")
    except (OSError, ValueError) as error:
        print(f"Recensement automatique / Automatic census: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
