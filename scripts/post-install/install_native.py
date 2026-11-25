#!/usr/bin/env python3
"""Install a user-local Vigil venv, optionally selecting native packages."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ("minimal", "forensic", "complet")
COMMON = ("coreutils", "util-linux", "file")
DISTRIBUTIONS = {
    "debian": (
        ("apt-get", "install", "--"),
        ("python3", "python3-venv"),
        ("chafa", "jq", "clamav", "clamav-freshclam", "sleuthkit", "ewf-tools", "ntfs-3g", "pv"),
        ("konsole", "libegl1", "libxkbcommon-x11-0", "libxcb-cursor0", "libxcb-icccm4",
         "libxcb-keysyms1", "libxcb-xinerama0", "libqt6waylandclient6"),
    ),
    "arch": (
        ("pacman", "-S", "--needed", "--"),
        ("python",),
        ("chafa", "jq", "clamav", "sleuthkit", "ntfs-3g", "pv"),
        ("konsole", "libegl", "libxkbcommon-x11", "xcb-util-cursor", "xcb-util-wm", "xcb-util-keysyms", "qt6-wayland"),
    ),
    "fedora": (
        ("dnf", "install", "--"),
        ("python3", "python3-pip"),
        ("chafa", "jq", "clamav", "clamav-update", "sleuthkit", "ntfs-3g", "pv"),
        ("konsole", "libglvnd-egl", "libxkbcommon-x11", "xcb-util-cursor", "xcb-util-wm", "xcb-util-keysyms", "qt6-qtwayland"),
    ),
    "opensuse": (
        ("zypper", "install", "--"),
        ("python3", "python3-pip"),
        ("chafa", "jq", "clamav", "sleuthkit", "ntfs-3g", "pv"),
        ("konsole", "libEGL1", "libxkbcommon-x11-0", "libxcb-cursor0", "libxcb-icccm4",
         "libxcb-keysyms1", "qt6-wayland"),
    ),
}


def identify(path):
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in {"ID", "ID_LIKE"}:
            data[key] = shlex.split(value)
    for name in data.get("ID", []) + data.get("ID_LIKE", []):
        if name in {"debian", "ubuntu", "kali", "parrot", "linuxmint"}:
            return "debian"
        if name in {"arch", "archlinux", "omarchy", "manjaro", "endeavouros"}:
            return "arch"
        if name in {"fedora", "rhel", "centos"}:
            return "fedora"
        if name == "suse" or name.startswith("opensuse"):
            return "opensuse"
    return None


def system_plan(family, profile):
    manager, minimal, forensic, desktop = DISTRIBUTIONS[family]
    packages = COMMON + minimal
    if profile in {"forensic", "complet"}:
        packages += forensic
    if profile == "complet":
        packages += desktop
    return ["sudo", *manager, *packages]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="minimal")
    parser.add_argument("--venv", type=Path, default=Path.home() / ".local/share/vigil/venv")
    parser.add_argument("--os-release", type=Path, default=Path("/etc/os-release"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--system-packages", action="store_true",
                        help="Explicitly allow package installation using the native package manager")
    args = parser.parse_args()
    try:
        if not args.dry_run and os.geteuid() == 0:
            raise ValueError("Run as a regular user. Only --system-packages uses sudo.")
        family = identify(args.os_release)
        if args.system_packages and not family:
            raise ValueError("Unsupported distribution for native package installation")
        target = args.venv.expanduser().resolve()
        source = ".[desktop]" if args.profile == "complet" else "."
        create = [sys.executable, "-m", "venv", str(target)]
        install = [str(target / "bin/python"), "-m", "pip", "install", "-e", source]
        print(f"Distribution: {family or 'unknown'} | Profile: {args.profile}", flush=True)
        if family:
            native = system_plan(family, args.profile)
            print(("Run: " if args.system_packages else "Optional system packages: ") + shlex.join(native), flush=True)
            if args.system_packages and not args.dry_run:
                subprocess.run(native, check=True)
        for command in (create, install):
            print(shlex.join(command), flush=True)
            if not args.dry_run:
                if command == create and (target / "pyvenv.cfg").is_file():
                    continue
                subprocess.run(command, cwd=ROOT, check=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Vigil: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
