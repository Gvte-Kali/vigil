"""Export one case as a tarball with internal and external SHA-256 manifests."""
import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .history import case_events
from .report_copies import sync_report_copies
from .storage import audit, database, evidence_copy_path, file_identity, require_active_case, utc_now


@dataclass(frozen=True)
class CaseExport:
    path: Path
    missing: tuple[str, ...]


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
        archive.addfile(archive_info(name, before.st_size), reader)
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
            path = directory / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_dev == device:
                yield path


def export_case(state, case_id, operator, destination):
    destination = destination.resolve(strict=True)
    if not destination.is_dir() or destination.is_relative_to("/investigation"):
        raise ValueError("export destination must be outside /investigation")
    custody = evidence_copy_path(state, case_id, "0" * 32).parents[2]
    with database(state) as connection:
        case = dict(require_active_case(connection, case_id))
        evidence = [dict(row) for row in connection.execute(
            "SELECT * FROM evidence WHERE case_id = ? ORDER BY id", (case_id,))]
        legacy = Path(case["legacy_path"]) if case["legacy_path"] else None
        if destination.is_relative_to(custody.resolve()) or (
                legacy and destination.is_relative_to(legacy.resolve())):
            raise ValueError("export destination must be outside the case directories")
        audit(connection, operator, case_id, "case.export.start", {})
        events = case_events(connection, case_id, limit=None)

    sync_report_copies(custody, legacy)
    stage = Path(tempfile.mkdtemp(prefix=".vigil-export-", dir=destination))
    final = destination / f"affaire-{case_id[:8]}-{uuid4().hex}"
    published = False
    try:
        archive_path = stage / "affaire.tar.gz"
        hashes = {}
        missing = []
        with tarfile.open(archive_path, "w:gz") as archive:
            folder = tarfile.TarInfo("preuves/")
            folder.type = tarfile.DIRTYPE
            folder.mode = 0o700
            archive.addfile(folder)
            for record in evidence:
                source = evidence_copy_path(state, case_id, record["id"])
                try:
                    source.lstat()
                except FileNotFoundError:
                    missing.append(record["path"])
                    record.update(archive_path=None, copy_status="missing")
                    continue
                name = f"preuves/{record['id']}/contenu"
                digest = archive_file(archive, source, name)
                if digest != record["sha256"]:
                    raise ValueError(f"evidence copy failed integrity check: {record['path']}")
                hashes[name] = digest
                record.update(archive_path=name, copy_status="included")
            for root, prefix, exclude in ((custody, "resultats", ("preuves",)), (legacy, "projet-v1", ())):
                if root is None:
                    continue
                if not root.is_dir() and prefix == "projet-v1":
                    raise ValueError(f"imported case directory is unavailable: {root}")
                for source in case_files(root, exclude=exclude):
                    name = f"{prefix}/{source.relative_to(root).as_posix()}"
                    hashes[name] = archive_file(archive, source, name)
            metadata = json.dumps({
                "schema_version": 2, "coverage": "partial" if missing else "complete",
                "missing_evidence_count": len(missing), "exported_at": utc_now(), "operator": operator,
                "case": case, "evidence": evidence, "audit": events,
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
        (stage / "affaire.tar.gz.sha256").write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
        with database(state) as connection:
            audit(connection, operator, case_id, "case.export.success", {
                "sha256": digest, "archive": str(final), "missing_evidence_count": len(missing),
            })
            stage.rename(final)
            published = True
    except BaseException:
        shutil.rmtree(final if published else stage)
        with database(state) as connection:
            if not connection.execute(
                "SELECT 1 FROM deleted_cases WHERE case_id = ?", (case_id,)
            ).fetchone():
                audit(connection, operator, case_id, "case.export.error", {})
        raise
    return CaseExport(final, tuple(missing))
