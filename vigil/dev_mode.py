"""Isolation checks for the opt-in, unprivileged development workspace."""
import os
from pathlib import Path


BLOCKED = "Action système désactivée en recette / System action disabled in development mode"


def active():
    return "VIGIL_DEV_ROOT" in os.environ


def validate(state):
    root = Path(os.environ["VIGIL_DEV_ROOT"])
    if not root.is_absolute() or root.resolve() != root or root.stat().st_uid != os.getuid():
        raise ValueError("Invalid development workspace root")
    for variable, name in (("VIGIL_STATE_DIR", "state"), ("VIGIL_DATA_DIR", "data"),
                           ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "xdg-state"),
                           ("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "xdg-data")):
        path = root / name
        if os.environ.get(variable) != str(path) or path.resolve() != path or not path.is_dir():
            raise ValueError(f"Development workspace requires isolated {variable}")
    if state != root / "state/cases.sqlite" or state.is_symlink():
        raise ValueError("Development workspace requires its own database")
