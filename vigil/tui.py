"""Native terminal workspace backed by the Vigil Core services."""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, ContentSwitcher, DataTable, Footer, Input, Select, Static, TabbedContent, TabPane, Tree, ProgressBar

from . import device_manager, storage
from .adapters import analysis_command, query_census
from .case_export import export_case
from .case_import import import_archive, verify_archive
from .case_removal import purge_case
from .core import BUILTIN_MODULES, discover, doctor
from .external_terminal import prepare_tracked
from .history import PAGE_SIZE, case_events
from .images import inspect_raw
from .inspection import inspect_file, investigation_mounts, list_evidence_directory
from .module_scaffold import create_module_draft
from .quick_actions import acquisition_command, legacy_mount_command, storage_command, update_command
from .reporting import case_pdf_reports, case_report, pdf_analysis_kind
from .shutdown_state import check_shutdown_state
from .tui_screens import Form, Operation
from .tui_picker import FileSystemPicker, PickerOptions
from . import dev_mode
from .tui_widgets import ActionCard, CardGrid, MetricCard, NavigationItem, SectionPanel, StatusIndicator, icon, supports_unicode
from .entity import FIELDS, data_directory, legacy_base, load_entity, save_entity
from .system_info import cpu_ticks, system_metrics

CORE_ERRORS = (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError)


def render_logo(source, size):
    if source.is_file() and os.geteuid() != 0 and "NO_COLOR" not in os.environ and supports_unicode():
        try:
            result = subprocess.run(["chafa", "--format", "symbols", "--colors", "256",
                                     "--size", size, str(source)], capture_output=True,
                                    text=True, timeout=2, check=True)
            if result.stdout.strip():
                return Text.from_ansi(result.stdout.rstrip())
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def logo():
    source = legacy_base() / "data/icons/vigil.svg"
    if not source.is_file():
        source = Path(sys.prefix) / "share/vigil/vigil.svg"
    return render_logo(source, "32x8") or Text("Vigil", style="bold")


def organization_logo(data, relative_path):
    if relative_path:
        root = (data / "config/logo").resolve()
        image = (data / relative_path).resolve()
        if image.is_relative_to(root):
            return render_logo(image, "24x8")
    return None


class Workspace(App):
    TITLE = "Vigil"
    CSS_PATH = "workspace.tcss"
    BINDINGS = [("ctrl+r", "refresh_workspace", "↻"), ("ctrl+q", "quit", "Quitter / Quit")]

    def __init__(self, state, language="fr", operator=None):
        super().__init__()
        self.state = state
        self.language = language
        self.operator = operator
        self.active_case = None
        self.case_rows = {}
        self.evidence_busy = False
        self.manifests = {}
        self.history_rows = {}
        self.report_paths = {}
        self.explorer_path = None
        self.current_page = "dashboard"
        self.manager_open = True
        self.sidebar_manual = False
        self.cpu_sample = None
        self.disk_rows = None
        self.dashboard_refreshing = False
        try:
            self.release = version("vigil-dfir")
        except PackageNotFoundError:
            self.release = "2.0"
        self.brand = Text("Vigil", style="bold")

    def tr(self, french, english):
        return english if self.language == "en" else french

    def navigation(self):
        t = self.tr
        return {
            "dashboard": t("Tableau de bord", "Dashboard"),
            "cases": t("Affaire en cours", "Current case"),
            "quick": t("Actions rapides", "Quick actions"),
            "entity": t("Entité", "Entity"),
            "catalogue": t("Catalogue de modules", "Module catalogue"),
        }

    def button(self, key, french, english, **options):
        label = self.tr(french, english)
        button = Button(label, id=key, **options)
        button.tooltip = label
        return button

    def compose(self) -> ComposeResult:
        t, b = self.tr, self.button
        with Horizontal(id="header"):
            yield Static(self.brand, id="brand")
            yield Static(id="session")
            yield b("sidebar-toggle", icon("menu"), icon("menu"))
            yield b("quit", "Quitter", "Quit")
            if supports_unicode():
                yield b("language", "🇫🇷 FR / EN 🇬🇧", "🇫🇷 FR / EN 🇬🇧")
            else:
                yield b("language", "FR / EN", "FR / EN")
        with Horizontal(id="body"):
            with VerticalScroll(id="sidebar"):
                for key, label in self.navigation().items():
                    if key == "cases":
                        yield Static(t("INVESTIGATION", "INVESTIGATION"), classes="nav-group")
                    if key == "entity":
                        yield Static(t("SYSTÈME", "SYSTEM"), classes="nav-group")
                    yield NavigationItem(label, key)
            with ContentSwitcher(initial="dashboard", id="pages"):
                with VerticalScroll(id="dashboard"):
                    yield Static(t("Tableau de bord", "Dashboard"), classes="heading")
                    yield Static(id="resources", classes="panel")
                    with Horizontal(id="metrics"):
                        yield MetricCard("CPU", "cpu")
                        yield MetricCard("RAM", "ram")
                    yield Static(id="mount-summary", classes="panel")
                    yield Static(id="recent-activity", classes="panel")
                    yield Static(t("Disques et partitions", "Disks and partitions"), classes="heading")
                    yield Tree(t("Périphériques bloc", "Block devices"), id="disk-tree")
                    yield b("diagnose", "Diagnostic des outils", "Tool diagnostics")
                    yield b("protect", "Activer la protection USB", "Enable USB protection")
                    yield b("review-session", "Bilan des sessions", "Session reports")
                with Vertical(id="cases"):
                    yield Static(t("Gestionnaire d’affaires", "Case manager"), classes="heading", id="manager-title")
                    with Horizontal(id="case-tools"):
                        yield Input(placeholder=t("Rechercher une affaire", "Search cases"), id="case-search")
                        yield Select([("A–Z", "name"), ("Z–A", "name-desc"),
                                      (t("Création", "Created"), "created_at"),
                                      (t("Activité", "Activity"), "latest")],
                                     value="name", allow_blank=False, id="case-sort")
                    with Horizontal(classes="master-detail", id="case-manager"):
                        yield DataTable(id="case-table", cursor_type="row")
                        with VerticalScroll(classes="panel", id="manager-actions"):
                            yield Static(id="case-detail")
                            yield SectionPanel(t("Actions de l’affaire", "Case actions"),
                                b("activate-case", "Ouvrir l’affaire", "Open case", variant="primary"),
                                b("delete-case", "Supprimer l’affaire", "Delete case", classes="destructive"))
                            yield SectionPanel(t("Gestion des affaires", "Manage cases"),
                                b("create-case", "Créer une affaire", "Create case", classes="success-action"),
                                b("import-case", "Importer…", "Import…", classes="violet-action"),
                                b("close-manager", "Revenir à l’affaire active", "Back to active case"))
                    with Vertical(id="case-workspace"):
                        yield Static(id="case-heading", classes="heading")
                        with Horizontal(classes="actions"):
                            yield b("open-manager", "Gestionnaire d’affaires", "Case manager")
                            yield b("deactivate-case", "Désactiver l’affaire", "Deactivate case")
                        with TabbedContent(id="workspace-tabs"):
                            with TabPane(t("Sources", "Sources"), id="sources"):
                                yield DataTable(id="mount-table", cursor_type="row")
                                with Horizontal(classes="actions"):
                                    yield b("mount-case", "Monter et recenser", "Mount and run census", variant="primary")
                                    yield b("unmount-case", "Démonter", "Unmount")
                                    yield b("inspect-image", "Inspecter une image RAW", "Inspect a RAW image")
                                    yield b("verify-mounts", "Vérifier les montages", "Verify mounts")
                            with TabPane(t("Explorateur", "Explorer"), id="explorer"):
                                with Horizontal(classes="master-detail"):
                                    yield Tree(t("Sources de l’affaire", "Case sources"), id="file-tree")
                                    with VerticalScroll(classes="panel"):
                                        yield Static(id="file-preview")
                                with Horizontal(classes="actions"):
                                    yield b("register-preview", "Enregistrer comme preuve", "Register as evidence")
                                    yield b("reload-explorer", "Actualiser les sources", "Refresh sources")
                            with TabPane(t("Preuves", "Evidence"), id="evidence"):
                                yield DataTable(id="evidence-table", cursor_type="row")
                                with Horizontal(id="evidence-picker-line"):
                                    yield Input(placeholder=t("Chemin du fichier", "File path"), id="evidence-path")
                                    yield b("browse-evidence", "Parcourir…", "Browse…")
                                with Horizontal(classes="actions"):
                                    yield b("add-evidence", "Ajouter", "Add", variant="primary")
                                    yield b("verify-evidence", "Vérifier la copie", "Verify copy")
                                    yield b("preview-evidence", "Inspecter la copie", "Inspect copy")
                                    yield b("delete-evidence", "Supprimer la preuve", "Delete evidence", classes="destructive")
                            with TabPane(t("Analyses", "Analyses"), id="analyses"):
                                yield DataTable(id="analysis-table", cursor_type="row")
                                with Horizontal(classes="actions"):
                                    yield b("run-analysis", "Lancer l’analyse", "Run analysis", variant="primary")
                                    yield b("analysis-results", "Résultats", "Results")
                                    yield b("query-index", "Consulter un recensement", "Query a census index")
                            with TabPane(t("Actions et journal", "Actions and history"), id="history"):
                                yield Input(placeholder=t("Filtrer par action ou opérateur", "Filter by action or operator"), id="history-search")
                                yield DataTable(id="history-table", cursor_type="row")
                                with Horizontal(classes="actions"):
                                    yield b("show-event", "Détails", "Details")
                                    yield b("earlier-events", "Événements précédents", "Earlier events")
                            with TabPane(t("Rapports PDF", "PDF reports"), id="reports"):
                                yield DataTable(id="report-table", cursor_type="row")
                                with Horizontal(classes="actions"):
                                    yield b("refresh-reports", "Actualiser", "Refresh")
                                    yield b("report-location", "Chemin du rapport", "Report path")
                            with TabPane(t("Exporter l’affaire", "Export case"), id="export"):
                                yield Static(t("L’archive contient les preuves copiées, les résultats, le journal et les empreintes SHA-256.",
                                               "The archive contains saved evidence, results, audit history and SHA-256 checksums."),
                                             classes="panel")
                                with Horizontal(classes="actions"):
                                    yield b("export-case", "Créer l’archive complète", "Create full archive", variant="primary")
                                    yield b("export-audit", "Exporter l’audit", "Export audit")
                with VerticalScroll(id="quick"):
                    yield Static(t("Actions rapides", "Quick actions"), classes="heading")
                    yield SectionPanel("Antivirus", CardGrid(
                        ActionCard(t("Scan antivirus", "Antivirus scan"),
                                   t("Analyser un support et produire un rapport.", "Scan media and produce a report."),
                                   "scan", id="quick-scan"),
                        ActionCard(t("Mettre à jour l’antivirus", "Update antivirus"),
                                   t("Télécharger les signatures ClamAV.", "Download ClamAV signatures."),
                                   "update", id="quick-update"),
                        ActionCard(t("Rapports antivirus", "Antivirus reports"),
                                   t("Retrouver les rapports de scan.", "Find previous scan reports."),
                                   "report", id="quick-reports", classes="reports-card"),
                    ), id="antivirus-group", classes="quick-group", glyph="scan",
                       description=t("Analyse et mise à jour des signatures.", "Scan media and update signatures."))
                    yield SectionPanel(t("Stockage", "Storage"), CardGrid(
                        ActionCard(t("Monter un stockage", "Mount storage"),
                                   t("Connecter un support de travail en RW.", "Connect a work drive read-write."),
                                   "mount", id="storage-mount"),
                        ActionCard(t("Démonter le stockage", "Unmount storage"),
                                   t("Libérer le support de travail.", "Release the work drive."),
                                   "unmount", id="storage-unmount"),
                    ), id="storage-group", classes="quick-group", glyph="cases",
                       description=t("Supports de travail en lecture-écriture.", "Read-write work drives."))
                    yield SectionPanel("Acquisition", CardGrid(
                        ActionCard(t("Cloner un disque", "Clone a disk"),
                                   t("Copier bit à bit vers un disque cible.", "Copy bit for bit to a target disk."),
                                   "clone", id="clone", classes="destructive"),
                        ActionCard(t("Créer une image RAW", "Create a RAW image"),
                                   t("Enregistrer une image vérifiée.", "Save a verified disk image."),
                                   "raw", id="raw", classes="sensitive"),
                    ), id="acquisition-group", classes="quick-group", glyph="raw",
                       description=t("Clonage et images forensiques vérifiées.", "Verified disk clones and forensic images."))
                with VerticalScroll(id="entity"):
                    yield Static(t("Configuration de l’entité", "Organization settings"), classes="heading")
                    yield Static(id="entity-config", classes="panel")
                    yield Static(id="entity-logo-preview")
                    yield b("edit-entity", "Modifier l’entité", "Edit organization")
                    yield b("entity-logo", "Choisir ou retirer le logo", "Choose or remove logo")
                    yield Static(t("Opérateur de session", "Session operator"), classes="heading")
                    yield DataTable(id="operator-table", cursor_type="row")
                    yield Input(placeholder=t("Nom de l’opérateur", "Operator name"), id="operator-name")
                    yield b("set-operator", "Choisir l’opérateur", "Set operator", variant="primary")
                with Vertical(id="catalogue"):
                    yield Static(t("Catalogue de modules", "Module catalogue"), classes="heading")
                    with Horizontal(id="case-tools-modules"):
                        yield Input(placeholder=t("Rechercher un module", "Search modules"), id="module-search")
                        yield Select([(t("Tous", "All"), "all"), (t("Disponibles", "Available"), "available")],
                                     value="all", allow_blank=False, id="module-filter")
                    with Horizontal(classes="master-detail"):
                        yield DataTable(id="module-table", cursor_type="row")
                        with VerticalScroll(classes="panel"):
                            yield Static(id="module-detail")
                    yield Static(id="module-errors")
                    yield b("create-module", "Créer un module", "Create module")
        yield StatusIndicator(id="status-bar")
        yield Footer()

    async def on_mount(self):
        await self.initialize_workspace()
        self.adjust_sidebar()
        self.set_interval(3, self.refresh_dashboard)
        if os.environ.get("VIGIL_SESSION_ID") or dev_mode.active():
            if not self.operator:
                await self.choose_session_operator()
            else:
                await self.offer_protection()

    async def choose_session_operator(self):
        _, operators = await asyncio.to_thread(self.case_data)
        t = self.tr
        choices = [(row["name"], row["name"]) for row in operators]
        choices.append((t("Créer un opérateur", "Create an operator"), ""))
        self.push_screen(Form(t("Opérateur de la session", "Session operator"), t,
                              (("name", t("Nom du nouvel opérateur (si création)", "New operator name (when creating)"), ""),),
                              choices=choices),
                         lambda response: self.submit_form("session-operator", response)
                         if response is not None else self.exit())

    async def pending_protection_reports(self):
        from .session import pending_sessions

        return await asyncio.to_thread(pending_sessions, self.state.parent / "sessions")

    async def offer_protection(self):
        if dev_mode.active():
            return
        if Path("/usr/local/sbin/vigil-hotplug").is_file() and not self.protection_active():
            await self.request_protection()

    async def request_protection(self):
        if dev_mode.active():
            self.notify(dev_mode.BLOCKED, severity="warning")
            return
        t = self.tr
        if self.protection_active():
            self.notify(t("Protection USB déjà active.", "USB protection is already active."))
            return
        if not os.environ.get("VIGIL_SESSION_GUARD", "").isdecimal():
            raise ValueError(t("Relancez la TUI avec vigil ou vigil-tui pour ouvrir une session supervisée.",
                               "Restart with vigil or vigil-tui to open a supervised session."))
        if not Path("/usr/local/sbin/vigil-hotplug").is_file():
            raise ValueError(t("L’assistant USB est absent. Installez-le avec scripts/post-install/install-hotplug.sh.",
                               "The USB helper is missing. Install it with scripts/post-install/install-hotplug.sh."))
        await self.launch_workflow("protect", {}, self.active_case, self.operator)

    async def finish_protection_start(self, status, guard, candidates):
        if status == 0 and self.protection_active():
            from .session import record_startup_recovery

            await asyncio.to_thread(record_startup_recovery, self.state, guard, candidates)
            self.notify(self.tr("Protection USB active.", "USB protection active."))
        else:
            self.notify(self.tr("Protection USB inactive. Consultez le diagnostic de l’opération.",
                                "USB protection inactive. Check the operation diagnostics."), severity="warning")
        await self.action_refresh_workspace()

    async def finish_session_review(self):
        await self.action_refresh_workspace()
        if not await self.pending_protection_reports():
            await self.offer_protection()

    async def initialize_workspace(self):
        t = self.tr
        columns = {
            "case-table": [t("Affaire", "Case"), t("Référence", "Reference"), t("Preuves", "Evidence")],
            "operator-table": [t("Opérateur", "Operator")],
            "evidence-table": [t("Chemin", "Path"), t("Octets", "Bytes"), "SHA-256"],
            "mount-table": [t("Montage", "Mountpoint"), t("Source", "Source"), t("Mode", "Mode"), t("État", "Status")],
            "module-table": [t("Module", "Module"), "Version", t("État", "Status")],
            "analysis-table": [t("Module", "Module"), t("Description", "Description")],
            "history-table": [t("Date", "Date"), t("Opérateur", "Operator"), "Action"],
            "report-table": [t("Analyse", "Analysis"), t("Rapport", "Report")],
        }
        for selector, names in columns.items():
            self.table(selector).add_columns(*names)
        if self.brand.plain == "Vigil":
            self.brand = await asyncio.to_thread(logo)
        self.query_one("#brand", Static).update(self.brand)
        self.show_page(self.current_page)
        self.show_case_manager(self.manager_open)
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
        self.query_one("#session", Static).update(Text(
            f"Vigil {self.release}  ·  {operator}\n{case}", no_wrap=True, overflow="ellipsis"
        ))
        self.query_one("#case-heading", Static).update(Text(case))
        self.write_session_context()
        for key in ("mount-case", "unmount-case", "run-analysis", "query-index", "export-case", "export-audit",
                    "deactivate-case", "delete-evidence", "preview-evidence", "register-preview"):
            self.query_one(f"#{key}", Button).disabled = not self.active_case or not self.operator
        self.query_one("#create-case", Button).disabled = not self.operator
        self.query_one("#set-operator", Button).disabled = bool(self.operator and os.environ.get("VIGIL_SESSION_ID"))
        self.query_one("#operator-name", Input).disabled = self.query_one("#set-operator", Button).disabled
        self.refresh_evidence_buttons()

    def refresh_evidence_buttons(self):
        disabled = self.evidence_busy or not self.active_case or not self.operator
        self.query_one("#add-evidence", Button).disabled = disabled
        self.query_one("#browse-evidence", Button).disabled = disabled
        self.query_one("#verify-evidence", Button).disabled = disabled or not self.table("evidence-table").row_count

    def date_label(self, value):
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    def refresh_case_detail(self, row=None):
        t = self.tr
        if row is None:
            detail = t("Sélectionnez une affaire pour afficher ses détails.", "Select a case to see its details.")
        else:
            detail = "\n".join((
                row["name"],
                f"{t('Référence', 'Reference')} : {row.get('reference') or '—'}",
                f"{t('Opérateur', 'Operator')} : {row.get('operator') or '—'}",
                f"{t('Création', 'Created')} : {self.date_label(row.get('created_at'))}",
                f"{t('Dernière activité', 'Last activity')} : {self.date_label(row.get('latest'))}",
                f"{t('Dossier', 'Directory')} : {row.get('directory') or '—'}",
                f"{t('Preuves', 'Evidence')} : {row['evidence_count']}",
                row.get("description") or "",
            ))
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
            self.show_case_manager(True)
        self.filter_cases()
        self.replace_rows("operator-table", ((r["id"], (r["name"],)) for r in operators))
        self.refresh_session()
        self.refresh_case_detail(self.case_rows.get(self.active_case))
        await self.refresh_evidence()

    async def refresh_evidence(self):
        rows = await asyncio.to_thread(storage.case_evidence_rows, self.state, self.active_case) if self.active_case else []
        self.replace_rows("evidence-table", ((row["id"], (row["path"], row["size"], row["sha256"])) for row in rows))
        self.refresh_evidence_buttons()

    async def refresh_mounts(self, rows=None):
        t = self.tr
        if rows is None:
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
        count = len(rows)
        protection = self.protection_active()
        state = t("Protection USB active", "USB protection active") if protection else t("Protection USB inactive", "USB protection inactive")
        if dev_mode.active():
            state = t("Mode recette · opérations système désactivées",
                      "Development mode · system operations disabled")
        self.query_one("#status-bar", StatusIndicator).show(
            state, f"{count} {t('montage(s)', 'mount(s)')}  ·  /investigation RO  ·  /stockage RW",
            active=protection,
        )
        return rows

    async def action_refresh_workspace(self):
        t = self.tr
        try:
            await self.refresh_cases()
            await self.refresh_mounts()
            self.refresh_metrics()
            config = await asyncio.to_thread(load_entity, data_directory())
            captions = (t("Entité", "Entity"), t("Établissement", "Establishment"),
                        t("Adresse", "Address"), t("Téléphone", "Phone"), t("Courriel", "Email"))
            fields = [f"{label} : {config.get(key) or '—'}" for key, label in zip(FIELDS, captions)]
            logo_name = config.get("logo")
            logo_name = logo_name if isinstance(logo_name, str) else ""
            fields.append(f"Logo : {Path(logo_name).name if logo_name else '—'}")
            self.query_one("#entity-config", Static).update(Text("\n".join(fields)))
            preview = await asyncio.to_thread(organization_logo, data_directory(), logo_name)
            logo_widget = self.query_one("#entity-logo-preview", Static)
            logo_widget.display = bool(preview)
            if preview:
                logo_widget.update(preview)
            self.manifests, errors = await asyncio.to_thread(discover, BUILTIN_MODULES)
            self.filter_modules()
            self.replace_rows("analysis-table", ((key, (key, item.name))
                                                  for key, item in sorted(self.manifests.items())
                                                  if item.category == "analysis"))
            self.query_one("#module-errors", Static).update(Text("\n".join(map(str, errors))))
            self.render_disk_tree(await asyncio.to_thread(device_manager.inventory), force=True)
            await self.refresh_case_views()
        except CORE_ERRORS as error:
            self.notify_error(error)

    def on_data_table_row_highlighted(self, event):
        if event.data_table.id == "case-table":
            self.refresh_case_detail(self.case_rows.get(event.row_key.value))
        elif event.data_table.id == "module-table":
            details = self.query("#module-detail")
            if details and (item := self.manifests.get(event.row_key.value)):
                details.first(Static).update(Text(
                    f"{event.row_key.value}  ·  {item.version}\n\n{item.name}\n"
                    f"{item.category}  ·  {item.entrypoint}\n"
                    f"{', '.join(item.dependencies)}"
                ))

    def selected_key(self, table):
        widget = self.table(table)
        if widget.row_count:
            return widget.coordinate_to_cell_key(widget.cursor_coordinate).row_key

    def register_operator(self, name):
        if not 1 <= len(name) <= 120 or not name.isprintable():
            raise ValueError(self.tr("Saisissez un nom lisible de 1 à 120 caractères.",
                                     "Enter a printable name of 1 to 120 characters."))
        with storage.database(self.state) as connection:
            storage.register_operator(connection, name)

    def create_case(self, name, reference="", description=""):
        with storage.database(self.state) as connection:
            storage.create_case(connection, name, self.operator, reference=reference, description=description)

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
                    self.ask("create-case", t("Créer une affaire", "Create case"), (
                        ("name", t("Nom", "Name"), ""),
                        ("reference", t("Référence", "Reference"), ""),
                        ("description", t("Description", "Description"), ""),
                    ))
                case "activate-case" if self.operator:
                    if key := self.selected_key("case-table"):
                        await asyncio.to_thread(self.verify_case, key.value)
                        self.active_case = key.value
                        self.refresh_session()
                        self.show_case_manager(False)
                        await self.refresh_case_views()
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
                case _:
                    await self.handle_action(event.button.id)
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
        if isinstance(self.screen, Operation) or self.evidence_busy:
            self.notify(self.tr("Attendez la fin de la vérification ou de la copie.",
                                "Wait for the verification or copy to finish."), severity="warning")
        elif len(self.screen_stack) == 1:
            self.push_screen(Form(self.tr("Fermer Vigil", "Close Vigil"), self.tr,
                                  message=self.tr("Confirmer la fermeture de Vigil ?", "Confirm closing Vigil?")),
                             lambda answer: self.call_later(self.confirm_quit) if answer is not None else None)

    async def confirm_quit(self):
        try:
            if not dev_mode.active():
                await asyncio.to_thread(check_shutdown_state)
        except CORE_ERRORS as error:
            self.info(self.tr("Fermeture suspendue", "Close blocked"), error)
            return
        self.exit()

    def render_disk_tree(self, rows, *, force=False):
        if not force and rows == self.disk_rows:
            return
        self.disk_rows = rows
        tree = self.query_one("#disk-tree", Tree)
        tree.clear()
        for row in rows:
            self.add_disk(tree.root, row)
        tree.root.expand()

    async def refresh_dashboard(self):
        if len(self.screen_stack) != 1 or self.current_page != "dashboard" or self.dashboard_refreshing:
            return
        self.dashboard_refreshing = True
        try:
            case = self.active_case
            mounts, disks, activity = await asyncio.gather(
                asyncio.to_thread(device_manager.status),
                asyncio.to_thread(device_manager.inventory),
                asyncio.to_thread(self.dashboard_activity, case),
            )
            if len(self.screen_stack) == 1 and self.current_page == "dashboard":
                self.refresh_metrics()
                await self.refresh_mounts(mounts)
                self.render_disk_tree(disks)
                if self.active_case == case:
                    self.show_activity(activity)
        except CORE_ERRORS as error:
            if len(self.screen_stack) == 1:
                self.query_one("#mount-summary", Static).update(Text(str(error)))
        finally:
            self.dashboard_refreshing = False

    def adjust_sidebar(self):
        sidebars = self.query("#sidebar")
        if sidebars and not self.sidebar_manual:
            sidebars.first().set_class(self.size.width < 72, "compact")

    def on_resize(self):
        if len(self.screen_stack) == 1:
            self.adjust_sidebar()

    def refresh_metrics(self):
        if len(self.screen_stack) != 1:
            return
        memory, uptime, _, count = system_metrics()
        if memory:
            used, total = memory[0] - memory[1], memory[0]
            self.query_one("#ram-progress", ProgressBar).update(progress=100 * used / total)
            ram = f"{used // 2**20} / {total // 2**20} MiB"
        else:
            ram = "—"
        try:
            sample = cpu_ticks()
            if self.cpu_sample:
                total_delta, idle_delta = (new - old for new, old in zip(sample, self.cpu_sample))
                if total_delta > 0 and 0 <= idle_delta <= total_delta:
                    self.query_one("#cpu-progress", ProgressBar).update(progress=100 * (total_delta - idle_delta) / total_delta)
            self.cpu_sample = sample
        except (OSError, ValueError):
            pass
        t = self.tr
        active = int(self.active_case in self.case_rows)
        self.query_one("#resources", Static).update(Text(
            f"{t('Affaires', 'Cases')} : {len(self.case_rows)}  ·  {t('Actives', 'Active')} : {active}  ·  "
            f"CPU : {count or '—'}  ·  RAM : {ram}\n"
            f"{t('Temps de fonctionnement', 'Uptime')} : {f'{uptime // 60} min' if uptime is not None else '—'}"
        ))

    def show_page(self, page):
        self.current_page = page
        self.query_one("#pages", ContentSwitcher).current = page
        for key in self.navigation():
            self.query_one(f"#nav-{key}", Button).set_class(key == page, "selected")

    def show_case_manager(self, opened):
        self.manager_open = opened or not self.active_case
        self.query_one("#manager-title").display = self.manager_open
        self.query_one("#case-tools").display = self.manager_open
        self.query_one("#case-manager").display = self.manager_open
        self.query_one("#manager-actions").display = self.manager_open
        self.query_one("#case-workspace").display = not self.manager_open
        self.query_one("#close-manager", Button).disabled = not self.active_case

    def filter_cases(self):
        query = self.query_one("#case-search", Input).value.casefold()
        order = self.query_one("#case-sort", Select).value
        rows = (r for r in self.case_rows.values() if query in r["name"].casefold())
        key = "name" if order == "name-desc" else order
        sorted_rows = sorted(rows, key=lambda r: ((r.get(key) or "").casefold(), r["name"].casefold(), r["id"]),
                             reverse=order != "name")
        self.replace_rows("case-table", ((r["id"], (r["name"], r["reference"] or "—", r["evidence_count"]))
                                         for r in sorted_rows))
        self.query_one("#activate-case", Button).disabled = not self.operator or not sorted_rows
        self.query_one("#delete-case", Button).disabled = not self.operator or not sorted_rows
        self.refresh_case_detail(sorted_rows[0] if sorted_rows else None)

    def filter_modules(self):
        import shutil

        query = self.query_one("#module-search", Input).value.casefold()
        filter_by_status = self.query_one("#module-filter", Select).value == "available"
        rows = []
        for key, module in sorted(self.manifests.items()):
            available = all(shutil.which(program) for program in module.dependencies)
            if query in f"{key} {module.name} {module.category}".casefold() and (available or not filter_by_status):
                status = self.tr("Disponible", "Available") if available else self.tr("Manquant", "Missing")
                rows.append((key, (module.name, module.version, status)))
        self.replace_rows("module-table", rows)
        self.query_one("#module-detail", Static).update("")

    def on_input_changed(self, event):
        if event.input.id == "case-search":
            self.filter_cases()
        elif event.input.id == "module-search":
            self.filter_modules()

    def on_select_changed(self, event):
        if event.select.id == "case-sort":
            self.filter_cases()
        elif event.select.id == "module-filter":
            self.filter_modules()

    def on_input_submitted(self, event):
        if event.input.id == "history-search":
            self.background(self.refresh_history)

    def write_session_context(self):
        if path := os.environ.get("VIGIL_SESSION_CONTEXT"):
            from .session import write_state

            try:
                write_state(Path(path), {"operator": self.operator,
                                         "case": self.case_rows.get(self.active_case, {}).get("name"),
                                         "language": self.language})
            except OSError as error:
                self.notify_error(error)

    def protection_active(self):
        pid = os.environ.get("VIGIL_SESSION_GUARD", "")
        if not pid.isdecimal():
            return False
        token = Path("/run/vigil-hotplug") / pid
        try:
            start = (Path("/proc") / pid / "stat").read_text().rsplit(")", 1)[1].split()[19]
            return token.stat().st_uid == 0 and token.read_text().strip() == f"{os.getuid()} {start}"
        except (OSError, ValueError, IndexError):
            return False

    def add_disk(self, parent, row):
        access = "RO" if row.get("ro") in {1, "1", True} else "RW"
        label = f"{row['name']} · {row.get('size') or '—'} · {access}"
        node = parent.add(Text(label), allow_expand=bool(row.get("children")))
        for child in row.get("children", []):
            self.add_disk(node, child)

    async def refresh_case_views(self):
        await self.refresh_evidence()
        await self.refresh_history()
        await self.refresh_reports()
        await self.refresh_explorer()

    async def refresh_history(self, *, earlier=False):
        case = self.active_case
        query = self.query_one("#history-search", Input).value.strip()
        previous = min(self.history_rows) if earlier and self.history_rows else None

        def read():
            with storage.database(self.state) as connection:
                storage.require_active_case(connection, case)
                return case_events(connection, case, query, before=previous)

        rows = await asyncio.to_thread(read) if case else []
        if not earlier:
            self.history_rows.clear()
        self.history_rows.update((r["sequence"], r) for r in rows)
        self.replace_rows("history-table", (
            (str(key), (r["timestamp"], r["operator"], r["action"])) for key, r in self.history_rows.items()
        ))
        self.query_one("#earlier-events", Button).disabled = len(rows) < PAGE_SIZE
        if not earlier and not query:
            self.show_activity(rows[:4])

    def dashboard_activity(self, case):
        if not case:
            return []
        with storage.database(self.state) as connection:
            return case_events(connection, case, limit=4)

    def show_activity(self, rows):
        activity = self.query_one("#recent-activity", Static)
        activity.update(Text("\n".join(f"{self.date_label(r['timestamp'])} · {r['action']}" for r in rows) or
                             self.tr("Aucune activité d’affaire.", "No case activity.")))

    async def refresh_reports(self):
        def read():
            with storage.database(self.state) as connection:
                legacy = storage.require_active_case(connection, self.active_case)["legacy_path"]
            return case_pdf_reports(self.state, self.active_case, legacy)

        paths = await asyncio.to_thread(read) if self.active_case else []
        self.report_paths = {str(i): path for i, path in enumerate(paths)}
        self.replace_rows("report-table", ((key, (pdf_analysis_kind(path) or "—", path.name))
                                           for key, path in self.report_paths.items()))

    async def refresh_explorer(self):
        tree = self.query_one("#file-tree", Tree)
        tree.clear()
        self.explorer_path = None
        self.query_one("#file-preview", Static).update(
            self.tr("Sélectionnez un fichier.", "Select a file.") if self.active_case else
            self.tr("Aucune affaire active.", "No active case."))
        if self.active_case:
            for root, mount_id in (await asyncio.to_thread(investigation_mounts)).items():
                tree.root.add(Text(root), data=(Path(root), root, mount_id, True))
            for row in await asyncio.to_thread(storage.case_evidence_rows, self.state, self.active_case):
                copy = await asyncio.to_thread(storage.evidence_copy_path, self.state, self.active_case, row["id"])
                if copy.is_file():
                    tree.root.add_leaf(Text(Path(row["path"]).name), data=(copy, None, None, False))
        tree.root.expand()

    async def on_tree_node_expanded(self, event):
        if event.control.id != "file-tree" or not event.node.data:
            return
        path, root, mount_id, directory = event.node.data
        if not directory or event.node.children:
            return
        try:
            rows = await asyncio.to_thread(list_evidence_directory, path, root, mount_id)
            for name, subdirectory in rows:
                event.node.add(Text(name), data=(path / name, root, mount_id, subdirectory),
                               allow_expand=subdirectory)
        except CORE_ERRORS as error:
            self.notify_error(error)

    async def on_tree_node_highlighted(self, event):
        if event.control.id != "file-tree" or not event.node.data:
            return
        path, root, mount_id, directory = event.node.data
        preview = self.query_one("#file-preview", Static)
        preview.remove_class("preview-error")
        self.explorer_path = None if directory or root is None else path
        if directory:
            preview.update(Text(str(path)))
            return
        try:
            result = await asyncio.to_thread(inspect_file, path, mount=(root, mount_id) if root else None)
            preview.update(self.preview_text(path, result))
        except CORE_ERRORS as error:
            preview.add_class("preview-error")
            preview.update(Text(str(error)))

    def preview_text(self, path, result):
        return Text(f"{path}\n{result['size']} octets · {result['mode']} · {result['mime_hint'] or '—'}\n\n"
                    f"HEX\n{result['hex']}\n\nASCII\n{result['strings']}")

    def ask(self, action, title, fields=(), **options):
        self.push_screen(Form(title, self.tr, fields, **options),
                         lambda response: self.submit_form(action, response) if response is not None else None)

    def info(self, title, detail):
        self.push_screen(Form(title, self.tr, message=str(detail)))

    @work
    async def background(self, function):
        try:
            await function()
        except CORE_ERRORS as error:
            self.notify_error(error)

    @work
    async def submit_form(self, action, response):
        t = self.tr
        case = self.active_case
        operator = self.operator
        if self.evidence_busy:
            return
        self.evidence_busy = True
        self.refresh_evidence_buttons()
        try:
            match action:
                case "session-operator":
                    name = response["name"] or response["choice"]
                    try:
                        await asyncio.to_thread(self.register_operator, name)
                    except ValueError as error:
                        self.notify_error(error)
                        await self.choose_session_operator()
                        return
                    self.operator = name
                    self.query_one("#set-operator", Button).disabled = True
                    await self.refresh_cases()
                    await self.offer_protection()
                case "create-case":
                    await asyncio.to_thread(self.create_case, response["name"], response["reference"], response["description"])
                    await self.refresh_cases()
                case "delete-case":
                    selected = response["selected"]
                    await asyncio.to_thread(self.remove_case, selected)
                    await self.refresh_cases()
                    self.show_case_manager(True)
                    await self.refresh_case_views()
                case "import-case":
                    path = self.form_path(response["path"])
                    if response["choice"] == "legacy":
                        await asyncio.to_thread(self.import_legacy, path)
                        await self.refresh_cases()
                    else:
                        preview = await asyncio.to_thread(verify_archive, path)
                        self.push_screen(Form(t("Vérifier puis importer", "Verify and import"), t,
                                              message=f"{path}\nSHA-256 : {preview.sha256}"),
                                         lambda choice: self.submit_form("restore-archive", {
                                             "path": str(path), "sha256": preview.sha256,
                                         }) if choice is not None else None)
                case "restore-archive":
                    await asyncio.to_thread(import_archive, self.state, self.form_path(response["path"]),
                                            operator, expected_sha256=response["sha256"])
                    await self.refresh_cases()
                case "edit-entity":
                    await asyncio.to_thread(save_entity, data_directory(), response)
                    await self.action_refresh_workspace()
                case "entity-logo":
                    from .entity import read_logo_png

                    def update_logo():
                        data = data_directory()
                        saved = load_entity(data)
                        image = read_logo_png(self.form_path(response["path"])) if response["choice"] == "import" else b""
                        save_entity(data, {key: saved.get(key, "") for key in FIELDS}, image)

                    await asyncio.to_thread(update_logo)
                    await self.action_refresh_workspace()
                case "create-module":
                    result = await asyncio.to_thread(create_module_draft, self.state, response["name"])
                    self.info(t("Brouillon du module", "Module draft"), result)
                case "export-case":
                    result = await asyncio.to_thread(export_case, self.state, case, operator, self.form_path(response["path"]))
                    self.info(t("Archive créée", "Archive created"), result.path)
                case "export-audit":
                    self.info(t("Audit exporté", "Audit exported"), await asyncio.to_thread(case_report, self.state, case))
                case "inspect-image":
                    result = await asyncio.to_thread(inspect_raw, self.form_path(response["path"]))
                    self.info(t("Image RAW", "RAW image"), json.dumps(result, ensure_ascii=False, indent=2))
                case "query-index":
                    result = await asyncio.to_thread(query_census, self.state, case, operator, self.form_path(response["path"]))
                    self.info(t("Résultat du recensement", "Census results"), result or t("Aucune discordance.", "No mismatches."))
                case "delete-evidence":
                    await asyncio.to_thread(storage.delete_evidence, self.state, case, response["selected"], operator)
                    await self.refresh_cases()
                case _:
                    await self.launch_workflow(action, response, case, operator)
        except CORE_ERRORS as error:
            self.notify_error(error)
        finally:
            self.evidence_busy = False
            if self.is_running:
                self.refresh_evidence_buttons()

    def pick_path(self, title, options, callback, *, initial=None):
        case = self.case_rows.get(self.active_case)
        custody = self.state.parent / "legacy-custody" / case["directory"] if case else None
        self.push_screen(FileSystemPicker(title, self.tr, options, initial=initial, case_directory=custody),
                         lambda path: callback(path) if path is not None else None)

    def pick_for(self, action, title, options, *, initial=None, fields=None):
        self.pick_path(title, options,
                       lambda path: self.submit_form(action, {**(fields or {}), "path": str(path)}),
                       initial=initial)

    def choose_import(self, answer):
        if answer is not None:
            legacy = answer["choice"] == "legacy"
            self.pick_for("import-case", self.tr("Choisir le projet ou l’archive", "Choose project or archive"),
                          PickerOptions("directory" if legacy else "open", () if legacy else (".tar.gz",)),
                          fields=answer)

    def choose_logo(self, answer):
        if answer is None:
            return
        if answer["choice"] == "remove":
            self.submit_form("entity-logo", answer)
        else:
            self.pick_for("entity-logo", self.tr("Choisir le logo", "Choose logo"),
                          PickerOptions("open", (".png", ".jpg", ".jpeg")), fields=answer)

    def choose_raw(self, answer):
        if answer is None:
            return
        if answer["choice"] == "usb":
            self.submit_form("raw", answer)
        else:
            self.pick_for("raw", self.tr("Enregistrer l’image RAW", "Save RAW image"),
                          PickerOptions("save", (".raw",), writable=True, acquisition=True),
                          initial=Path.home() / "acquisition.raw", fields=answer)

    def form_path(self, path):
        if not path:
            raise ValueError(self.tr("Indiquez un chemin.", "Enter a path."))
        return Path(path).expanduser().absolute()

    def import_legacy(self, path):
        name, raw = storage.read_legacy_project(path.resolve(strict=True))
        with storage.database(self.state) as connection:
            storage.create_case(connection, name, self.operator, str(path.resolve()), raw)

    def remove_case(self, identifier):
        with storage.database(self.state) as connection:
            storage.delete_case(connection, identifier, self.operator)
        if leftovers := purge_case(self.state, identifier):
            raise ValueError(str(leftovers))

    async def handle_action(self, action):
        t = self.tr
        if action.startswith("nav-"):
            self.show_page(action[4:])
            return
        if self.evidence_busy:
            self.notify(t("Une opération est en cours.", "An operation is active."))
            return
        needs_operator = {"import-case", "delete-case", "quick-scan", "storage-mount", "storage-unmount",
                          "clone", "raw", "quick-update"}
        if action in needs_operator and not self.operator:
            self.notify(t("Choisissez un opérateur dans Entité.", "Choose an operator under Entity."), severity="warning")
            self.show_page("entity")
            return
        match action:
            case "quit":
                await self.action_quit()
            case "browse-evidence":
                field = self.query_one("#evidence-path", Input)
                def select_evidence(path):
                    field.value = str(path)
                self.pick_path(t("Choisir une preuve", "Choose evidence"), PickerOptions("open"),
                               select_evidence, initial=field.value or None)
            case "sidebar-toggle":
                self.sidebar_manual = True
                self.query_one("#sidebar").toggle_class("compact")
            case "language":
                self.language = "en" if self.language == "fr" else "fr"
                await self.recompose()
                await self.initialize_workspace()
            case "open-manager" | "close-manager":
                self.show_case_manager(action == "open-manager")
            case "deactivate-case":
                self.active_case = None
                self.refresh_session()
                self.show_case_manager(True)
                await self.refresh_case_views()
            case "import-case":
                self.push_screen(Form(t("Importer une affaire", "Import case"), t, choices=(
                    ("Vigil 2.0 · " + t("Archive", "Archive"), "archive"),
                    ("Vigil 1.0 · " + t("Dossier du projet", "Project folder"), "legacy"),
                )), self.choose_import)
            case "delete-case" | "delete-evidence":
                table = "case-table" if action == "delete-case" else "evidence-table"
                if key := self.selected_key(table):
                    self.push_screen(Form(t("Confirmer la suppression", "Confirm deletion"), t),
                                     lambda response: self.submit_form(action, {"selected": key.value})
                                     if response is not None else None)
            case "edit-entity":
                config = await asyncio.to_thread(load_entity, data_directory())
                labels = (t("Entité", "Entity"), t("Établissement", "Establishment"), t("Adresse", "Address"),
                          t("Téléphone", "Phone"), t("Courriel", "Email"))
                self.ask(action, t("Configuration de l’entité", "Organization settings"),
                         tuple((key, label, str(config.get(key) or "")) for key, label in zip(FIELDS, labels)))
            case "entity-logo":
                self.push_screen(Form(t("Logo de l’entité", "Organization logo"), t, choices=(
                    (t("Charger un PNG ou JPEG", "Load a PNG or JPEG"), "import"),
                    (t("Retirer le logo", "Remove logo"), "remove"),
                )), self.choose_logo)
            case "review-session":
                pending = await self.pending_protection_reports()
                if not pending:
                    self.info(t("Bilan des sessions", "Session reports"),
                              t("Aucune session à vérifier.", "No session requires review."))
                else:
                    self.ask(action, t("Bilan des sessions", "Session reports"),
                             choices=tuple((name, name) for name in reversed(sorted(pending))))
            case "create-module":
                self.ask(action, t("Créer un module", "Create module"), (("name", t("Nom", "Name"), ""),))
            case "inspect-image":
                self.pick_for(action, t("Inspecter une image RAW", "Inspect a RAW image"),
                              PickerOptions("open", (".raw", ".dd", ".img", ".iso")))
            case "export-case":
                self.pick_for(action, t("Dossier de destination de l’archive", "Archive destination folder"),
                              PickerOptions("directory", writable=True))
            case "query-index":
                self.pick_for(action, t("Index de recensement", "Census index"),
                              PickerOptions("open", (".sqlite", ".sqlite3", ".db")))
            case "raw":
                self.push_screen(Form(t("Destination de l’image RAW", "RAW image destination"), t,
                                      choices=((t("Dossier local", "Local folder"), "local"),
                                               (t("Périphérique USB", "USB device"), "usb"))), self.choose_raw)
            case "clone":
                self.ask(action, t("Cloner un disque", "Clone a disk"),
                         message=t("Les données du disque de destination seront écrasées.",
                                   "Data on the destination disk will be overwritten."))
            case "protect":
                await self.request_protection()
            case "quick-scan" | "quick-update" | "storage-mount" | "storage-unmount" | "mount-case" | "unmount-case" | "run-analysis" | "export-audit":
                self.ask(action, str(self.query_one(f"#{action}", Button).label))
            case "diagnose":
                self.info(t("Diagnostic", "Diagnostics"), json.dumps(await asyncio.to_thread(doctor), ensure_ascii=False, indent=2))
            case "reload-explorer":
                await self.refresh_explorer()
            case "register-preview" if self.explorer_path and self.active_case and self.operator:
                self.start_evidence_operation("add", self.active_case, self.operator, str(self.explorer_path))
            case "preview-evidence" if self.active_case:
                if key := self.selected_key("evidence-table"):
                    path = await asyncio.to_thread(storage.evidence_copy_path, self.state, self.active_case, key.value)
                    result = await asyncio.to_thread(inspect_file, path)
                    self.info(t("Aperçu de la copie", "Copy preview"), self.preview_text(path, result).plain)
            case "earlier-events":
                await self.refresh_history(earlier=True)
            case "show-event":
                if key := self.selected_key("history-table"):
                    self.info(t("Événement", "Event"), json.dumps(self.history_rows[int(key.value)], ensure_ascii=False, indent=2))
            case "refresh-reports":
                await self.refresh_reports()
            case "report-location":
                if key := self.selected_key("report-table"):
                    title = t("Rapport PDF", "PDF report")
                    self.pick_path(title, PickerOptions("open", (".pdf",)), lambda path: self.info(title, path),
                                   initial=self.report_paths[key.value])
            case "quick-reports":
                with storage.database(self.state) as connection:
                    case = storage.find_antivirus_case(connection)
                paths = await asyncio.to_thread(case_pdf_reports, self.state, case) if case else []
                title = t("Rapports antivirus", "Antivirus reports")
                if paths:
                    self.pick_path(title, PickerOptions("open", (".pdf",)), lambda path: self.info(title, path),
                                   initial=paths[0])
                else:
                    self.info(title, t("Aucun rapport.", "No reports."))
            case "analysis-results" if self.active_case:
                directory = await asyncio.to_thread(storage.case_storage_directory, self.state, self.active_case)
                results = directory / "analyses"
                paths = sorted(path.name for path in results.iterdir() if path.is_dir() and not path.is_symlink()) if results.is_dir() else []
                self.info(t("Résultats des analyses", "Analysis results"), f"{results}\n" + "\n".join(paths))

    async def launch_workflow(self, action, fields, case, operator):
        if dev_mode.active():
            raise ValueError(dev_mode.BLOCKED)
        t = self.tr
        mode = None
        name = self.case_rows.get(case, {}).get("name", "")
        match action:
            case "raw":
                external = fields["choice"] == "usb"
                selected = None if external else self.form_path(fields["path"])
                argv = acquisition_command("image", external=external,
                                           local_directory=selected.parent if selected else None,
                                           language=self.language, interface="tui")
                if selected:
                    argv.extend(("--filename", selected.name))
            case "clone":
                argv = acquisition_command("clone", language=self.language, interface="tui")
            case "mount-case" | "unmount-case":
                mode = "operation"
                argv = await asyncio.to_thread(legacy_mount_command, action.split("-")[0], self.state, case, name, operator)
            case "storage-mount" | "storage-unmount":
                mode = "operation"
                argv = await asyncio.to_thread(storage_command, action.split("-")[1], self.state, case, name, operator)
            case "run-analysis":
                key = self.selected_key("analysis-table")
                if not key:
                    raise ValueError(t("Sélectionnez un module.", "Select a module."))
                mode = "analysis"
                argv = await asyncio.to_thread(analysis_command, self.state, case, operator, key.value)
            case "quick-update":
                argv = await asyncio.to_thread(update_command, self.state)
            case "quick-scan":
                run = uuid4().hex
                with storage.database(self.state) as connection:
                    case = storage.antivirus_case(connection, operator)
                    storage.audit(connection, operator, case, "antivirus.request", {"run_id": run})
                mode = "operation"
                argv = await asyncio.to_thread(legacy_mount_command, "scan", self.state, case,
                                               storage.ANTIVIRUS_CASE_NAME, operator, run_id=run)
            case "review-session":
                from .session import prepare_previous_report

                output = await asyncio.to_thread(prepare_previous_report, self.state, fields["choice"], [fields["choice"]])
                argv = ["/usr/bin/env", f"VIGIL_STATE_DIR={self.state.parent}", sys.executable,
                        "-m", "vigil.session", "--review-report", str(output)]
            case "protect":
                pid = os.environ.get("VIGIL_SESSION_GUARD", "")
                if not pid.isdecimal() or not Path("/proc", pid).is_dir():
                    raise ValueError(t("La session supervisée n’est plus disponible.", "The supervised session is no longer available."))
                pending = await self.pending_protection_reports()
                argv = ["/usr/bin/sh", str(legacy_base() / "scripts/post-install/activate-hotplug.sh"),
                        pid, "--reconcile-required"]
            case _:
                return
        if mode:
            argv = [sys.executable, "-m", "vigil.device_manager", mode, *argv]
        run, argv = prepare_tracked(argv, self.state.parent / "terminal-runs",
                                   {"operation": action, "language": self.language, "operator": operator, "case_id": case},
                                   interface="tui")
        callback = self.finish_session_review if action == "review-session" else self.action_refresh_workspace

        def finish(status):
            if action == "protect":
                self.background(lambda: self.finish_protection_start(status, pid, pending))
            else:
                self.background(callback)

        self.push_screen(Operation(str(self.query_one(f"#{action}", Button).label), t, argv,
                                   self.language, run, close_on_success=action == "protect"), finish)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--lang", choices=("fr", "en"), default="fr")
    parser.add_argument("--operator")
    arguments = parser.parse_args()
    if arguments.operator:
        with storage.database(arguments.db) as connection:
            storage.register_operator(connection, arguments.operator)
    Workspace(arguments.db, arguments.lang, arguments.operator).run()


if __name__ == "__main__":
    main()
