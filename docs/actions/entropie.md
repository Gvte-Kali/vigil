---
layout: default
parent: "Analyse"
title: "Entropie"
nav_order: 272
---

# 🎲 Forte entropie — `vigil_entropy.sh`

> `scripts/analyse/vigil_entropy.sh` détecte les fichiers à **forte
> entropie** : contenu hautement aléatoire (chiffré, compressé, blob binaire),
> non identifié par son type MIME.

---

## 📖 En résumé

Le script sélectionne les fichiers de type `application/octet-stream` (non
identifiés par `file`) de taille ≥ 4 Mo, calcule leur **entropie** via le taux
de compression `zstd` (un ratio > 98 % signale une entropie élevée), vérifie
l'**alignement sur secteur** (taille multiple de 512 — indicateur d'image
disque brute), calcule le **SHA-256** et génère un rapport PDF.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier les fichiers à forte entropie vers `DIR` |
| `--min-size N` | taille minimale en Mo (défaut : 4) |

## 🔄 Déroulement

1. Bannière, **sélection** des candidats (`octet-stream`, ≥ `--min-size` Mo).
2. **Calcul d'entropie** via `zstd` (ratio compression).
3. **Vérification** de l'alignement secteur (`taille % 512 == 0`).
4. **SHA-256** de chaque fichier retenu.
5. **Copie** optionnelle vers un dossier.
6. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Une forte entropie signale souvent des **données chiffrées** ou des **images
  disque brutes** non déclarées comme telles.
- L'alignement sur secteur est un **indicateur forensique** (image disque,
  secteur, partition cachée).
- Si `zstd` est absent, le calcul d'entropie est désactivé.

## 🔗 Voir aussi

- [Fichiers volumineux](volumineux.md)
- [Générateur PDF](../rapports-pdf/README.md)
