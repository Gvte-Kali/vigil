"""Publish a versioned JSON snapshot and its SHA-256 manifest."""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from .destination import writable_destination
from .history import case_events
from .report_copies import sync_report_copies
from .storage import case_storage_directory, database, require_active_case, utc_now


def case_report(state, case_id, destination=None):
    with database(state) as connection:
        require_active_case(connection, case_id)
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

    if destination is None:
        root = state.parent.resolve() / "reports"
        root.mkdir(mode=0o700, exist_ok=True)
        if root.is_symlink():
            raise ValueError("invalid report directory")
    else:
        root = destination
    root = writable_destination(root).path
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
        with database(state) as connection:
            require_active_case(connection, case_id)
            stage.rename(destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def case_pdf_reports(state, case_id, legacy_path=None):
    """List case-scoped PDFs without following symbolic links."""
    if not re.fullmatch(r"[0-9a-f]{32}", case_id):
        raise ValueError("invalid case ID")
    custody = case_storage_directory(state, case_id)
    restored = custody / "projet-v1"
    return sync_report_copies(custody, Path(legacy_path) if legacy_path else
                              restored if restored.is_dir() else None)


def pdf_analysis_kind(path):
    """Use the run ID first, then the naming convention of legacy PDFs."""
    run = path.parent.name
    if run.startswith("vigil."):
        return run.removeprefix("vigil.").split("-", 1)[0]
    if run.startswith("scan-"):
        from .antivirus_reports import METADATA, read_json

        for directory in (path.parent, path.parent.parent.parent / run):
            data = read_json(directory / METADATA)
            if data and data.get("name") == path.name:
                return "clamav"
        return "clamav" if path.name.startswith("rapport_clamav") else "usbhid"
    match = re.match(r"rapport_([a-z0-9-]+)", path.name.casefold())
    return match.group(1) if match else ""
