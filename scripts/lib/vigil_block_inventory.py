"""Shared Linux block inventory for the mount and acquisition triage."""
import json
import subprocess

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


if __name__ == "__main__":
    mount_inventory()
