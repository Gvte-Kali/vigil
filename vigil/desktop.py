"""Bilingual Qt workspace for the local Vigil core."""
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QLibraryInfo, QRectF, QSize, QObject, QSettings, QThread, QTranslator, Qt, Signal, Slot
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDockWidget, QFileDialog, QFrame, QInputDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import storage
from .adapters import CENSUS_LIMIT, query_census
from .core import BUILTIN_MODULES, discover, doctor
from .images import inspect_raw
from .system_panel import SystemPanel
from .terminal_panel import TerminalPanel
from .quick_actions import scan_command, tool, update_command

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
QListWidget#navigation::item:disabled { background: transparent; color: #91A1B3; }
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
        self.active_case_id = settings.value("active_case_id", "")
        self.language = "en" if settings.value("language") == "en" else "fr"
        self.translator = QTranslator(self)
        self.localized = []
        self.busy = None
        self.worker = None
        self.buttons = []
        self.resize(1130, 660)
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
        home = self.page("Accueil", "Home", heading=False)
        self.system_panel = SystemPanel(self.tr_pair)
        home.addWidget(self.system_panel)


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

        evidence = self.page("Preuves", "Evidence")
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


        self.navigation_group("INVESTIGATION", "INVESTIGATION")
        modules = self.page("Affaire en cours", "Current case")
        self.module_case = QLabel()
        self.module_case.setTextFormat(Qt.TextFormat.PlainText)
        modules.addWidget(self.module_case)
        self.modules = QListWidget()
        modules.addWidget(self.modules)
        module_actions = QHBoxLayout()
        modules.addLayout(module_actions)
        self.button(module_actions, "Consulter un index de recensement",
                    "Query a census index", self.query_index, primary=True)
        module_actions.addStretch()
        self.navigation_group("SYSTÈME", "SYSTEM")
        settings_page = self.page("Diagnostic", "Diagnostics")
        self.diagnostics = QListWidget()
        settings_page.addWidget(self.diagnostics)
        diagnostic_actions = QHBoxLayout()
        settings_page.addLayout(diagnostic_actions)
        self.button(diagnostic_actions, "Actualiser", "Refresh", self.refresh_diagnostics)
        diagnostic_actions.addStretch()
        self.navigation_group("ACTIONS RAPIDES", "QUICK ACTIONS")
        for french, english, action in (
            ("Scan antivirus", "Antivirus scan", self.quick_scan),
            ("Mettre à jour l’antivirus", "Update antivirus", self.quick_update),
            ("Ajouter un périphérique de stockage", "Add a storage device", self.quick_storage),
        ):
            page = self.page(french, english)
            self.button(page, french, english, action, primary=True)
            page.addStretch()

        self.terminal = TerminalPanel()
        self.terminal.completed.connect(self.quick_finished)
        self.terminal_dock = QDockWidget(self)
        self.bind(self.terminal_dock.setWindowTitle, "Terminal", "Terminal")
        self.terminal_dock.setWidget(self.terminal)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self.terminal_dock.hide()
        self.refresh_operators()
        self.translate()
        self.refresh_cases()
        self.navigation.setCurrentRow(1)

    def tr_pair(self, french, english):
        return english if self.language == "en" else french

    def bind(self, setter, french, english):
        self.localized.append((setter, french, english))

    def navigation_group(self, french, english):
        item = QListWidgetItem(self.navigation)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        button = QPushButton()
        button.setStyleSheet("text-align: left; background: #101318; border: none; color: #B9CAD9;")
        item.setSizeHint(button.sizeHint())
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

    def page(self, french, english, *, heading=True):
        widget = QWidget()
        widget.setProperty("workspacePage", True)
        item = QListWidgetItem(self.navigation)
        item.setData(Qt.ItemDataRole.UserRole, self.pages.addWidget(widget))
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
        self.update_case_label()

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
        manifests, errors = discover(BUILTIN_MODULES)
        for module in manifests.values():
            self.modules.addItem(f"{module.id}  ·  {module.version}")
        for path in errors:
            self.modules.addItem(self.tr_pair("Manifeste invalide", "Invalid manifest") + f"  ·  {path}")

    def refresh_cases(self, selected=None):
        try:
            with storage.database(self.database_path) as connection:
                rows = list(connection.execute("SELECT id, name FROM cases ORDER BY created_at, id"))
        except (OSError, ValueError, sqlite3.Error) as error:
            self.fail(error)
            return
        if not any(case_id == self.active_case_id for case_id, _ in rows):
            self.active_case_id = ""
            self.settings.remove("active_case_id")
        selected = selected or self.active_case_id
        self.cases.blockSignals(True)
        self.cases.clear()
        for case_id, name in rows:
            self.add_row(self.cases, name, case_id)
            if case_id == selected:
                self.cases.setCurrentRow(self.cases.count() - 1)
        if self.cases.currentRow() < 0 and rows:
            self.cases.setCurrentRow(0)
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
        self.settings.setValue("active_case_id", target_id)
        self.settings.sync()
        self.refresh_evidence()

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
        self.module_case.setText(label)
        self.active_case.setText("·  " + self.active_case.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, 200
        ))
        self.active_case.setToolTip(label)

    def refresh_evidence(self, *_):
        self.update_case_label()
        self.evidence.clear()
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
        for evidence_id, path, digest in rows:
            self.add_row(self.evidence, f"{path}  ·  {digest}", evidence_id)

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
        item = self.evidence.currentItem()
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
        if error:
            self.fail(error)
        else:
            self.on_success(result)

    def start_quick_action(self, command):
        if self.terminal.session is not None:
            self.terminal_dock.show()
            self.notify("Une commande est déjà en cours.", "A command is already running.")
            return
        try:
            self.terminal_dock.show()
            self.resizeDocks([self.terminal_dock], [270], Qt.Orientation.Vertical)
            self.terminal.start(command())
        except (OSError, ValueError) as error:
            self.fail(error)

    def quick_scan(self):
        file = self.choose_file()
        if file:
            self.start_quick_action(lambda: scan_command(Path(file), self.database_path))

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
        self.terminal.appendPlainText(self.tr_pair(f"Code de sortie : {code}", f"Exit code: {code}"))
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
            self.settings.setValue("active_case_id", self.active_case_id)
        self.save_operator()
        self.settings.setValue("language", self.language)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise ValueError("could not save workspace preferences")

    def closeEvent(self, event):
        if self.busy is not None or self.terminal.session is not None:
            event.ignore()
            self.notify("Attendez la fin de l’opération avant de fermer Vigil.",
                        "Wait for the operation to finish before closing Vigil.")
            return
        if not self.confirm_close():
            event.ignore()
            return
        try:
            self.save_before_close()
        except (OSError, ValueError, sqlite3.Error) as error:
            event.ignore()
            self.notify("La sauvegarde a échoué. Vigil reste ouvert.",
                        "Saving failed. Vigil will stay open.", str(error))
            return
        self.system_panel.stop()
        super().closeEvent(event)


def main():
    if os.geteuid() == 0:
        print("Lancez Vigil en tant qu’utilisateur ordinaire. / Run Vigil as a regular user.",
              file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    window = Workspace(QSettings("Vigil", "Vigil2"), storage.default_database())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
