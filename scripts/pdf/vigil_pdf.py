#!/usr/bin/env python3
"""Générateur PDF commun pour tous les rapports d'analyse Vigil.

Trame standardisée : page d'accueil identique (entité / établissement /
adresse / téléphone / email / logo + utilisateur + projet + date), en-tête de
page (bandeau accent + titre du rapport) et pied de page numéroté. Chaque type
d'analyse n'apporte que sa section de résultats via un fichier JSON (ou un log
pour ClamAV) et un identifiant de rapport ``--kind``.

Usage :
    vigil_pdf.py --kind images|videos|clamav \
        --json <resultat.json>  (images, videos)
        --log  <scan.log>        (clamav) \
        --user "..." --project "..." --dir <dossier_rapports> \
        [--action "..."] [--options "..."] [--comment "..."] [--config-dir "..."]

La charte graphique (couleurs, polices, tableaux) est définie une seule fois
ici. Les informations de l'entité sont lues depuis la configuration statique.
"""

import argparse
import json
import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfgen import canvas as _canvas


# --------------------------------------------------------------------------- #
#  Numerotation des pages : Page X / Y
# --------------------------------------------------------------------------- #

class NumberedCanvas(_canvas.Canvas):
    """Canvas a deux passes : reporte le nombre total de pages puis dessine
    le pied de page 'Page X / Y' sur chaque page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        width, height = A4
        self.setFillColor(COLOR_GREY)
        self.setFont("Helvetica", 8)
        self.drawRightString(width - 20 * mm, 9 * mm,
                             f"Page {self._pageNumber} / {total}")


# --------------------------------------------------------------------------- #
#  Charte graphique commune
# --------------------------------------------------------------------------- #

COLOR_ACCENT = HexColor("#2b4c7e")
COLOR_DARK = HexColor("#1a1a2e")
COLOR_DANGER = HexColor("#c0392b")
COLOR_DANGER_BG = HexColor("#fdf0ee")
COLOR_SUCCESS = HexColor("#27ae60")
COLOR_SUCCESS_BG = HexColor("#eafaf1")
COLOR_GREY = HexColor("#5f6c7b")
COLOR_LIGHT = HexColor("#f4f6f8")
COLOR_BORDER = HexColor("#d1d9e0")
COLOR_ROW_ALT = HexColor("#f8f9fb")


REPORT_META = {
    "images": {
        "title": "Rapport d'analyse des fichiers image",
        "header": "Rapport d'analyse des fichiers image",
        "doc_title": "Rapport d'analyse des fichiers image - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers image",
        "fname_prefix": "rapport_images",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent "
            "l'extraction et le classement des fichiers image détectés sur le "
            "périphérique analysé."
        ),
    },
    "videos": {
        "title": "Rapport d'analyse des fichiers vidéo",
        "header": "Rapport d'analyse des fichiers vidéo",
        "doc_title": "Rapport d'analyse des fichiers vidéo - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers vidéo",
        "fname_prefix": "rapport_videos",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent "
            "l'extraction et le classement des fichiers vidéo détectés sur le "
            "périphérique analysé."
        ),
    },
    "audio": {
        "title": "Rapport d'analyse des fichiers audio",
        "header": "Rapport d'analyse des fichiers audio",
        "doc_title": "Rapport d'analyse des fichiers audio - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers audio",
        "fname_prefix": "rapport_audio",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent "
            "l'extraction et le classement des fichiers audio détectés sur le "
            "périphérique analysé."
        ),
    },
    "office": {
        "title": "Rapport d'analyse des fichiers bureautiques",
        "header": "Rapport d'analyse des fichiers bureautiques",
        "doc_title": "Rapport d'analyse des fichiers bureautiques - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers bureautiques",
        "fname_prefix": "rapport_office",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent "
            "l'extraction et le classement des fichiers bureautiques détectés "
            "sur le périphérique analysé."
        ),
    },
    "archives": {
        "title": "Rapport d'analyse des fichiers archives",
        "header": "Rapport d'analyse des fichiers archives",
        "doc_title": "Rapport d'analyse des fichiers archives - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers archives",
        "fname_prefix": "rapport_archives",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent "
            "l'extraction des fichiers archives (zip, 7z, rar, tar, etc.) "
            "détectés sur le périphérique analysé."
        ),
    },
    "crypto": {
        "title": "Rapport d'analyse des fichiers verrouillés",
        "header": "Rapport d'analyse des fichiers verrouillés",
        "doc_title": "Rapport d'analyse des fichiers verrouillés - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers verrouillés",
        "fname_prefix": "rapport_crypto",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent les "
            "fichiers protégés par mot de passe ou chiffrés, détectés parmi "
            "les archives et documents du périphérique analysé."
        ),
    },
    "entropy": {
        "title": "Rapport d'analyse des fichiers à forte entropie",
        "header": "Rapport d'analyse des fichiers à forte entropie",
        "doc_title": "Rapport d'analyse des fichiers à forte entropie - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers à forte entropie",
        "fname_prefix": "rapport_entropy",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent les "
            "fichiers à forte entropie (contenu hautement aléatoire, chiffré "
            "ou compressé) détectés sur le périphérique analysé."
        ),
    },
    "formataudit": {
        "title": "Rapport d'audit de format (extensions trompeuses)",
        "header": "Rapport d'audit de format",
        "doc_title": "Rapport d'audit de format - Vigil",
        "doc_subject": "Audit des extensions trompeuses et contenu caché",
        "fname_prefix": "rapport_formataudit",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Il présente l'audit ciblé du contenu "
            "des fichiers dont l'extension ne correspond pas au format réel "
            "(exécutable renommé, archive déguisée...) et des fichiers à "
            "forte entropie, via signatures forensiques locales et binwalk."
        ),
    },
    "bigfiles": {
        "title": "Rapport d'analyse des fichiers volumineux",
        "header": "Rapport d'analyse des fichiers volumineux",
        "doc_title": "Rapport d'analyse des fichiers volumineux - Vigil",
        "doc_subject": "Rapport d'analyse des fichiers volumineux",
        "fname_prefix": "rapport_bigfiles",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés concernent les "
            "fichiers volumineux et les fichiers creux (octets nuls) détectés "
            "sur le périphérique analysé."
        ),
    },
    "clamav": {
        "title": "Rapport d'analyse antivirus",
        "header": "Rapport d'analyse antivirus",
        "doc_title": "Rapport d'analyse antivirus - Vigil",
        "doc_subject": "Rapport de scan antivirus ClamAV",
        "fname_prefix": "rapport_clamav",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Les résultats présentés sont basés sur "
            "les signatures virales ClamAV disponibles au moment du scan."
        ),
    },
    "usbhid": {
        "title": "Rapport de triage USB (détection Rubber Ducky)",
        "header": "Rapport de triage USB (détection Rubber Ducky)",
        "doc_title": "Rapport de triage USB - Vigil",
        "doc_subject": "Détection de périphériques USB à interface clavier (HID)",
        "fname_prefix": "rapport_usbhid",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Il présente le résultat du triage des "
            "périphériques USB apparus entre la baseline (périphériques "
            "débranchés) et le branchement des périphériques à analyser. "
            "Un périphérique se présentant avec une interface clavier (HID) "
            "est signalé comme potentiellement malveillant (type Rubber "
            "Ducky) : ses frappes sont bloquées et il n'est pas proposé au "
            "montage."
        ),
    },
    "census": {
        "title": "Rapport de recensement des fichiers",
        "header": "Rapport de recensement des fichiers",
        "doc_title": "Rapport de recensement des fichiers - Vigil",
        "doc_subject": "Rapport de recensement et dédoublonnage des fichiers",
        "fname_prefix": "rapport_census",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Il présente l'inventaire intégral et "
            "neutre des fichiers présents sur le périphérique analysé, le "
            "marquage des doublons (conservés, non jetés) et le filtrage "
            "checksafe à partir des bases externes fournies par l'autorité. "
            "La base SQLite associée (dans le dossier du projet) est signée "
            "en SHA-256 comme livrable forensique."
        ),
    },
    "custody": {
        "title": "Cha\u00eene de custody (journal des actions)",
        "header": "Cha\u00eene de custody",
        "doc_title": "Cha\u00eene de custody - Vigil",
        "doc_subject": "Journal des actions de la chasse",
        "fname_prefix": "rapport_custody",
        "footer_desc": (
            "Journal chronologique des actions effectu\u00e9es pendant la "
            "recherche de menaces (montage, analyses, d\u00e9montage)."
        ),
    },
    "multi": {
        "title": "Rapport d'analyse forensique consolidé",
        "header": "Rapport consolidé",
        "doc_title": "Rapport d'analyse forensique consolidé - Vigil",
        "doc_subject": "Rapport consolidé multi-analyses",
        "fname_prefix": "rapport_multi",
        "footer_desc": (
            "Ce rapport a été généré automatiquement par Vigil, plateforme "
            "d'analyse forensique USB. Il consolide en un seul document les "
            "résultats des analyses sélectionnées, exécutées en chaîne sur le "
            "périphérique analysé."
        ),
    },
}


# --------------------------------------------------------------------------- #
#  Configuration statique du système
# --------------------------------------------------------------------------- #

def load_system_config(data_dir=None):
    """Charge la configuration statique depuis data_dir/config/system.json."""
    base_dir = os.environ.get("VIGIL_BASE", "/opt/vigil")
    data_d = data_dir or os.environ.get("VIGIL_DATA_DIR",
                                          os.path.join(base_dir, "data"))
    config_file = os.path.join(data_d, "config", "system.json")
    config = {
        "entity_name": "", "establishment": "", "address": "",
        "phone": "", "email": "", "logo": "", "logo_path": None,
    }
    if os.path.isfile(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            for key in ("entity_name", "establishment", "address",
                        "phone", "email", "logo"):
                if key in raw:
                    config[key] = raw[key] or ""
        except (OSError, ValueError):
            pass
    if config["logo"]:
        logo_abs = os.path.join(data_d, config["logo"])
        if os.path.isfile(logo_abs):
            config["logo_path"] = logo_abs
    return config


# --------------------------------------------------------------------------- #
#  Styles et trame
# --------------------------------------------------------------------------- #

def esc(text):
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", fontName="Helvetica-Bold", fontSize=24,
        textColor=COLOR_DARK, spaceAfter=2, alignment=TA_LEFT, leading=28,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", fontName="Helvetica", fontSize=11,
        textColor=COLOR_GREY, spaceAfter=20, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", fontName="Helvetica-Bold", fontSize=14,
        textColor=COLOR_ACCENT, spaceBefore=18, spaceAfter=10,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="TableLabel", fontName="Helvetica-Bold", fontSize=9,
        textColor=white, alignment=TA_LEFT, leading=12,
    ))
    styles.add(ParagraphStyle(
        name="TableValue", fontName="Helvetica", fontSize=10,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=13,
    ))
    styles.add(ParagraphStyle(
        name="TableValueBold", fontName="Helvetica-Bold", fontSize=10,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=13,
    ))
    styles.add(ParagraphStyle(
        name="ThreatPath", fontName="Courier", fontSize=9,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=12,
    ))
    styles.add(ParagraphStyle(
        name="ThreatSig", fontName="Helvetica-Bold", fontSize=9,
        textColor=COLOR_DANGER, alignment=TA_LEFT, leading=12,
    ))
    styles.add(ParagraphStyle(
        name="FooterText", fontName="Helvetica", fontSize=8,
        textColor=COLOR_GREY, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="StatusBig", fontName="Helvetica-Bold", fontSize=16,
        textColor=COLOR_SUCCESS, alignment=TA_CENTER, leading=20,
    ))
    styles.add(ParagraphStyle(
        name="StatusBigDanger", fontName="Helvetica-Bold", fontSize=16,
        textColor=COLOR_DANGER, alignment=TA_CENTER, leading=20,
    ))
    styles.add(ParagraphStyle(
        name="StatusDesc", fontName="Helvetica", fontSize=10,
        textColor=COLOR_GREY, alignment=TA_LEFT, leading=13,
    ))
    return styles


def make_header_footer(config, header_label):
    """Fabrique le callback de page avec bandeau accent + pied de page."""
    entity_name = config.get("entity_name", "") or "VIGIL"
    establishment = config.get("establishment", "") or ""
    if establishment:
        header_text = f"{entity_name} / {establishment}"
    else:
        header_text = entity_name

    def header_footer(canvas_obj, doc):
        canvas_obj.saveState()
        width, height = A4

        canvas_obj.setFillColor(COLOR_ACCENT)
        canvas_obj.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
        canvas_obj.setFillColor(white)

        canvas_obj.setFont("Helvetica-Bold", 11)
        canvas_obj.drawString(20 * mm, height - 8 * mm, header_text)

        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.drawRightString(width - 20 * mm, height - 8 * mm,
                                   header_label)

        canvas_obj.setStrokeColor(COLOR_BORDER)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
        canvas_obj.setFillColor(COLOR_GREY)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(20 * mm, 9 * mm,
                              f"Vigil - {datetime.now().strftime('%d/%m/%Y')}")
        # Le numero de page (Page X / Y) est dessine par NumberedCanvas en
        # seconde passe : on n'ecrit rien ici pour eviter un double affichage.
        canvas_obj.restoreState()

    return header_footer


def info_table(rows, col_widths=None, logo=None):
    """Tableau d'information (label | valeur), avec logo optionnel en colonne."""
    if logo is not None:
        logo_w = 60 * mm
        label_w = 38 * mm
        value_w = 170 * mm - logo_w - label_w
        table_data = []
        for idx, (label, value) in enumerate(rows):
            cell = logo if idx == 0 else ""
            table_data.append([
                cell,
                Paragraph(label, ParagraphStyle("l", fontName="Helvetica-Bold",
                          fontSize=9, textColor=white, leading=12)),
                Paragraph(value, ParagraphStyle("v", fontName="Helvetica",
                          fontSize=10, textColor=COLOR_DARK, leading=13)),
            ])
        table = Table(table_data, colWidths=[logo_w, label_w, value_w])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), COLOR_LIGHT),
            ("SPAN", (0, 0), (0, -1)),
            ("VALIGN", (0, 0), (0, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("BACKGROUND", (1, 0), (1, -1), COLOR_ACCENT),
            ("TEXTCOLOR", (1, 0), (1, -1), white),
            ("VALIGN", (1, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("LEFTPADDING", (0, 0), (0, -1), 14),
            ("RIGHTPADDING", (0, 0), (0, -1), 14),
        ]))
        return table
    if col_widths is None:
        col_widths = [55 * mm, 115 * mm]
    data = []
    for label, value in rows:
        data.append([
            Paragraph(label, ParagraphStyle("l", fontName="Helvetica-Bold",
                      fontSize=9, textColor=white, leading=12)),
            Paragraph(value, ParagraphStyle("v", fontName="Helvetica",
                      fontSize=10, textColor=COLOR_DARK, leading=13)),
        ])
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), COLOR_ACCENT),
        ("TEXTCOLOR", (0, 0), (0, -1), white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
    ]))
    return table


def repartition_table(title, rows, styles):
    """Tableau de répartition (type MIME, durée, etc.) avec ligne de total."""
    headers = [
        Paragraph(title, styles["TableLabel"]),
        Paragraph("Nombre de fichiers", styles["TableLabel"]),
    ]
    data = [headers]
    total = 0
    for name, count in rows:
        data.append([
            Paragraph(esc(name), styles["TableValue"]),
            Paragraph(str(count), styles["TableValue"]),
        ])
        total += count
    data.append([
        Paragraph("<b>Total</b>", styles["TableValue"]),
        Paragraph(f"<b>{total}</b>", styles["TableValue"]),
    ])
    col_widths = [120 * mm, 50 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, COLOR_BORDER),
        ("BACKGROUND", (0, -1), (-1, -1), COLOR_LIGHT),
        ("LINEABOVE", (0, -1), (-1, -1), 1, COLOR_ACCENT),
    ]
    for i in range(1, len(data) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    return table


def mime_ext_table(rows, styles):
    """Tableau de répartition par couple (type MIME, extension).

    Colonnes : Type MIME | Extension | Nombre de fichiers, avec ligne de total.
    ``rows`` est une liste de dicts {mime, ext, count} déjà triée.
    """
    headers = [
        Paragraph("Type MIME", styles["TableLabel"]),
        Paragraph("Extension", styles["TableLabel"]),
        Paragraph("Nombre de fichiers", styles["TableLabel"]),
    ]
    data = [headers]
    total = 0
    for r in rows:
        mime = r.get("mime", "")
        ext = r.get("ext", "")
        count = int(r.get("count", 0))
        data.append([
            Paragraph(esc(mime), styles["TableValue"]),
            Paragraph(esc(ext) if ext else "—", styles["TableValue"]),
            Paragraph(str(count), styles["TableValue"]),
        ])
        total += count
    data.append([
        Paragraph("<b>Total</b>", styles["TableValue"]),
        Paragraph("", styles["TableValue"]),
        Paragraph(f"<b>{total}</b>", styles["TableValue"]),
    ])
    col_widths = [85 * mm, 45 * mm, 40 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, COLOR_BORDER),
        ("BACKGROUND", (0, -1), (-1, -1), COLOR_LIGHT),
        ("LINEABOVE", (0, -1), (-1, -1), 1, COLOR_ACCENT),
    ]
    for i in range(1, len(data) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    return table


def threats_table(infected_files, styles):
    """Tableau des menaces ClamAV (chemin + signature)."""
    headers = [
        Paragraph("Chemin du fichier", styles["TableLabel"]),
        Paragraph("Signature détectée", styles["TableLabel"]),
    ]
    data = [headers]
    for f in infected_files:
        data.append([
            Paragraph(esc(f["path"]), styles["ThreatPath"]),
            Paragraph(esc(f["signature"]), styles["ThreatSig"]),
        ])
    col_widths = [110 * mm, 60 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, COLOR_BORDER),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    return table


def files_table(files, styles, kind):
    """Tableau forensique compact : une ligne par fichier.

    Colonnes : Chemin (préfixé par le nom de partition) | SHA-256 | Taille |
    Date modif. | Type MIME — ou Extension pour les fichiers bureautiques
    (kind="office") : l'extension (docx, xlsx, odt...) est plus parlante que
    le type MIME, partagé par plusieurs formats. La dernière colonne est
    dimensionnée pour que la valeur tienne sur une seule ligne.
    """
    is_office = kind == "office"
    last_header = "Extension" if is_office else "Type"
    headers = [
        Paragraph("Chemin", styles["TableLabel"]),
        Paragraph("SHA-256", styles["TableLabel"]),
        Paragraph("Taille", styles["TableLabel"]),
        Paragraph("Date modif.", styles["TableLabel"]),
        Paragraph(last_header, styles["TableLabel"]),
    ]
    path_style = ParagraphStyle(
        name="FilePath", fontName="Courier", fontSize=7,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=9)
    hash_style = ParagraphStyle(
        name="FileHash", fontName="Courier", fontSize=7,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=9)
    val_style = ParagraphStyle(
        name="FileVal", fontName="Helvetica", fontSize=7,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=9)
    data = [headers]
    for f in files:
        size = _human_size(int(f.get("size", 0)))
        mtime = _format_mtime(f.get("mtime", ""))
        if is_office:
            last_value = esc(str(f.get("ext", "") or "(inconnue)"))
        else:
            last_value = esc(f.get("mime", ""))
        data.append([
            Paragraph(esc(f.get("path", "")), path_style),
            Paragraph(esc(f.get("sha256", "") or "(échec)"), hash_style),
            Paragraph(size, val_style),
            Paragraph(mtime, val_style),
            Paragraph(last_value, val_style),
        ])
    if is_office:
        # Largeur totale ramenée sous les 170 mm utiles d'A4 (marges 20 mm).
        col_widths = [52 * mm, 54 * mm, 18 * mm, 22 * mm, 20 * mm]
    else:
        col_widths = [56 * mm, 62 * mm, 18 * mm, 22 * mm, 12 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.2, COLOR_BORDER),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    return table


def _human_size(num_bytes):
    """Formate une taille en octets de facon lisible (o, Ko, Mo, Go)."""
    n = float(num_bytes)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            if unit == "o":
                return f"{int(n)} o"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{num_bytes} o"


def _format_mtime(raw):
    """Convertit une date ISO (2026-09-14T08:15:09) en jj/mm/aaaa HH:MM:SS."""
    if not raw:
        return "(non disponible)"
    text = str(raw).strip()
    import re as _re
    m = _re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", text)
    if m:
        return (f"{m.group(3)}/{m.group(2)}/{m.group(1)} "
                f"{m.group(4)}:{m.group(5)}:{m.group(6)}")
    return text


def _resolve_logo(config):
    """Retourne un flowable Image pour le logo, ou None."""
    logo_path = config.get("logo_path")
    if not (logo_path and os.path.isfile(logo_path)):
        return None
    try:
        from PIL import Image as PILImage
        with PILImage.open(logo_path) as img:
            iw, ih = img.size
        max_w_pt = 60 * mm
        max_h_pt = 40 * mm
        ratio = min(max_w_pt / iw, max_h_pt / ih)
        return Image(logo_path, width=iw * ratio, height=ih * ratio)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
#  Page d'accueil commune (identification)
# --------------------------------------------------------------------------- #

def build_front_page(story, styles, config, user, project, date_scan,
                     comment=None):
    """Page d'accueil identique pour tous les rapports : identification."""
    project_display = (project if project and project != "(no-project)"
                       else "(sans projet)")

    entity_rows = []
    entity_rows.append(("Entité",
                        esc(config.get("entity_name", "") or "(non configurée)")))
    if config.get("establishment"):
        entity_rows.append(("Établissement", esc(config["establishment"])))
    if config.get("address"):
        entity_rows.append(("Adresse", esc(config["address"])))
    if config.get("phone"):
        entity_rows.append(("Téléphone", esc(config["phone"])))
    if config.get("email"):
        entity_rows.append(("Email", esc(config["email"])))
    entity_rows.append(("Utilisateur", esc(user or "(non renseigné)")))
    entity_rows.append(("Projet", esc(project_display)))
    if date_scan:
        entity_rows.append(("Date de l'analyse", esc(date_scan)))

    story.append(Paragraph("Identification", styles["SectionTitle"]))
    story.append(info_table(entity_rows, logo=_resolve_logo(config)))

    if comment:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Commentaire", styles["SectionTitle"]))
        comment_style = ParagraphStyle(
            name="Comment", fontName="Helvetica", fontSize=10,
            textColor=COLOR_DARK, alignment=TA_LEFT, leading=15,
        )
        story.append(Paragraph(esc(comment), comment_style))

    story.append(PageBreak())


def build_signature_page(story, styles, user, report_title=""):
    """Page de validation et signature (commune a tous les rapports).

    Le libelle s'adapte au type de rapport via ``report_title`` : pour le scan
    antiviral on conserve la formulation historique, pour les autres analyses
    on parle d'analyse forensique.
    """
    story.append(PageBreak())
    story.append(Paragraph("Validation du rapport", styles["SectionTitle"]))
    if report_title and "antivir" in report_title.lower():
        attestation = (
            "Je soussigné(e), atteste avoir procédé au scan antiviral "
            "documenté dans ce rapport et en valide les résultats."
        )
    else:
        attestation = (
            "Je soussigné(e), atteste avoir procédé à l'analyse "
            "forensique documentée dans ce rapport et en valide les "
            "résultats."
        )
    story.append(Paragraph(attestation, styles["StatusDesc"]))
    story.append(Spacer(1, 40))
    sig_label_style = ParagraphStyle(
        name="SigLabel", fontName="Helvetica-Bold", fontSize=10,
        textColor=COLOR_GREY, alignment=TA_LEFT, leading=13,
    )
    sig_name_style = ParagraphStyle(
        name="SigName", fontName="Helvetica-Bold", fontSize=12,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=15,
    )
    sig_date_style = ParagraphStyle(
        name="SigDate", fontName="Helvetica", fontSize=11,
        textColor=COLOR_DARK, alignment=TA_LEFT, leading=15,
    )
    sig_table = Table([
        [Paragraph("Nom :", sig_label_style),
         Paragraph(esc(user or "(non renseigné)"), sig_name_style)],
        [Paragraph("Date :", sig_label_style),
         Paragraph(datetime.now().strftime("%d/%m/%Y"), sig_date_style)],
    ], colWidths=[35 * mm, 135 * mm])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 60))
    story.append(Paragraph("Signature", sig_label_style))


# --------------------------------------------------------------------------- #
#  Sections de résultats par type d'analyse
# --------------------------------------------------------------------------- #

def _section_images(story, styles, data):
    """Section résultats : analyse des fichiers image."""
    total_files = int(data.get("total_files", 0))
    image_count = int(data.get("image_count", 0))
    types = data.get("types", {})
    exif_ok = int(data.get("exif_ok", 0))
    exif_fail = int(data.get("exif_fail", 0))
    exif_available = bool(data.get("exif_available", False))
    faces_count = int(data.get("faces_count", 0))
    faces_files = data.get("faces_files", [])
    faces_available = data.get("faces_available", False)

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers image détectés", str(image_count)),
    ]))

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if types:
        type_rows = sorted(types.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))

    if faces_available:
        story.append(Paragraph("Détection des visages", styles["SectionTitle"]))
        if faces_count > 0:
            story.append(info_table([("Visages détectés", str(faces_count))]))
            story.append(Spacer(1, 8))
            file_list_style = ParagraphStyle(
                name="FacesList", fontName="Helvetica", fontSize=9,
                textColor=COLOR_DARK, alignment=TA_LEFT, leading=12,
            )
            for f in faces_files[:200]:
                story.append(Paragraph(esc(os.path.basename(f) or f),
                                       file_list_style))
            if len(faces_files) > 200:
                story.append(Paragraph(
                    f"... et {len(faces_files) - 200} autre(s) fichier(s).",
                    file_list_style))
        else:
            story.append(Paragraph(
                "Aucun visage n'a été découvert lors de l'analyse.",
                styles["StatusDesc"]))

    story.append(Paragraph("Métadonnées EXIF", styles["SectionTitle"]))
    if exif_available:
        story.append(info_table([
            ("Fichiers avec EXIF", str(exif_ok)),
            ("Fichiers sans EXIF", str(exif_fail)),
        ]))
    else:
        story.append(Paragraph(
            "exiftool non disponible : extraction EXIF désactivée.",
            styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers image", styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "images"))
    else:
        story.append(Paragraph("Aucun fichier image trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_videos(story, styles, data):
    """Section résultats : analyse des fichiers vidéo."""
    total_files = int(data.get("total_files", 0))
    video_count = int(data.get("video_count", 0))
    types = data.get("types", {})
    duration_ok = int(data.get("duration_ok", 0))
    duration_fail = int(data.get("duration_fail", 0))
    ffprobe_available = bool(data.get("ffprobe_available", False))
    durations = data.get("durations", {})

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers vidéo détectés", str(video_count)),
    ]))

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if types:
        type_rows = sorted(types.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))

    story.append(Paragraph("Métadonnées ffprobe", styles["SectionTitle"]))
    if ffprobe_available:
        story.append(info_table([
            ("Fichiers avec durée extraite", str(duration_ok)),
            ("Fichiers sans durée", str(duration_fail)),
        ]))
    else:
        story.append(Paragraph(
            "ffprobe non disponible : extraction durée/résolution désactivée.",
            styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers vidéo", styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "videos"))
    else:
        story.append(Paragraph("Aucun fichier vidéo trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_audio(story, styles, data):
    """Section résultats : analyse des fichiers audio."""
    total_files = int(data.get("total_files", 0))
    audio_count = int(data.get("audio_count", 0))
    types = data.get("types", {})
    duration_ok = int(data.get("duration_ok", 0))
    duration_fail = int(data.get("duration_fail", 0))
    ffprobe_available = bool(data.get("ffprobe_available", False))
    durations = data.get("durations", {})

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers audio détectés", str(audio_count)),
    ]))

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if types:
        type_rows = sorted(types.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))

    story.append(Paragraph("Métadonnées ffprobe", styles["SectionTitle"]))
    if ffprobe_available:
        story.append(info_table([
            ("Fichiers avec durée extraite", str(duration_ok)),
            ("Fichiers sans durée", str(duration_fail)),
        ]))
    else:
        story.append(Paragraph(
            "ffprobe non disponible : extraction durée/débit désactivée.",
            styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers audio", styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "audio"))
    else:
        story.append(Paragraph("Aucun fichier audio trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_office(story, styles, data):
    """Section résultats : analyse des fichiers bureautiques."""
    total_files = int(data.get("total_files", 0))
    office_count = int(data.get("office_count", 0))
    categories = data.get("categories", {})
    formats = data.get("formats", {})

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers bureautiques détectés", str(office_count)),
    ]))

    # Statistiques par catégorie
    cat_labels = {
        "document": "Document",
        "spreadsheet": "Tableur",
        "presentation": "Présentation",
        "pdf": "PDF",
        "rtf": "RTF",
    }
    if categories:
        story.append(Paragraph("Répartition par catégorie", styles["SectionTitle"]))
        cat_rows = [(cat_labels.get(k, k), int(v))
                    for k, v in sorted(categories.items(),
                                       key=lambda x: -int(x[1]))]
        story.append(repartition_table("Catégorie", cat_rows, styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))

    # Statistiques par format (extension)
    if formats:
        story.append(Paragraph("Répartition par format", styles["SectionTitle"]))
        fmt_rows = [(k, int(v)) for k, v in sorted(formats.items(),
                                                   key=lambda x: -int(x[1]))]
        story.append(repartition_table("Format", fmt_rows, styles))
    else:
        story.append(Paragraph("Aucune donnée de format disponible.",
                               styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers bureautiques",
                               styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et extension de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "office"))
    else:
        story.append(Paragraph("Aucun fichier bureautique trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_archives(story, styles, data):
    """Section résultats : analyse des fichiers archives."""
    total_files = int(data.get("total_files", 0))
    archive_count = int(data.get("archive_count", 0))
    types = data.get("types", {})
    protected_count = int(data.get("protected_count", 0))
    protected_available = bool(data.get("protected_available", False))

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers archives détectés", str(archive_count)),
    ]))

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if types:
        type_rows = sorted(types.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))

    story.append(Paragraph("Archives protégées par mot de passe",
                           styles["SectionTitle"]))
    if protected_available:
        story.append(info_table([
            ("Archives protégées détectées", str(protected_count)),
        ]))
    else:
        story.append(Paragraph(
            "7za non disponible : détection de la protection par mot de "
            "passe désactivée.",
            styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers archives",
                               styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "archives"))
    else:
        story.append(Paragraph("Aucun fichier archive trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_crypto(story, styles, data):
    """Section résultats : analyse des fichiers verrouillés (crypto)."""
    total_files = int(data.get("total_files", 0))
    candidate_count = int(data.get("candidate_count", 0))
    locked_count = int(data.get("locked_count", 0))
    types = data.get("types", {})
    lock_method_available = bool(data.get("lock_method_available", False))

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers candidats (archives + documents)", str(candidate_count)),
        ("Fichiers verrouillés détectés", str(locked_count)),
    ]))

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if types:
        type_rows = sorted(types.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucun fichier verrouillé : aucune répartition.",
                               styles["StatusDesc"]))

    story.append(Paragraph("Méthode de détection", styles["SectionTitle"]))
    if lock_method_available:
        story.append(info_table([
            ("Outil utilisé", "7za (polyvalent) + file (fallback)"),
        ]))
    else:
        story.append(Paragraph(
            "7za non disponible : détection limitée à la signature de file.",
            styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers verrouillés",
                               styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier confirmé comme "
            "verrouillé (protégé par mot de passe ou chiffré).",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "crypto"))
    else:
        story.append(Paragraph("Aucun fichier verrouillé trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_entropy(story, styles, data):
    """Section résultats : analyse des fichiers à forte entropie."""
    total_files = int(data.get("total_files", 0))
    candidate_count = int(data.get("candidate_count", 0))
    entropy_count = int(data.get("entropy_count", 0))
    entropy_available = bool(data.get("entropy_available", False))
    threshold = int(data.get("threshold", 9800))
    min_size = int(data.get("min_size", 4194304))
    aligned_count = int(data.get("aligned_count", 0))

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Candidats (octet-stream >= seuil)", str(candidate_count)),
        ("Fichiers à forte entropie", str(entropy_count)),
    ]))

    story.append(Paragraph("Paramètres de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Seuil d'entropie",
         f"{threshold // 100}.{threshold % 100:02d}%"),
        ("Taille minimale", _human_size(min_size)),
        ("Fichiers alignés (secteur 512 o)", str(aligned_count)),
    ]))

    story.append(Paragraph("Méthode de calcul", styles["SectionTitle"]))
    if entropy_available:
        story.append(info_table([
            ("Outil utilisé", "zstd (taux de compression)"),
        ]))
    else:
        story.append(Paragraph(
            "zstd non disponible : calcul d'entropie désactivé.",
            styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers à forte entropie",
                               styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "entropy"))
    else:
        story.append(Paragraph("Aucun fichier à forte entropie trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _section_formataudit(story, styles, data):
    """Section résultats : audit de format ciblé (mismatch + entropie)."""
    total_targets = int(data.get("total_targets", 0))
    audited = int(data.get("audited", 0))
    skipped = int(data.get("skipped", 0))
    mismatch_count = int(data.get("mismatch_count", 0))
    high_entropy_count = int(data.get("high_entropy_count", 0))
    binwalk_hits = int(data.get("binwalk_hits", 0))
    binwalk_available = bool(data.get("binwalk_available", False))
    signatures_active = int(data.get("signatures_active", 0))
    files = data.get("files", [])

    story.append(Paragraph("Résultat de l'audit", styles["SectionTitle"]))
    rows = [
        ("Fichiers ciblés par l'audit", str(total_targets)),
        ("Extensions trompeuses", str(mismatch_count)),
        ("Fichiers à forte entropie", str(high_entropy_count)),
    ]
    if skipped:
        rows.append(("Fichiers non audités (limite atteinte)", str(skipped)))
    story.append(info_table(rows))

    story.append(Paragraph("Méthode d'audit", styles["SectionTitle"]))
    method_rows = [
        ("Signatures forensiques locales", str(signatures_active)),
        ("Cibles", "extensions trompeuses + octet-stream"),
        ("Seuil de forte entropie", ">= 7.50 (Shannon, échantillon 4 Mo)"),
    ]
    if binwalk_available:
        method_rows.append(("binwalk", "installé — scan ciblé actif"))
    else:
        method_rows.append(
            ("binwalk", "non installé — signatures locales uniquement"))
    story.append(info_table(method_rows))
    story.append(Paragraph(
        "Chaque fichier ciblé est analysé par contenu : entropie (données "
        "chiffrées ou compressées qui se déguisent), signatures forensiques "
        "locales (identification du vrai format indépendamment du nom) et "
        "binwalk ciblé (contenu embarqué ou concaténé après la fin "
        "officielle du fichier).",
        styles["StatusDesc"]))

    if files:
        story.append(PageBreak())
        story.append(Paragraph("Fichiers audités", styles["SectionTitle"]))
        story.append(Paragraph(
            "Fichiers dont l'extension ment sur le contenu ou présentant "
            "des données à forte entropie. Priorité d'analyse pour "
            "l'opérateur.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        rows = [("Chemin relatif", "Ext.", "Format réel",
                 "Entropie", "Signatures trouvées")]
        for f in files:
            rel = f.get("path", "")
            if rel.startswith("/investigation/"):
                rel = rel[len("/investigation/"):]
            ext = os.path.splitext(rel)[1].lstrip(".") if rel else ""
            sigs = ", ".join(f.get("signatures", []))
            marks = []
            if f.get("extension_mismatch"):
                marks.append("extension trompeuse")
            if f.get("high_entropy"):
                marks.append("forte entropie")
            if sigs:
                marks.append(sigs)
            rows.append((esc(rel), esc(ext), esc(f.get("mime_type", "")),
                         f"{float(f.get('entropy', 0)):.2f}",
                         esc(" ; ".join(marks))))
        col_widths = [62 * mm, 12 * mm, 34 * mm, 16 * mm, 56 * mm]
        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [white, COLOR_ROW_ALT]),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph(
            "Aucun fichier suspect détecté : aucune extension trompeuse "
            "et aucun octet-stream à forte entropie dans l'index du "
            "recensement.",
            styles["StatusDesc"]))


def _section_bigfiles(story, styles, data):
    """Section résultats : analyse des fichiers volumineux."""
    total_files = int(data.get("total_files", 0))
    bigfile_count = int(data.get("bigfile_count", 0))
    sparse_count = int(data.get("sparse_count", 0))
    min_size_mb = int(data.get("min_size_mb", 512))
    types = data.get("types", {})

    story.append(Paragraph("Résultat de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Fichiers totaux analysés", str(total_files)),
        ("Fichiers volumineux détectés", str(bigfile_count)),
    ]))

    story.append(Paragraph("Paramètres de l'analyse", styles["SectionTitle"]))
    story.append(info_table([
        ("Taille minimale", f"{min_size_mb} Mo"),
        ("Fichiers creux (octets nuls)", str(sparse_count)),
        ("Fichiers non creux", str(bigfile_count - sparse_count)),
    ]))

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if types:
        type_rows = sorted(types.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))

    files = data.get("files", [])
    if files:
        story.append(PageBreak())
        story.append(Paragraph("Liste des fichiers volumineux",
                               styles["SectionTitle"]))
        story.append(Paragraph(
            "Chemin de partition, signature SHA-256, taille, date de "
            "modification et type MIME de chaque fichier analysé.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        story.append(files_table(files, styles, "bigfiles"))
    else:
        story.append(Paragraph("Aucun fichier volumineux trouvé lors de l'analyse.",
                               styles["StatusDesc"]))


def _format_bytes(size):
    """Formate une taille en octets en notation lisible (Ko/Mo/Go)."""
    size = int(size)
    if size < 1024:
        return f"{size} o"
    for unit in ("Ko", "Mo", "Go", "To"):
        size /= 1024.0
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} Po"


def _section_custody(story, styles, data):
    """Section r\u00e9sultats : cha\u00eene de custody en tableau chronologique."""
    entries = data.get("entries", [])
    story.append(Paragraph("R\u00e9sultat de la tra\u00e7abilit\u00e9",
                          styles["SectionTitle"]))
    story.append(Paragraph(
        "Journal chronologique des actions de la chasse (montage, "
        "analyses, d\u00e9montage). Chaque action est horodat\u00e9e et "
        "associ\u00e9e \u00e0 l'op\u00e9rateur.",
        styles["StatusDesc"]))
    story.append(Spacer(1, 10))
    if not entries:
        story.append(Paragraph(
            "Aucun \u00e9v\u00e9nement de custody enregistr\u00e9.",
            styles["StatusDesc"]))
        return
    headers = [
        Paragraph("Horodatage", styles["TableLabel"]),
        Paragraph("Op\u00e9rateur", styles["TableLabel"]),
        Paragraph("Action", styles["TableLabel"]),
        Paragraph("Statut", styles["TableLabel"]),
        Paragraph("D\u00e9tail", styles["TableLabel"]),
    ]
    ts_style = ParagraphStyle(
        name="CustodyTs", fontName="Courier", fontSize=7.5,
        textColor=COLOR_DARK, leading=9)
    cell_style = ParagraphStyle(
        name="CustodyCell", fontName="Helvetica", fontSize=8,
        textColor=COLOR_DARK, leading=10)
    msg_style = ParagraphStyle(
        name="CustodyMsg", fontName="Helvetica", fontSize=8,
        textColor=COLOR_DARK, leading=10)
    status_ok = ParagraphStyle(
        name="CustodyOk", fontName="Helvetica-Bold", fontSize=8,
        textColor=COLOR_SUCCESS, leading=10)
    status_err = ParagraphStyle(
        name="CustodyErr", fontName="Helvetica-Bold", fontSize=8,
        textColor=COLOR_DANGER, leading=10)
    data_rows = [headers]
    for e in entries:
        status = str(e.get("status", ""))
        st_style = status_err if status.lower() in ("error", "erreur") \
            else status_ok
        data_rows.append([
            Paragraph(esc(_format_mtime(str(e.get("timestamp", "")))),
                      ts_style),
            Paragraph(esc(str(e.get("user", ""))), cell_style),
            Paragraph(esc(str(e.get("action", ""))), cell_style),
            Paragraph(esc(status), st_style),
            Paragraph(esc(str(e.get("message", ""))), msg_style),
        ])
    col_widths = [30 * mm, 25 * mm, 30 * mm, 18 * mm, 67 * mm]
    table = Table(data_rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, COLOR_BORDER),
    ]
    for i in range(1, len(data_rows)):
        if i % 2 == 0:
            style_cmds.append(
                ("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)


def _section_census(story, styles, data):
    """Section résultats : recensement et dédoublonnage des fichiers."""
    total_files = int(data.get("total_files", 0))
    duplicate_count = int(data.get("duplicate_count", 0))
    duplicate_groups = int(data.get("duplicate_groups", 0))
    safe_filtered_count = int(data.get("safe_filtered_count", 0))
    checksafe_active = bool(data.get("checksafe_active", False))
    checksafe_base_name = bool(data.get("checksafe_base_name", False))
    checksafe_base_hash = bool(data.get("checksafe_base_hash", False))
    mime_stats = data.get("mime_stats", {})
    mime_ext_stats = data.get("mime_ext_stats", [])
    dup_doc = data.get("dup_doc", [])
    mismatch_count = int(data.get("mismatch_count", 0))
    mismatch_files = data.get("mismatch_files", [])
    db_path = data.get("db_path", "")
    db_sha256 = data.get("db_sha256", "")
    tsv_path = data.get("tsv_path", "")

    story.append(Paragraph("Résultat du recensement", styles["SectionTitle"]))
    result_rows = [
        ("Fichiers recensés", str(total_files)),
        ("Doublons marqués (conservés)", str(duplicate_count)),
        ("Groupes de doublons", str(duplicate_groups)),
        ("Fichiers sains filtrés (checksafe)", str(safe_filtered_count)),
    ]
    story.append(info_table(result_rows))

    story.append(Paragraph("Filtrage checksafe", styles["SectionTitle"]))
    if checksafe_active:
        bases = []
        if checksafe_base_name:
            bases.append("base de noms (files.safe.name)")
        if checksafe_base_hash:
            bases.append("base de signatures (files.safe.hash)")
        story.append(info_table([
            ("Base(s) externe(s) utilisée(s)", esc(" / ".join(bases))),
            ("Fichiers retirés comme sains", str(safe_filtered_count)),
        ]))
    else:
        story.append(Paragraph(
            "Aucune base externe trouvée dans /stockage : checksafe ne filtre "
            "rien. C'est le comportement attendu et documenté dans le rapport.",
            styles["StatusDesc"]))

    story.append(Paragraph("Extensions trompeuses", styles["SectionTitle"]))
    if mismatch_count > 0 and mismatch_files:
        story.append(Paragraph(
            f"{mismatch_count} fichier(s) dont l'extension ne correspond pas "
            "au format réel du contenu (ex. un fichier .jpg qui est en "
            "réalité un exécutable). Ces fichiers sont des cibles "
            "prioritaires pour l'analyse de contenu.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        rows = [("Chemin relatif", "Extension", "Format réel",
                 "Format attendu")]
        for m in mismatch_files:
            rows.append((esc(m.get("path", "")),
                         esc(m.get("extension", "")),
                         esc(m.get("mime_type", "")),
                         esc(m.get("expected_format", ""))))
        col_widths = [70 * mm, 18 * mm, 47 * mm, 45 * mm]
        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [white, COLOR_ROW_ALT]),
        ]))
        story.append(tbl)
        if mismatch_count > len(mismatch_files):
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"Liste limitée aux {len(mismatch_files)} premiers fichiers ; "
                f"{mismatch_count - len(mismatch_files)} autre(s) dans la base "
                "SQLite et l'export TSV du projet.",
                styles["StatusDesc"]))
    elif mismatch_count > 0:
        story.append(Paragraph(
            f"{mismatch_count} fichier(s) avec extension trompeuse détecté(s) "
            "(liste détaillée non transmise).",
            styles["StatusDesc"]))
    else:
        story.append(Paragraph(
            "Aucune extension trompeuse détectée : pour chaque fichier dont "
            "l'extension est connue, le format réel du contenu correspond à "
            "l'extension annoncée.",
            styles["StatusDesc"]))
    story.append(PageBreak())

    story.append(Paragraph("Répartition par type MIME", styles["SectionTitle"]))
    if mime_ext_stats:
        story.append(mime_ext_table(mime_ext_stats, styles))
    elif mime_stats:
        type_rows = sorted(mime_stats.items(), key=lambda x: -int(x[1]))
        story.append(repartition_table("Type MIME",
                                       [(k, int(v)) for k, v in type_rows],
                                       styles))
    else:
        story.append(Paragraph("Aucune donnée de répartition disponible.",
                               styles["StatusDesc"]))
    story.append(PageBreak())

    story.append(Paragraph("Base SQLite (livrable forensique)",
                           styles["SectionTitle"]))
    if db_path:
        sig_rows = [
            ("Chemin de la base", esc(db_path)),
            ("Signature SHA-256", esc(db_sha256 or "(échec)")),
        ]
        if tsv_path:
            sig_rows.append(("Export TSV (régénérable)", esc(tsv_path)))
        story.append(info_table(sig_rows))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "L'inventaire détaillé de chaque fichier (chemin relatif, hash "
            "SHA-256, taille, dates mtime/atime/ctime/btime, type MIME, "
            "extension, mode/uid/gid, marquage des doublons et filtrage "
            "checksafe) est stocké dans la base SQLite et l'export TSV du "
            "dossier du projet, livrables forensiques signés ci-dessus.",
            styles["StatusDesc"]))
    else:
        story.append(Paragraph(
            "Aucun projet actif : la base SQLite et l'export TSV n'ont pas "
            "été écrits. L'inventaire détaillé de chaque fichier (chemin, hash "
            "SHA-256, taille, dates, type MIME, marquage des doublons) n'est "
            "donc pas disponible ; relancez le recensement avec un projet "
            "actif pour générer la base SQLite.",
            styles["StatusDesc"]))

    # Résumé concis des doublons : sur un gros disque, lister chaque groupe
    # de doublons multiplie les pages du rapport. On n'indique que les
    # compteurs ; le détail (groupes, emplacements) reste dans la base
    # SQLite et l'export TSV du projet, livrables forensiques signés.
    dup_summary = data.get("dup_doc")
    if isinstance(dup_summary, dict) and (
            int(dup_summary.get("duplicate_groups", 0)) > 0
            or int(dup_summary.get("duplicate_files", 0)) > 0):
        story.append(Paragraph("Doublons (résumé)", styles["SectionTitle"]))
        story.append(Paragraph(
            "Chaque fichier dupliqué est conservé dans l'inventaire. Le "
            "détail des groupes et de leurs emplacements figure dans la base "
            "SQLite et l'export TSV du dossier du projet.",
            styles["StatusDesc"]))
        story.append(info_table([
            ("Groupes de doublons",
             str(int(dup_summary.get("duplicate_groups", 0)))),
            ("Fichiers impliqués",
             str(int(dup_summary.get("duplicate_files", 0)))),
            ("Copies redondantes",
             str(int(dup_summary.get("redundant_copies", 0)))),
            ("Volume redondant",
             _format_bytes(int(dup_summary.get("redundant_bytes", 0)))),
        ]))

    # Répartition par dossier : arborescence complète (chemin complet
    # affiché), tri alphabétique, fichiers cachés inclus (find -type f ne
    # filtre pas les fichiers commençant par un point).
    dir_stats = data.get("dir_stats", [])
    if dir_stats:
        story.append(PageBreak())
        story.append(Paragraph("Fichiers par dossier", styles["SectionTitle"]))
        story.append(Paragraph(
            "Arborescence des dossiers contenant au moins un fichier, avec "
            "le nombre de fichiers de chaque dossier (fichiers cachés "
            "inclus). Les dossiers sont classés par ordre alphabétique et "
            "affichés avec leur chemin complet. Le comptage est direct : "
            "les fichiers des sous-dossiers ne sont pas recomptés dans le "
            "dossier parent.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        headers = [
            Paragraph("Dossier", styles["TableLabel"]),
            Paragraph("Fichiers", styles["TableLabel"]),
        ]
        table_data = [headers]
        dir_style = ParagraphStyle(
            name="DirPath", fontName="Courier", fontSize=8,
            textColor=COLOR_DARK, alignment=TA_LEFT, leading=10)
        for entry in dir_stats:
            if entry["dir"] == ".":
                shown = ". (racine de l'analyse)"
            else:
                shown = entry["dir"]
            table_data.append([
                Paragraph(esc(shown), dir_style),
                Paragraph(str(int(entry["count"])), styles["TableValue"]),
            ])
        table_data.append([
            Paragraph("<b>Total</b>", styles["TableValue"]),
            Paragraph(f"<b>{total_files}</b>", styles["TableValue"]),
        ])
        col_widths = [140 * mm, 30 * mm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
            ("LINEBELOW", (0, 1), (-1, -2), 0.3, COLOR_BORDER),
            ("BACKGROUND", (0, -1), (-1, -1), COLOR_LIGHT),
            ("LINEABOVE", (0, -1), (-1, -1), 1, COLOR_ACCENT),
        ]
        for i in range(1, len(table_data) - 1):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
        table.setStyle(TableStyle(style_cmds))
        story.append(table)


def _parse_clamav_log(log_path):
    """Extrait le résumé d'un log clamscan."""
    info = {"infected": "0", "scanned": "0", "scanned_dirs": "",
            "engine": "", "known_viruses": "", "data_scanned": "",
            "time": "", "start_date": "", "end_date": "",
            "infected_files": []}
    if not log_path or not os.path.exists(log_path):
        return info
    # Nom du dossier scanné déduit du nom de fichier clamav_<target>_<stamp>.log
    base = os.path.basename(log_path)
    m = re.match(r"clamav_(.*)_\d{8}_\d{6}\.log$", base)
    if m:
        info["target"] = m.group(1)
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return info
    patterns = {
        "scanned": r"Scanned files:\s*(\d+)",
        "scanned_dirs": r"Scanned directories:\s*(\d+)",
        "infected": r"Infected files:\s*(\d+)",
        "engine": r"Engine version:\s*([^\n]+)",
        "known_viruses": r"Known viruses:\s*(\d+)",
        "data_scanned": r"Data scanned:\s*([^\n]+)",
        "time": r"Time:\s*([^\n]+)",
        "start_date": r"Start Date:\s*([^\n]+)",
        "end_date": r"End Date:\s*([^\n]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            info[key] = m.group(1).strip()
    for line in content.splitlines():
        stripped = line.strip()
        if " FOUND" in stripped:
            parts = stripped.rsplit(":", 1)
            if len(parts) == 2:
                filepath = parts[0]
                signature = parts[1].replace(" FOUND", "").strip()
            else:
                filepath = stripped
                signature = "Inconnu"
            info["infected_files"].append(
                {"path": filepath, "signature": signature})
    return info


def _format_clamav_date(raw):
    """Convertit une date ClamAV (2026:09:10 16:55:41) en jj/mm/aaaa à HH:MM:SS."""
    if not raw:
        return "(non disponible)"
    text = str(raw).strip()
    m = re.match(r"(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", text)
    if m:
        return (f"{m.group(3)}/{m.group(2)}/{m.group(1)} à "
                f"{m.group(4)}:{m.group(5)}:{m.group(6)}")
    m = re.match(r"(\d{4}):(\d{2}):(\d{2})", text)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return text


def _section_usbhid(story, styles, data):
    """Section résultats : triage USB anti-Rubber Ducky (interfaces HID)."""
    baseline_count = int(data.get("baseline_count", 0))
    after_count = int(data.get("after_count", 0))
    new_count = int(data.get("new_count", 0))
    hid_count = int(data.get("hid_count", 0))
    protected_count = int(data.get("protected_count", 0))
    blocked_count = int(data.get("blocked_count", 0))
    block_fail_count = int(data.get("block_fail_count", 0))
    blacklisted_count = int(data.get("blacklisted_count", 0))
    devices = data.get("devices", [])

    story.append(Paragraph("Résultat du triage", styles["SectionTitle"]))
    story.append(info_table([
        ("Périphériques USB avant branchement (baseline)", str(baseline_count)),
        ("Périphériques USB après branchement", str(after_count)),
        ("Nouveaux périphériques détectés", str(new_count)),
        ("Périphériques avec interface clavier (HID)", str(hid_count)),
        ("Protégés par l'utilisateur (frappes actives)", str(protected_count)),
        ("Frappes clavier bloquées (driver usbhid délié)", str(blocked_count)),
        ("Échecs de blocage", str(block_fail_count)),
        ("Périphériques blacklistés bloqués", str(blacklisted_count)),
    ]))

    if hid_count > 0:
        story.append(Spacer(1, 10))
        alert_style = ParagraphStyle(
            name="HidAlert", fontName="Helvetica-Bold", fontSize=12,
            textColor=COLOR_DANGER, leading=16)
        story.append(Paragraph(
            "⚠ ALERTE : {} périphérique(s) se présentent avec une interface "
            "clavier (HID). Un périphérique de stockage légitime ne se "
            "présente pas en clavier : ce comportement est caractéristique "
            "d'un Rubber Ducky ou d'un périphérique malveillant. Le(s) "
            "périphérique(s) concerné(s) n'ont PAS été proposés au montage "
            "et leurs frappes ont été bloquées par déliaison du driver "
            "usbhid.".format(hid_count),
            alert_style))
        story.append(Spacer(1, 10))

    if protected_count > 0:
        story.append(Spacer(1, 10))
        ok_style = ParagraphStyle(
            name="ProtectedOk", fontName="Helvetica-Bold", fontSize=11,
            textColor=COLOR_SUCCESS, leading=15)
        story.append(Paragraph(
            "✔ {} périphérique(s) clavier ont été PROTÉGÉS par "
            "l'analyste (choix « P ») : il s'agissait de périphériques de "
            "travail rebranchés pendant le triage. Leurs frappes restent "
            "actives et ils restent utilisables.".format(protected_count),
            ok_style))
        story.append(Spacer(1, 10))

    if devices:
        story.append(Paragraph("Périphériques apparus lors du branchement",
                                styles["SectionTitle"]))
        story.append(Paragraph(
            "Descripteurs USB de chaque périphérique détecté entre la "
            "baseline et le scan post-branchement. La colonne « Interface "
            "clavier » indique si le périphérique expose une interface "
            "HID de sous-classe clavier.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 6))
        headers = [Paragraph(h, styles["TableLabel"]) for h in (
            "Fabricant", "Produit", "VID:PID", "N° de série",
            "Interface clavier", "Statut")]
        val_style = ParagraphStyle(
            name="HidVal", fontName="Helvetica", fontSize=8,
            textColor=COLOR_DARK, leading=10)
        key_style = ParagraphStyle(
            name="HidKey", fontName="Courier", fontSize=8,
            textColor=COLOR_DARK, leading=10)
        rows = [headers]
        for dev in devices:
            is_hid = bool(dev.get("hid", False))
            is_protected = bool(dev.get("protected", False))
            is_blacklisted = bool(dev.get("blacklisted", False))
            if is_blacklisted:
                status_text = "Blacklisté — bloqué"
            elif is_hid and is_protected:
                status_text = "Clavier — protégé par l'analyste"
            elif is_hid:
                status_text = "Clavier — frappes bloquées"
            else:
                status_text = "Stockage"
            rows.append([
                Paragraph(esc(dev.get("manufacturer", "") or "(inconnu)"), val_style),
                Paragraph(esc(dev.get("product", "") or "(inconnu)"), val_style),
                Paragraph(esc("{}:{}".format(dev.get("vid", "?"),
                                             dev.get("pid", "?"))), key_style),
                Paragraph(esc(dev.get("serial", "") or "(absent)"), key_style),
                Paragraph("OUI — clavier détecté" if is_hid else "Non",
                          val_style),
                Paragraph(status_text, val_style),
            ])
        table = Table(rows, colWidths=[40 * mm, 40 * mm, 22 * mm,
                                       30 * mm, 20 * mm, 18 * mm], repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ACCENT),
            ("LINEBELOW", (0, 1), (-1, -1), 0.2, COLOR_BORDER),
        ]
        for i, dev in enumerate(devices, start=1):
            if bool(dev.get("blacklisted", False)) or bool(dev.get("hid", False)):
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_DANGER_BG))
            elif i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))
        table.setStyle(TableStyle(style_cmds))
        story.append(table)
    else:
        story.append(Paragraph(
            "Aucun nouveau périphérique USB n'a été détecté entre la "
            "baseline et le scan post-branchement.",
            styles["StatusDesc"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Procédure de triage", styles["SectionTitle"]))
    story.append(Paragraph(
        "La procédure oppose deux instantanés de l'état USB du poste "
        "d'analyse : un premier scan effectué périphériques débranchés "
        "(baseline), puis un second scan effectué après le branchement des "
        "périphériques à analyser. Tout périphérique apparu entre les deux "
        "est examiné au niveau de ses descripteurs USB. Une interface de "
        "classe HID (bInterfaceClass = 03) de sous-classe clavier "
        "(bInterfaceSubClass = 01) sur un périphérique censé être un "
        "stockage est l'indicateur d'un périphérique de type Rubber Ducky : "
        "ses frappes sont bloquées (déliaison du driver usbhid) et il n'est "
        "pas proposé au montage.",
        styles["StatusDesc"]))


def _section_clamav(story, styles, log_paths, action, options):
    """Section résultats : scan antivirus ClamAV (un ou plusieurs dossiers).

    ``log_paths`` est une liste de chemins de journaux clamscan. Quand elle
    contient plusieurs dossiers, un résumé global consolidé est produit (total
    scanné / infecté) suivi d'un détail par dossier puis des menaces.
    """
    if isinstance(log_paths, str):
        log_paths = [log_paths]
    summaries = [_parse_clamav_log(p) for p in log_paths]
    summaries = [s for s in summaries if s["scanned"] or s["infected"]
                 or s["infected_files"]]
    if not summaries:
        summaries = [_parse_clamav_log(log_paths[0] if log_paths else "")]

    total_scanned = 0
    total_infected = 0
    all_infected = []
    for s in summaries:
        try:
            total_scanned += int(s["scanned"] or "0")
        except ValueError:
            pass
        try:
            total_infected += int(s["infected"] or "0")
        except ValueError:
            pass
        for f in s["infected_files"]:
            entry = dict(f)
            entry["target"] = s.get("target", "")
            all_infected.append(entry)
    is_clean = total_infected == 0
    multi = len(summaries) > 1

    if is_clean:
        status_box = Table([[
            Paragraph("AUCUNE MENACE DÉTECTÉE", styles["StatusBig"])
        ]], colWidths=[170 * mm])
        status_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_SUCCESS_BG),
            ("BOX", (0, 0), (-1, -1), 2, COLOR_SUCCESS),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(status_box)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"Le scan de {total_scanned} fichier(s) n'a révélé aucune "
            f"infection. Le périphérique analysé est considéré comme sain.",
            styles["StatusDesc"]))
    else:
        status_box = Table([[
            Paragraph(f"{total_infected} MENACE(S) DÉTECTÉE(S)",
                      styles["StatusBigDanger"])
        ]], colWidths=[170 * mm])
        status_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_DANGER_BG),
            ("BOX", (0, 0), (-1, -1), 2, COLOR_DANGER),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(status_box)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"Le scan de {total_scanned} fichier(s) a détecté "
            f"{total_infected} fichier(s) infecté(s). Le détail des menaces "
            f"est présenté ci-dessous.",
            styles["StatusDesc"]))
    story.append(Spacer(1, 18))
    story.append(Paragraph("Résultat du scan", styles["SectionTitle"]))
    result_rows = [
        ("Statut", f'<b><font color="{("#27ae60" if is_clean else "#c0392b")}">'
         f'{("SAIN" if is_clean else "INFECTÉ")}</font></b>'),
        ("Dossiers analysés", str(len(summaries))),
        ("Fichiers scannés", str(total_scanned)),
        ("Fichiers infectés", str(total_infected)),
    ]
    ref = summaries[0]
    total_dirs = 0
    for s in summaries:
        try:
            total_dirs += int(s.get("scanned_dirs", "") or "0")
        except ValueError:
            pass
    if total_dirs:
        result_rows.append(("Dossiers scannés (total)", str(total_dirs)))
    total_data = ref.get("data_scanned", "")
    if total_data and not multi:
        result_rows.append(("Données analysées", esc(total_data)))
    if ref.get("time") and not multi:
        result_rows.append(("Durée du scan", esc(ref["time"])))
    story.append(info_table(result_rows))
    story.append(Paragraph("Configuration du scan", styles["SectionTitle"]))
    story.append(info_table([
        ("Action sur infectés", esc(action or "aucune")),
        ("Options clamscan", esc(options or "défaut")),
    ]))
    story.append(Paragraph("Moteur antivirus", styles["SectionTitle"]))
    engine_rows = []
    if ref["engine"]:
        engine_rows.append(("Version ClamAV", esc(ref["engine"])))
    if ref["known_viruses"]:
        engine_rows.append(("Signatures connues", esc(ref["known_viruses"])))
    if ref["start_date"]:
        engine_rows.append(("Début du scan",
                            esc(_format_clamav_date(ref["start_date"]))))
    if ref["end_date"]:
        engine_rows.append(("Fin du scan",
                            esc(_format_clamav_date(ref["end_date"]))))
    if engine_rows:
        story.append(info_table(engine_rows))

    # --- Détail par dossier (uniquement si plusieurs dossiers scannés) ---
    if multi:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Résultat par dossier scanné",
                               styles["SectionTitle"]))
        rows = [("Dossier", "Fichiers scannés", "Fichiers infectés")]
        for s in summaries:
            try:
                sc = int(s["scanned"] or "0")
            except ValueError:
                sc = 0
            try:
                ic = int(s["infected"] or "0")
            except ValueError:
                ic = 0
            rows.append((esc(s.get("target") or "?"), str(sc), str(ic)))
        col_widths = [85 * mm, 45 * mm, 40 * mm]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [white, COLOR_ROW_ALT]),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    if all_infected:
        story.append(PageBreak())
        story.append(Paragraph("Détail des menaces détectées",
                               styles["SectionTitle"]))
        story.append(Paragraph(
            f"{total_infected} fichier(s) infecté(s) ont été identifiés "
            f"lors du scan. Le tableau ci-dessous présente le chemin de "
            f"chaque fichier et la signature du malware détecté.",
            styles["StatusDesc"]))
        story.append(Spacer(1, 12))
        story.append(threats_table(all_infected, styles))
    return {"summaries": summaries, "scanned_count": total_scanned,
            "infected_count": total_infected, "is_clean": is_clean}


# --------------------------------------------------------------------------- #
#  Assemblage du rapport
# --------------------------------------------------------------------------- #

_SECTION_DISPATCH = {
    "usbhid": _section_usbhid,
    "images": _section_images,
    "videos": _section_videos,
    "audio": _section_audio,
    "office": _section_office,
    "archives": _section_archives,
    "crypto": _section_crypto,
    "entropy": _section_entropy,
    "bigfiles": _section_bigfiles,
    "census": _section_census,
    "formataudit": _section_formataudit,
    "custody": _section_custody,
}


def build_multi_report(sections, user, project, out_dir, sys_config=None,
                       comment="", fname_prefix=""):
    """Assemble un rapport consolidé multi-analyses en un seul PDF.

    ``sections`` est une liste de tuples ``(kind, source_path, status)`` :
      - kind : identifiant de rapport (images, videos, ..., clamav, census).
      - source_path : chemin du JSON de résultat (ou du log ClamAV).
      - status : "ok" si l'analyse a réussi, "error" sinon.

    Structure : page d'accueil commune → sommaire → une section par analyse
    (avec PageBreak) → page de signature.
    """
    if sys_config is None:
        sys_config = load_system_config()

    styles = build_styles()
    story = []
    meta = REPORT_META["multi"]

    story.append(Paragraph(meta["title"], styles["ReportTitle"]))
    story.append(Paragraph(
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}",
        styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=COLOR_ACCENT, spaceAfter=16))

    # --- Date d'analyse (première section disponible) ---
    date_scan = ""
    for kind, source_path, _status in sections:
        if kind == "clamav":
            logs = source_path if isinstance(source_path, list) else [source_path]
            logs = [p for p in logs if p]
            if logs:
                clamav_summary = _parse_clamav_log(logs[0])
                date_scan = _format_clamav_date(clamav_summary["start_date"])
                break
        else:
            try:
                with open(source_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                date_scan = data.get("date", "")
                break
            except (OSError, json.JSONDecodeError):
                continue

    # --- Page d'accueil commune ---
    build_front_page(story, styles, sys_config, user, project, date_scan,
                     comment=comment)

    # --- Sommaire (avec numeros de page, statut colore) ---
    story.append(Paragraph("Sommaire", styles["SectionTitle"]))
    story.append(Paragraph(
        f"{len(sections)} analyse(s) effectuée(s) sur le périphérique :",
        styles["StatusDesc"]))
    story.append(Spacer(1, 10))
    toc = TableOfContents()
    toc.dotsMinLevel = 0
    # Niveau 0 = analyse reussie (vert), niveau 1 = analyse en erreur (rouge).
    toc.levelStyles = [
        ParagraphStyle(name="TocOk", fontName="Helvetica", fontSize=11,
                       textColor=COLOR_SUCCESS, alignment=TA_LEFT,
                       leading=20, leftIndent=0, firstLineIndent=0),
        ParagraphStyle(name="TocErr", fontName="Helvetica", fontSize=11,
                       textColor=COLOR_DANGER, alignment=TA_LEFT,
                       leading=20, leftIndent=0, firstLineIndent=0),
    ]
    story.append(toc)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=COLOR_BORDER, spaceAfter=8))

    # --- Sections de résultats ---
    for idx, (kind, source_path, status) in enumerate(sections):
        story.append(PageBreak())
        sec_meta = REPORT_META.get(kind, {})
        sec_title = sec_meta.get("title", kind)
        marker = "[OK]" if status == "ok" else "[ERREUR]"
        sec_para = Paragraph(
            f"<para><a name=\"sec_{idx}\"/>{esc(sec_title)}</para>",
            styles["SectionTitle"])
        # Marqueur pour afterFlowable : notifie l'entree du sommaire.
        sec_para._toc_level = 0 if status == "ok" else 1
        sec_para._toc_text = f"{marker}  {sec_title}"
        sec_para._toc_key = f"sec_{idx}"
        story.append(sec_para)

        if status != "ok":
            story.append(Paragraph(
                f"Cette analyse n'a pas pu être exécutée correctement "
                f"(statut : {status}). Les résultats ne sont pas disponibles.",
                styles["StatusDesc"]))
            continue

        if kind == "clamav":
            logs = source_path if isinstance(source_path, list) else [source_path]
            logs = [p for p in logs if p]
            _section_clamav(story, styles, logs, "", "")
        elif kind in _SECTION_DISPATCH:
            try:
                if kind == "custody":
                    # chain_of_custody.json est un JSONL (un objet par
                    # ligne, ajoute au fil de la chasse). Par robustesse,
                    # le chargeur accepte aussi des entrees multi-lignes
                    # (pretty-print) : json.JSONDecoder consomme les
                    # objets les uns apres les autres.
                    data = {"entries": []}
                    with open(source_path, "r", encoding="utf-8") as fh:
                        raw = fh.read()
                    decoder = json.JSONDecoder()
                    pos = 0
                    n = len(raw)
                    while pos < n:
                        while pos < n and raw[pos] in " \t\r\n,":
                            pos += 1
                        if pos >= n:
                            break
                        try:
                            obj, pos = decoder.raw_decode(raw, pos)
                        except json.JSONDecodeError:
                            break
                        data["entries"].append(obj)
                else:
                    with open(source_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                story.append(Paragraph(
                    f"Impossible de charger les résultats : {esc(str(exc))}",
                    styles["StatusDesc"]))
                continue
            _SECTION_DISPATCH[kind](story, styles, data)
        else:
            story.append(Paragraph(
                f"Type d'analyse inconnu : {esc(kind)}",
                styles["StatusDesc"]))

    # --- Pied du rapport ---
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=COLOR_BORDER, spaceAfter=8))
    story.append(Paragraph(meta["footer_desc"], styles["StatusDesc"]))
    build_signature_page(story, styles, user, meta["title"])

    # --- Rendu PDF ---
    os.makedirs(out_dir, exist_ok=True)
    # --fname-prefix remplace le prefix standard (recherche de menaces :
    # rapport_menaces ou <nom>_rapport_menaces).
    # Format du nom : rapport_<type>_<jj>-<mm>-<aaaa>_<hh>h<mm>m<ss>s.pdf
    now = datetime.now()
    stamp = now.strftime("%d-%m-%Y_%Hh%Mm%Ss")
    fname = f"{fname_prefix or meta['fname_prefix']}_{stamp}.pdf"
    out_path = os.path.join(out_dir, fname)

    # DocTemplate qui notifie les entrees du sommaire (TableOfContents)
    # a chaque titre de section marqué (_toc_text/_toc_level).
    class _MultiDoc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            toc_text = getattr(flowable, "_toc_text", None)
            if toc_text is not None:
                level = getattr(flowable, "_toc_level", 0)
                key = getattr(flowable, "_toc_key", "")
                self.notify("TOCEntry", (level, toc_text, self.page, key))

    doc = _MultiDoc(
        out_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=18 * mm,
        title=meta["doc_title"], author="Vigil",
        subject=meta["doc_subject"],
    )
    header_footer = make_header_footer(sys_config, meta["header"])
    doc.multiBuild(story, onFirstPage=header_footer,
                   onLaterPages=header_footer,
                   canvasmaker=NumberedCanvas)
    return out_path


def build_report(kind, source_path, user, project, out_dir,
                 sys_config=None, action="", options="", comment=""):
    """Assemble le rapport PDF : page d'accueil commune + section résultats."""
    if kind not in REPORT_META:
        raise ValueError(f"Type de rapport inconnu : {kind}")
    meta = REPORT_META[kind]
    if sys_config is None:
        sys_config = load_system_config()

    styles = build_styles()
    story = []

    # --- En-tête du rapport (titre + date) ---
    story.append(Paragraph(meta["title"], styles["ReportTitle"]))
    story.append(Paragraph(
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}",
        styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=COLOR_ACCENT, spaceAfter=16))

    # --- Chargement des données et date d'analyse ---
    clamav_summary = None
    if kind == "clamav":
        # source_path : chemin unique ou liste de chemins (multi-dossiers).
        logs = source_path if isinstance(source_path, list) else [source_path]
        logs = [p for p in logs if p]
        clamav_summary = _parse_clamav_log(logs[0] if logs else "")
        date_scan = _format_clamav_date(clamav_summary["start_date"])
    else:
        logs = None
        with open(source_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        date_scan = data.get("date", "")

    # --- Page d'accueil commune ---
    build_front_page(story, styles, sys_config, user, project, date_scan,
                     comment=comment if kind == "clamav" else None)

    # --- Section résultats propre au type ---
    if kind == "images":
        _section_images(story, styles, data)
    elif kind == "videos":
        _section_videos(story, styles, data)
    elif kind == "audio":
        _section_audio(story, styles, data)
    elif kind == "office":
        _section_office(story, styles, data)
    elif kind == "archives":
        _section_archives(story, styles, data)
    elif kind == "crypto":
        _section_crypto(story, styles, data)
    elif kind == "entropy":
        _section_entropy(story, styles, data)
    elif kind == "bigfiles":
        _section_bigfiles(story, styles, data)
    elif kind == "census":
        _section_census(story, styles, data)
    elif kind == "formataudit":
        _section_formataudit(story, styles, data)
    elif kind == "usbhid":
        _section_usbhid(story, styles, data)
    elif kind == "clamav":
        _section_clamav(story, styles, logs, action, options)

    # --- Pied du rapport (description + signature pour ClamAV) ---
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=COLOR_BORDER, spaceAfter=8))
    story.append(Paragraph(meta["footer_desc"], styles["StatusDesc"]))

    if kind == "clamav":
        build_signature_page(story, styles, user, meta["title"])
    else:
        build_signature_page(story, styles, user, meta["title"])

    # --- Rendu PDF ---
    os.makedirs(out_dir, exist_ok=True)
    # Format du nom : rapport_<type>_<jj>-<mm>-<aaaa>_<hh>h<mm>m<ss>s.pdf
    now = datetime.now()
    stamp = now.strftime("%d-%m-%Y_%Hh%Mm%Ss")
    fname = f"{meta['fname_prefix']}_{stamp}.pdf"
    out_path = os.path.join(out_dir, fname)

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=18 * mm,
        title=meta["doc_title"], author="Vigil",
        subject=meta["doc_subject"],
    )
    header_footer = make_header_footer(sys_config, meta["header"])
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer,
              canvasmaker=NumberedCanvas)
    return out_path


def main():
    import sys
    ap = argparse.ArgumentParser(
        description="Génère un rapport PDF Vigil (trame standardisée).")
    ap.add_argument("--kind", required=True,
                    choices=sorted(REPORT_META.keys()),
                    help="Type de rapport")
    ap.add_argument("--json", default="",
                    help="Fichier JSON de résultat (images, vidéos)")
    ap.add_argument("--log", default=[], action="append",
                    help="Chemin du journal clamscan (clamav) ; répétable pour "
                         "consolider plusieurs dossiers dans un seul rapport")
    ap.add_argument("--section", default=[], action="append",
                    help="Section multi-analyse (mode multi) : format "
                         "<kind>:<status>:<path> où kind=images/videos/... "
                         "et status=ok/error et path=chemin JSON ou log. "
                         "Répétable pour plusieurs sections.")
    ap.add_argument("--user", default="")
    ap.add_argument("--project", default="")
    ap.add_argument("--action", default="", help="Action sur infectés (clamav)")
    ap.add_argument("--options", default="", help="Options clamscan (clamav)")
    ap.add_argument("--comment", default="",
                    help="Commentaire de l'utilisateur (clamav)")
    ap.add_argument("--dir", default="/opt/vigil/rapports",
                    help="Répertoire de sortie du PDF")
    ap.add_argument("--fname-prefix", default="",
                    help="Préfixe de nom de fichier (mode multi) : remplace "
                         "rapport_multi (ex. rapport_menaces)")
    ap.add_argument("--config-dir", default="",
                    help="Répertoire de données Vigil (contient config/system.json)")
    args = ap.parse_args()
    sys_config = load_system_config(args.config_dir)

    if args.kind == "multi":
        if not args.section:
            print("Erreur : --section <kind>:<status>:<path> est requis en "
                  "mode multi (répétable).", file=sys.stderr)
            sys.exit(2)
        sections = []
        for spec in args.section:
            parts = spec.split(":", 2)
            if len(parts) != 3:
                print(f"Erreur : format --section invalide : {spec}",
                      file=sys.stderr)
                print("Format attendu : <kind>:<status>:<path>",
                      file=sys.stderr)
                sys.exit(2)
            sec_kind, sec_status, sec_path = parts
            if sec_kind not in REPORT_META:
                print(f"Erreur : type de section inconnu : {sec_kind}",
                      file=sys.stderr)
                sys.exit(2)
            sections.append((sec_kind, sec_path, sec_status))
        out = build_multi_report(sections, args.user, args.project,
                                args.dir, sys_config=sys_config,
                                comment=args.comment,
                                fname_prefix=args.fname_prefix)
        print(out)
        return

    if args.kind == "clamav":
        source_path = args.log
    else:
        source_path = args.json
    if not source_path:
        print("Erreur : --json (images/vidéos) ou --log (clamav) est requis.",
              file=sys.stderr)
        sys.exit(2)

    out = build_report(args.kind, source_path, args.user, args.project,
                       args.dir, sys_config=sys_config, action=args.action,
                       options=args.options, comment=args.comment)
    print(out)


if __name__ == "__main__":
    main()
