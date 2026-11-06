---
layout: default
parent: Configuration
title: Périphériques USB
nav_order: 13
---

# Périphériques USB

Ouvrir **Périphériques USB** depuis la section Configuration pour consulter les
périphériques connectés et gérer les listes utilisées pendant le triage.

## Gérer les listes

1. Repérer le périphérique par son fabricant, son produit, son identifiant `VID:PID` ou son numéro de série.
2. Choisir **Whitelister (confiance)** ou **Blacklister (suspect)**.
3. Vérifier les entrées et cliquer sur **Enregistrer**.

Les tableaux permettent aussi d’ajouter et de retirer des entrées manuellement.

| Liste | Fichier | Effet au triage |
|---|---|---|
| Confiance | `data/usb/whitelist.txt` | Exempte le périphérique du blocage des nouveaux claviers HID |
| Blocage | `data/usb/blacklist.txt` | Désautorise le périphérique au niveau du noyau, y compris s’il n’est pas HID |

## Protéger le clavier de travail

Laisser le clavier branché pendant l’état de référence du triage.
S’il doit être débranché puis rebranché, l’ajouter à la liste de confiance.
Un nouveau clavier HID non autorisé est bloqué par défaut.

Un identifiant USB est un critère de filtrage, pas une preuve d’identité du matériel.
Voir [Montage en lecture seule](../actions/montage-lecture-seule.md).
