---
layout: default
parent: "🔍 Analyse forensique"
nav_order: 207
---

# 🎬 Analyse des vidéos — `vigil_videos.sh`

> `scripts/analyse/vigil_videos.sh` détecte et catalogue tous les
> fichiers **vidéo** du périphérique monté dans `/investigation/`.

---

## 📖 En résumé

Le script détecte les vidéos via `file` (MP4, AVI, x-msvideo…), les classe par
type MIME pour les statistiques, extrait la **durée** et la **résolution** de
chaque fichier via `ffprobe`, calcule le **SHA-256** et génère un rapport PDF.
Le rapport conserve le **chemin** de chaque vidéo (avec le dossier racine de la
partition) et sa signature, indicateurs pertinents pour une enquête.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier toutes les vidéos vers `DIR` |

## 🔄 Déroulement

1. Bannière, **détection** des fichiers vidéo via `file`.
2. **Classement** par type MIME → statistiques.
3. **Métadonnées** (durée, résolution) via `ffprobe`.
4. **SHA-256** de chaque vidéo.
5. **Copie** optionnelle vers un dossier.
6. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Le **chemin** de chaque vidéo (avec le nom de la partition) situe le fichier
  dans l'arborescence du support analysé.
- Le **SHA-256** garantit l'identification non ambiguë du fichier.
- La durée et la résolution aident au tri et à la corroboration.

## 🔗 Voir aussi

- [Générateur PDF](../rapports-pdf/README.md)
