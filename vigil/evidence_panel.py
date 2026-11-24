"""Inert explorer for the files registered in the active case."""
from datetime import UTC, datetime
from pathlib import Path

from .inspection import list_evidence_directory

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
        self.mounts = None
        self.live_items = {}
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
        self.tree.itemExpanded.connect(self.expand_directory)
        split.addWidget(self.tree)
        details = QWidget()
        details_layout = QVBoxLayout(details)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.TextFormat.PlainText)
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
        self.filter.setPlaceholderText(tr("Filtrer les fichiers affichés", "Filter displayed files"))
        self.hint.setText(tr(
            "Ouvrez un fichier de l’affaire pour lire ses 4 premiers Kio.",
            "Open a case file to read its first 4 KiB.",
        ))
        self.update_mount_status()
        self.tabs.setTabText(0, tr("Métadonnées", "Metadata"))
        self.tabs.setTabText(1, tr("Hexadécimal", "Hex"))
        self.tabs.setTabText(2, tr("Chaînes ASCII", "ASCII strings"))

    def set_files(self, rows):
        self.tree.clear()
        self.mounts = None
        self.live_items.clear()
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
        for group in groups.values():
            group.setExpanded(True)
        self.apply_filter(self.filter.text())

    def set_mounts(self, mounts):
        if mounts == self.mounts:
            return
        for item in self.live_items.values():
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self.live_items.clear()
        self.mounts = dict(mounts)
        for root, mount_id in sorted(mounts.items()):
            item = self.add_live_item(self.tree, root, Path(root), (root, mount_id), True)
            self.live_items[root] = item
        for view in self.views:
            view.clear()
        self.retranslate()
        self.apply_filter(self.filter.text())

    def update_mount_status(self):
        if self.mounts:
            self.hint.setText(self.tr_pair(
                "Montages système en lecture seule sous /investigation. Dépliez un dossier pour le parcourir.",
                "Read-only system mounts under /investigation. Expand a folder to browse it.",
            ))

    def add_live_item(self, parent, label, path, mount, directory):
        item = QTreeWidgetItem(parent, [label])
        item.setToolTip(0, str(path))
        item.setData(0, Qt.ItemDataRole.UserRole, (str(path), None, mount, directory))
        if directory:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    def expand_directory(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or len(data) != 4 or not data[3] or item.childCount():
            return
        path, _, mount, _ = data
        try:
            rows = list_evidence_directory(path, *mount)
        except (OSError, ValueError) as error:
            item.setToolTip(0, f"{path}\n{error}")
            self.hint.setText(str(error))
            return
        for name, directory in rows:
            self.add_live_item(item, name, Path(path) / name, mount, directory)
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless)
        self.apply_filter(self.filter.text())

    def apply_filter(self, value):
        query = value.strip().casefold()
        stack = [self.tree.topLevelItem(row) for row in range(self.tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            # Keep lazy directories visible so filtering cannot hide unloaded matches.
            file_item = data and (len(data) == 2 or not data[3])
            item.setHidden(bool(file_item and query not in item.toolTip(0).casefold()))
            stack.extend(item.child(index) for index in range(item.childCount()))

    def inspect(self, item, _column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if len(data) == 2:
            self.request_preview(*data)
        elif not data[3]:
            self.request_preview(*data[:3])

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
            f"{tr('SHA-256 enregistré', 'Recorded SHA-256')}: {digest or '—'}",
            f"{tr('Octets prévisualisés', 'Bytes previewed')}: {snapshot['bytes_read']}",
        )))
        self.views[1].setPlainText(snapshot["hex"])
        self.views[2].setPlainText(snapshot["strings"])
