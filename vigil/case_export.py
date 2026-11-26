"""Export one case as a tarball with internal and external SHA-256 manifests."""
import ctypes
import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import evidence_layout
from .case_import import verify_archive
from .destination import writable_destination
from .history import case_events
from .report_copies import sync_report_copies
from .storage import audit, case_storage_directory, database, evidence_copy_path, file_identity, require_active_case, utc_now


ARCHIVE_EXTENSION = ".tar.gz"


@dataclass(frozen=True)
class CaseExport:
    path: Path
    missing: tuple[str, ...]
    archive: Path


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size):
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def archive_info(name, size):
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o400
    return info


def archive_file(archive, path, name):
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"not a regular case file: {path}")
        reader = HashingReader(stream)
        member = archive_info(name, before.st_size)
        member.mtime = int(before.st_mtime)
        archive.addfile(member, reader)
        if file_identity(before) != file_identity(os.fstat(stream.fileno())):
            raise ValueError(f"case file changed during export: {path}")
        return reader.digest.hexdigest()


def case_files(root, *, exclude=()):
    if not root.exists():
        return
    if root.resolve() != root.absolute() or not root.is_dir():
        raise ValueError(f"invalid case directory: {root}")
    device = root.stat().st_dev

    def fail(error):
        raise error

    for folder, dirs, files in os.walk(root, onerror=fail):
        directory = Path(folder)
        dirs[:] = sorted(name for name in dirs if name not in exclude
                         and not (directory / name).is_symlink()
                         and (directory / name).stat().st_dev == device)
        for name in sorted(files):
            if name in exclude:
                continue
            path = directory / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_dev == device:
                yield path



def collect_results(state, case_id, custody, legacy):
    results = {f"resultats/{path.relative_to(custody).as_posix()}": path
               for path in case_files(custody, exclude=("preuves", "projet-v1", ".vigil-import"))}
    if legacy is not None:
        if not legacy.is_dir():
            raise ValueError(f"imported case directory is unavailable: {legacy}")
        results.update({f"projet-v1/{path.relative_to(legacy).as_posix()}": path
                        for path in case_files(legacy)})
    reports = state.parent / "reports"
    if reports.resolve() == reports.absolute():
        for folder in sorted(reports.glob("case-*")):
            if folder.is_symlink() or not folder.is_dir():
                continue
            metadata = folder / "case.json"
            if metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size > 32 * 1024**2:
                continue
            try:
                owner = json.loads(metadata.read_bytes()).get("case")
            except (UnicodeError, ValueError, AttributeError):
                continue
            if isinstance(owner, dict) and owner.get("id") == case_id:
                for name in ("case.json", "SHA256SUMS"):
                    path = folder / name
                    if path.is_file() and not path.is_symlink():
                        results[f"resultats/rapports-json/{folder.name}/{name}"] = path
    return results



def publish_export(stage, destination):
    # Linux renameat2 publishes the whole directory and refuses to replace an existing entry.
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    if rename(at_fdcwd, os.fsencode(stage), at_fdcwd, os.fsencode(destination), rename_noreplace):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def export_case(state, case_id, operator, destination, name="affaire"):
    stem = name.strip()
    if stem.lower().endswith(ARCHIVE_EXTENSION):
        stem = stem[:-len(ARCHIVE_EXTENSION)].rstrip()
    if not stem or stem.startswith(".") or any(
            char in "/\\" or ord(char) < 32 or ord(char) == 127 for char in stem):
        raise ValueError("Indiquez un nom de fichier valide / Enter a valid archive name")
    filename = stem + ARCHIVE_EXTENSION
    if len(os.fsencode(filename + ".sha256")) > 255:
        raise ValueError("Nom de fichier trop long / Archive name too long")
    destination = writable_destination(destination).path
    custody = case_storage_directory(state, case_id)
    with database(state) as connection:
        case = dict(require_active_case(connection, case_id))
        details = connection.execute(
            "SELECT reference, description FROM case_details WHERE case_id = ?", (case_id,),
        ).fetchone()
        if details is not None:
            case.update(dict(details))
        evidence = [dict(row) for row in connection.execute(
            """SELECT evidence.*, relative_path, source_key FROM evidence
               LEFT JOIN evidence_copies ON evidence.id = evidence_id
               WHERE evidence.case_id = ? ORDER BY evidence.id""", (case_id,))]
        origin = connection.execute("SELECT sha256, provenance FROM case_archives WHERE case_id = ?", (case_id,)).fetchone()
        source_archive = {"sha256": origin["sha256"], **json.loads(origin["provenance"])} if origin else None
        restored_legacy = custody / "projet-v1"
        legacy = (restored_legacy if origin and restored_legacy.is_dir() else
                  Path(case["legacy_path"]) if case["legacy_path"] else None)
        if destination.is_relative_to(custody.resolve()) or (
                legacy and destination.is_relative_to(legacy.resolve())):
            raise ValueError("export destination must be outside the case directories")
        audit(connection, operator, case_id, "case.export.start", {})
        events = case_events(connection, case_id, limit=None)

    writable_destination(destination)
    stage = Path(tempfile.mkdtemp(prefix=".vigil-export-", dir=destination))
    final = None
    published = False
    try:
        sync_report_copies(custody, legacy)
        sources = collect_results(state, case_id, custody, legacy)
        identities = {path: file_identity(path.lstat()) for path in sources.values()}
        with database(state) as connection:
            copies = {row["id"]: evidence_copy_path(state, case_id, row["id"], connection=connection)
                      for row in evidence}
        copy_identities = {path: file_identity(path.lstat()) if os.path.lexists(path) else None
                           for path in copies.values()}
        archive_path = stage / filename
        hashes, members = {}, {}
        missing = []
        with tarfile.open(archive_path, "w:gz") as archive:
            folder = tarfile.TarInfo("preuves/")
            folder.type = tarfile.DIRTYPE
            folder.mode = 0o700
            archive.addfile(folder)
            for record in evidence:
                source = copies[record["id"]]
                try:
                    source.lstat()
                except FileNotFoundError:
                    missing.append(record["path"])
                    record.update(archive_path=None, copy_status="missing")
                    continue
                evidence_layout.require_readonly(source)
                name = str(evidence_layout.legacy_path(record["id"]))
                digest = archive_file(archive, source, name)
                if digest != record["sha256"] or archive.members[-1].size != record["size"]:
                    raise ValueError(f"evidence copy failed integrity check: {record['path']}")
                hashes[name] = digest
                members[name] = archive.members[-1].size
                record.update(archive_path=name, copy_status="included")
            for name, source in sources.items():
                hashes[name] = archive_file(archive, source, name)
                members[name] = archive.members[-1].size
            try:
                release = version("vigil-dfir")
            except PackageNotFoundError:
                release = "2.0.0a1"
            metadata = json.dumps({
                "schema_version": 3, "vigil_version": release,
                "coverage": "partial" if missing else "complete",
                "missing_evidence_count": len(missing), "exported_at": utc_now(), "operator": operator,
                "case": case, "evidence": evidence, "audit": events, "members": members,
                "audit_cutoff": events[-1]["sequence"] if events else None,
                "source_archive": source_archive,
            }, ensure_ascii=True, indent=2).encode() + b"\n"
            archive.addfile(archive_info("affaire.json", len(metadata)), io.BytesIO(metadata))
            hashes["affaire.json"] = hashlib.sha256(metadata).hexdigest()
            # GNU sha256sum escaping keeps paths with newlines and backslashes verifiable.
            lines = []
            for name, digest in hashes.items():
                escaped = name.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                marker = "\\" if escaped != name else ""
                lines.append(f"{marker}{digest}  {escaped}\n")
            manifest = "".join(lines).encode("utf-8", errors="surrogateescape")
            archive.addfile(archive_info("SHA256SUMS", len(manifest)), io.BytesIO(manifest))
        with archive_path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        (stage / f"{filename}.sha256").write_bytes(f"{digest}  ".encode("ascii") + os.fsencode(filename) + b"\n")
        verify_archive(archive_path)
        with database(state) as connection:
            require_active_case(connection, case_id)
            current = [tuple(row) for row in connection.execute(
                "SELECT id, path, size, sha256 FROM evidence WHERE case_id = ? ORDER BY id", (case_id,)
            )]
            snapshot = [(row["id"], row["path"], row["size"], row["sha256"]) for row in evidence]
            if current != snapshot:
                raise ValueError("evidence selection changed during export")
            if (collect_results(state, case_id, custody, legacy) != sources
                    or any(file_identity(path.lstat()) != identity for path, identity in identities.items())
                    or any((file_identity(path.lstat()) if os.path.lexists(path) else None) != identity
                           for path, identity in copy_identities.items())):
                raise ValueError("case files changed during export")
            # Keep repeat exports separate, with a readable suffix only on collision.
            for number in range(1, 10001):
                final = destination / (stem if number == 1 else f"{stem} ({number})")
                try:
                    publish_export(stage, final)
                except FileExistsError:
                    continue
                published = True
                break
            else:
                raise FileExistsError(f"No available export folder for {stem}")
            audit(connection, operator, case_id, "case.export.success", {
                "sha256": digest, "archive": str(final / filename), "missing_evidence_count": len(missing),
            })
    except BaseException:
        shutil.rmtree(final if published else stage)
        with database(state) as connection:
            if not connection.execute(
                "SELECT 1 FROM deleted_cases WHERE case_id = ?", (case_id,)
            ).fetchone():
                audit(connection, operator, case_id, "case.export.error", {})
        raise
    return CaseExport(final, tuple(missing), final / filename)
