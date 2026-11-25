"""Vigil 2.0 commands, usable without Qt or a desktop session."""
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import storage
from .case_export import export_case
from .case_import import import_archive, verify_archive
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
            rows = connection.execute("SELECT * FROM cases WHERE id NOT IN (SELECT case_id FROM deleted_cases) ORDER BY created_at, id")
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


@cases.command("verify-archive")
def verify_case_archive(path: Path):
    with command():
        result = verify_archive(path)
        emit({**asdict(result), "status": "valid-partial" if result.missing else "valid"})


@cases.command("import-archive")
def import_case_archive(path: Path, operator: str = typer.Option(...), db: DatabaseOption = None):
    with command():
        emit(import_archive(db or storage.default_database(), path, operator))


@cases.command("export")
def export(case_id: str, destination: Path, operator: str = typer.Option(...),
           db: DatabaseOption = None):
    with command():
        result = export_case(db or storage.default_database(), case_id, operator, destination)
        emit({"directory": str(result.path), "archive": str(result.path / "affaire.tar.gz"),
              "coverage": "partial" if result.missing else "complete",
              "missing_evidence": result.missing})


@evidence.command("add")
def add(case_id: str, path: Path, operator: str = typer.Option(...),
        db: DatabaseOption = None):
    with command():
        emit(storage.register_file(db or storage.default_database(), case_id, path, operator))


@evidence.command("verify")
def verify(evidence_id: str, operator: str = typer.Option(...), db: DatabaseOption = None):
    with command():
        result = storage.verify_file(db or storage.default_database(), evidence_id, operator)
        emit(result)
        if not result["matches"]:
            raise typer.Exit(2)


@evidence.command("inspect-raw")
def inspect_raw_command(path: Path, sector_size: int = 512):
    with command():
        emit(inspect_raw(path, sector_size))


if __name__ == "__main__":
    app()
