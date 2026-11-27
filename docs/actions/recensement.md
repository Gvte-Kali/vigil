---
layout: default
parent: Analyse
title: Recensement
nav_order: 264
grand_parent: Actions
grand_parent: Français
---

# Recensement des fichiers

Créer un inventaire des fichiers : chemins, tailles, dates, types MIME, empreintes
SHA-256, doublons et écarts entre extension et contenu.

Script : `scripts/analyse/vigil_census.sh`.

## Utilisation

1. Sélectionner l’utilisateur et le projet dans la page d’analyse.
2. Monter le support en lecture seule.
3. Lancer le recensement avant les analyses ciblées.
4. Consulter les statistiques dans le PDF et les détails dans SQLite ou TSV.

Un nouveau recensement **remplace les livrables du précédent** dans le même projet.
Exporter les résultats avant une relance si leur conservation est nécessaire.

## Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | Activer le PDF (défaut) ou le désactiver |
| `--no-dedup` | Désactiver le marquage des doublons |
| `--no-checksafe` | Désactiver le filtrage par bases externes |
| `--no-project` | Mode autonome utilisé par la recherche de menaces ; sortie dans `hunt/` |

## Données produites

Dans `data/projects/<projet>/` : base `census_*.sqlite`, export `census_*.tsv`,
empreinte `.sqlite.sha256` et traces `.sains.*` / `.doublons.*`.

| Table SQLite | Contenu |
|---|---|
| `inventory_meta` | Support, montage, opérateur, projet, dates et bilan |
| `files` | Métadonnées, hash de contenu, doublons, filtrage et extensions trompeuses |

Les dates sont normalisées en UTC ; leur interprétation reste liée au système de fichiers d’origine.

## Doublons et fichiers connus

Les doublons sont groupés par **SHA-256**, marqués et conservés dans l’inventaire.
Les analyses ciblées peuvent traiter un représentant et documenter les autres emplacements.

Checksafe lit deux bases facultatives dans `/stockage`, au format TSV UTF-8 à
une colonne. Utiliser des listes fournies par une autorité de confiance.

| Fichier | En-tête | Une entrée par ligne |
|---|---|---|
| `files.safe.name.tsv` | `name` | Nom de fichier sans chemin, comparé sans tenir compte de la casse |
| `files.safe.hash.tsv` | `sha1` | SHA-1 en 40 caractères hexadécimaux |

Sans liste de noms, le filtre vérifie les empreintes de tous les fichiers. Une
liste de noms avec le seul en-tête ne retient aucun candidat. Sans empreintes
valides, ou si une base TSV présente est invalide, aucun fichier n'est marqué
comme connu. Les erreurs figurent dans la sortie console et le JSON du
recensement. Les limites par base sont 32 Mio, 500 000 entrées et 4096 octets
par ligne. SHA-256 reste l'empreinte de référence de l'inventaire.

Pour migrer, demander un export texte des listes à la source de confiance.
Les anciens fichiers `files.safe.name` et `files.safe.hash` sont ignorés.


## Extensions trompeuses

Le format détecté est comparé à `config/ext_mime_map.json`.
Les écarts sont conservés dans `extension_mismatch` et `expected_format`.
Les extensions inconnues et les fichiers vides ne déclenchent pas cette alerte.

L’outil `scripts/analyse/vigil_census_query.py` permet de consulter l’index par type MIME,
extension ou anomalie. Voir aussi [Recherche de menaces](menaces.md).
