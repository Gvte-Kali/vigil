"""Terminal presentation for acquisition phases, independent of block I/O."""
import os
import shutil
import sys
import time
from contextlib import contextmanager
from itertools import cycle
from threading import Event, Thread

SYNC_NOTICE = (
    "La copie logique est terminée. Vigil procède maintenant à la synchronisation des écritures "
    "en attente vers le support de destination.\n\n"
    "Cette étape peut prendre plusieurs minutes selon le volume de données, les performances du "
    "support, son interface de connexion et son système de fichiers.\n\n"
    "Ne débranchez pas le périphérique avant la fin de l’opération."
)


def interactive(stream):
    return stream.isatty() and os.environ.get("TERM") != "dumb"


def accent(text):
    return f"\033[96m{text}\033[0m" if "NO_COLOR" not in os.environ else text


def human_size(value):
    value = float(value)
    for unit in ("o", "Kio", "Mio", "Gio", "Tio", "Pio"):
        if value < 1024 or unit == "Pio":
            return f"{value:.1f} {unit}"
        value /= 1024


def duration(seconds):
    minutes, seconds = divmod(int(max(0, seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class Progress:
    def __init__(self, label, total):
        self.label = label
        self.total = total
        self.start = self.last = time.monotonic()
        self.stream = sys.stdout
        self.tty = interactive(self.stream)
        self.drawn = False

    def update(self, processed):
        now = time.monotonic()
        complete = processed == self.total
        if not complete and now - self.last < (0.25 if self.tty else 5):
            return
        self.last = now
        percent = (processed * 1000 // self.total) / 10
        volume = f"{human_size(processed)} / {human_size(self.total)}"
        bar = ""
        if self.tty and shutil.get_terminal_size((80, 24)).columns >= 58:
            filled = processed * 10 // self.total
            bar = " [" + "━" * filled + "─" * (10 - filled) + "]"
        text = f"{self.label}{bar} {percent:.1f} % · {volume}"
        elapsed = now - self.start
        if elapsed >= 3 and processed > 0:
            rate = processed / elapsed
            throughput = f" · {human_size(rate)}/s"
            if self.tty and not complete:
                throughput += f" · reste ≈ {duration((self.total - processed) / rate)}"
            if not self.tty or len(text + throughput) < shutil.get_terminal_size((80, 24)).columns:
                text += throughput
        if complete and not self.tty:
            text += f" ({processed}/{self.total} octets)"
        self.drawn = self.tty and not complete
        print(("\r\033[2K" if self.tty else "") + (accent(text) if self.tty else text), file=self.stream,
              end="" if self.drawn else "\n", flush=True)

    def finish(self):
        if self.drawn:
            print(file=self.stream, flush=True)


@contextmanager
def indeterminate(label, *, clock=time.monotonic):
    heading = f"{label}…"
    print("\n" + (accent(heading) if interactive(sys.stdout) else heading), flush=True)
    start = clock()
    if not interactive(sys.stdout):
        yield
        return
    done = Event()

    def render():
        for frame in cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if done.wait(0.25):
                return
            print(f"\r\033[2K{frame}  Temps écoulé : {duration(clock() - start)}", end="", flush=True)

    thread = Thread(target=render, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        print(f"\r\033[2KTemps écoulé : {duration(clock() - start)}", flush=True)
