"""Publish a versioned JSON snapshot and its SHA-256 manifest."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from .history import case_events
from .storage import database, utc_now


def case_report(state, case_id):
    with database(state) as connection:
        case = connection.execute(
            "SELECT id, name, created_at FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        if case is None:
            raise ValueError("unknown case ID")
        evidence = connection.execute(
            "SELECT id, path, size, sha256 FROM evidence WHERE case_id = ? ORDER BY id",
            (case_id,),
        )
        snapshot = {
            "schema_version": 1,
            "created_at": utc_now(),
            "case": dict(case),
            "evidence": [dict(row) for row in evidence],
            "audit": case_events(connection, case_id, limit=None),
            "coverage": "registered_metadata_and_audit",
        }

    root = state.parent.resolve() / "reports"
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid report directory")
    stage = Path(tempfile.mkdtemp(prefix=".report-", dir=root))
    try:
        payload = stage / "case.json"
        encoded = (json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n").encode()
        payload.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        manifest = stage / "SHA256SUMS"
        manifest.write_text(f"{digest}  {payload.name}\n", encoding="ascii")
        with payload.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("report integrity verification failed")
        destination = root / f"case-{uuid4().hex}"
        stage.rename(destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)
