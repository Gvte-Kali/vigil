"""Qt terminal bound to one local PTY command at a time."""
import os
from pathlib import Path

import pyte
from PySide6.QtCore import QSocketNotifier, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from .runner import TerminalProcess


class TerminalPanel(QPlainTextEdit):
    completed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.session = None
        self.notifier = None
        self.output_ended = False
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.check_exit)

    def start(self, arguments):
        self.screen = pyte.HistoryScreen(80, 24, history=500)
        self.stream = pyte.ByteStream(self.screen)
        self.session = TerminalProcess(
            arguments, Path.home(),
            {"PATH": os.defpath, "HOME": str(Path.home()), "TERM": "xterm",
             "LANG": os.environ.get("LANG", "C.UTF-8")},
        )
        self.output_ended = False
        self.resize_terminal()
        self.clear()
        self.notifier = QSocketNotifier(self.session.master, QSocketNotifier.Type.Read, self)
        self.notifier.activated.connect(self.read_ready)
        self.timer.start()
        self.setFocus()

    def read_ready(self, *_):
        data = self.session.read()
        if not data:
            self.notifier.setEnabled(False)
            self.output_ended = True
            self.check_exit()
            return
        self.stream.feed(data)
        history = (
            "".join(line[index].data for index in range(self.screen.columns)).rstrip()
            for line in self.screen.history.top
        )
        self.setPlainText("\n".join([*history, *(line.rstrip() for line in self.screen.display)]).rstrip())
        self.moveCursor(QTextCursor.MoveOperation.End)

    def check_exit(self):
        code = self.session.process.poll()
        if code is None or not self.output_ended:
            return
        self.timer.stop()
        self.notifier.setEnabled(False)
        self.notifier.deleteLater()
        self.session.__exit__()
        self.session = self.notifier = None
        self.completed.emit(code)

    def resize_terminal(self):
        if self.session is None:
            return
        metrics = self.fontMetrics()
        columns = max(20, min(250, self.viewport().width() // metrics.horizontalAdvance("M")))
        rows = max(6, min(100, self.viewport().height() // metrics.height()))
        self.screen.resize(lines=rows, columns=columns)
        self.session.resize(rows, columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_terminal()

    def keyPressEvent(self, event):
        if self.session is not None and not self.output_ended:
            keys = Qt.Key
            codes = {
                keys.Key_Return: b"\r", keys.Key_Enter: b"\r", keys.Key_Backspace: b"\x7f",
                keys.Key_Up: b"\x1b[A", keys.Key_Down: b"\x1b[B",
                keys.Key_Right: b"\x1b[C", keys.Key_Left: b"\x1b[D",
            }
            data = codes.get(event.key()) or event.text().encode()
            if event.key() == keys.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                data = b"\x03"
            if data:
                try:
                    self.session.write(data)
                except OSError:
                    pass
                return
        super().keyPressEvent(event)
