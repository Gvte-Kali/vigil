"""Native terminal workspace backed by the Vigil Core services."""
import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Input, Static, TabbedContent, TabPane

from . import device_manager, storage
from .core import BUILTIN_MODULES, discover
from .entity import FIELDS, data_directory, legacy_base, load_entity
from .system_info import system_metrics

CORE_ERRORS = (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError)


def logo():
    source = legacy_base() / "data/icons/vigil.svg"
    if not source.is_file():
        source = Path(sys.prefix) / "share/vigil/vigil.svg"
    if source.is_file() and os.geteuid() != 0 and "NO_COLOR" not in os.environ:
        try:
            result = subprocess.run(["chafa", "--format", "symbols", "--colors", "256",
                                     "--size", "20x6", str(source)], capture_output=True,
                                    text=True, timeout=2, check=True)
            if result.stdout.strip():
                return Text.from_ansi(result.stdout.rstrip())
        except (OSError, subprocess.SubprocessError):
            pass
    return Text("Vigil", style="bold cyan")


class Workspace(App):
    TITLE = "Vigil"
    CSS = """
    Screen { background: #14181d; color: #e3ebf2; }
    #brand { background: #1c252e; width: 100%; height: auto; padding: 0 2; }
    #session { color: #76dbe7; padding: 0 2; height: auto; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 0 1; }
    VerticalScroll { height: 1fr; }
    DataTable { height: 1fr; min-height: 4; background: #14181d; }
    DataTable > .datatable--header { background: #25323e; color: #76dbe7; }
    DataTable > .datatable--cursor { background: #104a57; }
    #case-form, #evidence-form { height: auto; }
    #case-form Input, #evidence-form Input { width: 1fr; }
    Button { margin-right: 1; }
    Button.-primary { background: #106171; color: white; }
    #case-detail, #mount-summary, #entity-config, #module-errors { height: auto; padding: 1; }
    """
    BINDINGS = [("ctrl+r", "refresh_workspace", "↻"), ("ctrl+q", "quit", "Quitter / Quit")]

    def __init__(self, state, language="fr", operator=None):
        super().__init__()
        self.state = state
        self.language = language
        self.operator = operator
        self.active_case = None
        self.case_rows = {}
        self.evidence_busy = False
        self.brand = Text("Vigil", style="bold cyan")

    def tr(self, french, english):
        return english if self.language == "en" else french

    def compose(self) -> ComposeResult:
        t = self.tr
        yield Static(self.brand, id="brand")
        yield Static(id="session")
        with TabbedContent():
            with TabPane(t("Tableau de bord", "Dashboard"), id="dashboard"):
                with VerticalScroll():
                    yield Static(id="resources")
                    yield Static(id="mount-summary")
            with TabPane(t("Affaire en cours", "Current case"), id="cases"):
                yield DataTable(id="case-table", cursor_type="row")
                with Horizontal(id="case-form"):
                    yield Input(placeholder=t("Nom de la nouvelle affaire", "New case name"), id="case-name")
                    yield Button(t("Créer", "Create"), id="create-case", variant="primary")
                    yield Button(t("Activer", "Activate"), id="activate-case")
                yield Static(id="case-detail")
            with TabPane(t("Preuves", "Evidence"), id="evidence"):
                yield DataTable(id="evidence-table", cursor_type="row")
                with Horizontal(id="evidence-form"):
                    yield Input(placeholder=t("Chemin du fichier", "File path"), id="evidence-path")
                    yield Button(t("Ajouter", "Add"), id="add-evidence", variant="primary")
                    yield Button(t("Vérifier la copie", "Verify copy"), id="verify-evidence")
            with TabPane(t("Actions rapides", "Quick actions"), id="quick"):
                yield Button(t("Vérifier les montages", "Verify mounts"), id="verify-mounts", variant="primary")
                yield DataTable(id="mount-table", cursor_type="row")
            with TabPane(t("Entité", "Entity"), id="entity"):
                yield Static(id="entity-config")
                yield DataTable(id="operator-table", cursor_type="row")
                yield Input(placeholder=t("Nom de l’opérateur", "Operator name"), id="operator-name")
                yield Button(t("Choisir l’opérateur", "Set operator"), id="set-operator", variant="primary")
            with TabPane(t("Catalogue", "Catalogue"), id="catalogue"):
                yield DataTable(id="module-table", cursor_type="row")
                yield Static(id="module-errors")
        yield Footer()

    async def on_mount(self):
        t = self.tr
        columns = {
            "case-table": [t("Affaire", "Case"), t("Référence", "Reference"), t("Preuves", "Evidence")],
            "operator-table": [t("Opérateur", "Operator")],
            "evidence-table": [t("Chemin", "Path"), t("Octets", "Bytes"), "SHA-256"],
            "mount-table": [t("Montage", "Mountpoint"), t("Source", "Source"), t("Mode", "Mode"), t("État", "Status")],
            "module-table": [t("Module", "Module"), t("Catégorie", "Category"), t("Entrée", "Entrypoint")],
        }
        for selector, names in columns.items():
            self.table(selector).add_columns(*names)
        self.query_one("#brand", Static).update(await asyncio.to_thread(logo))
        await self.action_refresh_workspace()

    def table(self, name):
        return self.query_one(f"#{name}", DataTable)

    def replace_rows(self, name, rows):
        table = self.table(name)
        table.clear()
        for key, values in rows:
            table.add_row(*(Text(str(value)) for value in values), key=key)

    def notify_error(self, error):
        self.notify(str(error), severity="error", title=self.tr("Opération interrompue", "Operation interrupted"))

    def refresh_session(self):
        t = self.tr
        operator = self.operator or t("Aucun opérateur", "No operator")
        case = self.case_rows.get(self.active_case, {}).get("name") or t("Aucune affaire active", "No active case")
        self.query_one("#session", Static).update(Text(f"{operator}  ·  {case}"))
        self.query_one("#create-case", Button).disabled = not self.operator
        self.query_one("#activate-case", Button).disabled = not self.operator or not self.case_rows
        self.refresh_evidence_buttons()

    def refresh_evidence_buttons(self):
        disabled = self.evidence_busy or not self.active_case or not self.operator
        self.query_one("#add-evidence", Button).disabled = disabled
        self.query_one("#verify-evidence", Button).disabled = disabled or not self.table("evidence-table").row_count

    def refresh_case_detail(self, row=None):
        t = self.tr
        if row is None:
            detail = t("Sélectionnez une affaire pour afficher ses détails.", "Select a case to see its details.")
        else:
            detail = f"{row['name']}  ·  {t('Preuves', 'Evidence')} : {row['evidence_count']}"
            if row.get("description"):
                detail += f"\n{row['description']}"
        self.query_one("#case-detail", Static).update(Text(detail))

    def case_data(self):
        rows = storage.case_manager_rows(self.state)
        with storage.database(self.state) as connection:
            operators = storage.list_operators(connection)
        return sorted(rows, key=lambda row: (row["name"].casefold(), row["id"])), operators

    async def refresh_cases(self):
        rows, operators = await asyncio.to_thread(self.case_data)
        self.case_rows = {row["id"]: row for row in rows}
        if self.active_case not in self.case_rows:
            self.active_case = None
        self.replace_rows("case-table", ((r["id"], (r["name"], r["reference"] or "—", r["evidence_count"])) for r in rows))
        self.replace_rows("operator-table", ((r["id"], (r["name"],)) for r in operators))
        self.refresh_session()
        self.refresh_case_detail(self.case_rows.get(self.active_case))
        await self.refresh_evidence()

    async def refresh_evidence(self):
        rows = await asyncio.to_thread(storage.case_evidence_rows, self.state, self.active_case) if self.active_case else []
        self.replace_rows("evidence-table", ((row["id"], (row["path"], row["size"], row["sha256"])) for row in rows))
        self.refresh_evidence_buttons()

    async def refresh_mounts(self):
        t = self.tr
        rows = await asyncio.to_thread(device_manager.status)
        self.replace_rows("mount-table", (
            (str(index), (r["mountpoint"], r["path"], r.get("mount_mode", "—"),
                          t("Vérifié", "Verified") if r["verified"] else r.get("error", t("Non vérifié", "Unverified"))))
            for index, r in enumerate(rows)
        ))
        summary = [
            f"{r['mountpoint']}  ·  {r['path']}  ·  {t('Vérifié', 'Verified') if r['verified'] else t('Non vérifié', 'Unverified')}"
            for r in rows
        ]
        self.query_one("#mount-summary", Static).update(Text("\n".join(summary) or t("Aucun montage Vigil.", "No Vigil mounts.")))
        return rows

    async def action_refresh_workspace(self):
        t = self.tr
        try:
            await self.refresh_cases()
            await self.refresh_mounts()
            memory, uptime, load, count = system_metrics()
            ram = f"{(memory[0] - memory[1]) // 2**20} / {memory[0] // 2**20} MiB" if memory else "—"
            self.query_one("#resources", Static).update(Text(
                f"CPU : {count or '—'}    RAM : {ram}\n"
                f"{t('Temps de fonctionnement', 'Uptime')} : {f'{uptime // 60} min' if uptime is not None else '—'}"
            ))
            config = await asyncio.to_thread(load_entity, data_directory())
            captions = (t("Entité", "Entity"), t("Établissement", "Establishment"),
                        t("Adresse", "Address"), t("Téléphone", "Phone"), t("Courriel", "Email"))
            self.query_one("#entity-config", Static).update(Text("\n".join(
                f"{label} : {config.get(key) or '—'}" for key, label in zip(FIELDS, captions)
            )))
            manifests, errors = await asyncio.to_thread(discover, BUILTIN_MODULES)
            self.replace_rows("module-table", ((key, (key, item.category, item.entrypoint))
                                                for key, item in sorted(manifests.items())))
            self.query_one("#module-errors", Static).update(Text("\n".join(map(str, errors))))
        except CORE_ERRORS as error:
            self.notify_error(error)

    def on_data_table_row_highlighted(self, event):
        if event.data_table.id == "case-table":
            self.refresh_case_detail(self.case_rows.get(event.row_key.value))

    def selected_key(self, table):
        widget = self.table(table)
        if widget.row_count:
            return widget.coordinate_to_cell_key(widget.cursor_coordinate).row_key

    def register_operator(self, name):
        with storage.database(self.state) as connection:
            storage.register_operator(connection, name)

    def create_case(self, name):
        with storage.database(self.state) as connection:
            storage.create_case(connection, name, self.operator)

    def verify_case(self, case_id):
        with storage.database(self.state) as connection:
            storage.require_active_case(connection, case_id)

    async def on_button_pressed(self, event):
        t = self.tr
        try:
            match event.button.id:
                case "set-operator":
                    field = self.query_one("#operator-name", Input)
                    key = self.selected_key("operator-table")
                    name = field.value.strip()
                    if not name and key is not None:
                        name = self.table("operator-table").get_row(key)[0].plain
                    await asyncio.to_thread(self.register_operator, name)
                    self.operator, self.active_case = name, None
                    field.clear()
                    await self.refresh_cases()
                case "create-case" if self.operator:
                    field = self.query_one("#case-name", Input)
                    await asyncio.to_thread(self.create_case, field.value.strip())
                    field.clear()
                    await self.refresh_cases()
                    self.notify(t("Affaire créée.", "Case created."))
                case "activate-case" if self.operator:
                    if key := self.selected_key("case-table"):
                        await asyncio.to_thread(self.verify_case, key.value)
                        self.active_case = key.value
                        self.refresh_session()
                        await self.refresh_evidence()
                case "add-evidence" if self.active_case and self.operator and not self.evidence_busy:
                    field = self.query_one("#evidence-path", Input)
                    if path := field.value.strip():
                        self.start_evidence_operation("add", self.active_case, self.operator, path)
                    else:
                        raise ValueError(t("Indiquez un chemin de fichier.", "Enter a file path."))
                case "verify-evidence" if self.active_case and self.operator and not self.evidence_busy:
                    if key := self.selected_key("evidence-table"):
                        self.start_evidence_operation("verify", self.active_case, self.operator, key.value)
                case "verify-mounts":
                    mounts = await self.refresh_mounts()
                    if not mounts:
                        self.notify(t("Aucun montage Vigil.", "No Vigil mounts."))
                    elif all(item["verified"] for item in mounts):
                        self.notify(t("Montages vérifiés.", "Mounts verified."))
                    else:
                        self.notify(t("Montage non vérifié.", "Mount verification failed."), severity="warning")
        except CORE_ERRORS as error:
            self.notify_error(error)

    def start_evidence_operation(self, operation, case_id, operator, argument):
        self.evidence_busy = True
        self.refresh_evidence_buttons()
        self.evidence_operation(operation, case_id, operator, argument)

    @work
    async def evidence_operation(self, operation, case_id, operator, argument):
        t = self.tr

        def execute():
            with device_manager.device_lease(shared=True):
                if operation == "add":
                    return storage.register_file(self.state, case_id, Path(argument).expanduser(), operator)
                return storage.verify_file(self.state, argument, operator, use_copy=True)

        try:
            result = await asyncio.to_thread(execute)
            if operation == "add":
                field = self.query_one("#evidence-path", Input)
                if field.value.strip() == argument:
                    field.clear()
                await self.refresh_cases()
                self.notify(t("Preuve enregistrée.", "Evidence registered."))
            elif result["matches"]:
                self.notify(t("Intégrité SHA-256 confirmée.", "SHA-256 verified."))
            else:
                self.notify(t("Vérification SHA-256 échouée.", "SHA-256 verification failed."), severity="error")
        except CORE_ERRORS as error:
            self.notify_error(error)
        finally:
            self.evidence_busy = False
            self.refresh_evidence_buttons()

    async def action_quit(self):
        if self.evidence_busy:
            self.notify(self.tr("Attendez la fin de la vérification ou de la copie.",
                                "Wait for the verification or copy to finish."), severity="warning")
        else:
            await super().action_quit()
