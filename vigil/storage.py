"""Local case metadata and read-only integrity verification."""
import hashlib
import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ANTIVIRUS_CASE_NAME = "Scan antivirus"
SCHEMA_VERSION = 1
APPLICATION_ID = 0x5649474C
SCHEMA = (
    "CREATE TABLE operators (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)",
    """CREATE TABLE cases (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, legacy_path TEXT UNIQUE,
        legacy_info TEXT, created_at TEXT NOT NULL
    )""",
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
            elif app_id != APPLICATION_ID or version != SCHEMA_VERSION:
                raise ValueError("unsupported Vigil database or schema version")
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


def audit(connection, operator, case_id, action, details):
    operator_id = register_operator(connection, operator)
    connection.execute(
        """INSERT INTO audit(timestamp, operator_id, case_id, action, details)
           VALUES (?, ?, ?, ?, ?)""",
        (utc_now(), operator_id, case_id, action, json.dumps(details)),
    )


def create_case(connection, name, operator, legacy_path=None, legacy_info=None):
    if not name.strip():
        raise ValueError("case name required")
    case_id = uuid4().hex
    result = connection.execute(
        """INSERT INTO cases VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(legacy_path) DO NOTHING""",
        (case_id, name, legacy_path, legacy_info, utc_now()),
    )
    if result.rowcount == 0:
        return connection.execute(
            "SELECT id FROM cases WHERE legacy_path = ?", (legacy_path,)
        ).fetchone()[0]
    audit(connection, operator, case_id, "case.import" if legacy_path else "case.create",
          {"legacy_path": legacy_path})
    return case_id


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


def fingerprint(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("evidence must be a regular file")
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)
        if not (
            file_identity(before) == file_identity(after) == file_identity(current)
        ):
            raise ValueError("evidence changed during hashing")
    return before.st_size, digest


def file_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def add_evidence(connection, case_id, path, size, digest, operator):
    evidence_id = uuid4().hex
    connection.execute(
        "INSERT INTO evidence VALUES (?, ?, ?, ?, ?)",
        (evidence_id, case_id, str(path), size, digest),
    )
    audit(connection, operator, case_id, "evidence.add",
          {"evidence_id": evidence_id, "sha256": digest})
    return evidence_id


def register_file(state, case_id, path, operator):
    path = path.absolute()
    if state.exists() and state.samefile(path):
        raise ValueError("database and evidence must be separate files")
    size, digest = fingerprint(path)
    with database(state) as connection:
        evidence_id = add_evidence(connection, case_id, path, size, digest, operator)
    return {"id": evidence_id, "size": size, "sha256": digest}


def verify_file(state, evidence_id, operator):
    with database(state) as connection:
        record = connection.execute(
            "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
    if record is None:
        raise ValueError("unknown evidence ID")
    size, digest = fingerprint(Path(record["path"]))
    result = {
        "id": evidence_id, "expected_sha256": record["sha256"], "sha256": digest,
        "matches": size == record["size"] and digest == record["sha256"],
    }
    with database(state) as connection:
        audit(connection, operator, record["case_id"], "evidence.verify", result)
    return result
