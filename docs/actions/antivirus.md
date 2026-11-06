---
layout: default
parent: Analyse
title: Antivirus
nav_order: 265
grand_parent: Actions
---

# Antivirus ClamAV

`scripts/clamav/vigil_clamav_scan.sh` analyse les dossiers montés sous
`/investigation`, sans projet et sans journal de traçabilité de projet.
Depuis l’accueil, utiliser plutôt [Recherche de menaces](menaces.md) pour le parcours complet.

## Lancement

```bash
bash /opt/vigil/scripts/clamav/vigil_clamav_scan.sh
```

Choisir les dossiers à scanner, puis consulter le rapport consolidé.
La progression est une estimation, notamment pendant le traitement des archives.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Rapport consolidé activé par défaut |
| `--log` / `--no-log` | Conservation du journal désactivée par défaut |
| `--all --yes` | Tous les dossiers, sans confirmation |
| `--user NOM` | Choisir l’opérateur |
| `--comment TXT` | Ajouter un commentaire en mode non interactif |
| `--archives` / `--no-archives` | Analyse du contenu des archives activée par défaut |
| `--size-unlimited` / `--size-limit` | Plafond configuré à `2047M` par défaut, ou `512M` en mode limité |
| `--alert-encrypted` / `--no-alert-encrypted` | Signalement des archives chiffrées activé par défaut |

## Interpréter les résultats

Le mode nommé « illimité » reste soumis au plafond configuré et aux limites de
ClamAV : un fichier trop gros peut être ignoré. Examiner les avertissements et les erreurs.
Une alerte `Heuristics.Encrypted.*` signale un contenu chiffré non inspecté ; elle
ne suffit pas à conclure à une infection. Un résultat sans détection ne garantit
pas l’absence de menace.

## Variante complète en terminal

`scripts/clamav/vigil_clamav_full_scan.sh` enchaîne montage, scan et démontage.
Il accepte les options PDF, journal, utilisateur, archives, taille et chiffrement
ci-dessus. Sans `--user`, il choisit un utilisateur configuré selon le contexte
interactif ou actif. Cette variante n’a pas de bouton dédié dans l’accueil.

Mettre les [signatures à jour](../configuration/clamav.md) avant un scan.
