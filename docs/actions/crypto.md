---
layout: default
parent: Analyse
title: Fichiers chiffrés
nav_order: 271
grand_parent: Actions
---

# Fichiers chiffrés

Rechercher les protections par mot de passe dans les archives et les documents compatibles (Office, PDF, OpenDocument), avec `7za` ou `file`.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_crypto.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |


## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Seuls les fichiers dont la protection est confirmée figurent dans les résultats. La présence de chiffrement ne prouve pas une intention de dissimulation.

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
