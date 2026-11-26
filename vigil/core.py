"""Desktop-independent module discovery and capability diagnostics."""
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from yaml.constructor import ConstructorError


class ManifestLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep)
        if len(mapping) != len(node.value):
            raise ConstructorError(None, None, "duplicate manifest key", node.start_mark)
        return mapping


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    api_version: Literal[1]
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*\.[a-z][a-z0-9_-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    entrypoint: str
    dependencies: list[str] = Field(default_factory=list)
    capabilities: list[Literal["evidence.read", "results.write", "privileged.operation"]]

    @field_validator("entrypoint")
    @classmethod
    def relative_script(cls, value):
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.suffix not in {".sh", ".py"}:
            raise ValueError("expected a relative Bash or Python script")
        return value

    @field_validator("dependencies")
    @classmethod
    def executable_names(cls, values):
        if any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", value) for value in values):
            raise ValueError("dependencies must be executable names")
        return values


def discover(directory):
    manifests = {}
    errors = {}
    for path in sorted(directory.glob("*.yaml")):
        try:
            with path.open("rb") as stream:
                data = stream.read(65537)
            if len(data) > 65536:
                raise ValueError("manifest exceeds 64 KiB")
            manifest = Manifest.model_validate(yaml.load(data, Loader=ManifestLoader))
            if manifest.id in manifests:
                raise ValueError(f"duplicate module ID: {manifest.id}")
            manifests[manifest.id] = manifest
        except (OSError, ValueError, yaml.YAMLError, RecursionError) as error:
            errors[path.name] = str(error)
    return manifests, errors


def script_diagnostics():
    """Check the shared entrypoints used by the CLI and both workspaces."""
    from .entity import legacy_base

    root = legacy_base()
    manifests, _ = discover(BUILTIN_MODULES)
    entrypoints = {manifest.entrypoint for manifest in manifests.values()}
    entrypoints.update({
        "scripts/analyse/vigil_census_mount_guard.py", "scripts/analyse/vigil_usb_mount.sh",
        "scripts/analyse/vigil_usb_umount.sh", "scripts/clamav/vigil_clamav_full_scan.sh",
        "scripts/imager/vigil_acquire.py", "scripts/imager/vigil_acquire_triage.sh",
        "scripts/lib/vigil-device-ops.sh", "scripts/lib/vigil-device-select.sh",
        "scripts/lib/vigil-device-triage.sh", "scripts/lib/vigil-terminal.sh",
        "scripts/lib/vigil_block_inventory.py", "scripts/post-install/activate-hotplug.sh",
        "scripts/stockage/vigil_stockage_mount.sh", "scripts/stockage/vigil_stockage_umount.sh",
    })
    issues = {}
    for entry in sorted(entrypoints):
        path = root / entry
        try:
            if not path.resolve(strict=True).is_relative_to(root.resolve()):
                raise ValueError("outside the Vigil installation")
            if not path.is_file():
                raise ValueError("expected a regular script")
            with path.open("rb") as stream:
                stream.read(1)
        except (OSError, ValueError) as error:
            issues[entry] = str(error)
    return {"checked": len(entrypoints), "issues": issues}


def doctor():
    from .external_terminal import TERMINALS

    return {
        "scripts": script_diagnostics(),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP"),
        "session": "wayland" if os.environ.get("WAYLAND_DISPLAY") else
        "x11" if os.environ.get("DISPLAY") else "headless",
        "tools": {tool: shutil.which(tool) for tool in (
            "bash", "sh", "python3", "unshare", "sudo", "file", "jq", "clamscan", "freshclam", "ewfinfo", "affinfo",
            "chafa", "lsblk", "findmnt", "mmls", "pv", "xdg-open", *TERMINALS,
        )},
    }


BUILTIN_MODULES = Path(__file__).with_name("modules")
