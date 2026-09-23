---
layout: default
parent: "Analyse"
nav_order: 209
---

# 📑 Analyse des fichiers bureautiques — `vigil_office.sh`

> `scripts/analyse/vigil_office.sh` détecte et catalogue les fichiers
> **bureautiques** (Documents, Tableurs, Présentations, PDF, RTF) du périphérique
> monté dans `/investigation/`.

---

## 📖 En résumé

La détection se fait **par extension** puis confirmation du **type MIME** via
`file`. Cela est nécessaire car `file` ne distingue pas les formats OOXML
(docx/xlsx/pptx sont tous renvoyés comme `application/zip`). Les fichiers sont
classés par catégorie (Document, Tableur, Présentation, PDF, RTF) et par
format (extension) pour les statistiques, puis le **SHA-256** est calculé et un
rapport PDF est généré.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier tous les fichiers bureautiques vers `DIR` |

## 🔄 Déroulement

1. Bannière, **détection** par extension + vérification du type MIME.
2. **Classement** par catégorie et par format → statistiques.
3. **SHA-256** de chaque fichier.
4. **Copie** optionnelle vers un dossier.
5. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Les documents bureautiques peuvent contenir des **métadonnées d'auteur**,
  des dates de création/modification et des commentaires.
- Le SHA-256 garantit l'identification non ambiguë de chaque pièce.

## 🔗 Voir aussi

- [Fichiers verrouillés (crypto)](crypto.md)
- [Générateur PDF](../rapports-pdf/README.md)
