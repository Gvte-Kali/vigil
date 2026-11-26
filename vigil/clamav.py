"""Resolve and validate the one ClamAV signature store used by Vigil."""
import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

MAX_AGE = timedelta(days=7)
ENGINE_RECORD = "vigil-engine-status.json"


def signatures_path(state):
    return state.absolute().parent / "clamav"


def signature_environment(state):
    return f"VIGIL_CLAMAV_DB_DIR={signatures_path(state)}"


def configured_directory():
    if directory := os.environ.get("VIGIL_CLAMAV_DB_DIR"):
        path = Path(directory)
    else:
        from .storage import default_database
        path = signatures_path(default_database())
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Répertoire ClamAV non sûr / Unsafe ClamAV database directory")
    return path


def executable(name):
    program = shutil.which(name)
    if program is None:
        raise ValueError(f"{name}: executable unavailable")
    return program


def database_snapshot(directory):
    if not directory.is_absolute() or directory.resolve() != directory or not directory.is_dir():
        raise ValueError(f"Base Vigil absente ou inaccessible / Vigil database missing or unreadable: {directory}")
    entries = []
    for stem in ("main", "daily", "bytecode"):
        files = [directory / f"{stem}.{ext}" for ext in ("cvd", "cld")]
        found = [path for path in files if os.path.lexists(path)]
        if not found and stem == "bytecode":
            continue
        if len(found) != 1 or found[0].is_symlink() or not found[0].is_file():
            raise ValueError(f"Base Vigil incomplète ou ambiguë / Incomplete or ambiguous Vigil database: {directory}/{stem}")
        with found[0].open("rb") as stream:
            before = os.fstat(stream.fileno())
            fields = stream.read(512).decode("ascii", errors="replace").split(":")
        try:
            if fields[0] != "ClamAV-VDB" or not fields[2].isdigit() or before.st_size <= 512:
                raise ValueError
            published = datetime.fromtimestamp(int(fields[8].strip()), UTC) if stem == "daily" else None
        except (IndexError, ValueError, OverflowError, OSError) as error:
            raise ValueError(f"En-tête de signatures invalide / Invalid signatures header: {found[0]}") from error
        entries.append((stem, found[0].name, int(fields[2]), published,
                        before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns))
    return entries


def signature_status(directory, *, now=None):
    snapshot = database_snapshot(directory)
    command = [executable("clamscan"), "--database", str(directory)]
    version = subprocess.run([*command, "--version"], capture_output=True, text=True, timeout=15, check=True)
    engine = version.stdout.strip().partition("/")[0]
    if not engine.startswith("ClamAV "):
        raise ValueError("Version du moteur indisponible / Cannot identify ClamAV engine")
    # --version alone is not a load test. Force libclamav to open this exact store.
    with tempfile.NamedTemporaryFile() as fixture:
        fixture.write(b"Vigil ClamAV database load check\n")
        fixture.flush()
        loaded = subprocess.run([*command, "--no-summary", "--", fixture.name],
                                capture_output=True, text=True, timeout=120, check=False)
    if loaded.returncode not in {0, 1}:
        raise ValueError(f"ClamScan ne peut pas charger la base Vigil / ClamScan cannot load the Vigil database: "
                         f"{directory}\n{loaded.stderr.strip() or loaded.stdout.strip()}")
    if database_snapshot(directory) != snapshot:
        raise ValueError("La base a changé pendant le contrôle / The database changed during verification")
    _, daily, revision, published, *_ = next(row for row in snapshot if row[0] == "daily")
    age = (now or datetime.now(UTC)) - published
    if age < -timedelta(hours=1):
        raise ValueError("Date de publication daily dans le futur / Future daily release date")
    engine_update = "unknown"
    advisory = directory / ENGINE_RECORD
    if not advisory.is_symlink():
        try:
            recorded = json.loads(advisory.read_text(encoding="utf-8"))
            if recorded == {"engine": engine, "engine_update": "outdated"}:
                engine_update = "outdated"
        except (OSError, ValueError):
            pass
    return {"directory": str(directory), "engine": engine, "daily_file": daily, "daily_version": revision,
            "daily_published": published.isoformat(), "age_hours": max(0, int(age.total_seconds() // 3600)),
            "freshness": "stale" if age > MAX_AGE else "current", "engine_update": engine_update}


def describe(status):
    en = os.environ.get("VIGIL_LANG") == "en"
    freshness = ("stale (> 7 days)" if en else "obsolètes (> 7 jours)") if status["freshness"] == "stale" else (
        "current" if en else "à jour")
    engine_update = {"outdated": "obsolète / outdated", "current": "à jour / current",
                     "unknown": "non vérifié / not verified"}[status["engine_update"]]
    print(f"Moteur / Engine: {status['engine']} ({engine_update})")
    print(f"Base Vigil / Vigil database: {status['directory']}")
    print(f"Daily: {status['daily_version']} · {status['daily_published']} · {status['daily_file']}")
    print(f"Signatures: {status['age_hours']} h · {freshness}", flush=True)


def update_signatures(directory, command):
    expected = f"--config-file={directory / 'vigil-freshclam.conf'}"
    if command[1:] != [expected]:
        raise ValueError("Invalid FreshClam command")
    result = subprocess.Popen([*command, "--datadir=" + str(directory)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors="replace")
    lines = []
    with result.stdout:
        for line in result.stdout:
            print(line, end="", flush=True)
            lines.append(line)
    if result.wait():
        raise ValueError("Mise à jour FreshClam échouée / FreshClam update failed")
    status = signature_status(directory)
    # FreshClam reports the published or current version for daily in its own output.
    revisions = re.findall(r"daily\.(?:cvd|cld)\s+(?:updated|database is up-to-date)\s*\(version:\s*(\d+)",
                           "".join(lines), re.I)
    if not revisions or int(revisions[-1]) != status["daily_version"]:
        raise ValueError("Révision daily FreshClam/ClamScan non concordante / FreshClam and ClamScan daily revisions disagree")
    status["engine_update"] = "outdated" if any(
        "CLAMAV INSTALLATION IS OUTDATED" in line.upper() for line in lines
    ) else "unknown"
    with tempfile.NamedTemporaryFile(dir=directory, mode="w", encoding="utf-8", delete=False) as stream:
        staged = Path(stream.name)
        try:
            json.dump({key: status[key] for key in ("engine", "engine_update")}, stream)
            stream.flush()
            os.replace(staged, directory / ENGINE_RECORD)
        finally:
            staged.unlink(missing_ok=True)
    describe(status)
    return status


def prepare_scan(directory, *, offline=False, log=None):
    status = signature_status(directory)
    describe(status)
    status["offline"] = offline
    if log:
        log.write_text(json.dumps(status, ensure_ascii=False) + "\n", encoding="utf-8")
    if status["freshness"] == "stale" and not offline:
        if not sys.stdin.isatty():
            raise ValueError("Signatures obsolètes : utilisez --offline pour continuer explicitement / Stale signatures: use --offline to continue")
        en = os.environ.get("VIGIL_LANG") == "en"
        answer = input("[U] Update · [O] Continue offline · [Enter] Cancel: " if en else
                       "[U] Mettre à jour · [O] Continuer hors ligne · [Entrée] Annuler : ").strip().casefold()
        if answer == "u":
            from .quick_actions import update_command
            status = update_signatures(directory, update_command(directory.parent / "cases.sqlite"))
            if status["freshness"] == "stale":
                raise ValueError("Signatures toujours obsolètes / Signatures are still stale")
        elif answer != "o":
            raise ValueError("Scan annulé / Scan cancelled")
        else:
            offline = True
    status["offline"] = offline
    if log:
        log.write_text(json.dumps(status, ensure_ascii=False) + "\n", encoding="utf-8")
    return status


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("directory")
    sub.add_parser("refresh")
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--offline", action="store_true")
    prepare.add_argument("--log", type=Path)
    update = sub.add_parser("update")
    update.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    directory = configured_directory()
    if args.action == "directory":
        print(directory)
    elif args.action == "prepare":
        prepare_scan(directory, offline=args.offline, log=args.log)
    elif args.action == "update":
        update_signatures(directory, args.command)
    elif args.action == "refresh":
        from .quick_actions import update_command
        update_signatures(directory, update_command(directory.parent / "cases.sqlite"))


if __name__ == "__main__":
    if __package__ is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        __package__ = "vigil"
    try:
        main()
    except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
