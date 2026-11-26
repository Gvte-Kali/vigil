"""Keep case PDF copies grouped by their source execution."""
from contextlib import contextmanager
import fcntl
import os
import shutil
import sys
import tempfile
from pathlib import Path


def report_sources(custody, imported=None):
    yield ("montage", custody)
    for folder in sorted(custody.glob("scan-*")):
        if folder.is_dir() and not folder.is_symlink():
            yield (folder.name, folder)
    analyses = custody / "analyses"
    if analyses.is_dir() and not analyses.is_symlink():
        for folder in sorted(analyses.iterdir()):
            if folder.is_dir() and not folder.is_symlink():
                yield (f"analyses/{folder.name}", folder)
    if imported and imported.is_dir() and imported.resolve() == imported.absolute():
        yield ("projet-v1", imported)


@contextmanager
def report_copy_lock(custody):
    if custody.resolve() != custody.absolute() or custody.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid case directory for PDF reports")
    custody.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(custody, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def sync_report_copies(custody, imported=None):
    with report_copy_lock(custody):
        return _sync_report_copies(custody, imported)


def _sync_report_copies(custody, imported):
    root = custody / "rapports"
    if root.resolve() != root.absolute():
        raise ValueError("invalid PDF report directory")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    for group, directory in report_sources(custody, imported):
        for source in directory.glob("*"):
            if source.suffix.casefold() != ".pdf" or source.is_symlink() or not source.is_file():
                continue
            destination = root / group / source.name
            if destination.resolve() != destination.absolute():
                raise ValueError(f"invalid PDF copy destination: {destination}")
            original = source.stat()
            if destination.exists():
                previous = destination.stat()
                if (original.st_size, original.st_mtime_ns) == (previous.st_size, previous.st_mtime_ns):
                    continue
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
                candidate = Path(temporary) / "report"
                shutil.copyfile(source, candidate)
                shutil.copystat(source, candidate)
                candidate.chmod(0o600)
                candidate.replace(destination)
    copies = []
    for directory, _, files in os.walk(root):
        for name in files:
            path = Path(directory) / name
            if path.suffix.casefold() == ".pdf" and not path.is_symlink() and path.is_file():
                copies.append(path)
    return sorted(copies, key=lambda path: (-path.stat().st_mtime_ns, path.name.casefold(), str(path)))


def report_sync_context(custody):
    return [
        f"VIGIL_REPORT_PYTHON={sys.executable}",
        f"VIGIL_REPORT_SYNC={Path(__file__).resolve()}",
        f"VIGIL_REPORT_CASE={custody}",
    ]


SYNC_REPORTS = '"$VIGIL_REPORT_PYTHON" "$VIGIL_REPORT_SYNC" "$VIGIL_REPORT_CASE"'


if __name__ == "__main__":
    try:
        sync_report_copies(Path(sys.argv[1]))
    except (OSError, ValueError) as error:
        sys.exit(f"Copie des rapports de l’affaire / Case report copy: {error}")
