"""Command builders for Qt actions that do not require elevated privileges."""
import shutil


def tool(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f"{name}: executable unavailable")
    return path


def signatures_path(state):
    return state.parent / "clamav"


def scan_command(path, state):
    path = path.resolve(strict=True)
    if not (path.is_file() or path.is_dir()):
        raise ValueError("select a regular file or directory")
    arguments = [tool("clamscan"), "--recursive=yes", "--scan-archive=yes",
                 "--alert-encrypted=yes", "--follow-dir-symlinks=0",
                 "--follow-file-symlinks=0", "--cross-fs=no"]
    signatures = signatures_path(state)
    if any(file.is_file() for pattern in ("*.cvd", "*.cld") for file in signatures.glob(pattern)):
        arguments.extend(("--database", str(signatures)))
    return [*arguments, "--", str(path)]


def update_command(state):
    executable = tool("freshclam")
    signatures = signatures_path(state)
    signatures.mkdir(mode=0o700, parents=True, exist_ok=True)
    config = signatures / "freshclam.conf"
    if not config.exists():
        with config.open("x", encoding="ascii") as stream:
            stream.write("DatabaseMirror database.clamav.net\n")
    return [executable, f"--config-file={config}", f"--datadir={signatures}"]
