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
            self.assertNotIn("Affaires", [window.navigation.item(i).text() for i in range(window.navigation.count())])
            for language in ("fr", "en"):
                self.assertFalse(window.language_buttons[language].icon().isNull())
            flag = window.language_buttons["fr"].icon().pixmap(QSize(24, 16), 2).toImage()
            self.assertEqual(flag.pixelColor(46, 16).name(), "#ed2939")
            window.add_operator("Alice")
            window.create_case("Test & preuve")
            with patch.object(window, "confirm_case_selection", return_value=True):
                window.case_clicked(window.cases.currentItem())
            self.assertIn("Test & preuve", window.active_case.text())
            window.language_buttons["en"].click()
            self.assertNotIn("Cases", [window.navigation.item(i).text() for i in range(window.navigation.count())])
            self.assertEqual(window.case_title.text(), "Current case · Test & preuve")
            self.close_workspace(window)
            reopened = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            self.assertEqual(reopened.case_title.text(), "Current case")
            self.assertEqual(reopened.operator.currentText(), "Alice")
            self.assertTrue(reopened.language_buttons["en"].isChecked())
            reopened.language_buttons["fr"].click()
            self.assertEqual(reopened.case_navigation.tabText(1), "Preuves")
            self.close_workspace(reopened)

    def test_case_manager_filters_preserves_selection_and_requires_explicit_open(self):
        from vigil.desktop import QDialog, Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            window.add_operator("Alice")
            window.create_case("Zulu")
            window.create_case("Fixture", "REF-42", "Test description")

            def select():
                dialog = window.case_picker
                deadline = time.monotonic() + 3
                while dialog.loading and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertFalse(dialog.loading)
                self.assertEqual(dialog.proxy.rowCount(), 2)
                hint = next(label for label in dialog.findChildren(type(dialog.count))
                            if label.text() == "Sélectionnez une affaire pour consulter ses informations."
                            and not label.isHidden())
                dialog.list.setCurrentIndex(dialog.proxy.index(0, 0))
                self.assertTrue(hint.isHidden())
                selected = dialog.selected_id()
                dialog.sort.setCurrentIndex(1)
                self.assertEqual(dialog.selected_id(), selected)
                dialog.search.setText("FIXTURE")
                self.assertEqual(dialog.proxy.rowCount(), 1)
                self.assertEqual(dialog.selected_id(), selected)
                self.assertIn("REF-42", [label.text() for label in dialog.findChildren(type(dialog.count))])
                self.assertFalse(window.active_case_id)
                if pick_with_button:
                    dialog.open.click()
                else:
                    dialog.list.doubleClicked.emit(dialog.list.currentIndex())
                return dialog.result()

            with patch.object(window, "confirm_case_selection", return_value=True), \
                    patch.object(QDialog, "exec", autospec=True, side_effect=select):
                for pick_with_button in (False, True):
                    window.active_case_id = ""
                    window.choose_case()
                    self.assertTrue(window.active_case_id)
            self.assertIsNone(window.case_picker)
            self.close_workspace(window)

    def test_case_manager_action_bars_and_import_menu_at_minimum_size(self):
        from PySide6.QtWidgets import QToolButton
        from vigil.case_manager import CaseManager
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            for language, label in (("fr", "Importer"), ("en", "Import")):
                window.change_language(language)
                calls = []
                dialog = CaseManager(window, lambda: [], lambda: None, lambda: calls.append("legacy"),
                                     lambda _: None, lambda _: None,
                                     import_archive=lambda: calls.append("archive"))
                dialog.show()
                self.app.processEvents()
                for size in (dialog.size(), dialog.minimumSize()):
                    dialog.resize(size)
                    self.app.processEvents()
                    self.assertLess(dialog.new.y(), dialog.search.y())
                    self.assertLess(dialog.import_button.y(), dialog.search.y())
                    self.assertEqual(dialog.count.geometry().center().y(), dialog.open.geometry().center().y())
                    for action in (dialog.new, dialog.import_button, dialog.cancel, dialog.open):
                        self.assertIs(action.parentWidget(), dialog)
                        self.assertTrue(dialog.rect().contains(action.geometry()))
                    self.assertFalse(dialog.open.isEnabled())
                self.assertEqual(dialog.import_button.text(), label)
                self.assertEqual(dialog.import_button.popupMode(), QToolButton.ToolButtonPopupMode.InstantPopup)
                menu_actions = dialog.import_button.menu().actions()
                self.assertEqual(len(menu_actions), 2)
                for action in menu_actions:
                    self.assertFalse(action.icon().isNull())
                    action.trigger()
                self.assertEqual(calls, ["archive", "legacy"])
                dialog.reject()
                dialog.deleteLater()
            self.close_workspace(window)

    def test_archive_preview_confirmation_restores_without_activating(self):
        from vigil import storage
        from vigil.case_export import export_case
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "cases.sqlite"
            with storage.database(source) as connection:
                case_id = storage.create_case(connection, "Portable", "Alice")
            archive = export_case(source, case_id, "Alice", root).path / "affaire.tar.gz"
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat),
                               root / "restored" / "cases.sqlite")
            window.add_operator("Bob")
            accept, cancel = object(), object()
            with patch("vigil.desktop.QFileDialog.getOpenFileName", return_value=(str(archive), "")), \
                    patch("vigil.desktop.QMessageBox") as message, patch.object(window, "notify") as notify, \
                    patch.object(window, "run_task", side_effect=lambda operation, success: success(operation())):
                message.return_value.addButton.side_effect = [accept, cancel]
                message.return_value.clickedButton.return_value = accept
                window.import_case_archive()
            self.assertEqual(window.cases.currentItem().text(), "Portable")
            self.assertFalse(window.active_case_id)
            self.assertIn(case_id, notify.call_args.args[2])
            self.close_workspace(window)

    def test_case_manager_refuses_deletion_during_operations(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            window.add_operator("Alice")
            window.create_case("First")
            window.create_case("Second")
            first, second = (window.cases.item(i).data(256) for i in range(2))
            window.active_case_id = first
            window.external_runs.append(type("PendingRun", (), {"status": lambda self: None})())
            with patch.object(window, "notify") as notify:
                window.delete_selected_case(second)
            notify.assert_called_once()
            self.assertEqual(window.cases.count(), 2)
            self.assertEqual(window.active_case_id, first)
            window.external_runs.clear()
            self.close_workspace(window)

    def test_background_file_registration_and_verification(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            window.add_operator("Alice")
            window.create_case("Fixture")
            with patch.object(window, "confirm_case_selection", return_value=True):
                window.case_clicked(window.cases.currentItem())
            source = root / "synthetic.raw"
            source.write_bytes(b"fixture")
            with patch.object(window, "choose_file", return_value=str(source)):
                window.add_file()
            self.wait_for_task(window)
            self.assertEqual(window.evidence.topLevelItemCount(), 1)
            self.assertFalse(window.case_folder_button.isHidden())
            source.unlink()
            window.change_language("en")
            group = window.explorer.tree.topLevelItem(0)
            window.explorer.inspect(group.child(0), 0)
            self.wait_for_task(window)
            metadata = window.explorer.views[0].toPlainText()
            self.assertIn("local case copy", metadata)
            self.assertIn(f"Original path: {source}", metadata)
            self.assertEqual(Path(metadata.splitlines()[0]).name, "contenu")
            self.assertEqual(Path(group.text(0)).name, "preuves")
            self.assertEqual(window.explorer.views[2].toPlainText(), "fixture")
            evidence_item = window.evidence.topLevelItem(0).child(0)
            digest = evidence_item.text(1)
            self.assertEqual(len(digest), 64)
            window.explorer.tree.setCurrentItem(group.child(0))
            with patch.object(window, "notify") as notify:
                window.process_explorer_selection(window.explorer.selected_sources(), False)
                self.wait_for_task(window)
                self.assertIn("Matches", notify.call_args.args[2])
                self.assertEqual(notify.call_args.kwargs["copy_text"], digest)
            window.show()
            self.app.processEvents()
            window.evidence.setCurrentItem(evidence_item)
            from vigil.desktop import QDesktopServices

            self.assertTrue(evidence_item.text(2).startswith("preuves/"))
            with patch.object(QDesktopServices, "openUrl", return_value=True) as open_case_url:
                window.case_folder_button.click()
            self.assertEqual(Path(open_case_url.call_args.args[0].toLocalFile()).name, "Fixture")
            with patch.object(QDesktopServices, "openUrl", return_value=True) as open_url:
                window.open_evidence_folder()
            self.assertEqual(Path(open_url.call_args.args[0].toLocalFile()).parent.name, "preuves")
            window.case_navigation.setCurrentIndex(window.case_pages.indexOf(window.evidence.parentWidget()))
            window.evidence.itemActivated.emit(evidence_item, 0)
            self.wait_for_task(window)
            self.assertIs(window.case_pages.currentWidget(), window.explorer_page)
            self.assertIn("local case copy", window.explorer.views[0].toPlainText())

            Path(open_url.call_args.args[0].toLocalFile(), "contenu").unlink()
            window.case_navigation.setCurrentIndex(window.case_pages.indexOf(window.evidence.parentWidget()))
            with patch.object(window, "fail") as failure:
                window.evidence.itemActivated.emit(evidence_item, 0)
                self.wait_for_task(window)
                self.assertIn("has no local copy", str(failure.call_args.args[0]))
            self.assertIs(window.case_pages.currentWidget(), window.evidence.parentWidget())
            self.assertTrue(window.isVisible())

            from PySide6.QtWidgets import QMessageBox

            with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
                window.delete_selected_evidence()
            self.wait_for_task(window)
            self.assertEqual(window.evidence.topLevelItemCount(), 0)
            self.assertTrue(window.case_folder_button.isHidden())
            self.assertEqual(window.explorer.tree.topLevelItemCount(), 0)
            self.assertTrue(window.active_case_id)
            self.assertTrue(window.isVisible())
            self.close_workspace(window)

    def test_explorer_click_previews_latest_and_double_click_routes_by_type(self):
        from vigil import storage
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "settings"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            window.add_operator("Alice")
            window.create_case("Fixture")
            with patch.object(window, "confirm_case_selection", return_value=True):
                window.case_clicked(window.cases.currentItem())
            for name in ("first", "second"):
                source = root / f"{name}.txt"
                source.write_text(name)
                storage.register_file(window.database_path, window.active_case_id, source, "Alice")
            window.refresh_evidence()
            group = window.explorer.tree.topLevelItem(0)
            window.explorer.tabs.setCurrentIndex(1)
            with patch.object(window.explorer, "external_action") as external:
                for index in range(2):
                    window.explorer.tree.setCurrentItem(group.child(index))
                deadline = time.monotonic() + 3
                while window.explorer.views[2].toPlainText() != "second" and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertEqual(window.explorer.views[2].toPlainText(), "second")
                self.assertEqual(window.explorer.tabs.currentIndex(), 1)
                self.assertIn("7365", window.explorer.views[1].toPlainText().replace(" ", ""))
                external.assert_not_called()
                window.explorer.open_item(group, 0)
                self.assertTrue(group.isExpanded())
                external.assert_not_called()
                window.explorer.open_item(group.child(1), 0)
                self.assertEqual(external.call_args.args[0], "file")
            self.close_workspace(window)

    def test_pdf_table_sorts_dates_and_selects_the_correct_report_folder(self):
        from PySide6.QtCore import Qt
        from vigil.desktop import QDesktopServices, Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "settings"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            window.add_operator("Alice")
            window.create_case("Fixture")
            with patch.object(window, "confirm_case_selection", return_value=True):
                window.case_clicked(window.cases.currentItem())
            from vigil.storage import case_storage_directory

            custody = case_storage_directory(window.database_path, window.active_case_id) / "analyses"
            for module, name, timestamp in (
                ("archives", "a.pdf", 1767139200),  # 31 December 2025 UTC
                ("clamav", "b.pdf", 1767312000),    # 2 January 2026 UTC
            ):
                directory = custody / f"vigil.{module}-fixture"
                directory.mkdir(parents=True)
                report = directory / name
                report.touch()
                os.utime(report, (timestamp, timestamp))
            window.refresh_pdf_reports()
            table = window.pdf_reports
            self.assertEqual(table.item(0, 2).text(), "b.pdf")
            table.sortItems(1, Qt.SortOrder.AscendingOrder)
            self.assertEqual(table.item(0, 2).text(), "a.pdf")
            table.sortItems(2, Qt.SortOrder.DescendingOrder)
            self.assertEqual(table.item(0, 2).text(), "b.pdf")
            table.setCurrentCell(0, 0)
            with patch.object(QDesktopServices, "openUrl", return_value=True) as open_url:
                window.open_pdf_folder()
            self.assertEqual(Path(open_url.call_args.args[0].toLocalFile()).name, "vigil.clamav-fixture")
            self.close_workspace(window)

    def test_active_case_requires_confirmation_for_switch(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = str(root / "settings.ini")
            database = root / "cases.sqlite"
            window = Workspace(QSettings(config, QSettings.Format.IniFormat), database)
            window.add_operator("Alice")
            for name in ("First", "Second"):
                window.create_case(name)
            self.assertEqual(window.active_case_id, "")
            window.cases.setCurrentRow(0)
            with patch.object(window, "confirm_case_selection", return_value=False) as confirm:
                window.case_clicked(window.cases.currentItem())
            confirm.assert_called_once_with(None, "First")
            self.assertEqual(window.active_case_id, "")
            window.cases.setCurrentRow(0)
            with patch.object(window, "confirm_case_selection", return_value=True):
                window.case_clicked(window.cases.currentItem())
            first = window.active_case_id
            with patch.object(window, "confirm_case_selection", return_value=False) as confirm:
                window.case_clicked(window.cases.currentItem())
            confirm.assert_called_once_with(None, "First")
            self.assertEqual(window.active_case_id, first)

            window.cases.setCurrentRow(1)
            with patch.object(window, "confirm_case_selection", return_value=False) as confirm:
                window.case_clicked(window.cases.currentItem())
            confirm.assert_called_once_with("First", "Second")
            self.assertEqual(window.active_case_id, first)
            self.assertEqual(window.cases.currentRow(), 0)
            window.cases.setCurrentRow(1)
            with patch.object(window, "confirm_case_selection", return_value=True):
                window.case_clicked(window.cases.currentItem())
            self.assertIn("Second", window.active_case.text())
            window.change_language("en")
            self.assertEqual(window.case_title.text(), "Current case · Second")
            window.change_language("fr")
            self.assertEqual(window.case_title.text(), "Affaire en cours · Second")
            window.change_language("en")
            with patch("vigil.desktop.investigation_mounts", return_value={"/investigation/sdb1": 42}):
                window.refresh_case_mount()
            window.explorer.set_files([("id", "/investigation/sdb1/note.txt", "fixture-digest")])
            self.assertEqual(window.explorer.tree.topLevelItemCount(), 1)
            root_item = window.explorer.tree.topLevelItem(0)
            self.assertEqual(root_item.text(0), "/investigation/sdb1")
            with patch("vigil.evidence_panel.list_evidence_directory",
                       return_value=[("docs", True), ("note.txt", False)]) as list_directory:
                window.explorer.expand_directory(root_item)
            list_directory.assert_called_once_with("/investigation/sdb1", "/investigation/sdb1", 42)
            root_item.setExpanded(True)
            root_item.child(1).setSelected(True)
            with patch("vigil.evidence_panel.list_evidence_directory",
                       return_value=[("docs", True), ("note.txt", False)]):
                window.explorer.set_files([("id", "/investigation/sdb1/note.txt", "fixture-digest")])
            root_item = window.explorer.tree.topLevelItem(0)
            self.assertTrue(root_item.isExpanded())
            self.assertTrue(root_item.child(1).isSelected())
            with patch.object(window.explorer, "request_preview") as preview:
                window.explorer.inspect(root_item.child(1), 0)
            preview.assert_called_once_with("/investigation/sdb1/note.txt", "fixture-digest", ("/investigation/sdb1", 42))
            with patch("vigil.desktop.investigation_mounts", return_value={}):
                window.refresh_case_mount()
            self.assertEqual(window.explorer.tree.topLevelItemCount(), 1)
            self.assertEqual(window.explorer.tree.topLevelItem(0).child(0).text(0), "note.txt")
            self.assertNotEqual(window.active_case_id, first)
            self.close_workspace(window)

            legacy_settings = QSettings(config, QSettings.Format.IniFormat)
            legacy_settings.setValue("active_case_id", window.active_case_id)
            legacy_settings.sync()
            reopened = Workspace(legacy_settings, database)
            self.assertEqual(reopened.active_case_id, "")
            self.assertEqual(reopened.cases.currentRow(), -1)
            self.assertEqual(reopened.history_rows.count(), 0)
            self.assertFalse(legacy_settings.contains("active_case_id"))
            reopened.cases.setCurrentRow(1)
            with patch.object(reopened, "confirm_case_selection", return_value=True):
                reopened.case_clicked(reopened.cases.currentItem())
            self.assertIn("Second", reopened.active_case.text())
            self.assertEqual(len(reopened.system_panel.cards), 4)
            self.close_workspace(reopened)

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
        panel.render_inventory()
        self.assertTrue(panel.tree.topLevelItem(1).child(0).child(1).isExpanded())
        panel.stop()
        panel.close()

    def close_workspace(self, window):
        with patch.object(window, "confirm_close", return_value=True):
            self.assertTrue(window.close())

    def test_close_confirmation_and_failed_save_keep_workspace_open(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            with patch.object(window, "confirm_close", return_value=False):
                with patch.object(window, "save_before_close") as save:
                    self.assertFalse(window.close())
                    save.assert_not_called()
            with patch.object(window, "confirm_close", return_value=True):
                with patch.object(window, "save_before_close", side_effect=OSError("fixture")):
                    with patch.object(window, "notify") as notify:
                        self.assertFalse(window.close())
                        self.assertIn("Saving failed", notify.call_args.args[1])
            self.close_workspace(window)

    def test_sidebar_switches_pages_and_localizes_groups(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            self.assertEqual(window.navigation.currentItem().text(), "Accueil")
            self.assertEqual(window.pages.currentIndex(), 0)
            self.assertTrue(window.pages.currentWidget().isAncestorOf(window.system_panel))
            self.assertTrue(window.pages.currentWidget().isAncestorOf(window.diagnostics))
            self.assertNotIn("Diagnostic", [window.navigation.item(i).text()
                                            for i in range(window.navigation.count())])
            self.assertEqual(window.system_panel.resources_timer.interval(), 5000)
            self.assertEqual(window.system_panel.inventory_timer.interval(), 2000)
            window.navigation.setCurrentRow(3)
            self.assertEqual(window.pages.currentIndex(), 1)
            window.language_buttons["en"].click()
            self.assertEqual(window.navigation.item(0).text(), "WORKSPACE")
            self.assertEqual(window.navigation.currentItem().text(), "Current case")
            self.assertEqual(window.pages.currentIndex(), 1)
            self.close_workspace(window)

    def test_group_can_collapse_and_reopen(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            window.show()
            self.app.processEvents()
            for index in range(window.navigation.count()):
                group = window.navigation.item(index)
                header = window.navigation.itemWidget(group)
                if header is not None:
                    self.assertTrue(header.isVisible())
                    self.assertGreaterEqual(header.height(), header.fontMetrics().height() + 12)
            header = window.navigation.itemWidget(window.navigation.item(0))
            header.click()
            self.assertTrue(window.navigation.item(1).isHidden())
            header.click()
            self.assertFalse(window.navigation.item(1).isHidden())
            self.close_workspace(window)

    def test_quick_actions_are_one_standalone_page(self):
        from PySide6.QtWidgets import QLabel, QPushButton
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            sidebar = window.navigation
            quick = sidebar.item(sidebar.count() - 1)
            self.assertEqual(quick.text(), "Actions rapides")
            system = next(sidebar.item(index) for index in range(sidebar.count())
                          if sidebar.item(index).text() == "SYSTÈME")
            sidebar.itemWidget(system).click()
            self.assertTrue(quick.isHidden())
            sidebar.itemWidget(system).click()
            self.assertFalse(quick.isHidden())
            sidebar.setCurrentItem(quick)
            page = window.pages.currentWidget()
            self.assertEqual(
                [label.text() for label in page.findChildren(QLabel, "quickCategoryTitle")],
                ["Antivirus", "Stockage", "Acquisition"],
            )
            from vigil.desktop import QuickActionArea
            from PySide6.QtWidgets import QBoxLayout

            area = page.findChild(QuickActionArea)
            window.show()
            window.resize(1440, 850)
            self.app.processEvents()
            self.assertEqual(area.sections.direction(), QBoxLayout.Direction.LeftToRight)
            window.resize(940, 740)
            self.app.processEvents()
            self.assertEqual(area.sections.direction(), QBoxLayout.Direction.LeftToRight)
            action_buttons = page.findChildren(QPushButton)
            self.assertEqual(len(action_buttons), 7)
            self.assertTrue(all(not button.icon().isNull() for button in action_buttons))
            window.language_buttons["en"].click()
            self.assertEqual(quick.text(), "Quick actions")
            self.assertEqual(page.findChildren(QLabel, "quickCategoryTitle")[1].text(), "Storage")
            self.close_workspace(window)

    def test_external_terminal_preference_is_accessible_without_task_dock(self):
        from PySide6.QtWidgets import QDockWidget, QInputDialog
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            self.assertFalse(window.findChildren(QDockWidget))
            with patch.object(QInputDialog, "getItem", return_value=("foot", True)):
                window.button_for_terminal.click()
            self.assertEqual(window.settings.value("external_terminal"), "foot")
            self.close_workspace(window)

    def test_mount_storage_button_sends_mount_without_an_active_case(self):
        from PySide6.QtWidgets import QMessageBox, QPushButton
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat),
                               root / "cases.sqlite")
            window.add_operator("Alice")
            self.assertEqual(window.active_case_id, "")
            button = next(b for b in window.findChildren(QPushButton) if b.text() == "Monter un stockage")
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                    patch.object(window, "launch_external") as launch:
                button.click()
            argv, operation = launch.call_args.args
            self.assertEqual(operation, "storage-mount")
            self.assertIn("VIGIL_LEGACY_PROJECT=(no-project)", argv)
            self.assertIn("VIGIL_ACTIVE_USER=Alice", argv)
            self.assertTrue(argv[-1].endswith("vigil_stockage_mount.sh"))
            self.close_workspace(window)

    def test_case_workspace_holds_icon_tabs(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            navigation = [window.navigation.item(i).text() for i in range(window.navigation.count())]
            self.assertNotIn("Preuves", navigation)
            window.navigation.setCurrentRow(navigation.index("Affaire en cours"))
            sections = [
                window.case_navigation.tabText(i) for i in range(window.case_navigation.count())
            ]
            self.assertEqual(sections, [
                "Explorateur", "Preuves", "Analyses", "Actions et journal", "Rapports PDF", "Exporter l’affaire",
            ])
            window.case_navigation.setCurrentIndex(2)
            self.assertTrue(window.case_pages.currentWidget().isAncestorOf(window.modules))
            self.assertIn("Recensement de fichiers", [
                window.modules.item(i).text().split("  ·  ")[0]
                for i in range(window.modules.count())
            ])
            self.assertTrue(window.case_navigation.usesScrollButtons())
            self.assertTrue(all(not window.case_navigation.tabIcon(i).isNull()
                                for i in range(window.case_navigation.count())))
            self.close_workspace(window)

    def test_case_header_displays_mounted_source_and_clears_it(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            with patch("vigil.desktop.read_zones", return_value={
                "/investigation": [("/investigation/part", "/dev/loop7p1", "ext4", "ro")],
            }):
                window.refresh_case_mount()
                self.assertIn("Sous-montages", window.investigation_mount.text())
                self.assertIn("/dev/loop7p1", window.investigation_mount.text())
                self.assertIn("ro", window.investigation_mount.text())
            with patch("vigil.desktop.read_zones", return_value={"/investigation": []}):
                window.refresh_case_mount()
                self.assertIn("Non monté", window.investigation_mount.text())
                self.assertNotIn("/dev/loop7p1", window.investigation_mount.text())
            self.close_workspace(window)

    def test_startup_requires_an_operator_and_locks_the_choice(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            with patch.object(window, "session_operator_input", return_value=("", False)):
                self.assertFalse(window.choose_session_operator())
            with patch.object(window, "session_operator_input", return_value=("Alice", True)):
                self.assertTrue(window.choose_session_operator())
            self.assertEqual(window.require_operator(), "Alice")
            self.assertFalse(window.operator.isEnabled())
            self.assertEqual(window.active_case_id, "")
            self.close_workspace(window)

    def test_entity_form_preserves_legacy_metadata_and_validates_logo(self):
        import json

        from PySide6.QtGui import QImage
        from vigil.entity_panel import EntityPanel

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            config = data / "config/system.json"
            config.parent.mkdir()
            config.write_text('{"entity_name":"Old name","custom":42}')
            panel = EntityPanel(data, lambda french, english: english)
            self.assertEqual(panel.fields["entity_name"].text(), "Old name")
            logo = data / "example.png"
            image = QImage(10, 10, QImage.Format.Format_RGB32)
            image.fill(0x336699)
            self.assertTrue(image.save(str(logo)))
            with patch("vigil.entity_panel.QFileDialog.getOpenFileName", return_value=(str(logo), "")):
                panel.choose_logo()
            self.assertFalse(panel.preview.pixmap().isNull())
            panel.fields["entity_name"].setText("New name")
            panel.save()
            saved = json.loads(config.read_text())
            self.assertEqual(saved["custom"], 42)
            self.assertEqual(saved["entity_name"], "New name")
            self.assertTrue((data / saved["logo"]).is_file())
            panel.remove_logo()
            panel.save()
            self.assertEqual(json.loads(config.read_text())["logo"], "")
            panel.close()

    def test_close_does_not_save_while_a_vigil_zone_is_mounted(self):
        from vigil.desktop import Workspace
        from vigil.shutdown_state import ShutdownBlocked

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            with patch.object(window, "confirm_close", return_value=True), \
                    patch("vigil.desktop.check_shutdown_state", side_effect=ShutdownBlocked("/investigation")), \
                    patch.object(window, "save_before_close") as save, patch.object(window, "notify") as notify:
                self.assertFalse(window.close())
                save.assert_not_called()
                self.assertIn("Close blocked", notify.call_args.args[1])
            self.close_workspace(window)

    def test_close_saves_with_empty_zones_without_comparing_block_modes(self):
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = Workspace(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat),
                root / "cases.sqlite",
            )
            with patch.object(window, "confirm_close", return_value=True), \
                    patch("vigil.shutdown_state.read_zones", return_value={"/investigation": [], "/stockage": []}), \
                    patch("vigil.shutdown_state.read_block_modes") as read_modes, \
                    patch.object(window, "save_before_close") as save, \
                    patch.object(window, "notify") as notify:
                self.assertTrue(window.close())
                read_modes.assert_not_called()
                save.assert_called_once()
                notify.assert_not_called()

    def test_antivirus_case_is_hidden_from_case_picker(self):
        from vigil import storage
        from vigil.desktop import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root / "cases.sqlite"
            with storage.database(database) as connection:
                storage.antivirus_case(connection, "Alice")
                storage.create_case(connection, "Fixture", "Alice")
            window = Workspace(QSettings(str(root / "prefs"), QSettings.Format.IniFormat), database)
            self.assertEqual([window.cases.item(i).text() for i in range(window.cases.count())],
                             ["Fixture"])
            self.close_workspace(window)

    def wait_for_task(self, window):
        for _ in range(200):
            self.app.processEvents()
            time.sleep(0.01)
            if window.busy is None:
                return
        self.fail("background task did not finish")
