"""Supervise the Qt session and open a terminal with its shutdown checks."""
import configparser
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from .entity import legacy_base
from .external_terminal import TERMINALS, ExternalRun, launch_terminal
from .shutdown_state import ShutdownBlocked, capture_startup_state, check_shutdown_state
from .storage import default_database
from .terminal import show_logo

REPORTS = Path("/run/vigil-hotplug/reports")
HELPER = Path("/usr/local/sbin/vigil-hotplug")


def session_preferences(state):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(state.parent / "preferences" / f"{os.getuid()}.ini", encoding="utf-8")
        values = parser["General"]
        preferred = values.get("external_terminal", "")
        return values.get("language", "fr"), preferred if preferred in TERMINALS else ""
    except (OSError, KeyError, ValueError, configparser.Error):
        return "fr", ""


def receipt_path(pid):
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return REPORTS / f"{pid}-{int(fields[19])}.json"
    except (OSError, IndexError, ValueError):
        return None


def read_receipt(path, *, wait=12, include_pending=False):
    if not HELPER.is_file():
        return {"status": "not_installed"}
    if path is None:
        return {"status": "unavailable"}
    deadline = time.monotonic() + wait
    while True:
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                return {"status": "unavailable"}
            receipt = json.loads(path.read_text())
            if include_pending or receipt["status"] != "pending":
                return receipt
        except FileNotFoundError:
            # No activation was recorded, or the installed helper predates receipts.
            return {"status": "not_activated" if REPORTS.is_dir() else "unavailable"}
        except (OSError, ValueError, KeyError):
            return {"status": "unavailable"}
        if time.monotonic() >= deadline:
            return {"status": "pending"}
        time.sleep(0.15)


def record_startup_recovery(state, guard_pid, candidates):
    receipt = read_receipt(receipt_path(int(guard_pid)), wait=0, include_pending=True)
    if receipt.get("startup_recovery") != "complete":
        return
    for name in set(candidates) & set(pending_sessions(state.parent / "sessions")):
        if not re.fullmatch(r"[0-9a-f]{32}\.json", name):
            continue
        journal = state.parent / "sessions" / name
        try:
            entry = json.loads(journal.read_text())
            if entry.get("session") == journal.stem:
                entry.update(status="closed", recovered_at_startup=True)
                write_state(journal, entry)
        except (OSError, ValueError, AttributeError):
            continue


def mount_check():
    try:
        check_shutdown_state()
    except ShutdownBlocked as error:
        return {"status": "mounted", "detail": str(error)}
    except (OSError, ValueError) as error:
        return {"status": "unavailable", "detail": str(error)}
    return {"status": "clear"}


def persist_report(state, report):
    folder = state.parent / "shutdown-reports"
    try:
        if folder.resolve() != folder.absolute() or folder.resolve().is_relative_to("/investigation"):
            raise ValueError("unsafe shutdown report directory")
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        stream = tempfile.NamedTemporaryFile(dir=folder, prefix="shutdown-", suffix=".json",
                                             mode="w", encoding="utf-8", delete=False)
    except (OSError, ValueError):
        stream = tempfile.NamedTemporaryFile(prefix="vigil-shutdown-", suffix=".json",
                                             mode="w", encoding="utf-8", delete=False, dir="/tmp")
    with stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return Path(stream.name)


def session_record(state, identifier):
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("invalid session identifier")
    folder = state.parent / "sessions"
    if folder.resolve() != folder.absolute() or folder.resolve().is_relative_to("/investigation"):
        raise ValueError("unsafe session directory")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder / f"{identifier}.json"


def write_state(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".session-", delete=False,
                                     mode="w", encoding="utf-8") as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def boot_identity():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def pending_sessions(folder):
    unresolved = []
    boot = boot_identity()
    for path in folder.glob("*.json"):
        try:
            record = json.loads(path.read_text())
            if record["status"] == "closed":
                continue
            owner = receipt_path(record["pid"])
            if owner and owner.name == record.get("owner") and record.get("boot", boot) == boot:
                continue
            unresolved.append(path.name)
        except (OSError, ValueError, KeyError, TypeError):
            unresolved.append(path.name)
    return unresolved


def prepare_previous_report(state, name, candidates):
    if not re.fullmatch(r"[0-9a-f]{32}\.json", name):
        raise ValueError("invalid session journal")
    journal = state.parent / "sessions" / name
    entry = json.loads(journal.read_text())
    output = Path(entry.get("report", ""))
    if not output.is_file():
        language, _ = session_preferences(state)
        output = persist_report(state, {
            "exit_status": 1, "error": "", "language": language, "hotplug": {"status": "unavailable"},
            "mounts": mount_check(), "session": entry["session"], "journal": str(journal),
            "snapshot": entry.get("snapshot"), "previous_unresolved": candidates,
        })
        entry.update(status="unresolved", report=str(output))
        write_state(journal, entry)
    return output


def review_previous(state, candidates, preferred):
    for name in reversed(sorted(candidates)):
        try:
            output = prepare_previous_report(state, name, candidates)
            launch_terminal([sys.executable, "-m", "vigil.session", "--review-report", str(output)],
                            preferred, detached=True)
            return
        except (OSError, ValueError, KeyError) as error:
            print(error, file=sys.stderr)


def active_runs(root, session_id):
    active = []
    for context in root.glob("*/context.json"):
        try:
            entry = json.loads(context.read_text())
            if entry.get("vigil_session") != session_id:
                continue
            age = max(0, time.time() - context.stat().st_mtime)
            if ExternalRun(context.parent, time.monotonic() - age).status() is None:
                active.append(str(entry.get("operation", context.parent.name)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return active


def guard(root, session_id):
    # Keep the authorized PID alive while the supervisor lives. On supervisor death,
    # EOF releases the pipe, but any independently tracked writer must still finish.
    sys.stdin.buffer.read()
    while active_runs(root, session_id):
        time.sleep(0.5)


def supervise(arguments, *, interface="gui", state=None):
    state = state or default_database()
    terminal_workspace = interface == "tui"
    if os.geteuid() == 0:
        print("Lancez Vigil en tant qu’utilisateur ordinaire. / Run Vigil as a regular user.",
              file=sys.stderr)
        return 1
    identifier = uuid4().hex
    started = time.monotonic()
    boot = boot_identity()
    path = supervisor_record = owner = context_path = None
    pending = []
    snapshot = ""
    operations = []
    error = ""
    caretaker = None
    waiting_terminal = False
    try:
        supervisor_record = session_record(state, identifier)
        pending = pending_sessions(supervisor_record.parent)
        if pending:
            print("Vigil · Sessions précédentes à vérifier / Previous sessions need review: "
                  + ", ".join(pending), file=sys.stderr)
        context_path = supervisor_record.with_suffix(".context")
        _, captured = capture_startup_state(state)
        snapshot = str(captured)
        owner = receipt_path(os.getpid())
        write_state(supervisor_record, {"status": "open", "pid": os.getpid(), "session": identifier,
                                        "owner": owner.name if owner else "", "boot": boot, "snapshot": snapshot})
        runs = state.parent / "terminal-runs"
        caretaker = subprocess.Popen(
            [sys.executable, "-m", "vigil.session", "--guard", str(runs), identifier],
            stdin=subprocess.PIPE, start_new_session=True,
        )
        path = receipt_path(caretaker.pid)
        environment = {**os.environ, "VIGIL_SESSION_ID": identifier, "VIGIL_SESSION_SNAPSHOT": snapshot,
                       "VIGIL_SESSION_GUARD": str(caretaker.pid), "VIGIL_SESSION_CONTEXT": str(context_path),
                       "VIGIL_SESSION_PENDING": json.dumps(pending)}
        module = "vigil.tui" if terminal_workspace else "vigil.desktop"
        child = subprocess.Popen([sys.executable, "-m", module, *arguments],
                                 env=environment, start_new_session=not terminal_workspace)

        def forward(signum, _frame):
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

        handlers = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        try:
            status = child.wait()
            operations = active_runs(runs, identifier)
        finally:
            for sig, previous in handlers.items():
                signal.signal(sig, previous)
    except (OSError, ValueError) as failure:
        status, error = 1, str(failure)
    finally:
        if caretaker is not None:
            if operations and supervisor_record and not terminal_workspace:
                _, preferred = session_preferences(state)
                try:
                    launch_terminal([sys.executable, "-m", "vigil.session", "--wait-session", str(supervisor_record)],
                                    preferred, detached=True)
                    waiting_terminal = True
                except (OSError, ValueError):
                    pass
            caretaker.stdin.close()
            caretaker.wait()
    context = {}
    if context_path:
        try:
            context = json.loads(context_path.read_text())
        except (OSError, ValueError):
            pass
    language, preferred = session_preferences(state)
    if terminal_workspace:
        language = context.get("language") or language
    hotplug = read_receipt(path)
    try:
        release = version("vigil-dfir")
    except PackageNotFoundError:
        release = "2.0"
    report = {"exit_status": status, "error": error, "language": language, "hotplug": hotplug,
              "mounts": mount_check(), "session": identifier, "snapshot": snapshot,
              "operator": context.get("operator"), "case": context.get("case"),
              "receipt": str(path) if path else None, "journal": str(supervisor_record) if supervisor_record else None,
              "version": release, "closed_at": datetime.now(timezone.utc).astimezone().isoformat(),
              "duration": round(time.monotonic() - started, 1),
              "operations_at_exit": operations, "previous_unresolved": pending,
              "interface": interface}
    try:
        output = persist_report(state, report)
        if supervisor_record:
            unresolved = (
                hotplug["status"] in {"pending", "error"}
                or (path is not None and status != 0 and hotplug["status"] == "unavailable")
                or any(row.get("state") in {"error", "unverified"} for row in hotplug.get("devices", []))
            )
            write_state(supervisor_record, {"status": "unresolved" if unresolved else "closed",
                                            "session": identifier, "report": str(output), "snapshot": snapshot,
                                            "pid": os.getpid(), "owner": owner.name if owner else "", "boot": boot})
    except OSError:
        if terminal_workspace:
            show_compact_report(report, None)
        else:
            show_report(report, None, interactive=sys.stdin.isatty())
    else:
        if terminal_workspace:
            show_compact_report(report, output)
            return status if status >= 0 else 128 - status
        try:
            if not waiting_terminal:
                launch_terminal([sys.executable, "-m", "vigil.session", "--show-report", str(output)],
                            preferred, detached=True)
        except (OSError, ValueError):
            show_report(report, output, interactive=sys.stdin.isatty())
    return status if status >= 0 else 128 - status


def clean(text):
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(text))


def terminal_style(text, color):
    if sys.stdout.isatty() and os.environ.get("TERM") not in {None, "dumb"} and "NO_COLOR" not in os.environ:
        return f"\033[{color}m{text}\033[0m"
    return text


def show_hotplug(report, tr):
    status = report["status"]
    if status == "other_session":
        print(terminal_style(tr("Une autre session Vigil est ouverte. Sa protection reste active.",
                                "Another Vigil session is open. Its protection remains active."), "93"))
        return False
    if status != "complete":
        messages = {
            "not_activated": tr("Protection non activée pour cette session.", "Protection was not activated for this session."),
            "not_installed": tr("Assistant de protection absent.", "Protection helper is not installed."),
            "unavailable": tr("Aucun reçu de restauration vérifiable.", "No verifiable recovery receipt."),
            "pending": tr("Restauration encore en cours.", "Recovery still in progress."),
            "error": tr("La restauration a échoué.", "Recovery failed."),
        }
        print(terminal_style(messages.get(status, messages["unavailable"]), "93"))
        if report.get("detail"):
            print("  " + clean(report["detail"]))
        return status == "error"
    devices = report.get("devices", [])
    failed = False
    if not devices:
        print(terminal_style(tr("Aucun mode périphérique à rétablir.", "No device mode to restore."), "92"))
    for row in devices:
        state = row.get("state")
        device = clean(row["device"])
        mode = "RO" if row.get("mode") == 1 else "RW"
        if state == "restored":
            text = tr(f"Mode {mode} confirmé, exclusion Vigil retirée.",
                      f"{mode} mode confirmed, Vigil exclusion removed.")
            if row.get("os_ignored"):
                text += " " + tr("UDisks ignore toujours ce support selon les règles du poste.",
                                 "UDisks still ignores this device under host rules.")
            color = "92"
        elif state == "absent":
            text, color = tr("Support absent ou remplacé.", "Device absent or replaced."), "93"
        else:
            text, color = tr("Restauration non confirmée.", "Recovery not confirmed."), "91"
            failed = True
        report_line({"92": "OK", "93": "SKIP", "91": "FAIL"}[color], f"{device} · {text}")
        if row.get("detail"):
            print("  " + clean(row["detail"]))
    return failed


def report_line(status, text):
    colors = {"OK": "92", "INFO": "96", "WARN": "93", "FAIL": "91",
              "SKIP": "90", "RUN": "95", "WAIT": "93"}
    print(terminal_style(f"[ {status:^4} ]", colors[status]) + " " + text)


def show_report(report, path, *, interactive):
    def tr(fr, en):
        return en if report["language"] == "en" else fr

    show_logo()
    print(terminal_style("━" * 52 + "\n" + tr("  Vigil · Nettoyage et restauration système",
                                                "  Vigil · Session Cleanup & System Recovery") + "\n" + "━" * 52, "1;96"))
    for key, label in (
        ("session", tr("Session", "Session")), ("version", tr("Version", "Version")),
        ("closed_at", tr("Fermeture", "Closed")), ("operator", tr("Opérateur", "Operator")),
        ("case", tr("Affaire", "Case")), ("snapshot", tr("Instantané initial", "Initial snapshot")),
        ("journal", tr("Journal de session", "Session journal")),
    ):
        if report.get(key):
            report_line("INFO", f"{label} · {clean(report[key])}")
    for operation in report.get("operations_at_exit", []):
        report_line("WAIT", tr("Opération active à la fermeture", "Operation active at exit")
                    + f" · {clean(operation)}")
    for previous in report.get("previous_unresolved", []):
        report_line("WARN", tr("Session antérieure à vérifier", "Previous session needs review") + f" · {previous}")
    status = report["exit_status"]
    if status == 0:
        report_line("OK", tr("Session terminée (code 0).", "Session ended (status 0)."))
    else:
        reason = f"signal {-status}" if status < 0 else tr(f"code {status}", f"status {status}")
        report_line("FAIL", tr(f"Arrêt inattendu ({reason}).", f"Unexpected exit ({reason})."))
    if report["error"]:
        print("  " + clean(report["error"]))
    mounts = report["mounts"]
    if mounts["status"] == "clear":
        print(terminal_style(tr("/investigation et /stockage sont démontés.",
                                "/investigation and /stockage are unmounted."), "92"))
    else:
        print(terminal_style(tr("Montages Vigil à vérifier.", "Check the Vigil mounts."), "93"))
        for line in mounts.get("detail", "").splitlines():
            print("  " + clean(line))
    print("\n" + terminal_style(tr("Gestion des périphériques", "Device management"), "1;96"))
    hotplug = report["hotplug"]
    if hotplug["status"] == "pending" and report.get("receipt"):
        hotplug = read_receipt(Path(report["receipt"]), wait=0)
    retry = show_hotplug(hotplug, tr)
    states = [row.get("state") for row in hotplug.get("devices", [])]
    print("\n" + terminal_style(tr("Résumé", "Summary"), "1;96"))
    counts = (states.count("restored"), states.count("absent"),
              states.count("error") + states.count("unverified"))
    report_line("INFO", tr(f"Vérifiés : {counts[0]} · Ignorés : {counts[1]} · Non confirmés : {counts[2]}",
                          f"Verified: {counts[0]} · Skipped: {counts[1]} · Unconfirmed: {counts[2]}"))
    if "duration" in report:
        report_line("INFO", tr(f"Durée de session : {report['duration']} s",
                              f"Session duration: {report['duration']} s"))
    if mounts["status"] != "clear" or retry or hotplug["status"] in {"pending", "unavailable", "error"}:
        report_line("WARN", tr("Restauration incomplète ou non vérifiable.", "Recovery incomplete or unverifiable."))
    print(tr("Le contrôle couvre les modes et exclusions enregistrés par Vigil.",
             "This check covers the modes and exclusions recorded by Vigil."))
    print(tr("Les règles propres à l’OS restent en vigueur.", "The host operating system rules remain in effect."))
    if path is not None:
        print(f"\n{tr('Rapport', 'Report')} · {path}")
    else:
        print(tr("Rapport non enregistré sur disque.", "Report was not saved to disk."))
    if not interactive:
        return
    try:
        can_retry = HELPER.is_file() and mounts["status"] == "clear" and (
            retry or hotplug["status"] == "pending" or (status != 0 and hotplug["status"] == "unavailable")
        )
        if can_retry:
            answer = input(tr("Entrée pour fermer, R pour retenter la restauration Vigil : ",
                              "Enter to close, R to retry Vigil recovery: "))
            if answer.strip().lower() != "r":
                return
            recover(report, path, tr)
        input(tr("Appuyez sur ENTRÉE pour fermer ce terminal… ", "Press Enter to close this terminal… "))
    except (EOFError, KeyboardInterrupt):
        pass


def recover(report, path, tr):
    if mount_check()["status"] != "clear":
        report_line("WARN", tr("Des montages Vigil bloquent la restitution.", "Vigil mounts block recovery."))
        return
    report_line("RUN", tr("Vérification et restitution ciblées…", "Checking and restoring recorded changes…"))
    try:
        result = subprocess.run(["/usr/bin/sudo", "--", str(HELPER), "recover"], stdout=subprocess.PIPE,
                                text=True, check=True)
        recovery = json.loads(result.stdout)
        show_hotplug(recovery, tr)
        report["recovery_retry"] = recovery
        if report.get("journal") and recovery["status"] == "complete" and all(
            row.get("state") in {"restored", "absent"} for row in recovery.get("devices", [])
        ):
            journal = Path(report["journal"])
            state = default_database()
            if journal == session_record(state, report["session"]):
                entry = json.loads(journal.read_text())
                if entry.get("status") == "unresolved":
                    entry["status"] = "closed"
                    write_state(journal, entry)
        if path is not None:
            with path.open("w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError, subprocess.SubprocessError):
        print(terminal_style(tr("Nouvelle tentative non confirmée.", "Recovery retry not confirmed."), "91"))


def wait_session(journal):
    language, _ = session_preferences(default_database())
    message = ("Waiting for tracked operations to finish…" if language == "en"
               else "Attente de la fin des opérations suivies…")
    report_line("WAIT", message)
    while True:
        try:
            entry = json.loads(journal.read_text())
            if entry.get("report"):
                path = Path(entry["report"])
                return show_report_file(path)
            owner = receipt_path(entry["pid"])
            if not owner or owner.name != entry["owner"]:
                break
        except (OSError, ValueError, KeyError):
            break
        time.sleep(0.5)
    report_line("WARN", "Vigil · Supervisor unavailable / Superviseur indisponible")
    if sys.stdin.isatty():
        try:
            input("Entrée / Press Enter ")
        except (EOFError, KeyboardInterrupt):
            pass
    return 1


def show_compact_report(report, path, *, interactive=False):
    def tr(fr, en):
        return en if report["language"] == "en" else fr

    hotplug = report.get("recovery_retry", report["hotplug"])
    failures = [row for row in hotplug.get("devices", []) if row.get("state") in {"error", "unverified"}]
    mounted = report["mounts"]["status"] != "clear"
    retry = bool(failures) or hotplug["status"] in {"error", "pending", "unavailable"}
    if mounted:
        print(tr("Montages encore présents ou non vérifiés.", "Mounts still present or unverified."))
    if retry:
        print(tr("Restitution USB à vérifier.", "USB recovery needs review."))
        if detail := hotplug.get("detail"):
            print(clean(detail))
        for row in failures:
            print(f"  {clean(row.get('device'))} · {clean(row.get('detail') or row.get('state'))}")
    elif hotplug["status"] == "complete":
        print(tr("Protection USB précédente rétablie.", "Previous USB state restored."))
    elif hotplug["status"] == "other_session":
        print(tr("Protection USB conservée pour l’autre session Vigil.", "USB protection retained for the other Vigil session."))
    else:
        print(tr("Session Vigil fermée.", "Vigil session closed."))
    if path is not None:
        print(f"{tr('Bilan', 'Report')} · {path}")
    if interactive and retry and not mounted and HELPER.is_file():
        try:
            if input(tr("R : retenter la restitution · Entrée : fermer : ",
                        "R: retry recovery · Enter: close: ")).strip().lower() == "r":
                recover(report, path, tr)
        except (EOFError, KeyboardInterrupt):
            pass


def show_report_file(path, *, review=False):
    report = json.loads(path.read_text(encoding="utf-8"))
    if review:
        report.setdefault("mounts_at_exit", report["mounts"])
        report["mounts"] = mount_check()
    if os.environ.get("VIGIL_EMBEDDED_TERMINAL") == "1":
        show_compact_report(report, path, interactive=sys.stdin.isatty())
    else:
        show_report(report, path, interactive=sys.stdin.isatty())
    hotplug = report.get("recovery_retry", report["hotplug"])
    return int(report["mounts"]["status"] != "clear" or hotplug["status"] in {"pending", "error", "unavailable"}
               or any(row.get("state") in {"error", "unverified"} for row in hotplug.get("devices", [])))


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--guard":
        guard(Path(sys.argv[2]), sys.argv[3])
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "--wait-session":
        return wait_session(Path(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] in {"--show-report", "--review-report"}:
        return show_report_file(Path(sys.argv[2]), review=sys.argv[1] == "--review-report")
    return supervise(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
