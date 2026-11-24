"""Explicit adapters for historical commands available from the workspace."""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from . import storage

CENSUS_LIMIT = 100


def query_census(state, case_id, operator, index):
    if os.geteuid() == 0:
        raise ValueError("run Vigil as a regular user")
    script = Path(__file__).resolve().parents[1] / "scripts/analyse/vigil_census_query.py"
    if not script.is_file():
        script = Path(sys.prefix) / "share/vigil/scripts/vigil_census_query.py"
    if not script.is_file():
        raise ValueError("census query script unavailable")
    index = index.resolve(strict=True)
    details = {
        "run_id": uuid4().hex, "module": "vigil.census-query", "index": str(index),
        "filter": "mismatched", "limit": CENSUS_LIMIT,
    }
    with storage.database(state) as connection:
        storage.audit(connection, operator, case_id, "module.start", details)
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(script), "--index", str(index),
             "--mismatched", "--limit", str(CENSUS_LIMIT)],
            capture_output=True, text=True, errors="replace",
            stdin=subprocess.DEVNULL, timeout=20, check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        with storage.database(state) as connection:
            storage.audit(connection, operator, case_id, "module.error", details)
        diagnostic = getattr(error, "stderr", None) or str(error)
        raise ValueError(diagnostic.strip()) from error
    with storage.database(state) as connection:
        storage.audit(connection, operator, case_id, "module.success", details)
    return completed.stdout
