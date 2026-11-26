"""Textual catalogue for the shared antivirus report records."""
import asyncio
import sqlite3

from rich.text import Text
from textual import events
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static

from .antivirus_reports import antivirus_reports
from .desktop_integration import dispatch_viewing_copy
from .tui_screens import Form


class ReportTable(DataTable):
    async def _on_click(self, event: events.Click):
        row, column = (event.style.meta.get(key, -1) for key in ("row", "column"))
        if row >= 0 and column >= 0 and (event.chain == 1 or event.button == 3):
            self.move_cursor(row=row, column=column, animate=False)
            event.prevent_default()
            event.stop()
            if event.button == 3:
                self.screen.open_menu()


class AntivirusReportScreen(ModalScreen):
    BINDINGS = [("escape", "close", "Fermer / Close"),
                ("shift+f10", "menu", "Menu")]

    def __init__(self, state, tr):
        super().__init__()
        self.state, self.tr = state, tr
        self.rows = {}
        self.sort_column, self.descending = 0, True

    def compose(self):
        t = self.tr
        with Vertical(classes="dialog antivirus-reports"):
            yield Static(t("Rapports antivirus", "Antivirus reports"), classes="heading")
            yield Input(placeholder=t("Rechercher un rapport", "Search reports"), id="antivirus-search")
            yield ReportTable(cursor_type="row", id="antivirus-report-table")
            yield Static(id="antivirus-report-error")
            with Horizontal(classes="actions"):
                yield Button(t("Ouvrir le PDF", "Open PDF"), id="antivirus-open")
                yield Button(t("Ouvrir le dossier", "Open folder"), id="antivirus-folder")
                yield Button(t("Actualiser", "Refresh"), id="antivirus-reload")
                yield Button(t("Fermer", "Close"), id="antivirus-close")

    async def on_mount(self):
        t = self.tr
        self.query_one(DataTable).add_columns(t("Date et heure", "Date and time"), t("Rapport PDF", "PDF report"),
                                              t("Résultat", "Result"))
        await self.reload()

    async def reload(self):
        try:
            self.rows = {str(row.path): row for row in await asyncio.to_thread(antivirus_reports, self.state)}
        except (OSError, ValueError, sqlite3.Error) as error:
            self.show_error(error)
            return
        self.show_error("")
        self.render_rows()

    def render_rows(self):
        table = self.query_one(DataTable)
        table.clear()
        query = self.query_one(Input).value.casefold().strip()
        labels = (lambda row: row.timestamp, lambda row: row.path.name.casefold(),
                  lambda row: (row.status, row.threats if row.threats is not None else -1))
        for row in sorted(self.rows.values(), key=labels[self.sort_column], reverse=self.descending):
            values = (row.date_label(), row.path.name, row.result_label(self.tr))
            if any(query in value.casefold() for value in values):
                table.add_row(*(Text(value) for value in values), key=str(row.path))
        for key in ("open", "folder"):
            self.query_one(f"#antivirus-{key}", Button).disabled = table.row_count == 0

    def on_input_changed(self):
        self.render_rows()

    def on_data_table_header_selected(self, event):
        column = event.column_index
        self.descending = not self.descending if column == self.sort_column else column == 0
        self.sort_column = column
        self.render_rows()

    def selected(self):
        table = self.query_one(DataTable)
        if table.row_count and table.is_valid_row_index(table.cursor_row):
            return self.rows[table.ordered_rows[table.cursor_row].key.value]
        return None

    async def open_selected(self, folder=False):
        if row := self.selected():
            try:
                await asyncio.to_thread(dispatch_viewing_copy, row.path.parent if folder else row.path)
            except (OSError, ValueError) as error:
                self.show_error(error)

    async def on_data_table_row_selected(self):
        await self.open_selected()

    def show_error(self, error):
        self.query_one("#antivirus-report-error", Static).update(Text(str(error)))

    async def on_button_pressed(self, event):
        match event.button.id:
            case "antivirus-open":
                await self.open_selected()
            case "antivirus-folder":
                await self.open_selected(folder=True)
            case "antivirus-reload":
                await self.reload()
            case "antivirus-close":
                self.dismiss()

    def action_close(self):
        self.dismiss()

    def action_menu(self):
        self.open_menu()

    def open_menu(self):
        t = self.tr
        options = [(t("Actualiser", "Refresh"), "reload")]
        if self.selected():
            options[0:0] = [(t("Ouvrir le PDF", "Open PDF"), "open"), (t("Ouvrir le dossier", "Open folder"), "folder")]

        async def choose(result):
            if result:
                if result["choice"] == "reload":
                    await self.reload()
                else:
                    await self.open_selected(result["choice"] == "folder")

        self.app.push_screen(Form(t("Rapports antivirus", "Antivirus reports"), t, choices=options), choose)
