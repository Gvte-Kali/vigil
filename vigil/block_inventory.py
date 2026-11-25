"""Shared Linux block inventory for the mount and acquisition triage."""
import json
import os
import stat
import subprocess
from pathlib import Path

DEVICE_COLUMNS = "NAME,TYPE,SIZE,TRAN,RM,MODEL,SERIAL,FSTYPE,MAJ:MIN,MOUNTPOINTS,RO,LABEL,PTTYPE,PARTTYPE"


def command(program, *args):
    return subprocess.run((program, *args), capture_output=True, text=True, check=True).stdout


def devices(*args, human=False):
    options = ("/usr/bin/lsblk", "--json", "--paths")
    if not human:
        options += ("--bytes",)
    options += ("--output",)
    try:
        output = command(*options, DEVICE_COLUMNS + ",PARTTYPENAME", *args)
    except subprocess.CalledProcessError as error:
        if "PARTTYPENAME" not in (error.stderr or ""):
            raise
        output = command(*options, DEVICE_COLUMNS, *args)
    return json.loads(output)["blockdevices"]


def external_storage(disk, partition=None):
    return disk.get("tran") == "usb" or (partition or disk).get("rm") in (1, "1")


def filesystem(row):
    if not row.get("fstype") or not row.get("label"):
        for key, field in (("fstype", "TYPE"), ("label", "LABEL")):
            if not row.get(key):
                try:
                    row[key] = command("/usr/sbin/blkid", "-o", "value", "-s", field, "--", row["name"]).strip()
                except (OSError, subprocess.CalledProcessError):
                    pass
    return row.get("fstype")


def block_access(row):
    mode = row.get("ro")
    return "RO" if mode in (1, "1") else "RW" if mode in (0, "0") else "?"


def fields(*values):
    return "|".join("".join(c if c.isprintable() and c not in "|\\" else " "
                           for c in str(value if value is not None else "")).strip()
                    for value in values)


def mount_inventory():
    for disk in devices(human=True):
        if disk["type"] != "disk":
            continue
        name = disk["name"].removeprefix("/dev/")
        print(fields("parent", name, disk["size"], disk.get("model"), block_access(disk)))
        children = disk.get("children", ())
        if not children and external_storage(disk) and not any(disk.get("mountpoints") or ()):
            print(fields("rawdisk", name, disk["size"], disk.get("model"), filesystem(disk), disk.get("label")))
        for part in children:
            if part["type"] != "part" or not external_storage(disk, part):
                continue
            part_name = part["name"].removeprefix("/dev/")
            if mountpoint := next((m for m in part.get("mountpoints") or () if m), None):
                if fields(mountpoint) == mountpoint:
                    print(fields("mounted", part_name, mountpoint, part["size"], disk.get("model")))
            elif filesystem(part):
                print(fields("access", part_name, block_access(part)))
                print(fields("part", part_name, part["size"], disk.get("model"),
                             part["fstype"], part.get("label"), part.get("parttypename"), name))


def block_node(number, block_path=Path("/sys/dev/block")):
    node = (block_path / number).resolve(strict=True)
    disk = node.parent if (node / "partition").is_file() else node
    return node, disk


def block_identity(path, number, block_path=Path("/sys/dev/block")):
    info = Path(path).stat()
    if not stat.S_ISBLK(info.st_mode) or f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}" != number:
        raise ValueError(f"{path}: block device identity changed / identité du périphérique modifiée")
    node, disk = block_node(number, block_path)
    if (node / "dev").read_text().strip() != number:
        raise ValueError(f"{path}: inconsistent sysfs identity / identité sysfs incohérente")
    return node, disk


def block_context(path, number, *, role, mountpoint=None, block_path=Path("/sys/dev/block")):
    node, disk = block_identity(path, number, block_path)
    sequence = (disk / "diskseq").read_text().strip()
    mode = (node / "ro").read_text().strip()
    disk_mode = (disk / "ro").read_text().strip()
    if mode not in {"0", "1"} or disk_mode not in {"0", "1"}:
        raise ValueError(f"{path}: unknown device protection / protection bloc inconnue")
    return {
        "path": str(path), "major_minor": number, "disk_sequence": sequence,
        "disk": f"/dev/{disk.name}", "capacity": int((node / "size").read_text()) * 512,
        "role": role, "mountpoint": mountpoint, "block_mode": "ro" if mode == "1" else "rw",
        "disk_mode": "ro" if disk_mode == "1" else "rw",
    }


def usb_parent(node):
    return next((parent for parent in node.parents
                 if (parent / "idVendor").is_file() and (parent / "idProduct").is_file()), None)


def inspect_usb(device):
    identity = (device.name, (device / "busnum").read_text().strip(),
                (device / "devnum").read_text().strip())
    interfaces = list(device.glob(f"{device.name}:*/bInterfaceClass"))
    if (device / "authorized").read_text().strip() != "1" or not interfaces:
        raise ValueError(f"Interfaces USB non vérifiables / USB interfaces unavailable: {device.name}")
    if any(interface.read_text().strip().lower() == "03" for interface in interfaces):
        raise ValueError(f"Interface USB HID détectée / HID interface detected: {device.name}")
    return identity


def idle(node):
    holders = Path("/sys/dev/block") / node["maj:min"] / "holders"
    return (not any(node.get("mountpoints") or ()) and not any(holders.iterdir())
            and all(idle(child) for child in node.get("children", ())))


def disk_sequence(row):
    return (Path("/sys/dev/block") / row["maj:min"] / "diskseq").read_text().strip()


def usb_identity(row):
    location, _ = block_node(row["maj:min"])
    if parent := usb_parent(location):
        return inspect_usb(parent)
    raise ValueError(f"Parent USB introuvable / USB parent not found: {row['name']}")


def check_disk(row, sequence):
    current, = devices("--", row["name"])
    if (current["type"] != "disk" or current["maj:min"] != row["maj:min"]
            or current["size"] != row["size"] or disk_sequence(current) != sequence):
        raise ValueError(f"Identité du disque modifiée / Disk identity changed: {row['name']}")
    if "usb_identity" in row and usb_identity(current) != row["usb_identity"]:
        raise ValueError(f"Identité USB modifiée / USB identity changed: {row['name']}")
    if not idle(current):
        raise ValueError(f"Disque en cours d’utilisation / Disk in use: {row['name']}")
