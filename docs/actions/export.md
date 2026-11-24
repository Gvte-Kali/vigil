---
layout: default
parent: Analyse
title: Export du projet
nav_order: 275
grand_parent: Actions
---

# Exporter un projet

## Vigil 2.0

Depuis **Affaire en cours → Exporter l’affaire**, choisir **Créer l’archive
complète** et une destination. Le dossier publié contient `affaire.tar.gz` et
`affaire.tar.gz.sha256`. En CLI, la commande équivalente est
`vigil2 cases export ID DESTINATION --operator NOM`.

Vérifier l’archive avec `sha256sum -c affaire.tar.gz.sha256`. Après extraction,
exécuter `sha256sum -c SHA256SUMS` depuis le dossier extrait. Le manifeste
`affaire.json` associe chaque chemin d’origine à son fichier dans `preuves/`.
L’archive inclut les résultats de l’affaire, le journal et les fichiers
réguliers du projet hérité s’il a été importé.

Les copies sont stockées sans extension et en mode Linux `0400`. Le format TAR
enregistre ce mode. Une extraction doit conserver les permissions pour
l’appliquer. Un fichier potentiellement malveillant reste à traiter comme
tel même avec ses permissions de lecture seule.

Si une preuve ancienne a été enregistrée sans copie, réajouter le fichier
d’origine depuis l’explorateur ou l’onglet Preuves. Vigil compare son empreinte
à celle enregistrée avant de créer la copie. L’export complet exige une copie
vérifiable pour chaque preuve.

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
