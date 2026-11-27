---
layout: default
title: Rapports PDF
nav_order: 30
parent: Français
---

# Lire les rapports Vigil

Les analyses utilisent le générateur commun `scripts/pdf/vigil_pdf.py` fondé sur ReportLab. Sur une installation de site, les PDF se trouvent généralement sous `/opt/vigil/rapports/`. Certains rapports sont également rattachés au dossier de l'affaire ou à une exécution.

## Comment lire un rapport ?

1. **Page de garde :** vérifier l'entité, le logo, l'opérateur, le contexte et la date.
2. **Périmètre :** identifier le support et les opérations effectivement effectuées.
3. **Statistiques :** distinguer fichiers examinés, ignorés, erreurs et détections.
4. **Résultats détaillés :** examiner les chemins et empreintes disponibles.
5. **Conclusion :** ne pas confondre « aucune détection » et preuve d'innocuité.

Un rapport consolidé regroupe plusieurs sections avec sommaire. Les inventaires volumineux ont leur détail dans SQLite/TSV ; le PDF en présente généralement un résumé.

## Types de rapports

| Usage | Argument `--kind` |
|---|---|
| Fichiers | `images`, `videos`, `audio`, `office`, `archives`, `crypto`, `entropy`, `bigfiles` |
| Inventaire | `census`, `formataudit` |
| Antivirus et USB | `clamav`, `usbhid` |
| Traçabilité | `custody` |
| Rapport multi-sections | `multi` |

## Pour les utilisateurs avancés

Le générateur peut créer un PDF depuis un JSON déjà produit :

```bash
python3 /opt/vigil/scripts/pdf/vigil_pdf.py \
  --kind images --json /chemin/resultat.json \
  --user "Operateur" --project "Affaire" --dir /chemin/rapports
```

Utilisez `--log` pour les données ClamAV et `--section` répété pour un rapport multi-sections. Consultez `--help` pour les options `--comment`, `--config-dir`, `--fname-prefix` et autres. Le thème Graphite du site web ne modifie pas les rapports.

## Langue des rapports

Les rapports créés depuis la GUI ou la TUI reprennent la langue de l'interface au lancement de l'opération (`VIGIL_LANG=fr` ou `VIGIL_LANG=en`). Les titres, résumés et libellés sont localisés ; les chemins, empreintes, observations et journaux techniques d'origine sont conservés sans transformation. En génération autonome, définir `VIGIL_LANG=en` avant la commande pour obtenir un rapport en anglais.
