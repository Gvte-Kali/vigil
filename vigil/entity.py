"""Shared Vigil 1.0 entity configuration and atomic writes."""
import json
import stat
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


def read_logo_png(path):
    """Validate a bounded organization logo and normalize it to PNG."""
    import io

    from PIL import Image

    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 10 * 1024 * 1024:
            raise ValueError("logo must be a regular image up to 10 MiB")
        try:
            with Image.open(stream, formats=("PNG", "JPEG")) as image:
                width, height = image.size
                if max(width, height) > 4096 or width * height > 8_000_000:
                    raise ValueError("invalid or oversized logo dimensions")
                output = io.BytesIO()
                image.convert("RGBA").save(output, format="PNG")
        except Image.DecompressionBombError as error:
            raise ValueError("invalid or oversized logo dimensions") from error
    return output.getvalue()


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
