---
layout: default
title: Accueil
nav_order: 1
---

<p class="eyebrow">Documentation / Vigil</p>

# Examiner. Comprendre. Tracer.

Vigil est une application Linux d’analyse de supports numériques. Elle réunit
montage en lecture seule, analyses de fichiers, recherche de menaces et rapports PDF.

[Commencer l’installation](installation/README.md){: .btn .btn-primary }
[Analyser un support](actions/analyse.md){: .btn }

## Première utilisation

1. Lancer `vigil` sur le poste installé.
2. Renseigner l’[entité et les utilisateurs](configuration/systeme.md).
3. Créer un [projet](configuration/projets.md), puis sélectionner l’utilisateur et le projet dans la page d’analyse.
4. Monter le support, lancer les analyses et consulter les rapports dans `/opt/vigil/rapports/`.
5. Démonter le support, puis [exporter le projet](actions/export.md).

## Choisir son parcours

| Besoin | Point d’entrée |
|---|---|
| Préparer le poste | [Installation](installation/README.md) |
| Régler l’entité, les projets et les périphériques | [Configuration](configuration/README.md) |
| Chercher des menaces sans projet | [Recherche de menaces](actions/menaces.md) |
| Examiner des fichiers dans un projet | [Analyse](actions/analyse.md) |
| Créer une image ou cloner un disque | [Actions](actions/README.md) |
| Comprendre les résultats | [Rapports PDF](rapports-pdf/README.md) |
| Contribuer à l’interface | [Interface graphique](interface-graphique/README.md) |

## Repères essentiels

- **Analyse** : support monté en lecture seule dans `/investigation` ; utilisateur et projet requis dans l’interface.
- **Recherche de menaces** : parcours autonome avec opérateur et journal de traçabilité propres, sans projet.
- **Stockage** : support monté en lecture/écriture dans `/stockage`, pour les fichiers de travail.
- **Intégrité** : les empreintes SHA-256 permettent de comparer les contenus ; elles ne constituent pas une signature numérique authentifiée.

Vigil applique des protections logicielles. Leur portée dépend du support et du protocole : le verrouillage bloc d’un disque ne s’applique pas à un téléphone MTP.
