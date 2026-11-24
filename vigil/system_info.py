"""Read-only inventory for the Linux mount namespace visible to Vigil."""
import os
import re
from pathlib import Path

ZONES = ("/investigation", "/stockage")
LSBLK_COLUMNS = "NAME,PATH,TYPE,SIZE,FSTYPE,PARTTYPE,PTTYPE,RO,MODEL,FSAVAIL,FSUSE%"
ESCAPE = re.compile(r"\\([0-7]{3})")


def decode_mount(value):
    return ESCAPE.sub(lambda match: chr(int(match[1], 8)), value)


def zone_mounts(lines):
    zones = {path: [] for path in ZONES}
    for line in lines:
        before, separator, after = line.partition(" - ")
        fields = before.split()
        filesystem = after.split()
        if not separator or len(fields) < 6 or len(filesystem) < 3:
            continue
        target = decode_mount(fields[4])
        for zone, entries in zones.items():
            if target == zone or target.startswith(zone + "/"):
                entries.append((
                    target, decode_mount(filesystem[1]), filesystem[0],
                    "ro" if "ro" in fields[5].split(",") else "rw"
                    if "rw" in fields[5].split(",") else "",
                ))
    return zones


def read_zones():
    with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="replace") as stream:
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
