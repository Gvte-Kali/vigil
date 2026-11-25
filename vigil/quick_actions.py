"""Command builders for Qt actions that do not require elevated privileges."""
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path

from .entity import data_directory, legacy_base
from .report_copies import SYNC_REPORTS, report_sync_context


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


def legacy_mount_command(operation, state, case_id, name, operator, *, run_id=None):
    names = {
        "mount": "analyse/vigil_usb_mount.sh",
        "unmount": "analyse/vigil_usb_umount.sh",
        "scan": "clamav/vigil_clamav_full_scan.sh",
    }
    if operation not in names or not re.fullmatch(r"[0-9a-f]{32}", case_id):
        raise ValueError("invalid historical mount context")
    base = legacy_base()
    script = base / "scripts" / names[operation]
    if not script.is_file():
        raise ValueError(f"legacy script unavailable: {script}")
    directory = state.parent / "legacy-custody" / case_id
    if directory.resolve() != directory.absolute() or directory.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid legacy custody directory")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)

    def label(value):
        return "".join(character if character.isprintable() else " " for character in value)

    context = [f"VIGIL_BASE={base}", f"VIGIL_DATA_DIR={data_directory(base)}",
               f"VIGIL_LEGACY_PROJECT={label(name)}",
               f"VIGIL_ACTIVE_USER={label(operator)}", f"VIGIL_LEGACY_CASE_DIR={directory}"]
    arguments = []
    if operation in {"mount", "unmount"}:
        context.append("VIGIL_CASE_INTEGRITY=1")
    if operation == "scan":
        if not run_id or not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("invalid scan execution ID")
        run = directory / f"scan-{run_id}"
        run.mkdir(mode=0o700)
        context.append(f"VIGIL_LEGACY_SCAN_DIR={run}")
        arguments = ["--user", label(operator), "--log", "--pdf"]

    wrapper = '/usr/bin/sudo -v && exec /usr/bin/bash "$@"'
    if operation == "mount":
        wrapper = (
            '/usr/bin/python3 -I "$VIGIL_BASE/scripts/analyse/vigil_census_mount_guard.py" '
            '--before-mount && /usr/bin/sudo -v && /usr/bin/env VIGIL_CASE_CENSUS=1 /usr/bin/bash "$@" && '
            '/usr/bin/env VIGIL_CASE_CENSUS=1 /usr/bin/bash '
            '"$VIGIL_BASE/scripts/analyse/vigil_census.sh" --user "$VIGIL_ACTIVE_USER"; '
            f'rc=$?; {SYNC_REPORTS} || {{ [ "$rc" -ne 0 ] || rc=1; }}; exit "$rc"'
        )
    if operation == "scan":
        wrapper = (
            '/usr/bin/sudo -v && /usr/bin/bash "$@"; '
            f'rc=$?; {SYNC_REPORTS} || {{ [ "$rc" -ne 0 ] || rc=1; }}; exit "$rc"'
        )
    return [
        "/usr/bin/env", *report_sync_context(directory), *context, "/usr/bin/bash", "-c", wrapper,
        "vigil", str(script), *arguments,
    ]


def storage_command(operation, state, case_id, name, operator):
    scripts = {"mount": "vigil_stockage_mount.sh", "unmount": "vigil_stockage_umount.sh"}
    if operation not in scripts:
        raise ValueError("Opération de stockage inconnue / Unsupported storage operation")
    if case_id and (not isinstance(case_id, str) or not re.fullmatch(r"[0-9a-f]{32}", case_id)):
        raise ValueError("Identifiant d’affaire invalide / Invalid case ID")
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError("Opérateur requis pour le stockage / Storage requires an operator")
    base = legacy_base()
    script = base / "scripts" / "stockage" / scripts[operation]
    if not script.is_file():
        raise ValueError(f"legacy script unavailable: {script}")
    directory = state.parent / ("legacy-custody" if case_id else "storage-operations")
    if case_id:
        directory /= case_id
    if directory.resolve() != directory.absolute() or directory.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid storage log directory")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)

    def label(value):
        return "".join(character if character.isprintable() else " " for character in value)

    return [
        "/usr/bin/env", "VIGIL_QT_STORAGE=1", f"VIGIL_BASE={base}",
        f"VIGIL_DATA_DIR={data_directory(base)}", f"VIGIL_ACTIVE_USER={label(operator)}",
        f"VIGIL_LEGACY_PROJECT={label(name) if case_id else '(no-project)'}",
        f"VIGIL_LEGACY_CASE_DIR={directory}", "/usr/bin/bash", "-c",
        '/usr/bin/sudo -v && exec /usr/bin/bash "$@"', "vigil", str(script),
    ]


def acquisition_command(operation, *, local_directory=None, external=False, language=None):
    if operation not in {"clone", "image"}:
        raise ValueError("unsupported acquisition operation")
    if (local_directory is not None and external) or (operation == "clone" and (local_directory is not None or external)):
        raise ValueError("invalid acquisition destination")
    script = legacy_base() / "scripts" / "imager" / "vigil_acquire.py"
    if not script.is_file():
        raise ValueError(f"acquisition script unavailable: {script}")
    if language not in {None, "fr", "en"}:
        raise ValueError("invalid script language")
    arguments = ["--language", language] if language else []
    if local_directory is not None:
        arguments.extend(("--local-directory", str(local_directory)))
    elif external:
        arguments.append("--external")
    return [
        "/usr/bin/sudo", "--", "/usr/bin/unshare", "--mount", "--propagation", "private",
        "--", "/usr/bin/python3", "-I", str(script), operation, "--local-default", str(Path.home()), *arguments,
    ]
