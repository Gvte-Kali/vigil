"""Vigil 2.0 commands, usable without Qt or a desktop session."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import storage
from .core import BUILTIN_MODULES, discover, doctor
from .images import inspect_raw

app = typer.Typer(no_args_is_help=True)
modules = typer.Typer(no_args_is_help=True)
cases = typer.Typer(no_args_is_help=True)
evidence = typer.Typer(no_args_is_help=True)
app.add_typer(modules, name="modules")
app.add_typer(cases, name="cases")
app.add_typer(evidence, name="evidence")
DatabaseOption = Annotated[Optional[Path], typer.Option("--db")]


@contextmanager
def command():
    try:
        yield
    except (OSError, ValueError, sqlite3.Error) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error


def emit(result):
    typer.echo(json.dumps(result, ensure_ascii=False))


@app.command("doctor")
def doctor_command():
    emit(doctor())


@modules.command("list")
def list_modules(category: Optional[str] = None):
    manifests, errors = discover(BUILTIN_MODULES)
    emit({"modules": [
        manifest.model_dump() for manifest in manifests.values()
        if category is None or manifest.category == category
    ], "errors": errors})
    if errors:
        raise typer.Exit(1)


@cases.command("create")
def create(name: str, operator: str = typer.Option(...), db: DatabaseOption = None):
    with command():
        with storage.database(db or storage.default_database()) as connection:
            case_id = storage.create_case(connection, name, operator)
        emit({"id": case_id})


@cases.command("list")
def list_cases(db: DatabaseOption = None):
    with command():
        with storage.database(db or storage.default_database()) as connection:
            rows = connection.execute("SELECT * FROM cases ORDER BY created_at, id")
            result = [dict(row) for row in rows]
        emit(result)


@cases.command("import")
def import_case(path: Path, operator: str = typer.Option(...), db: DatabaseOption = None):
    with command():
        path = path.resolve(strict=True)
        name, raw = storage.read_legacy_project(path)
        with storage.database(db or storage.default_database()) as connection:
            case_id = storage.create_case(connection, name, operator, str(path), raw)
        emit({"id": case_id, "legacy_path": str(path)})


@evidence.command("add")
def add(case_id: str, path: Path, operator: str = typer.Option(...),
        db: DatabaseOption = None):
    with command():
        path = path.absolute()
        state = db or storage.default_database()
        if state.exists() and state.samefile(path):
            raise ValueError("database and evidence must be separate files")
        size, digest = storage.fingerprint(path)
        with storage.database(state) as connection:
            evidence_id = storage.add_evidence(connection, case_id, path, size, digest, operator)
        emit({"id": evidence_id, "size": size, "sha256": digest})


@evidence.command("verify")
def verify(evidence_id: str, operator: str = typer.Option(...), db: DatabaseOption = None):
    path = db or storage.default_database()
    with command():
        with storage.database(path) as connection:
            record = connection.execute(
                "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
            ).fetchone()
        if record is None:
            raise ValueError("unknown evidence ID")
        size, digest = storage.fingerprint(Path(record["path"]))
        result = {
            "id": evidence_id, "expected_sha256": record["sha256"], "sha256": digest,
            "matches": size == record["size"] and digest == record["sha256"],
        }
        with storage.database(path) as connection:
            storage.audit(connection, operator, record["case_id"], "evidence.verify", result)
        emit(result)
        if not result["matches"]:
            raise typer.Exit(2)


@evidence.command("inspect-raw")
def inspect_raw_command(path: Path, sector_size: int = 512):
    with command():
        emit(inspect_raw(path, sector_size))


if __name__ == "__main__":
    app()
