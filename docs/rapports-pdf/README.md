---
layout: default
title: Rapports
nav_order: 30
---

# Rapports PDF

Les analyses utilisent le générateur commun `scripts/pdf/vigil_pdf.py`, basé sur
ReportLab. Les PDF sont écrits par défaut dans `/opt/vigil/rapports/`.

## Lire un rapport

La couverture reprend l’entité, le logo, l’opérateur, le projet ou le contexte,
et la date. Les pages suivantes présentent les statistiques puis les résultats,
avec les chemins et les empreintes disponibles.

- Les analyses ciblées décrivent les fichiers retenus.
- Le recensement résume l’inventaire ; le détail est dans SQLite et TSV.
- Un rapport consolidé réunit plusieurs sections avec un sommaire.
- Une section en erreur ou un fichier ignoré doit être examiné avant de conclure.

## Types disponibles

| Usage | Valeurs de `--kind` |
|---|---|
| Fichiers | `images`, `videos`, `audio`, `office`, `archives`, `crypto`, `entropy`, `bigfiles` |
| Inventaire et audit | `census`, `formataudit` |
| Antivirus et USB | `clamav`, `usbhid` |
| Traçabilité | `custody` |
| Rapport consolidé | `multi` |

## Génération technique

Depuis un résultat JSON existant :

```bash
python3 /opt/vigil/scripts/pdf/vigil_pdf.py   --kind images --json /chemin/resultat.json   --user "Operateur" --project "Dossier" --dir /chemin/rapports
```

ClamAV accepte `--log` ; les rapports consolidés utilisent des arguments `--section`
répétés. Consulter `python3 /opt/vigil/scripts/pdf/vigil_pdf.py --help` pour le format
et les options (`--comment`, `--config-dir`, `--fname-prefix`, etc.).

La charte des PDF est définie dans le générateur. Le thème **Graphite** concerne
le site de documentation ; la [charte de l’application](../interface-graphique/theme.md)
est définie séparément.
