"""Graphite/Cyan tokens shared by the Qt workspace."""
GRAPHITE = "#101419"
SURFACE = "#192129"
BORDER = "#34434E"
TEXT = "#DCE3EA"
ACCENT = "#55C5D2"
SUCCESS = "#79CDA0"
WARNING = "#E4BC72"
VIOLET = "#B59AF0"
SPACE = 8
ICONS = {
    "Dashboard": "home", "Configuration": "settings", "Entity": "folder", "System": "settings", "Current case": "folder", "Module catalogue": "database",
    "Quick actions": "play",
    "Evidence explorer": "folder-tree", "Evidence": "shield", "Analyses": "flask-conical",
    "Actions and history": "list", "PDF reports": "folder", "Export case": "upload",
}

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
QListView#caseManagerList {
    background: #18212B; alternate-background-color: #263444; selection-background-color: #203741;
    border: 1px solid #35404E; border-radius: 6px;
}
QWidget#caseInspectorPanel { border: 1px solid #35404E; border-radius: 6px; }
QFrame#caseActionDivider { background: #35404E; border: none; }
QToolButton#caseImportButton {
    background: #273447; color: #F1F6FC; border: 1px solid #4B6076;
    border-radius: 7px; padding: 6px 22px 6px 12px; font-weight: 600;
}
QToolButton#caseImportButton:hover { background: #35475D; border-color: #7393AE; }
QToolButton#caseImportButton:focus { border-color: #A3F3FC; }
QToolButton#caseImportButton:disabled { background: #202A36; color: #91A1B3; border-color: #35404E; }
QToolButton#caseImportButton::menu-indicator { subcontrol-position: right center; right: 8px; }
QMenu#caseImportMenu { background: #18212B; border: 1px solid #35404E; padding: 4px; }
QMenu#caseImportMenu::item { padding: 8px 14px 8px 30px; border-radius: 4px; }
QMenu#caseImportMenu::item:selected { background: #203741; color: #A5EAF2; }
QMenu#caseImportMenu::item:disabled { color: #91A1B3; }
QPushButton[caseDestructive="true"]:enabled { color: #FF9CA3; border-color: #75434B; }
QPushButton[caseDestructive="true"]:enabled:hover { background: #482A34; }
QListWidget#navigation {
    background: #101318; border: none; padding: 0 7px 0 0;
    selection-background-color: #203741; selection-color: #80DEE8;
}
QListWidget#navigation::item { min-height: 31px; padding: 4px 11px; border-radius: 6px; }
QListWidget#navigation::item:hover:!selected { background: #1B2834; }
QListWidget#navigation::item:selected { background: #203741; color: #80DEE8; }
QTabBar::tab { background: #151B22; color: #BAC9D7; padding: 8px 11px; }
QTabBar::tab:selected { background: #203741; color: #80DEE8; border-bottom: 2px solid #57C7D4; }
QTabBar::tab:focus { border-top: 1px solid #57C7D4; }
QTableWidget { background: #121820; border: 1px solid #3B495B; gridline-color: #34434E; }
QHeaderView::section { background: #192129; color: #DCE3EA; padding: 6px; border: 0; border-bottom: 1px solid #34434E; }
QStatusBar { background: #151B22; color: #BAC9D7; }
QListWidget#navigation::item:disabled { background: transparent; color: #91A1B3; }
QScrollArea#quickActionArea { background: transparent; border: 0; }
QFrame#quickActionSection { background: #171E27; border: 1px solid #35404E; border-radius: 12px; }
QFrame#quickActionCard { background: #202A36; border: 1px solid #354658; border-radius: 8px; }
QFrame#quickActionCard QLabel { background: transparent; color: #BDCADA; }
QFrame#quickActionCard QPushButton { text-align: left; padding: 9px 11px; }
QFrame#quickActionCard QPushButton:focus { border: 1px solid #A5EAF2; }
QFrame#quickActionCard QPushButton[destructive="true"] { color: #FFE0AA; border-color: #806640; }
QFrame#quickActionCard QPushButton[destructive="true"]:hover { background: #493A2D; }
QLabel#quickCategoryTitle { background: transparent; font-size: 17px; font-weight: 700; }
QLabel#quickActionTitle { color: #57C7D4; background: transparent; font-weight: 700; }
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

for old, new in (("#101318", GRAPHITE), ("#1A2029", SURFACE), ("#35404E", BORDER),
                 ("#DCE3EC", TEXT), ("#57C7D4", ACCENT)):
    STYLE = STYLE.replace(old, new)
