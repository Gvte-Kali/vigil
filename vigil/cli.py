"""Vigil 2.0 commands, usable without Qt or a desktop session."""
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import clamav, device_manager, storage
from .quick_actions import scan_command
from .case_export import export_case
from .case_import import import_archive, verify_archive
from .core import BUILTIN_MODULES, discover, doctor
from .images import inspect_raw
from .terminal import show_logo


class VigilCLI(typer.Typer):
    def __call__(self, *args, **kwargs):
        # Existing editable installs still launch app() directly.
        if (not sys.argv[1:] and not args and kwargs.get("args") is None
                and sys.stdin.isatty() and sys.stdout.isatty() and "_VIGIL_COMPLETE" not in os.environ):
            kwargs["args"] = ["tui"]
        if sys.stderr.isatty() and "_VIGIL_COMPLETE" not in os.environ:
            if os.environ.get("TERM") not in (None, "dumb"):
                print("\033[H\033[2J", end="", file=sys.stderr, flush=True)
            show_logo(stream=sys.stderr)
        return super().__call__(*args, **kwargs)


app = VigilCLI(name="vigil", no_args_is_help=True)
modules = typer.Typer(no_args_is_help=True)
cases = typer.Typer(no_args_is_help=True)
evidence = typer.Typer(no_args_is_help=True)
devices = typer.Typer(no_args_is_help=True, help="Manage devices / Gérer les périphériques.")
antivirus = typer.Typer(no_args_is_help=True, help="ClamAV avec le profil Vigil / ClamAV using the Vigil profile.")
app.add_typer(antivirus, name="antivirus")
app.add_typer(modules, name="modules")
app.add_typer(cases, name="cases")
app.add_typer(evidence, name="evidence")
app.add_typer(devices, name="devices")
DatabaseOption = Annotated[Optional[Path], typer.Option("--db")]


def show_version(requested: bool):
    if requested:
        try:
            release = version("vigil-dfir")
        except PackageNotFoundError:
            release = "2.0.0a1"
        typer.echo(f"Vigil {release}")
        raise typer.Exit()


@app.callback()
def options(
    version_requested: Annotated[Optional[bool], typer.Option(
        "--version", callback=show_version, is_eager=True, help="Show the Vigil version and exit.",
    )] = None,
):
    """Vigil digital forensics workspace."""


@contextmanager
def command():
    try:
        yield
    except (OSError, ValueError, EOFError, sqlite3.Error, subprocess.SubprocessError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error


def emit(result):
    typer.echo(json.dumps(result, ensure_ascii=False))


@contextmanager
def device_command():
    try:
        yield
    except (OSError, ValueError) as error:
        emit({"success": False, "error": str(error)})
        raise typer.Exit(1) from error


@devices.command("list")
def list_devices():
    """List block devices / Lister les périphériques bloc."""
    with device_command():
        emit({"devices": device_manager.inventory()})


@devices.command("triage")
def triage_device(device: Optional[str] = None, zone: str = "investigation"):
    """Select and validate a device / Sélectionner et valider un périphérique."""
    with device_command():
        emit(device_manager.triage(zone, device))


@devices.command("mount")
def mount_device(device: Optional[str] = None, zone: str = "investigation",
                 confirm_write: bool = typer.Option(False, "--confirm-write")):
    """Mount a device in a Vigil zone / Monter un périphérique dans une zone Vigil."""
    with device_command():
        result = device_manager.operate("mount", zone, device=device, confirm_write=confirm_write)
        emit(result)
        if not result["success"]:
            raise typer.Exit(1)


@devices.command("unmount")
def unmount_device(target: Optional[str] = None, zone: str = "investigation"):
    """Unmount a Vigil resource / Démonter une ressource Vigil."""
    with device_command():
        result = device_manager.operate("unmount", zone, target=target)
        emit(result)
        if not result["success"]:
            raise typer.Exit(1)


@devices.command("status")
def device_status():
    """Show mounted resources / Afficher les ressources montées."""
    with device_command():
        emit({"mounts": device_manager.status()})


@devices.command("verify")
def verify_devices(target: Optional[str] = None):
    """Verify mount identity and protections / Vérifier l’identité et les protections."""
    with device_command():
        resources = [row for row in device_manager.status() if target is None or row["mountpoint"] == target]
        verified = all(row["verified"] for row in resources) and (target is None or bool(resources))
        emit({"verified": verified, "mounts": resources})
        if not verified:
            raise typer.Exit(1)


@app.command("tui")
def launch_tui(
    db: DatabaseOption = None,
    lang: Annotated[str, typer.Option("--lang", help="fr or en")] = "fr",
    operator: Annotated[Optional[str], typer.Option("--operator")] = None,
):
    """Open the terminal workspace / Ouvrir l’espace de travail terminal."""
    if lang not in {"fr", "en"}:
        raise typer.BadParameter("fr or en", param_hint="--lang")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo("Un terminal interactif est requis / An interactive terminal is required.", err=True)
        raise typer.Exit(1)
    try:
        import textual
    except ModuleNotFoundError as error:
        if error.name != "textual":
            raise
        typer.echo("Textual manquant : réinstallez Vigil / Textual missing: reinstall Vigil.", err=True)
        raise typer.Exit(1) from error
    from .session import supervise

    state = (db or storage.default_database()).absolute()
    arguments = ["--db", str(state), "--lang", lang]
    if operator is not None:
        operator = operator.strip()
        if not 1 <= len(operator) <= 120 or not operator.isprintable():
            raise typer.BadParameter("printable name of 1–120 characters required", param_hint="--operator")
        arguments.extend(("--operator", operator))
    raise typer.Exit(supervise(arguments, interface="tui", state=state))


@app.command("gui")
def launch_gui():
    """Open the Qt workspace / Ouvrir l’espace de travail Qt."""
    from .session import supervise

    raise typer.Exit(supervise([]))


@antivirus.command("status")
def antivirus_status(db: DatabaseOption = None):
    """Verify and show the active Vigil signature set."""
    with command():
        emit(clamav.signature_status(clamav.signatures_path(db or storage.default_database())))


@antivirus.command("update")
def antivirus_update(db: DatabaseOption = None):
    """Update the Vigil signature set and verify it with ClamScan."""
    from . import dev_mode

    with command():
        if dev_mode.active():
            raise ValueError(dev_mode.BLOCKED)
        state = db or storage.default_database()
        clamav.describe(clamav.refresh_signatures(clamav.signatures_path(state)))


@antivirus.command("scan")
def antivirus_scan(path: Path, db: DatabaseOption = None,
                   offline: bool = typer.Option(False, "--offline", help="Explicitly accept stale signatures.")):
    """Scan a readable path with the Vigil signature set."""
    from . import dev_mode

    with command():
        if dev_mode.active():
            raise ValueError(dev_mode.BLOCKED)
        state = db or storage.default_database()
        argv = scan_command(path, state)
        clamav.prepare_scan(clamav.signatures_path(state), offline=offline)
        with clamav.signature_lock(clamav.signatures_path(state), shared=True):
            physical = Path(argv[-1])
            if physical.is_relative_to("/investigation"):
                from .inspection import investigation_mounts

                if not any(physical.is_relative_to(root) for root in investigation_mounts()):
                    raise ValueError("Montage d’investigation RO requis / A read-only investigation mount is required")
                status = device_manager.run_job(argv, analysis=True)
            else:
                status = subprocess.run(argv, check=False).returncode
        raise typer.Exit(status)


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


@evidence.command("migrate")
def migrate_evidence(case_id: str, operator: str = typer.Option(...), db: DatabaseOption = None):
    """Migrate and verify legacy local evidence copies."""
    with command():
        emit(storage.migrate_evidence_copies(db or storage.default_database(), case_id, operator))


@evidence.command("list")
def list_evidence(case_id: str, db: DatabaseOption = None):
    with command():
        emit(storage.case_evidence_rows(db or storage.default_database(), case_id))


@evidence.command("verify")
def verify(evidence_id: str, operator: str = typer.Option(...), db: DatabaseOption = None,
           use_copy: bool = typer.Option(False, "--copy", help="Verify the local evidence copy")):
    with command():
        result = storage.verify_file(db or storage.default_database(), evidence_id, operator, use_copy=use_copy)
        emit(result)
        if not result["matches"]:
            raise typer.Exit(2)


@evidence.command("inspect-raw")
def inspect_raw_command(path: Path, sector_size: int = 512):
    with command():
        emit(inspect_raw(path, sector_size))


def main():
    app(prog_name="vigil")


def tui_main():
    app(args=["tui", *sys.argv[1:]], prog_name="vigil")


if __name__ == "__main__":
    main()
