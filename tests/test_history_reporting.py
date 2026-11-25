import os
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from vigil.history import case_events
from vigil.reporting import case_pdf_reports, case_report
from vigil.storage import audit, create_case, database


class HistoryAndReportingTest(unittest.TestCase):
    def test_pagination_and_case_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "vigil.sqlite"
            with database(state) as connection:
                case = create_case(connection, "First", "Alice")
                other = create_case(connection, "Second", "Bob")
                for number in range(5):
                    audit(connection, "Alice", case, "module.success", {"number": number})
                audit(connection, "Bob", other, "module.success", {})
                first = case_events(connection, case, "alice", limit=2)
                second = case_events(connection, case, before=first[-1]["sequence"], limit=2)
                self.assertTrue(all(row["operator"] == "Alice" for row in first + second))
                self.assertLess(second[0]["sequence"], first[-1]["sequence"])

    def test_pdf_list_is_case_scoped_and_ignores_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "vigil.sqlite"
            with database(state) as connection:
                case = create_case(connection, "Case", "Alice")
                create_case(connection, "Other", "Alice")
            run = root / "legacy-custody" / "Case" / "scan-fixture"
            run.mkdir(parents=True)
            outside = root / "legacy-custody" / "Other"
            outside.mkdir(parents=True)
            report = run / "scan.pdf"
            report.touch()
            foreign = outside / "foreign.pdf"
            foreign.touch()
            (run / "link.pdf").symlink_to(foreign)
            copy = run.parent / "rapports" / run.name / report.name
            self.assertEqual(case_pdf_reports(state, case), [copy])
            self.assertEqual(copy.read_bytes(), report.read_bytes())
            report.unlink()
            self.assertEqual(case_pdf_reports(state, case), [copy])

    def test_pdf_copies_keep_timestamps_and_distinguish_analysis_runs(self):
        from vigil.reporting import pdf_analysis_kind

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "cases.sqlite"
            with database(state) as connection:
                case = create_case(connection, "Analysis", "Alice")
            custody = state.parent / "legacy-custody" / "Analysis"
            for module, timestamp in (("archives", 100), ("clamav", 200)):
                folder = custody / "analyses" / f"vigil.{module}-fixture"
                folder.mkdir(parents=True)
                report = folder / "report.pdf"
                report.write_text(module)
                os.utime(report, (timestamp, timestamp))
            reports = case_pdf_reports(state, case)
            self.assertEqual([pdf_analysis_kind(path) for path in reports], ["clamav", "archives"])
            self.assertEqual([int(path.stat().st_mtime) for path in reports], [200, 100])
            self.assertEqual([path.read_text() for path in reports], ["clamav", "archives"])

    def test_report_digests_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "vigil.sqlite"
            with database(state) as connection:
                case = create_case(connection, "First", "Alice")
                create_case(connection, "Second", "Bob")
            first = case_report(state, case)
            second = case_report(state, case)
            self.assertNotEqual(first, second)
            report = first / "case.json"
            self.assertEqual(json.loads(report.read_text())["case"]["name"], "First")
            checksum, filename = (first / "SHA256SUMS").read_text().split()
            self.assertEqual(filename, report.name)
            self.assertEqual(checksum, hashlib.sha256(report.read_bytes()).hexdigest())
