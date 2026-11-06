---
layout: default
title: Analyse
parent: Actions
nav_order: 22
has_children: true
---

# Analyser un support

Examiner les fichiers d’un support monté dans `/investigation` et rattacher les résultats à un projet.

## Prérequis

- Un utilisateur et un projet créés dans la configuration.
- Un support à examiner et de l’espace pour les résultats.
- Konsole disponible pour les scripts interactifs.

## Procédure

1. Ouvrir **Analyser un périphérique**, puis sélectionner l’utilisateur et le projet.
2. Cliquer sur **Monter** et suivre le [montage en lecture seule](montage-lecture-seule.md).
3. Choisir le type de périphérique pour filtrer les outils disponibles.
4. Lancer le [recensement](recensement.md), puis les analyses utiles, seules ou en multi-scan.
5. Consulter les PDF dans `/opt/vigil/rapports/` et les données du projet dans `data/projects/<projet>/`.
6. [Démonter](demontage.md) le support, puis [exporter](export.md) le projet.

## Choisir une analyse

| Besoin | Outil |
|---|---|
| Inventaire, doublons, extensions trompeuses | [Recensement](recensement.md) |
| Métadonnées et repérage de visages | [Images](images.md), [visages](visages.md) |
| Durée et caractéristiques des médias | [Vidéos](videos.md), [audio](audio.md) |
| Documents et conteneurs | [Bureautique](bureautique.md), [archives](archives.md) |
| Protection ou contenu peu identifiable | [Fichiers chiffrés](crypto.md), [entropie](entropie.md) |
| Fichiers de grande taille | [Fichiers volumineux](volumineux.md) |
| Chaîne prédéfinie avec rapport unique | [Orchestrateur](orchestrateur.md) |

## Traçabilité

Les analyses ciblées exigent un projet actif et journalisent leurs actions dans
`chain_of_custody.log`. Le recensement possède aussi un mode autonome technique.
Le [scan ClamAV](antivirus.md) fonctionne sans projet ; la
[recherche de menaces](menaces.md) utilise son propre journal.
