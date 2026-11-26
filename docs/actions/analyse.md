---
layout: default
title: Analyse
parent: Actions
nav_order: 22
has_children: true
---

# Analyser un support

Le parcours principal passe par **Investigation → Affaire en cours** dans la GUI Qt, puis par les vues d'exploration, de preuves et d'analyses.

## Avant de lancer

- Choisir un **opérateur** et créer ou activer une **affaire**.
- Identifier le support, vérifier les protections RO et prévoir une destination distincte pour les résultats.
- Vérifier les dépendances des modules proposés.

## Parcours GUI Qt

1. Ouvrir **Affaire en cours** et activer l'affaire choisie.
2. Depuis les actions de montage, suivre le [triage et le montage RO](montage-lecture-seule.md) dans `/investigation`.
3. Explorer les dossiers et consulter les aperçus et métadonnées.
4. Enregistrer les fichiers utiles comme preuves, avec leur empreinte SHA-256.
5. Ouvrir **Analyses** et lancer le [recensement](recensement.md) ou un autre module disponible.
6. Lire le résultat et les [rapports PDF](../rapports-pdf/README.md).
7. [Démonter](demontage.md) puis [exporter](export.md) l'affaire.

## Choisir un module

| Besoin | Module |
|---|---|
| Inventaire, doublons et extensions trompeuses | [Recensement](recensement.md) |
| Images et métadonnées | [Images](images.md), [Visages](visages.md) |
| Médias | [Vidéos](videos.md), [Audio](audio.md) |
| Documents et conteneurs | [Bureautique](bureautique.md), [Archives](archives.md) |
| Protection et données binaires | [Fichiers chiffrés](crypto.md), [Entropie](entropie.md) |
| Gros fichiers | [Fichiers volumineux](volumineux.md) |
| Suite automatisée | [Orchestrateur](orchestrateur.md) |

## Scripts historiques

Les pages de modules décrivent souvent la page Vigil 1.0 **Analyser un périphérique**, qui demandait un utilisateur et un projet et écrivait dans `data/projects/<projet>/`. Les adaptateurs Qt actuels utilisent aussi les services de la branche 2.0 ; ne supposez pas que tous les chemins historiques sont ceux d'une nouvelle affaire.

Le recensement et les analyses ciblées peuvent écrire dans des formats SQLite/TSV/PDF. Les résultats d'un scan autonome ClamAV ou d'une [recherche de menaces](menaces.md) n'impliquent pas nécessairement une affaire active.

## Traçabilité

Vérifiez les journaux liés à l'opérateur et à l'affaire. Un SHA-256 compare des contenus ; il n'authentifie pas l'auteur de l'acquisition.
