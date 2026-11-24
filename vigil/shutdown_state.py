"""Record and verify the block and mount state visible to Vigil."""
import json
from pathlib import Path
from uuid import uuid4

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
        disk = node.parent if (node / "partition").is_file() else node
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
            "major_minor": number,
            "disk_sequence": sequence,
            "mode": "ro" if mode == "1" else "rw",
        }
    return modes


def capture_startup_state(state):
    snapshot = {
        "schema_version": 1,
        "captured_at": utc_now(),
        "block_devices": read_block_modes(),
        "zones": read_zones(),
    }
    path = state.parent / "system-snapshots" / f"startup-{uuid4().hex}.json"
    atomic_write(path, (json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n").encode())
    return snapshot["block_devices"], path


def check_shutdown_state(baseline):
    mounted = [row for entries in read_zones().values() for row in entries]
    if mounted:
        raise ShutdownBlocked("\n".join(
            f"{target} · {source} · {filesystem} · {mode}"
            for target, source, filesystem, mode in mounted
        ))
    current = read_block_modes()
    changes = []
    for name in sorted(baseline.keys() | current.keys()):
        before, after = baseline.get(name), current.get(name)
        if before != after:
            # Show identity as well as mode when the kernel reuses a device name.
            def describe(record):
                if record is None:
                    return "—"
                sequence = record["disk_sequence"] or "?"
                return f"{record['mode']} ({record['major_minor']}, seq={sequence})"

            changes.append(f"/dev/{name}: {describe(before)} → {describe(after)}")
    if changes:
        raise ShutdownBlocked("\n".join(changes))
