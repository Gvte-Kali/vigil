"""Read the Linux distribution family from os-release."""
import shlex


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
