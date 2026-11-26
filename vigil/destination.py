"""Validate writable destinations against the current Linux mount namespace."""
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath

from .system_info import decode_mount


@dataclass(frozen=True)
class Mount:
    id: int
    device: str
    root: PurePosixPath
    target: Path
    filesystem: str
    source: str

    def coordinate(self, path):
        return self.root / path.relative_to(self.target)


def read_mounts():
    mounts = []
    with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
        for line in stream:
            left, _, right = line.partition(" - ")
            fields, fs = left.split(), right.split()
            mounts.append(Mount(int(fields[0]), fields[2], PurePosixPath(decode_mount(fields[3])),
                                Path(decode_mount(fields[4])), fs[0], decode_mount(fs[1])))
    return mounts


def mount_at(path, mounts):
    return max((m for m in mounts if path.is_relative_to(m.target)),
               key=lambda m: (len(m.target.parts), m.id))


def block_disk(device):
    try:
        node = (Path("/sys/dev/block") / device).resolve(strict=True)
    except FileNotFoundError:
        return None
    return node.parent if (node / "partition").exists() else node


def backing_disk(mount):
    disk = block_disk(mount.device)
    if disk is None and mount.source.startswith("/dev/"):
        try:
            info = Path(mount.source).stat()
        except OSError:
            return None
        if info.st_rdev:
            disk = block_disk(f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}")
    return disk


def on_investigation(path, mount, mounts):
    zone = Path("/investigation")
    if path.is_relative_to(zone):
        return True
    zone_mount = mount_at(zone, mounts)
    if (zone_mount.device == mount.device
            and mount.coordinate(path).is_relative_to(zone_mount.coordinate(zone))):
        return True
    protected = [m for m in mounts if m.target.is_relative_to(zone)]
    if any(m.device == mount.device for m in protected):
        return True
    disk = backing_disk(mount)
    return disk is not None and any(backing_disk(m) == disk for m in protected)


@dataclass(frozen=True)
class Destination:
    path: Path
    filesystem: str
    available: int
    writable: bool
    investigation: bool


def destination_info(directory, *, fd=None):
    """Inspect an existing directory or the open descriptor used for writing."""
    directory = Path(directory)
    if fd is not None:
        directory = Path(f"/proc/self/fd/{fd}")
    path = directory.resolve(strict=True)
    if not path.is_dir():
        raise ValueError("Un dossier existant est requis / An existing directory is required")
    mounts = read_mounts()
    mount = mount_at(path, mounts)
    if fd is None:
        stats = os.statvfs(path)
    else:
        fields = Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines()
        mount_id = next((int(line.split()[1]) for line in fields if line.startswith("mnt_id:")), None)
        if mount_id != mount.id:
            raise ValueError("Montage de destination modifié / Destination mount changed")
        stats = os.fstatvfs(fd)
    writable = not stats.f_flag & os.ST_RDONLY and os.access(path, os.W_OK | os.X_OK)
    return Destination(path, mount.filesystem, stats.f_bavail * stats.f_frsize, writable,
                       on_investigation(path, mount, mounts))


def writable_destination(directory, *, fd=None):
    if Path(directory).absolute().is_relative_to("/investigation"):
        raise ValueError("Destination d’investigation interdite / Investigation destination forbidden")
    destination = destination_info(directory, fd=fd)
    if destination.investigation:
        raise ValueError("Destination d’investigation interdite / Investigation destination forbidden")
    if not destination.writable:
        raise ValueError("Dossier non inscriptible / Directory is not writable")
    return destination
