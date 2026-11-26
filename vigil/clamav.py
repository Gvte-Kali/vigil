"""Resolve and validate the one ClamAV signature store used by Vigil."""
import argparse
import codecs
from contextlib import contextmanager
import fcntl
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import signal
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
    if not path.is_absolute() or path.resolve() != path or path.is_relative_to("/investigation"):
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
    try:
        with result.stdout:
            for line in result.stdout:
                print(line, end="", flush=True)
                lines.append(line)
        code = result.wait()
    except BaseException:
        if result.poll() is None:
            result.terminate()
            result.wait()
        raise
    if code:
        raise ValueError(tr("Mise à jour FreshClam échouée", "FreshClam update failed") + " · " + update_error("".join(lines)))
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
            status = refresh_signatures(directory)
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


MAX_CVD_BYTES = 1024**3
SIGNATURE_FILES = tuple(f"{stem}.{ext}" for stem in ("main", "daily", "bytecode") for ext in ("cvd", "cld"))
ONLINE_CONFIRMATION = (
    "Cette opération nécessite un accès Internet. Vigil contactera les dépôts logiciels de votre "
    "distribution et les serveurs ClamAV afin de mettre à jour le moteur antivirus et ses signatures. "
    "Souhaitez-vous continuer ?",
    "This operation requires Internet access. Vigil will contact your distribution's repositories "
    "and the ClamAV servers to update the antivirus engine and signatures. Continue?",
)


def tr(fr, en):
    return en if os.environ.get("VIGIL_LANG") == "en" else fr


@contextmanager
def signature_lock(directory, *, shared=False):
    directory.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = directory.parent / ".clamav.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(tr("Un scan ou une mise à jour ClamAV est en cours.",
                                "A ClamAV scan or update is already active.")) from error
        yield path
    finally:
        os.close(fd)


def engine_version():
    result = subprocess.run([executable("clamscan"), "--version"], capture_output=True, text=True, check=True, timeout=15)
    return result.stdout.strip().partition("/")[0]


def previous_status(directory):
    try:
        return signature_status(directory)
    except (OSError, ValueError, subprocess.SubprocessError):
        try:
            return {"engine": engine_version()}
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}


def print_transition(previous, current):
    for title, left, right in (
        (tr("Moteur", "Engine"), previous.get("engine"), current.get("engine")),
        ("Daily", previous.get("daily_version"), current.get("daily_version")),
    ):
        print(f"{title} · {left if left is not None else '—'} → {right if right is not None else '—'}")
    if "daily_version" in current:
        describe(current)


def publish_signatures(directory, candidate):
    """Activate a validated set with backup and rollback under the update lease."""
    verified = signature_status(candidate)
    names = (*SIGNATURE_FILES, ENGINE_RECORD)
    backup = Path(tempfile.mkdtemp(prefix=".rollback-", dir=directory))
    keep_backup = False
    try:
        for name in names:
            current = directory / name
            if os.path.lexists(current):
                if current.is_symlink() or not current.is_file():
                    raise ValueError(f"Unsafe signature entry: {current}")
                os.link(current, backup / name)
        try:
            for name in names:
                source = candidate / name
                target = directory / name
                if source.is_file():
                    os.replace(source, target)
                else:
                    target.unlink(missing_ok=True)
            result = signature_status(directory)
            if any(result[key] != verified[key] for key in ("daily_version", "daily_file", "engine")):
                raise ValueError("Signature activation mismatch")
        except BaseException:
            keep_backup = True
            for name in names:
                old, current = backup / name, directory / name
                if old.exists():
                    restore = backup / f"restore-{name}"
                    os.link(old, restore)
                    os.replace(restore, current)
                else:
                    current.unlink(missing_ok=True)
            keep_backup = False
            raise
    finally:
        if keep_backup:
            print(f"{tr('Sauvegarde conservée', 'Backup retained')} · {backup}", file=sys.stderr)
        else:
            shutil.rmtree(backup)
    return result


def refresh_signatures(directory):
    from .quick_actions import freshclam_command

    with signature_lock(directory):
        directory.mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".freshclam-update-", dir=directory) as staging:
            candidate = Path(staging)
            for name in SIGNATURE_FILES:
                current = directory / name
                if current.is_file() and not current.is_symlink():
                    shutil.copyfile(current, candidate / name)
            update_signatures(candidate, freshclam_command(candidate))
            return publish_signatures(directory, candidate)


def update_error(output):
    patterns = (
        (r"resolve host|name resolution|dns|could not resolve", "Échec DNS", "DNS lookup failed"),
        (r"ssl|\btls\b|certificate|proxy", "Erreur TLS ou proxy", "TLS or proxy error"),
        (r"lock|another process|running transaction", "Gestionnaire de paquets verrouillé", "Package manager locked"),
        (r"not in the sudoers|password|not allowed|permission denied",
         "Autorisation administrateur refusée", "Administrator permission denied"),
        (r"unreachable|no route|offline", "Connexion Internet indisponible", "Internet connection unavailable"),
        (r"interrupt|cancel|aborted|partial file", "Téléchargement interrompu", "Download interrupted"),
        (r"repository|repositories|release file|mirror|repomd",
         "Dépôts indisponibles", "Software repositories unavailable"),
        (r"connect|timeout|timed out|http|403|429|503", "Serveur distant inaccessible", "Remote server unreachable"),
    )
    for pattern, fr, en in patterns:
        if re.search(pattern, output, re.I):
            return tr(fr, en)
    return tr("Consultez le journal de l’opération.", "Check the operation log.")


def checked_update_step(arguments):
    environment = {**os.environ, "LC_ALL": "C"}
    with subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          env=environment) as process:
        output = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        # Package managers can print a prompt without a newline, then wait on stdin.
        while chunk := process.stdout.read1(8192):
            text = decoder.decode(chunk)
            print(text, end="", flush=True)
            output.append(text)
        output.append(decoder.decode(b"", final=True))
        print(output[-1], end="", flush=True)
        code = process.wait()
    if code:
        raise ValueError(update_error("".join(output)))


def engine_upgrade_plan(family, packages):
    if family == "arch":
        return []
    if not packages:
        raise ValueError(tr("Aucun paquet ClamAV installé n’a été détecté.", "No installed ClamAV packages found."))
    if family == "debian":
        return [("apt-get", "-o", "APT::Update::Error-Mode=any", "update"),
                ("apt-get", "install", "--only-upgrade", "--", *packages)]
    if family == "fedora":
        return [("dnf", "upgrade", "--refresh", "--", *packages)]
    if family == "opensuse":
        return [("zypper", "refresh"), ("zypper", "update", "--", *packages)]
    raise ValueError(tr("Distribution non prise en charge.", "Unsupported distribution."))


def installed_clamav(family):
    command = (["dpkg-query", "-W", "-f=${binary:Package}\t${db:Status-Abbrev}\n", "clamav*", "libclamav*"]
               if family == "debian" else ["pacman", "-Qq"] if family == "arch" else ["rpm", "-qa", "--qf", "%{NAME}\n"])
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode and not result.stdout:
        raise ValueError(result.stderr.strip() or "Installed ClamAV package discovery failed")
    return sorted({line.split()[0] for line in result.stdout.splitlines()
                   if line.split() and re.fullmatch(r"(?:lib)?clamav[\w.+:-]*", line.split()[0])
                   and (family != "debian" or len(line.split()) > 1 and line.split()[1].startswith("ii"))})


def online_update(directory):
    from .linux_distribution import identify

    previous = previous_status(directory)
    engine_ok = False
    try:
        family = identify(Path("/etc/os-release"))
        packages = installed_clamav(family) if family else ()
        if family == "arch":
            print(tr("Arch : mettez à niveau le système avec sudo pacman -Syu pour actualiser le moteur. "
                     "Vigil poursuit avec les signatures uniquement.",
                     "Arch: run sudo pacman -Syu to upgrade the engine. Vigil will update signatures only."))
        else:
            for action, *arguments in engine_upgrade_plan(family, packages):
                checked_update_step(["sudo", "--", executable(action), *arguments])
            engine_ok = True
            print(tr("Paquets ClamAV vérifiés.", "ClamAV packages checked."))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"{tr('Étape moteur en échec', 'Engine stage failed')} · {error}", file=sys.stderr)
    try:
        current = refresh_signatures(directory)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"{tr('Étape signatures en échec', 'Signature stage failed')} · {error}", file=sys.stderr)
        print_transition(previous, previous_status(directory))
        print(tr("Résultat : partiel." if engine_ok else "Résultat : échec.",
                 "Result: partial." if engine_ok else "Result: failed."))
        return 2 if engine_ok else 1
    if current["engine_update"] == "outdated":
        engine_ok = False
        print(tr("La version récente du moteur n’est pas disponible dans la mise à jour appliquée.",
                 "The newer engine version was not available in the applied package update."))
    complete = engine_ok and current["freshness"] == "current"
    print_transition(previous, current)
    print(tr("Résultat : réussite complète." if complete else "Résultat : partiel.",
             "Result: complete." if complete else "Result: partial."))
    return 0 if complete else 2


def usb_candidates(candidate):
    from .device_manager import status
    from .inspection import investigation_mounts, list_evidence_directory, open_evidence_path

    resources = [row for row in status() if row["zone"] == "/investigation"]
    if not resources or not all(row["verified"] for row in resources):
        raise ValueError(tr("Montage USB RO non vérifié.", "USB read-only mount is not verified."))
    mounts = investigation_mounts()
    roots = {Path(row["mountpoint"]): mounts.get(row["mountpoint"]) for row in resources}
    if any(value is None for value in roots.values()):
        raise ValueError("USB mount identity changed")
    signature_tool = executable("sigtool")
    selected = {}
    for root, mount_id in roots.items():
        pending = [root]
        while pending:
            folder = pending.pop()
            for name, directory in list_evidence_directory(folder, root, mount_id):
                source = folder / name
                if directory:
                    if source not in roots:
                        pending.append(source)
                    continue
                if name not in SIGNATURE_FILES:
                    continue
                display = "".join(char if char.isprintable() else "?" for char in str(source))
                if source.suffix == ".cld":
                    print(f"{display} · {tr('CLD sans provenance de confiance : refusé', 'CLD without trusted provenance: rejected')}")
                    continue
                with tempfile.TemporaryDirectory(dir=candidate) as staging:
                    path = Path(staging) / name
                    with open_evidence_path(source, root, mount_id) as fd:
                        if not 512 < os.fstat(fd).st_size <= MAX_CVD_BYTES:
                            print(f"{display} · {tr('Taille CVD refusée', 'CVD size rejected')}")
                            continue
                        with open(f"/proc/self/fd/{fd}", "rb") as origin, path.open("xb") as output:
                            shutil.copyfileobj(origin, output)
                    result = subprocess.run([signature_tool, "--info", str(path)], capture_output=True,
                                            text=True, check=False, timeout=120)
                    header = result.stdout
                    if result.returncode or not re.search(r"(?im)^Verification OK\.?\s*$", header):
                        print(f"{display} · {tr('Signature officielle non vérifiée', 'Official signature not verified')}")
                        continue
                    version = re.search(r"(?im)^Version:\s*(\d+)\s*$", header)
                    date = re.search(r"(?im)^Build time:\s*(.+)$", header)
                    if not version:
                        continue
                    print(f"{display} · {version[1]} · {date[1] if date else '—'} · OK")
                    if int(version[1]) > selected.get(name, -1):
                        os.replace(path, candidate / name)
                        selected[name] = int(version[1])
    return selected


def offline_update(directory):
    with signature_lock(directory):
        directory.mkdir(mode=0o700, exist_ok=True)
        previous = previous_status(directory)
        with tempfile.TemporaryDirectory(prefix=".usb-update-", dir=directory) as staging:
            candidate = Path(staging)
            selected = usb_candidates(candidate)
            if not {"main.cvd", "daily.cvd"} <= selected.keys():
                raise ValueError(tr("Le support doit fournir main et daily signées et vérifiées.",
                                    "The medium must provide verified, signed main and daily CVD files."))
            for name in ("main", "daily", "bytecode"):
                current = [directory / f"{name}.{ext}" for ext in ("cvd", "cld")]
                for path in current:
                    if path.is_file() and not path.is_symlink():
                        with path.open("rb") as stream:
                            revision = int(stream.read(512).split(b":")[2])
                        chosen = selected.get(f"{name}.cvd")
                        if chosen is not None and chosen < revision:
                            raise ValueError(f"{name}: {chosen} < {revision} · {tr('rétrogradation refusée', 'downgrade refused')}")
                        if chosen is None:
                            shutil.copyfile(path, candidate / path.name)
            advisory = directory / ENGINE_RECORD
            if advisory.is_file() and not advisory.is_symlink():
                shutil.copyfile(advisory, candidate / ENGINE_RECORD)
            proposed = signature_status(candidate)
            print_transition(previous, proposed)
            if input(tr("Importer ces signatures ? [o/N] : ", "Import these signatures? [y/N]: ")).casefold() not in {"o", "y"}:
                raise ValueError(tr("Import annulé.", "Import cancelled."))
            current = publish_signatures(directory, candidate)
        print_transition(previous, current)
        partial = current["freshness"] == "stale"
        print(tr("Résultat : partiel (signatures anciennes)." if partial else "Résultat : réussite complète.",
                 "Result: partial (stale signatures)." if partial else "Result: complete."))
        return 2 if partial else 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("directory")
    sub.add_parser("refresh")
    sub.add_parser("online")
    sub.add_parser("offline")
    sub.add_parser("lock-path")
    sub.add_parser("mounts-clear")
    verify = sub.add_parser("verify-log")
    verify.add_argument("log", type=Path)
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
        refresh_signatures(directory)
    elif args.action == "online":
        return online_update(directory)
    elif args.action == "offline":
        try:
            return offline_update(directory)
        except (OSError, ValueError, EOFError, subprocess.SubprocessError):
            print(tr("Résultat : échec.", "Result: failed."), file=sys.stderr)
            raise
    elif args.action == "lock-path":
        with signature_lock(directory, shared=True) as path:
            print(path)
    elif args.action == "verify-log":
        recorded = json.loads(args.log.read_text())
        _, daily, version, published, *_ = next(row for row in database_snapshot(directory) if row[0] == "daily")
        if (daily, version, published.isoformat()) != (
            recorded["daily_file"], recorded["daily_version"], recorded["daily_published"]
        ):
            raise ValueError(tr("La base a changé, relancez le scan.", "The database changed, restart the scan."))
    elif args.action == "mounts-clear":
        from .system_info import read_zones
        if read_zones()["/investigation"]:
            raise ValueError(tr("La zone /investigation doit être démontée.",
                                "The /investigation zone must be unmounted."))


if __name__ == "__main__":
    if __package__ is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        __package__ = "vigil"
    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(tr("Opération interrompue.", "Operation interrupted."))
    except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
