#!/usr/bin/env python3
"""Prepare and run an isolated Vigil GUI or TUI development workspace."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DIRECTORIES = {
    "VIGIL_STATE_DIR": "state", "VIGIL_DATA_DIR": "data", "XDG_CONFIG_HOME": "config",
    "XDG_STATE_HOME": "xdg-state", "XDG_CACHE_HOME": "cache", "XDG_DATA_HOME": "xdg-data",
}


def directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError(f"Expected a private directory owned by the operator: {path}")
    return path


def environment(workspace):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("VIGIL_") and key not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}}
    env["VIGIL_DEV_ROOT"] = str(workspace)
    env["VIRTUAL_ENV"] = str(workspace / "venv")
    env["PATH"] = os.pathsep.join((str(workspace / "venv/bin"), env.get("PATH", os.defpath)))
    for key, name in DIRECTORIES.items():
        env[key] = str(directory(workspace / name))
    return env


def fixture(path, contents):
    try:
        with path.open("xb") as output:
            output.write(contents)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != contents:
            raise ValueError(f"Existing fixture differs: {path}") from None


def fixtures(workspace):
    root = directory(workspace / "fixtures")
    project = directory(root / "legacy-case")
    fixture(project / "info.json", b'{"name":"Vigil Synthetic 1.x"}\n')
    fixture(root / "specimen.txt", b"Vigil synthetic evidence\nLine 2\n")
    image = bytearray(4096)
    image[450] = 0x83
    struct.pack_into("<II", image, 454, 1, 7)
    image[510:512] = b"\x55\xaa"
    fixture(root / "disk.raw", image)
    print(f"Fixtures: {root}")


def diagnose(venv, env):
    tools = ("python3", "chafa", "lsblk", "findmnt", "jq", "file", "clamscan", "freshclam",
             "ewfinfo", "affinfo", "mmls", "pv", "konsole", "kitty", "ghostty", "alacritty", "foot", "xdg-terminal-exec")
    result = {"tools": {tool: shutil.which(tool, path=env["PATH"]) for tool in tools},
              "desktop": env.get("XDG_CURRENT_DESKTOP"), "session_type": env.get("XDG_SESSION_TYPE"),
              "display": bool(env.get("DISPLAY")), "wayland_display": bool(env.get("WAYLAND_DISPLAY")),
              "hyprland": bool(env.get("HYPRLAND_INSTANCE_SIGNATURE"))}
    python = venv / "python"
    if python.is_file():
        for key, platform in (("qt_offscreen", "offscreen"), ("qt_x11", "xcb"), ("qt_wayland", "wayland")):
            if (key == "qt_x11" and not result["display"]) or (key == "qt_wayland" and not result["wayland_display"]):
                result[key] = {"tested": False, "reason": "Display unavailable"}
                continue
            try:
                probe = subprocess.run([str(python), "-c", "from PySide6.QtWidgets import QApplication; "
                                        "app = QApplication([]); print(app.platformName())"],
                                       env={**env, "QT_QPA_PLATFORM": platform},
                                       capture_output=True, text=True, timeout=8)
                result[key] = {"tested": True, "ok": probe.returncode == 0,
                               "detail": (probe.stderr or probe.stdout).strip()}
            except subprocess.TimeoutExpired:
                result[key] = {"tested": True, "ok": False, "detail": "Qt startup timed out"}
    else:
        result["venv"] = "Missing. Run setup first."
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.home() / ".local/share/vigil-dev")
    parser.add_argument("action", choices=("setup", "fixtures", "doctor", "test", "gui", "gui-legacy", "tui"))
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise ValueError("Run the development workspace as a regular user")
        workspace = args.workspace.expanduser().absolute()
        if workspace.resolve() != workspace:
            raise ValueError("Workspace path must not contain symbolic links or '..'")
        directory(workspace)
        env = environment(workspace)
        venv = workspace / "venv/bin"
        if args.action == "setup":
            directory(venv.parent)
            subprocess.run([sys.executable, str(ROOT / "scripts/post-install/install_native.py"),
                            "--profile", "complet", "--venv", str(venv.parent)], env=env, check=True)
            fixtures(workspace)
        elif args.action == "fixtures":
            fixtures(workspace)
        elif args.action == "doctor":
            diagnose(venv, env)
        else:
            if not (venv / "vigil").is_file():
                raise ValueError("Development venv missing. Run setup.")
            commands = {
                "test": [str(venv / "python"), "-m", "unittest", "discover", "-s", str(ROOT / "tests")],
                "gui": [str(venv / "vigil"), "gui"],
                "gui-legacy": [str(venv / "vigil-gui")],
                "tui": [str(venv / "vigil"), "tui"],
            }
            if args.action == "test":
                # Test production code paths against each test's isolated fixture.
                env.pop("VIGIL_DEV_ROOT")
                env.setdefault("QT_QPA_PLATFORM", "offscreen")
            os.chdir(ROOT)
            argv = commands[args.action]
            os.execve(argv[0], argv, env)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Vigil: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
