import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtCore import QSettings, QSize
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "optional Qt dependency unavailable")
class WorkspaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_language_switch_persistence_and_case_selection(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            config = str(Path(tmp) / "settings.ini")
            database = Path(tmp) / "cases.sqlite"
            window = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            self.assertFalse(window.windowIcon().pixmap(40, 40).isNull())
            self.assertEqual(window.tabs.tabText(0), "Affaires")
            for language in ("fr", "en"):
                self.assertFalse(window.language_buttons[language].icon().isNull())
            flag = window.language_buttons["fr"].icon().pixmap(QSize(24, 16), 2).toImage()
            self.assertEqual(flag.pixelColor(46, 16).name(), "#ed2939")
            window.operator.setText("Alice")
            window.case_name.setText("Test & preuve")
            window.create_case()
            window.language_buttons["en"].click()
            self.assertEqual(window.tabs.tabText(0), "Cases")
            self.assertEqual(window.case_label.text(), "Active case  ·  Test & preuve")
            window.close()
            reopened = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            self.assertEqual(reopened.tabs.tabText(0), "Cases")
            self.assertTrue(reopened.language_buttons["en"].isChecked())
            reopened.language_buttons["fr"].click()
            self.assertEqual(reopened.tabs.tabText(1), "Preuves")
            reopened.close()

    def test_background_file_registration_and_verification(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            window.operator.setText("Alice")
            window.case_name.setText("Fixture")
            window.create_case()
            source = root / "synthetic.raw"
            source.write_bytes(b"fixture")
            with patch.object(window, "choose_file", return_value=str(source)):
                window.add_file()
            self.wait_for_task(window)
            self.assertEqual(window.evidence.count(), 1)
            window.evidence.setCurrentRow(0)
            with patch.object(window, "notify") as notify:
                window.verify_file()
                self.wait_for_task(window)
                self.assertEqual(notify.call_args.args[1], "The fingerprint matches.")
            window.close()

    def wait_for_task(self, window):
        for _ in range(200):
            self.app.processEvents()
            time.sleep(0.01)
            if window.busy is None:
                return
        self.fail("background task did not finish")
