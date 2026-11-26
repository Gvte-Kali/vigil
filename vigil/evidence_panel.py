"""Inert explorer for the files registered in the active case."""
import os
from datetime import UTC, datetime
from pathlib import Path

from .desktop_integration import checked_descriptor
from .inspection import list_evidence_directory

from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QMenu, QLineEdit, QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)


class EvidencePanel(QWidget):
    def __init__(self, translate, request_preview, selection_action, icon, has_case, *, passive_preview, external_action):
        super().__init__()
        self.tr_pair = translate
        self.request_preview = request_preview
        self.selection_action = selection_action
        self.passive_preview = passive_preview
        self.external_action = external_action
        self.icon = icon
        self.has_case = has_case
        self.mounts = {}
        self.registered_files = {}
        self.archived = False
        self.local_copies = {}
        self.result_folders = {}
        self.displayed_directory = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.filter = QLineEdit()
        self.filter.setClearButtonEnabled(True)
        self.filter.addAction(icon("search", "#55C5D2"), QLineEdit.ActionPosition.LeadingPosition)
        self.filter.textChanged.connect(self.apply_filter)
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.filter, 1)
        self.open_folder = QPushButton(icon("folder-open", "#55C5D2"), "")
        self.open_folder.clicked.connect(lambda: self.external("folder", self.current_location()))
        toolbar.addWidget(self.open_folder)
        layout.addLayout(toolbar)
        split = QSplitter()
        layout.addWidget(split)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        self.tree.currentItemChanged.connect(self.select_preview)
        self.tree.itemDoubleClicked.connect(self.open_item)
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
            view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            self.tabs.addTab(view, "")
        split.addWidget(details)
        split.setSizes([340, 600])
        self.retranslate()

    def retranslate(self):
        tr = self.tr_pair
        self.open_folder.setText(tr("Ouvrir le dossier", "Open folder"))
        self.open_folder.setEnabled(self.current_location() is not None)
        self.filter.setPlaceholderText(tr("Filtrer les fichiers affichés", "Filter displayed files"))
        if not self.has_case():
            hint = tr("Choisissez une affaire pour accéder aux preuves.", "Choose a case to see its evidence.")
        elif not self.mounts and not self.registered_files:
            hint = tr("Aucun support monté ni preuve enregistrée.", "No mounted devices or registered evidence.")
        else:
            hint = tr("Sélectionnez un fichier pour afficher ses 4 premiers Kio.", "Select a file to see its first 4 KiB.")
        self.hint.setText(hint)
        self.update_mount_status()
        self.tabs.setTabText(0, tr("Métadonnées", "Metadata"))
        self.tabs.setTabText(1, tr("Hexadécimal", "Hex"))
        self.tabs.setTabText(2, tr("Chaînes ASCII", "ASCII strings"))

    def set_files(self, rows, *, copies=None, keep_state=True, archived=False, result_folders=None):
        self.archived = archived
        self.result_folders = result_folders or {}
        copies = copies or {}
        self.local_copies = {name: copies.get(evidence_id) for evidence_id, name, _ in rows}
        self.registered_files = {name: digest for _, name, digest in rows}
        self.rebuild_tree(keep_state=keep_state)

    def set_mounts(self, mounts):
        if mounts != self.mounts:
            self.displayed_directory = None
            self.mounts = dict(mounts)
            self.rebuild_tree()

    @staticmethod
    def item_key(item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and len(data) == 4:
            return ("mounted", data[0], tuple(data[2] or ()))
        return ("registered", data[0]) if data else ("group", item.text(0))

    def items(self):
        stack = [self.tree.topLevelItem(i) for i in reversed(range(self.tree.topLevelItemCount()))]
        while stack:
            item = stack.pop()
            yield item
            stack.extend(item.child(i) for i in reversed(range(item.childCount())))

    def rebuild_tree(self, *, keep_state=False):
        expanded, collapsed, selected, populated = set(), set(), set(), set()
        scroll = self.tree.verticalScrollBar()
        position = scroll.value()
        current = self.tree.currentItem()
        current_key = self.item_key(current) if current and keep_state else None
        if keep_state:
            for item in self.items():
                key = self.item_key(item)
                (expanded if item.isExpanded() else collapsed).add(key)
                if item.childCount():
                    populated.add(key)
                if item.isSelected():
                    selected.add(key)
        if not keep_state:
            self.displayed_directory = None
        self.tree.clear()
        if not keep_state:
            for view in self.views:
                view.clear()
        groups = {}
        for name, digest in self.registered_files.items():
            if self.registered_source(name)[1] is not None:
                continue
            path = Path(name)
            copy = self.local_copies.get(name)
            parent = next((str(folder) for folder in reversed(copy.parents) if folder.name == "preuves"), str(copy.parent)) if copy else self.tr_pair("Sans copie locale", "No local copy")
            if parent not in groups:
                groups[parent] = QTreeWidgetItem(self.tree, [parent])
                groups[parent].setIcon(0, self.icon("folder", "#55C5D2"))
            item = QTreeWidgetItem(groups[parent], [path.name])
            item.setData(0, Qt.ItemDataRole.UserRole, (name, digest))
            item.setIcon(0, self.file_icon(path))
            item.setToolTip(0, f"{copy}\n{name}" if copy else name)
        for group in groups.values():
            group.setExpanded(self.item_key(group) not in collapsed)
        for root, mount_id in sorted(self.mounts.items()):
            self.add_live_item(self.tree, root, Path(root), (root, mount_id), True)
        for root, labels in self.result_folders.items():
            self.add_live_item(self.tree, self.tr_pair(*labels), root, None, True)
        if keep_state:
            for item in self.items():
                key = self.item_key(item)
                if key in expanded:
                    item.setExpanded(True)
                elif key in populated:
                    self.expand_directory(item)
                if key == current_key:
                    self.tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
                item.setSelected(key in selected)
            scroll.setValue(position)
        self.retranslate()
        self.apply_filter(self.filter.text())

    def update_mount_status(self):
        if self.mounts:
            self.hint.setText(self.tr_pair(
                "Montages système en lecture seule sous /investigation. Dépliez un dossier pour le parcourir.",
                "Read-only system mounts under /investigation. Expand a folder to browse it.",
            ))

    def file_icon(self, path):
        image = path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".gif"}
        return self.icon("image" if image else "list", "#94A3B3")

    def add_live_item(self, parent, label, path, mount, directory):
        item = QTreeWidgetItem(parent, [label])
        item.setIcon(0, self.icon("folder", "#55C5D2") if directory else self.file_icon(path))
        item.setToolTip(0, str(path))
        item.setData(0, Qt.ItemDataRole.UserRole, (str(path), None if self.archived else self.registered_files.get(str(path)), mount, directory))
        if directory:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    def expand_directory(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or len(data) != 4 or not data[3] or item.childCount():
            return
        path, _, mount, _ = data
        try:
            if mount:
                rows = list_evidence_directory(path, *mount)
            else:
                scope = next(root for root in self.result_folders if Path(path).is_relative_to(root))
                with checked_descriptor(Path(path), scope=scope, directory=True) as descriptor:
                    with os.scandir(descriptor) as entries:
                        rows = sorted((entry.name, entry.is_dir(follow_symlinks=False))
                                      for entry in entries if entry.is_dir(follow_symlinks=False)
                                      or entry.is_file(follow_symlinks=False))
        except (OSError, ValueError, StopIteration) as error:
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

    def registered_source(self, name):
        if self.archived:
            return name, None, False
        roots = [root for root in self.mounts or {} if Path(name).is_relative_to(root)]
        root = max(roots, key=len, default=None)
        return name, (root, self.mounts[root]) if root else None, False

    def selected_sources(self):
        sources = []
        for item in self.tree.selectedItems():
            if item.isHidden():
                continue
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                sources.append((data[0], *data[2:]) if len(data) == 4 else self.registered_source(data[0]))
            else:
                sources.extend(self.registered_source(child.data(0, Qt.ItemDataRole.UserRole)[0])
                               for child in (item.child(index) for index in range(item.childCount()))
                               if not child.isHidden())
        return sources

    def resource(self, item):
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            if item.childCount():
                first = item.child(0).data(0, Qt.ItemDataRole.UserRole)
                copy = self.local_copies.get(first[0])
                if copy:
                    return str(copy.parents[1]), None, None, True
            return None
        if len(data) == 4:
            return tuple(data)
        copy = self.local_copies.get(data[0])
        if copy:
            return (*data, None, False)
        return None

    def current_location(self):
        item = self.tree.currentItem()
        if item is not None:
            return self.resource(item)
        if self.displayed_directory is not None:
            return self.displayed_directory
        if self.tree.topLevelItemCount() == 1:
            return self.resource(self.tree.topLevelItem(0))
        return None

    def external(self, action, resource):
        if resource is not None:
            self.external_action(action, resource)

    def select_preview(self, item, _previous):
        resource = self.resource(item)
        if resource is not None and resource[3]:
            self.displayed_directory = resource
        self.open_folder.setEnabled(self.current_location() is not None)
        data = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if data and (len(data) == 2 or not data[3]):
            self.passive_preview(*data[:3])
        else:
            self.passive_preview()
            for view in self.views:
                view.clear()

    def open_item(self, item, _column):
        resource = self.resource(item)
        if resource is not None and resource[3]:
            item.setExpanded(True)
        elif resource is not None:
            self.external("file", resource)
        elif item.data(0, Qt.ItemDataRole.UserRole):
            self.hint.setText(self.tr_pair("Le contenu référencé est indisponible.",
                                          "The referenced content is unavailable."))

    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.tree.setCurrentItem(item)
        sources = [row for row in self.selected_sources() if row[1] or not any(
            Path(row[0]).is_relative_to(root) for root in self.result_folders
        )]
        resource = self.resource(item)
        tr = self.tr_pair
        menu = QMenu(self)
        if resource is not None:
            directory = resource[3]
            if directory:
                menu.addAction(self.icon("folder", "#55C5D2"), tr("Ouvrir dans Vigil", "Open in Vigil"),
                               lambda: item.setExpanded(True))
            else:
                menu.addAction(self.icon("external-link", "#55C5D2"),
                               tr("Ouvrir avec l’application par défaut", "Open with default application"),
                               lambda: self.external("file", resource))
            menu.addAction(self.icon("folder-open", "#55C5D2"),
                           tr("Ouvrir le dossier", "Open folder"), lambda: self.external("folder", resource))
            menu.addAction(self.icon("copy", "#55C5D2"), tr("Copier le chemin", "Copy path"),
                           lambda: self.external("copy", resource))
        if sources:
            if resource is not None:
                menu.addSeparator()
            menu.addAction(tr("Ajouter aux preuves", "Add to evidence"),
                           lambda: self.selection_action(sources, True))
            menu.addAction(tr("Vérifier l’intégrité", "Verify integrity"),
                           lambda: self.selection_action(sources, False))
        if not menu.isEmpty():
            menu.exec(self.tree.viewport().mapToGlobal(position))
        menu.deleteLater()

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
        if local := snapshot.get("local_copy"):
            lines = [local, tr("Source de l’aperçu : copie locale de l’affaire",
                               "Preview source: local case copy"),
                     f"{tr('Chemin d’origine', 'Original path')}: {path}"]
        else:
            lines = [path]
        lines.extend((
            f"{tr('Taille', 'Size')}: {snapshot['size']} B",
            f"{tr('Permissions', 'Permissions')}: {snapshot['mode']}",
            f"{tr('Modifié (UTC)', 'Modified (UTC)')}: "
            f"{datetime.fromtimestamp(snapshot['mtime'], UTC).isoformat()}",
            f"{tr('MIME estimé par extension', 'MIME inferred from extension')}: "
            f"{snapshot['mime_hint'] or '—'}",
            f"{tr('SHA-256 enregistré', 'Recorded SHA-256')}: {digest or '—'}",
            f"{tr('Octets prévisualisés', 'Bytes previewed')}: {snapshot['bytes_read']}",
        ))
        self.views[0].setPlainText("\n".join(lines))
        self.views[1].setPlainText(snapshot["hex"])
        self.views[2].setPlainText(snapshot["strings"])
