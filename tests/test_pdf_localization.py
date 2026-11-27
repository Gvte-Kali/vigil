"""Regression tests for the language of generated Vigil PDF presentation."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf" / "vigil_pdf.py"


@unittest.skipUnless(importlib.util.find_spec("reportlab"), "reportlab not installed")
class PDFLocalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("vigil_pdf_test_localized", SCRIPT)
        cls.pdf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.pdf)

    def test_all_report_types_have_english_title(self):
        with patch.dict(os.environ, {"VIGIL_LANG": "en"}):
            for kind in self.pdf.REPORT_META:
                with self.subTest(kind=kind):
                    meta = self.pdf._report_meta(kind)
                    self.assertTrue(meta["title"])
                    self.assertNotEqual(meta["title"], self.pdf.REPORT_META[kind]["title"])
                    self.assertTrue(meta["footer_desc"].startswith("Automatically"))

    def test_french_metadata_unchanged(self):
        with patch.dict(os.environ, {"VIGIL_LANG": "fr"}):
            for kind in self.pdf.REPORT_META:
                with self.subTest(kind=kind):
                    self.assertEqual(self.pdf._report_meta(kind),
                                     self.pdf.REPORT_META[kind])

    def test_english_sections_and_dynamic_labels(self):
        with patch.dict(os.environ, {"VIGIL_LANG": "en"}):
            self.assertEqual(self.pdf._display("Résultat de l'analyse"), "Analysis results")
            self.assertEqual(self.pdf._display("Généré le 28/11/2026"), "Generated on 28/11/2026")
            self.assertIn("Detected", self.pdf._display("3 MENACE(S) DÉTECTÉE(S)") .title())
            self.assertIn("unavailable", self.pdf._display(
                "Cette analyse n'a pas pu être exécutée correctement (statut : failed). "
                "Les résultats ne sont pas disponibles."))
            style = self.pdf.ParagraphStyle("StatusDesc", fontName="Helvetica")
            self.assertEqual(self.pdf.Paragraph("Résultat de l'analyse", style).text,
                             "Analysis results")

    def test_evidence_cell_unchanged(self):
        with patch.dict(os.environ, {"VIGIL_LANG": "en"}):
            style = self.pdf.ParagraphStyle("FilePath", fontName="Courier")
            path = "Résultat de l'analyse"
            self.assertEqual(self.pdf.Paragraph(path, style).text, path)


if __name__ == "__main__":
    unittest.main()
