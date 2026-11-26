"""Keyboard-accessible Qt action card using the native button state machine."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ActionCard(QPushButton):
    def __init__(self, icon, color, action):
        super().__init__()
        self.setObjectName("quickActionCard")
        self.action_icon = icon
        content = QVBoxLayout(self)
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(8)
        heading = QHBoxLayout()
        heading.setSpacing(8)
        glyph = QLabel()
        glyph.setPixmap(icon.pixmap(18, 18))
        heading.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        self.title = QLabel()
        self.title.setStyleSheet(f"color: {color}; font-weight: 700;")
        self.title.setWordWrap(True)
        heading.addWidget(self.title, 1)
        content.addLayout(heading)
        self.description = QLabel()
        self.description.setObjectName("actionCardDescription")
        self.description.setWordWrap(True)
        content.addWidget(self.description)
        for label in (glyph, self.title, self.description):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setTextFormat(Qt.TextFormat.PlainText)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(action)

    def set_title(self, text):
        self.title.setText(text)
        self.setAccessibleName(text)

    def text(self):
        return self.title.text()

    def icon(self):
        return self.action_icon

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()
