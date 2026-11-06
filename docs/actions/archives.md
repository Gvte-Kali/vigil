---
layout: default
parent: Analyse
title: Archives
nav_order: 270
grand_parent: Actions
---

# Archives

Recenser les archives, les classer par type et rechercher une protection par mot de passe lorsque les outils nécessaires sont disponibles.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_archives.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |


## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Une archive protégée nécessite une analyse complémentaire de son contenu. Voir [Fichiers chiffrés](crypto.md).

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
