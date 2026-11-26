"""Qt catalogue for the shared antivirus report records."""
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLineEdit, QMenu, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .antivirus_reports import antivirus_reports
from .desktop_integration import dispatch_viewing_copy


class SortedItem(QTableWidgetItem):
    def __lt__(self, other):
        return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)


class AntivirusReportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.workspace = parent
        t = parent.tr_pair
        self.setWindowTitle(t("Rapports antivirus", "Antivirus reports"))
        self.resize(840, 490)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("Rechercher un rapport", "Search reports"))
        self.search.textChanged.connect(self.filter_rows)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels((t("Date et heure", "Date and time"), t("Rapport PDF", "PDF report"),
                                              t("Résultat", "Result")))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 175)
        self.table.setColumnWidth(1, 390)
        self.table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        self.table.cellDoubleClicked.connect(lambda *_: self.open_selected())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)
        self.table.itemSelectionChanged.connect(self.update_actions)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.open = QPushButton(t("Ouvrir le PDF", "Open PDF"))
        self.folder = QPushButton(t("Ouvrir le dossier", "Open folder"))
        self.open.clicked.connect(self.open_selected)
        self.folder.clicked.connect(lambda: self.open_selected(folder=True))
        refresh = QPushButton(t("Actualiser", "Refresh"))
        close = QPushButton(t("Fermer", "Close"))
        refresh.clicked.connect(self.reload)
        close.clicked.connect(self.close)
        for button in (self.open, self.folder, refresh, close):
            actions.addWidget(button)
        self.reload()

    def reload(self):
        try:
            rows = antivirus_reports(self.workspace.database_path)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.workspace.fail(error)
            rows = []
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            result = row.result_label(self.workspace.tr_pair)
            for col, (value, order) in enumerate(((row.date_label(), row.timestamp),
                                                   (row.path.name, row.path.name.casefold()),
                                                   (result, (row.status, row.threats if row.threats is not None else -1)))):
                item = SortedItem(value)
                item.setData(Qt.ItemDataRole.UserRole, order)
                if col == 1:
                    item.setData(Qt.ItemDataRole.UserRole + 1, str(row.path))
                self.table.setItem(index, col, item)
        self.table.setSortingEnabled(True)
        self.filter_rows()
        self.update_actions()

    def filter_rows(self):
        query = self.search.text().strip().casefold()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, not any(
                query in self.table.item(row, col).text().casefold() for col in range(self.table.columnCount())
            ))
        if self.table.currentRow() >= 0 and self.table.isRowHidden(self.table.currentRow()):
            self.table.clearSelection()
        self.update_actions()

    def update_actions(self):
        for button in (self.open, self.folder):
            button.setEnabled(bool(self.table.selectedItems()))

    def open_selected(self, *, folder=False):
        if self.table.selectedItems():
            item = self.table.item(self.table.currentRow(), 1)
            path = Path(item.data(Qt.ItemDataRole.UserRole + 1))
            try:
                dispatch_viewing_copy(path.parent if folder else path)
            except (OSError, ValueError) as error:
                self.workspace.fail(error)

    def context_menu(self, position):
        index = self.table.indexAt(position)
        menu = QMenu(self)
        if index.isValid():
            self.table.setCurrentCell(index.row(), index.column())
            menu.addAction(self.open.text(), self.open_selected)
            menu.addAction(self.folder.text(), lambda: self.open_selected(folder=True))
        menu.addAction(self.workspace.tr_pair("Actualiser", "Refresh"), self.reload)
        menu.exec(self.table.viewport().mapToGlobal(position))
        menu.deleteLater()
