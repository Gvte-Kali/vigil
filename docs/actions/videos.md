---
layout: default
parent: Analyse
title: Vidéos
nav_order: 267
grand_parent: Actions
---

# Vidéos

Repérer les vidéos et relever leur durée et leur résolution avec `ffprobe`.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_videos.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |


## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Le rapport conserve le chemin, le type et les caractéristiques disponibles de chaque vidéo.

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
