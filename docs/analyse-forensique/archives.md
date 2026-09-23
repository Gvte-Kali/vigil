---
layout: default
parent: "Analyse"
nav_order: 210
---

# 🗄️ Analyse des archives — `vigil_archives.sh`

> `scripts/analyse/vigil_archives.sh` détecte et catalogue les fichiers
> **archives** (zip, 7z, rar, tar, gzip, xz, bzip2…) du périphérique monté dans
> `/investigation/`.

---

## 📖 En résumé

Le script détecte les archives via `file`, les classe par type MIME pour les
statistiques, **vérifie si l'archive est protégée par mot de passe** (si les
outils sont disponibles), calcule le **SHA-256** et génère un rapport PDF.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier toutes les archives vers `DIR` |

## 🔄 Déroulement

1. Bannière, **détection** des archives via `file`.
2. **Classement** par type MIME → statistiques.
3. **Vérification** de la protection par mot de passe (si outils dispo).
4. **SHA-256** de chaque archive.
5. **Copie** optionnelle vers un dossier.
6. **Rapport PDF** (statistiques **avant** la liste des fichiers).

## 🔍 Pertinence forensique

- Les archives peuvent **masquer** des fichiers (mot de passe) ou contenir des
  éléments effacés ailleurs sur le support.
- Le statut « protégé par mot de passe » est un indicateur important pour la
  suite de l'enquête (cf. [fichiers verrouillés](crypto.md)).

## 🔗 Voir aussi

- [Fichiers verrouillés (crypto)](crypto.md)
- [Générateur PDF](../rapports-pdf/README.md)
