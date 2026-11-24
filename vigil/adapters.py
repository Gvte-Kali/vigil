"""Explicit adapters for historical commands available from the workspace."""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from . import storage
from .quick_actions import signatures_path
from .report_copies import SYNC_REPORTS, report_sync_context

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


def analysis_command(state, case_id, operator, module_id):
    """Build a non-privileged command for a trusted built-in case adapter."""
    from .core import BUILTIN_MODULES, discover
    from .entity import data_directory, legacy_base

    manifests, _ = discover(BUILTIN_MODULES)
    module = manifests.get(module_id)
    if module is None or module.category != "analysis" or set(module.capabilities) != {
        "evidence.read", "results.write",
    }:
        raise ValueError("unsupported built-in analysis")
    base = legacy_base()
    script = (base / module.entrypoint).resolve(strict=True)
    is_antivirus = module_id == "vigil.clamav"
    expected_directory = base / "scripts" / ("clamav" if is_antivirus else "analyse")
    if script.parent != expected_directory:
        raise ValueError("invalid built-in analysis entrypoint")
    run_id = uuid4().hex
    custody = storage.evidence_copy_path(state, case_id, "0" * 32).parents[2]
    root = custody / "analyses"
    if root.resolve() != root.absolute():
        raise ValueError("invalid analysis output directory")
    output = root / f"{module_id}-{run_id}"
    with storage.database(state) as connection:
        case = storage.require_active_case(connection, case_id)
        storage.audit(connection, operator, case_id, "analysis.request",
                      {"module": module_id, "run_id": run_id, "results": str(output)})
    output.mkdir(mode=0o700, parents=True)
    args = ["--json-out", str(output)]
    if module_id == "vigil.census" or is_antivirus:
        args.extend(("--user", operator))
    if is_antivirus:
        args.extend(("--all", "--yes", "--pdf", "--log", "--comment="))
    # Preserve the script exit code through tee. The terminal launcher keeps diagnostics visible.
    wrapper = (
        'umask 077; set -o pipefail; /usr/bin/bash "$@" 2>&1 | tee "$VIGIL_ANALYSIS_RESULTS/terminal.log"; '
        f'rc=$?; {SYNC_REPORTS} || {{ [ "$rc" -ne 0 ] || rc=1; }}; '
        'printf "%s\\n" "$rc" > "$VIGIL_ANALYSIS_RESULTS/exit-code"; exit "$rc"'
    )
    return [
        "/usr/bin/env", *report_sync_context(custody), f"VIGIL_BASE={base}", f"VIGIL_DATA_DIR={data_directory(base)}",
        "VIGIL_CASE_ANALYSIS=1", f"VIGIL_CASE_CENSUS={int(module_id == 'vigil.census')}",
        "VIGIL_INVESTIGATION_DIR=/investigation", f"VIGIL_LEGACY_PROJECT={case['name']}",
        f"VIGIL_ACTIVE_USER={operator}", f"VIGIL_ANALYSIS_RESULTS={output}",
        f"VIGIL_LEGACY_SCAN_DIR={output if is_antivirus else ''}",
        f"VIGIL_CLAMAV_DB_DIR={signatures_path(state)}", f"VIGIL_LEGACY_CASE_DIR={output}", "/usr/bin/bash", "-c", wrapper,
        "vigil", str(script), *args,
    ]
