"""Command builders for Qt actions that do not require elevated privileges."""
import os
import shutil
import stat
import tempfile
from pathlib import Path


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
    signatures = signatures_path(state).absolute()
    signatures.mkdir(mode=0o700, parents=True, exist_ok=True)
    if signatures.is_symlink():
        raise ValueError("Vigil signature directory must not be a symbolic link")
    if any(character in str(signatures) for character in '\r\n"'):
        raise ValueError("unsupported characters in the signature directory")
    config = signatures / "vigil-freshclam.conf"
    with tempfile.NamedTemporaryFile(
        dir=signatures, prefix=".freshclam-", mode="w", encoding="utf-8", delete=False,
    ) as stream:
        generated = Path(stream.name)
        try:
            stream.write(f'DatabaseDirectory "{signatures}"\nDatabaseMirror database.clamav.net\n')
            stream.flush()
            os.replace(generated, config)
        finally:
            generated.unlink(missing_ok=True)
    return [executable, f"--config-file={config}"]


def mount_command(operation):
    """Invoke only the system-installed helper, with interactive sudo."""

    helper = Path("/usr/local/sbin/vigil-mount")
    if operation not in {"mount", "unmount"}:
        raise ValueError("unsupported mount operation")
    for directory in reversed(helper.parents):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("untrusted mount helper directory")
    info = helper.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("untrusted mount helper")
    return ["/usr/bin/sudo", "-k", "--", str(helper), operation]
