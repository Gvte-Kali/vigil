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
    write_status(directory, "started.json", {"pid": os.getpid(), "start": process_start(os.getpid())})
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
        operation = subprocess.Popen(args)
        if interrupted is not None and operation.poll() is None:
            operation.send_signal(interrupted)
        result = operation.wait()
        status = result if result >= 0 else 128 - result
    except OSError as error:
        print(str(error), file=sys.stderr)
        status = 127
    write_status(directory, "result.json", {"exit_code": status})
    print(f"\nCode de sortie / Exit code: {status}", flush=True)
    if sys.stdin.isatty() and interrupted is None:
        try:
            input("Entrée / Enter")
        except EOFError:
            pass
    return status


if __name__ == "__main__":
    sys.exit(main())
