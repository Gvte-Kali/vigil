"""Shared Vigil 1.0 entity configuration and atomic writes."""
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

FIELDS = ("entity_name", "establishment", "address", "phone", "email")


def legacy_base():
    source = Path(__file__).resolve().parents[1]
    return source if (source / "scripts/analyse").is_dir() else Path("/opt/vigil")


def data_directory(base=None):
    return Path(os.environ.get("VIGIL_DATA_DIR") or (base or legacy_base()) / "data")


def load_entity(data):
    path = data / "config/system.json"
    try:
        with path.open(encoding="utf-8") as stream:
            result = json.load(stream)
    except FileNotFoundError:
        return {}
    if not isinstance(result, dict):
        raise ValueError("entity configuration must be a JSON object")
    return result


def atomic_write(path, content):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def save_entity(data, fields, logo=None):
    config = load_entity(data)
    config.update({key: fields[key] for key in FIELDS})
    config["configured_at"] = datetime.now(UTC).isoformat()
    new_logo = None
    if logo is not None:
        if logo:
            config["logo"] = f"config/logo/entity-{uuid4().hex}.png"
            new_logo = data / config["logo"]
            atomic_write(new_logo, logo)
        else:
            config["logo"] = ""
    try:
        atomic_write(data / "config/system.json",
                     (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode())
    except OSError:
        if new_logo is not None:
            new_logo.unlink(missing_ok=True)
        raise
    return config
