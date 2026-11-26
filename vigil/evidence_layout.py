"""Path allocation for immutable case evidence copies."""
import hashlib
import json
import os
import re
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from .destination import read_mounts


def validate_path(value):
    if not isinstance(value, str) or "\0" in value:
        raise ValueError("invalid evidence copy path")
    parts = value.split("/")
    if len(parts) < 3 or parts[0] != "preuves" or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid evidence copy path")
    return Path(*parts)


def legacy_path(evidence_id):
    return Path("preuves", evidence_id, "contenu")


def source_layout(original, mount=None, *, historical=False):
    path = Path(original)
    relative = path.relative_to("/") if path.is_absolute() else path
    if ".." in relative.parts or not relative.parts:
        relative = Path(path.name if path.name not in {"", ".", ".."} else "fichier")
    if historical or not path.is_absolute():
        return "origine-inconnue", "unknown", relative, "unknown"
    if mount is None:
        return "local", "local", relative, "local"

    root, mount_id = mount
    relative = path.relative_to(root)
    record = next((row for row in read_mounts() if row.id == mount_id and row.target == Path(root)), None)
    if record is None:
        raise ValueError("evidence mount changed")
    # The filesystem hierarchy may start inside a volume (e.g. a bind mount).
    relative = Path(*record.coordinate(path).relative_to(PurePosixPath("/")).parts)
    row = {}
    if record.source.startswith("/dev/"):
        try:
            result = subprocess.run(
                ["/usr/bin/lsblk", "--json", "--inverse", "--output",
                 "NAME,TYPE,WWN,SERIAL,MODEL,UUID,PARTUUID,PARTN,LABEL", "--", record.source],
                capture_output=True, text=True, timeout=3, check=True,
            )
            row, = json.loads(result.stdout)["blockdevices"]
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            pass
    disk = next((parent for parent in (row.get("children") or ()) if parent.get("type") == "disk"), row)
    volume = row.get("partuuid") or row.get("uuid")
    physical = disk.get("wwn") or disk.get("serial")
    if record.source.startswith("/dev/loop"):
        # Images can intentionally contain identical partition UUIDs.
        key = "image:" + loop_backing(record.device, record.source)
    elif physical:
        key = "disk:" + str(physical)
    elif volume:
        key = "volume:" + str(volume)
        # Filesystem identifiers can be cloned. Distinguish ports when udev
        # knows the physical connection but the device has no serial or WWN.
        by_path = Path("/dev/disk/by-path")
        aliases = sorted(link.name for link in by_path.glob("*")
                         if link.resolve() == Path(record.source).resolve())
        if aliases:
            key += ":port:" + re.sub(r"-part[0-9]+$", "", aliases[0])
    else:
        key = f"mount:{boot_id()}:{mount_id}"
    identity = key
    if row.get("type") == "part":
        part = row.get("partn") or volume
        if part:
            relative = Path("partition-" + safe_label(str(part)), relative)
            identity = json.dumps([key, str(part)], ensure_ascii=True)
    label = disk.get("model") if physical else (row.get("label") or record.filesystem)
    return safe_label(label or "support"), key, relative, identity


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def loop_backing(device, source):
    node = (Path("/sys/dev/block") / device).resolve()
    for candidate in (node, node.parent, Path("/sys/class/block") / Path(source).name):
        try:
            backing = Path((candidate / "loop/backing_file").read_text().strip())
            info = backing.stat()
            return f"{info.st_dev}:{info.st_ino}"
        except OSError:
            continue
    return f"{boot_id()}:{device}"


def safe_label(label):
    return re.sub(r"[^\w.-]+", "-", str(label)).strip(".-")[:48] or "support"


def checked_copy(custody, relative):
    path = custody / validate_path(str(relative))
    try:
        safe = path.resolve() == path.absolute()
    except RuntimeError as error:
        raise ValueError("unsafe evidence copy path") from error
    if not safe:
        raise ValueError("unsafe evidence copy path")
    return path


@contextmanager
def copy_parent(custody, relative, *, create=False):
    parts = validate_path(str(relative)).parts
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for part in custody.absolute().parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                else:
                    os.fsync(fd)
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, parts[-1]
    finally:
        os.close(fd)


def publish_copy(staged, custody, relative):
    with copy_parent(custody, relative, create=True) as (fd, name):
        os.link(staged, name, dst_dir_fd=fd, follow_symlinks=False)
        try:
            os.fsync(fd)
        except OSError:
            os.unlink(name, dir_fd=fd)
            raise


def allocate_copy(staged, custody, layout, evidence_id):
    label, key, relative, _ = layout
    source = f"{label}_{hashlib.sha256(key.encode()).hexdigest()[:12]}"
    primary = Path("preuves", source, relative)
    try:
        publish_copy(staged, custody, primary)
        return primary
    except (FileExistsError, NotADirectoryError):
        # Distinguish a normal file/directory collision from a symlink.
        checked_copy(custody, primary)
    alternative = Path("preuves", source + "-variante-" + evidence_id, relative)
    publish_copy(staged, custody, alternative)
    return alternative


def require_readonly(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o400:
        raise ValueError("invalid local evidence copy: expected a regular file with mode 0400")
