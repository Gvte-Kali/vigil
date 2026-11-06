---
layout: default
parent: Analyse
title: Fichiers volumineux
nav_order: 273
grand_parent: Actions
---

# Fichiers volumineux

Repérer les fichiers d’au moins 512 Mio, hors vidéos, et rechercher ceux constitués uniquement d’octets nuls.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_bigfiles.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |
| `--min-size N` | Taille minimale en Mio (défaut : `512`) |

## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Un fichier contenant des zéros n’est pas nécessairement un fichier creux : la taille logique et l’allocation physique sont des notions distinctes.

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
