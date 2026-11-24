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


def doctor():
    return {
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP"),
        "session": "wayland" if os.environ.get("WAYLAND_DISPLAY") else
        "x11" if os.environ.get("DISPLAY") else "headless",
        "tools": {tool: shutil.which(tool) for tool in (
            "bash", "file", "jq", "clamscan", "ewfinfo", "affinfo",
            "xdg-terminal-exec", "konsole", "gnome-terminal", "xfce4-terminal",
            "kitty", "xterm",
        )},
    }


BUILTIN_MODULES = Path(__file__).with_name("modules")
