---
layout: default
parent: "Analyse"
nav_order: 268
---

# 🎵 Analyse des fichiers audio — `vigil_audio.sh`

> `scripts/analyse/vigil_audio.sh` détecte et catalogue tous les
> fichiers **audio** du périphérique monté dans `/investigation/`.

---

## 📖 En résumé

Le script détecte les fichiers audio via `file` (MPEG, OGG, WAV…), les classe
par type MIME pour les statistiques, extrait la **durée** et le **débit**
(bitrate) via `ffprobe`, calcule le **SHA-256** de chaque fichier et génère un
rapport PDF.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier tous les fichiers audio vers `DIR` |

## 🔄 Déroulement

1. Bannière, **détection** des fichiers audio via `file`.
2. **Classement** par type MIME → statistiques.
3. **Métadonnées** (durée, bitrate) via `ffprobe`.
4. **SHA-256** de chaque fichier.
5. **Copie** optionnelle vers un dossier.
6. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Le **chemin** (avec le nom de partition) et le **SHA-256** identifient sans
  ambiguïté chaque enregistrement audio.
- La durée et le bitrate aident à corréler des enregistrements (notes vocales,
  messages, etc.).

## 🔗 Voir aussi

- [Générateur PDF](../rapports-pdf/README.md)
