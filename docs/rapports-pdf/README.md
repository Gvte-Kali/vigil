---
layout: default
title: "📄 Rapports PDF"
nav_order: 50
has_children: True
---

# 📄 Rapports PDF

> Tous les rapports d'analyse Vigil sont générés par un **générateur PDF commun**,
> `scripts/pdf/vigil_pdf.py`, qui garantit une **trame standardisée** identique
> pour tous les types d'analyse.

---

## 📖 En résumé

Chaque type d'analyse (images, vidéos, audio, bureautique, archives, crypto,
entropie, volumineux, antivirus) n'apporte que sa **section de résultats** via
un fichier JSON (ou un log pour ClamAV) et un identifiant `--kind`. Le
générateur se charge de la **page d'accueil** (entité, établissement, adresse,
téléphone, email, logo, utilisateur, projet, date), de l'**en-tête** de page
et du **pied de page** numéroté. La charte graphique (couleurs, polices,
tableaux) est définie **une seule fois**.

---

## ⚙️ Usage

```bash
vigil_pdf.py --kind images|videos|audio|office|archives|crypto|entropy|bigfiles|clamav \
    --json <resultat.json>     # (analyses de fichiers)
    --log  <scan.log>          # (clamav)
    --user "..." --project "..." --dir <dossier_rapports> \
    [--action "..."] [--options "..."] [--comment "..."] [--config-dir "..."]
```

## 📋 Types de rapports (`--kind`)

Analyses de fichiers : `images`, `videos`, `audio`, `office`, `archives`,
`crypto`, `entropy`, `bigfiles`.

Autres rapports :

| `--kind` | Rapport |
|---|---|
| `clamav` | Analyse antivirus (depuis un journal clamscan) |
| `census` | Recensement des fichiers (base SQLite du projet) |
| `formataudit` | Audit de format — extensions trompeuses, forte entropie |
| `usbhid` | Triage USB — détection Rubber Ducky (frappes bloquées) |
| `custody` | Chaîne de custody (journal des actions du projet) |
| `multi` | Rapport **consolidé** multi-analyses (sommaire + sections) |

Le mode `multi` est utilisé par l'orchestrateur (`vigil_scan_all.sh`) et par la
recherche de menaces (`vigil_malware_hunt.sh`) : chaque analyse produit son
JSON (`--no-pdf --json-out`), puis un PDF unique assemblé via
`vigil_pdf.py --kind multi`.

## 🧱 Structure d'un rapport

1. **Page d'accueil** : entité / établissement / adresse / téléphone / email /
   logo + utilisateur + projet + date du scan.
2. **En-tête** de page : bandeau accent + titre du rapport.
3. **Pied de page** numéroté.
4. **Statistiques** (présentées **avant** la liste des fichiers).
5. **Liste des fichiers** : chemin (avec dossier racine de la partition) +
   **SHA-256** à côté de chaque fichier.

## 🎨 Charte graphique

Définie dans `vigil_pdf.py` (`COLOR_ACCENT`, `COLOR_DARK`, `COLOR_DANGER`,
`COLOR_SUCCESS`, `COLOR_GREY`…). Repose sur **reportlab** (SimpleDocTemplate,
Table, Paragraph, Image…).

## 🔗 Voir aussi

- [Analyse forensique](../analyse-forensique/README.md)
