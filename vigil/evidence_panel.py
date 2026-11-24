"""Inert explorer for the files registered in the active case."""
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)


class EvidencePanel(QWidget):
    def __init__(self, translate, request_preview):
        super().__init__()
        self.tr_pair = translate
        self.request_preview = request_preview
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.filter = QLineEdit()
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter)
        split = QSplitter()
        layout.addWidget(split)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemActivated.connect(self.inspect)
        split.addWidget(self.tree)
        details = QWidget()
        details_layout = QVBoxLayout(details)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        details_layout.addWidget(self.hint)
        self.tabs = QTabWidget()
        details_layout.addWidget(self.tabs)
        self.views = [QPlainTextEdit() for _ in range(3)]
        for view in self.views:
            view.setReadOnly(True)
            self.tabs.addTab(view, "")
        split.addWidget(details)
        split.setSizes([340, 600])
        self.retranslate()

    def retranslate(self):
        tr = self.tr_pair
        self.filter.setPlaceholderText(tr("Filtrer les fichiers enregistrés", "Filter registered files"))
        self.hint.setText(tr(
            "Ouvrez un fichier de l’affaire pour lire ses 4 premiers Kio.",
            "Open a case file to read its first 4 KiB.",
        ))
        self.tabs.setTabText(0, tr("Métadonnées", "Metadata"))
        self.tabs.setTabText(1, tr("Hexadécimal", "Hex"))
        self.tabs.setTabText(2, tr("Chaînes ASCII", "ASCII strings"))

    def set_files(self, rows):
        self.tree.clear()
        for view in self.views:
            view.clear()
        groups = {}
        for _, name, digest in rows:
            path = Path(name)
            parent = str(path.parent)
            if parent not in groups:
                groups[parent] = QTreeWidgetItem(self.tree, [parent])
            item = QTreeWidgetItem(groups[parent], [path.name])
            item.setData(0, Qt.ItemDataRole.UserRole, (name, digest))
            item.setToolTip(0, name)
        self.tree.expandAll()
        self.apply_filter(self.filter.text())

    def apply_filter(self, value):
        query = value.strip().casefold()
        for row in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(row)
            for index in range(group.childCount()):
                child = group.child(index)
                child.setHidden(query not in child.toolTip(0).casefold())
            group.setHidden(all(group.child(index).isHidden() for index in range(group.childCount())))

    def inspect(self, item, _column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            self.request_preview(*data)

    def show_preview(self, path, digest, snapshot):
        tr = self.tr_pair
        self.views[0].setPlainText("\n".join((
            path,
            f"{tr('Taille', 'Size')}: {snapshot['size']} B",
            f"{tr('Permissions', 'Permissions')}: {snapshot['mode']}",
            f"{tr('Modifié (UTC)', 'Modified (UTC)')}: "
            f"{datetime.fromtimestamp(snapshot['mtime'], UTC).isoformat()}",
            f"{tr('MIME estimé par extension', 'MIME inferred from extension')}: "
            f"{snapshot['mime_hint'] or '—'}",
            f"{tr('SHA-256 enregistré', 'Recorded SHA-256')}: {digest}",
            f"{tr('Octets prévisualisés', 'Bytes previewed')}: {snapshot['bytes_read']}",
        )))
        self.views[1].setPlainText(snapshot["hex"])
        self.views[2].setPlainText(snapshot["strings"])
