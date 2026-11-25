"""Use the shared script logo in Vigil's Python entry points."""
import subprocess
import sys
from pathlib import Path

from .entity import legacy_base


def show_logo(*, stream=None):
    if stream is None:
        stream = sys.stdout

    base = legacy_base()
    library = base / "scripts/lib/vigil-terminal.sh"
    logo = base / "data/icons/vigil.svg"
    if not library.is_file():
        shared = Path(sys.prefix) / "share/vigil"
        library = shared / "scripts/vigil-terminal.sh"
        logo = shared / "vigil.svg"

    if library.is_file():
        subprocess.run(
            ["/bin/sh", "-c", '. "$1"; vigil_logo "$2"', "vigil", str(library), str(logo)],
            stdout=stream,
            check=False,
        )
    else:
        print("Vigil", file=stream)
