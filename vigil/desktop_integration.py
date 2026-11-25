"""Resolve explorer selections and stage inert copies for desktop applications."""
import os
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .inspection import open_evidence_path

MAX_VIEW_BYTES = 256 * 1024**2
EXECUTABLE_SUFFIX = {
    ".appimage", ".bat", ".cmd", ".com", ".desktop", ".dll", ".exe", ".jar", ".js",
    ".lnk", ".msi", ".ps1", ".py", ".run", ".sh", ".url", ".vbs",
}
# Only recognized document, image, media, archive and plain-text types may leave the inert viewer.
DOCUMENT_SUFFIX = {
    ".pdf", ".txt", ".log", ".csv", ".json", ".xml", ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".svg",
    ".doc", ".docx", ".docm", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".pptm",
    ".odt", ".ods", ".odp", ".mp4", ".mkv", ".webm", ".mp3", ".wav", ".flac",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz",
}


@contextmanager
def checked_descriptor(path, *, mount=None, scope=None, directory=False):
    if mount:
        with open_evidence_path(path, *mount, directory=directory) as descriptor:
            yield descriptor
        return
    if (scope is None or not path.is_relative_to(scope)
            or path.resolve(strict=True) != path.absolute()
            or path.is_relative_to("/investigation")):
        raise ValueError("Unsafe or unavailable local resource / Ressource locale inaccessible ou hors périmètre")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fd = os.open("/", flags | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:], 2):
            entry_flags = flags | os.O_DIRECTORY if directory or index < len(path.parts) else (
                os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            child = os.open(part, entry_flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
            raise ValueError("Unexpected resource type / Type de ressource inattendu")
        yield fd
    finally:
        os.close(fd)


def prepare_view(state, source, display_name, *, mount=None, scope=None):
    suffix = Path(display_name).suffix.casefold()
    if suffix in EXECUTABLE_SUFFIX or suffix not in DOCUMENT_SUFFIX:
        raise ValueError("Use the inert HEX/ASCII viewer for this file type / Utilisez l’aperçu inerte HEX/ASCII")
    with checked_descriptor(source, mount=mount, scope=scope) as selected:
        descriptor = os.open(f"/proc/self/fd/{selected}", os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_mode & 0o111:
                raise ValueError("External opening of executable or special files is blocked / Fichier exécutable ou spécial refusé")
            sample = stream.read(8192)
            magic = (b"\x7fELF", b"MZ", b"#!", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe",
                     b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce")
            if sample.lstrip().startswith(magic) or b"[Desktop Entry]" in sample:
                raise ValueError("Executable content refused / Contenu exécutable refusé")
            if before.st_size > MAX_VIEW_BYTES:
                raise ValueError("External viewing copy limited to 256 MiB / Copie de consultation limitée à 256 Mio")
            folder = state.parent / "viewing-copies"
            if folder.resolve() != folder.absolute() or folder.resolve().is_relative_to("/investigation"):
                raise ValueError("Unsafe viewing directory / Dossier de consultation hors périmètre")
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            view = Path(tempfile.mkdtemp(prefix="view-", dir=folder))
            name = re.sub(r"[^\w .-]", "_", Path(display_name).stem)[:48].strip(" .") or "document"
            target = view / (name + suffix)
            try:
                stream.seek(0)
                with target.open("xb") as copied:
                    remaining = before.st_size
                    while remaining:
                        chunk = stream.read(min(1024**2, remaining))
                        if not chunk:
                            raise ValueError("File changed while copying / Fichier modifié pendant la copie")
                        copied.write(chunk)
                        remaining -= len(chunk)
                    after = os.fstat(stream.fileno())
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise ValueError("File changed while copying / Fichier modifié pendant la copie")
                    os.fchmod(copied.fileno(), 0o400)
            except BaseException:
                shutil.rmtree(view)
                raise
    return target


def graphical_user():
    return os.geteuid() != 0 and bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))



def reveal_in_file_manager(path):
    """Ask the optional freedesktop FileManager1 service to select the file."""
    program = shutil.which("gdbus")
    if not program:
        return False
    # as_uri percent-encodes embedded quotes. GVariant expects an array of URI strings.
    selection = "['" + path.as_uri() + "']"
    try:
        result = subprocess.run(
            [program, "call", "--session", "--timeout", "1", "--dest", "org.freedesktop.FileManager1",
             "--object-path", "/org/freedesktop/FileManager1", "--method",
             "org.freedesktop.FileManager1.ShowItems", selection, "''"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=1.5, check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
