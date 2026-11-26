"""Local process lifecycle and PTY transport for built-in adapters."""
import errno
import fcntl
import os
import pty
import signal
import struct
import subprocess
import sys
import termios
from pathlib import Path


class TerminalProcess:
    """Own a single child session and expose its terminal to the caller."""

    def __init__(self, argv: list[str], cwd: Path, env: dict[str, str]):
        if not argv or not Path(argv[0]).is_absolute():
            raise ValueError("an absolute executable path is required")
        master, slave = pty.openpty()
        self.master = master
        try:
            self.resize(24, 80)
            child = Path(__file__).with_name("_pty_child.py")
            self.process = subprocess.Popen(
                [sys.executable, "-I", str(child), *argv],
                stdin=slave, stdout=slave, stderr=slave, cwd=cwd,
                env=env, start_new_session=True,
            )
        except BaseException:
            os.close(master)
            raise
        finally:
            os.close(slave)

    def resize(self, rows: int, columns: int):
        if not (1 <= rows <= 65535 and 1 <= columns <= 65535):
            raise ValueError("invalid terminal dimensions")
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

    def read(self, size: int = 65536):
        try:
            return os.read(self.master, size)
        except OSError as error:
            if error.errno != errno.EIO:
                raise
            return b""

    def write(self, data: bytes):
        return os.write(self.master, data)

    def cancel(self, timeout: float = 2):
        if self.process.poll() is not None:
            return self.process.returncode
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        return self.process.wait()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        try:
            self.cancel()
        finally:
            os.close(self.master)
