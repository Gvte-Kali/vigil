"""Validate and restore portable Vigil case archives without Qt."""
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tarfile
import tempfile
import zlib
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from . import storage

CHUNK = 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}")
ID = re.compile(r"[0-9a-f]{32}")
MANIFESTS = {"affaire.json", "SHA256SUMS"}


@dataclass(frozen=True)
class ArchiveLimits:
    entries: int = 200_000
    metadata: int = 32 * CHUNK
    expanded: int = 128 * 1024**3
    path_bytes: int = 1024


@dataclass(frozen=True)
class ArchivePreview:
    sha256: str
    schema_version: int
    source_id: str
    name: str
    exported_at: str
    coverage: str
    evidence_count: int
    missing: int
    results: int
    reports: int
    legacy: bool
    bytes: int
    sidecar_verified: bool


class ArchiveError(ValueError):
    def __init__(self, status, message):
        super().__init__(f"{status}: {message}")
        self.status = status


def require(condition, message, status="corrupt"):
    if not condition:
        raise ArchiveError(status, message)


def canonical_name(name, limits):
    parts = name.split("/")
    require(len(name.encode("utf-8", "surrogateescape")) <= limits.path_bytes
            and all(part not in {"", ".", ".."} and "\0" not in part
                    and len(os.fsencode(part)) <= 255 for part in parts),
            "unsafe or incompatible member path", "dangerous")
    return name


def checksum_lines(raw, limits):
    hashes = {}
    escaped = {"n": "\n", "r": "\r", "\\": "\\"}
    for line in raw.decode("utf-8", "surrogateescape").split("\n"):
        if not line:
            continue
        match = re.fullmatch(r"(\\?)([0-9a-f]{64})  (.+)", line)
        require(match is not None, "invalid SHA256SUMS line")
        marker, digest, name = match.groups()
        if marker:
            require(not re.search(r"\\(?![nr\\])", name), "invalid checksum path escape")
            name = re.sub(r"\\([nr\\])", lambda token: escaped[token[1]], name)
        canonical_name(name, limits)
        require(name not in hashes, "duplicate checksum path", "dangerous")
        hashes[name] = digest
    return hashes


def valid_id(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def valid_text(value, maximum=4096):
    return type(value) is str and 0 < len(value) <= maximum and "\0" not in value


def valid_date(value):
    if not valid_text(value, 100):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_metadata(raw, files):
    try:
        data = json.loads(raw, object_pairs_hook=json_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ArchiveError("corrupt", "invalid affaire.json") from error
    require(isinstance(data, dict), "manifest must be an object")
    require(type(data.get("schema_version")) is int and data["schema_version"] in (2, 3),
            "unsupported case archive schema", "incompatible")
    case = data.get("case")
    require(isinstance(case, dict) and valid_id(case.get("id"))
            and valid_text(case.get("name"), 512) and case["name"].isprintable()
            and valid_date(case.get("created_at")) and valid_date(data.get("exported_at"))
            and valid_text(data.get("operator"), 512), "invalid case metadata")
    for field, length in (("reference", 120), ("description", 4000), ("legacy_path", 16384),
                          ("legacy_info", CHUNK)):
        value = case.get(field)
        require(value is None or (isinstance(value, str) and len(value) <= length and "\0" not in value),
                f"invalid case {field}")
    evidence, events = data.get("evidence"), data.get("audit")
    require(isinstance(evidence, list) and isinstance(events, list), "missing evidence or audit list")
    used = set()
    included = set()
    for row in evidence:
        require(isinstance(row, dict) and valid_id(row.get("id"))
                and row.get("id") not in used and row.get("case_id") == case["id"]
                and valid_text(row.get("path"), 16384) and type(row.get("size")) is int
                and 0 <= row["size"] < 2**63 and HEX.fullmatch(str(row.get("sha256", ""))),
                "invalid or duplicated evidence metadata")
        used.add(row["id"])
        member = f"preuves/{row['id']}/contenu"
        if row.get("copy_status") == "included":
            require(row.get("archive_path") == member and files.get(member) == (row["sha256"], row["size"]),
                    "evidence content does not match its reference")
            included.add(member)
        else:
            require(row.get("copy_status") == "missing" and row.get("archive_path") is None,
                    "invalid missing evidence status")
    require(included == {name for name in files if name.startswith("preuves/")}, "undeclared evidence content")
    missing = len(evidence) - len(included)
    require(type(data.get("missing_evidence_count")) is int and data["missing_evidence_count"] == missing
            and data.get("coverage") == ("partial" if missing else "complete"), "inconsistent archive coverage")
    sequence = 0
    for event in events:
        require(isinstance(event, dict) and type(event.get("sequence")) is int
                and sequence < event["sequence"] < 2**63 and valid_date(event.get("timestamp"))
                and valid_text(event.get("operator"), 512) and valid_text(event.get("action"), 512)
                and valid_text(event.get("details"), 4 * CHUNK), "invalid audit event")
        sequence = event["sequence"]
        provenance = event.get("provenance")
        if provenance is not None:
            require(isinstance(provenance, dict) and valid_text(provenance.get("operator"), 512)
                    and valid_id(provenance.get("case_id"))
                    and HEX.fullmatch(str(provenance.get("archive_sha256", "")))
                    and type(provenance.get("sequence")) is int and 0 < provenance["sequence"] < 2**63,
                    "invalid historical event provenance")
    if data["schema_version"] == 3:
        expected = {name: size for name, (_, size) in files.items() if name != "affaire.json"}
        require(data.get("members") == expected and all(type(size) is int for size in data["members"].values())
                and data.get("audit_cutoff") == (sequence or None)
                and valid_text(data.get("vigil_version"), 80), "invalid version 3 snapshot metadata")
    return data, missing


class LimitedTarInfo(tarfile.TarInfo):
    @classmethod
    def frombuf(cls, buf, encoding, errors):
        info = super().frombuf(buf, encoding, errors)
        if info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
            require(info.type == tarfile.XHDTYPE and 0 <= info.size <= 64 * 1024,
                    "unsupported or excessive TAR metadata or special member", "dangerous")
        return info

    def reject_sparse(self, *_):
        raise ArchiveError("dangerous", "GNU sparse TAR entries are unsupported")

    _proc_gnusparse_00 = _proc_gnusparse_01 = _proc_gnusparse_10 = reject_sparse


def archive_path(path):
    path = Path(path).expanduser()
    if path.is_dir():
        path /= "affaire.tar.gz"
    if path.is_symlink() or not path.is_file():
        raise ArchiveError("incompatible", "choose a regular Vigil archive or its containing folder")
    return path.absolute()


@contextmanager
def open_regular(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    with os.fdopen(os.open(path, flags), "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "input is not a regular file", "dangerous")
        yield stream


def read_package(source, limits, stage=None):
    source = archive_path(source)
    sidecar = source.with_name(source.name + ".sha256")
    checked = False
    try:
        with open_regular(source) as stream:
            before = storage.file_identity(os.fstat(stream.fileno()))
            require(stream.read(2) == b"\x1f\x8b", "expected a gzip archive", "incompatible")
            stream.seek(0)
            require(before[2] <= limits.expanded + limits.metadata + 64 * CHUNK,
                    "compressed input exceeds the size budget", "incomplete")
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if os.path.lexists(sidecar):
                require(not sidecar.is_symlink() and sidecar.is_file(), "invalid external checksum file")
                with open_regular(sidecar) as checksum:
                    line = checksum.read(1025)
                match = re.fullmatch(rb"([a-fA-F0-9]{64}) [ *][^\r\n]+\r?\n?", line)
                require(len(line) <= 1024 and match is not None
                        and match[1].decode().lower() == digest, "external archive SHA-256 mismatch")
                checked = True
            stream.seek(0)
            with gzip.GzipFile(fileobj=stream) as decoded:
                data, missing, files, total = inspect_tar(decoded, limits, stage)
            require(storage.file_identity(os.fstat(stream.fileno())) == before, "archive changed during verification")
            stream.seek(0)
            require(hashlib.file_digest(stream, "sha256").hexdigest() == digest,
                    "archive bytes changed during verification")
    except (EOFError, tarfile.TarError, gzip.BadGzipFile, zlib.error, UnicodeError, RecursionError) as error:
        raise ArchiveError("corrupt", "invalid or truncated archive") from error
    previews = ArchivePreview(
        digest, data["schema_version"], data["case"]["id"], data["case"]["name"],
        data["exported_at"], data["coverage"], len(data["evidence"]), missing,
        sum(name.startswith("resultats/") for name in files),
        sum(name.endswith(".pdf") and name.startswith(("resultats/", "projet-v1/")) for name in files),
        any(name.startswith("projet-v1/") for name in files), total, checked,
    )
    return previews, data


class BudgetReader:
    def __init__(self, stream, remaining):
        self.stream = stream
        self.remaining = remaining

    def read(self, size):
        data = self.stream.read(min(size, self.remaining + 1))
        self.remaining -= len(data)
        require(self.remaining >= 0, "decompression budget exceeded", "incomplete")
        return data


def inspect_tar(decoded, limits, stage):
    files, documents, seen = {}, {}, set()
    total = 0
    with tarfile.open(fileobj=BudgetReader(decoded, limits.expanded + limits.entries * 4096 + 64 * CHUNK),
                      mode="r|", tarinfo=LimitedTarInfo) as archive:
        for member in archive:
            name = canonical_name(member.name, limits)
            require(math.isfinite(member.mtime) and -62135596800 <= member.mtime <= 253402300799,
                    "invalid member timestamp")
            require(name not in seen, "duplicate TAR entry", "dangerous")
            seen.add(name)
            require(len(seen) <= limits.entries, "too many entries", "incomplete")
            if member.isdir():
                require(name == "preuves" and member.size == 0, "unsupported directory entry", "dangerous")
                continue
            require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE) and not member.issparse(),
                    "unsupported TAR member", "dangerous")
            require(name in MANIFESTS or re.fullmatch(r"preuves/[0-9a-f]{32}/contenu", name)
                    or (name.startswith(("resultats/", "projet-v1/"))
                        and name.split("/")[1] not in {"preuves", "projet-v1", ".vigil-import"}),
                    "unexpected archive member", "dangerous")
            require(0 <= member.size <= limits.expanded - total, "expanded byte limit exceeded", "incomplete")
            total += member.size
            reader = archive.extractfile(member)
            if name in MANIFESTS:
                require(member.size <= limits.metadata, "manifest exceeds byte limit", "incomplete")
                documents[name] = reader.read()
                if name == "affaire.json":
                    files[name] = hashlib.sha256(documents[name]).hexdigest(), member.size
                continue
            target = None
            if stage is not None:
                require(shutil.disk_usage(stage).free >= member.size, "insufficient staging space", "incomplete")
                relative = name.removeprefix("resultats/")
                destination = stage / relative
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                target = destination.open("xb")
            digest = hashlib.sha256()
            read = 0
            try:
                while block := reader.read(CHUNK):
                    digest.update(block)
                    read += len(block)
                    if target:
                        target.write(block)
                if target:
                    os.fchmod(target.fileno(), 0o400 if name.startswith("preuves/") else 0o600)
                    target.flush()
                    os.utime(destination, (member.mtime, member.mtime))
                    os.fsync(target.fileno())
            finally:
                if target:
                    target.close()
            require(read == member.size, "member ended early")
            files[name] = digest.hexdigest(), read
        # tarfile stops at the first end marker. Validate remaining padding and gzip CRC.
        padding = archive.fileobj.read(512)
        require(len(padding) == 512 and not padding.strip(b"\0"), "missing TAR end marker")
        trailing = 0
        while block := archive.fileobj.read(CHUNK):
            trailing += len(block)
            require(trailing <= 64 * CHUNK and not block.strip(b"\0"), "invalid TAR trailing data")
    require(documents.keys() == MANIFESTS, "missing Vigil archive manifests", "incompatible")
    require(checksum_lines(documents["SHA256SUMS"], limits) == {key: value[0] for key, value in files.items()},
            "archive member set or SHA-256 mismatch")
    for name in files:
        parents = name.split("/")[:-1]
        require(not any("/".join(parents[:end]) in files for end in range(1, len(parents) + 1)),
                "member path collides with a file", "dangerous")
    data, missing = read_metadata(documents["affaire.json"], files)
    return data, missing, files, total


def verify_archive(source, *, limits=ArchiveLimits()):
    return read_package(source, limits)[0]


def import_archive(state, source, operator, *, expected_sha256=None, limits=ArchiveLimits()):
    """Publish a verified copy and its database rows, with compensating cleanup."""
    require(valid_text(operator, 120) and operator.isprintable(), "invalid importing operator")
    state = Path(state).absolute()
    root = state.parent / "legacy-custody"
    resolved = root.resolve()
    require(resolved == root and not resolved.is_relative_to("/investigation"),
            "unsafe staging directory", "dangerous")
    require(not state.resolve().is_relative_to("/investigation"), "unsafe database path", "dangerous")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".vigil-import-", dir=root))
    published = None
    committed = False
    try:
        preview, data = read_package(source, limits, stage)
        require(expected_sha256 is None or expected_sha256 == preview.sha256,
                "archive changed after preview")
        original = data["case"]
        for evidence in data["evidence"]:
            if evidence["copy_status"] == "included":
                with open_regular(stage / evidence["archive_path"]) as copy:
                    require(hashlib.file_digest(copy, "sha256").hexdigest() == evidence["sha256"],
                            "restored evidence SHA-256 mismatch")
        for folder, _, _ in os.walk(stage, topdown=False):
            with directory_descriptor(folder) as descriptor:
                os.fsync(descriptor)
        with storage.database(state) as connection:
            existing = connection.execute(
                """SELECT case_archives.case_id, deleted_cases.case_id IS NOT NULL AS deleted
                   FROM case_archives LEFT JOIN deleted_cases USING (case_id) WHERE sha256 = ?""",
                (preview.sha256,),
            ).fetchone()
            if existing:
                require(not existing["deleted"], "this archive was previously imported and removed", "conflict")
                directory = storage.case_storage_directory(state, existing["case_id"], connection=connection)
                require(directory.is_dir(), "previously imported case directory is missing", "conflict")
                return {**asdict(preview), "case_id": existing["case_id"], "reused": True}
            case_id = original["id"]
            if connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() or (
                os.path.lexists(root / case_id)
            ):
                case_id = uuid4().hex
            # Keep the dedicated local antivirus workspace separate.
            name = original["name"]
            if name.casefold() == storage.ANTIVIRUS_CASE_NAME.casefold():
                name += " (archive)"
            # Do not simulate a creation event for archived activity.
            connection.execute(
                "INSERT INTO cases VALUES (?, ?, NULL, ?, ?)",
                (case_id, name, original.get("legacy_info"), original["created_at"]),
            )
            storage.assign_case_directory(connection, case_id, name)
            if original.get("reference") or original.get("description"):
                connection.execute("INSERT INTO case_details VALUES (?, ?, ?)", (
                    case_id, original.get("reference") or "", original.get("description") or "",
                ))

            evidence_map = restore_evidence(connection, stage, case_id, data["evidence"])
            operator_map = restore_history(connection, case_id, preview, data["audit"])
            receipt = {
                "format": preview.schema_version, "source_case_id": preview.source_id,
                "source_name": original["name"],
                "source_legacy_path": original.get("legacy_path"), "exported_at": preview.exported_at,
                "export_operator": data["operator"], "coverage": preview.coverage,
                "source_archive": data.get("source_archive"), "evidence_ids": evidence_map,
                "operator_ids": operator_map,
            }
            connection.execute("INSERT INTO case_archives VALUES (?, ?, ?)", (
                case_id, preview.sha256, json.dumps(receipt, ensure_ascii=True),
            ))
            storage.audit(connection, operator, case_id, "case.archive.import", {
                "sha256": preview.sha256, "source_case_id": preview.source_id, "restored_case_id": case_id,
                "validation": "verified", "coverage": preview.coverage, "missing": preview.missing,
            })
            final = storage.case_storage_directory(state, case_id, connection=connection)
            require(not os.path.lexists(final), "case folder already exists", "conflict")
            marker = stage / ".vigil-import"
            with marker.open("x", encoding="ascii") as stream:
                json.dump({"case_id": case_id, "sha256": preview.sha256}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            if (stage / "preuves").is_dir():
                with directory_descriptor(stage / "preuves") as descriptor:
                    os.fsync(descriptor)
            with directory_descriptor(stage) as descriptor:
                os.fsync(descriptor)
            stage.rename(final)
            published = final
            with directory_descriptor(root) as descriptor:
                os.fsync(descriptor)
        committed = True
        try:
            (published / ".vigil-import").unlink()
        except OSError:
            # A durable receipt makes the leftover marker safe to reconcile.
            pass
        return {**asdict(preview), "case_id": case_id, "reused": False}
    finally:
        if published is not None and not committed:
            shutil.rmtree(published, ignore_errors=True)
        shutil.rmtree(stage, ignore_errors=True)




@contextmanager
def directory_descriptor(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


def restore_evidence(connection, stage, case_id, rows):
    mapping = {}
    inbound = {row["id"] for row in rows}
    for row in rows:
        source = row["id"]
        target = source
        if connection.execute("SELECT 1 FROM evidence WHERE id = ?", (target,)).fetchone():
            target = uuid4().hex
            while target in inbound or connection.execute("SELECT 1 FROM evidence WHERE id = ?", (target,)).fetchone():
                target = uuid4().hex
            if row["copy_status"] == "included":
                (stage / "preuves" / source).rename(stage / "preuves" / target)
        if row["copy_status"] == "included":
            copy = stage / "preuves" / target / "contenu"
            info = copy.stat()
            require(stat.S_IMODE(info.st_mode) == 0o400 and info.st_size == row["size"],
                    "restored evidence metadata mismatch")
        connection.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)", (
            target, case_id, row["path"], row["size"], row["sha256"],
        ))
        mapping[source] = target
    return mapping


def restore_history(connection, case_id, preview, events):
    operators = {}
    for row in events:
        provenance = row.get("provenance") or {
            "case_id": preview.source_id, "archive_sha256": preview.sha256,
            "sequence": row["sequence"], "operator": row["operator"],
            "operator_id": row.get("operator_id"),
        }
        identity = json.dumps([provenance["case_id"], provenance["archive_sha256"],
                               provenance.get("operator_id") or provenance["operator"]], ensure_ascii=True)
        if identity not in operators:
            # Reserve a distinct local operator identity even if the display name is already used.
            operator_id = provenance.get("operator_id")
            if not valid_id(operator_id) or connection.execute(
                "SELECT 1 FROM operators WHERE id = ?", (operator_id,),
            ).fetchone():
                operator_id = uuid4().hex
            alias = f"{provenance['operator']} [archive {operator_id}]"
            connection.execute("INSERT INTO operators VALUES (?, ?)", (operator_id, alias))
            connection.execute("INSERT INTO archive_operators VALUES (?)", (operator_id,))
            operators[identity] = operator_id
        result = connection.execute(
            "INSERT INTO audit(timestamp, operator_id, case_id, action, details) VALUES (?, ?, ?, ?, ?)",
            (row["timestamp"], operators[identity], case_id, row["action"], row["details"]),
        )
        connection.execute("INSERT INTO archive_events VALUES (?, ?)", (
            result.lastrowid, json.dumps(provenance, ensure_ascii=True),
        ))
    return operators
