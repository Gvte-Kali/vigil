"""Bilingual Qt workspace for the local Vigil core."""
import json
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QByteArray, QLibraryInfo, QRectF, QSize, QObject, QSettings, QThread, QThreadPool, QTimer, QTranslator, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QBoxLayout, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QInputDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit, QSplitter,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QScrollArea, QStackedWidget, QTabBar,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import storage
from .action_card import ActionCard
from .clamav import ONLINE_CONFIRMATION
from .case_export import export_case
from .case_import import import_archive, verify_archive
from .case_manager import CaseLoad, CaseManager, NewCaseDialog
from .case_removal import purge_case
from .adapters import CENSUS_LIMIT, analysis_command, query_census
from .core import BUILTIN_MODULES, discover, doctor
from .desktop_theme import ACCENT, ICONS, SPACE, STYLE, SUCCESS, VIOLET, WARNING
from .images import inspect_raw
from .inspection import inspect_file, inspect_open_file, investigation_mounts
from .module_scaffold import create_module_draft
from .evidence_panel import EvidencePanel
from .desktop_integration import (checked_descriptor, dispatch_viewing_copy, graphical_user,
                                  prepare_view, reveal_in_file_manager)
from . import dev_mode
from .entity import data_directory, legacy_base
from .entity_panel import EntityPanel
from .history import PAGE_SIZE, case_events
from .reporting import case_pdf_reports, case_report, pdf_analysis_kind
from .system_panel import SystemPanel
from .system_info import read_zones
from .shutdown_state import ShutdownBlocked, capture_startup_state, check_shutdown_state
from .quick_actions import acquisition_command, legacy_mount_command, storage_command, offline_update_command, update_workflow_command
from .external_terminal import TERMINALS, detected_terminal, launch_terminal, launch_tracked

ANALYSIS_LABELS = {
    "archives": ("Archives", "Archives"),
    "audio": ("Fichiers audio", "Audio files"),
    "bigfiles": ("Fichiers volumineux", "Large files"),
    "clamav": ("Scan antivirus", "Antivirus scan"),
    "census": ("Recensement de fichiers", "File inventory"),
    "crypto": ("Fichiers chiffrés", "Encrypted files"),
    "entropy": ("Analyse de l’entropie", "Entropy analysis"),
    "images": ("Images et métadonnées", "Images and metadata"),
    "office": ("Documents bureautiques", "Office documents"),
    "videos": ("Fichiers vidéo", "Video files"),
}


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


class QuickActionArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setObjectName("quickActionArea")
        self.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, SPACE, SPACE)
        self.sections = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.sections.setSpacing(2 * SPACE)
        layout.addLayout(self.sections)
        layout.addStretch()
        self.setWidget(content)


class ReportDateItem(QTableWidgetItem):
    def __lt__(self, other):
        return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)


class Workspace(QMainWindow):
    def __init__(self, settings, database_path):
        super().__init__()
        self.settings = settings
        self.database_path = database_path
        self.closing_checks = False
        self.startup_state_error = None
        try:
            if not dev_mode.active() and not os.environ.get("VIGIL_SESSION_SNAPSHOT"):
                capture_startup_state(database_path)
        except (OSError, ValueError) as error:
            self.startup_state_error = error
        self.active_case_id = ""
        self.skip_viewing_copy_confirmation = False
        self.settings.remove("active_case_id")
        self.language = "en" if settings.value("language") == "en" else "fr"
        self.translator = QTranslator(self)
        self.localized = []
        self.busy = None
        self.external_runs = []
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
        header.setContentsMargins(12, 6, 12, 6)
        header.setSpacing(10)
        logo = QLabel()
        logo_path = Path(__file__).resolve().parents[1] / "data/icons/vigil.svg"
        if not logo_path.is_file():
            logo_path = Path(sys.prefix) / "share/vigil/vigil.svg"
        icon = QIcon(str(logo_path))
        self.setWindowIcon(icon)
        logo.setPixmap(icon.pixmap(32, 32))
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
        self.sidebar_compact = False
        self.navigation.setFixedWidth(208)
        self.navigation.setIconSize(QSize(18, 18))
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_button = QPushButton(self.action_icon("list", ACCENT), "")
        self.bind(sidebar_button.setAccessibleName, "Replier ou déplier la navigation", "Toggle navigation width")
        self.bind(sidebar_button.setToolTip, "Replier ou déplier la navigation", "Toggle navigation width")
        sidebar_button.clicked.connect(self.toggle_navigation_width)
        header.insertWidget(0, sidebar_button)
        self.bind(self.navigation.setAccessibleName, "Navigation", "Navigation")
        self.navigation.currentItemChanged.connect(self.open_page)
        body.addWidget(self.navigation)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.navigation_group("ESPACE DE TRAVAIL", "WORKSPACE")
        home = self.page("Tableau de bord", "Dashboard", scroll=True)
        self.dashboard_case = QLabel()
        self.dashboard_case.setTextFormat(Qt.TextFormat.PlainText)
        home.addWidget(self.dashboard_case)
        metrics = QHBoxLayout()
        home.addLayout(metrics)
        self.dashboard_cards = []
        for icon_name, color in (("list", ACCENT), ("circle-dot", VIOLET), ("shield", SUCCESS)):
            card = QFrame()
            card.setObjectName("quickActionSection")
            card.setMaximumWidth(300)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 9, 12, 9)
            icon_label = QLabel()
            icon_label.setPixmap(self.action_icon(icon_name, color).pixmap(18, 18))
            icon_label.setStyleSheet("background: transparent;")
            card_layout.addWidget(icon_label)
            column = QVBoxLayout()
            column.setSpacing(2)
            title = QLabel()
            value = QLabel()
            for label in (title, value):
                label.setTextFormat(Qt.TextFormat.PlainText)
                column.addWidget(label)
            title.setStyleSheet("background: transparent; color: #BAC9D7;")
            value.setStyleSheet(f"background: transparent; color: {color}; font-size: 19px; font-weight: 700;")
            card_layout.addLayout(column, 1)
            metrics.addWidget(card, 1)
            self.dashboard_cards.append((title, value))
        metrics.addStretch()
        dashboard_body = QHBoxLayout()
        dashboard_body.setSpacing(14)
        home.addLayout(dashboard_body, 1)
        self.hotplug_status = QLabel()
        self.hotplug_status.setWordWrap(True)
        hotplug_column = QVBoxLayout()
        dashboard_body.addLayout(hotplug_column, 3)
        self.system_panel = SystemPanel(self.tr_pair, self.action_icon)
        hotplug_column.addWidget(self.system_panel, 1)
        dashboard_side = QVBoxLayout()
        dashboard_body.addLayout(dashboard_side, 2)
        recent = QLabel()
        recent.setObjectName("quickActionTitle")
        self.bind(recent.setText, "Activité récente de l’affaire", "Recent case activity")
        dashboard_side.addWidget(recent)
        self.dashboard_events = QListWidget()
        dashboard_side.addWidget(self.dashboard_events, 1)

        self.case_picker = None
        self.cases = QListWidget(self)
        self.cases.hide()

        self.navigation_group("INVESTIGATION", "INVESTIGATION")
        case_workspace = self.page("Affaire en cours", "Current case", heading=False)
        case_toolbar = QScrollArea()
        case_toolbar.setFrameShape(QFrame.Shape.NoFrame)
        case_toolbar.setWidgetResizable(True)
        case_toolbar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        toolbar_content = QWidget()
        case_header = QHBoxLayout(toolbar_content)
        case_header.setContentsMargins(0, 0, 0, 0)
        case_toolbar.setWidget(toolbar_content)
        case_toolbar.setFixedHeight(60)
        case_workspace.addWidget(case_toolbar)
        self.case_title = QLabel()
        self.case_title.setObjectName("pageTitle")
        self.case_title.setTextFormat(Qt.TextFormat.PlainText)
        self.case_title.setWordWrap(True)
        case_header.addWidget(self.case_title, 1)
        self.button(case_header, "Choisir l’affaire", "Choose case", self.choose_case)
        self.case_folder_button = self.button(case_header, "Ouvrir le dossier de l’affaire", "Open case folder",
                                              self.open_case_folder)
        self.case_folder_button.hide()
        self.button(case_header, "Monter périphérique/image", "Mount device/image",
                    self.request_mount, primary=True)
        self.button(case_header, "Démonter périphérique/image", "Unmount device/image",
                    self.request_unmount)
        case_toolbar.setFixedHeight(case_header.sizeHint().height() + 16)
        self.investigation_mount = QLabel()
        self.investigation_mount.setTextFormat(Qt.TextFormat.PlainText)
        self.investigation_mount.setWordWrap(True)
        case_workspace.addWidget(self.investigation_mount)
        self.case_workspace_page = case_workspace.parentWidget()
        self.case_navigation, self.case_pages = self.workspace_tabs(case_workspace, "Vues de l’affaire", "Case views")

        explorer = self.case_view("Explorateur", "Evidence explorer")
        self.explorer_case_id = None
        self.preview_request = None
        self.preview_generation = 0
        self.preview_jobs = {}
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.start_queued_preview)
        self.explorer = EvidencePanel(self.tr_pair, self.preview_evidence, self.process_explorer_selection,
                                      self.action_icon, lambda: bool(self.active_case_id),
                                      passive_preview=self.queue_explorer_preview,
                                      external_action=self.external_explorer_action)
        explorer.addWidget(self.explorer)
        self.explorer_page = explorer.parentWidget()

        evidence = self.case_view("Preuves", "Evidence")
        self.evidence = QTreeWidget()
        self.evidence.setColumnCount(3)
        self.evidence.setUniformRowHeights(True)
        self.evidence_case_id = None
        self.bind(lambda name: self.evidence.setHeaderLabels([name, "SHA-256", self.tr_pair("Copie locale", "Local copy")]),
                  "Fichier", "File")
        self.evidence.setColumnWidth(0, 390)
        self.evidence.itemActivated.connect(self.queue_evidence_preview)
        evidence.addWidget(self.evidence)
        self.evidence_empty = QLabel()
        self.bind(self.evidence_empty.setText, "Aucune preuve enregistrée.", "No registered evidence.")
        evidence.addWidget(self.evidence_empty)
        evidence_actions = QHBoxLayout()
        evidence.addLayout(evidence_actions)
        self.button(evidence_actions, "Ajouter un fichier à l’affaire", "Add a file to the case",
                    self.add_file, primary=True)
        self.button(evidence_actions, "Ouvrir le fichier", "Open file", self.open_evidence_preview)
        self.button(evidence_actions, "Ouvrir le dossier", "Open folder", self.open_evidence_folder)
        self.button(evidence_actions, "Supprimer la preuve", "Delete evidence", self.delete_selected_evidence)
        self.button(evidence_actions, "Inspecter une image RAW", "Inspect a RAW image", self.inspect_image)
        evidence_actions.addStretch()


        modules = self.case_view("Analyses", "Analyses")
        self.analysis_hint = QLabel()
        self.analysis_hint.setWordWrap(True)
        self.bind(
            self.analysis_hint.setText,
            "Sélectionnez un module pour analyser les supports montés en lecture seule dans /investigation.",
            "Select a module to analyse read-only mounts under /investigation.",
        )
        modules.addWidget(self.analysis_hint)
        self.modules = QListWidget()
        modules.addWidget(self.modules)
        self.modules.itemActivated.connect(lambda _: self.run_selected_analysis())
        module_actions = QHBoxLayout()
        modules.addLayout(module_actions)
        self.button(module_actions, "Lancer l’analyse", "Run analysis", self.run_selected_analysis, primary=True)
        self.button(module_actions, "Ouvrir les résultats", "Open results", self.open_analysis_results)
        self.button(module_actions, "Consulter un index de recensement",
                    "Query a census index", self.query_index, primary=True)
        module_actions.addStretch()
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
        reports = self.case_view("Rapports PDF", "PDF reports")
        self.pdf_reports_page = reports.parentWidget()
        self.pdf_reports = QTableWidget(0, 3)
        self.pdf_reports.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pdf_reports.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pdf_reports.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pdf_reports.verticalHeader().hide()
        self.pdf_reports.horizontalHeader().setStretchLastSection(True)
        self.pdf_reports.setColumnWidth(0, 175)
        self.pdf_reports.setColumnWidth(1, 180)
        self.bind(lambda _: self.pdf_reports.setHorizontalHeaderLabels([
            self.tr_pair("Date", "Date"), self.tr_pair("Analyse", "Analysis"),
            self.tr_pair("Nom du rapport", "Report name"),
        ]), "", "")
        self.pdf_reports.horizontalHeader().setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        self.pdf_reports.setSortingEnabled(True)
        reports.addWidget(self.pdf_reports)
        self.button(reports, "Actualiser la liste", "Refresh list", self.refresh_pdf_reports)
        self.button(reports, "Ouvrir le dossier du rapport", "Open report folder",
                    self.open_pdf_folder, primary=True)

        export = self.case_view("Exporter l’affaire", "Export case")
        export_intro = QLabel()
        export_intro.setWordWrap(True)
        self.bind(export_intro.setText,
                  "L’archive complète contient les preuves copiées, les résultats, le journal et les empreintes SHA-256.",
                  "The full archive contains saved evidence, results, audit history and SHA-256 checksums.")
        export.addWidget(export_intro)
        self.button(export, "Créer l’archive complète", "Create full archive",
                    self.export_full_case, primary=True)
        self.button(export, "Exporter l’audit de l’affaire", "Export case audit", self.export_case_report)
        export.addStretch()

        quick_actions = self.page("Actions rapides", "Quick actions")
        action_area = QuickActionArea()
        quick_actions.addWidget(action_area, 1)
        sections = action_area.sections
        antivirus = self.quick_action_section(sections, "Antivirus", "Antivirus", "shield", ACCENT)
        self.quick_action_card(
            antivirus, "Scan antivirus", "Antivirus scan",
            "Monte le support, lance ClamAV et enregistre le rapport PDF.",
            "Mount the device, run ClamAV and save the PDF report.",
            "shield", self.quick_scan, color=ACCENT,
        )
        self.quick_action_card(
            antivirus, "Mettre à jour l’antivirus", "Update antivirus",
            "Met à jour le moteur et les signatures ClamAV.",
            "Update the ClamAV engine and signatures.",
            "upload", self.quick_update, color="#82AAFF",
        )
        self.quick_action_card(
            antivirus, "Mettre à jour la base virale depuis un périphérique USB", "Update signatures from USB",
            "Vérifie et importe les signatures officielles sans connexion.",
            "Verify and import official signatures offline.",
            "plug", self.quick_update_usb, color=SUCCESS,
        )
        self.quick_action_card(
            antivirus, "Rapports antivirus", "Antivirus reports",
            "Retrouve les PDF consolidés des scans rapides.",
            "Find consolidated PDFs from quick scans.",
            "folder", self.show_antivirus_reports, color=VIOLET,
        )
        antivirus.addStretch()
        storage_actions = self.quick_action_section(sections, "Stockage", "Storage", "folder", SUCCESS)
        self.quick_action_card(
            storage_actions, "Monter un stockage", "Mount storage",
            "Sélectionne un support de travail et le monte en lecture-écriture sous /stockage.",
            "Select a work drive and mount it read-write under /stockage.",
            "hard-drive", lambda: self.quick_storage("mount"), color=SUCCESS,
        )
        self.quick_action_card(
            storage_actions, "Démonter le stockage", "Unmount storage",
            "Démonte les supports de travail sous /stockage.",
            "Unmount work drives under /stockage.",
            "hard-drive", lambda: self.quick_storage("unmount"), color=WARNING,
        )
        storage_actions.addStretch()
        acquisition = self.quick_action_section(sections, "Acquisition", "Acquisition", "hard-drive", VIOLET)
        self.quick_action_card(
            acquisition, "Cloner un disque", "Clone a disk",
            "Copie bit à bit sur un disque USB cible et vérifie son SHA-256.",
            "Copy bit for bit to a USB disk and verify its SHA-256.",
            "hard-drive", lambda: self.start_quick_action(lambda: acquisition_command("clone", language=self.language), "clone"),
            color=WARNING,
        )
        self.quick_action_card(
            acquisition, "Créer une image RAW", "Create a RAW image",
            "Enregistre une image vérifiée en local ou sur un stockage USB temporaire.",
            "Save a verified image locally or on temporarily mounted USB storage.",
            "hard-drive", self.quick_raw_image, color=VIOLET,
        )
        acquisition.addStretch()
        sections.addStretch()

        self.navigation_group("SYSTÈME", "SYSTEM")
        configuration = self.page("Configuration", "Configuration")
        self.configuration_tabs, self.configuration_pages = self.workspace_tabs(
            configuration, "Onglets de configuration", "Configuration tabs"
        )
        self.configuration_tabs.currentChanged.connect(self.configuration_pages.setCurrentIndex)
        entity_page = self.workspace_tab(self.configuration_tabs, self.configuration_pages, "Entité", "Entity")
        self.entity_panel = EntityPanel(data_directory(), self.tr_pair)
        entity_page.addWidget(self.entity_panel)
        system = self.workspace_tab(self.configuration_tabs, self.configuration_pages, "Système", "System")
        self.section_heading(system, "Terminal par défaut", "Default terminal")
        self.terminal_status = QLabel()
        self.terminal_status.setTextFormat(Qt.TextFormat.PlainText)
        system.addWidget(self.terminal_status)
        self.button_for_terminal = self.button(system, "Choisir le terminal…", "Choose terminal…",
                                               self.choose_terminal)
        self.section_heading(system, "Session et environnement graphique", "Session and graphical environment")
        self.session_status = QLabel()
        self.session_status.setTextFormat(Qt.TextFormat.PlainText)
        system.addWidget(self.session_status)
        self.section_heading(system, "Protections système", "System protections")
        system.addWidget(self.hotplug_status)
        self.section_heading(system, "Diagnostic des outils et dépendances", "Tool and dependency diagnostics")
        self.tools_filter = QComboBox()
        self.tools_filter.addItems(["", "", ""])
        self.bind(lambda label: self.tools_filter.setItemText(0, label), "Tous les outils", "All tools")
        self.bind(lambda label: self.tools_filter.setItemText(1, label), "Outils manquants", "Missing tools")
        self.bind(lambda label: self.tools_filter.setItemText(2, label), "Outils disponibles", "Available tools")
        self.tools_filter.currentIndexChanged.connect(self.filter_tools)
        system.addWidget(self.tools_filter)
        self.diagnostics = self.data_table(3)
        self.bind(lambda _: self.diagnostics.setHorizontalHeaderLabels([
            self.tr_pair("Outil", "Tool"), self.tr_pair("État", "Status"), self.tr_pair("Chemin", "Path")
        ]), "", "")
        system.addWidget(self.diagnostics, 1)

        catalogue = self.workspace_tab(self.configuration_tabs, self.configuration_pages,
                                       "Catalogue de modules", "Module catalogue")
        catalogue_actions = QHBoxLayout()
        catalogue.addLayout(catalogue_actions)
        self.catalogue_filter = QLineEdit()
        self.catalogue_filter.addAction(self.action_icon("search", ACCENT), QLineEdit.ActionPosition.LeadingPosition)
        self.bind(self.catalogue_filter.setPlaceholderText, "Rechercher un module", "Search modules")
        catalogue_actions.addWidget(self.catalogue_filter, 1)
        self.catalogue_availability = QComboBox()
        self.catalogue_availability.addItems(["", ""])
        self.bind(lambda text: self.catalogue_availability.setItemText(0, text), "Tous", "All")
        self.bind(lambda text: self.catalogue_availability.setItemText(1, text), "Disponibles", "Available")
        catalogue_actions.addWidget(self.catalogue_availability)
        self.button(catalogue_actions, "Créer un module", "Create a module", self.new_module, primary=True)
        module_split = QSplitter()
        catalogue.addWidget(module_split, 1)
        self.catalogue = self.data_table(3)
        self.bind(lambda _: self.catalogue.setHorizontalHeaderLabels([
            self.tr_pair("Module", "Module"), "Version", self.tr_pair("État", "Status")
        ]), "", "")
        self.catalogue.setColumnWidth(0, 200)
        self.catalogue.currentCellChanged.connect(self.show_module_details)
        self.catalogue_filter.textChanged.connect(self.filter_catalogue)
        self.catalogue_availability.currentIndexChanged.connect(self.filter_catalogue)
        module_split.addWidget(self.catalogue)
        self.module_inspector = QPlainTextEdit()
        self.module_inspector.setReadOnly(True)
        module_split.addWidget(self.module_inspector)
        module_split.setSizes([560, 360])

        self.footer_protection = QLabel()
        self.footer_zones = QLabel()
        self.statusBar().addPermanentWidget(self.footer_protection)
        self.statusBar().addPermanentWidget(self.footer_zones)
        self.refresh_operators()
        self.translate()
        self.refresh_cases()
        self.navigation.setCurrentRow(1)
        self.case_navigation.currentChanged.connect(self.open_case_view)
        self.case_navigation.setCurrentIndex(0)
        self.mount_timer = QTimer(self)
        self.mount_timer.timeout.connect(self.refresh_case_mount)
        self.mount_timer.timeout.connect(self.refresh_hotplug_status)
        self.mount_timer.timeout.connect(self.refresh_external_runs)
        self.mount_timer.start(2000)

    def tr_pair(self, french, english):
        return english if self.language == "en" else french

    def bind(self, setter, french, english):
        self.localized.append((setter, french, english))

    def toggle_navigation_width(self):
        self.sidebar_compact = not self.sidebar_compact
        self.navigation.setFixedWidth(56 if self.sidebar_compact else 208)
        for row in range(self.navigation.count()):
            item = self.navigation.item(row)
            heading = self.navigation.itemWidget(item)
            if heading is None:
                item.setText("" if self.sidebar_compact else item.toolTip())
            else:
                heading.setText("" if self.sidebar_compact else item.text())

    def navigation_group(self, french, english):
        item = QListWidgetItem(self.navigation)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        heading = QLabel()
        heading.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)
        heading.setStyleSheet("color: #57C7D2; padding-left: 8px; font-weight: 600;")
        self.navigation.setItemWidget(item, heading)

        def label(value):
            item.setText(value)
            heading.setAccessibleName(value)
            heading.setText("" if self.sidebar_compact else value)
            item.setSizeHint(QSize(0, heading.fontMetrics().height() + 24))

        self.bind(label, french, english)

    def open_page(self, item, _previous):
        if item is not None:
            index = item.data(Qt.ItemDataRole.UserRole)
            if index is not None:
                self.pages.setCurrentIndex(index)
                if (self.pages.currentWidget() is self.case_workspace_page
                        and self.case_pages.currentWidget() is self.history_page):
                    self.reset_history()

    def page(self, french, english, *, heading=True, scroll=False):
        widget = QWidget()
        widget.setProperty("workspacePage", True)
        item = QListWidgetItem(self.navigation)
        item.setData(Qt.ItemDataRole.UserRole, self.pages.addWidget(widget))
        item.setIcon(self.action_icon(ICONS[english], ACCENT))
        def page_label(label):
            item.setText("" if self.sidebar_compact else label)
            item.setToolTip(label)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, label)

        self.bind(page_label, french, english)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if heading:
            title = QLabel()
            title.setObjectName("pageTitle")
            self.bind(title.setText, french, english)
            layout.addWidget(title)
        if scroll:
            area = QScrollArea()
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setWidgetResizable(True)
            content = QWidget()
            inner = QVBoxLayout(content)
            inner.setContentsMargins(0, 0, SPACE, 0)
            area.setWidget(content)
            layout.addWidget(area, 1)
            return inner
        return layout

    def section_heading(self, layout, french, english):
        title = QLabel()
        title.setObjectName("quickActionTitle")
        self.bind(title.setText, french, english)
        layout.addWidget(title)

    def workspace_tabs(self, layout, french, english):
        navigation = QTabBar()
        navigation.setExpanding(False)
        navigation.setUsesScrollButtons(True)
        navigation.setIconSize(QSize(16, 16))
        navigation.setObjectName("caseNavigation")
        self.bind(navigation.setAccessibleName, french, english)
        layout.addWidget(navigation)
        pages = QStackedWidget()
        content = QScrollArea()
        content.setFrameShape(QFrame.Shape.NoFrame)
        content.setWidgetResizable(True)
        content.setWidget(pages)
        layout.addWidget(content, 1)
        return navigation, pages

    def workspace_tab(self, navigation, pages, french, english):
        widget = QWidget()
        pages.addWidget(widget)
        index = navigation.addTab(self.action_icon(ICONS[english], ACCENT), "")
        self.bind(lambda label: navigation.setTabText(index, label), french, english)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout

    def case_view(self, french, english):
        return self.workspace_tab(self.case_navigation, self.case_pages, french, english)

    def open_case_view(self, index):
        if index >= 0:
            self.case_pages.setCurrentIndex(index)
            if self.case_pages.currentWidget() is self.history_page:
                self.reset_history()
            if self.case_pages.currentWidget() is self.pdf_reports_page:
                self.refresh_pdf_reports()

    def quick_action_section(self, sections, french, english, icon_name, accent):
        section = QFrame()
        section.setObjectName("quickActionSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        heading.setSpacing(9)
        icon = QLabel()
        icon.setStyleSheet("background: transparent;")
        icon.setPixmap(self.action_icon(icon_name, accent).pixmap(20, 20))
        heading.addWidget(icon)
        title = QLabel()
        title.setObjectName("quickCategoryTitle")
        title.setStyleSheet(f"color: {accent};")
        self.bind(title.setText, french, english)
        heading.addWidget(title, 1)
        layout.addLayout(heading)
        actions = QVBoxLayout()
        actions.setSpacing(9)
        layout.addLayout(actions, 1)
        section.setMinimumWidth(272)
        section.setMaximumWidth(420)
        sections.addWidget(section, 1, Qt.AlignmentFlag.AlignTop)
        return actions

    def quick_action_card(self, column, french, english, description_fr, description_en, icon_name, action, *, color):
        card = ActionCard(self.action_icon(icon_name, color), color, action)
        self.bind(card.set_title, french, english)
        self.bind(card.description.setText, description_fr, description_en)
        self.buttons.append(card)
        column.addWidget(card)

    @staticmethod
    @lru_cache(maxsize=80)
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
        return button

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
        self.refresh_pdf_reports()
        self.system_panel.render()
        self.refresh_hotplug_status()
        self.explorer.retranslate()
        self.entity_panel.retranslate()
        self.refresh_case_mount()
        self.update_case_label()
        self.refresh_dashboard()

    def notify(self, french, english, details="", *, copy_text=""):
        message = QMessageBox(self.case_picker or self)
        message.setWindowTitle("Vigil")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(self.tr_pair(french, english))
        if details:
            message.setDetailedText(details)
        if copy_text:
            copy = message.addButton(self.tr_pair("Copier le SHA-256", "Copy SHA-256"),
                                     QMessageBox.ButtonRole.ActionRole)
            copy.clicked.connect(lambda: QApplication.clipboard().setText(copy_text))
            message.addButton(QMessageBox.StandardButton.Ok)
        message.exec()

    def fail(self, error):
        self.notify("L’opération a échoué.", "The operation failed.", str(error))

    def refresh_diagnostics(self):
        result = doctor()
        self.refresh_terminal_status()
        session = self.tr_pair("Session graphique", "Graphical session")
        desktop = self.tr_pair("Environnement de bureau", "Desktop environment")
        self.session_status.setText(
            f"{session} · {result['session']} · Qt {QApplication.platformName()}\n"
            f"{desktop} · {result['desktop'] or '—'}"
        )
        self.diagnostics.setRowCount(0)
        for name, path in result["tools"].items():
            self.add_table_row(self.diagnostics, [name, self.tr_pair("Disponible", "Available") if path
                                                  else self.tr_pair("Indisponible", "Unavailable"), path or "—"],
                               available=bool(path))
        self.filter_tools()
        self.modules.clear()
        self.catalogue.setRowCount(0)
        manifests, errors = discover(BUILTIN_MODULES)
        self.catalogue_manifests = manifests
        for module in manifests.values():
            names = ANALYSIS_LABELS.get(module.id.removeprefix("vigil."), (module.name, module.name))
            self.add_row(self.modules, f"{self.tr_pair(*names)}  ·  {module.entrypoint.rsplit('/', 1)[-1]}", module.id)
            ready = all(shutil.which(dep) for dep in module.dependencies)
            item = self.add_table_row(self.catalogue, [self.tr_pair(*names), module.version,
                                     self.tr_pair("Disponible", "Available") if ready else self.tr_pair("Outils manquants", "Missing tools")],
                                     available=ready)
            item.setData(Qt.ItemDataRole.UserRole, module.id)
            item.setIcon(self.action_icon("flask-conical", VIOLET))
        self.filter_catalogue()
        self.show_module_details(self.catalogue.currentRow())
        for path in errors:
            self.modules.addItem(self.tr_pair("Manifeste invalide", "Invalid manifest") + f"  ·  {path}")

    def refresh_cases(self, selected=None):
        requested = selected
        try:
            with storage.database(self.database_path) as connection:
                rows = list(connection.execute(
                    "SELECT id, name FROM cases WHERE name <> ? "
                    "AND id NOT IN (SELECT case_id FROM deleted_cases) ORDER BY created_at, id",
                    (storage.ANTIVIRUS_CASE_NAME,),
                ))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        if not any(case_id == self.active_case_id for case_id, _ in rows):
            self.active_case_id = ""
            self.skip_viewing_copy_confirmation = False
        selected = selected or self.active_case_id
        self.cases.blockSignals(True)
        self.cases.clear()
        for case_id, name in rows:
            self.add_row(self.cases, name, case_id)
            if case_id == selected:
                self.cases.setCurrentRow(self.cases.count() - 1)
        self.cases.blockSignals(False)
        self.refresh_evidence()
        if self.case_picker is not None:
            self.case_picker.active_id = self.active_case_id
            self.case_picker.reload(requested)

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

    def choose_case(self):
        state = self.database_path
        dialog = CaseManager(self, lambda: storage.case_manager_rows(state), self.new_case,
                             self.import_case, self.delete_selected_case, self.open_managed_case,
                             import_archive=self.import_case_archive)
        self.case_picker = dialog
        dialog.reload()
        try:
            dialog.exec()
        finally:
            self.case_picker = None
            dialog.deleteLater()

    def open_managed_case(self, case_id):
        item = next((self.cases.item(i) for i in range(self.cases.count())
                     if self.cases.item(i).data(Qt.ItemDataRole.UserRole) == case_id), None)
        if item is not None:
            self.case_clicked(item)

    def delete_selected_case(self, case_id):
        if not case_id:
            return
        if self.case_resources_in_use():
            return
        try:
            with storage.database(self.database_path) as connection:
                name = storage.require_active_case(connection, case_id)["name"]
                if name == storage.ANTIVIRUS_CASE_NAME:
                    raise ValueError("the antivirus case cannot be deleted")
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        operator = self.require_operator()
        if not operator:
            return
        parent = self.case_picker or self
        tr = self.tr_pair
        dialog = QMessageBox(parent)
        dialog.setWindowTitle(tr("Supprimer l’affaire", "Delete case"))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(tr(f"Que supprimer pour « {name} » ?", f"What should be deleted for “{name}”?"))
        remove = dialog.addButton(tr("Retirer de la liste", "Remove from list"), QMessageBox.ButtonRole.ActionRole)
        purge = dialog.addButton(tr("Supprimer intégralement", "Delete permanently"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        choice = dialog.clickedButton()
        if choice not in (remove, purge):
            return

        confirm = QMessageBox(parent)
        confirm.setWindowTitle(tr("Validation 1 sur 2", "Confirmation 1 of 2"))
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setTextFormat(Qt.TextFormat.PlainText)
        confirm.setText(tr(
            f"Supprimer définitivement les copies de preuves, résultats, rapports locaux et journal de « {name} » ? Cet effacement est irréversible.",
            f"Permanently delete saved evidence, results, local reports and audit history for “{name}”? This cannot be undone.",
        ) if choice == purge else tr(
            f"Retirer « {name} » de la liste en conservant ses données ?",
            f"Remove “{name}” from the list and retain its data?",
        ))
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        if choice == purge:
            typed, accepted = QInputDialog.getText(
                parent, tr("Validation 2 sur 2", "Confirmation 2 of 2"),
                tr("Saisissez le nom exact de l’affaire pour confirmer la suppression définitive.",
                   "Enter the exact case name to confirm permanent deletion."),
            )
            if not accepted:
                return
            if typed != name:
                self.notify("Le nom saisi ne correspond pas à l’affaire.", "The name does not match the case.")
                return
        elif QMessageBox.question(
            parent, tr("Validation 2 sur 2", "Confirmation 2 of 2"),
            tr("Confirmer le retrait de la liste ?", "Confirm removal from the list?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        if self.case_resources_in_use():
            return
        try:
            if any(read_zones().values()):
                self.notify("Démontez les volumes d’investigation et de stockage avant de supprimer l’affaire.",
                            "Unmount investigation and storage volumes before deleting the case.")
                return
            if choice == purge:
                leftovers = purge_case(self.database_path, case_id)
                if leftovers:
                    self.notify("L’affaire a été retirée. Des fichiers restent à supprimer.",
                                "The case was removed. Some files still need cleanup.",
                                "\n".join(str(path) for path in leftovers))
            else:
                with storage.database(self.database_path) as connection:
                    storage.delete_case(connection, case_id, operator)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        self.refresh_cases()
        self.reset_history()

    def case_resources_in_use(self):
        self.refresh_external_runs()
        if self.busy is not None or self.external_runs:
            self.notify("Attendez la fin des opérations Vigil avant de supprimer une affaire.",
                        "Wait for Vigil operations to finish before deleting a case.")
            return True
        return False

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
        if target_id != self.active_case_id:
            self.skip_viewing_copy_confirmation = False
        self.active_case_id = target_id
        self.save_session_context()
        self.refresh_evidence()
        self.reset_history()
        if self.case_picker is not None:
            self.case_picker.accept()

    def confirm_case_selection(self, current, target):
        dialog = QMessageBox(self.case_picker or self)
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
        title = self.tr_pair("Affaire en cours", "Current case")
        self.case_title.setText(f"{title} · {name}" if item else title)
        self.active_case.setText("·  " + self.active_case.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, 200
        ))
        self.active_case.setToolTip(name)

    def refresh_evidence(self, *_):
        self.update_case_label()
        self.refresh_pdf_reports()
        keep_explorer = self.explorer_case_id == self.active_case_id
        self.explorer_case_id = self.active_case_id
        self.refresh_dashboard()
        case = self.active_case_item()
        if case is None:
            self.update_evidence_tree([])
            self.explorer.set_files([], keep_state=False)
            self.refresh_explorer_mounts()
            return
        try:
            with storage.database(self.database_path) as connection:
                archived = storage.is_archive_case(connection, self.active_case_id)
                rows = list(connection.execute(
                    "SELECT id, path, sha256 FROM evidence WHERE case_id = ? ORDER BY path",
                    (case.data(Qt.ItemDataRole.UserRole),),
                ))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        copies = {}
        for evidence_id, _, _ in rows:
            try:
                copy = storage.evidence_copy_path(self.database_path, self.active_case_id, evidence_id)
                if not copy.is_symlink() and copy.is_file():
                    copies[evidence_id] = copy
            except (OSError, ValueError):
                continue
        result_folders = {}
        custody = None
        try:
            custody = storage.case_storage_directory(self.database_path, self.active_case_id)
            for folder, labels in (
                ("analyses", ("Résultats d’analyse", "Analysis results")),
                ("rapports", ("Rapports PDF", "PDF reports")),
                ("rapports-json", ("Rapports JSON", "JSON reports")),
            ):
                root = custody / folder
                if root.is_dir() and not root.is_symlink() and next(root.iterdir(), None) is not None:
                    result_folders[root] = labels
        except (OSError, ValueError):
            pass
        self.explorer.set_files(rows, copies=copies, keep_state=keep_explorer,
                                archived=archived, result_folders=result_folders)
        self.refresh_explorer_mounts()
        self.update_evidence_tree(rows, copies, custody=custody, archived=archived)

    def update_evidence_tree(self, rows, copies=None, *, custody=None, archived=False):
        copies = copies or {}
        self.case_folder_button.setVisible(bool(copies) or archived)
        expanded = set()
        if self.evidence_case_id == self.active_case_id:
            expanded = {item.text(0) for item in (
                self.evidence.topLevelItem(i) for i in range(self.evidence.topLevelItemCount())
            ) if item.isExpanded()}
        self.evidence_case_id = self.active_case_id
        self.evidence.clear()
        self.evidence_empty.setVisible(not rows)
        groups = {}
        for evidence_id, name, digest in rows:
            path = Path(name)
            copy = copies.get(evidence_id)
            relative = copy.relative_to(custody) if copy and custody else None
            group = str(custody / "preuves") if relative else self.tr_pair(
                "Preuve référencée — contenu indisponible", "Referenced evidence — content unavailable",
            )
            if group not in groups:
                groups[group] = QTreeWidgetItem(self.evidence, [group])
                groups[group].setExpanded(group in expanded)
            relative_copy = str(relative) if relative else "—"
            item = QTreeWidgetItem(groups[group], [path.name, digest, relative_copy])
            if copy:
                item.setToolTip(2, str(copy))
            item.setToolTip(0, name)
            item.setToolTip(1, digest)
            item.setData(0, Qt.ItemDataRole.UserRole, evidence_id)

    @staticmethod
    def data_table(columns):
        table = QTableWidget(0, columns)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def add_table_row(table, values, *, available=True):
        index = table.rowCount()
        table.insertRow(index)
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            table.setItem(index, column, item)
        first = table.item(index, 0)
        first.setData(Qt.ItemDataRole.UserRole + 1, available)
        return first

    def filter_tools(self, *_):
        for row in range(self.diagnostics.rowCount()):
            ready = self.diagnostics.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
            mode = self.tools_filter.currentIndex()
            self.diagnostics.setRowHidden(row, (mode == 1 and ready) or (mode == 2 and not ready))

    def filter_catalogue(self, *_):
        query = self.catalogue_filter.text().strip().casefold()
        for row in range(self.catalogue.rowCount()):
            item = self.catalogue.item(row, 0)
            module_id = item.data(Qt.ItemDataRole.UserRole) or ""
            ready = item.data(Qt.ItemDataRole.UserRole + 1)
            show = query in f"{item.text()} {module_id}".casefold()
            self.catalogue.setRowHidden(row, not show or (self.catalogue_availability.currentIndex() == 1 and not ready))

    def show_module_details(self, row, *_):
        item = self.catalogue.item(row, 0)
        tr = self.tr_pair
        if item is None:
            self.module_inspector.setPlainText(tr("Sélectionnez un module.", "Select a module."))
            return
        manifest = self.catalogue_manifests.get(item.data(Qt.ItemDataRole.UserRole))
        if manifest is None:
            return
        self.module_inspector.setPlainText("\n".join((
            item.text(), f"{manifest.id} · {manifest.version}", "",
            f"{tr('Catégorie', 'Category')} · {manifest.category}",
            f"{tr('Provenance', 'Source')} · Vigil (GPL v3)",
            f"API / manifeste · {manifest.api_version} / {manifest.schema_version}",
            f"{tr('Dépendances', 'Dependencies')} · {', '.join(manifest.dependencies) or '—'}",
            f"{tr('Capacités', 'Capabilities')} · {', '.join(manifest.capabilities) or '—'}",
            f"{tr('Entrée', 'Entrypoint')} · {manifest.entrypoint}",
        )))

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
        count = paths = None
        events = []
        if self.active_case_id:
            try:
                with storage.database(self.database_path) as connection:
                    count, paths = connection.execute(
                        "SELECT count(*), count(DISTINCT path) FROM evidence WHERE case_id = ?", (self.active_case_id,),
                    ).fetchone()
                    events = case_events(connection, self.active_case_id, limit=8)
            except (OSError, ValueError, sqlite3.Error):
                pass
        for (title, indicator), (label, value) in zip(self.dashboard_cards, (
            (self.tr_pair("Fichiers enregistrés", "Registered files"), paths),
            (self.tr_pair("Événements récents", "Recent events"), len(events) if count is not None else None),
            (self.tr_pair("Preuves", "Evidence"), count),
        )):
            title.setText(label)
            indicator.setText(str(value) if value is not None else "—")
        if not events:
            self.dashboard_events.addItem(self.tr_pair("Aucun événement pour cette affaire.", "No case events."))
        for event in events:
            self.dashboard_events.addItem(QListWidgetItem(self.action_icon("list", ACCENT),
                f"{event['timestamp']}  ·  {event['action']}  ·  {event['operator']}"))

    def queue_explorer_preview(self, *resource):
        self.preview_generation += 1
        if not resource:
            self.preview_request = None
            return
        self.preview_request = self.active_case_id, resource, self.preview_generation
        self.preview_timer.start(45)

    def start_queued_preview(self):
        if self.preview_request is None:
            return
        case_id, resource, generation = self.preview_request
        self.preview_request = None
        if self.active_case_id == case_id:
            self.preview_evidence(*resource, generation=generation)

    def external_explorer_action(self, action, resource):
        case_id = self.active_case_id
        if case_id and self.busy is None:
            # A modal dialog must not interrupt QTreeWidget's item activation.
            QTimer.singleShot(0, self, lambda: self.open_explorer_resource(case_id, action, resource))

    def open_explorer_resource(self, case_id, action, resource):
        if self.active_case_id != case_id or self.busy is not None:
            return
        name, digest, mount, directory = resource
        original = Path(name)
        operator = self.require_operator()
        if not operator:
            return
        if action != "copy" and not graphical_user():
            self.notify("Session graphique non privilégiée introuvable.",
                        "No non-privileged graphical session is available.")
            return

        if action == "folder" or (action == "file" and not self.skip_viewing_copy_confirmation):
            dialog = QMessageBox(self)
            remember = None
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            if action == "folder":
                dialog.setText(self.tr_pair("Ouvrir dans l’explorateur système ?",
                                            "Open in the system file manager?"))
                dialog.setInformativeText(self.tr_pair(
                    "Le gestionnaire de fichiers peut générer automatiquement des miniatures.",
                    "The file manager may generate thumbnails automatically.",
                ))
            else:
                dialog.setText(self.tr_pair("Ouvrir une copie de consultation ?",
                                            "Open a viewing copy?"))
                dialog.setInformativeText(self.tr_pair(
                    "Le fichier s’ouvre dans l’application par défaut, sans isolation de l’OS. "
                    "Vigil fournit une copie de consultation en lecture seule stricte. "
                    "Les modifications de cette copie ne peuvent pas altérer la preuve enregistrée.",
                    "The file opens in the default application without OS isolation. "
                    "Vigil provides a strictly read-only viewing copy. "
                    "Changes to this copy cannot alter the registered evidence.",
                ))
                remember = QCheckBox(self.tr_pair(
                    "Ne plus afficher ce message tant que cette affaire est ouverte",
                    "Do not show this message again while this case is open",
                ), dialog)
                dialog.setCheckBox(remember)
            dialog.setStandardButtons(QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Cancel)
            dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if dialog.exec() != QMessageBox.StandardButton.Open or self.active_case_id != case_id:
                return
            if remember is not None and remember.isChecked():
                self.skip_viewing_copy_confirmation = True

        def prepare():
            scope = storage.case_storage_directory(self.database_path, case_id) if mount is None else None
            result_file = scope is not None and digest is None and any(
                original.is_relative_to(scope / folder) for folder in ("analyses", "rapports", "rapports-json")
            )
            if mount is None and not directory and not result_file:
                source = storage.find_evidence_copy(self.database_path, case_id, original, digest)
                if source is None:
                    raise ValueError("Referenced content unavailable / Contenu référencé indisponible")
            else:
                source = original
            if action == "file":
                return prepare_view(self.database_path, source, original.name, mount=mount, scope=scope), None
            if action == "folder" and not directory:
                with checked_descriptor(source, mount=mount, scope=scope):
                    pass
            target = source.parent if action == "folder" and not directory else source
            with checked_descriptor(target, mount=mount, scope=scope,
                                    directory=directory or action == "folder"):
                return target, source if action == "folder" and not directory else None

        def record(result, *, location=None, error=None):
            if action == "copy":
                return
            try:
                with storage.database(self.database_path) as connection:
                    row = connection.execute(
                        "SELECT id FROM evidence WHERE case_id = ? AND path = ? AND sha256 = ?",
                        (case_id, name, digest),
                    ).fetchone()
                    storage.audit(connection, operator, case_id, "explorer.external.request", {
                        "action": action, "path": name, "evidence_id": row["id"] if row else None,
                        "resource": "directory" if directory else "file",
                        "requested_location": str(location) if location is not None else None,
                        "result": result, "error": str(error) if error else None,
                    })
            except (OSError, ValueError, sqlite3.Error) as diagnostic:
                self.fail(diagnostic)

        def failed(error):
            record("failed", error=error)
            self.fail(error)

        def launch(prepared):
            target, selected = prepared
            if action == "copy":
                QApplication.clipboard().setText(str(target))
                return
            if self.active_case_id != case_id:
                failed(ValueError(self.tr_pair("L’affaire active a changé.", "The active case changed.")))
                return
            if action == "file":
                try:
                    dispatch_viewing_copy(target)
                except (OSError, ValueError) as error:
                    failed(error)
                else:
                    record("dispatched", location=target)
                return
            accepted = (selected is not None and reveal_in_file_manager(selected)) or QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(target)))
            if accepted:
                record("os_accepted", location=target)
            else:
                failed(ValueError(self.tr_pair("Le système n’a pas accepté l’ouverture.",
                                                "The system did not accept the open request.")))

        self.run_task(prepare, launch, on_error=failed)

    def preview_evidence(self, name, digest, mount=None, *, evidence_id=None, generation=None):
        if self.busy is not None and generation is None:
            return
        case_id = self.active_case_id

        original = Path(name)
        result_folders = tuple(self.explorer.result_folders)

        def inspect():
            if mount is None and digest and case_id:
                if evidence_id is None:
                    local = storage.find_evidence_copy(self.database_path, case_id, original, digest)
                else:
                    copy = storage.evidence_copy_path(self.database_path, case_id, evidence_id)
                    local = copy if copy.exists() else None
                if local is not None:
                    snapshot = inspect_file(local, display_name=original.name)
                    snapshot["local_copy"] = str(local)
                    return snapshot
                with storage.database(self.database_path) as connection:
                    archived = storage.is_archive_case(connection, case_id)
                if archived or evidence_id is not None or original.is_relative_to("/investigation") or not original.is_file():
                    raise ValueError(self.tr_pair(
                        "Cette preuve n’a pas de copie locale. Remontez le support d’origine en lecture seule "
                        "et ajoutez de nouveau le fichier aux preuves.",
                        "This evidence has no local copy. Remount the original device read-only and add the file again.",
                    ))
            if mount is None and digest is None:
                root = next((folder for folder in result_folders if original.is_relative_to(folder)), None)
                with checked_descriptor(original, scope=root) as descriptor:
                    return inspect_open_file(descriptor, original.name)
            return inspect_file(original, mount=mount)

        def display(snapshot):
            if (self.active_case_id == case_id
                    and (generation is None or generation == self.preview_generation)
                    and (mount is None or self.explorer.mounts.get(mount[0]) == mount[1])):
                try:
                    self.explorer.show_preview(name, digest, snapshot)
                except (OSError, ValueError, OverflowError) as error:
                    logging.getLogger(__name__).exception("Could not display evidence preview")
                    self.fail(error)
                    return
                if evidence_id is not None:
                    self.case_navigation.setCurrentIndex(self.case_pages.indexOf(self.explorer_page))

        def preview_failed(error):
            if generation is None:
                self.fail(error)
            elif generation == self.preview_generation:
                for view in self.explorer.views:
                    view.clear()
                self.explorer.hint.setText(str(error))

        if generation is None:
            self.run_task(inspect, display, on_error=preview_failed)
        else:
            self.preview_jobs[generation] = (display, preview_failed)
            job = CaseLoad(generation, inspect)
            job.signals.completed.connect(self.complete_preview)
            QThreadPool.globalInstance().start(job)

    @Slot(int, object, object)
    def complete_preview(self, generation, snapshot, error):
        success, failure = self.preview_jobs.pop(generation)
        if error is not None:
            failure(error)
        else:
            success(snapshot)

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
            provenance = row.get("provenance")
            marker = self.tr_pair(" · Importé", " · Imported") if provenance else ""
            details = row["details"]
            if provenance:
                details += "\n\n" + self.tr_pair("Provenance", "Provenance") + "\n" + json.dumps(
                    provenance, ensure_ascii=False, indent=2,
                )
            self.add_row(self.history_rows,
                         f"{row['timestamp']}  ·  {row['operator']}  ·  {row['action']}{marker}", details)
            self.history_before = row["sequence"]
        self.more_history.setEnabled(len(rows) > PAGE_SIZE)

    def refresh_pdf_reports(self):
        self.pdf_reports.setRowCount(0)
        case_id = self.active_case_id
        if not case_id:
            return
        try:
            with storage.database(self.database_path) as connection:
                row = connection.execute("SELECT legacy_path FROM cases WHERE id = ?", (case_id,)).fetchone()
            reports = case_pdf_reports(self.database_path, case_id, row["legacy_path"] if row else None)
            self.pdf_reports.setSortingEnabled(False)
            self.pdf_reports.setRowCount(len(reports))
            labels = ANALYSIS_LABELS | {"usbhid": ("Triage USB", "USB triage")}
            for index, path in enumerate(reports):
                kind = pdf_analysis_kind(path)
                analysis = self.tr_pair(*labels.get(kind, ("Analyse non identifiée", "Unknown analysis")))
                timestamp = path.stat().st_mtime_ns
                date = datetime.fromtimestamp(timestamp / 1_000_000_000).strftime(
                    self.tr_pair("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S")
                )
                date_item = ReportDateItem(date)
                date_item.setData(Qt.ItemDataRole.UserRole, timestamp)
                name_item = QTableWidgetItem(path.name)
                name_item.setData(Qt.ItemDataRole.UserRole, str(path))
                name_item.setToolTip(str(path))
                for column, item in enumerate((date_item, QTableWidgetItem(analysis), name_item)):
                    self.pdf_reports.setItem(index, column, item)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
        finally:
            self.pdf_reports.setSortingEnabled(True)

    def open_pdf_folder(self):
        item = self.pdf_reports.item(self.pdf_reports.currentRow(), 2)
        if item is None:
            self.notify("Sélectionnez un rapport.", "Select a report.")
            return
        directory = Path(item.data(Qt.ItemDataRole.UserRole)).parent
        if not directory.is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            self.notify("Impossible d’ouvrir le dossier du rapport.",
                        "Could not open the report folder.", str(directory))

    def export_full_case(self):
        self.refresh_external_runs()
        if self.busy is not None or self.external_runs:
            self.notify("Attendez la fin des opérations Vigil avant l’export.",
                        "Wait for Vigil operations to finish before exporting.")
            return
        case_id = self.active_case_id
        if not case_id:
            self.notify("Choisissez d’abord une affaire.", "Choose a case first.")
            return
        operator = self.require_operator()
        if not operator:
            return
        destination = QFileDialog.getExistingDirectory(
            self, self.tr_pair("Destination de l’archive", "Archive destination"),
        )
        if not destination:
            return
        self.run_task(
            lambda: export_case(self.database_path, case_id, operator, Path(destination)),
            self.show_case_export,
        )

    def show_case_export(self, result):
        if result.missing:
            count = len(result.missing)
            self.notify(f"Archive créée avec {count} preuve(s) sans copie.",
                        f"Archive created with {count} missing evidence copy/copies.",
                        "\n".join((str(result.path), *result.missing)))
        else:
            self.notify("Archive et empreinte SHA-256 enregistrées.",
                        "Archive and SHA-256 checksum saved.", str(result.path))

    def export_case_report(self):
        case_id = self.active_case_id
        if not case_id:
            self.notify("Choisissez une affaire depuis Affaire en cours.",
                        "Choose a case from Current case.")
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

    def save_session_context(self):
        if path := os.environ.get("VIGIL_SESSION_CONTEXT"):
            from .session import write_state
            case = self.active_case_item()
            try:
                write_state(Path(path), {"operator": self.operator.currentText() if self.operator.currentData() else None,
                                         "case": case.text() if case is not None else None})
            except OSError:
                logging.getLogger(__name__).exception("Could not save session context")

    def save_operator(self, *_):
        self.save_session_context()
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

    def new_case(self):
        operator = self.require_operator()
        if not operator:
            return
        dialog = NewCaseDialog(self.case_picker or self, self.tr_pair, operator)
        try:
            while dialog.exec() == QDialog.DialogCode.Accepted:
                name = dialog.name.text().strip()
                reference = dialog.reference.text().strip()
                description = dialog.description.toPlainText().strip()
                if self.create_case(name, reference, description):
                    return
        finally:
            dialog.deleteLater()

    def create_case(self, name, reference="", description=""):
        name = name.strip()
        operator = self.require_operator()
        if not operator:
            return False
        if (not name or len(name) > 120 or not name.isprintable()
                or name in {".", ".."} or any(char in name for char in "/\\")
                or name.casefold() == storage.ANTIVIRUS_CASE_NAME.casefold()):
            self.notify("Saisissez un nom valide sans séparateur de chemin ni nom réservé.",
                        "Enter a valid name without path separators or reserved names.")
            return False
        if (len(reference) > 120 or (reference and not reference.isprintable())
                or len(description) > 4000
                or any(not char.isprintable() and char not in "\n\t" for char in description)):
            self.notify("Vérifiez la référence et la description (4 000 caractères maximum).",
                        "Check the reference and description (maximum 4,000 characters).")
            return False
        try:
            with storage.database(self.database_path) as connection:
                case_id = storage.create_case(connection, name, operator,
                                              reference=reference, description=description)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return False
        self.refresh_cases(case_id)
        return True

    def import_case_archive(self):
        if self.busy is not None:
            return
        operator = self.require_operator()
        if not operator:
            return
        source, _ = QFileDialog.getOpenFileName(
            self.case_picker or self, self.tr_pair("Archive Vigil 2.0", "Vigil 2.0 archive"),
            filter=self.tr_pair("Archives TAR.GZ (*.tar.gz *.tgz);;Tous les fichiers (*)",
                                "TAR.GZ archives (*.tar.gz *.tgz);;All files (*)"),
        )
        if not source:
            return
        path, state = Path(source), self.database_path

        def confirm(preview):
            tr = self.tr_pair
            dialog = QMessageBox(self.case_picker or self)
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            dialog.setWindowTitle(tr("Prévisualisation de l’import", "Import preview"))
            dialog.setText(preview.name)
            validation = tr("Valide, archive partielle", "Valid, partial archive") if preview.missing else tr("Valide, archive complète", "Valid, complete archive")
            lines = [
                validation, f"{tr('Affaire source', 'Source case')} · {preview.source_id}",
                f"{tr('Version du format', 'Format version')} · {preview.schema_version}",
                f"{tr('Date de l’export', 'Export date')} · {preview.exported_at}",
                f"{tr('Preuves / copies / manquantes', 'Evidence / copies / missing')} · "
                f"{preview.evidence_count} / {preview.evidence_count - preview.missing} / {preview.missing}",
                f"{tr('Fichiers de résultats / PDF archivés', 'Result files / archived PDFs')} · "
                f"{preview.results} / {preview.reports}",
                f"{tr('Projet Vigil 1.0 embarqué', 'Vigil 1.0 project included')} · "
                f"{tr('Oui', 'Yes') if preview.legacy else tr('Non', 'No')}",
                f"{tr('Taille décompressée', 'Expanded size')} · {preview.bytes:,} {tr('octets', 'bytes')}",
                tr("Somme externe vérifiée.", "External checksum verified.") if preview.sidecar_verified else
                tr("Somme externe absente. Manifeste interne vérifié.", "No external checksum. Internal manifest verified."),
            ]
            dialog.setInformativeText("\n".join(lines))
            dialog.setIcon(QMessageBox.Icon.Warning if preview.missing else QMessageBox.Icon.Information)
            accept = dialog.addButton(tr("Importer", "Import"), QMessageBox.ButtonRole.AcceptRole)
            cancel = dialog.addButton(tr("Annuler", "Cancel"), QMessageBox.ButtonRole.RejectRole)
            dialog.setDefaultButton(cancel)
            dialog.exec()
            if dialog.clickedButton() is accept:
                self.run_task(lambda: import_archive(state, path, operator, expected_sha256=preview.sha256),
                              self.show_archive_import)

        self.run_task(lambda: verify_archive(path), confirm)

    def show_archive_import(self, result):
        self.refresh_cases(result["case_id"])
        missing = result["missing"]
        if result["reused"]:
            french, english = "Cette archive a déjà été importée.", "This archive was already imported."
        elif missing:
            french, english = "Archive partielle restaurée.", "Partial archive restored."
        else:
            french, english = "Affaire restaurée.", "Case restored."
        self.notify(french, english, f"{result['case_id']}\nSHA-256 · {result['sha256']}\n"
                    + self.tr_pair(f"Preuves sans contenu · {missing}", f"Evidence without content · {missing}"))

    def import_case(self):
        operator = self.require_operator()
        if not operator:
            return
        directory = QFileDialog.getExistingDirectory(
            self.case_picker or self, self.tr_pair("Dossier du projet historique", "Legacy project folder"),
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
            self.notify("Import impossible ou projet incompatible.", "Import failed or project is incompatible.", str(error))
            return
        self.refresh_cases(case_id)
        self.notify("Projet importé.", "Project imported.", name)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr_pair("Choisir un fichier", "Choose a file"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return path

    def selected_evidence_item(self):
        item = self.evidence.currentItem()
        if item is None or not item.data(0, Qt.ItemDataRole.UserRole):
            self.notify("Sélectionnez un fichier dans les preuves.", "Select a file in Evidence.")
            return None
        return item

    def queue_evidence_preview(self, item, _column):
        evidence_id = item.data(0, Qt.ItemDataRole.UserRole)
        if evidence_id:
            # Let the item view finish handling activation before changing views.
            case_id, name, digest = self.active_case_id, item.toolTip(0), item.text(1)
            QTimer.singleShot(0, self, lambda: self.open_saved_preview(case_id, evidence_id, name, digest))

    def open_evidence_preview(self):
        item = self.selected_evidence_item()
        if item is not None:
            self.open_saved_preview(self.active_case_id, item.data(0, Qt.ItemDataRole.UserRole),
                                    item.toolTip(0), item.text(1))

    def open_saved_preview(self, case_id, evidence_id, name, digest):
        if case_id and case_id == self.active_case_id:
            self.preview_evidence(name, digest, evidence_id=evidence_id)

    def open_case_folder(self):
        if not self.active_case_id:
            return
        try:
            directory = storage.case_storage_directory(self.database_path, self.active_case_id)
            if directory.is_dir() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
                return
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        self.notify("Impossible d’ouvrir le dossier de l’affaire.", "Could not open the case folder.")

    def open_evidence_folder(self):
        item = self.selected_evidence_item()
        if item is None:
            return
        try:
            copy = storage.evidence_copy_path(
                self.database_path, self.active_case_id, item.data(0, Qt.ItemDataRole.UserRole),
            )
            if not copy.is_file() or copy.is_symlink():
                self.notify("Cette preuve n’a pas de copie locale.", "This evidence has no local copy.")
                return
            if QDesktopServices.openUrl(QUrl.fromLocalFile(str(copy.parent))):
                return
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        self.notify("Impossible d’ouvrir le dossier de la preuve.", "Could not open the evidence folder.")

    def delete_selected_evidence(self):
        item = self.evidence.currentItem()
        case_id = self.active_case_id
        evidence_id = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if not case_id or not evidence_id:
            self.notify("Sélectionnez une preuve.", "Select evidence first.")
            return
        operator = self.require_operator()
        if not operator:
            return
        dialog = QMessageBox(self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(self.tr_pair(
            "Supprimer cette preuve et sa copie locale ? Le fichier original sera conservé.",
            "Delete this evidence and its local copy? The original file will be retained.",
        ))
        dialog.setInformativeText(item.toolTip(0))
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        if dialog.exec() == QMessageBox.StandardButton.Yes:
            self.run_task(
                lambda: storage.delete_evidence(self.database_path, case_id, evidence_id, operator),
                lambda _: self.refresh_evidence(),
            )

    def add_file(self):
        case = self.active_case_item()
        if case is None:
            self.notify("Choisissez une affaire depuis Affaire en cours.", "Choose a case from Current case.")
            return
        operator = self.require_operator()
        if not operator or not (path := self.choose_file()):
            return
        case_id = case.data(Qt.ItemDataRole.UserRole)
        self.run_task(
            lambda: storage.register_file(self.database_path, case_id, Path(path), operator),
            lambda _: self.refresh_evidence(),
        )

    def process_explorer_selection(self, sources, register):
        if self.busy is not None or not self.active_case_id:
            return
        operator = self.require_operator()
        if not operator:
            return
        case_id = self.active_case_id

        def show(result):
            rows, errors = result
            if register and self.active_case_id == case_id:
                self.refresh_evidence()
            tr = self.tr_pair
            labels = {
                "added": tr("Ajouté", "Added"),
                "existing": tr("Déjà enregistré", "Already registered"),
                "calculated": tr("Empreinte calculée", "Fingerprint calculated"),
                "matches": tr("Conforme", "Matches"),
                "changed": tr("Différent", "Changed"),
            }
            details = []
            for path, digest, status, expected in rows:
                details.append(f"{labels[status]} · {path}\nSHA-256  {digest}")
                if status == "changed":
                    details.append(tr("Empreintes enregistrées", "Recorded fingerprints")
                                   + "  " + ", ".join(expected))
            details.extend(f"{tr('Erreur', 'Error')} · {path}\n{error}" for path, error in errors)
            self.notify(f"{len(rows)} fichier(s) traité(s), {len(errors)} erreur(s).",
                        f"{len(rows)} file(s) processed, {len(errors)} error(s).",
                        "\n\n".join(details),
                        copy_text="\n".join(digest for _, digest, _, _ in rows) if not register else "")

        self.run_task(
            lambda: storage.process_explorer_selection(
                self.database_path, case_id, operator, sources, register=register, use_saved_copy=True),
            show,
        )

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

    def run_selected_analysis(self):
        if self.busy is not None:
            return
        item = self.modules.currentItem()
        if item is None or not (module_id := item.data(Qt.ItemDataRole.UserRole)) or not self.active_case_id:
            self.notify("Choisissez une affaire et un module d’analyse.",
                        "Choose a case and an analysis module.")
            return
        operator = self.require_operator()
        if not operator:
            return
        try:
            mounts = read_zones()["/investigation"]
            if not mounts or any(mode != "ro" for _, _, _, mode in mounts):
                self.notify("Montez les supports d’investigation en lecture seule.",
                            "Mount the investigation volumes read-only.")
                return
            self.launch_external(analysis_command(self.database_path, self.active_case_id, operator, module_id),
                                 module_id, case_id=self.active_case_id, device_mode="analysis")
        except (OSError, sqlite3.Error, ValueError) as error:
            self.fail(error)

    def open_analysis_results(self):
        case_id = self.active_case_id
        if not case_id:
            self.notify("Choisissez d’abord une affaire.", "Choose a case first.")
            return
        try:
            root = storage.case_storage_directory(self.database_path, case_id) / "analyses"
            if root.is_dir() and root.resolve() == root.absolute() and QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(root))):
                return
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        self.notify("Aucun dossier de résultats accessible.", "No accessible results folder.")

    def query_index(self):
        case = self.active_case_item()
        if case is None:
            self.notify("Choisissez une affaire depuis Affaire en cours.", "Choose a case from Current case.")
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

    def run_task(self, operation, on_success, *, on_error=None):
        if self.case_picker is not None:
            self.case_picker.setEnabled(False)
        self.busy = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.busy)
        self.busy.started.connect(self.worker.run)
        self.worker.finished.connect(self.store_result)
        self.worker.finished.connect(self.busy.quit)
        self.busy.finished.connect(self.worker.deleteLater)
        self.busy.finished.connect(self.finish_task)
        self.on_success = on_success
        self.on_task_error = on_error or self.fail
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
        if self.case_picker is not None:
            self.case_picker.setEnabled(True)
        self.statusBar().clearMessage()
        for button in self.buttons:
            button.setEnabled(True)
        result, error = self.task_result
        self.refresh_dashboard()
        if error is not None:
            logging.getLogger(__name__).warning("Background operation failed: %s", error)
            self.on_task_error(error)
        else:
            self.on_success(result)

    def refresh_hotplug_status(self):
        pid = os.environ.get("VIGIL_SESSION_GUARD", str(os.getpid()))
        token = Path("/run/vigil-hotplug") / pid
        try:
            start = (Path("/proc") / pid / "stat").read_text().rsplit(")", 1)[1].split()[19]
            active = token.stat().st_uid == 0 and token.read_text().strip() == f"{os.getuid()} {start}"
        except (OSError, IndexError):
            active = False
        if dev_mode.active():
            text = self.tr_pair("Mode recette · opérations système désactivées",
                                "Development mode · system operations disabled")
        elif active:
            text = self.tr_pair("Protection des nouveaux disques active", "New disk protection active")
        elif Path("/usr/local/sbin/vigil-hotplug").is_file():
            text = self.tr_pair("Protection des nouveaux disques inactive · autorisation sudo requise",
                                "New disk protection inactive · sudo authorisation required")
        else:
            text = self.tr_pair("Protection des nouveaux disques non installée",
                                "New disk protection is not installed")
        self.hotplug_status.setText(text)
        self.footer_protection.setText(text)
        self.hotplug_status.setStyleSheet(
            f"color: {'#80D7A4' if active else '#EBC47A'}; font-weight: 600;"
        )

    def start_hotplug_protection(self):
        if dev_mode.active():
            return
        pending = json.loads(os.environ.get("VIGIL_SESSION_PENDING", "[]"))
        if pending:
            self.notify(
                "Une session antérieure doit être vérifiée. La protection automatique n’est pas réactivée.",
                "A previous session needs review. Automatic protection was not reactivated.",
                "\n".join(pending),
            )
            from .session import review_previous
            review_previous(self.database_path, pending, self.settings.value("external_terminal", ""))
            return
        helper = "/usr/local/sbin/vigil-hotplug"
        if not Path(helper).is_file():
            return
        try:
            script = legacy_base() / "scripts/post-install/activate-hotplug.sh"
            if not script.is_file():
                raise FileNotFoundError(script)
            launch_terminal(["/usr/bin/sh", str(script), os.environ.get("VIGIL_SESSION_GUARD", str(os.getpid()))],
                            self.settings.value("external_terminal", ""), detached=True)
        except (OSError, ValueError) as error:
            self.statusBar().showMessage(str(error), 10000)

    def refresh_explorer_mounts(self):
        if not self.active_case_id:
            self.explorer.set_mounts({})
            return
        try:
            mounts = investigation_mounts()
        except OSError:
            mounts = {}
        self.explorer.set_mounts(mounts)

    def refresh_case_mount(self):
        self.refresh_explorer_mounts()
        try:
            zones = read_zones()
        except OSError:
            zones = None
        entries = zones.get("/investigation") if zones is not None else None
        summary = []
        for zone in ("/investigation", "/stockage"):
            if zones is None or zone not in zones:
                state = self.tr_pair("inconnu", "unknown")
            elif not zones[zone]:
                state = self.tr_pair("non monté", "not mounted")
            else:
                state = "/".join(sorted({mode.upper() or "?" for _, _, _, mode in zones[zone]}))
                blocks = []
                for _, source, _, _ in zones[zone]:
                    try:
                        device = Path(source).resolve(strict=True)
                        if not device.is_block_device():
                            raise OSError("unverified block source")
                        flag = (Path("/sys/class/block") / device.name / "ro").read_text().strip()
                        blocks.append({"1": "RO", "0": "RW"}.get(flag, "?"))
                    except OSError:
                        blocks.append("?")
                state += " · " + self.tr_pair("bloc ", "block ") + "/".join(sorted(set(blocks)))
            summary.append(f"{zone}  {state}")
        self.footer_zones.setText("  |  ".join(summary))
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
        if self.busy is not None:
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
            (self.tr_pair("Monter le support et lancer automatiquement son recensement ?",
                          "Mount the device and start its census automatically?")
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
            self.launch_external(legacy_mount_command(
                operation, self.database_path, case_id, case.text(), operator,
            ), operation, case_id=case_id, device_mode="operation")
        except (OSError, ValueError) as error:
            self.fail(error)
            return
        self.statusBar().showMessage(self.tr_pair(
            "Script historique ouvert dans le terminal.",
            "Legacy script opened in the terminal.",
        ), 10000)

    def refresh_terminal_status(self):
        preferred = self.settings.value("external_terminal", "")
        preferred = preferred if preferred in TERMINALS else ""
        configured = preferred or self.tr_pair("Automatique", "Automatic")
        terminal = detected_terminal(preferred) or self.tr_pair("Aucun détecté", "None detected")
        state = self.tr_pair("Terminal détecté", "Detected terminal")
        self.terminal_status.setText(f"{configured} · {state} {terminal}")

    def choose_terminal(self):
        current = self.settings.value("external_terminal", "")
        choices = ["", *TERMINALS]
        auto = self.tr_pair("Automatique", "Automatic")
        labels = [auto, *TERMINALS]
        name, accepted = QInputDialog.getItem(
            self, self.tr_pair("Terminal externe", "External terminal"),
            self.tr_pair("Émulateur de terminal", "Terminal emulator"), labels,
            choices.index(current) if current in choices else 0, False,
        )
        if accepted:
            self.settings.setValue("external_terminal", choices[labels.index(name)])
            self.settings.sync()
            self.refresh_terminal_status()

    def launch_external(self, arguments, operation, *, case_id=None, device_mode=None):
        if dev_mode.active():
            raise ValueError(dev_mode.BLOCKED)
        if device_mode is not None:
            arguments = [sys.executable, "-m", "vigil.device_manager", device_mode, *arguments]
        context = {"operation": operation, "operator": self.operator.currentText(),
                   "case_id": case_id, "language": self.language}
        run = launch_tracked(arguments, self.database_path.parent / "terminal-runs", context,
                             self.settings.value("external_terminal", ""))
        self.external_runs.append(run)

    def refresh_external_runs(self):
        for run in tuple(self.external_runs):
            status = run.status()
            if status is None:
                continue
            self.external_runs.remove(run)
            text = self.tr_pair(f"Terminal · résultat : {status}", f"Terminal · result: {status}")
            if status == "unknown":
                text = self.tr_pair("Terminal · résultat inconnu", "Terminal · result unknown")
            self.statusBar().showMessage(text, 10000)

    def start_quick_action(self, command, operation="quick-action", *, case_id=None):
        try:
            if dev_mode.active():
                raise ValueError(dev_mode.BLOCKED)
            self.launch_external(command(), operation, case_id=case_id)
        except (OSError, ValueError) as error:
            self.fail(error)

    def show_antivirus_reports(self):
        from .qt_antivirus_reports import AntivirusReportDialog

        dialog = AntivirusReportDialog(self)
        dialog.exec()
        dialog.deleteLater()

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
            self.launch_external(legacy_mount_command(
                "scan", self.database_path, case_id, "Scan antivirus", operator, run_id=run_id,
            ), "antivirus", case_id=case_id, device_mode="operation")
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)

    def quick_update(self):
        response = QMessageBox.question(
            self, "Vigil",
            self.tr_pair(*ONLINE_CONFIRMATION),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.start_quick_action(lambda: update_workflow_command(self.database_path), "freshclam")

    def quick_update_usb(self):
        operator = self.require_operator()
        if not operator:
            return
        try:
            if dev_mode.active():
                raise ValueError(dev_mode.BLOCKED)
            self.launch_external(offline_update_command(self.database_path, operator),
                                 "clamav-usb", device_mode="operation")
        except (OSError, ValueError) as error:
            self.fail(error)

    def quick_raw_image(self):
        tr = self.tr_pair
        dialog = QMessageBox(self)
        dialog.setWindowTitle(tr("Destination de l’image RAW", "RAW image destination"))
        dialog.setText(tr("Où enregistrer l’image ?", "Where should the image be saved?"))
        local = dialog.addButton(tr("Dossier local", "Local folder"), QMessageBox.ButtonRole.ActionRole)
        external = dialog.addButton(tr("Périphérique USB", "USB device"), QMessageBox.ButtonRole.ActionRole)
        cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        choice = dialog.clickedButton()
        if choice == local:
            directory = QFileDialog.getExistingDirectory(
                self, tr("Choisir le dossier de destination", "Choose the destination folder"), str(Path.home()),
            )
            if directory:
                self.start_quick_action(lambda: acquisition_command("image", local_directory=Path(directory), language=self.language), "image-raw")
        elif choice == external:
            self.start_quick_action(lambda: acquisition_command("image", external=True, language=self.language), "image-raw")

    def quick_storage(self, operation):
        operator = self.require_operator()
        if not operator:
            return
        tr = self.tr_pair
        prompt = (tr("Ouvrir le montage en lecture-écriture d’un support de travail ?",
                     "Open the read-write mounting workflow for a work drive?")
                  if operation == "mount" else
                  tr("Démonter les supports de travail sous /stockage ?",
                     "Unmount work drives under /stockage?"))
        if QMessageBox.question(self, "Vigil", prompt,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        case = self.active_case_item()
        case_id = self.active_case_id
        try:
            arguments = storage_command(operation, self.database_path, case_id, case.text() if case else "", operator)
            self.launch_external(arguments, f"storage-{operation}", case_id=case_id or None, device_mode="operation")
        except (OSError, ValueError) as error:
            if operation == "mount":
                self.notify("Impossible d’ouvrir le montage du stockage.", "Could not open storage mounting.", str(error))
            else:
                self.notify("Impossible d’ouvrir le démontage du stockage.", "Could not open storage unmounting.", str(error))

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

    def closeEvent(self, event):
        if self.closing_checks:
            event.ignore()
            return
        self.refresh_external_runs()
        if self.busy is not None or self.external_runs:
            event.ignore()
            self.notify("Attendez la fin de l’opération avant de fermer Vigil.",
                        "Wait for the operation to finish before closing Vigil.")
            return
        if not self.confirm_close():
            event.ignore()
            return

        self.closing_checks = True
        progress = QProgressDialog(
            self.tr_pair("Vérification des montages Vigil…", "Checking Vigil mounts…"),
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
            if not dev_mode.active():
                check_shutdown_state()
            stage = "save"
            self.save_before_close()
            stage = "system"
            if not dev_mode.active():
                check_shutdown_state()
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
                self.notify("Impossible de vérifier les montages Vigil. Vigil reste ouvert.",
                            "Could not check Vigil mounts. Vigil will stay open.", str(error))
            return
        self.mount_timer.stop()
        self.system_panel.stop()
        super().closeEvent(event)


def main():
    if not dev_mode.active() and not os.environ.get("VIGIL_SESSION_ID"):
        from .session import supervise
        return supervise(sys.argv[1:])
    if os.geteuid() == 0:
        print("Lancez Vigil en tant qu’utilisateur ordinaire. / Run Vigil as a regular user.",
              file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    database_path = storage.default_database()
    preferences = database_path.parent / "preferences" / f"{os.getuid()}.ini"
    settings = QSettings(str(preferences), QSettings.Format.IniFormat)
    if not preferences.exists() and not dev_mode.active():
        legacy_settings = QSettings("Vigil", "Vigil2")
        settings.setValue("language", legacy_settings.value("language", "fr"))
    window = Workspace(settings, database_path)
    if window.startup_state_error is not None:
        window.notify("Impossible d’enregistrer l’état système initial.",
                      "Could not record the initial system state.", str(window.startup_state_error))
        window.system_panel.stop()
        return 1
    if not window.choose_session_operator():
        window.system_panel.stop()
        return 0
    window.showMaximized()
    window.start_hotplug_protection()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
