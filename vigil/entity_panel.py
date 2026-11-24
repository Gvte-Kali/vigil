"""Qt editor for the organization metadata used in PDF reports."""
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .entity import load_entity, save_entity

LABELS = {
    "entity_name": ("Nom de l’entité", "Organization name"),
    "establishment": ("Établissement", "Establishment"),
    "address": ("Adresse", "Address"),
    "phone": ("Téléphone", "Phone"),
    "email": ("Adresse e-mail", "Email address"),
}


class EntityPanel(QWidget):
    def __init__(self, data, translate):
        super().__init__()
        self.data = data
        self.tr_pair = translate
        self.pending_logo = None
        self.changed = False
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.fields = {}
        self.labels = {}
        for key in LABELS:
            field = QLineEdit()
            field.textEdited.connect(self.mark_changed)
            label = QLabel()
            label.setBuddy(field)
            self.fields[key] = field
            self.labels[key] = label
            form.addRow(label, field)
        self.preview = QLabel()
        self.preview.setMinimumHeight(80)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.preview)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.choose = QPushButton()
        self.choose.clicked.connect(self.choose_logo)
        actions.addWidget(self.choose)
        self.remove = QPushButton()
        self.remove.clicked.connect(self.remove_logo)
        actions.addWidget(self.remove)
        self.save_button = QPushButton()
        self.save_button.setProperty("primary", True)
        self.save_button.clicked.connect(self.save_interactive)
        actions.addWidget(self.save_button)
        actions.addStretch()
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        try:
            config = load_entity(data)
            for key, field in self.fields.items():
                field.setText(str(config.get(key) or ""))
            logo = config.get("logo")
            if isinstance(logo, str) and logo:
                logo_path = (data / logo).resolve()
                if logo_path.is_relative_to(data.resolve()):
                    self.show_logo(self.read_logo(logo_path))
        except (OSError, ValueError) as error:
            self.show_error(error)
        self.retranslate()

    def retranslate(self):
        tr = self.tr_pair
        for key, pair in LABELS.items():
            self.labels[key].setText(tr(*pair))
        self.choose.setText(tr("Choisir un logo…", "Choose a logo…"))
        self.remove.setText(tr("Retirer le logo", "Remove logo"))
        self.save_button.setText(tr("Enregistrer l’entité", "Save organization"))
        if self.preview.pixmap().isNull():
            self.preview.setText(tr("Aucun logo d’entité", "No organization logo"))

    def mark_changed(self, *_):
        self.changed = True
        self.status.clear()

    @staticmethod
    def read_logo(path):
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("logo must be a regular image up to 10 MiB")
        reader = QImageReader(str(path))
        size = reader.size()
        if reader.format().data().lower() not in {b"png", b"jpeg", b"jpg"}:
            raise ValueError("logo must be PNG or JPEG")
        if not size.isValid() or max(size.width(), size.height()) > 4096 or size.width() * size.height() > 8_000_000:
            raise ValueError("invalid or oversized logo dimensions")
        image = reader.read()
        if image.isNull():
            raise ValueError("could not decode logo")
        return image

    def show_logo(self, image):
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            180, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))

    def choose_logo(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, self.tr_pair("Choisir un logo", "Choose a logo"), "", "PNG / JPEG (*.png *.jpg *.jpeg)",
        )
        if not filename:
            return
        try:
            image = self.read_logo(Path(filename))
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not image.save(buffer, "PNG"):
                raise ValueError("could not encode logo")
            self.pending_logo = bytes(buffer.data())
            self.show_logo(image)
            self.mark_changed()
        except (OSError, ValueError) as error:
            self.show_error(error)

    def remove_logo(self):
        self.pending_logo = b""
        self.preview.clear()
        self.retranslate()
        self.mark_changed()

    def show_error(self, error):
        self.status.setText(self.tr_pair("Configuration inaccessible", "Configuration unavailable")
                            + f" · {error}")

    def save(self):
        if self.changed:
            save_entity(self.data, {key: field.text() for key, field in self.fields.items()},
                        self.pending_logo)
            self.changed = False
            self.pending_logo = None
            self.status.setText(self.tr_pair("Configuration enregistrée.", "Configuration saved."))

    def save_interactive(self):
        try:
            self.save()
        except (OSError, ValueError) as error:
            self.show_error(error)
