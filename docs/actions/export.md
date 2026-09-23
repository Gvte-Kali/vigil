---
layout: default
parent: "Analyse"
nav_order: 275
---

# 📦 Export du projet — `vigil_export_project.sh`

> `scripts/export/vigil_export_project.sh` exporte proprement le dossier d'un
> projet : il recense tous les fichiers, calcule leur SHA-256, archive le
> dossier, puis calcule le SHA-256 de l'archive pour vérification à réception.

---

## 📖 En résumé

L'export est lancé depuis le gestionnaire de projets (bouton **« Exporter »**).
Il produit, dans le dossier de destination choisi, trois fichiers :

| Fichier | Contenu |
|---|---|
| `<projet>_<stamp>.tar.gz` | Archive du dossier du projet (tous les fichiers) |
| `<projet>_<stamp>.sha256` | Liste des SHA-256 de **chaque fichier** du dossier du projet (format `sha256sum`) |
| `<projet>_<stamp>.hash_archive.sha256` | SHA-256 de l'archive elle-même (format `sha256sum`) pour vérifier l'intégrité à réception |

L'export est journalisé dans la **chaîne de custody** du projet
(`chain_of_custody.log`) : début, succès (avec le hash de l'archive) ou erreur.

---

## ⚙️ Étapes

1. **SHA-256 de chaque fichier** du dossier du projet
   (`$PROJECTS_DIR/<projet>/` — logs, base SQLite, TSV, rapports, etc.).
   Format `sha256sum` : `<hash>  <chemin_relatif_au_dossier_projet>`.
2. **Archivage** tar.gz du contenu du dossier du projet (chemins relatifs).
3. **SHA-256 de l'archive** écrit dans `hash_archive.sha256`
   (vérifiable avec `sha256sum -c`).

---

## 🔧 Prérequis

- Un **utilisateur** actif (obligatoire, chaine de custody).
- Un **projet** actif (obligatoire — l'export trace la custody).
- Outils : `sha256sum`, `tar`, `find` (standards).

## ⚙️ Options

| Option | Effet |
|---|---|
| `--dest DIR` | Dossier de destination de l'archive (défaut : `/opt/vigil/rapports/`) |

## 🛡️ Vérification à réception

```bash
# Vérifier l'intégrité de l'archive :
sha256sum -c <projet>_<stamp>.hash_archive.sha256
# Vérifier les fichiers extraits :
sha256sum -c <projet>_<stamp>.sha256
```

## 🔗 Voir aussi

- [Recensement des fichiers](recensement.md) — base SQLite du projet
- [Orchestrateur](orchestrateur.md) — `vigil_scan_all.sh`
