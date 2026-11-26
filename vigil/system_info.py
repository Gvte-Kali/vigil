"""Read-only inventory for the Linux mount namespace visible to Vigil."""
import os
import re
from pathlib import Path

ZONES = ("/investigation", "/stockage")
LSBLK_COLUMNS = "NAME,PATH,TYPE,SIZE,FSTYPE,PARTTYPE,PTTYPE,RO,MODEL,TRAN,FSAVAIL,FSUSE%"
ESCAPE = re.compile(r"\\([0-7]{3})")


def decode_mount(value):
    return ESCAPE.sub(lambda match: chr(int(match[1], 8)), value)


def mount_records(lines):
    for line in lines:
        left, separator, right = line.partition(" - ")
        fields, filesystem = left.split(), right.split()
        if not separator or len(fields) < 6 or len(filesystem) < 3:
            raise ValueError("inconsistent mountinfo / état des montages incohérent")
        target = decode_mount(fields[4])
        zone = next((zone for zone in ZONES if target == zone or target.startswith(zone + "/")), None)
        if zone is not None:
            yield {
                "zone": zone, "mount_id": int(fields[0]), "major_minor": fields[2],
                "mountpoint": target, "path": decode_mount(filesystem[1]),
                "filesystem": filesystem[0], "mode": fields[5].split(","),
            }


def mounted_resources():
    with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
        return list(mount_records(stream))


def zone_mounts(lines):
    zones = {path: [] for path in ZONES}
    for row in mount_records(lines):
        mode = "ro" if "ro" in row["mode"] else "rw" if "rw" in row["mode"] else ""
        zones[row["zone"]].append((row["mountpoint"], row["path"], row["filesystem"], mode))
    return zones


def read_zones():
    with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
        return zone_mounts(stream)


def system_metrics():
    """Report kernel measurements, using None for unavailable values."""

    memory = None
    uptime = None
    load = None
    try:
        fields = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                fields[key] = int(value.split()[0]) * 1024
        total = fields["MemTotal"]
        available = fields["MemAvailable"]
        if 0 <= available <= total and total > 0:
            memory = (total - available, total)
    except (OSError, KeyError, ValueError, IndexError):
        pass
    try:
        uptime = int(float(Path("/proc/uptime").read_text(encoding="ascii").split()[0]))
    except (OSError, ValueError, IndexError, OverflowError):
        pass
    try:
        load = os.getloadavg()
    except OSError:
        pass
    return memory, uptime, load, os.cpu_count()


def cpu_ticks():
    with Path("/proc/stat").open(encoding="ascii") as stream:
        parts = stream.readline().split()
    if not parts or parts[0] != "cpu" or len(parts) < 6:
        raise ValueError("invalid aggregate CPU metrics")
    ticks = [int(value) for value in parts[1:9]]
    return sum(ticks), ticks[3] + ticks[4]
