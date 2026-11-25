"""Qt case picker and case creation form."""
from datetime import datetime

from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, QObject, QRunnable, QSize, QSortFilterProxyModel,
    QThreadPool, QTimer, Qt, Signal, Slot,
)
from PySide6.QtGui import QColor, QFontDatabase, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListView, QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from .desktop_theme import ACCENT, SUCCESS, VIOLET
from .storage import case_manager_artifacts

CASE = Qt.ItemDataRole.UserRole


def plain_label(text=""):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def date_label(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


class CaseModel(QAbstractListModel):
    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and 0 <= index.row() < len(self.rows):
            row = self.rows[index.row()]
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
                return row["name"]
            if role == CASE:
                return row
        return None

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class CaseFilter(QSortFilterProxyModel):
    sort_keys = ("name", "name", "created_at", "latest")

    def __init__(self, parent):
        super().__init__(parent)
        self.query = ""
        self.sort_mode = 0

    def filterAcceptsRow(self, row, parent):
        return self.query in self.sourceModel().index(row, 0, parent).data().casefold()

    def lessThan(self, left, right):
        key = self.sort_keys[self.sort_mode]
        def rank(index):
            row = index.data(CASE)
            return ((row[key] or "").casefold(), row["name"].casefold(), row["id"])
        return rank(left) < rank(right)


class CaseDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(240, 54)

    def paint(self, painter, option, index):
        manager = self.parent()
        row = index.data(CASE)
        palette = option.palette
        rect = option.rect
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, palette.color(QPalette.ColorRole.Highlight))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, palette.color(QPalette.ColorRole.AlternateBase))
        active = row["id"] == manager.active_id
        manager.icon("folder", SUCCESS if active else ACCENT).paint(painter, rect.x() + 12, rect.y() + 16, 22, 22)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(palette.color(QPalette.ColorRole.Text))
        name = painter.fontMetrics().elidedText(row["name"], Qt.TextElideMode.ElideRight, max(0, rect.width() - 54))
        painter.drawText(rect.x() + 46, rect.y() + 22, name)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(VIOLET))
        secondary = date_label(row["latest"]) or manager.tr_pair("Non renseigné", "Not recorded")
        if active:
            secondary = manager.tr_pair("Active", "Active") + " · " + secondary
        painter.drawText(rect.x() + 46, rect.y() + 43, secondary)
        painter.restore()


class LoadSignals(QObject):
    completed = Signal(int, object, object)


class CaseLoad(QRunnable):
    def __init__(self, generation, load):
        super().__init__()
        self.generation = generation
        self.load = load
        self.signals = LoadSignals()

    def run(self):
        try:
            rows = self.load()
        except Exception as error:
            self.signals.completed.emit(self.generation, None, error)
        else:
            self.signals.completed.emit(self.generation, rows, None)


class CaseManager(QDialog):
    def __init__(self, parent, load_rows, create, import_case, delete, open_case, *, import_archive):
        super().__init__(parent)
        self.tr_pair = tr = parent.tr_pair
        self.icon = parent.action_icon
        self.active_id = parent.active_case_id
        self.load_rows = load_rows
        self.generation = 0
        self.pending_id = self.active_id
        self.metrics = {}
        self.metrics_requests = {}
        self.metrics_generation = 0
        self.details_timer = QTimer(self)
        self.details_timer.setSingleShot(True)
        self.details_timer.setInterval(160)
        self.details_timer.timeout.connect(self.load_details)
        self.load_error = False
        self.loading = True
        self.setWindowTitle(tr("Gestionnaire d’affaires", "Case Manager"))
        self.resize(900, 600)
        self.setMinimumSize(540, 360)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        header = QHBoxLayout()
        emblem = plain_label()
        emblem.setPixmap(self.icon("folder-tree", ACCENT).pixmap(28, 28))
        header.addWidget(emblem)
        heading = QVBoxLayout()
        title = plain_label(tr("Affaires d’investigation", "Investigation cases"))
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        summary = plain_label(tr("Retrouvez, consultez et ouvrez vos affaires.",
                                 "Find, review and open your cases."))
        summary.setWordWrap(True)
        heading.addWidget(summary)
        header.addLayout(heading, 1)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Rechercher une affaire", "Search cases"))
        self.search.setAccessibleName(self.search.placeholderText())
        self.search.addAction(self.icon("search", ACCENT), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        toolbar.addWidget(self.search, 1)
        self.sort = QComboBox()
        self.sort.setAccessibleName(tr("Trier", "Sort"))
        self.sort.addItems([tr("Nom A–Z", "Name A–Z"), tr("Nom Z–A", "Name Z–A"),
                            tr("Création récente", "Newest created"), tr("Dernière activité", "Last activity")])
        toolbar.addWidget(self.sort)
        self.count = plain_label()
        toolbar.addWidget(self.count)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)
        self.model = CaseModel(self)
        self.proxy = CaseFilter(self)
        self.proxy.setSourceModel(self.model)
        self.list_stack = QStackedWidget()
        self.list = QListView()
        self.list.setObjectName("caseManagerList")
        self.list.setModel(self.proxy)
        self.list.setItemDelegate(CaseDelegate(self))
        self.list.setUniformItemSizes(True)
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list_stack.addWidget(self.list)
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch()
        empty_icon = plain_label()
        empty_icon.setPixmap(self.icon("folder", VIOLET).pixmap(32, 32))
        empty_layout.addWidget(empty_icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.empty_title = plain_label()
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setWordWrap(True)
        empty_layout.addWidget(self.empty_title)
        self.empty_text = plain_label()
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_text.setWordWrap(True)
        empty_layout.addWidget(self.empty_text)
        self.reset_search = QPushButton(tr("Effacer la recherche", "Clear search"))
        self.reset_search.clicked.connect(self.search.clear)
        empty_layout.addWidget(self.reset_search, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch()
        self.list_stack.addWidget(empty)
        splitter.addWidget(self.list_stack)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inspector = QWidget()
        self.details = QVBoxLayout(inspector)
        self.details.setContentsMargins(12, 12, 12, 12)
        self.details.setSpacing(8)
        scroll.setWidget(inspector)
        splitter.addWidget(scroll)
        splitter.setSizes([460, 380])

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)
        bar = QHBoxLayout()
        actions = QWidget()
        management = QHBoxLayout(actions)
        management.setContentsMargins(0, 0, 0, 0)
        self.new = self.make_button(management, tr("Nouvelle affaire", "New case"), "plus", create)
        self.archive_button = self.make_button(management, tr("Importer une archive Vigil 2.0",
                                                               "Import a Vigil 2.0 archive"), "upload", import_archive)
        self.import_button = self.make_button(management, tr("Importer un projet Vigil 1.0",
                                                              "Import a Vigil 1.0 project"), "folder", import_case)
        self.import_button.setToolTip(tr("Importer un ancien projet Vigil", "Import a legacy Vigil project"))
        self.delete = self.make_button(management, tr("Supprimer", "Delete"), "trash",
                                       lambda: delete(self.selected_id()), color="#FF9CA3")
        self.delete.setProperty("caseDestructive", True)
        management.addStretch()
        action_scroll = QScrollArea()
        action_scroll.setFrameShape(QFrame.Shape.NoFrame)
        action_scroll.setWidget(actions)
        action_scroll.setWidgetResizable(True)
        action_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        action_scroll.setFixedHeight(actions.sizeHint().height() + 20)
        bar.addWidget(action_scroll, 1)
        self.cancel = self.make_button(bar, tr("Annuler", "Cancel"), "x", self.reject)
        self.open = self.make_button(bar, tr("Ouvrir l’affaire", "Open case"), "folder",
                                     lambda: open_case(self.selected_id()), color="#101318")
        self.open.setProperty("primary", True)
        root.addLayout(bar)

        self.search.textChanged.connect(lambda: self.update_filter())
        self.sort.currentIndexChanged.connect(lambda: self.update_filter())
        self.list.selectionModel().currentChanged.connect(self.selection_changed)
        self.list.doubleClicked.connect(lambda _index: self.open.click())
        self.shortcuts = [
            QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search.setFocus),
            QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new.click),
        ]
        for key in ("Return", "Enter"):
            shortcut = QShortcut(QKeySequence(key), self.list, activated=self.open.click)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            self.shortcuts.append(shortcut)
        self.setTabOrder(self.search, self.sort)
        self.setTabOrder(self.sort, self.list)
        self.setTabOrder(self.list, self.new)
        self.update_filter()

    def make_button(self, layout, text, icon, action, *, color=ACCENT):
        button = QPushButton(self.icon(icon, color), text)
        button.setAutoDefault(False)
        button.clicked.connect(action)
        layout.addWidget(button)
        return button

    def selected_id(self):
        row = self.list.currentIndex().data(CASE)
        return row["id"] if row else ""

    def select_id(self, case_id):
        for index in range(self.proxy.rowCount()):
            candidate = self.proxy.index(index, 0)
            if candidate.data(CASE)["id"] == case_id:
                self.list.setCurrentIndex(candidate)
                return
        self.list.setCurrentIndex(QModelIndex())

    def reload(self, selected=None):
        self.pending_id = selected or self.selected_id() or self.active_id
        self.metrics.clear()
        self.metrics_requests.clear()
        if selected:
            self.search.clear()
        self.generation += 1
        self.loading = True
        self.load_error = False
        self.update_filter()
        job = CaseLoad(self.generation, self.load_rows)
        job.signals.completed.connect(self.loaded)
        QThreadPool.globalInstance().start(job)

    @Slot(int, object, object)
    def loaded(self, generation, rows, error):
        if generation != self.generation:
            return
        self.loading = False
        self.load_error = error is not None
        self.model.replace(rows or [])
        self.update_filter(self.pending_id)
        if error is not None:
            self.empty_text.setText(str(error))

    def update_filter(self, selected=None):
        selected = self.selected_id() if selected is None else selected
        self.proxy.query = self.search.text().strip().casefold()
        self.proxy.sort_mode = self.sort.currentIndex()
        self.proxy.invalidate()
        order = Qt.SortOrder.AscendingOrder if self.proxy.sort_mode == 0 else Qt.SortOrder.DescendingOrder
        self.proxy.sort(0, order)
        self.select_id(selected)
        shown, total = self.proxy.rowCount(), self.model.rowCount()
        tr = self.tr_pair
        self.count.setText(f"{shown}/{total} " + tr("affaires", "cases"))
        self.list_stack.setCurrentIndex(0 if shown else 1)
        self.reset_search.setVisible(bool(total and not shown))
        if self.loading and not shown:
            title, body = tr("Chargement…", "Loading…"), ""
        elif self.load_error:
            title, body = tr("Impossible de charger les affaires.", "Could not load cases."), ""
        elif total:
            title, body = tr("Aucune affaire ne correspond à votre recherche.", "No cases match your search."), ""
        else:
            title = tr("Aucune affaire disponible", "No cases available")
            body = tr("Créez une nouvelle affaire ou importez un ancien projet pour commencer une investigation.",
                      "Create a case or import a legacy project to start an investigation.")
        self.empty_title.setText(title)
        self.empty_text.setText(body)
        self.selection_changed()

    def load_details(self):
        row = self.list.currentIndex().data(CASE)
        if self.loading or not row or row["id"] in self.metrics or row["id"] in self.metrics_requests.values():
            return
        self.metrics_generation += 1
        self.metrics_requests[self.metrics_generation] = row["id"]
        state, case_id, directory = self.parent().database_path, row["id"], row["directory"]
        job = CaseLoad(self.metrics_generation, lambda: case_manager_artifacts(state, case_id, directory))
        job.signals.completed.connect(self.details_loaded)
        QThreadPool.globalInstance().start(job)

    @Slot(int, object, object)
    def details_loaded(self, generation, metrics, error):
        case_id = self.metrics_requests.pop(generation, None)
        if case_id:
            self.metrics[case_id] = metrics or {}
            if case_id == self.selected_id():
                self.selection_changed()

    def selection_changed(self, *_):
        row = self.list.currentIndex().data(CASE)
        self.details_timer.start()
        self.open.setEnabled(bool(row) and not self.loading)
        self.delete.setEnabled(bool(row) and not self.loading)
        while self.details.count():
            item = self.details.takeAt(0)
            if (widget := item.widget()) is not None:
                widget.hide()
                widget.deleteLater()
        tr = self.tr_pair
        if not row:
            hint = plain_label(tr("Sélectionnez une affaire pour consulter ses informations.",
                                  "Select a case to view its details."))
            hint.setWordWrap(True)
            self.details.addWidget(hint)
        else:
            title = plain_label(row["name"])
            title.setObjectName("pageTitle")
            title.setWordWrap(True)
            self.details.addWidget(title)
            active = row["id"] == self.active_id
            metrics = self.metrics.get(row["id"], {})
            path = metrics.get("path", str(self.parent().database_path.parent / "legacy-custody" / row["directory"]))
            rows = (
                ("circle-dot", "État", "Status", tr("Active", "Active") if active else tr("Disponible", "Available")),
                ("info", "Identifiant", "ID", row["id"]),
                ("list", "Référence", "Reference", row["reference"]),
                ("list", "Description", "Description", row["description"]),
                ("plus", "Création", "Created", date_label(row["created_at"])),
                ("circle-dot", "Dernière activité", "Last activity", date_label(row["latest"])),
                ("user", "Opérateur de création", "Creating operator", row["operator"]),
                ("hard-drive", "Preuves", "Evidence", row["evidence_count"]),
                ("database", "Fichiers recensés", "Inventoried files", metrics.get("inventory")),
                ("flask-conical", "Analyses réussies", "Successful analyses", metrics.get("analyses")),
                ("list", "Rapports PDF locaux", "Local PDF reports", metrics.get("reports")),
                ("folder", "Dossier local", "Local folder", path),
            )
            for icon, fr, en, value in rows:
                box = QWidget()
                line = QHBoxLayout(box)
                line.setContentsMargins(0, 0, 0, 0)
                symbol = plain_label()
                symbol.setPixmap(self.icon(icon, SUCCESS if icon == "circle-dot" and active else VIOLET).pixmap(15, 15))
                label = plain_label(tr(fr, en))
                label.setWordWrap(True)
                text = plain_label(str(value) if value is not None and value != "" else tr("Non renseigné", "Not recorded"))
                text.setWordWrap(True)
                text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if en in {"ID", "Local folder"}:
                    text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
                line.addWidget(symbol)
                line.addWidget(label, 2)
                line.addWidget(text, 3)
                self.details.addWidget(box)
        self.details.addStretch()


class NewCaseDialog(QDialog):
    def __init__(self, parent, tr, operator):
        super().__init__(parent)
        self.setWindowTitle(tr("Nouvelle affaire", "New case"))
        self.resize(460, 260)
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.name.setMaxLength(120)
        self.reference = QLineEdit()
        self.reference.setMaxLength(120)
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(104)
        form.addRow(tr("Nom de l’affaire", "Case name"), self.name)
        form.addRow(tr("Référence du dossier", "Case reference"), self.reference)
        form.addRow(tr("Description", "Description"), self.description)
        form.addRow(tr("Opérateur", "Operator"), plain_label(operator))
        buttons = QDialogButtonBox()
        self.submit = buttons.addButton(tr("Créer", "Create"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.submit.setProperty("primary", True)
        buttons.addButton(tr("Annuler", "Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form.addRow(buttons)
