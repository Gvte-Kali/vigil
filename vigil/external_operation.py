"""Record the real command result inside the external terminal."""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def process_start(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    if fields[0] == "Z":
        raise ProcessLookupError(pid)
    return fields[19]


def write_status(directory, name, value):
    temporary = directory / f".{name}"
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(directory / name)


def main():
    directory = Path(sys.argv[1])
    args = sys.argv[2:]
    context = json.loads((directory / "context.json").read_text(encoding="utf-8"))
    interface = args.pop(0).partition("=")[2] if args and args[0] in {"--interface=gui", "--interface=tui"} else None
    if interface is None:
        interface = "tui" if os.environ.get("VIGIL_EMBEDDED_TERMINAL") == "1" else "gui"
    language = "en" if context.get("language") == "en" else "fr"
    environment = {**os.environ, "VIGIL_LANG": language}
    if interface == "tui":
        environment["VIGIL_EMBEDDED_TERMINAL"] = "1"
    else:
        environment.pop("VIGIL_EMBEDDED_TERMINAL", None)
    started = {"pid": os.getpid(), "start": process_start(os.getpid())}
    write_status(directory, "started.json", started)
    operation = None
    interrupted = None

    def interrupt(signum, _frame):
        nonlocal interrupted
        interrupted = signum
        if operation is not None and operation.poll() is None:
            operation.send_signal(signum)

    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, interrupt)
    try:
        operation = subprocess.Popen(args, env=environment)
        try:
            started["child"] = {"pid": operation.pid, "start": process_start(operation.pid)}
            write_status(directory, "started.json", started)
        except (OSError, ValueError, IndexError):
            pass
        if interrupted is not None and operation.poll() is None:
            operation.send_signal(interrupted)
        result = operation.wait()
        status = result if result >= 0 else 128 - result
    except OSError as error:
        print(str(error), file=sys.stderr)
        status = 127
    write_status(directory, "result.json", {"exit_code": status})
    label = "Exit code" if language == "en" else "Code de sortie"
    print(f"\n{label} : {status}", flush=True)
    if sys.stdin.isatty() and interrupted is None and interface == "gui":
        try:
            input("Press Enter" if language == "en" else "Appuyez sur Entrée")
        except EOFError:
            pass
    return status


if __name__ == "__main__":
    sys.exit(main())
