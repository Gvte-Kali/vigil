---
layout: default
parent: "Analyse"
nav_order: 266
---

# 🖼️ Analyse des images — `vigil_images.sh`

> `scripts/analyse/vigil_images.sh` détecte et catalogue tous les
> fichiers **image** (photos) du périphérique monté dans `/investigation/`.

---

## 📖 En résumé

Le script détecte les images via `file` (JPEG, PNG, GIF…), les classe par type
MIME pour les statistiques, extrait les métadonnées **EXIF** si `exiftool` est
disponible (date, appareil, GPS…), calcule le **SHA-256** de chaque image et
génère un rapport PDF. Optionnellement, il peut **détecter les visages** et
copier les images vers un dossier.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier toutes les images vers `DIR` |
| `--faces` | activer la détection des visages après l'analyse |
| `--copy-faces-to DIR` | copier les images contenant des visages vers `DIR` |

## 🔄 Déroulement

1. Bannière, puis **détection** des fichiers image via `file`.
2. **Classement** par type MIME → statistiques.
3. **Extraction EXIF** via `exiftool` (si disponible).
4. **SHA-256** de chaque image.
5. **Détection des visages** (option `--faces`) → voir [visages.md](visages.md).
6. **Copies** optionnelles vers les dossiers choisis.
7. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Les métadonnées EXIF (date de prise de vue, modèle d'appareil, coordonnées GPS)
  sont des éléments de preuve fréquemment exploités.
- La détection de visages peut identifier des personnes sur des photos.

## 🔗 Voir aussi

- [Détection des visages](visages.md)
- [Générateur PDF](../rapports-pdf/README.md)
