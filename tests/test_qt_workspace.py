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
            self.assertEqual(window.tabs.tabText(1), "Affaires")
            for language in ("fr", "en"):
                self.assertFalse(window.language_buttons[language].icon().isNull())
            flag = window.language_buttons["fr"].icon().pixmap(QSize(24, 16), 2).toImage()
            self.assertEqual(flag.pixelColor(46, 16).name(), "#ed2939")
            window.add_operator("Alice")
            window.case_name.setText("Test & preuve")
            window.create_case()
            window.select_case()
            window.case_search.setText("unmatched")
            self.assertTrue(window.cases.item(0).isHidden())
            self.assertIn("Test & preuve", window.active_case.text())
            window.case_search.setText("PREUVE")
            self.assertFalse(window.cases.item(0).isHidden())
            window.language_buttons["en"].click()
            self.assertEqual(window.tabs.tabText(1), "Cases")
            self.assertEqual(window.case_label.text(), "Locked case  ·  Test & preuve")
            window.close()
            reopened = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            self.assertEqual(reopened.tabs.tabText(1), "Cases")
            self.assertEqual(reopened.operator.currentText(), "Alice")
            self.assertTrue(reopened.language_buttons["en"].isChecked())
            reopened.language_buttons["fr"].click()
            self.assertEqual(reopened.tabs.tabText(2), "Preuves")
            reopened.close()

    def test_background_file_registration_and_verification(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            window.add_operator("Alice")
            window.case_name.setText("Fixture")
            window.create_case()
            window.select_case()
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

    def test_active_case_requires_confirmation_for_switch(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = str(root / "settings.ini")
            database = root / "cases.sqlite"
            window = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            window.add_operator("Alice")
            for name in ("First", "Second"):
                window.case_name.setText(name)
                window.create_case()
            self.assertEqual(window.active_case_id, "")
            window.cases.setCurrentRow(0)
            window.select_case()
            first = window.active_case_id

            window.cases.setCurrentRow(1)
            with patch.object(window, "confirm_case_change", return_value=False) as confirm:
                window.case_clicked(window.cases.currentItem())
            confirm.assert_called_once_with("First", "Second")
            self.assertEqual(window.active_case_id, first)
            self.assertEqual(window.cases.currentRow(), 0)
            window.cases.setCurrentRow(1)
            with patch.object(window, "confirm_case_change", return_value=True):
                window.case_clicked(window.cases.currentItem())
            self.assertIn("Second", window.active_case.text())
            self.assertNotEqual(window.active_case_id, first)
            window.close()

            reopened = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            self.assertIn("Second", reopened.active_case.text())
            self.assertEqual(len(reopened.system_panel.cards), 4)
            reopened.close()

    def test_inventory_keeps_partition_details_collapsed(self):
        from vigil.system_panel import SystemPanel

        with patch.object(SystemPanel, "refresh"):
            panel = SystemPanel(lambda french, english: english)
        panel.devices = [{
            "path": "/dev/example", "type": "disk", "size": 2048, "pttype": "gpt",
            "children": [{"path": "/dev/example1", "type": "part", "size": 1024,
                          "fstype": "ext4", "parttype": "fixture"}],
        }]
        panel.render()
        disk = panel.tree.topLevelItem(1).child(0)
        details, partition = disk.child(0), disk.child(1)
        self.assertTrue(disk.isExpanded())
        self.assertFalse(details.isExpanded())
        self.assertFalse(partition.isExpanded())
        self.assertNotEqual(disk.foreground(0).color(), partition.foreground(0).color())
        partition.setExpanded(True)
        self.assertIn("ext4", partition.child(1).text(0))
        panel.close()

    def wait_for_task(self, window):
        for _ in range(200):
            self.app.processEvents()
            time.sleep(0.01)
            if window.busy is None:
                return
        self.fail("background task did not finish")
