---
layout: default
parent: "🔍 Analyse forensique"
nav_order: 213
---

# 🗃️ Fichiers volumineux — `vigil_bigfiles.sh`

> `scripts/analyse/vigil_bigfiles.sh` détecte les fichiers de **grande
> taille** (défaut ≥ 512 Mo), en écartant les vidéos (traitées par le script
> dédié). Il détecte aussi les **fichiers creux** (sparse) composés uniquement
> d'octets nuls.

---

## 📖 En résumé

Le script détecte les fichiers ≥ `--min-size` Mo (sauf vidéos), repère les
fichiers **creux** (octets nuls uniquement — espaces non alloués), calcule le
**SHA-256** de chaque fichier retenu et génère un rapport PDF.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier les fichiers volumineux vers `DIR` |
| `--min-size N` | taille minimale en Mo (défaut : 512) |

## 🔄 Déroulement

1. Bannière, **détection** des fichiers ≥ `--min-size` Mo (hors vidéos).
2. **Détection** des fichiers creux (octets nuls uniquement).
3. **SHA-256** de chaque fichier retenu.
4. **Copie** optionnelle vers un dossier.
5. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Un fichier volumineux non identifié peut être une **image disque**, une
  **base de données** ou un **conteneur caché**.
- Les fichiers creux (sparse) sont un **indicateur forensique** important :
  image disque, fichier effacé, espace non alloué.

## 🔗 Voir aussi

- [Forte entropie](entropie.md)
- [Générateur PDF](../rapports-pdf/README.md)
