"""Common Textual dialogs and embedded PTY for operator workflows."""
import asyncio
import codecs
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
                yield Static(Text(label))
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

    def __init__(self, title, tr, argv, language, tracked=None):
        super().__init__()
        self.title_text, self.tr, self.argv, self.language = title, tr, argv, language
        self.tracked = tracked
        self.terminal = None
        self.status = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog operation"):
            yield Static(Text(self.title_text), id="operation-title", classes="heading")
            yield ProgressBar(total=None, show_percentage=False, show_eta=False, id="operation-progress")
            yield RichLog(markup=False, highlight=False, wrap=True, max_lines=1500, id="operation-log")
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
                pending = ""
                # Preserve prompts that do not end with a newline.
                while True:
                    readable = await asyncio.to_thread(select.select, [terminal.master], [], [], 0.15)
                    self.update_echo()
                    if not readable[0]:
                        if pending:
                            self.write_output(log, pending.replace("\r", "\n"))
                            pending = ""
                        continue
                    data = terminal.read()
                    if not data:
                        break
                    pending += decoder.decode(data).replace("\r\n", "\n")
                    records = pending.replace("\r", "\n").split("\n")
                    pending = records.pop()
                    for record in records:
                        self.write_output(log, record)
                if pending:
                    self.write_output(log, pending)
                self.status = await asyncio.to_thread(terminal.process.wait)
        except (OSError, ValueError) as error:
            log.write(Text(str(error), style="bold red"))
            self.status = 1
            if self.tracked and not (self.tracked.directory / "started.json").exists():
                from .external_operation import write_status

                write_status(self.tracked.directory, "result.json", {"exit_code": self.status})
        finally:
            self.terminal = None
            self.query_one(Input).disabled = True
            self.query_one("#interrupt", Button).disabled = True
            self.query_one("#operation-close", Button).disabled = False
            self.query_one(ProgressBar).update(total=1, progress=1)
            self.query_one("#operation-title", Static).update(Text(
                f"{self.title_text} · {self.tr('Code de sortie', 'Exit code')} : {self.status}"
            ))
            self.query_one("#operation-close", Button).focus()

    def update_echo(self):
        try:
            echo = termios.tcgetattr(self.terminal.master)[3] & termios.ECHO
        except termios.error:
            return
        self.query_one(Input).password = not echo

    def write_output(self, log, record):
        text = Text.from_ansi(record)
        log.write(text)
        if re.search(r"(?i)copie|copy|sha-256|vérification|verifying", text.plain):
            if match := re.search(r"(?<![\d.])(\d{1,3}(?:[.,]\d+)?)\s*%", text.plain):
                percent = float(match.group(1).replace(",", "."))
                if 0 <= percent <= 100:
                    self.query_one(ProgressBar).update(total=100, progress=percent)

    def on_input_submitted(self, event):
        if self.terminal:
            self.terminal.write(event.value.encode() + b"\n")
            event.input.clear()

    def on_button_pressed(self, event):
        if event.button.id == "operation-close" and self.status is not None:
            self.dismiss(self.status)
        elif event.button.id == "interrupt" and self.terminal is not None:
            self.terminal.write(b"\x03")
