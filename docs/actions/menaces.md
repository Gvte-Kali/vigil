---
layout: default
parent: Actions
title: Recherche de menaces
nav_order: 21
---

# Recherche de menaces

Depuis l’accueil, **Recherche de menaces** lance
`scripts/clamav/vigil_malware_hunt.sh` dans Konsole.
Ce parcours utilise un opérateur et son propre journal, **sans projet**.

## Procédure

1. Confirmer le lancement et choisir l’opérateur si demandé (`--user NOM` permet de le fournir).
2. Donner un nom facultatif au rapport.
3. Suivre le triage USB et le montage en lecture seule.
4. Laisser s’exécuter le recensement, l’audit de format, ClamAV et le démontage.
5. Lire le rapport PDF, puis choisir si les preuves intermédiaires doivent être exportées.

## Ce qui est examiné

| Étape | Résultat |
|---|---|
| Triage et montage | Périphériques apparus, blocages HID, protection en lecture seule |
| Recensement | Inventaire SQLite/TSV, SHA-256, doublons et extensions trompeuses |
| Audit de format | Extensions incohérentes et fichiers binaires à forte entropie |
| ClamAV | Détections et limites d’analyse, y compris dans les archives |
| Démontage | Comparaison d’intégrité et libération du support |

L’audit utilise des signatures locales (`config/forensic_signatures.json`) et,
si disponible, `binwalk`. Il cible notamment les fichiers `application/octet-stream`
dont l’entropie de Shannon atteint 7,5 bits/octet sur l’échantillon analysé.
Une forte entropie peut correspondre à des données compressées ou chiffrées ;
elle ne prouve pas une menace.

## Rapport et traçabilité

Le PDF unique regroupe triage USB, ClamAV, audit, recensement et journal chronologique.
Il est écrit dans `/opt/vigil/rapports/`, sous un nom de type
`rapport_menaces_<date>_<heure>.pdf`, éventuellement précédé du nom choisi.

Les fichiers temporaires et le journal `chain_of_custody.json` sont réunis dans
`$VIGIL_BASE/hunt/`. Aucun dossier de projet n’est modifié.
Si le triage bloque le seul support, le parcours peut se terminer avec un rapport de triage seul.

## Export et nettoyage

En mode interactif, après génération du PDF, l’export facultatif produit une
archive `tar.gz` contenant `hunt/` et le rapport, avec un fichier `.sha256`.

**Le contenu de `hunt/` est purgé au début de chaque chasse et à sa clôture.**
Exporter les éléments à conserver avant la clôture. Si l’export échoue ou est
annulé après acceptation, la purge finale est annulée pour conserver les données ;
les récupérer avant de lancer une nouvelle chasse.

Voir [Antivirus](antivirus.md), [Recensement](recensement.md) et
[Montage en lecture seule](montage-lecture-seule.md).
