---
layout: default
title: FAQ et dépannage
nav_order: 7
---

# FAQ et dépannage

## Les sources sont-elles vraiment protégées ?

Vigil utilise des protections **logicielles** : lecture seule au niveau bloc lorsqu'elle s'applique et options de montage RO. Elles ne remplacent pas un bloqueur d'écriture matériel. Elles ne s'appliquent pas de la même façon aux téléphones MTP/PTP. Vérifiez le bilan et la politique de votre investigation.

## Pourquoi séparer /investigation et /stockage ?

`/investigation` sert à examiner des sources sans écrire dessus. `/stockage` reçoit les données de travail en lecture/écriture. Une destination d'acquisition ne doit jamais être confondue avec sa source.

## Une empreinte SHA-256 suffit-elle ?

Elle sert à **comparer l'intégrité** de deux contenus. Elle ne prouve pas à elle seule leur provenance ni l'identité d'un opérateur.

## ClamAV ne détecte rien : le support est-il sûr ?

Non. Le résultat dépend de la version du moteur, de la fraîcheur des signatures, des fichiers lus, des limites de taille, des archives chiffrées et des erreurs éventuelles. Voir [ClamAV](configuration/clamav.md).

## La TUI est-elle aussi complète que la GUI ?

Non. La TUI est expérimentale et **non fonctionnelle actuellement**. Utilisez la GUI Qt pour vos investigations. Voir [compatibilité](compatibility.md).

## Vigil ne voit pas un disque USB

Vérifiez `lsblk`, le triage et les éventuels blocages HID/USB. Ne modifiez pas les règles udev manuellement pour forcer un montage. Consulter [Périphériques USB](configuration/peripheriques-usb.md).

## Le montage ou la fermeture échoue

Ne débranchez pas un support pendant une opération. Relevez l'identité du périphérique, les montages actifs, le compte rendu de session et l'erreur. Suivez le [guide de démontage](actions/demontage.md). Ne redémarrez pas aveuglément un outil de copie.

## Où sont les rapports et les preuves ?

Sur une installation site `/opt/vigil`, les rapports courants se trouvent généralement sous `/opt/vigil/rapports` et les données de l'affaire dans le stockage associé. Pour une installation de développement, les chemins peuvent relever de XDG. Lire [Rapports](rapports-pdf/README.md) et [Projets](configuration/projets.md).

## Puis-je installer Vigil sur Fedora ou Omarchy ?

Le mode utilisateur peut y être testé, mais les opérations privilégiées et l'installateur de site sont principalement documentés pour Debian. Utilisez d'abord la [recette de développement non intrusive](development/native-recette.md).

## Comment signaler un problème ?

Ouvrez une [issue](https://github.com/Gvte-Kali/vigil/issues) en précisant l'OS, le commit, le scénario et des journaux sans données sensibles.
