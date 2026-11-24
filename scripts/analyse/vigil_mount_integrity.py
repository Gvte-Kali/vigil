#!/usr/bin/env python3
"""Fingerprint the complete set of readable regular files on one mounted volume."""
import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from vigil_census_mount_guard import decode


def mount_identity(target):
    matches = []
    with open("/proc/self/mountinfo", encoding="utf-8", errors="surrogateescape") as stream:
        for line in stream:
            left, _, right = line.partition(" - ")
            fields, fs = left.split(), right.split()
            if decode(fields[4]) == target:
                if "ro" not in fields[5].split(","):
                    raise ValueError(f"{target}: montage non protégé en lecture seule")
                matches.append([fields[0], fields[2], decode(fields[3]), fs[0], decode(fs[1])])
    if len(matches) != 1:
        raise ValueError(f"{target}: montage introuvable ou ambigu")
    return [Path("/proc/sys/kernel/random/boot_id").read_text().strip(), *matches[0]]


def require_mount(fd, mount_id):
    with open(f"/proc/self/fdinfo/{fd}", encoding="ascii") as stream:
        actual = next((line.split()[1] for line in stream if line.startswith("mnt_id:")), None)
    if actual != mount_id or not os.fstatvfs(fd).f_flag & os.ST_RDONLY:
        raise ValueError("montage modifié ou sous-montage rencontré")


def tree_digest(target, mount_id):
    def fail(error):
        raise error

    digest = hashlib.sha256()
    count = 0
    root = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        require_mount(root, mount_id)
        for folder, dirs, files, directory in os.fwalk(".", dir_fd=root, onerror=fail):
            require_mount(directory, mount_id)
            dirs.sort(key=os.fsencode)
            for name in sorted(files, key=os.fsencode):
                fd = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
                try:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode):
                        continue
                    require_mount(fd, mount_id)
                    with open(f"/proc/self/fd/{fd}", "rb") as stream:
                        content = hashlib.file_digest(stream, "sha256").digest()
                    after = os.fstat(fd)
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise ValueError(f"fichier modifié pendant la lecture : {os.path.join(folder, name)!r}")
                    relative = os.fsencode(os.path.join(folder, name))
                    digest.update(len(relative).to_bytes(8, "big") + relative + content)
                    count += 1
                finally:
                    os.close(fd)
    finally:
        os.close(root)
    return digest.hexdigest(), count


def check(operation, target, directory):
    if not target.startswith("/investigation/") or os.path.normpath(target) != target:
        raise ValueError("point de montage hors de la zone d’investigation")
    identity = mount_identity(target)
    key = hashlib.sha256(os.fsencode(target)).hexdigest()
    path = directory / f"integrity-{key}.json"
    if operation == "verify":
        try:
            reference = json.loads(path.read_text(encoding="ascii"))
        except FileNotFoundError as exc:
            raise ValueError("aucune référence complète pour ce montage") from exc
        if reference["version"] != 1 or reference["identity"] != identity:
            raise ValueError("référence d’un autre montage ou d’une autre session")
    else:
        path.unlink(missing_ok=True)

    digest, count = tree_digest(target, identity[1])
    if mount_identity(target) != identity:
        raise ValueError("le montage a changé pendant la lecture")
    if operation == "record":
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump({"version": 1, "identity": identity, "target": target,
                           "sha256": digest, "files": count}, stream)
                stream.flush()
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        print(f"Référence SHA-256 : {digest} ({count} fichier(s))")
        return 0
    if (digest, count) != (reference["sha256"], reference["files"]):
        print(f"Écart d’intégrité : référence {reference['sha256']} ({reference['files']} fichier(s)), "
              f"recalcul {digest} ({count} fichier(s)).")
        return 2
    print(f"Intégrité vérifiée : {digest} ({count} fichier(s)).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("record", "verify"))
    parser.add_argument("target")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        return check(args.operation, args.target, args.directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Intégrité non vérifiable : {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
