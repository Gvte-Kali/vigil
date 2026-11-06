---
layout: default
parent: Analyse
title: Bureautique
nav_order: 269
grand_parent: Actions
---

# Bureautique

Recenser les documents bureautiques à partir de leur type détecté par `file`.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_office.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |


## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Pour rechercher les protections par mot de passe, utiliser aussi [Fichiers chiffrés](crypto.md).

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
