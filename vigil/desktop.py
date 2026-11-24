"""Bilingual Qt workspace for the local Vigil core."""
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QObject, QSettings, QThread, QTranslator, Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import storage
from .core import BUILTIN_MODULES, discover, doctor
from .images import inspect_raw

STYLE = """
QWidget { background: #101318; color: #DCE3EC; }
QLineEdit, QListWidget, QTabWidget::pane { background: #1A2029; border: 1px solid #35404E; }
QPushButton, QTabBar::tab { background: #242D38; padding: 7px 12px; }
QPushButton:focus, QLineEdit:focus { border: 1px solid #57C7D4; }
QTabBar::tab:selected, QListWidget::item:selected { background: #57C7D4; color: #101318; }
QPushButton:disabled { color: #81909F; }
"""


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
        self.language = settings.value("language", "fr")
        self.translator = QTranslator(self)
        self.localized = []
        self.busy = None
        self.worker = None
        self.buttons = []
        self.resize(900, 580)
        self.setWindowTitle("Vigil 2.0")
        self.setStyleSheet(STYLE)

        root = QWidget()
        layout = QVBoxLayout(root)
        header = QHBoxLayout()
        logo = QLabel()
        logo_path = Path(__file__).resolve().parents[1] / "data/icons/vigil.svg"
        if not logo_path.is_file():
            logo_path = Path(sys.prefix) / "share/vigil/vigil.svg"
        icon = QIcon(str(logo_path))
        self.setWindowIcon(icon)
        logo.setPixmap(icon.pixmap(40, 40))
        header.addWidget(logo)
        header.addWidget(QLabel("Vigil 2.0"))
        header.addStretch()
        self.operator = QLineEdit()
        self.bind(self.operator.setPlaceholderText, "Opérateur", "Operator")
        header.addWidget(self.operator)
        self.switch = QPushButton()
        self.switch.setCheckable(True)
        self.switch.setChecked(self.language == "en")
        self.switch.toggled.connect(self.change_language)
        header.addWidget(self.switch)
        layout.addLayout(header)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)

        cases = self.page("Affaires", "Cases")
        self.cases = QListWidget()
        cases.addWidget(self.cases)
        self.case_name = QLineEdit()
        self.bind(self.case_name.setPlaceholderText, "Nom de l’affaire", "Case name")
        cases.addWidget(self.case_name)
        self.button(cases, "Créer une affaire", "Create case", self.create_case)
        self.button(cases, "Importer un ancien projet", "Import legacy project", self.import_case)

        evidence = self.page("Preuves", "Evidence")
        self.case_label = QLabel()
        self.case_label.setTextFormat(Qt.TextFormat.PlainText)
        evidence.addWidget(self.case_label)
        self.evidence = QListWidget()
        evidence.addWidget(self.evidence)
        self.button(evidence, "Ajouter un fichier à l’affaire", "Add a file to the case", self.add_file)
        self.button(evidence, "Vérifier SHA-256", "Verify SHA-256", self.verify_file)
        self.button(evidence, "Inspecter une image RAW", "Inspect a RAW image", self.inspect_image)

        modules = self.page("Modules", "Modules")
        self.modules = QListWidget()
        modules.addWidget(self.modules)
        settings_page = self.page("Diagnostic", "Diagnostics")
        self.diagnostics = QListWidget()
        settings_page.addWidget(self.diagnostics)
        self.button(settings_page, "Actualiser", "Refresh", self.refresh_diagnostics)
        self.cases.currentItemChanged.connect(self.refresh_evidence)
        self.translate()
        self.refresh_cases()

    def tr_pair(self, french, english):
        return english if self.language == "en" else french

    def bind(self, setter, french, english):
        self.localized.append((setter, french, english))

    def page(self, french, english):
        widget = QWidget()
        index = self.tabs.addTab(widget, "")
        self.bind(lambda label: self.tabs.setTabText(index, label), french, english)
        return QVBoxLayout(widget)

    def button(self, layout, french, english, action):
        button = QPushButton()
        self.bind(button.setText, french, english)
        button.clicked.connect(action)
        self.buttons.append(button)
        layout.addWidget(button)

    def change_language(self, english):
        self.language = "en" if english else "fr"
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
        self.switch.setText(self.tr_pair("FR / EN · Français", "FR / EN · English"))
        self.statusBar().showMessage(
            self.tr_pair("Calcul en cours…", "Computing…") if self.busy else ""
        )
        self.switch.setAccessibleName(self.tr_pair("Langue de l’interface", "Interface language"))
        self.refresh_diagnostics()
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
        self.cases.clear()
        for case_id, name in rows:
            self.add_row(self.cases, name, case_id)
            if case_id == selected:
                self.cases.setCurrentRow(self.cases.count() - 1)
        if self.cases.currentRow() < 0 and rows:
            self.cases.setCurrentRow(0)

    @staticmethod
    def add_row(widget, label, identifier):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, identifier)
        widget.addItem(item)

    def update_case_label(self):
        item = self.cases.currentItem()
        name = item.text() if item else self.tr_pair("Aucune affaire", "No case selected")
        self.case_label.setText(self.tr_pair("Affaire active", "Active case") + f"  ·  {name}")

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

    def require_operator(self):
        operator = self.operator.text().strip()
        if not operator:
            self.notify("Saisissez le nom de l’opérateur.", "Enter the operator name.")
        return operator

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
