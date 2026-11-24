"""Remove the local files and database records owned by one selected case."""
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from .storage import ANTIVIRUS_CASE_NAME, database, evidence_copy_path, require_active_case
from .system_info import decode_mount


def case_directories(state, case_id):
    custody = evidence_copy_path(state, case_id, "0" * 32).parents[2]
    if custody.exists():
        yield custody
    reports = state.parent / "reports"
    if reports.resolve() != reports.absolute():
        raise ValueError("invalid report directory")
    if not reports.is_dir():
        return
    for folder in reports.iterdir():
        if not re.fullmatch(r"case-[0-9a-f]{32}", folder.name) or folder.is_symlink():
            continue
        manifest = folder / "case.json"
        if not manifest.is_file() or manifest.is_symlink():
            continue
        try:
            content = json.loads(manifest.read_text(encoding="utf-8"))
        except (UnicodeError, ValueError):
            continue
        case = content.get("case") if isinstance(content, dict) else None
        if isinstance(case, dict) and case.get("id") == case_id:
            yield folder


def purge_case(state, case_id):
    moved = []
    try:
        with database(state) as connection:
            case = require_active_case(connection, case_id)
            if case["name"] == ANTIVIRUS_CASE_NAME:
                raise ValueError("the antivirus case cannot be deleted")
            with Path("/proc/self/mountinfo").open(encoding="utf-8", errors="surrogateescape") as stream:
                mounts = [Path(decode_mount(line.split(" - ", 1)[0].split()[4])) for line in stream]
            legacy = Path(case["legacy_path"]).resolve() if case["legacy_path"] else None
            for path in case_directories(state, case_id):
                absolute = path.absolute()
                if (not path.is_dir() or path.resolve() != absolute
                        or any(target.is_relative_to(absolute) for target in mounts)
                        or (legacy and (absolute.is_relative_to(legacy) or legacy.is_relative_to(absolute)))):
                    raise ValueError(f"unsafe case deletion directory: {path}")
                staged = path.with_name(f".purge-{uuid4().hex}")
                path.rename(staged)
                moved.append((path, staged))
            connection.execute("DELETE FROM evidence WHERE case_id = ?", (case_id,))
            connection.execute("DELETE FROM audit WHERE case_id = ?", (case_id,))
            connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    except BaseException:
        for path, staged in reversed(moved):
            staged.rename(path)
        raise

    # Remove only the staged local directories. Leave any failed cleanup identifiable.
    leftovers = []
    for _, staged in moved:
        try:
            shutil.rmtree(staged)
        except OSError:
            leftovers.append(staged)
    return leftovers
