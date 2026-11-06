---
layout: default
parent: Actions
title: Copie forensique
nav_order: 24
---

# Copie forensique

Créer une image d’un disque avec `scripts/imager/vigil_disk_imager.sh`,
depuis **Faire une copie forensique d’un disque**.

## Procédure

1. Choisir le disque source parmi les supports externes proposés.
2. Vérifier son identité et le verrouillage en lecture seule.
3. Choisir le format, le nom de l’image et la destination.
4. Confirmer l’acquisition et attendre le bilan.
5. Conserver l’image, ses empreintes de contrôle et le journal d’acquisition.

La destination peut être un support externe ou un dossier local. Le script vérifie
l’espace local en réservant 20 % du disque système.

## Formats

| Format | Outil | Usage |
|---|---|---|
| RAW | `dc3dd` | Image brute (`.raw`, `.dd`, `.img`) |
| E01 | `ewfacquire` | Image segmentée avec métadonnées et compression |
| AFF | Outils AFFlib | Format de conteneur forensique |

Le script vérifie les dépendances du format choisi et l’état de lecture seule
avant l’acquisition. Les empreintes SHA-256 permettent de contrôler les fichiers
produits ; conserver aussi le journal pour interpréter l’opération.

Pour copier directement vers un autre disque, voir [Clonage](clonage.md).
