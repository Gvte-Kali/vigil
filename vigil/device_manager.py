"""Coordinate the Vigil mount zones, device selection and supervised device jobs."""
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import syslog
from contextlib import contextmanager
from pathlib import Path

from .block_inventory import block_context, devices, external_storage, idle, inspect_usb, usb_parent
from .entity import data_directory, legacy_base
from .storage import default_database
from .system_info import ZONES, mounted_resources

# Use the existing root-owned lock directory inode so an editable install can
# coordinate old and new entry points without creating a replaceable lock file.
LOCK = Path("/run/lock")
LEASE_ENV = "VIGIL_DEVICE_LEASE"
DEVICE = re.compile(r"/dev/[A-Za-z0-9][A-Za-z0-9_.-]*")


class DeviceBusy(ValueError):
    pass


@contextmanager
def device_lease(*, shared=False):
    fd = os.open(LOCK, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if os.fstat(fd).st_uid != Path("/").stat().st_uid:
            raise ValueError("Untrusted device lock / verrou de périphériques non fiable")
        try:
            fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DeviceBusy("Une opération utilise les périphériques Vigil / A Vigil device operation is active") from error
        yield fd
    finally:
        os.close(fd)


def verify_resource(record, *, block_path=Path("/sys/dev/block")):
    expected = "ro" if record["zone"] == "/investigation" else "rw"
    opposite = "rw" if expected == "ro" else "ro"
    role = "source" if expected == "ro" else "destination"
    result = dict(record, role=role, mount_mode=expected, verified=False)
    if expected not in record["mode"] or opposite in record["mode"]:
        return dict(result, error="Unexpected mount protection / protection de montage inattendue")
    try:
        number = record["major_minor"]
        if record.get("filesystem") == "fuseblk" and number.startswith("0:"):
            info = Path(record["path"]).stat()
            if stat.S_ISBLK(info.st_mode):
                number = f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}"
        context = block_context(record["path"], number, role=role,
                                mountpoint=record["mountpoint"], block_path=block_path)
    except (OSError, ValueError) as error:
        return dict(result, error=str(error))
    result.update(context)
    if context["block_mode"] != expected or context["disk_mode"] != expected:
        return dict(result, error="Unexpected block protection / protection bloc inattendue")
    return dict(result, verified=True)


def status():
    records = mounted_resources()
    counts = {}
    for record in records:
        path = record["mountpoint"]
        counts[path] = counts.get(path, 0) + 1
    return [
        verify_resource(record) if counts[record["mountpoint"]] == 1
        else dict(record, verified=False, error="Ambiguous mount / montage ambigu")
        for record in records
    ]


def normalized_zone(zone):
    path = "/" + zone
    if path not in ZONES:
        raise ValueError("Unknown zone / zone inconnue")
    return path


def validate_selection(path, zone, blacklist):
    if not DEVICE.fullmatch(path):
        raise ValueError("Expected a canonical /dev path / chemin /dev canonique attendu")
    for disk in devices():
        if disk["type"] != "disk":
            continue
        children = disk.get("children", ())
        for row in (disk, *children):
            if row["name"] != path:
                continue
            if row["type"] not in {"disk", "part"} or not external_storage(disk, row) or not idle(disk):
                break
            context = block_context(path, row["maj:min"], role="source" if zone == "/investigation" else "destination")
            node = (Path("/sys/dev/block") / row["maj:min"]).resolve(strict=True)
            parent = usb_parent(node)
            if parent is not None:
                context["usb_identity"] = inspect_usb(parent)
                vid_pid = (parent / "idVendor").read_text().strip() + ":" + (parent / "idProduct").read_text().strip()
                serial_file = parent / "serial"
                serial = serial_file.read_text().strip() if serial_file.is_file() else None
                entries = blacklist.read_text().splitlines() if blacklist.is_file() else []
                if vid_pid in entries or serial and serial in entries:
                    raise ValueError("USB device denied / périphérique USB sur liste de blocage")
            elif disk.get("tran") == "usb" or zone == "/stockage":
                raise ValueError("USB identity unavailable / identité USB non vérifiable")
            return context
    raise ValueError(f"{path}: no eligible unmounted device / périphérique démonté admissible introuvable")


def _run(arguments, fd, *, machine=False, context=None, env=None):
    child_env = dict(os.environ if env is None else env, **{LEASE_ENV: str(fd)})
    if context is not None:
        child_env["VIGIL_DEVICE_CONTEXT"] = json.dumps(context, ensure_ascii=True)
    result = subprocess.run(arguments, env=child_env, pass_fds=(fd,),
                            stdin=subprocess.DEVNULL if machine else None,
                            stdout=sys.stderr if machine else None, check=False)
    return result.returncode


def _audit(action, zone, result, resources=()):
    syslog.syslog(syslog.LOG_NOTICE, json.dumps({
        "component": "vigil.devices", "operation": action, "zone": zone,
        "uid": os.getuid(), "status": result,
        "resources": [{key: row.get(key) for key in ("path", "mountpoint", "mount_id", "major_minor",
                                                     "disk_sequence", "verified")} for row in resources],
    }, ensure_ascii=True))


def run_job(arguments, *, analysis=False):
    with device_lease(shared=analysis) as fd:
        context = None
        if analysis:
            context = [item for item in status() if item["zone"] == "/investigation"]
            if not context or not all(item["verified"] for item in context):
                raise ValueError("Montages d’investigation RO non vérifiés / Investigation RO mounts not verified")
        code = _run(arguments, fd, context=context)
        _audit("analysis" if analysis else "job", "/investigation" if analysis else None,
               "success" if code == 0 else "failed", context or ())
        return code


def inventory():
    return devices()


def triage(zone, path=None):
    zone = normalized_zone(zone)
    base = legacy_base()
    data = data_directory(base)
    with device_lease(shared=path is not None) as fd:
        if path is None:
            if not sys.stdin.isatty():
                raise ValueError("Le mode non interactif exige --device / Provide --device")
            script = base / "scripts/lib/vigil-device-select.sh"
            result = subprocess.run(
                ["/usr/bin/bash", str(script), str(data),
                 "Source" if zone == "/investigation" else "Destination"],
                stdout=subprocess.PIPE, text=True, pass_fds=(fd,), check=False,
            )
            if result.returncode:
                raise ValueError("Sélection annulée ou impossible / Selection cancelled or unavailable")
            path = result.stdout.strip()
        return validate_selection(path, zone, data / "usb/blacklist.txt")


def operate(action, zone, *, device=None, target=None, confirm_write=False):
    zone = normalized_zone(zone)
    interactive = device is None and target is None
    if interactive and not sys.stdin.isatty():
        raise ValueError("Le mode non interactif exige --device ou --target / Provide --device or --target")
    if action == "mount" and zone == "/stockage" and not interactive and not confirm_write:
        raise ValueError("Confirmez l’écriture avec --confirm-write / Confirm writes with --confirm-write")
    base = legacy_base()
    data = data_directory(base)
    operator = str(os.getuid())
    directory = "analyse" if zone == "/investigation" else "stockage"
    name = {"mount": "mount", "unmount": "umount"}[action]
    prefix = "vigil_usb_" if zone == "/investigation" else "vigil_stockage_"
    script = base / "scripts" / directory / (prefix + name + ".sh")
    env = dict(os.environ, VIGIL_BASE=str(base), VIGIL_DATA_DIR=str(data), VIGIL_DEVICE_MANAGED="1")
    for key in ("SELECTION", "TARGET", "NONINTERACTIVE", "IDENTITY", "CONTEXT", "MOUNT_ID"):
        env.pop("VIGIL_DEVICE_" + key, None)
    log_dir = default_database().parent / "device-operations"
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    env.update(VIGIL_ACTIVE_USER=operator, VIGIL_LEGACY_PROJECT="(no-project)",
               VIGIL_LEGACY_CASE_DIR=str(log_dir), VIGIL_CASE_INTEGRITY="1")
    if zone == "/investigation":
        env["VIGIL_CASE_CENSUS"] = "1"
    else:
        env["VIGIL_QT_STORAGE"] = "1"
    with device_lease() as fd:
        before = [row for row in mounted_resources() if row["zone"] == zone]
        if action == "mount" and before:
            raise ValueError("Zone déjà montée, démontez-la d’abord / Zone occupied, unmount first")
        if action == "unmount" and interactive and before:
            targets = [row["mountpoint"] for row in before
                       if not any(other["mountpoint"].startswith(row["mountpoint"] + "/") for other in before)]
            script_dir = base / "scripts/lib"
            result = subprocess.run(
                ["/usr/bin/bash", str(script_dir / "vigil-device-select.sh"), "--mounted", *targets],
                stdout=subprocess.PIPE, text=True, check=False,
            )
            if result.returncode:
                raise ValueError("Sélection annulée ou impossible / Selection cancelled or unavailable")
            target = targets[int(result.stdout)]
        if not interactive:
            env["VIGIL_DEVICE_NONINTERACTIVE"] = "1"
        if not interactive or target is not None:
            if action == "mount":
                context = validate_selection(device, zone, data / "usb/blacklist.txt")
                env["VIGIL_DEVICE_SELECTION"] = device
                env["VIGIL_DEVICE_IDENTITY"] = json.dumps(context)
            else:
                matches = [row for row in before if row["mountpoint"] == target]
                if len(matches) != 1 or any(row["mountpoint"].startswith(target + "/") for row in before):
                    raise ValueError("Point de montage absent, ambigu ou avec sous-montages / Target missing, ambiguous or has submounts")
                env["VIGIL_DEVICE_TARGET"] = target
                env["VIGIL_DEVICE_MOUNT_ID"] = str(matches[0]["mount_id"])
        code = _run(["/usr/bin/bash", str(script)], fd, machine=not interactive, env=env)
        after = [row for row in status() if row["zone"] == zone]
        if action == "mount":
            verified = bool(after) and all(row["verified"] for row in after)
            complete = verified and (not device or any(device in {row["path"], row.get("disk")} for row in after))
        else:
            complete = not any(row["mountpoint"] == target for row in after) if target else not after
        success = code == 0 and complete
        _audit(action, zone, "success" if success else "failed", after if action == "mount" else before)
        return {"operation": action, "zone": zone, "success": success, "exit_code": code, "mounts": after}


def shell_check(arguments):
    try:
        action, zone, operand = arguments
        if zone not in ZONES:
            raise ValueError("Invalid zone / zone invalide")
        if action in {"mount", "capture"}:
            observed = validate_selection(operand, zone, data_directory() / "usb/blacklist.txt")
            if expected := os.environ.get("VIGIL_DEVICE_IDENTITY"):
                canonical = json.loads(json.dumps(observed))
                if canonical != json.loads(expected):
                    raise ValueError("Selected identity changed / identité sélectionnée modifiée")
            if action == "capture":
                print(json.dumps(observed, ensure_ascii=True))
        elif action in {"unmount", "mount-id", "verify"}:
            snapshot = mounted_resources()
            records = [row for row in snapshot if row["zone"] == zone and row["mountpoint"] == operand]
            if len(records) != 1:
                raise ValueError("Missing or ambiguous mount / montage absent ou ambigu")
            if action == "mount-id":
                print(records[0]["mount_id"])
            elif action == "verify":
                result = verify_resource(records[0])
                if not result["verified"]:
                    raise ValueError(result["error"])
                if expected := os.environ.get("VIGIL_DEVICE_IDENTITY"):
                    context = json.loads(expected)
                    if any(context[key] != result[key] for key in ("disk_sequence", "disk")):
                        raise ValueError("Mounted disk identity changed / identité du disque monté modifiée")
                expected_device = os.environ.get("VIGIL_VERIFY_DEVICE")
                if expected_device and result["path"] != expected_device:
                    raise ValueError("Mounted device changed / périphérique monté modifié")
            else:
                if any(row["mountpoint"].startswith(operand + "/") for row in snapshot):
                    raise ValueError("Nested mount still in use / sous-montage encore présent")
                if expected := os.environ.get("VIGIL_DEVICE_MOUNT_ID"):
                    if str(records[0]["mount_id"]) != expected:
                        raise ValueError("Mount identity changed / identité du montage modifiée")
        else:
            raise ValueError("Invalid operation / opération invalide")
        return 0
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


def main():
    """Internal adapter for supervised GUI jobs."""
    try:
        mode, *arguments = sys.argv[1:]
        if mode not in {"operation", "analysis"} or not arguments:
            raise ValueError("Invalid device job / opération périphérique invalide")
        return run_job(arguments, analysis=mode == "analysis")
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
