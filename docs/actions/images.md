---
layout: default
parent: Analyse
title: Images
nav_order: 266
grand_parent: Actions
---

# Images

Repérer les images et extraire les métadonnées EXIF disponibles (date, appareil, coordonnées GPS) avec `exiftool`.

## Utilisation

Dans la page **Analyser un périphérique**, sélectionner l’utilisateur et le projet,
monter le support, puis lancer cette analyse.

Script : `scripts/analyse/vigil_images.sh`.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le rapport PDF (défaut) ou le désactiver |
| `--copy-to DIR` | Copier les fichiers retenus vers un dossier de travail |
| `--faces` | Rechercher les visages après l’analyse |
| `--copy-faces-to DIR` | Copier les images contenant des visages |

## Résultat

Le rapport présente les statistiques puis les fichiers retenus avec leur chemin et
leur empreinte SHA-256. Les PDF sont écrits dans `/opt/vigil/rapports/`.

Les métadonnées peuvent être absentes ou modifiées. La [détection de visages](visages.md) repère des zones candidates ; elle n’identifie pas les personnes.

Voir [le parcours d’analyse](analyse.md) et [les rapports PDF](../rapports-pdf/README.md).
