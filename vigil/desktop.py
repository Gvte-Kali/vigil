"""Bilingual Qt workspace for the local Vigil core."""
import os
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QByteArray, QLibraryInfo, QRectF, QSize, QObject, QSettings, QThread, QTimer, QTranslator, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QDockWidget, QFileDialog, QFrame, QInputDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QStackedWidget, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import storage
from .adapters import CENSUS_LIMIT, query_census
from .core import BUILTIN_MODULES, discover, doctor
from .images import inspect_raw
from .inspection import inspect_file
from .module_scaffold import create_module_draft
from .evidence_panel import EvidencePanel
from .entity import data_directory, legacy_base
from .entity_panel import EntityPanel
from .history import PAGE_SIZE, case_events
from .reporting import case_pdf_reports, case_report
from .system_panel import SystemPanel
from .system_info import read_zones
from .shutdown_state import ShutdownBlocked, capture_startup_state, check_shutdown_state
from .terminal_panel import TerminalPanel
from .quick_actions import legacy_mount_command, tool, update_command
from .external_terminal import launch_action, launch_terminal

ANALYSIS_LABELS = {
    "archives": ("Archives", "Archives"),
    "audio": ("Fichiers audio", "Audio files"),
    "bigfiles": ("Fichiers volumineux", "Large files"),
    "census": ("Recensement de fichiers", "File inventory"),
    "crypto": ("Fichiers chiffrés", "Encrypted files"),
    "entropy": ("Analyse de l’entropie", "Entropy analysis"),
    "images": ("Images et métadonnées", "Images and metadata"),
    "office": ("Documents bureautiques", "Office documents"),
    "videos": ("Fichiers vidéo", "Video files"),
}

STYLE = """
QWidget { background: #101318; color: #DCE3EC; font-size: 13px; }
QFrame#header { background: #1A2029; border: 1px solid #35404E; border-radius: 10px; }
QFrame#header QLabel { background: transparent; }
QLabel#brand { font-size: 21px; font-weight: 700; }
QTreeWidget { background: #121820; border: 1px solid #3B495B; border-radius: 7px; }
QLabel#sectionContext { color: #B9CAD9; padding: 3px 0; }
QLineEdit, QComboBox, QListWidget {
    background: #121820; border: 1px solid #3B495B; border-radius: 7px;
    padding: 8px; selection-background-color: #57C7D4; selection-color: #101318;
}
QListWidget::item { padding: 8px; border-radius: 4px; }
QListWidget::item:hover:!selected { background: #263444; }
QListWidget::item:selected { background: #57C7D4; color: #101318; }
QListWidget#navigation {
    background: #101318; border: none; padding: 0 7px 0 0;
    selection-background-color: #203741; selection-color: #80DEE8;
}
QListWidget#navigation::item { min-height: 31px; padding: 4px 11px; border-radius: 6px; }
QListWidget#navigation::item:hover:!selected { background: #1B2834; }
QListWidget#navigation::item:selected { background: #203741; color: #80DEE8; }
QListWidget#caseNavigation { background: #1A2029; }
QListWidget#caseNavigation::item:selected { background: #203741; color: #80DEE8; }
QListWidget#navigation::item:disabled { background: transparent; color: #91A1B3; }
QFrame#quickActionSection { background: #1A2029; border: 1px solid #35404E; border-radius: 8px; }
QFrame#quickActionCard { background: #202A36; border: 1px solid #455569; border-radius: 7px; }
QFrame#quickActionCard QLabel { background: transparent; color: #C4D1E0; }
QLabel#quickActionTitle { color: #57C7D4; background: transparent; font-weight: 700; }
QLabel#pageTitle { font-size: 20px; font-weight: 700; }
QWidget[workspacePage="true"] { background: #101318; }
QPushButton {
    background: #273447; color: #F1F6FC; border: 1px solid #4B6076;
    border-radius: 7px; padding: 8px 13px; font-weight: 600;
}
QPushButton:hover { background: #35475D; border-color: #7393AE; }
QPushButton:pressed { background: #1C2939; }
QPushButton[primary="true"] { background: #57C7D4; color: #101318; border-color: #72DAE5; }
QPushButton[primary="true"]:hover { background: #80DEE8; }
QPushButton[primary="true"]:pressed { background: #44AAB8; }
QPushButton[languageButton="true"] { padding: 6px 9px; }
QPushButton[languageButton="true"]:checked {
    background: #284753; border-color: #57C7D4; color: #F0FCFF;
}
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QListWidget:focus { border-color: #A3F3FC; }
QScrollBar:vertical { width: 12px; background: #1A2029; margin: 0; }
QScrollBar:horizontal { height: 12px; background: #1A2029; margin: 0; }
QScrollBar::handle { background: #57C7D4; border-radius: 5px; min-width: 28px; min-height: 28px; }
QScrollBar::handle:hover { background: #80DEE8; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QPushButton:disabled { background: #202A36; color: #91A1B3; border-color: #35404E; }
"""

FLAGS = {
    "fr": '<path fill="#002395" d="M0 0h10v20H0z"/><path fill="#fff" d="M10 0h10v20H10z"/>'
          '<path fill="#ED2939" d="M20 0h10v20H20z"/>',
    "en": '<path fill="#012169" d="M0 0h30v20H0z"/>'
          '<path stroke="#fff" stroke-width="4" d="M0 0l30 20m0-20L0 20"/>'
          '<path stroke="#C8102E" stroke-width="1.6" d="M0 0l30 20m0-20L0 20"/>'
          '<path stroke="#fff" stroke-width="6" d="M15 0v20M0 10h30"/>'
          '<path stroke="#C8102E" stroke-width="3.6" d="M15 0v20M0 10h30"/>',
}


def flag_icon(language):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 20">{FLAGS[language]}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode("ascii")))
    pixmap = QPixmap(48, 32)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    with QPainter(pixmap) as painter:
        renderer.render(painter, QRectF(0, 0, 24, 16))
    return QIcon(pixmap)


class Worker(QObject):
    finished = Signal(object, object)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    @Slot()
    def run(self):
        try:
            result = self.operation()
        except (OSError, sqlite3.Error, ValueError) as error:
            self.finished.emit(None, error)
        else:
            self.finished.emit(result, None)


class Workspace(QMainWindow):
    def __init__(self, settings, database_path):
        super().__init__()
        self.settings = settings
        self.database_path = database_path
        self.closing_checks = False
        self.startup_state_error = None
        try:
            self.startup_block_modes, self.startup_snapshot_path = capture_startup_state(database_path)
        except (OSError, ValueError) as error:
            self.startup_state_error = error
        self.active_case_id = ""
        self.settings.remove("active_case_id")
        self.language = "en" if settings.value("language") == "en" else "fr"
        self.translator = QTranslator(self)
        self.localized = []
        self.busy = None
        self.worker = None
        self.buttons = []
        screen = self.screen().availableGeometry()
        self.resize(min(1280, screen.width()), min(660, screen.height()))
        self.setWindowTitle("Vigil 2.0")
        self.setStyleSheet(STYLE)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(14)
        header_frame = QFrame()
        header_frame.setObjectName("header")
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(14, 10, 14, 10)
        header.setSpacing(10)
        logo = QLabel()
        logo_path = Path(__file__).resolve().parents[1] / "data/icons/vigil.svg"
        if not logo_path.is_file():
            logo_path = Path(sys.prefix) / "share/vigil/vigil.svg"
        icon = QIcon(str(logo_path))
        self.setWindowIcon(icon)
        logo.setPixmap(icon.pixmap(40, 40))
        header.addWidget(logo)
        brand = QLabel("Vigil 2.0")
        brand.setObjectName("brand")
        header.addWidget(brand)
        self.active_case = QLabel()
        self.active_case.setObjectName("sectionContext")
        self.active_case.setTextFormat(Qt.TextFormat.PlainText)
        header.addWidget(self.active_case)
        header.addStretch()
        self.operator = QComboBox()
        self.operator.setMinimumWidth(145)
        self.bind(self.operator.setAccessibleName, "Opérateur actif", "Active operator")
        self.operator.currentIndexChanged.connect(self.save_operator)
        header.addWidget(self.operator)
        self.button(header, "Opérateurs…", "Operators…", self.manage_operators)
        self.manage_operator_button = self.buttons[-1]
        self.languages = QButtonGroup(self)
        self.language_buttons = {}
        for language, name in (("fr", "Français"), ("en", "English")):
            button = QPushButton(flag_icon(language), language.upper())
            button.setProperty("languageButton", True)
            button.setIconSize(QSize(24, 16))
            button.setCheckable(True)
            button.setChecked(self.language == language)
            button.setAccessibleName(name)
            button.setToolTip(name)
            self.languages.addButton(button)
            self.language_buttons[language] = button
            button.clicked.connect(lambda _, code=language: self.change_language(code))
            header.addWidget(button)
        layout.addWidget(header_frame)
        body = QHBoxLayout()
        body.setSpacing(14)
        layout.addLayout(body, 1)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.group_items = {}
        self.group_open = {}
        self.current_group = None
        self.navigation.setFixedWidth(224)
        self.bind(self.navigation.setAccessibleName, "Navigation", "Navigation")
        self.navigation.currentItemChanged.connect(self.open_page)
        body.addWidget(self.navigation)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.navigation_group("ESPACE DE TRAVAIL", "WORKSPACE")
        home = self.page("Accueil", "Home")
        self.dashboard_case = QLabel()
        self.dashboard_case.setTextFormat(Qt.TextFormat.PlainText)
        home.addWidget(self.dashboard_case)
        metrics = QHBoxLayout()
        home.addLayout(metrics)
        self.dashboard_cards = []
        for color in ("#57C7D4", "#BB9AF7", "#80D7A4"):
            card = QLabel()
            card.setTextFormat(Qt.TextFormat.PlainText)
            card.setMinimumHeight(67)
            card.setStyleSheet(
                f"background: #1A2029; color: {color}; padding: 12px; "
                "border-radius: 8px; font-size: 15px; font-weight: 600;"
            )
            metrics.addWidget(card, 1)
            self.dashboard_cards.append(card)
        recent = QLabel()
        recent.setObjectName("quickActionTitle")
        self.bind(recent.setText, "Activité récente de l’affaire", "Recent case activity")
        home.addWidget(recent)
        self.dashboard_events = QListWidget()
        home.addWidget(self.dashboard_events)


        cases = self.page("Affaires", "Cases")
        self.case_search = QLineEdit()
        self.case_search.setClearButtonEnabled(True)
        self.bind(self.case_search.setPlaceholderText, "Rechercher une affaire", "Search cases")
        self.bind(self.case_search.setAccessibleName, "Rechercher une affaire", "Search cases")
        self.case_search.textChanged.connect(self.filter_cases)
        cases.addWidget(self.case_search)
        self.cases = QListWidget()
        cases.addWidget(self.cases)
        self.cases.itemClicked.connect(self.case_clicked)
        for key in ("Return", "Enter"):
            shortcut = QShortcut(QKeySequence(key), self.cases)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda: self.case_clicked(self.cases.currentItem()))
        self.case_name = QLineEdit()
        self.bind(self.case_name.setPlaceholderText, "Nom de l’affaire", "Case name")
        case_actions = QHBoxLayout()
        cases.addLayout(case_actions)
        case_actions.addWidget(self.case_name, 1)
        self.button(case_actions, "Créer une affaire", "Create case", self.create_case, primary=True)
        self.button(case_actions, "Importer un ancien projet", "Import legacy project", self.import_case)

        self.navigation_group("INVESTIGATION", "INVESTIGATION")
        case_workspace = self.page("Affaire en cours", "Current case", heading=False)
        case_header = QHBoxLayout()
        case_workspace.addLayout(case_header)
        case_title = QLabel()
        case_title.setObjectName("pageTitle")
        self.bind(case_title.setText, "Affaire en cours", "Current case")
        case_header.addWidget(case_title)
        case_header.addStretch()
        self.button(case_header, "Monter périphérique/image", "Mount device/image",
                    self.request_mount, primary=True)
        self.button(case_header, "Démonter périphérique/image", "Unmount device/image",
                    self.request_unmount)
        self.investigation_mount = QLabel()
        self.investigation_mount.setTextFormat(Qt.TextFormat.PlainText)
        self.investigation_mount.setWordWrap(True)
        case_workspace.addWidget(self.investigation_mount)
        self.case_workspace_page = case_workspace.parentWidget()
        self.module_case = QLabel()
        self.module_case.setObjectName("sectionContext")
        self.module_case.setTextFormat(Qt.TextFormat.PlainText)
        case_workspace.addWidget(self.module_case)
        case_body = QHBoxLayout()
        case_workspace.addLayout(case_body, 1)
        self.case_pages = QStackedWidget()
        case_body.addWidget(self.case_pages, 1)
        self.case_navigation = QListWidget()
        self.case_navigation.setObjectName("caseNavigation")
        self.case_navigation.setFixedWidth(160)
        self.bind(self.case_navigation.setAccessibleName, "Vues de l’affaire", "Case views")
        case_body.addWidget(self.case_navigation)
        self.case_navigation.currentRowChanged.connect(self.open_case_view)

        explorer = self.case_view("Explorateur", "Evidence explorer")
        self.explorer = EvidencePanel(self.tr_pair, self.preview_evidence)
        explorer.addWidget(self.explorer)

        evidence = self.case_view("Preuves", "Evidence")
        self.case_label = QLabel()
        self.case_label.setObjectName("sectionContext")
        self.case_label.setTextFormat(Qt.TextFormat.PlainText)
        evidence.addWidget(self.case_label)
        self.evidence = QListWidget()
        evidence.addWidget(self.evidence)
        evidence_actions = QHBoxLayout()
        evidence.addLayout(evidence_actions)
        self.button(evidence_actions, "Ajouter un fichier à l’affaire", "Add a file to the case",
                    self.add_file, primary=True)
        self.button(evidence_actions, "Vérifier SHA-256", "Verify SHA-256", self.verify_file)
        self.button(evidence_actions, "Inspecter une image RAW", "Inspect a RAW image", self.inspect_image)
        evidence_actions.addStretch()


        modules = self.case_view("Analyses", "Analyses")
        self.analysis_hint = QLabel()
        self.analysis_hint.setWordWrap(True)
        self.bind(
            self.analysis_hint.setText,
            "La consultation d’un index est disponible ici. Les autres scripts sont répertoriés "
            "pour référence et restent accessibles via Vigil 1.0.",
            "Index queries are available here. The other scripts are listed for reference "
            "and remain accessible through Vigil 1.0.",
        )
        modules.addWidget(self.analysis_hint)
        self.modules = QListWidget()
        modules.addWidget(self.modules)
        module_actions = QHBoxLayout()
        modules.addLayout(module_actions)
        self.button(module_actions, "Consulter un index de recensement",
                    "Query a census index", self.query_index, primary=True)
        module_actions.addStretch()
        catalogue = self.page("Catalogue de modules", "Module catalogue")
        self.catalogue_filter = QLineEdit()
        self.bind(self.catalogue_filter.setPlaceholderText, "Rechercher dans les modules intégrés",
                  "Search bundled modules")
        self.catalogue_filter.textChanged.connect(self.filter_catalogue)
        catalogue.addWidget(self.catalogue_filter)
        self.catalogue = QListWidget()
        self.catalogue.itemActivated.connect(self.show_module_details)
        catalogue.addWidget(self.catalogue)
        self.button(catalogue, "Créer un module", "Create a module", self.new_module, primary=True)

        history = self.case_view("Actions et journal", "Actions and history")
        self.history_filter = QLineEdit()
        self.bind(self.history_filter.setPlaceholderText, "Filtrer par action ou opérateur",
                  "Filter by action or operator")
        self.history_filter.textChanged.connect(self.reset_history)
        history.addWidget(self.history_filter)
        self.history_rows = QListWidget()
        self.history_rows.itemActivated.connect(self.show_event)
        history.addWidget(self.history_rows)
        actions = QHBoxLayout()
        history.addLayout(actions)
        self.button(actions, "Actualiser le journal", "Refresh history", self.reset_history)
        self.button(actions, "Afficher les événements précédents", "Load earlier events",
                    self.load_history)
        self.more_history = self.buttons[-1]
        self.button(actions, "Exporter le journal et les métadonnées", "Export audit and evidence metadata",
                    self.export_case_report, primary=True)
        actions.addStretch()
        self.history_before = None
        self.history_page = history.parentWidget()
        self.navigation_group("SYSTÈME", "SYSTEM")
        settings_page = self.page("Diagnostic", "Diagnostics")
        self.system_panel = SystemPanel(self.tr_pair)
        settings_page.addWidget(self.system_panel, 2)
        self.diagnostics = QListWidget()
        settings_page.addWidget(self.diagnostics)
        diagnostic_actions = QHBoxLayout()
        settings_page.addLayout(diagnostic_actions)
        self.button(diagnostic_actions, "Actualiser", "Refresh", self.refresh_diagnostics)
        diagnostic_actions.addStretch()
        entity_page = self.page("Configuration de l’entité", "Organization settings")
        self.entity_panel = EntityPanel(data_directory(), self.tr_pair)
        entity_page.addWidget(self.entity_panel)
        integrity = self.case_view("Intégrité", "Integrity")
        self.integrity_context = QLabel()
        self.integrity_context.setTextFormat(Qt.TextFormat.PlainText)
        integrity.addWidget(self.integrity_context)
        self.integrity_files = QListWidget()
        integrity.addWidget(self.integrity_files)
        self.button(integrity, "Comparer avec l’empreinte enregistrée",
                    "Compare against the recorded hash", self.verify_integrity, primary=True)
        self.button(integrity, "Exporter l’audit de l’affaire", "Export case audit",
                    self.export_case_report)

        reports = self.case_view("Rapports PDF", "PDF reports")
        self.pdf_reports_page = reports.parentWidget()
        self.pdf_reports = QListWidget()
        reports.addWidget(self.pdf_reports)
        self.button(reports, "Actualiser la liste", "Refresh list", self.refresh_pdf_reports)
        self.button(reports, "Ouvrir le dossier du rapport", "Open report folder",
                    self.open_pdf_folder, primary=True)

        quick_actions = self.page("Actions rapides", "Quick actions", grouped=False)
        antivirus = self.quick_action_section(quick_actions, "Antivirus", "Antivirus")
        self.quick_action_card(
            antivirus, "Scan antivirus", "Antivirus scan",
            "Monte le support, lance ClamAV et enregistre le rapport PDF.",
            "Mount the device, run ClamAV and save the PDF report.",
            "shield", self.quick_scan, primary=True,
        )
        self.quick_action_card(
            antivirus, "Mettre à jour l’antivirus", "Update antivirus",
            "Télécharge les signatures ClamAV dans le profil Vigil.",
            "Download ClamAV signatures into the Vigil profile.",
            "upload", self.quick_update,
        )
        self.quick_action_card(
            antivirus, "Rapports antivirus", "Antivirus reports",
            "Retrouve les PDF consolidés des scans rapides.",
            "Find consolidated PDFs from quick scans.",
            "folder", self.show_antivirus_reports,
        )
        antivirus.addStretch()
        storage_actions = self.quick_action_section(quick_actions, "Stockage", "Storage")
        self.quick_action_card(
            storage_actions, "Ajouter un périphérique de stockage", "Add a storage device",
            "Affiche les périphériques détectés et leurs montages.",
            "Show detected devices and their mounts.",
            "hard-drive", self.quick_storage, primary=True,
        )
        storage_actions.addStretch()
        quick_actions.addStretch()

        self.terminal = TerminalPanel()
        self.terminal.completed.connect(self.quick_finished)
        self.terminal_dock = QDockWidget(self)
        self.terminal_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.terminal_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.terminal_dock.setTitleBarWidget(QWidget())
        self.bind(self.terminal_dock.setWindowTitle, "Centre des tâches", "Task centre")
        self.task_tabs = QTabWidget()
        tasks_page = QWidget()
        tasks_layout = QVBoxLayout(tasks_page)
        self.tasks = QListWidget()
        tasks_layout.addWidget(self.tasks)
        self.cancel_task_button = QPushButton()
        self.bind(self.cancel_task_button.setText, "Annuler la commande active", "Cancel active command")
        self.cancel_task_button.setEnabled(False)
        self.cancel_task_button.clicked.connect(self.terminal.interrupt)
        tasks_layout.addWidget(self.cancel_task_button)
        self.task_tabs.addTab(self.terminal, "Terminal")
        self.bind(lambda label: self.task_tabs.setTabText(1, label), "Tâches", "Tasks")
        self.task_tabs.addTab(tasks_page, "")
        self.terminal_dock.setWidget(self.task_tabs)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self.terminal_dock.hide()
        self.terminal_toggle = QPushButton()
        self.terminal_toggle.setCheckable(True)
        self.terminal_toggle.clicked.connect(self.toggle_terminal)
        self.terminal_dock.visibilityChanged.connect(self.update_terminal_toggle)
        self.statusBar().addPermanentWidget(self.terminal_toggle)
        self.refresh_operators()
        self.translate()
        self.refresh_cases()
        self.navigation.setCurrentRow(1)
        self.case_navigation.setCurrentRow(0)
        self.mount_timer = QTimer(self)
        self.mount_timer.timeout.connect(self.refresh_case_mount)
        self.mount_timer.start(3000)

    def tr_pair(self, french, english):
        return english if self.language == "en" else french

    def bind(self, setter, french, english):
        self.localized.append((setter, french, english))

    def navigation_group(self, french, english):
        item = QListWidgetItem(self.navigation)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        button = QPushButton()
        button.setStyleSheet(
            "QPushButton { text-align: left; background: #101318; "
            "border: 1px solid transparent; color: #57C7D4; } "
            "QPushButton:hover { background: #203741; color: #80DEE8; } "
            "QPushButton:focus { border-color: #57C7D4; }"
        )
        self.navigation.setItemWidget(item, button)
        key = french
        self.current_group = key
        self.group_items[key] = []
        self.group_open[key] = True

        def label(value):
            item.setText(value)
            arrow = "▾" if self.group_open[key] else "▸"
            button.setText(f"{arrow}  {value}")
            button.setAccessibleName(value)
            button.ensurePolished()
            height = max(button.sizeHint().height(), button.fontMetrics().height() + 16)
            button.setMinimumHeight(height)
            item.setSizeHint(QSize(0, height + 8))

        def toggle():
            self.group_open[key] = not self.group_open[key]
            for child in self.group_items[key]:
                child.setHidden(not self.group_open[key])
            label(self.tr_pair(french, english))

        self.bind(label, french, english)
        button.clicked.connect(toggle)

    def open_page(self, item, _previous):
        if item is not None:
            index = item.data(Qt.ItemDataRole.UserRole)
            if index is not None:
                self.pages.setCurrentIndex(index)
                if (self.pages.currentWidget() is self.case_workspace_page
                        and self.case_pages.currentWidget() is self.history_page):
                    self.reset_history()

    def page(self, french, english, *, heading=True, grouped=True):
        widget = QWidget()
        widget.setProperty("workspacePage", True)
        item = QListWidgetItem(self.navigation)
        item.setData(Qt.ItemDataRole.UserRole, self.pages.addWidget(widget))
        if grouped:
            self.group_items[self.current_group].append(item)
        self.bind(item.setText, french, english)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if heading:
            title = QLabel()
            title.setObjectName("pageTitle")
            self.bind(title.setText, french, english)
            layout.addWidget(title)
        return layout

    def case_view(self, french, english):
        widget = QWidget()
        self.case_pages.addWidget(widget)
        item = QListWidgetItem(self.case_navigation)
        self.bind(item.setText, french, english)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout

    def open_case_view(self, index):
        if index >= 0:
            self.case_pages.setCurrentIndex(index)
            if self.case_pages.currentWidget() is self.history_page:
                self.reset_history()
            if self.case_pages.currentWidget() is self.pdf_reports_page:
                self.refresh_pdf_reports()

    def quick_action_section(self, page, french, english):
        section = QFrame()
        section.setObjectName("quickActionSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel()
        title.setObjectName("quickActionTitle")
        self.bind(title.setText, french, english)
        layout.addWidget(title)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        page.addWidget(section)
        return actions

    def quick_action_card(self, row, french, english, description_fr, description_en,
                          icon_name, action, *, primary=False):
        card = QFrame()
        card.setObjectName("quickActionCard")
        card.setMaximumWidth(310)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        description = QLabel()
        description.setWordWrap(True)
        self.bind(description.setText, description_fr, description_en)
        layout.addWidget(description)
        layout.addStretch()
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self.button(buttons, french, english, action, primary=primary)
        button = self.buttons[-1]
        button.setIcon(self.action_icon(icon_name, "#101318" if primary else "#57C7D4"))
        buttons.addStretch()
        row.addWidget(card)

    @staticmethod
    def action_icon(name, color):
        source = legacy_base() / "data/icons" / f"{name}.svg"
        if not source.is_file():
            source = Path(sys.prefix) / "share/vigil/icons" / f"{name}.svg"
        if not source.is_file():
            return QIcon()
        svg = source.read_bytes().replace(b"currentColor", color.encode("ascii"))
        renderer = QSvgRenderer(QByteArray(svg))
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        with QPainter(pixmap) as painter:
            renderer.render(painter)
        return QIcon(pixmap)

    def button(self, layout, french, english, action, *, primary=False):
        button = QPushButton()
        if primary:
            button.setProperty("primary", True)
        self.bind(button.setText, french, english)
        button.clicked.connect(action)
        self.buttons.append(button)
        layout.addWidget(button)

    def change_language(self, language):
        if language == self.language:
            return
        self.language = language
        self.settings.setValue("language", self.language)
        self.settings.sync()
        self.translate()
        if self.settings.status() != QSettings.Status.NoError:
            self.notify("Impossible d’enregistrer la langue.", "Could not save the language.")

    def translate(self):
        app = QApplication.instance()
        app.removeTranslator(self.translator)
        if self.language == "fr":
            path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if self.translator.load("qtbase_fr", path):
                app.installTranslator(self.translator)
        for setter, french, english in self.localized:
            setter(self.tr_pair(french, english))
        self.statusBar().showMessage(
            self.tr_pair("Calcul en cours…", "Computing…") if self.busy else ""
        )
        if self.operator.count():
            self.operator.setItemText(0, self.tr_pair("Choisir un opérateur", "Choose an operator"))
        self.refresh_diagnostics()
        self.system_panel.render()
        self.explorer.retranslate()
        self.entity_panel.retranslate()
        self.update_terminal_toggle(not self.terminal_dock.isHidden())
        self.refresh_case_mount()
        self.update_case_label()
        self.refresh_dashboard()

    def notify(self, french, english, details=""):
        message = QMessageBox(self)
        message.setWindowTitle("Vigil")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(self.tr_pair(french, english))
        if details:
            message.setDetailedText(details)
        message.exec()

    def fail(self, error):
        self.notify("L’opération a échoué.", "The operation failed.", str(error))

    def refresh_diagnostics(self):
        result = doctor()
        self.diagnostics.clear()
        self.diagnostics.addItem(self.tr_pair("Session graphique", "Graphical session") + f"  ·  {result['session']}")
        for name, path in result["tools"].items():
            self.diagnostics.addItem(f"{name}  ·  {path or self.tr_pair('Indisponible', 'Unavailable')}")
        self.modules.clear()
        self.catalogue.clear()
        manifests, errors = discover(BUILTIN_MODULES)
        for module in manifests.values():
            names = ANALYSIS_LABELS.get(module.id.removeprefix("vigil."), (module.name, module.name))
            self.modules.addItem(f"{self.tr_pair(*names)}  ·  {module.entrypoint.rsplit('/', 1)[-1]}")
            self.add_row(self.catalogue, f"{module.id}  ·  {module.version}", module.id)
        self.filter_catalogue(self.catalogue_filter.text())
        for path in errors:
            self.modules.addItem(self.tr_pair("Manifeste invalide", "Invalid manifest") + f"  ·  {path}")

    def refresh_cases(self, selected=None):
        try:
            with storage.database(self.database_path) as connection:
                rows = list(connection.execute(
                    "SELECT id, name FROM cases WHERE name <> ? ORDER BY created_at, id",
                    (storage.ANTIVIRUS_CASE_NAME,),
                ))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        if not any(case_id == self.active_case_id for case_id, _ in rows):
            self.active_case_id = ""
        selected = selected or self.active_case_id
        self.cases.blockSignals(True)
        self.cases.clear()
        for case_id, name in rows:
            self.add_row(self.cases, name, case_id)
            if case_id == selected:
                self.cases.setCurrentRow(self.cases.count() - 1)
        self.filter_cases(self.case_search.text())
        self.cases.blockSignals(False)
        self.refresh_evidence()

    def filter_cases(self, text):
        query = text.strip().casefold()
        for index in range(self.cases.count()):
            item = self.cases.item(index)
            item.setHidden(query not in item.text().casefold())

    @staticmethod
    def add_row(widget, label, identifier):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, identifier)
        widget.addItem(item)

    def active_case_item(self):
        return next((
            self.cases.item(index) for index in range(self.cases.count())
            if self.cases.item(index).data(Qt.ItemDataRole.UserRole) == self.active_case_id
        ), None)

    def case_clicked(self, item):
        if item is None or item.isHidden():
            return
        target_id = item.data(Qt.ItemDataRole.UserRole)
        current = self.active_case_item()
        previous = current.text() if current is not None and current is not item else None
        if not self.confirm_case_selection(previous, item.text()):
            if current is None or current.isHidden():
                self.cases.setCurrentRow(-1)
            else:
                self.cases.setCurrentItem(current)
            return
        self.active_case_id = target_id
        self.refresh_evidence()
        self.reset_history()

    def confirm_case_selection(self, current, target):
        dialog = QMessageBox(self)
        title = (self.tr_pair("Changer d’affaire", "Switch case") if current is not None
                 else self.tr_pair("Confirmer l’affaire", "Confirm case"))
        dialog.setWindowTitle(title)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        if current is None:
            dialog.setText(self.tr_pair(f"Activer l’affaire « {target} » ?",
                                        f"Activate case “{target}”?"))
        else:
            dialog.setText(self.tr_pair(f"Passer de « {current} » à « {target} » ?",
                                        f"Switch from “{current}” to “{target}”?"))
        accept = dialog.addButton(self.tr_pair("Confirmer", "Confirm"),
                                  QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.tr_pair("Annuler", "Cancel"),
                                  QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        return dialog.clickedButton() == accept

    def update_case_label(self):
        item = self.active_case_item()
        name = item.text() if item else self.tr_pair("Aucune affaire active", "No active case")
        label = self.tr_pair("Affaire verrouillée", "Locked case") + f"  ·  {name}" if item else name
        self.case_label.setText(label)
        self.integrity_context.setText(label)
        self.module_case.setText(label)
        self.active_case.setText("·  " + self.active_case.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, 200
        ))
        self.active_case.setToolTip(label)

    def refresh_evidence(self, *_):
        self.update_case_label()
        self.evidence.clear()
        self.integrity_files.clear()
        self.refresh_pdf_reports()
        self.explorer.set_files([])
        self.refresh_dashboard()
        case = self.active_case_item()
        if case is None:
            return
        try:
            with storage.database(self.database_path) as connection:
                rows = list(connection.execute(
                    "SELECT id, path, sha256 FROM evidence WHERE case_id = ? ORDER BY path",
                    (case.data(Qt.ItemDataRole.UserRole),),
                ))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        self.explorer.set_files(rows)
        for evidence_id, path, digest in rows:
            label = f"{path}  ·  {digest}"
            self.add_row(self.evidence, label, evidence_id)
            self.add_row(self.integrity_files, label, evidence_id)

    def filter_catalogue(self, value):
        query = value.strip().casefold()
        for index in range(self.catalogue.count()):
            item = self.catalogue.item(index)
            item.setHidden(query not in item.text().casefold())

    def show_module_details(self, item):
        module_id = item.data(Qt.ItemDataRole.UserRole)
        manifests, _ = discover(BUILTIN_MODULES)
        manifest = manifests.get(module_id)
        if manifest is None:
            return
        tr = self.tr_pair
        details = "\n".join((
            f"{manifest.id} · {manifest.version}",
            f"{tr('Auteur individuel', 'Individual author')}: {tr('Non renseigné', 'Unspecified')}",
            f"{tr('Licence du dépôt', 'Repository license')}: GPL v3",
            f"{tr('Dépendances', 'Dependencies')}: {', '.join(manifest.dependencies) or '—'}",
            f"{tr('Permissions déclarées', 'Declared permissions')}: {', '.join(manifest.capabilities) or '—'}",
            f"{tr('Entrée', 'Entrypoint')}: {manifest.entrypoint}",
            "https://github.com/Gvte-Kali/vigil",
        ))
        self.notify("Module intégré", "Bundled module", details)

    def new_module(self):
        name, accepted = QInputDialog.getText(
            self, self.tr_pair("Créer un module", "Create a module"),
            self.tr_pair("Identifiant local", "Local identifier"),
        )
        if not accepted:
            return
        try:
            path = create_module_draft(self.database_path, name.strip())
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        self.notify("Squelette du module enregistré.", "Module draft created.", str(path))

    def refresh_dashboard(self):
        self.dashboard_case.setText(self.active_case.toolTip())
        self.dashboard_events.clear()
        count = None
        events = []
        if self.active_case_id:
            try:
                with storage.database(self.database_path) as connection:
                    count = connection.execute(
                        "SELECT count(*) FROM evidence WHERE case_id = ?", (self.active_case_id,),
                    ).fetchone()[0]
                    events = case_events(connection, self.active_case_id, limit=8)
            except (OSError, ValueError, sqlite3.Error):
                pass
        for card, (label, value) in zip(self.dashboard_cards, (
            (self.tr_pair("Fichiers enregistrés", "Registered files"), count),
            (self.tr_pair("Événements récents", "Recent events"), len(events) if count is not None else None),
            (self.tr_pair("Tâches locales actives", "Active local tasks"),
             int(self.busy is not None) + int(self.terminal.session is not None)),
        )):
            card.setText(f"{label}\n{value if value is not None else '—'}")
        for event in events:
            self.dashboard_events.addItem(
                f"{event['timestamp']}  ·  {event['action']}  ·  {event['operator']}"
            )

    def preview_evidence(self, name, digest):
        if self.busy is not None:
            return
        case_id = self.active_case_id

        def display(snapshot):
            if self.active_case_id == case_id:
                self.explorer.show_preview(name, digest, snapshot)

        self.run_task(lambda: inspect_file(Path(name)), display)

    def verify_integrity(self):
        self.verify_selected_file(self.integrity_files.currentItem())

    def reset_history(self, *_):
        self.history_rows.clear()
        self.history_before = None
        self.load_history()

    def load_history(self):
        self.more_history.setEnabled(False)
        if not self.active_case_id:
            return
        try:
            with storage.database(self.database_path) as connection:
                rows = case_events(
                    connection, self.active_case_id, self.history_filter.text().strip(),
                    self.history_before, PAGE_SIZE + 1,
                )
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        for row in rows[:PAGE_SIZE]:
            self.add_row(self.history_rows,
                         f"{row['timestamp']}  ·  {row['operator']}  ·  {row['action']}",
                         row["details"])
            self.history_before = row["sequence"]
        self.more_history.setEnabled(len(rows) > PAGE_SIZE)

    def refresh_pdf_reports(self):
        self.pdf_reports.clear()
        case_id = self.active_case_id
        if not case_id:
            return
        try:
            with storage.database(self.database_path) as connection:
                row = connection.execute("SELECT legacy_path FROM cases WHERE id = ?", (case_id,)).fetchone()
            for path in case_pdf_reports(self.database_path, case_id, row["legacy_path"] if row else None):
                self.add_row(self.pdf_reports, f"{path.parent.name}  ·  {path.name}", str(path))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)

    def open_pdf_folder(self):
        item = self.pdf_reports.currentItem()
        if item is None:
            self.notify("Sélectionnez un rapport.", "Select a report.")
            return
        directory = Path(item.data(Qt.ItemDataRole.UserRole)).parent
        if not directory.is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            self.notify("Impossible d’ouvrir le dossier du rapport.",
                        "Could not open the report folder.", str(directory))

    def export_case_report(self):
        case_id = self.active_case_id
        if not case_id:
            self.notify("Confirmez une affaire dans l’onglet Affaires.",
                        "Confirm a case in the Cases tab.")
            return
        self.run_task(
            lambda: case_report(self.database_path, case_id),
            lambda path: self.notify("Rapport JSON et manifeste enregistrés.",
                                     "JSON report and manifest saved.", str(path)),
        )

    def show_event(self, item):
        self.notify("Événement d’audit de l’affaire", "Case audit event",
                    item.data(Qt.ItemDataRole.UserRole))

    def refresh_operators(self, selected=None):
        if selected is None:
            selected = self.settings.value("operator_id")
        try:
            with storage.database(self.database_path) as connection:
                operators = storage.list_operators(connection)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        self.operator.blockSignals(True)
        self.operator.clear()
        self.operator.addItem(self.tr_pair("Choisir un opérateur", "Choose an operator"))
        for operator_id, name in operators:
            self.operator.addItem(name, operator_id)
        self.operator.setCurrentIndex(max(0, self.operator.findData(selected)) if selected else 0)
        self.operator.blockSignals(False)
        self.save_operator()

    def save_operator(self, *_):
        self.settings.setValue("operator_id", self.operator.currentData() or "")

    def session_operator_input(self):
        tr = self.tr_pair
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Opérateur de la session", "Session operator"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(tr("Choisissez l’opérateur.", "Choose the operator.")))
        choices = QComboBox()
        choices.addItems([self.operator.itemText(index) for index in range(1, self.operator.count())])
        choices.setCurrentIndex(max(0, self.operator.currentIndex() - 1))
        layout.addWidget(choices)
        create = QPushButton(tr("Créer un opérateur", "Create an operator"))
        layout.addWidget(create)
        new_name = QLineEdit()
        new_name.setPlaceholderText(tr("Nom du nouvel opérateur", "New operator name"))
        layout.addWidget(new_name)
        new_name.hide()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        confirm.setText(tr("Continuer", "Continue"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", "Cancel"))
        confirm.setEnabled(choices.count() > 0)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def create_operator():
            creating = new_name.isHidden()
            new_name.setVisible(creating)
            choices.setEnabled(not creating)
            create.setText(tr("Choisir un opérateur existant", "Choose an existing operator")
                           if creating else tr("Créer un opérateur", "Create an operator"))
            confirm.setEnabled(bool(new_name.text().strip()) if creating else choices.count() > 0)
            if creating:
                new_name.setFocus()

        create.clicked.connect(create_operator)
        new_name.textChanged.connect(lambda value: confirm.setEnabled(bool(value.strip())))
        if not choices.count():
            create_operator()
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return (choices.currentText() if new_name.isHidden() else new_name.text()), accepted

    def choose_session_operator(self):
        while True:
            name, accepted = self.session_operator_input()
            if not accepted:
                return False
            name = name.strip()
            if name and len(name) <= 120 and name.isprintable():
                break
            self.notify("Saisissez un nom lisible de 1 à 120 caractères.",
                        "Enter a printable name of 1 to 120 characters.")
        self.add_operator(name)
        if self.operator.currentText() != name or self.operator.currentData() is None:
            return False
        self.operator.setEnabled(False)
        self.manage_operator_button.hide()
        return True

    def manage_operators(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(self.tr_pair("Opérateurs", "Operators"))
        dialog.setLabelText(self.tr_pair("Nom du nouvel opérateur", "New operator name"))
        dialog.setOkButtonText(self.tr_pair("Enregistrer", "Save"))
        dialog.setCancelButtonText(self.tr_pair("Annuler", "Cancel"))
        if dialog.exec():
            self.add_operator(dialog.textValue())

    def add_operator(self, name):
        name = name.strip()
        if not name or len(name) > 120 or not name.isprintable():
            self.notify("Saisissez un nom lisible de 1 à 120 caractères.",
                        "Enter a printable name of 1 to 120 characters.")
            return
        try:
            with storage.database(self.database_path) as connection:
                operator_id = storage.register_operator(connection, name)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        self.refresh_operators(operator_id)

    def require_operator(self):
        if self.operator.currentData() is None:
            self.notify("Créez un opérateur avec Opérateurs… ou sélectionnez-en un.",
                        "Create an operator with Operators… or select one.")
            return None
        return self.operator.currentText()

    def create_case(self):
        operator = self.require_operator()
        name = self.case_name.text().strip()
        if not operator:
            return
        if not name:
            self.notify("Saisissez le nom de l’affaire.", "Enter the case name.")
            return
        try:
            with storage.database(self.database_path) as connection:
                case_id = storage.create_case(connection, name, operator)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        self.case_name.clear()
        self.refresh_cases(case_id)

    def import_case(self):
        operator = self.require_operator()
        if not operator:
            return
        directory = QFileDialog.getExistingDirectory(
            self, self.tr_pair("Dossier du projet historique", "Legacy project folder"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not directory:
            return
        try:
            path = Path(directory).resolve(strict=True)
            name, raw = storage.read_legacy_project(path)
            with storage.database(self.database_path) as connection:
                case_id = storage.create_case(connection, name, operator, str(path), raw)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        self.refresh_cases(case_id)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr_pair("Choisir un fichier", "Choose a file"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return path

    def add_file(self):
        case = self.active_case_item()
        if case is None:
            self.notify("Confirmez une affaire dans l’onglet Affaires.", "Confirm a case in the Cases tab.")
            return
        operator = self.require_operator()
        if not operator or not (path := self.choose_file()):
            return
        case_id = case.data(Qt.ItemDataRole.UserRole)
        self.run_task(
            lambda: storage.register_file(self.database_path, case_id, Path(path), operator),
            lambda _: self.refresh_evidence(),
        )

    def verify_file(self):
        self.verify_selected_file(self.evidence.currentItem())

    def verify_selected_file(self, item):
        if item is None:
            self.notify("Sélectionnez un fichier enregistré.", "Select a registered file.")
            return
        operator = self.require_operator()
        if not operator:
            return
        evidence_id = item.data(Qt.ItemDataRole.UserRole)
        self.run_task(
            lambda: storage.verify_file(self.database_path, evidence_id, operator),
            self.show_verification,
        )

    def show_verification(self, result):
        details = f"SHA-256\n{result['expected_sha256']}\n{result['sha256']}"
        if result["matches"]:
            self.notify("L’empreinte correspond.", "The fingerprint matches.", details)
        else:
            self.notify("L’empreinte a changé.", "The fingerprint changed.", details)

    def inspect_image(self):
        if path := self.choose_file():
            self.run_task(lambda: inspect_raw(Path(path)), self.show_image)

    def show_image(self, result):
        partitions = [
            f"#{row['number']}  ·  {row['type']}  ·  {row['offset']} / {row['size']}"
            for row in result["partitions"]
        ]
        summary = self.tr_pair("Décalage / taille (octets)", "Offset / size (bytes)")
        self.notify(
            "Inspection RAW terminée.", "RAW inspection complete.",
            "\n".join([summary, *partitions, f"SHA-256\n{result['sha256']}"]),
        )

    def query_index(self):
        case = self.active_case_item()
        if case is None:
            self.notify("Confirmez une affaire dans l’onglet Affaires.", "Confirm a case in the Cases tab.")
            return
        operator = self.require_operator()
        if not operator or not (path := self.choose_file()):
            return
        case_id = case.data(Qt.ItemDataRole.UserRole)
        self.run_task(
            lambda: query_census(self.database_path, case_id, operator, Path(path)),
            self.show_index_result,
        )

    def show_index_result(self, result):
        if result:
            self.notify(
                f"Extensions discordantes (maximum {CENSUS_LIMIT} résultats).",
                f"Extension mismatches (up to {CENSUS_LIMIT} results).",
                result,
            )
        else:
            self.notify("Aucune extension discordante.", "No extension mismatches.")

    def run_task(self, operation, on_success):
        self.busy = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.busy)
        self.busy.started.connect(self.worker.run)
        self.worker.finished.connect(self.store_result)
        self.worker.finished.connect(self.busy.quit)
        self.busy.finished.connect(self.worker.deleteLater)
        self.busy.finished.connect(self.finish_task)
        self.on_success = on_success
        for button in self.buttons:
            button.setEnabled(False)
        self.statusBar().showMessage(self.tr_pair("Calcul en cours…", "Computing…"))
        self.busy.start()
        self.refresh_dashboard()

    @Slot(object, object)
    def store_result(self, result, error):
        self.task_result = result, error

    @Slot()
    def finish_task(self):
        self.busy.deleteLater()
        self.busy = self.worker = None
        self.statusBar().clearMessage()
        for button in self.buttons:
            button.setEnabled(True)
        result, error = self.task_result
        self.refresh_dashboard()
        if error:
            self.fail(error)
        else:
            self.on_success(result)

    def refresh_case_mount(self):
        try:
            entries = read_zones()["/investigation"]
        except OSError:
            entries = None
        if entries is None:
            state = self.tr_pair("État indisponible", "Status unavailable")
        elif not entries:
            state = self.tr_pair("Non monté", "Not mounted")
        elif any(target == "/investigation" for target, *_ in entries):
            state = self.tr_pair("Monté", "Mounted")
        else:
            state = self.tr_pair("Sous-montages", "Submounts")
        sources = [
            " · ".join(filter(None, (source, target, filesystem, mode)))
            for target, source, filesystem, mode in entries or ()
        ]
        self.investigation_mount.setText("\n".join([f"/investigation  ·  {state}", *sources]))
        color = "#80D7A4" if entries and all(row[3] == "ro" for row in entries) else "#EBC47A"
        self.investigation_mount.setStyleSheet(f"color: {color}; padding: 4px;")

    def request_mount(self):
        self.request_mount_action("mount")

    def request_unmount(self):
        self.request_mount_action("unmount")

    def request_mount_action(self, operation):
        self.refresh_case_mount()
        if self.terminal.session is not None or self.busy is not None:
            self.notify("Attendez la fin de l’opération en cours.", "Wait for the current operation.")
            return
        case_id = self.active_case_id
        if not case_id:
            self.notify("Confirmez une affaire avant cette opération.",
                        "Confirm a case before this operation.")
            return
        operator = self.require_operator()
        if not operator:
            return
        response = QMessageBox.question(
            self, "Vigil",
            (self.tr_pair("Ouvrir le montage Vigil 1.0 dans le terminal par défaut ?",
                          "Open Vigil 1.0 mounting in the default terminal?")
             if operation == "mount" else
             self.tr_pair("Ouvrir le démontage Vigil 1.0 dans le terminal par défaut ?", "Open Vigil 1.0 unmounting in the default terminal?")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        details = {"run_id": uuid4().hex, "operation": operation, "target": "/investigation"}
        try:
            with storage.database(self.database_path) as connection:
                storage.audit(connection, operator, case_id, "mount.request", details)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        try:
            case = self.active_case_item()
            launch_terminal(legacy_mount_command(
                operation, self.database_path, case_id, case.text(), operator,
            ))
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        self.statusBar().showMessage(self.tr_pair(
            "Script historique ouvert dans le terminal.",
            "Legacy script opened in the terminal.",
        ), 10000)

    def update_terminal_toggle(self, visible):
        self.terminal_toggle.setChecked(visible)
        self.terminal_toggle.setText(self.tr_pair("Masquer le centre des tâches", "Hide task centre")
                                     if visible else
                                     self.tr_pair("Afficher le centre des tâches", "Show task centre"))

    def toggle_terminal(self, visible):
        self.terminal_dock.setVisible(visible)
        if visible:
            self.resizeDocks([self.terminal_dock], [270], Qt.Orientation.Vertical)

    def start_quick_action(self, command):
        try:
            launch_action(command())
        except (OSError, ValueError) as error:
            self.fail(error)

    def show_antivirus_reports(self):
        try:
            with storage.database(self.database_path) as connection:
                case_id = storage.find_antivirus_case(connection)
            reports = case_pdf_reports(self.database_path, case_id) if case_id else []
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        reports = [report for report in reports if report.name.startswith("rapport_clamav_")]
        if not reports:
            self.notify("Aucun rapport antivirus consolidé.", "No consolidated antivirus report.")
            return
        names = [f"{report.parent.name} · {report.name}" for report in reports]
        selected, accepted = QInputDialog.getItem(
            self, self.tr_pair("Rapports antivirus", "Antivirus reports"),
            self.tr_pair("Choisir le rapport dont tu veux ouvrir le dossier.",
                         "Choose a report to open its folder."),
            names, len(names) - 1, False,
        )
        if accepted:
            directory = reports[names.index(selected)].parent
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
                self.notify("Impossible d’ouvrir le dossier.", "Could not open the folder.", str(directory))

    def quick_scan(self):
        operator = self.require_operator()
        if not operator:
            return
        try:
            existing = read_zones()["/investigation"]
        except OSError as error:
            self.fail(error)
            return
        if existing:
            self.notify("Le scan rapide nécessite une zone /investigation démontée.",
                        "Quick scan requires an unmounted /investigation zone.",
                        "\n".join(f"{source} → {target}" for target, source, *_ in existing))
            return
        response = QMessageBox.question(
            self, "Vigil",
            self.tr_pair("Lancer le parcours montage, scan et démontage dans l’affaire Scan antivirus ?",
                         "Run the mount, scan and unmount workflow in the Scan antivirus case?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        run_id = uuid4().hex
        try:
            with storage.database(self.database_path) as connection:
                case_id = storage.antivirus_case(connection, operator)
                storage.audit(connection, operator, case_id, "antivirus.request", {"run_id": run_id})
            self.refresh_cases()
            launch_action(legacy_mount_command(
                "scan", self.database_path, case_id, "Scan antivirus", operator, run_id=run_id,
            ))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)

    def quick_update(self):
        response = QMessageBox.question(
            self, "Vigil",
            self.tr_pair("Télécharger les signatures ClamAV dans le profil Vigil ?",
                         "Download ClamAV signatures into the Vigil profile?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.start_quick_action(lambda: update_command(self.database_path))

    def quick_storage(self):
        self.start_quick_action(lambda: [
            tool("lsblk"), "-o", "NAME,PATH,TYPE,SIZE,FSTYPE,RO,MOUNTPOINTS",
        ])
        self.system_panel.refresh()
        self.statusBar().showMessage(self.tr_pair(
            "Connectez le périphérique puis relancez l’inventaire. Montage réservé à l’administrateur.",
            "Connect the device and refresh the inventory. Mounting requires an administrator.",
        ), 10000)

    def quick_finished(self, code):
        self.cancel_task_button.setEnabled(False)
        status = self.tr_pair(f"Code de sortie : {code}", f"Exit code: {code}")
        self.terminal.appendPlainText(status)
        if self.tasks.count():
            task = self.tasks.item(0)
            if code == 2 and task.text() == "freshclam" and (
                "Can't open/parse the config file" in self.terminal.toPlainText()
            ):
                self.terminal.appendPlainText(self.tr_pair(
                    "FreshClam refuse le fichier local. Si /etc/clamav/freshclam.conf fonctionne, "
                    "vérifiez les refus AppArmor. Voir docs/configuration/clamav.md.",
                    "FreshClam rejected the local file. If /etc/clamav/freshclam.conf works, "
                    "check AppArmor denials. See docs/configuration/clamav.md.",
                ))
            task.setText(f"{task.text()} · {status}")
        self.refresh_dashboard()
        self.system_panel.refresh()

    def confirm_close(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.tr_pair("Fermer Vigil", "Close Vigil"))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        case = self.active_case_item()
        if case is not None:
            name = case.text()
            dialog.setText(self.tr_pair(
                f"Enregistrer l’état de l’affaire « {name} » et fermer Vigil ?",
                f"Save the state of case “{name}” and close Vigil?",
            ))
        else:
            dialog.setText(self.tr_pair("Fermer Vigil ?", "Close Vigil?"))
        accept = dialog.addButton(self.tr_pair("Fermer", "Close"), QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.tr_pair("Annuler", "Cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        return dialog.clickedButton() == accept

    def save_before_close(self):
        """Commit future pending case edits before synchronizing preferences."""
        if self.active_case_id:
            if not self.database_path.is_file():
                raise ValueError("case database unavailable")
            with storage.database(self.database_path) as connection:
                case = connection.execute(
                    "SELECT 1 FROM cases WHERE id = ?", (self.active_case_id,)
                ).fetchone()
                if case is None:
                    raise ValueError("active case unavailable")
        self.entity_panel.save()
        self.save_operator()
        self.settings.setValue("language", self.language)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise ValueError("could not save workspace preferences")

    def confirm_block_changes(self, changes):
        tr = self.tr_pair
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Modes d’accès aux périphériques", "Device access modes"))
        layout = QVBoxLayout(dialog)

        def text(value):
            label = QLabel(value)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(label)

        def mode(record):
            if record is None:
                return tr("absent", "absent")
            return tr("lecture seule (RO)", "read-only (RO)") if record["mode"] == "ro" else (
                tr("lecture-écriture (RW)", "read-write (RW)")
            )

        text(tr(
            "Les zones Vigil sont démontées. Les écarts ci-dessous concernent le verrou "
            "logiciel au niveau bloc dans Linux. Ils ne décrivent ni le mode d’un montage "
            "ni un verrou matériel de l’appareil.",
            "The Vigil zones are unmounted. The differences below concern Linux block-level "
            "software protection. They do not describe filesystem mount options or hardware locks.",
        ))
        text(tr(
            "Choisis le mode bloc souhaité pour chaque entrée. Si le mode actuel est différent, "
            "Vigil restera ouvert pour qu’un administrateur vérifie et applique le changement.",
            "Choose the desired block mode for each entry. If it differs from the current mode, "
            "Vigil stays open so an administrator can verify and apply the change.",
        ))
        choices = {}
        for name, before, after in changes:
            record = after if after is not None else before
            parent = record.get("parent")
            level = (tr(f"partition du disque /dev/{parent}", f"partition of disk /dev/{parent}")
                     if parent else tr("périphérique bloc entier", "whole block device"))
            text(f"/dev/{name} · {level}\n"
                 f"{tr('Au démarrage', 'At startup')} : {mode(before)}"
                 f" → {tr('Maintenant', 'Now')} : {mode(after)}")
            if after is not None:
                choice = QComboBox()
                choice.addItem(tr("Lecture seule (RO)", "Read-only (RO)"), "ro")
                choice.addItem(tr("Lecture-écriture (RW)", "Read-write (RW)"), "rw")
                choice.setCurrentIndex(choice.findData(after["mode"]))
                choice.setAccessibleName(f"/dev/{name}")
                layout.addWidget(choice)
                choices[name] = choice
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Vérifier et fermer", "Check and close"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Rester dans Vigil", "Stay in Vigil"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return {name: choice.currentData() for name, choice in choices.items()}

    def closeEvent(self, event):
        if self.closing_checks:
            event.ignore()
            return
        if self.busy is not None or self.terminal.session is not None:
            event.ignore()
            self.notify("Attendez la fin de l’opération avant de fermer Vigil.",
                        "Wait for the operation to finish before closing Vigil.")
            return
        if not self.confirm_close():
            event.ignore()
            return

        self.closing_checks = True
        progress = QProgressDialog(
            self.tr_pair("Vérification des montages et des modes bloc…",
                         "Checking mounts and block-device modes…"),
            "", 0, 0, self,
        )
        progress.setWindowTitle(self.tr_pair("Vérification avant fermeture", "Shutdown checks"))
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
        error = None
        stage = "system"
        try:
            if self.startup_state_error is not None:
                raise self.startup_state_error
            changes = check_shutdown_state(self.startup_block_modes)
            if changes:
                progress.hide()
                desired = self.confirm_block_changes(changes)
                if desired is None:
                    event.ignore()
                    return
                pending = [
                    f"/dev/{name}: {after['mode'].upper()} → {desired[name].upper()}"
                    for name, _, after in changes if after is not None and after["mode"] != desired[name]
                ]
                if pending:
                    event.ignore()
                    self.notify(
                        "Le mode choisi n’est pas encore appliqué. Fais vérifier ces périphériques "
                        "par un administrateur, puis réessaie. Vigil n’a changé aucun verrou.",
                        "The selected mode is not yet active. Have an administrator check these "
                        "devices, then retry. Vigil has not changed any lock.",
                        "\n".join(pending),
                    )
                    return
                progress.show()
            stage = "save"
            self.save_before_close()
            stage = "system"
            if check_shutdown_state(self.startup_block_modes) != changes:
                raise ValueError(self.tr_pair(
                    "L’état des périphériques a changé pendant la vérification. Réessayez.",
                    "Device state changed during the check. Try again.",
                ))
        except (OSError, ValueError, sqlite3.Error) as failure:
            error = failure
        finally:
            progress.hide()
            progress.deleteLater()
            self.closing_checks = False

        if error is not None:
            event.ignore()
            if isinstance(error, ShutdownBlocked):
                self.notify(
                    "Fermeture bloquée : un montage subsiste dans /investigation ou /stockage. Démontez la source indiquée.",
                    "Close blocked: a mount remains under /investigation or /stockage. Unmount the listed source.", str(error),
                )
            elif stage == "save":
                self.notify("La sauvegarde a échoué. Vigil reste ouvert.",
                            "Saving failed. Vigil will stay open.", str(error))
            else:
                self.notify("L’état système n’a pas pu être vérifié. Vigil reste ouvert.",
                            "System state could not be verified. Vigil will stay open.", str(error))
            return
        self.mount_timer.stop()
        self.system_panel.stop()
        super().closeEvent(event)


def main():
    if os.geteuid() == 0:
        print("Lancez Vigil en tant qu’utilisateur ordinaire. / Run Vigil as a regular user.",
              file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    window = Workspace(QSettings("Vigil", "Vigil2"), storage.default_database())
    if window.startup_state_error is not None:
        window.notify("Impossible d’enregistrer l’état système initial.",
                      "Could not record the initial system state.", str(window.startup_state_error))
        window.system_panel.stop()
        return 1
    if not window.choose_session_operator():
        window.system_panel.stop()
        return 0
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
