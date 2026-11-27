---
layout: default
parent: Analyse
title: Export du projet
nav_order: 275
grand_parent: Actions
grand_parent: Français
---

# Exporter un projet

## Vigil 2.0

Depuis **Affaire en cours → Exporter l’affaire**, choisir **Créer l’archive
complète** et une destination. Le dossier publié contient `affaire.tar.gz` et
`affaire.tar.gz.sha256`. En CLI, la commande équivalente est
`vigil cases export ID DESTINATION --operator NOM`.

Depuis le **Gestionnaire d’affaires**, choisir **Importer → Importer une archive
Vigil 2.0**, sélectionner le TAR.GZ et confirmer après vérification. Le même service
est disponible via `vigil cases verify-archive CHEMIN` et
`vigil cases import-archive CHEMIN --operator NOM`. L’import des dossiers
Vigil 1.0 avec `info.json` reste une action distincte.

Une archive partielle conserve les références et empreintes des preuves dont
la copie manque. Vigil les signale comme indisponibles. Les copies présentes
sont contrôlées et restaurées en mode Linux `0400`.

Le [contrat de portabilité](../development/case-archive.md) documente le
format v3, la compatibilité v2, la couverture, les conflits, les contrôles
d’intégrité et la reprise après erreur.

## Vigil 1.0

Depuis **Gérer les projets**, sélectionner le projet et cliquer sur **Exporter**.
Un projet actif et une destination accessible sont requis. Sélectionner aussi un
utilisateur pour identifier l’opérateur ; le script accepte sinon `(no-user)`.

Script : `scripts/export/vigil_export_project.sh`.
L’option `--dest DIR` choisit la destination ; par défaut, `/opt/vigil/rapports/`.

## Fichiers produits

| Fichier | Contenu |
|---|---|
| `<projet>_<stamp>.tar.gz` | Archive du dossier du projet |
| `<projet>_<stamp>.sha256` | Empreintes des fichiers du projet, hors fichiers `.sha256` |
| `<projet>_<stamp>.hash_archive.sha256` | Empreinte de l’archive |

Le début, le succès ou l’échec de l’export sont inscrits dans le journal du projet.

## Vérifier à réception

Dans le dossier contenant l’archive et son fichier de contrôle, remplacer le nom
ci-dessous par celui de l’export reçu :

```bash
sha256sum -c dossier_20261106_120000.hash_archive.sha256
```

Après extraction, lancer la vérification du manifeste `.sha256` depuis la racine
des fichiers extraits, en lui passant le chemin du manifeste.
Une empreinte vérifie l’intégrité par comparaison ; elle n’authentifie pas l’émetteur.

Voir [Projets](../configuration/projets.md) et [Recensement](recensement.md).
