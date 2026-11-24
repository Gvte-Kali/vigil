#!/usr/bin/env python3
"""Interactive, verified acquisition from an unmounted Linux block device."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

BLOCK_RO_SET = 0x125D
BLOCK_RO_GET = 0x125E
CHUNK_SIZE = 4 * 1024 * 1024
FILESYSTEMS = {"ext4", "exfat", "vfat", "ntfs"}
DEVICE_COLUMNS = "NAME,TYPE,SIZE,TRAN,MODEL,SERIAL,FSTYPE,MAJ:MIN,MOUNTPOINTS,RO,LABEL,PTTYPE,PARTTYPE"
VIGIL_BANNER = """█   █ ███  ███  ███ █
█   █  █  █      █  █
█   █  █  █  ██  █  █
 █ █   █  █   █  █  █
  █   ███  ███  ███ █████"""


def command(program, *args):
    return subprocess.run((program, *args), capture_output=True, text=True, check=True).stdout


def devices(*args):
    options = ("/usr/bin/lsblk", "--json", "--bytes", "--paths", "--output")
    try:
        output = command(*options, DEVICE_COLUMNS + ",PARTTYPENAME", *args)
    except subprocess.CalledProcessError as error:
        # Older util-linux releases can expose the raw partition type only.
        if "PARTTYPENAME" not in (error.stderr or ""):
            raise
        output = command(*options, DEVICE_COLUMNS, *args)
    return json.loads(output)["blockdevices"]


def disk_sequence(row):
    return (Path("/sys/dev/block") / row["maj:min"] / "diskseq").read_text().strip()


def idle(node):
    holders = Path("/sys/dev/block") / node["maj:min"] / "holders"
    return (not any(node.get("mountpoints") or ()) and not any(holders.iterdir())
            and all(idle(child) for child in node.get("children", ())))


def check_disk(row, sequence):
    current, = devices("--", row["name"])
    if (current["type"] != "disk" or current["maj:min"] != row["maj:min"]
            or current["size"] != row["size"] or disk_sequence(current) != sequence):
        raise ValueError(f"Identité du disque modifiée : {row['name']}")
    if not idle(current):
        raise ValueError(f"Disque ou partition en cours d’utilisation : {row['name']}")


def menu_text(value):
    return "".join(character if character.isprintable() else " " for character in str(value or "")).strip()


def menu_size(size):
    size = int(size)
    scale = float(size)
    for unit in ("o", "Kio", "Mio", "Gio", "Tio", "Pio"):
        if scale < 1024 or unit == "Pio":
            return f"{scale:.1f} {unit} ({size} octets)"
        scale /= 1024


def describe_device(row):
    is_disk = row["type"] == "disk"
    fields = [f"Taille : {menu_size(row['size'])}"]
    if is_disk:
        fields.extend((f"Modèle : {menu_text(row.get('model')) or 'inconnu'}",
                       f"Série : {menu_text(row.get('serial')) or 'inconnue'}",
                       f"Connexion : {menu_text(row.get('tran')) or 'inconnue'}",
                       f"Table : {menu_text(row.get('pttype')) or 'inconnue'}"))
    else:
        part_type = row.get("parttypename") or row.get("parttype")
        fields.append(f"Type : {menu_text(part_type) or 'inconnu'}")
    if not is_disk or not row.get("children"):
        fields.append(f"FS : {menu_text(row.get('fstype')) or 'inconnu'}")
    if label := menu_text(row.get("label")):
        fields.append(f"Volume : {label}")
    ro = row.get("ro")
    mode = "RO" if ro in (1, "1") else "RW" if ro in (0, "0") else "inconnu"
    fields.append(f"Bloc : {mode}")
    mounts = ", ".join(menu_text(mount) for mount in (row.get("mountpoints") or ()) if mount)
    fields.append(f"Montage : {mounts or 'aucun'}")
    return f"{menu_text(row['name'])} · " + " · ".join(fields)


def choose(rows, title, *, parents=None):
    if not rows:
        raise ValueError(f"Aucun périphérique admissible : {title}")
    print(f"\n=== {title} ===")
    previous_parent = None
    for index, row in enumerate(rows, 1):
        parent = parents.get(row["name"]) if parents else None
        if parent and parent is not previous_parent:
            print(f"  Disque parent : {describe_device(parent)}")
            previous_parent = parent
        indent = "    " if parent else "  "
        print(f"{indent}[{index}] {describe_device(row)}")
        if row["type"] == "disk":
            for part in row.get("children", ()):
                if part["type"] == "part":
                    print(f"      └─ {describe_device(part)}")
    while True:
        choice = input("Numéro ou q pour annuler : ").strip()
        if choice.lower() == "q":
            raise InterruptedError("Opération annulée.")
        if choice.isdecimal() and len(choice) <= 8 and 1 <= int(choice) <= len(rows):
            return rows[int(choice) - 1]


def block_mode(fd):
    return struct.unpack("i", fcntl.ioctl(fd, BLOCK_RO_GET, bytes(4)))[0]


def validate_fd(fd, row):
    info = os.fstat(fd)
    if not stat.S_ISBLK(info.st_mode) or f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}" != row["maj:min"]:
        raise ValueError(f"Identité du périphérique non confirmée : {row['name']}")


@contextmanager
def block_device(row, sequence, *, source):
    check_disk(row, sequence)
    flags = os.O_RDONLY if source else os.O_RDWR
    fd = os.open(row["name"], flags | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb" if source else "r+b", buffering=0) as stream:
        validate_fd(fd, row)
        check_disk(row, sequence)
        original = block_mode(fd)
        changed = source and original == 0
        if changed:
            fcntl.ioctl(fd, BLOCK_RO_SET, struct.pack("i", 1))
        try:
            if block_mode(fd) != int(source):
                raise ValueError(f"Mode bloc incorrect : {row['name']}")
            yield stream
            if source and block_mode(fd) != 1:
                raise ValueError(f"Protection en écriture perdue : {row['name']}")
        finally:
            if changed:
                fcntl.ioctl(fd, BLOCK_RO_SET, struct.pack("i", original))
                if block_mode(fd) != original:
                    raise ValueError(f"Restauration du mode bloc impossible : {row['name']}")


def checksum(stream, size, *, output=None, label):
    digest = hashlib.sha256()
    remaining = size
    last = time.monotonic()
    while remaining:
        payload = stream.read(min(remaining, CHUNK_SIZE))
        if not payload:
            raise OSError(f"Lecture incomplète : {remaining} octets manquants.")
        digest.update(payload)
        if output is not None:
            pending = memoryview(payload)
            while pending:
                written = output.write(pending)
                if not written:
                    raise OSError("Écriture incomplète.")
                pending = pending[written:]
        remaining -= len(payload)
        if time.monotonic() - last >= 2 or not remaining:
            print(f"{label} : {size - remaining}/{size} octets", flush=True)
            last = time.monotonic()
    return digest.hexdigest()


def transfer(source, target, size):
    reference = checksum(source, size, output=target, label="Copie")
    target.flush()
    os.fsync(target.fileno())
    if hasattr(os, "posix_fadvise"):
        try:
            os.posix_fadvise(target.fileno(), 0, size, os.POSIX_FADV_DONTNEED)
        except OSError:
            pass
    target.seek(0)
    actual = checksum(target, size, label="Vérification SHA-256")
    if actual != reference:
        raise ValueError(f"Écart SHA-256 : source {reference}, relecture {actual}")
    return reference


@contextmanager
def external_directory(disk, sequence, partition, owner):
    check_disk(disk, sequence)
    fd = os.open(partition["name"], os.O_RDONLY | os.O_EXCL | os.O_NOFOLLOW)
    try:
        validate_fd(fd, partition)
        if block_mode(fd):
            raise ValueError(f"Destination externe protégée en écriture : {partition['name']}")
    finally:
        os.close(fd)
    check_disk(disk, sequence)
    directory = tempfile.mkdtemp(prefix="vigil-acquisition-", dir="/run")
    mounted = False
    try:
        options = "rw,nodev,nosuid,noexec"
        if partition["fstype"] != "ext4":
            options += f",uid={owner[0]},gid={owner[1]},umask=077"
        command("/usr/bin/mount", "-t", partition["fstype"], "-o", options,
                "--", partition["name"], directory)
        mounted = True
        source = command("/usr/bin/findmnt", "--mountpoint", directory, "-n", "-o", "SOURCE").strip()
        info = Path(source).stat()
        if (disk_sequence(disk) != sequence or not stat.S_ISBLK(info.st_mode)
                or f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}" != partition["maj:min"]
                or os.statvfs(directory).f_flag & os.ST_RDONLY):
            raise ValueError("Montage de destination non confirmé en lecture-écriture.")
        yield Path(directory)
    finally:
        if mounted:
            command("/usr/bin/umount", "--", directory)
        # Never recursively remove a mountpoint, even when unmounting fails.
        os.rmdir(directory)


def create_image(source, size, directory, filename, owner=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,170}\.raw", filename):
        raise ValueError("Nom attendu : nom-image.raw (lettres, chiffres, points, tirets).")
    folder = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created = []
    try:
        filesystem = os.fstatvfs(folder)
        if filesystem.f_bavail * filesystem.f_frsize < size:
            raise ValueError("Espace disponible insuffisant pour l’image.")
        sums = filename + ".sha256"
        for name in (filename, sums):
            try:
                os.stat(name, dir_fd=folder, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FileExistsError(f"Ce fichier existe déjà : {name}")

        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        fd = os.open(filename, flags, 0o600, dir_fd=folder)
        created.append((filename, os.fstat(fd)))
        with os.fdopen(fd, "w+b", buffering=0) as target:
            digest = transfer(source, target, size)
            if owner is not None:
                os.fchown(target.fileno(), *owner)
        fd = os.open(sums, flags, 0o600, dir_fd=folder)
        created.append((sums, os.fstat(fd)))
        with os.fdopen(fd, "w", encoding="ascii") as manifest:
            manifest.write(f"{digest}  {filename}\n")
            manifest.flush()
            if owner is not None:
                os.fchown(manifest.fileno(), *owner)
            os.fsync(manifest.fileno())
        os.fsync(folder)
        return digest
    except BaseException:
        for name, original in reversed(created):
            try:
                current = os.stat(name, dir_fd=folder, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino):
                    os.unlink(name, dir_fd=folder)
            except FileNotFoundError:
                pass
        raise
    finally:
        os.close(folder)


def run(operation, local_default, *, local_directory=None, external=False):
    disks = [row for row in devices() if row["type"] == "disk" and row["size"] > 0 and idle(row)]
    source = choose(disks, "Disque source entier, démonté")
    sequence = disk_sequence(source)
    targets = [row for row in disks if row["maj:min"] != source["maj:min"] and row["tran"] == "usb"]
    size = source["size"]
    if operation == "clone":
        target = choose([row for row in targets if row["size"] >= size], "Cible USB à écraser")
        target_sequence = disk_sequence(target)
        print(f"Source : {source['name']} · {size} octets → Cible : {target['name']} · {target['size']} octets")
        print("Les données de la cible seront écrasées sur la longueur de la source.")
        if input(f"Saisissez ECRASER {target['name']} : ").strip() != f"ECRASER {target['name']}":
            raise InterruptedError("Clonage annulé.")
        with block_device(source, sequence, source=True) as origin:
            with block_device(target, target_sequence, source=False) as output:
                digest = transfer(origin, output, size)
        print(f"Clone vérifié · SHA-256 : {digest}")
        return

    if local_directory is not None:
        mode = "1"
    elif external:
        mode = "2"
    else:
        mode = input("Destination : [1] locale, [2] partition USB externe, [q] annuler : ").strip()
    if mode not in {"1", "2"}:
        raise InterruptedError("Imagerie annulée.")
    owner = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
    if mode == "1":
        local = Path(local_directory if local_directory is not None else
                     input(f"Dossier local existant [{local_default}] : ").strip() or local_default)
        local = local.resolve(strict=True)
        if not local.is_dir() or local.stat().st_uid != owner[0] or local.is_relative_to("/investigation"):
            raise ValueError("Choisissez un dossier local existant qui vous appartient, hors de /investigation.")
    else:
        partitions = [(disk, part) for disk in targets for part in disk.get("children", ())
                      if part["type"] == "part" and part["fstype"] in FILESYSTEMS]
        parents = {part["name"]: disk for disk, part in partitions}
        selected = choose([part for _, part in partitions], "Partition USB de destination", parents=parents)
        target = parents[selected["name"]]
        target_sequence = disk_sequence(target)
        if selected["fstype"] == "vfat" and size >= 2**32:
            raise ValueError("Cette image dépasse la taille maximale d’un fichier FAT32.")
    filename = input("Nom de l’image [acquisition.raw] : ").strip() or "acquisition.raw"
    if input("Saisissez COPIER pour lancer l’acquisition : ").strip() != "COPIER":
        raise InterruptedError("Imagerie annulée.")
    with block_device(source, sequence, source=True) as origin:
        if mode == "1":
            digest = create_image(origin, size, local, filename, owner)
        else:
            with external_directory(target, target_sequence, selected, owner) as directory:
                digest = create_image(origin, size, directory, filename,
                                      owner if selected["fstype"] == "ext4" else None)
            print(f"Destination démontée : {selected['name']}")
    print(f"Image vérifiée : {filename} · SHA-256 : {digest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("clone", "image"))
    parser.add_argument("--local-default", required=True)
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--local-directory")
    destination.add_argument("--external", action="store_true")
    args = parser.parse_args()
    if args.operation == "clone" and (args.local_directory is not None or args.external):
        parser.error("Options de destination réservées à l’imagerie RAW.")
    if os.geteuid() != 0 or "SUDO_UID" not in os.environ:
        parser.error("Lancez cette action avec sudo dans un espace de montage privé.")
    if os.readlink("/proc/self/ns/mnt") == os.readlink("/proc/1/ns/mnt"):
        parser.error("Espace de montage privé requis.")

    def interrupt(*_):
        raise InterruptedError("Acquisition interrompue.")

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    print(VIGIL_BANNER)
    print("Vigil - Clonage bit à bit" if args.operation == "clone" else "Vigil - Acquisition d’une image RAW")
    try:
        run(args.operation, args.local_default, local_directory=args.local_directory, external=args.external)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as error:
        diagnostic = getattr(error, "stderr", None) or str(error)
        print(f"Acquisition non validée : {diagnostic}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
