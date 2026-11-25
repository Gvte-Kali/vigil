"""Resolve and launch external terminals independently of Qt."""
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

TERMINALS = {
    "xdg-terminal-exec": (),
    "kitty": ("-o", "initial_window_height=44c"),
    "alacritty": ("-o", "window.dimensions={ columns = 80, lines = 44 }", "-e"),
    "foot": ("--window-size-chars=80x44",),
    "konsole": ("-p", "TerminalRows=44", "-e"),
    "gnome-terminal": ("--geometry=80x44", "--"),
    "xfce4-terminal": ("--geometry=80x44", "--execute"),
    "xterm": ("-geometry", "80x44", "-e"),
}
MISSING_TERMINAL = "Aucun terminal compatible trouvé / No compatible external terminal found."


def terminal_commands(arguments, preferred=""):
    if not arguments or any(not isinstance(arg, str) or "\0" in arg for arg in arguments):
        raise ValueError("invalid terminal arguments")
    if preferred and preferred not in TERMINALS:
        raise ValueError("unknown terminal preference")
    candidates = (preferred, *TERMINALS) if preferred else TERMINALS
    for name in dict.fromkeys(candidates):
        if name == "foot" and not os.environ.get("WAYLAND_DISPLAY"):
            continue
        if name == "xterm" and os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
            continue
        executable = shutil.which(name)
        if executable:
            yield [executable, *TERMINALS[name], *arguments]


def terminal_command(arguments, preferred=""):
    command = next(terminal_commands(arguments, preferred), None)
    if command is None:
        raise FileNotFoundError(MISSING_TERMINAL)
    return command


def launch_terminal(arguments, preferred="", *, detached=False):
    if not detached:
        return subprocess.Popen(terminal_command(arguments, preferred))
    # A failed desktop emulator should not prevent the remaining candidates from being tried.
    failures = []
    for command in terminal_commands(arguments, preferred):
        try:
            terminal = subprocess.Popen(command, start_new_session=True)
            try:
                status = terminal.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                return terminal
            if status == 0:  # Some frontends delegate to an existing terminal process.
                return terminal
            failures.append(f"{command[0]} ({status})")
        except OSError as error:
            failures.append(str(error))
    if failures:
        raise OSError(MISSING_TERMINAL + " " + "; ".join(failures))
    raise FileNotFoundError(MISSING_TERMINAL)


@dataclass(frozen=True)
class ExternalRun:
    directory: Path
    requested_at: float

    def status(self):
        from .external_operation import process_start

        try:
            return json.loads((self.directory / "result.json").read_text())["exit_code"]
        except FileNotFoundError:
            pass
        try:
            started = json.loads((self.directory / "started.json").read_text())
        except FileNotFoundError:
            return None if time.monotonic() - self.requested_at < 30 else "unknown"
        for process in (started, started.get("child")):
            if process is None:
                continue
            try:
                if process_start(process["pid"]) == process["start"]:
                    return None
            except (OSError, ValueError, IndexError):
                pass
        return "unknown"


def launch_tracked(arguments, root, context, preferred=""):
    if root.resolve() != root.absolute() or root.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid terminal result directory")
    run_id = uuid4().hex
    directory = root / run_id
    directory.mkdir(mode=0o700, parents=True)
    (directory / "context.json").write_text(
        json.dumps({**context, "run_id": run_id, "arguments": arguments,
                    "vigil_session": os.environ.get("VIGIL_SESSION_ID")}, ensure_ascii=False),
        encoding="utf-8",
    )
    runner = Path(__file__).resolve().with_name("external_operation.py")
    try:
        launch_terminal([sys.executable, "-I", str(runner), str(directory), *arguments], preferred)
    except OSError:
        (directory / "result.json").write_text('{"exit_code": "launch_failed"}', encoding="utf-8")
        raise
    return ExternalRun(directory, time.monotonic())


def launch_script(path, *arguments):
    return launch_action(["/usr/bin/bash", path, *arguments])


def launch_action(arguments):
    wrapper = (
        '"$@"; status=$?; printf "\\nCode de sortie / Exit code: %s\\n" "$status"; '
        'read -r -p "Entrée / Enter"; exit "$status"'
    )
    return launch_terminal(["/usr/bin/bash", "-c", wrapper, "vigil", *arguments])
