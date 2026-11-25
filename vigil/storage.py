"""Local case metadata and read-only integrity verification."""
import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
import unicodedata
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .inspection import investigation_mounts, list_evidence_directory, open_evidence_path

ANTIVIRUS_CASE_NAME = "Scan antivirus"
SCHEMA_VERSION = 4
APPLICATION_ID = 0x5649474C
DELETED_CASES_DDL = """CREATE TABLE deleted_cases (
    case_id TEXT PRIMARY KEY REFERENCES cases(id), deleted_at TEXT NOT NULL
)"""
CASE_DIRECTORIES_DDL = """CREATE TABLE case_directories (
    case_id TEXT PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
)"""
CASE_DETAILS_DDL = """CREATE TABLE case_details (
    case_id TEXT PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    reference TEXT NOT NULL, description TEXT NOT NULL
)"""
SCHEMA = (
    "CREATE TABLE operators (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)",
    """CREATE TABLE cases (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, legacy_path TEXT UNIQUE,
        legacy_info TEXT, created_at TEXT NOT NULL
    )""",
    DELETED_CASES_DDL,
    CASE_DIRECTORIES_DDL,
    CASE_DETAILS_DDL,
    """CREATE TABLE evidence (
        id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
        path TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL
    )""",
    """CREATE TABLE audit (
        sequence INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
        operator_id TEXT NOT NULL REFERENCES operators(id),
        case_id TEXT NOT NULL REFERENCES cases(id), action TEXT NOT NULL,
        details TEXT NOT NULL
    )""",
)


def default_database():
    site_state = os.environ.get("VIGIL_STATE_DIR")
    if site_state and Path(site_state).is_absolute():
        return Path(site_state) / "cases.sqlite"
    if Path(__file__).resolve().parents[1] == Path("/opt/vigil"):
        return Path("/opt/vigil/data/state/cases.sqlite")
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root and Path(root).is_absolute() else Path.home() / ".local/state"
    return base / "vigil" / "cases.sqlite"


def utc_now():
    return datetime.now(UTC).isoformat()


@contextmanager
def database(path):
    if path.resolve().is_relative_to(Path("/investigation").resolve()):
        raise ValueError("database must be outside /investigation")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            app_id = connection.execute("PRAGMA application_id").fetchone()[0]
            if version == app_id == 0 and not connection.execute(
                "SELECT 1 FROM sqlite_schema LIMIT 1"
            ).fetchone():
                for statement in SCHEMA:
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif app_id == APPLICATION_ID and version in (1, 2, 3):
                if version == 1:
                    connection.execute(DELETED_CASES_DDL)
                if version < 3:
                    connection.execute(CASE_DIRECTORIES_DDL)
                    for case_id, name in connection.execute("SELECT id, name FROM cases ORDER BY created_at, id"):
                        assign_case_directory(connection, case_id, name)
                connection.execute(CASE_DETAILS_DDL)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif app_id != APPLICATION_ID or version != SCHEMA_VERSION:
                raise ValueError("unsupported Vigil database or schema version")
            if version != SCHEMA_VERSION:
                # Persist directory assignments before a caller can rename a legacy folder.
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
            yield connection
    finally:
        connection.close()


def register_operator(connection, name):
    if not name.strip():
        raise ValueError("operator name required")
    connection.execute(
        "INSERT INTO operators VALUES (?, ?) ON CONFLICT(name) DO NOTHING",
        (uuid4().hex, name),
    )
    return connection.execute("SELECT id FROM operators WHERE name = ?", (name,)).fetchone()[0]


def list_operators(connection):
    return list(connection.execute("SELECT id, name FROM operators ORDER BY name COLLATE NOCASE, id"))


def require_active_case(connection, case_id):
    row = connection.execute(
        "SELECT * FROM cases WHERE id = ? AND id NOT IN (SELECT case_id FROM deleted_cases)",
        (case_id,),
    ).fetchone()
    if row is None:
        raise ValueError("unknown or deleted case")
    return row


def delete_case(connection, case_id, operator):
    case = require_active_case(connection, case_id)
    if case["name"] == ANTIVIRUS_CASE_NAME:
        raise ValueError("the antivirus case cannot be deleted")
    audit(connection, operator, case_id, "case.delete", {"name": case["name"]})
    connection.execute("INSERT INTO deleted_cases VALUES (?, ?)", (case_id, utc_now()))


def audit(connection, operator, case_id, action, details):
    require_active_case(connection, case_id)
    operator_id = register_operator(connection, operator)
    connection.execute(
        """INSERT INTO audit(timestamp, operator_id, case_id, action, details)
           VALUES (?, ?, ?, ?, ?)""",
        (utc_now(), operator_id, case_id, action, json.dumps(details)),
    )


def assign_case_directory(connection, case_id, name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")[:100] or "Affaire"
    # A legacy directory name is reserved even when no directory currently exists.
    if re.fullmatch(r"[0-9a-fA-F]{32}", base):
        base = f"Affaire_{base}"
    database_file = connection.execute("PRAGMA database_list").fetchone()[2]
    root = Path(database_file).parent / "legacy-custody"
    candidate = base
    suffix = 2
    while (os.path.lexists(root / candidate)
           or connection.execute("SELECT 1 FROM case_directories WHERE name = ?", (candidate,)).fetchone()):
        candidate = f"{base}_{suffix}"
        suffix += 1
    connection.execute("INSERT INTO case_directories VALUES (?, ?)", (case_id, candidate))


def create_case(connection, name, operator, legacy_path=None, legacy_info=None, *, reference="", description=""):
    if not name.strip():
        raise ValueError("case name required")
    case_id = uuid4().hex
    result = connection.execute(
        """INSERT INTO cases VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(legacy_path) DO NOTHING""",
        (case_id, name, legacy_path, legacy_info, utc_now()),
    )
    if result.rowcount == 0:
        existing = connection.execute(
            "SELECT id FROM cases WHERE legacy_path = ?", (legacy_path,)
        ).fetchone()[0]
        require_active_case(connection, existing)
        return existing
    assign_case_directory(connection, case_id, name)
    if reference or description:
        connection.execute("INSERT INTO case_details VALUES (?, ?, ?)", (case_id, reference, description))
    audit(connection, operator, case_id, "case.import" if legacy_path else "case.create",
          {"legacy_path": legacy_path})
    return case_id


def case_manager_rows(state):
    """Read case summaries without opening evidence, reports or census databases."""
    with database(state) as connection:
        return [dict(row) for row in connection.execute("""
            WITH activity AS (
                SELECT case_id, max(timestamp) AS latest,
                       min(CASE WHEN action IN ('case.create', 'case.import') THEN sequence END) AS creation_event
                FROM audit GROUP BY case_id
            ), evidence_counts AS (
                SELECT case_id, count(*) AS total FROM evidence GROUP BY case_id
            )
            SELECT c.id, c.name, c.created_at, d.reference, d.description,
                   a.latest, n.name AS directory,
                   coalesce(e.total, 0) AS evidence_count, o.name AS operator
            FROM cases c JOIN case_directories n ON n.case_id = c.id
            LEFT JOIN case_details d ON d.case_id = c.id
            LEFT JOIN activity a ON a.case_id = c.id
            LEFT JOIN audit v ON v.sequence = a.creation_event
            LEFT JOIN operators o ON o.id = v.operator_id
            LEFT JOIN evidence_counts e ON e.case_id = c.id
            WHERE c.name <> ? AND c.id NOT IN (SELECT case_id FROM deleted_cases)
            """, (ANTIVIRUS_CASE_NAME,))]


def case_manager_artifacts(state, case_id, name):
    """Read published case metadata without scanning a device or modifying the case."""
    if not re.fullmatch(r"[0-9a-f]{32}", case_id) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("invalid case directory")
    root = state.parent / "legacy-custody"
    planned, previous = root / name, root / case_id
    directory = previous if previous.exists() and not planned.exists() else planned
    if directory.resolve() != directory.absolute() or directory.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid case directory")
    metadata = {"path": str(directory), "inventory": None, "analyses": None, "reports": None}
    if not directory.is_dir():
        return metadata

    def local(path):
        return path.resolve() == path.absolute()

    analyses = directory / "analyses"
    runs = sorted(path for path in analyses.iterdir() if local(path) and path.is_dir()) if (
        local(analyses) and analyses.is_dir()
    ) else []
    finished = []
    for run in runs:
        status = run / "exit-code"
        if local(status) and status.is_file():
            with status.open("rb") as stream:
                finished.append(stream.read(16).strip())
    metadata["analyses"] = finished.count(b"0")
    reports = directory / "rapports"
    if local(reports) and reports.is_dir():
        metadata["reports"] = sum(
            not (Path(folder) / filename).is_symlink() and (Path(folder) / filename).is_file()
            for folder, _, files in os.walk(reports) for filename in files if filename.endswith(".pdf")
        )
    candidates = [
        index for folder in [directory, *(run for run in runs if run.name.startswith("vigil.census-"))]
        for index in folder.glob("census_*.sqlite") if local(index) and index.is_file()
    ]
    if candidates:
        index = max(candidates, key=lambda path: path.stat().st_mtime_ns)
        try:
            connection = sqlite3.connect(index.as_uri() + "?mode=ro", uri=True, timeout=0.2)
            try:
                row = connection.execute("SELECT total_files FROM inventory_meta ORDER BY id DESC LIMIT 1").fetchone()
                metadata["inventory"] = row[0] if row else None
            finally:
                connection.close()
        except sqlite3.Error:
            pass
    return metadata


def find_antivirus_case(connection):
    existing = connection.execute(
        "SELECT id FROM cases WHERE name = ? LIMIT 2", (ANTIVIRUS_CASE_NAME,),
    ).fetchall()
    if len(existing) > 1:
        raise ValueError("more than one case named Scan antivirus")
    return existing[0]["id"] if existing else None


def antivirus_case(connection, operator):
    return find_antivirus_case(connection) or create_case(connection, ANTIVIRUS_CASE_NAME, operator)


def read_legacy_project(path):
    with (path / "info.json").open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("legacy project metadata exceeds 1 MiB")
    raw = data.decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("name", path.name), str):
        raise ValueError("invalid legacy project metadata")
    return parsed.get("name", path.name), raw


def fingerprint(path, *, mount=None, copy_to=None):
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if mount is None:
        return fingerprint_descriptor(os.open(path, flags), lambda: path.stat(follow_symlinks=False), copy_to)
    with open_evidence_path(path, *mount) as source:
        descriptor = os.open(f"/proc/self/fd/{source}", os.O_RDONLY | os.O_CLOEXEC)
        return fingerprint_descriptor(descriptor, lambda: mounted_file_stat(path, mount), copy_to)


def mounted_file_stat(path, mount):
    with open_evidence_path(path, *mount) as descriptor:
        return os.fstat(descriptor)


def fingerprint_descriptor(descriptor, current_stat, copy_to):
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("evidence must be a regular file")
        if copy_to is None:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        else:
            sha = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                copy_to.write(chunk)
                sha.update(chunk)
            digest = sha.hexdigest()
        after = os.fstat(stream.fileno())
        if not (file_identity(before) == file_identity(after) == file_identity(current_stat())):
            raise ValueError("evidence changed during hashing")
    return before.st_size, digest


def file_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def add_evidence(connection, case_id, path, size, digest, operator, evidence_id):
    connection.execute(
        "INSERT INTO evidence VALUES (?, ?, ?, ?, ?)",
        (evidence_id, case_id, str(path), size, digest),
    )
    audit(connection, operator, case_id, "evidence.add",
          {"evidence_id": evidence_id, "sha256": digest})
    return evidence_id


def case_storage_directory(state, case_id, *, connection=None):
    if not re.fullmatch(r"[0-9a-f]{32}", case_id):
        raise ValueError("invalid case ID")
    if connection is None:
        with database(state) as connection:
            return case_storage_directory(state, case_id, connection=connection)
    row = connection.execute("SELECT name FROM case_directories WHERE case_id = ?", (case_id,)).fetchone()
    if row is None:
        raise ValueError("unknown case")
    name = row["name"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("invalid case directory name")
    root = state.parent / "legacy-custody"
    path, previous = root / name, root / case_id
    for directory in (path, previous):
        resolved = directory.resolve()
        if resolved != directory.absolute() or resolved.is_relative_to("/investigation"):
            raise ValueError("invalid case storage directory")
        if directory.exists() and not directory.is_dir():
            raise ValueError("case storage path is not a directory")
    if previous.is_dir():
        if path.exists():
            raise ValueError(f"conflicting case directories: {previous} and {path}")
        previous.rename(path)
    return path


def evidence_copy_path(state, case_id, evidence_id, *, connection=None):
    if len(evidence_id) != 32 or any(char not in "0123456789abcdef" for char in evidence_id):
        raise ValueError("invalid evidence ID")
    path = case_storage_directory(state, case_id, connection=connection) / "preuves" / evidence_id
    if path.resolve() != path.absolute():
        raise ValueError("invalid evidence storage directory")
    return path / "contenu"


def find_evidence_copy(state, case_id, original, digest=None):
    """Find the local copy for this exact recorded version of a case file."""
    with database(state) as connection:
        require_active_case(connection, case_id)
        query = "SELECT id FROM evidence WHERE case_id = ? AND path = ?"
        params = (case_id, str(original))
        if digest is not None:
            query += " AND sha256 = ?"
            params += (digest,)
        ids = connection.execute(query + " ORDER BY rowid DESC", params).fetchall()
    for row in ids:
        copy = evidence_copy_path(state, case_id, row["id"])
        try:
            mode = copy.lstat().st_mode
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("invalid local evidence copy")
        return copy
    return None


def register_file(state, case_id, path, operator, *, mount=None):
    path = path.absolute()
    if state.exists() and state.samefile(path):
        raise ValueError("database and evidence must be separate files")
    if mount is None and (path.is_relative_to("/investigation") or path.resolve().is_relative_to("/investigation")):
        roots = investigation_mounts()
        root = max((root for root in roots if path.is_relative_to(root)), key=len, default=None)
        if root is None:
            raise ValueError("no verified read-only mount covers this evidence path")
        mount = root, roots[root]

    with database(state) as connection:
        require_active_case(connection, case_id)
        existing = connection.execute(
            "SELECT id, size, sha256 FROM evidence WHERE case_id = ? AND path = ? ORDER BY rowid",
            (case_id, str(path)),
        ).fetchall()
    for row in existing:
        if evidence_copy_path(state, case_id, row["id"]).exists():
            return {**dict(row), "existing": True}

    new_id = uuid4().hex
    stage_dir = evidence_copy_path(state, case_id, new_id).parent.parent
    stage_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    published = []
    try:
        with tempfile.TemporaryDirectory(dir=stage_dir) as staging:
            with tempfile.NamedTemporaryFile(dir=staging, delete=False) as stream:
                staged = Path(stream.name)
                size, digest = fingerprint(path, mount=mount, copy_to=stream)
                stream.flush()
                os.fchmod(stream.fileno(), 0o400)
                if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) != 0o400:
                    raise ValueError("evidence storage does not enforce mode 0400")
                os.fsync(stream.fileno())
            # Close the writable handle before publishing the protected copy.
            with database(state) as connection:
                require_active_case(connection, case_id)
                # Another registration may have completed while this file was copied.
                records = connection.execute(
                    "SELECT id, size, sha256 FROM evidence WHERE case_id = ? AND path = ? ORDER BY rowid",
                    (case_id, str(path)),
                ).fetchall()
                if records:
                    matching = [row for row in records if (row["size"], row["sha256"]) == (size, digest)]
                    if not matching:
                        raise ValueError("source no longer matches the recorded evidence fingerprint")
                    for row in matching:
                        target = evidence_copy_path(state, case_id, row["id"], connection=connection)
                        if not target.exists():
                            target.parent.mkdir(mode=0o700, exist_ok=True)
                            os.link(staged, target, follow_symlinks=False)
                            published.append(target)
                            audit(connection, operator, case_id, "evidence.copy",
                                  {"evidence_id": row["id"], "sha256": digest})
                    evidence_id = matching[0]["id"]
                else:
                    evidence_id = new_id
                    target = evidence_copy_path(state, case_id, evidence_id, connection=connection)
                    target.parent.mkdir(mode=0o700)
                    os.link(staged, target, follow_symlinks=False)
                    published.append(target)
                    add_evidence(connection, case_id, path, size, digest, operator, evidence_id)
    except BaseException:
        for target in published:
            target.unlink()
        raise
    return {"id": evidence_id, "size": size, "sha256": digest, "existing": bool(records)}


def delete_evidence(state, case_id, evidence_id, operator):
    source = evidence_copy_path(state, case_id, evidence_id)
    staged = None
    try:
        with database(state) as connection:
            require_active_case(connection, case_id)
            record = connection.execute(
                "SELECT path, sha256 FROM evidence WHERE id = ? AND case_id = ?",
                (evidence_id, case_id),
            ).fetchone()
            if record is None:
                raise ValueError("unknown evidence in this case")
            try:
                info = source.lstat()
            except FileNotFoundError:
                info = None
            if info is not None:
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("invalid local evidence copy")
                temporary = source.with_name(f".removed-{uuid4().hex}")
                source.rename(temporary)
                staged = temporary
            connection.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
            audit(connection, operator, case_id, "evidence.delete", {
                "evidence_id": evidence_id, "path": record["path"],
                "sha256": record["sha256"], "had_local_copy": staged is not None,
            })
    except BaseException:
        if staged is not None:
            staged.rename(source)
        raise
    if staged is not None:
        staged.unlink()
        try:
            source.parent.rmdir()
        except OSError:
            pass


def verify_file(state, evidence_id, operator, *, use_copy=False):
    with database(state) as connection:
        record = connection.execute(
            "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
    if record is None:
        raise ValueError("unknown evidence ID")
    stored = evidence_copy_path(state, record["case_id"], evidence_id)
    path = stored if use_copy and stored.exists() else Path(record["path"])
    size, digest = fingerprint(path)
    result = {
        "id": evidence_id, "expected_sha256": record["sha256"], "sha256": digest,
        "matches": size == record["size"] and digest == record["sha256"],
    }
    with database(state) as connection:
        audit(connection, operator, record["case_id"], "evidence.verify", result)
    return result


def process_explorer_selection(state, case_id, operator, sources, *, register, use_saved_copy=False):
    pending = [(Path(path), tuple(mount) if mount else None, directory)
               for path, mount, directory in reversed(sources)]
    seen = set()
    results, errors = [], []
    while pending:
        path, mount, directory = pending.pop()
        key = path, mount
        if key in seen:
            continue
        seen.add(key)
        try:
            if directory:
                children = list_evidence_directory(path, *mount)
                pending.extend((path / name, mount, is_dir) for name, is_dir in reversed(children))
                continue
            source = path
            if not register and use_saved_copy and mount is None:
                source = find_evidence_copy(state, case_id, path) or path
            if source == path and path.is_relative_to("/investigation") and mount is None:
                raise ValueError("no local copy or verified read-only mount for this evidence path")
            if state.exists() and state.samefile(source):
                raise ValueError("database and evidence must be separate files")
            if register:
                result = register_file(state, case_id, path, operator, mount=mount)
                results.append((str(path), result["sha256"], "existing" if result["existing"] else "added", []))
                continue
            size, digest = fingerprint(source, mount=mount)
        except (OSError, ValueError) as error:
            errors.append((str(path), str(error)))
            continue
        with database(state) as connection:
            records = connection.execute(
                "SELECT id, size, sha256 FROM evidence WHERE case_id = ? AND path = ?",
                (case_id, str(path)),
            ).fetchall()
            if not records:
                audit(connection, operator, case_id, "evidence.hash",
                      {"path": str(path), "sha256": digest, "size": size})
            for record in records:
                audit(connection, operator, case_id, "evidence.verify", {
                    "id": record["id"], "expected_sha256": record["sha256"], "sha256": digest,
                    "matches": size == record["size"] and digest == record["sha256"],
                })
        expected = [record["sha256"] for record in records]
        status = (
            "calculated" if not records else
            "matches" if all(size == row["size"] and digest == row["sha256"] for row in records)
            else "changed"
        )
        results.append((str(path), digest, status, expected))
    return results, errors
