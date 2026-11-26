---
layout: default
title: Critères restant à valider
parent: Développement
nav_order: 22
---

# Critères restant à valider

Cette vue résume les cases encore ouvertes du [todo](../../todo.txt) après
l’ajout du Journal d’affaire et de son export JSON.

| Phase | Critères restant ouverts |
|---|---|
| 00 | Validation humaine de l’audit. |
| 01 | Broker à opérations fermées, états RO bloc et montage imposés aux parcours, traitement MTP, validation des destinations et recette en VM. |
| 02 | Contrats complets, adaptateurs historiques, parité CLI/GUI, presets, multi-scans et recherche autonome. |
| 03 | Persistance des exécutions, reprise des dossiers et livrables de la 1.0, ouverture de partitions GPT et d’images E01/AFF avec protection et nettoyage. |
| 04 | Densité et recette graphique, gestionnaire de modules, catalogue, signatures et isolation. La création du dépôt séparé reste soumise à accord. |
| 05 | File persistante, progression, annulation, tentatives et récupération après crash, télémétrie des tâches. Le Journal d’affaire couvre l’audit existant. |
| 06 | Explorateur paginé avec aperçus inertes, FTS5, annotations, tags et collections, tableaux et export contrôlé. |
| 07 | Artefacts Windows, corrélation, timeline complète et carving guidé séparé. |
| 08 | PDF personnalisables, publication et contrôle des livrables complets, recette F01–F27 et parité avant retrait de Tkinter. Release sur accord. |

## Export du journal

Le bouton du Journal d’affaire publie un dossier distinct sous
`$XDG_STATE_HOME/vigil/reports`, ou `~/.local/state/vigil/reports`
si XDG_STATE_HOME est absent. Il contient `case.json` et `SHA256SUMS`.
Le JSON représente un instantané SQLite de l’affaire, des métadonnées des
fichiers enregistrés et du journal existant. La vérification SHA-256 porte
sur le fichier JSON. Les fichiers sources ne sont pas recopiés. Dans le
dossier du rapport, vérifier avec `sha256sum -c SHA256SUMS`.

La recette opérateur figure dans `tests.txt`. Le retour de code se fait par
revert du commit sur la branche dédiée. Les dossiers de rapports existants
peuvent être conservés et relus indépendamment de la version de Vigil.
