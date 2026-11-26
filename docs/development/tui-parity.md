---
layout: default
title: Parité Textual
parent: Développement
nav_order: 25
---

# Parité du workspace Textual

> **Avertissement : TUI expérimentale et non fonctionnelle actuellement.** Ce document décrit l'implémentation et des tests partiels, et non une interface validée pour les investigations.

Référence visuelle et ergonomique : workspace PySide6 du commit
`5644a9781c68b63811dc23183493ddf41cddb0c6`. Les données, les commandes
et les protections sont celles du Core courant de `vigil-2.0`.

| Parcours Qt | Parcours Textual | Validation et écarts |
| --- | --- | --- |
| En-tête, menu latéral, barre d’état | Logo Chafa, version, opérateur, affaire, FR/EN, menu repliable, zone et protection visibles | Ordre, bascule de langue et redimensionnement testés |
| Dashboard et inventaire | Mesures CPU/RAM, durée, compte d’affaires, montages, arbre bloc, activité, diagnostic et protection | Recette système sur les distributions cibles ouverte |
| Gestionnaire d’affaires | Liste et inspecteur, recherche, tri, création, suppression, import de projet ou d’archive et activation séparée | Test de création et d’activation. Recette des archives volumineuses et partielles ouverte |
| Sources | Montages observés, menu de montage et recensement, démontage et inspection RAW | Le montage physique appelle le parcours existant. Rattachement de plusieurs images et prise en charge des autres formats encore à faire dans le Core |
| Explorateur et preuves | Arbres des montages RO et des copies, aperçu borné HEX/ASCII, ajout, copie, SHA-256 et suppression | Test d’ajout et de contrôle. Actions de sélection multiple et ouverture graphique contextuelle à migrer |
| Analyses et recensement | Choix d’un module, terminal intégré, résultats sur disque et requête d’index | Interaction PTY testée avec un processus de simulation. Recette des outils sur supports physiques ouverte |
| Journal, rapports et export | Journal filtrable et paginé, détails, liste des PDF, chemin des rapports, export d’audit et archive | L’écran rapporte les chemins des PDF. Le rendu PDF et l’exploration détaillée des résultats dans la TUI restent ouverts |
| Actions rapides | Antivirus, signatures et rapports, stockage RW, clonage et acquisition RAW dans l’ordre de la référence | Les commandes du Core sont raccordées. Recette opérateur sudo, matériel USB et reprise ouverte |
| Entité | Coordonnées, logo PNG/JPEG, opérateur de session | Chargement et sauvegarde via les services d’entité. Aperçu du logo via Chafa |
| Catalogue | Filtre, disponibilité, inspecteur et création de brouillon | Recette du catalogue communautaire ouverte |
| Session et lanceurs | Supervision commune, bilan dans le terminal courant, publication de `vigil-tui` | Collision, idempotence et trois entrées testées. Validation de la restitution matérielle ouverte |

## Présentation du terminal intégré

Les actions rapides s’affichent en cartes, sur une à trois colonnes selon la
largeur. L’en-tête accueille le logo SVG rendu par Chafa sur huit lignes. Les icônes se replient en ASCII sur
un terminal non UTF-8 ou avec `VIGIL_ASCII=1`.

Le terminal intégré conserve les messages dans le journal et met les étapes
de détection USB, de scan, de copie, de synchronisation et de vérification
sur des barres séparées. Les scripts exécutés dans un terminal classique
gardent leur affichage habituel.

Au démarrage de la TUI, l’assistant demande l’autorisation sudo et restaure
les protections laissées par une précédente session avant d’armer udev. Une
restitution impossible reste signalée. Le bilan affiché à la fermeture est
concis et le rapport complet reste disponible sur disque. Après mise à jour
du dépôt, réinstaller l’assistant privilégié avec
`bash scripts/post-install/install-hotplug.sh` depuis le compte opérateur,
après fermeture de toutes les sessions Vigil.
