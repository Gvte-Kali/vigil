---
layout: default
title: Premiers pas
nav_order: 5
---

# Ma première investigation avec Vigil

Ce tutoriel suit **la GUI Qt de la branche `main`**. Utilisez un support de test autorisé et dépourvu de données irremplaçables. Les actions exactes dépendent des outils installés.

## Avant de commencer

- Vigil installé sur un poste Linux Debian ou dérivé, de préférence dans une VM de test.
- Un opérateur autorisé, un support USB de démonstration et un emplacement distinct pour les résultats.
- Les dépendances diagnostiquées et les signatures ClamAV mises à jour si un scan est prévu.

## Étapes

1. **Lancer l'application.** Ouvrir `vigil gui` ou `vigil-gui` ; vérifier l'état affiché dans l'en-tête et la barre d'état.
2. **Configurer l'entité.** Dans **Système → Configuration → Entité**, renseigner l'organisation et éventuellement son logo.
3. **Choisir l'opérateur.** Sélectionner l'identité utilisée pour les actions journalisées ; un opérateur n'est pas une protection d'accès.
4. **Créer une affaire.** Ouvrir **Investigation → Affaire en cours**, créer l'affaire puis l'activer explicitement.
5. **Préparer le support.** Identifier le périphérique, garder la destination séparée et vérifier la protection USB. Ne pas utiliser un disque de production pour cette recette.
6. **Monter en lecture seule.** Suivre le [triage et montage](actions/montage-lecture-seule.md) dans `/investigation` et vérifier son résultat.
7. **Explorer et conserver.** Consulter les métadonnées et enregistrer une preuve. Vérifier que la copie locale et le SHA-256 sont présents.
8. **Analyser.** Lancer un [recensement](actions/recensement.md) ou une analyse compatible ; lire les alertes et les fichiers ignorés.
9. **Lire les rapports.** Ouvrir les [PDF](rapports-pdf/README.md) et le journal ; une absence de détection ne prouve pas l'absence de menace.
10. **Terminer proprement.** Démonter via Vigil, vérifier le bilan de restitution, [exporter l'affaire](actions/export.md) et contrôler le SHA-256 de l'archive.

## Résultat attendu

Une affaire accessible avec un opérateur identifié, une preuve contrôlée, des résultats documentés et un export vérifiable. Un échec de protection, de démontage ou de vérification doit être consigné et résolu avant de débrancher le support.

## En cas de problème

Consulter la [FAQ](faq.md), le [guide d'installation](installation/README.md) ou la [documentation des périphériques USB](configuration/peripheriques-usb.md). Ne jamais contourner une protection RO pour poursuivre une démonstration.
