"""Bilingual Qt workspace for the local Vigil core."""
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QLibraryInfo, QRectF, QSize, QObject, QSettings, QThread, QTranslator, Qt, Signal, Slot
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QInputDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import storage
from .adapters import CENSUS_LIMIT, query_census
from .core import BUILTIN_MODULES, discover, doctor
from .images import inspect_raw
from .system_panel import SystemPanel

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
QTabWidget::pane {
    background: #1A2029; border: 1px solid #35404E; border-radius: 8px;
}
QWidget[workspacePage="true"] { background: #1A2029; }
QTabBar::tab {
    background: #1A2029; color: #C4D1E0; padding: 10px 18px;
    margin-right: 4px; border: 1px solid #35404E;
    border-top-left-radius: 7px; border-top-right-radius: 7px;
}
QTabBar::tab:hover { background: #283648; }
QTabBar::tab:selected {
    background: #253744; color: #EAFBFF;
    border-bottom: 3px solid #57C7D4; font-weight: 700;
}
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
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)

        home = self.page("Accueil", "Home")
        home_splitter = QSplitter(Qt.Orientation.Horizontal)
        home_splitter.setChildrenCollapsible(False)
        home.addWidget(home_splitter)
        self.system_panel = SystemPanel(self.tr_pair)
        home_splitter.addWidget(self.system_panel)
        home_context = QWidget()
        home_context.setProperty("workspacePage", True)
        home_details = QVBoxLayout(home_context)
        self.home_case = QLabel()
        self.home_case.setTextFormat(Qt.TextFormat.PlainText)
        self.home_case.setWordWrap(True)
        home_details.addWidget(self.home_case)
        self.button(home_details, "Ouvrir les affaires", "Open cases",
                    lambda: self.tabs.setCurrentIndex(1), primary=True)
        home_details.addStretch()
        home_splitter.addWidget(home_context)
        home_splitter.setSizes([460, 600])

        cases = self.page("Affaires", "Cases")
        self.case_search = QLineEdit()
        self.case_search.setClearButtonEnabled(True)
        self.bind(self.case_search.setPlaceholderText, "Rechercher une affaire", "Search cases")
        self.bind(self.case_search.setAccessibleName, "Rechercher une affaire", "Search cases")
        self.case_search.textChanged.connect(self.filter_cases)
        cases.addWidget(self.case_search)
        self.cases = QListWidget()
        cases.addWidget(self.cases)
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


        modules = self.page("Modules", "Modules")
        self.modules = QListWidget()
        modules.addWidget(self.modules)
        module_actions = QHBoxLayout()
        modules.addLayout(module_actions)
        self.button(module_actions, "Consulter un index de recensement",
                    "Query a census index", self.query_index, primary=True)
        module_actions.addStretch()
        settings_page = self.page("Diagnostic", "Diagnostics")
        self.diagnostics = QListWidget()
        settings_page.addWidget(self.diagnostics)
        diagnostic_actions = QHBoxLayout()
        settings_page.addLayout(diagnostic_actions)
        self.button(diagnostic_actions, "Actualiser", "Refresh", self.refresh_diagnostics)
        diagnostic_actions.addStretch()
        self.cases.currentItemChanged.connect(self.refresh_evidence)
        self.refresh_operators()
        self.translate()
        self.refresh_cases()

    def tr_pair(self, french, english):
        return english if self.language == "en" else french

    def bind(self, setter, french, english):
        self.localized.append((setter, french, english))

    def page(self, french, english):
        widget = QWidget()
        widget.setProperty("workspacePage", True)
        index = self.tabs.addTab(widget, "")
        self.bind(lambda label: self.tabs.setTabText(index, label), french, english)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
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
        current = self.cases.currentItem()
        if selected is None and current is not None:
            selected = current.data(Qt.ItemDataRole.UserRole)
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

    def update_case_label(self):
        item = self.cases.currentItem()
        name = item.text() if item else self.tr_pair("Aucune affaire", "No case selected")
        label = self.tr_pair("Affaire active", "Active case") + f"  ·  {name}"
        self.case_label.setText(label)
        self.home_case.setText(label)
        self.active_case.setText("·  " + self.active_case.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, 200
        ))
        self.active_case.setToolTip(name)

    def refresh_evidence(self, *_):
        self.update_case_label()
        self.evidence.clear()
        case = self.cases.currentItem()
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
        case = self.cases.currentItem()
        if case is None:
            self.notify("Sélectionnez une affaire.", "Select a case.")
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
        case = self.cases.currentItem()
        if case is None:
            self.notify("Sélectionnez une affaire.", "Select a case.")
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

    def closeEvent(self, event):
        if self.busy is not None:
            event.ignore()
            self.notify("Une opération est en cours.", "An operation is in progress.")
        else:
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
