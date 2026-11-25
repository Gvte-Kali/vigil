#!/usr/bin/env python3
"""Interactive, verified acquisition from an unmounted Linux block device."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

# The launcher uses isolated Python. Load the companion module from this script's directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vigil_progress import Progress, sync_notice, duration, human_size, indeterminate, tr

BLOCK_RO_SET = 0x125D
BLOCK_RO_GET = 0x125E
CHUNK_SIZE = 4 * 1024 * 1024
FILESYSTEMS = {"ext4", "exfat", "vfat", "ntfs"}
DEVICE_COLUMNS = "NAME,TYPE,SIZE,TRAN,MODEL,SERIAL,FSTYPE,MAJ:MIN,MOUNTPOINTS,RO,LABEL,PTTYPE,PARTTYPE"


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
    if row.get("tran") == "usb":
        identity = usb_identity(current)
        if identity != row["usb_identity"]:
            raise ValueError(f"Identité USB modifiée : {row['name']}")
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


def terminal_style(text, tone, *, stream=None):
    stream = stream or sys.stdout
    if not stream.isatty() or os.environ.get("TERM") == "dumb" or "NO_COLOR" in os.environ:
        return text
    return f"\033[{tone}m{text}\033[0m"


def section(title):
    rule = "━" * min(52, shutil.get_terminal_size((80, 24)).columns)
    print()
    for line in (rule, f"  {title}", rule):
        print(terminal_style(line, "96"))


def describe_device(row):
    is_disk = row["type"] == "disk"
    fields = []
    if is_disk:
        fields.extend((f"Modèle : {menu_text(row.get('model')) or tr('inconnu', 'unknown')}",
                       f"Série : {menu_text(row.get('serial')) or tr('inconnue', 'unknown')}",
                       f"Connexion : {menu_text(row.get('tran')) or tr('inconnue', 'unknown')}",
                       f"Table : {menu_text(row.get('pttype')) or tr('inconnue', 'unknown')}"))
    else:
        part_type = row.get("parttypename") or row.get("parttype")
        fields.append(f"Type : {menu_text(part_type) or tr('inconnu', 'unknown')}")
    if not is_disk or not row.get("children"):
        fields.append(f"FS : {menu_text(row.get('fstype')) or tr('inconnu', 'unknown')}")
    if label := menu_text(row.get("label")):
        fields.append(f"Volume : {label}")
    ro = row.get("ro")
    mode = "RO" if ro in (1, "1") else "RW" if ro in (0, "0") else tr("inconnu", "unknown")
    fields.append(tr("Bloc :", "Block:") + f" {mode}")
    mounts = ", ".join(menu_text(mount) for mount in (row.get("mountpoints") or ()) if mount)
    fields.append(tr("Montage :", "Mounted at:") + f" {mounts or tr('aucun', 'none')}")
    return fields


def print_device(row, indent, prefix=""):
    name = menu_text(row["name"])
    label = f"{prefix} {name}" if prefix else name
    print(f"{indent}{terminal_style(label, '1;96')}  {terminal_style(menu_size(row['size']), '1')}")
    width = max(20, shutil.get_terminal_size((80, 24)).columns - len(indent) - 2)
    line = []
    length = 0
    for field in describe_device(row):
        if line and length + len(field) + 7 > width:
            print(f"{indent}  " + "   •   ".join(line))
            line, length = [], 0
        key, _, value = field.partition(" : ")
        if len(field) > width:
            for chunk in textwrap.wrap(field, width=width, break_long_words=False, break_on_hyphens=False):
                print(f"{indent}  {chunk}")
            continue
        tone = "92" if key == "Bloc" and value == "RO" else "93" if key == "Bloc" and value == "RW" else "1"
        line.append(f"{terminal_style(key + ' :', '90')} {terminal_style(value, tone)}")
        length += len(field) + (7 if len(line) > 1 else 0)
    if line:
        print(f"{indent}  " + "   •   ".join(line))


def choose(rows, title, *, parents=None):
    if not rows:
        raise ValueError(f"Aucun périphérique admissible : {title}")
    section(title)
    print()
    previous_parent = None
    for index, row in enumerate(rows, 1):
        parent = parents.get(row["name"]) if parents else None
        if parent and parent is not previous_parent:
            if previous_parent is not None:
                print()
            print_device(parent, "  ", tr("Disque parent :", "Parent disk :"))
            previous_parent = parent
        indent = "    " if parent else "  "
        print_device(row, indent, f"[{index}]")
        if row["type"] == "disk":
            for part in row.get("children", ()):
                if part["type"] == "part":
                    print_device(part, "      ", "└─")
            print()
    if previous_parent is not None:
        print()
    while True:
        choice = input(terminal_style(tr("Numéro ou q pour annuler : ", "Number or q to cancel: "), "1;93")).strip()
        if choice.lower() == "q":
            raise InterruptedError(tr("Opération annulée.", "Operation cancelled."))
        if choice.isdecimal() and len(choice) <= 8 and 1 <= int(choice) <= len(rows):
            return rows[int(choice) - 1]
        print(terminal_style(tr("Numéro invalide.", "Invalid number."), "91"))


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
    progress = Progress(label, size)
    try:
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
                        raise OSError(tr("Écriture incomplète.", "Short write."))
                    pending = pending[written:]
            remaining -= len(payload)
            progress.update(size - remaining)
    finally:
        progress.finish()
    return digest.hexdigest()


def transfer(source, target, size, timings=None):
    timings = {} if timings is None else timings
    start = time.monotonic()
    reference = checksum(source, size, output=target, label=tr("Copie", "Copy"))
    timings["copy"] = time.monotonic() - start
    print(f"\n{sync_notice()}", flush=True)
    start = time.monotonic()
    with indeterminate(tr("Synchronisation des écritures sur la destination", "Synchronizing writes sur la destination")):
        target.flush()
        os.fsync(target.fileno())
    timings["sync"] = time.monotonic() - start
    if hasattr(os, "posix_fadvise"):
        with indeterminate("Préparation de la relecture (cache de la destination)"):
            try:
                os.posix_fadvise(target.fileno(), 0, size, os.POSIX_FADV_DONTNEED)
            except OSError:
                pass
    target.seek(0)
    print(tr("\nRelecture de la destination et calcul du SHA-256", "\nReading back the destination and calculating SHA-256"), flush=True)
    start = time.monotonic()
    actual = checksum(target, size, label=tr("Vérification SHA-256", "SHA-256 verification"))
    timings["verify"] = time.monotonic() - start
    if actual != reference:
        raise ValueError(f"Écart SHA-256 : source {reference}, relecture {actual}")
    timings["destination_hash"] = actual
    return reference


def acquisition_summary(kind, source, destination, size, digest, timings, started, *, manifest=None, unmounted=False):
    section(tr("Acquisition terminée", "Acquisition complete"))
    print(terminal_style(tr("Intégrité : vérifiée · SHA-256 identiques", "Integrity verified · SHA-256 values match"), "1;92"))
    print(f"  Type : {kind}\n  Source : {source}\n  Destination : {destination}")
    print(tr(f"  Volume : {human_size(size)} ({size} octets)", f"  Volume: {human_size(size)} ({size} bytes)"))
    print(f"  SHA-256 source : {digest}\n  SHA-256 destination : {timings['destination_hash']}")
    copy, sync, verify = (duration(timings[key]) for key in ("copy", "sync", "verify"))
    total = duration(time.monotonic() - started)
    print(tr(f"  Copie : {copy} · Synchronisation : {sync} · Vérification : {verify} · Total : {total}",
             f"  Copy: {copy} · Sync: {sync} · Verification: {verify} · Total: {total}"))
    if timings["copy"] >= 3:
        print(tr("  Débit moyen de copie :", "  Average copy rate:") + f" {human_size(size / timings['copy'])}/s")
    if manifest:
        print(tr("  Manifeste :", "  Manifest:") + f" {manifest}")
    if unmounted:
        print(tr("  Destination USB démontée.", "  USB destination unmounted."))
    print(tr("  Code de sortie : 0", "  Exit code: 0"))


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
            raise ValueError(tr("Montage de destination non confirmé en lecture-écriture.", "Could not confirm a read/write destination mount."))
        yield Path(directory)
    finally:
        if mounted:
            with indeterminate("Démontage de la destination USB"):
                command("/usr/bin/umount", "--", directory)
        # Never recursively remove a mountpoint, even when unmounting fails.
        os.rmdir(directory)


def create_image(source, size, directory, filename, owner=None, timings=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,170}\.raw", filename):
        raise ValueError(tr("Nom attendu : nom-image.raw (lettres, chiffres, points, tirets).", "Expected image-name.raw (letters, digits, dots and hyphens)."))
    folder = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created = []
    try:
        filesystem = os.fstatvfs(folder)
        if filesystem.f_bavail * filesystem.f_frsize < size:
            raise ValueError(tr("Espace disponible insuffisant pour l’image.", "Insufficient free space for the image."))
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
            digest = transfer(source, target, size, timings)
            if owner is not None:
                os.fchown(target.fileno(), *owner)
        fd = os.open(sums, flags, 0o600, dir_fd=folder)
        created.append((sums, os.fstat(fd)))
        with indeterminate("Synchronisation du manifeste SHA-256"):
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


def usb_identity(row):
    """Reject missing, unauthorized or composite HID USB mass-storage devices."""
    location = (Path("/sys/dev/block") / row["maj:min"]).resolve(strict=True)
    for parent in location.parents:
        if (parent / "idVendor").is_file() and (parent / "idProduct").is_file():
            return inspect_usb(parent)
    raise ValueError(f"Parent USB introuvable : {row['name']}")


def inspect_usb(device):
    identity = (device.name, (device / "busnum").read_text().strip(),
                (device / "devnum").read_text().strip())
    interfaces = list(device.glob(f"{device.name}:*/bInterfaceClass"))
    if (device / "authorized").read_text().strip() != "1" or not interfaces:
        raise ValueError(f"Interfaces USB non vérifiables sur le port {device.name}.")
    if any(interface.read_text().strip().lower() == "03" for interface in interfaces):
        raise ValueError(f"Interface USB HID détectée sur le port {device.name}. Débranchez ce support.")
    return identity


def usb_snapshot():
    snapshot = {}
    for device in Path("/sys/bus/usb/devices").iterdir():
        if not (device / "idVendor").is_file():
            continue
        identity = (device.name, (device / "busnum").read_text().strip(),
                    (device / "devnum").read_text().strip())
        snapshot[identity] = device
    return snapshot


def triage_usb(role, *, allow_internal=False):
    section(f"Triage USB HID · {role}")
    print(tr("Débranchez le support USB qui sera utilisé. Laissez les autres périphériques en place.", "Disconnect the USB drive you will use. Leave other devices connected."))
    options = tr(" · i : source interne", " · i : internal source") if allow_internal else ""
    answer = input(f"Entrée : relever l’état initial · q : annuler{options} : ").strip().lower()
    if answer == "i" and allow_internal:
        return set()
    if answer == "q":
        raise InterruptedError(tr("Acquisition annulée.", "Acquisition cancelled."))
    before = usb_snapshot()
    if input(tr("Branchez le support USB, puis Entrée · q : annuler : ", "Connect the USB drive, then press Enter · q: cancel : ")).strip().lower() == "q":
        raise InterruptedError(tr("Acquisition annulée.", "Acquisition cancelled."))
    command("/usr/bin/udevadm", "settle", "--timeout=10")
    after = usb_snapshot()
    new = after.keys() - before.keys()
    if not new:
        raise ValueError(tr("Aucun nouveau support USB détecté. Relancez et suivez les étapes de branchement.", "No new USB drive detected. Restart and follow the connection prompts."))
    for identity in sorted(new):
        if inspect_usb(after[identity]) != identity:
            raise ValueError(tr("L’identité USB a changé pendant le triage.", "The USB identity changed during triage."))
    print(terminal_style(f"Triage terminé : {len(new)} nouveau(x) périphérique(s), aucune interface HID détectée.", "92"))
    return new


def triaged_disk(row, approved):
    try:
        identity = usb_identity(row)
        if identity in approved:
            row["usb_identity"] = identity
            return True
        return False
    except (OSError, ValueError):
        return False


def target_disks(source, sequence):
    approved = triage_usb("destination")
    check_disk(source, sequence)
    return [row for row in devices() if row["type"] == "disk" and row["tran"] == "usb"
            and row["maj:min"] != source["maj:min"] and triaged_disk(row, approved) and idle(row)]


@contextmanager
def writable_target(disk, sequence, partition=None):
    """Permit writes only to the confirmed destination, and restore its block modes."""
    check_disk(disk, sequence)
    with ExitStack() as stack:
        descriptors = []
        for row in (disk, partition) if partition else (disk,):
            fd = os.open(row["name"], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            stack.callback(os.close, fd)
            validate_fd(fd, row)
            descriptors.append((fd, block_mode(fd)))
        check_disk(disk, sequence)
        try:
            for fd, _ in descriptors:
                if block_mode(fd):
                    fcntl.ioctl(fd, BLOCK_RO_SET, struct.pack("i", 0))
                if block_mode(fd):
                    raise ValueError(tr("Impossible de rendre la destination confirmée inscriptible.", "Could not make the confirmed destination writable."))
            yield
        finally:
            errors = []
            for fd, original in reversed(descriptors):
                # Use the open descriptor so unplugging cannot restore a replacement device.
                try:
                    if block_mode(fd) != original:
                        fcntl.ioctl(fd, BLOCK_RO_SET, struct.pack("i", original))
                    if block_mode(fd) != original:
                        raise ValueError(tr("mode bloc non restauré", "block mode not restored"))
                except (OSError, ValueError) as error:
                    errors.append(str(error))
            if errors:
                raise ValueError(f"Restauration de {disk['name']} : " + "; ".join(errors))


def run(operation, local_default, *, local_directory=None, external=False):
    approved = triage_usb("source", allow_internal=True)
    disks = [row for row in devices() if row["type"] == "disk" and row["size"] > 0
             and (triaged_disk(row, approved) if approved else row["tran"] not in {"usb", None})
             and idle(row)]
    source = choose(disks, tr("Disque source entier, démonté", "Whole unmounted source disk"))
    sequence = disk_sequence(source)
    size = source["size"]
    if operation == "clone":
        targets = target_disks(source, sequence)
        target = choose([row for row in targets if row["size"] >= size], tr("Cible USB à écraser", "USB target to overwrite"))
        target_sequence = disk_sequence(target)
        section(tr("Confirmation du clonage", "Confirm cloning"))
        print(f"\n  Source : {menu_text(source['name'])} · {menu_size(size)}")
        print(tr("  Cible  :", "  Target:") + f" {menu_text(target['name'])} · {menu_size(target['size'])}\n")
        print(terminal_style(tr("Les données de la cible seront écrasées sur la longueur de la source.", "Target data will be overwritten up to the size of the source."), "1;91"))
        confirmation = f"ECRASER {target['name']}"
        if input(terminal_style(tr(f"\nSaisissez {confirmation} : ", f"\nType {confirmation}: "), "1;93")).strip() != confirmation:
            raise InterruptedError(tr("Clonage annulé.", "Cloning cancelled."))
        timings, started = {}, time.monotonic()
        with block_device(source, sequence, source=True) as origin:
            with writable_target(target, target_sequence):
                with block_device(target, target_sequence, source=False) as output:
                    digest = transfer(origin, output, size, timings)
        acquisition_summary(tr("Clonage bloc", "Block clone"), source["name"], target["name"], size, digest, timings, started)
        return

    if local_directory is not None:
        mode = "1"
    elif external:
        mode = "2"
    else:
        section(tr("Destination de l’image", "Image destination"))
        print(tr("  [1] Dossier local\n  [2] Partition USB externe\n  [q] Annuler\n", "  [1] Local folder\n  [2] External USB partition\n  [q] Cancel\n"))
        mode = input(terminal_style(tr("Choix : ", "Choice: "), "1;93")).strip()
    if mode not in {"1", "2"}:
        raise InterruptedError(tr("Imagerie annulée.", "Imaging cancelled."))
    owner = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
    if mode == "1":
        local = Path(local_directory if local_directory is not None else
                     input(tr(f"Dossier local existant [{local_default}] : ", f"Existing local folder [{local_default}]: ")).strip() or local_default)
        local = local.resolve(strict=True)
        if not local.is_dir() or local.stat().st_uid != owner[0] or local.is_relative_to("/investigation"):
            raise ValueError(tr("Choisissez un dossier local existant qui vous appartient, hors de /investigation.", "Choose an existing local folder you own, outside /investigation."))
    else:
        targets = target_disks(source, sequence)
        partitions = [(disk, part) for disk in targets for part in disk.get("children", ())
                      if part["type"] == "part" and part["fstype"] in FILESYSTEMS]
        if not partitions:
            formats = ", ".join(sorted(FILESYSTEMS))
            raise ValueError(tr(
                f"Aucune partition USB de destination disponible en dehors du disque source {source['name']}.\n"
                f"    Branchez un second support USB démonté avec une partition compatible ({formats}), "
                "ou relancez l’action en choisissant « Dossier local ».",
                f"No eligible USB destination partition separate from the source disk {source['name']}.\n"
                f"    Connect a second unmounted USB drive with a supported partition ({formats}), "
                "or restart and choose Local folder.",
            ))
        parents = {part["name"]: disk for disk, part in partitions}
        selected = choose([part for _, part in partitions], tr("Partition USB de destination", "USB destination partition"), parents=parents)
        target = parents[selected["name"]]
        target_sequence = disk_sequence(target)
        if selected["fstype"] == "vfat" and size >= 2**32:
            raise ValueError(tr("Cette image dépasse la taille maximale d’un fichier FAT32.", "This image exceeds the FAT32 file size limit."))
    section(tr("Confirmation de l’imagerie", "Confirm imaging"))
    print(f"\n  Source : {menu_text(source['name'])} · {menu_size(size)}")
    destination = local if mode == "1" else selected["name"]
    print(f"  Destination : {menu_text(destination)}\n")
    filename = input(terminal_style(tr("Nom de l’image [acquisition.raw] : ", "Image filename [acquisition.raw] : "), "1;93")).strip() or "acquisition.raw"
    if input(terminal_style(tr("Saisissez COPIER pour lancer l’acquisition : ", "Type COPIER to start acquisition : "), "1;93")).strip() != "COPIER":
        raise InterruptedError(tr("Imagerie annulée.", "Imaging cancelled."))
    timings, started = {}, time.monotonic()
    with block_device(source, sequence, source=True) as origin:
        if mode == "1":
            digest = create_image(origin, size, local, filename, owner, timings)
        else:
            with writable_target(target, target_sequence, selected):
                with external_directory(target, target_sequence, selected, owner) as directory:
                    digest = create_image(origin, size, directory, filename,
                                          owner if selected["fstype"] == "ext4" else None, timings)
            print(terminal_style(f"Destination démontée : {selected['name']}", "92"))
    image_path = str(local / filename) if mode == "1" else f"{selected['name']} : /{filename}"
    acquisition_summary("Image RAW", source["name"], image_path, size, digest, timings, started,
                        manifest=image_path + ".sha256", unmounted=mode == "2")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("clone", "image"))
    parser.add_argument("--local-default", required=True)
    parser.add_argument("--language", choices=("fr", "en"))
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--local-directory")
    destination.add_argument("--external", action="store_true")
    args = parser.parse_args()
    if args.language:
        os.environ["VIGIL_LANG"] = args.language
    if args.operation == "clone" and (args.local_directory is not None or args.external):
        parser.error(tr("Options de destination réservées à l’imagerie RAW.", "Destination options are only available for RAW imaging."))
    if os.geteuid() != 0 or "SUDO_UID" not in os.environ:
        parser.error(tr("Lancez cette action avec sudo dans un espace de montage privé.", "Run this action with sudo in a private mount namespace."))
    if os.readlink("/proc/self/ns/mnt") == os.readlink("/proc/1/ns/mnt"):
        parser.error(tr("Espace de montage privé requis.", "A private mount namespace is required."))

    def interrupt(*_):
        raise InterruptedError(tr("Acquisition interrompue.", "Acquisition interrupted."))

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    print(flush=True)
    terminal_library = Path(__file__).resolve().parents[1] / "lib/vigil-terminal.sh"
    logo = terminal_library.parents[2] / "data/icons/vigil.svg"
    subprocess.run(("/bin/sh", "-c", '. "$1"; vigil_logo "$2"', "vigil",
                    str(terminal_library), str(logo)), check=False)
    section(tr("Vigil - Clonage bit à bit", "Vigil - Bit-for-bit cloning") if args.operation == "clone" else tr("Vigil - Acquisition d’une image RAW", "Vigil - RAW image acquisition"))
    try:
        run(args.operation, args.local_default, local_directory=args.local_directory, external=args.external)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as error:
        diagnostic = getattr(error, "stderr", None) or str(error)
        print(terminal_style(f"\nAcquisition non validée : {diagnostic}", "91", stream=sys.stderr), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
