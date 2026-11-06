---
layout: default
parent: Analyse
title: Entropie
nav_order: 272
grand_parent: Actions
---

# Forte entropie

Repérer les fichiers `application/octet-stream` peu compressibles avec `zstd` et relever leur alignement sur 512 octets.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_entropy.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |
| `--min-size N` | Taille minimale en **octets** (défaut : `4194304`, soit 4 Mio) |
| `--threshold N` | Seuil du ratio de compression, en centièmes de pourcent (défaut : `9800`, soit 98 %) |

## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Ce test estime la compressibilité ; il ne démontre pas un chiffrement. Sans `zstd`, le calcul est désactivé. Attention : l’unité de `--min-size` diffère de celle de l’analyse des fichiers volumineux.

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
