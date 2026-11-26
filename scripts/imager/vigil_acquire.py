#!/usr/bin/env python3
"""Interactive, verified acquisition from an unmounted Linux block device."""
import argparse
import fcntl
import hashlib
import os
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

# The launcher uses isolated Python. Load the companion module from this script's directory.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR), str(SCRIPT_DIR.parents[1])]
from vigil.block_inventory import (
    block_context,
    block_access, check_disk, command, devices, disk_sequence, external_storage,
    fields, filesystem, idle, inspect_usb, usb_identity,
)
from vigil.device_manager import device_lease
from vigil.destination import writable_destination
from vigil_progress import Progress, sync_notice, duration, human_size, indeterminate, tr

BLOCK_RO_SET = 0x125D
BLOCK_RO_GET = 0x125E
CHUNK_SIZE = 4 * 1024 * 1024
FILESYSTEMS = {"ext4", "exfat", "vfat", "ntfs"}
TRIAGE = SCRIPT_DIR / "vigil_acquire_triage.sh"


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


def triage_command(action, directory, *arguments):
    sys.stdout.flush()
    return subprocess.run(("/usr/bin/bash", str(TRIAGE), action, str(directory), *arguments),
                          stdout=subprocess.PIPE, text=True, check=False)


def choose(inventory, title, prompt, directory):
    while True:
        options = inventory()
        records = []
        for disk, part, _ in options:
            row = part or disk
            kind = "part" if part else "disk" if disk.get("children") else "rawdisk"
            records.append(fields(
                kind, Path(row["name"]).name, menu_size(row["size"]),
                disk.get("model"), row.get("fstype"), row.get("label"), row.get("parttypename"),
                Path(disk["name"]).name if part else "", block_access(row),
                menu_size(disk["size"]), disk.get("model"),
            ))
        result = triage_command("select", directory, title, prompt, *records)
        if result.returncode == 2:
            continue
        if result.returncode == 1:
            raise InterruptedError(tr("Opération annulée.", "Operation cancelled."))
        result.check_returncode()
        return options[int(result.stdout)]


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
        context = block_context(row["name"], row["maj:min"], role="source" if source else "destination")
        if context["disk_sequence"] != sequence or context["capacity"] != row["size"]:
            raise ValueError(f"Contexte du disque modifié / Disk context changed: {row['name']}")
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
        destination = writable_destination(directory, fd=folder)
        if destination.available < size:
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


def triage_usb(role, directory, data_directory, *, allow_internal=False):
    result = triage_command("triage", directory, str(data_directory), role,
                            "internal" if allow_internal else "")
    if allow_internal and result.returncode == 3:
        return None
    if result.returncode == 1:
        raise InterruptedError(tr("Acquisition annulée.", "Acquisition cancelled."))
    result.check_returncode()
    approved = set()
    for line in result.stdout.splitlines():
        port, busdev = line.split("|")
        bus, dev = busdev.split(":")
        approved.add((port, bus, dev))
    return approved


def triaged_disk(row, approved):
    try:
        identity = usb_identity(row)
        if identity in approved:
            row["usb_identity"] = identity
            return True
        return False
    except (OSError, ValueError):
        return False


def disk_options(approved, *, source=None, sequence=None, image=False):
    if source is not None:
        check_disk(source, sequence)
    for disk in devices():
        if disk["type"] != "disk" or not disk["size"]:
            continue
        if source is not None and (disk["maj:min"] == source["maj:min"]
                                   or disk["name"] == source["name"] or disk["size"] < source["size"]):
            continue
        try:
            if not idle(disk):
                continue
            if approved is None:
                if external_storage(disk) or not disk.get("tran"):
                    continue
            elif not external_storage(disk) or not triaged_disk(disk, approved):
                continue
            current_sequence = disk_sequence(disk)
        except OSError:
            continue
        if not image:
            yield disk, None, current_sequence
            continue
        for part in disk.get("children", ()):
            if (part["type"] == "part" and part["size"] >= source["size"]
                    and filesystem(part) in FILESYSTEMS
                    and (part["fstype"] != "vfat" or source["size"] < 2**32)):
                yield disk, part, current_sequence


def choose_target(source, sequence, directory, data_directory, *, image=False):
    approved = triage_usb(tr("Destination", "Destination"), directory, data_directory)
    title = (tr("Partition USB de destination", "USB destination partition") if image
             else tr("Disque USB de destination à écraser", "USB destination disk to overwrite"))
    return choose(lambda: list(disk_options(approved, source=source, sequence=sequence, image=image)),
                  title, "de destination", directory)


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


def run(operation, local_default, *, local_directory=None, external=False, data_directory=None, filename=None):
    data_directory = data_directory or SCRIPT_DIR.parents[1] / "data"
    with tempfile.TemporaryDirectory(prefix="vigil-source-") as directory:
        approved = triage_usb(tr("Source", "Source"), directory, data_directory, allow_internal=True)
        source, _, sequence = choose(lambda: list(disk_options(approved)),
                                     tr("Disque source entier, démonté", "Whole unmounted source disk"),
                                     "source", directory)
    check_disk(source, sequence)
    size = source["size"]
    if operation == "clone":
        with tempfile.TemporaryDirectory(prefix="vigil-destination-") as directory:
            target, _, target_sequence = choose_target(source, sequence, directory, data_directory)
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
        local = writable_destination(local).path
        if not local.is_dir() or local.stat().st_uid != owner[0] or local.is_relative_to("/investigation"):
            raise ValueError(tr("Choisissez un dossier local existant qui vous appartient, hors de /investigation.", "Choose an existing local folder you own, outside /investigation."))
    else:
        with tempfile.TemporaryDirectory(prefix="vigil-destination-") as directory:
            target, selected, target_sequence = choose_target(source, sequence, directory, data_directory, image=True)
    section(tr("Confirmation de l’imagerie", "Confirm imaging"))
    print(f"\n  Source : {menu_text(source['name'])} · {menu_size(size)}")
    destination = local if mode == "1" else selected["name"]
    print(f"  Destination : {menu_text(destination)}\n")
    filename = filename or input(terminal_style(tr("Nom de l’image [acquisition.raw] : ", "Image filename [acquisition.raw] : "), "1;93")).strip() or "acquisition.raw"
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
    parser.add_argument("--data-directory", type=Path)
    parser.add_argument("--language", choices=("fr", "en"))
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--local-directory")
    destination.add_argument("--external", action="store_true")
    parser.add_argument("--filename", help=argparse.SUPPRESS)
    parser.add_argument("--interface", choices=("gui", "tui"))
    parser.add_argument("--embedded-terminal", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.language:
        os.environ["VIGIL_LANG"] = args.language
    if args.filename and args.local_directory is None:
        parser.error("--filename requires --local-directory")
    if args.operation == "clone" and (args.local_directory is not None or args.external):
        parser.error(tr("Options de destination réservées à l’imagerie RAW.", "Destination options are only available for RAW imaging."))
    if os.geteuid() != 0 or "SUDO_UID" not in os.environ:
        parser.error(tr("Lancez cette action avec sudo dans un espace de montage privé.", "Run this action with sudo in a private mount namespace."))
    if os.readlink("/proc/self/ns/mnt") == os.readlink("/proc/1/ns/mnt"):
        parser.error(tr("Espace de montage privé requis.", "A private mount namespace is required."))

    if args.interface == "tui" or (args.interface is None and args.embedded_terminal):
        os.environ["VIGIL_EMBEDDED_TERMINAL"] = "1"
    elif args.interface == "gui":
        os.environ.pop("VIGIL_EMBEDDED_TERMINAL", None)

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
        with device_lease():
            run(args.operation, args.local_default, local_directory=args.local_directory, external=args.external,
                data_directory=args.data_directory, filename=args.filename)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as error:
        diagnostic = getattr(error, "stderr", None) or str(error)
        print(terminal_style(f"\nAcquisition non validée : {diagnostic}", "91", stream=sys.stderr), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
