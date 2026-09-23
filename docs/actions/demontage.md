---
layout: default
parent: "Analyse"
title: "Démontage"
nav_order: 262
---

# 📌 Démontage — `vigil_usb_umount.sh`

> `scripts/analyse/vigil_usb_umount.sh` démonte proprement les périphériques montés
> en lecture seule dans `/investigation` et déverrouille l'accès bloc.

---

## 📖 En résumé

Le script liste les points de montage actifs sous `/investigation`, vérifie
l'**intégrité** du contenu (hash d'arbre recalculé vs hash pris au montage),
démonte chaque point (`umount`), puis relâche le verrou lecture seule du
device bloc associé (`blockdev --setrw`). Aucune donnée n'est altérée : le
démontage reste une opération en lecture seule sur le périphérique.

---

## 🔄 Détail du déroulement

1. **Bannière ASCII** « VIGIL », puis contexte utilisateur/projet repris
   des fichiers actifs (`data/active_user`, `data/active_project`) — sans
   contexte, le démontage fonctionne quand même, sans log de custody.
2. **Liste** des points de montage sous `/investigation` avec leur device
   bloc associé.
3. **Vérification d'intégrité** (par point de montage) :
   - le **hash d'arbre actuel** est recalculé
     (`sha256sum` de tous les fichiers, trié, lui-même hashé) ;
   - il est comparé au **hash stocké au montage**
     (`data/projects/<projet>/device_<dev>.sha256`) ;
   - **égal** → `integrity_check` en succès dans la chaîne de custody
     (« hash initial = hash recalculé ») ;
   - **différent** → alerte « périphérique corrompu » (statut
     `corrupted`) — le démontage continue mais l'écart est tracé ;
   - fichier de hash **manquant** (montage hors projet) → simple
     avertissement.
4. **Démontage** de chaque point (`umount`), partition par partition.
5. **Déverrouillage** du device bloc (`blockdev --setrw`) : le
   périphérique redevient accessible en lecture/écriture pour son
   propriétaire légitime.
6. **Suppression** des points de montage vides sous `/investigation`.
7. **Bilan** : succès/échecs par device, tracé dans la chaîne de custody
   (projet) ou le journal de chasse (`hunt/chain_of_custody.json` si
   `VIGIL_HUNT_CUSTODY` est exporté — cas de la
   [recherche de menaces](menaces.md)).

## 🖥️ Lancement depuis la GUI

Sur la page **« Analyse du périphérique USB »**, le bouton **Démonter**
lance le script dans Konsole. Il agit sur **tous** les points de montage
actifs sous `/investigation`.

## 🔗 Voir aussi

- [Montage en lecture seule](montage-lecture-seule.md)
- [Analyse](analyse.md) — le workflow complet d'une analyse
