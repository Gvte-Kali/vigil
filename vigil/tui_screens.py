"""Common Textual dialogs and embedded PTY for operator workflows."""
import asyncio
import codecs
import json
import os
import re
import termios
import select
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ProgressBar, RichLog, Select, Static

from .runner import TerminalProcess


PROGRESS_PREFIX = "\x1eVIGIL_PROGRESS "
TERMINAL_BREAK = re.compile(r"\r\n|\n|\r(?=.)", re.DOTALL)


class TerminalLines:
    """Keep the unfinished terminal line separate from the committed log."""

    def __init__(self):
        self.pending = ""

    def feed(self, text):
        source = self.pending + text
        records = []
        start = 0
        for separator in TERMINAL_BREAK.finditer(source):
            if separator.group() != "\r":
                records.append(source[start:separator.start()])
            start = separator.end()
        self.pending = source[start:]
        return records


class OperationStage(Horizontal):
    def __init__(self):
        super().__init__(classes="operation-stage")

    def compose(self) -> ComposeResult:
        yield Static()
        yield ProgressBar(total=None, show_eta=False)

    def update(self, label, percent, detail, done):
        self.query_one(Static).update(Text(label + (f" · {detail}" if detail else ""),
                                           no_wrap=True, overflow="ellipsis"))
        self.query_one(ProgressBar).update(total=100 if percent is not None or done else None,
                                           progress=100 if done else percent or 0)


class Form(ModalScreen):
    """Confirm a workflow and collect its parameters."""

    BINDINGS = [("escape", "cancel", "Annuler / Cancel")]

    def __init__(self, title, tr, fields=(), *, choices=(), message=""):
        super().__init__()
        self.title_text, self.tr, self.fields, self.choices, self.message = title, tr, fields, choices, message

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog"):
            yield Static(Text(self.title_text), classes="heading")
            if self.message:
                yield Static(Text(self.message))
            if self.choices:
                yield Select(self.choices, value=self.choices[0][1], allow_blank=False, id="form-choice")
            for key, label, value in self.fields:
                yield Static(Text(label), classes="form-field")
                yield Input(value, id=f"field-{key}")
            with Horizontal(classes="actions"):
                yield Button(self.tr("Annuler", "Cancel"), id="cancel")
                yield Button(self.tr("Valider", "Confirm"), id="confirm", variant="primary")

    def on_mount(self):
        if self.fields:
            self.query_one(Input).focus()
        else:
            self.query_one("#cancel").focus()

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event):
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "confirm":
            self.confirm()

    def on_input_submitted(self):
        self.confirm()

    def confirm(self):
        fields = {key: self.query_one(f"#field-{key}", Input).value.strip() for key, _, _ in self.fields}
        if self.choices:
            fields["choice"] = self.query_one(Select).value
        self.dismiss(fields)


class Operation(ModalScreen):
    """Display an existing console workflow with a controlling terminal."""

    COMPONENT_CLASSES = ModalScreen.COMPONENT_CLASSES | {"operation--error"}

    def __init__(self, title, tr, argv, language, tracked=None):
        super().__init__()
        self.title_text, self.tr, self.argv, self.language = title, tr, argv, language
        self.tracked = tracked
        self.terminal = None
        self.status = None
        self.stages = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog operation"):
            yield Static(Text(self.title_text), id="operation-title", classes="heading")
            yield VerticalScroll(id="operation-stages")
            yield RichLog(markup=False, highlight=False, wrap=True, max_lines=1500, id="operation-log")
            yield Static(id="operation-live")
            yield Input(placeholder=self.tr("Réponse puis Entrée", "Type a response and press Enter"), id="operation-input")
            with Horizontal(classes="actions"):
                yield Button(self.tr("Interrompre", "Interrupt"), id="interrupt")
                yield Button(self.tr("Fermer", "Close"), id="operation-close", disabled=True)

    def on_mount(self):
        self.query_one(Input).focus()
        self.run_operation()

    def on_resize(self):
        if self.terminal:
            self.terminal.resize(max(1, self.size.height - 8), max(1, self.size.width - 8))

    @work
    async def run_operation(self):
        log = self.query_one(RichLog)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            with TerminalProcess(self.argv, Path.cwd(), dict(os.environ, VIGIL_LANG=self.language, VIGIL_EMBEDDED_TERMINAL="1")) as terminal:
                self.terminal = terminal
                self.on_resize()
                lines = TerminalLines()
                while True:
                    readable = await asyncio.to_thread(select.select, [terminal.master], [], [], 0.15)
                    self.update_echo()
                    if not readable[0]:
                        continue
                    data = terminal.read()
                    if not data:
                        break
                    for record in lines.feed(decoder.decode(data)):
                        await self.write_output(log, record)
                    pending = lines.pending.rstrip("\r")
                    self.query_one("#operation-live", Static).update(
                        Text() if pending.startswith("\x1e") else Text.from_ansi(pending)
                    )
                for record in lines.feed(decoder.decode(b"", final=True) + "\n"):
                    if record:
                        await self.write_output(log, record)
                self.query_one("#operation-live", Static).update("")
                self.status = await asyncio.to_thread(terminal.process.wait)
        except (OSError, ValueError) as error:
            log.write(Text(str(error), style=self.get_component_rich_style("operation--error")))
            self.status = 1
            if self.tracked and not (self.tracked.directory / "started.json").exists():
                from .external_operation import write_status

                write_status(self.tracked.directory, "result.json", {"exit_code": self.status})
        finally:
            self.terminal = None
            for stage in self.stages.values():
                bar = stage.query_one(ProgressBar)
                if bar.total is None:
                    bar.update(total=100, progress=0)
                    stage.add_class("incomplete")
            self.query_one(Input).disabled = True
            self.query_one("#interrupt", Button).disabled = True
            self.query_one("#operation-close", Button).disabled = False
            title = self.query_one("#operation-title", Static)
            title.set_class(self.status != 0, "operation-failed")
            title.update(Text(
                f"{self.title_text} · {self.tr('Code de sortie', 'Exit code')} : {self.status}"
            ))
            self.query_one("#operation-close", Button).focus()

    def update_echo(self):
        try:
            echo = termios.tcgetattr(self.terminal.master)[3] & termios.ECHO
        except termios.error:
            return
        self.query_one(Input).password = not echo

    async def write_output(self, log, record):
        if not record.startswith(PROGRESS_PREFIX):
            log.write(Text.from_ansi(record))
            return
        try:
            event = json.loads(record[len(PROGRESS_PREFIX):])
            key = event["stage"]
            percent = event.get("percent")
            detail = event.get("detail", "")
            done = event.get("done") is True
            if not isinstance(key, str) or not 1 <= len(key) <= 160 or not isinstance(detail, str):
                raise ValueError
            if percent is not None and (not isinstance(percent, (int, float)) or not 0 <= percent <= 100):
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        labels = {
            "clamav": self.tr("Scan ClamAV", "ClamAV scan"),
            "usb": self.tr("Détection USB", "USB detection"),
            "usb-source": self.tr("Détection USB · source", "USB detection · source"),
            "usb-destination": self.tr("Détection USB · destination", "USB detection · destination"),
        }
        if key not in self.stages:
            stage = OperationStage()
            self.stages[key] = stage
            panel = self.query_one("#operation-stages", VerticalScroll)
            await panel.mount(stage)
            panel.scroll_end(animate=False)
        self.stages[key].update(labels.get(key, key), percent, detail[:160], done)

    def on_input_submitted(self, event):
        if self.terminal:
            self.terminal.write(event.value.encode() + b"\n")
            event.input.clear()

    def on_button_pressed(self, event):
        if event.button.id == "operation-close" and self.status is not None:
            self.dismiss(self.status)
        elif event.button.id == "interrupt" and self.terminal is not None:
            self.terminal.write(b"\x03")
