"""Export one case as a tarball with internal and external SHA-256 manifests."""
import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path
from uuid import uuid4

from .history import case_events
from .storage import audit, database, evidence_copy_path, file_identity, utc_now


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
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            raise ValueError("unknown case ID")
        case = dict(row)
        evidence = [dict(row) for row in connection.execute(
            "SELECT * FROM evidence WHERE case_id = ? ORDER BY id", (case_id,))]
        legacy = Path(case["legacy_path"]) if case["legacy_path"] else None
        if destination.is_relative_to(custody.resolve()) or (
                legacy and destination.is_relative_to(legacy.resolve())):
            raise ValueError("export destination must be outside the case directories")
        audit(connection, operator, case_id, "case.export.start", {})
        events = case_events(connection, case_id, limit=None)

    stage = Path(tempfile.mkdtemp(prefix=".vigil-export-", dir=destination))
    final = destination / f"affaire-{case_id[:8]}-{uuid4().hex}"
    try:
        archive_path = stage / "affaire.tar.gz"
        hashes = {}
        with tarfile.open(archive_path, "w:gz") as archive:
            folder = tarfile.TarInfo("preuves/")
            folder.type = tarfile.DIRTYPE
            folder.mode = 0o700
            archive.addfile(folder)
            for record in evidence:
                source = evidence_copy_path(state, case_id, record["id"])
                if not source.is_file():
                    raise ValueError(f"evidence copy missing, re-add the original: {record['path']}")
                name = f"preuves/{record['id']}/contenu"
                digest = archive_file(archive, source, name)
                if digest != record["sha256"]:
                    raise ValueError(f"evidence copy failed integrity check: {record['path']}")
                hashes[name] = digest
                record["archive_path"] = name
            for root, prefix, exclude in ((custody, "resultats", ("preuves",)), (legacy, "projet-v1", ())):
                if root is None:
                    continue
                if not root.is_dir() and prefix == "projet-v1":
                    raise ValueError(f"imported case directory is unavailable: {root}")
                for source in case_files(root, exclude=exclude):
                    name = f"{prefix}/{source.relative_to(root).as_posix()}"
                    hashes[name] = archive_file(archive, source, name)
            metadata = json.dumps({
                "schema_version": 1, "exported_at": utc_now(), "operator": operator,
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
        stage.rename(final)
    except BaseException:
        shutil.rmtree(stage)
        with database(state) as connection:
            audit(connection, operator, case_id, "case.export.error", {})
        raise
    with database(state) as connection:
        audit(connection, operator, case_id, "case.export.success", {"sha256": digest, "archive": str(final)})
    return final
