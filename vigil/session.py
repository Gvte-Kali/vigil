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

from .entity import legacy_base
from .external_terminal import launch_terminal
from .shutdown_state import ShutdownBlocked, check_shutdown_state
from .storage import default_database

REPORTS = Path("/run/vigil-hotplug/reports")
HELPER = Path("/usr/local/sbin/vigil-hotplug")


def session_preferences(state):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(state.parent / "preferences" / f"{os.getuid()}.ini", encoding="utf-8")
        values = parser["General"]
        return values.get("language", "fr"), values.get("external_terminal", "")
    except (OSError, KeyError, ValueError, configparser.Error):
        return "fr", ""


def receipt_path(pid):
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return REPORTS / f"{pid}-{int(fields[19])}.json"
    except (OSError, IndexError, ValueError):
        return None


def read_receipt(path, *, wait=12):
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
            if receipt["status"] != "pending":
                return receipt
        except FileNotFoundError:
            # No activation was recorded, or the installed helper predates receipts.
            return {"status": "unavailable"}
        except (OSError, ValueError, KeyError):
            return {"status": "unavailable"}
        if time.monotonic() >= deadline:
            return {"status": "pending"}
        time.sleep(0.15)


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


def supervise(arguments):
    state = default_database()
    if os.geteuid() == 0:
        print("Lancez Vigil en tant qu’utilisateur ordinaire. / Run Vigil as a regular user.",
              file=sys.stderr)
        return 1
    path = None
    error = ""
    try:
        child = subprocess.Popen([sys.executable, "-m", "vigil.desktop", *arguments],
                                 start_new_session=True)
        path = receipt_path(child.pid)

        def forward(signum, _frame):
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

        handlers = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        try:
            status = child.wait()
        finally:
            for sig, previous in handlers.items():
                signal.signal(sig, previous)
    except OSError as failure:
        status, error = 1, str(failure)
    language, preferred = session_preferences(state)
    report = {"exit_status": status, "error": error, "language": language,
              "hotplug": read_receipt(path), "mounts": mount_check()}
    try:
        output = persist_report(state, report)
    except OSError:
        show_report(report, None, interactive=sys.stdin.isatty())
    else:
        try:
            launch_terminal([sys.executable, "-m", "vigil.session", "--show-report", str(output)], preferred)
        except (OSError, ValueError):
            show_report(report, output, interactive=sys.stdin.isatty())
    return status if status >= 0 else 128 - status


def clean(text):
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(text))


def terminal_style(text, color):
    if sys.stdout.isatty() and os.environ.get("TERM") not in {None, "dumb"} and "NO_COLOR" not in os.environ:
        return f"\033[{color}m{text}\033[0m"
    return text


def show_logo():
    library = legacy_base() / "scripts/lib/vigil-terminal.sh"
    if library.is_file():
        subprocess.run(["/bin/sh", "-c", '. "$1"; vigil_logo "$2"', "vigil", str(library),
                        str(legacy_base() / "data/icons/vigil.svg")], check=False)
        return
    logo = Path(sys.prefix) / "share/vigil/vigil.svg"
    if logo.is_file() and sys.stdout.isatty() and os.environ.get("TERM") not in {None, "dumb"} and "NO_COLOR" not in os.environ:
        try:
            subprocess.run(["chafa", "--format", "symbols", "--colors", "256", "--size", "40x20", str(logo)],
                           stderr=subprocess.DEVNULL, check=True)
            return
        except (OSError, subprocess.SubprocessError):
            pass
    print(terminal_style("Vigil", "96"))


def show_hotplug(report, tr):
    status = report["status"]
    if status == "other_session":
        print(terminal_style(tr("Une autre session Vigil est ouverte. Sa protection reste active.",
                                "Another Vigil session is open. Its protection remains active."), "93"))
        return False
    if status != "complete":
        messages = {
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
        print(terminal_style(f"{device} · {text}", color))
        if row.get("detail"):
            print("  " + clean(row["detail"]))
    return failed


def show_report(report, path, *, interactive):
    def tr(fr, en):
        return en if report["language"] == "en" else fr

    show_logo()
    print(terminal_style("━" * 52 + "\n" + tr("  Vigil · Vérification à la fermeture",
                                                "  Vigil · Shutdown checks") + "\n" + "━" * 52, "1;96"))
    status = report["exit_status"]
    if status == 0:
        print(terminal_style(tr("Session terminée (code 0).", "Session ended (status 0)."), "92"))
    else:
        reason = f"signal {-status}" if status < 0 else tr(f"code {status}", f"status {status}")
        print(terminal_style(tr(f"Arrêt inattendu ({reason}).", f"Unexpected exit ({reason})."), "91"))
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
    retry = show_hotplug(report["hotplug"], tr)
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
            retry or (status != 0 and report["hotplug"]["status"] == "unavailable")
        )
        if can_retry:
            answer = input(tr("Entrée pour fermer, R pour retenter la restauration Vigil : ",
                              "Enter to close, R to retry Vigil recovery: "))
            if answer.strip().lower() != "r":
                return
            recover(report, path, tr)
        input(tr("Appuyez sur Entrée pour fermer… ", "Press Enter to close… "))
    except (EOFError, KeyboardInterrupt):
        pass


def recover(report, path, tr):
    try:
        result = subprocess.run(["/usr/bin/sudo", "--", str(HELPER), "recover"], stdout=subprocess.PIPE,
                                text=True, check=True)
        recovery = json.loads(result.stdout)
        show_hotplug(recovery, tr)
        report["recovery_retry"] = recovery
        if path is not None:
            with path.open("w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError, subprocess.SubprocessError):
        print(terminal_style(tr("Nouvelle tentative non confirmée.", "Recovery retry not confirmed."), "91"))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--show-report":
        path = Path(sys.argv[2])
        show_report(json.loads(path.read_text(encoding="utf-8")), path, interactive=sys.stdin.isatty())
        return 0
    return supervise(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
