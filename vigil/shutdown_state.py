"""Record and verify the block and mount state visible to Vigil."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from .device_manager import DeviceBusy, device_lease
from .entity import atomic_write
from .storage import utc_now
from .system_info import read_zones

SYS_BLOCK = Path("/sys/class/block")


class ShutdownBlocked(ValueError):
    """The observed system state prevents an ordinary Vigil shutdown."""


def read_block_modes(directory=SYS_BLOCK):
    modes = {}
    for entry in sorted(directory.iterdir()):
        node = entry.resolve(strict=True)
        is_partition = (node / "partition").is_file()
        disk = node.parent if is_partition else node
        try:
            sequence = (disk / "diskseq").read_text(encoding="ascii").strip()
        except FileNotFoundError:
            sequence = None
        number = (node / "dev").read_text(encoding="ascii").strip()
        mode = (node / "ro").read_text(encoding="ascii").strip()
        if mode not in {"0", "1"}:
            raise ValueError(f"/dev/{entry.name}: unknown read-only flag {mode!r}")
        modes[entry.name] = {
            "sysfs": str(node),
            "parent": disk.name if is_partition else None,
            "major_minor": number,
            "disk_sequence": sequence,
            "mode": "ro" if mode == "1" else "rw",
        }
    return modes


def system_policy_snapshot():
    rules = {}
    for path in (Path("/etc/udev/rules.d/99-vigil-hotplug.rules"),
                 Path("/etc/udisks2/udisks2.conf"), Path("/etc/systemd/system/udisks2.service")):
        if path.is_symlink():
            rules[str(path)] = {"link": str(path.readlink())}
        elif path.is_file():
            try:
                with path.open("rb") as stream:
                    rules[str(path)] = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
            except OSError as error:
                rules[str(path)] = {"error": str(error)}
        else:
            rules[str(path)] = {"present": False}
    service = {}
    if systemctl := shutil.which("systemctl"):
        for operation in ("is-enabled", "is-active"):
            try:
                result = subprocess.run(
                    [systemctl, operation, "udisks2.service"], capture_output=True,
                    text=True, timeout=2, check=False,
                )
                service[operation] = result.stdout.strip() or None
            except (OSError, subprocess.SubprocessError):
                service[operation] = None
    return {"policies": rules, "udisks2": service}


def capture_startup_state(state):
    snapshot = {
        "schema_version": 1,
        "captured_at": utc_now(),
        "block_devices": read_block_modes(),
        "zones": read_zones(),
        **system_policy_snapshot(),
    }
    folder = state.parent / "system-snapshots"
    if folder.resolve() != folder.absolute() or folder.resolve().is_relative_to("/investigation"):
        raise ValueError("unsafe system snapshot directory")
    path = folder / f"startup-{uuid4().hex}.json"
    atomic_write(path, (json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n").encode())
    return snapshot["block_devices"], path


def check_shutdown_state():
    """Block shutdown while either Vigil zone contains a mount."""
    try:
        with device_lease():
            mounted = [row for entries in read_zones().values() for row in entries]
    except DeviceBusy as error:
        raise ShutdownBlocked(str(error)) from error
    if mounted:
        raise ShutdownBlocked("\n".join(
            f"{target} · {source} · {filesystem} · {mode}"
            for target, source, filesystem, mode in mounted
        ))
