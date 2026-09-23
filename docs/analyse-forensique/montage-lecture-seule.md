---
layout: default
parent: "Analyse"
nav_order: 201
---

# 📌 Montage en lecture seule — `vigil_usb_mount.sh`

> `scripts/analyse/vigil_usb_mount.sh` monte un périphérique USB / disque / smartphone
> **en lecture seule** dans `/investigation`. C'est l'étape préalable à toute analyse.

---

## 📖 En résumé

On choisit le **type de périphérique** (smartphone, stockage USB, ou tout type),
puis on sélectionne le périphérique parmi ceux détectés. Le périphérique est
monté en lecture seule stricte, de façon à **ne jamais altérer** les preuves.
On peut monter une **partition** ou **tout le disque** d'un coup.

---

## 🔄 Déroulement

1. **Bannière ASCII** « VIGIL ».
2. **Triage USB anti-Rubber Ducky** (voir ci-dessous) : baseline
   périphériques débranchés → branchement → comparaison des descripteurs.
3. **Choix du type de périphérique** :
   - `[1]` Smartphone (MTP/PTP)
   - `[2]` Périphérique de stockage USB (clé, disque…)
   - `[3]` Autre (tous types)
3. **`clear` + bannière**, puis **détection** des périphériques via `lsblk`.
4. **Liste enrichie** : nom de device, taille, modèle, bus, vendor, série,
   nombre de partitions, système de fichiers, état de montage.
5. **Choix** d'une partition ou de l'option **« Monter tout le disque »** —
   la touche `r` rafraîchit la liste des périphériques (périphérique lent
   à se faire détecter par `lsblk`), `q` quitte.
6. **Verrouillage lecture seule** (`blockdev --setro`) puis **montage** avec
   `ro,noexec,nosuid,nodev,noatime`.

## 🦆 Triage USB anti-Rubber Ducky

Avant tout montage, Vigil compare deux instantanés de l'état USB du poste
d'analyse :

1. **Baseline** : l'utilisateur débranche les périphériques USB à analyser et
   valide avec Entrée — Vigil enregistre les périphériques présents (les
   contrôleurs et hubs internes restent, c'est normal et sans impact) ;
2. **Branchement** : l'utilisateur branche les périphériques à analyser et
   valide avec Entrée — après **10 secondes** de détection noyau
   (décompte avec barre de progression ; le tampon clavier est purgé
   à chaque seconde : des Entrées anticipées ne peuvent pas être
   réutilisées comme réponse à un prompt), Vigil compare.

Tout périphérique **apparu** entre les deux instantanés et exposant une
**interface clavier HID** (`bInterfaceClass=03`, sous-classe `01`) est
signalé comme potentiel **Rubber Ducky** :

- ses **frappes sont bloquées automatiquement, sans confirmation** —
  un périphérique de stockage légitime ne se présente jamais en
  clavier, et les Entrées tapées pendant le décompte ne peuvent pas
  déclencher un mauvais choix (blocage par défaut) ;
- le blocage est effectif par **déliaison du driver `usbhid`** : le
  clavier n'envoie plus rien au poste d'analyse ;
- il est listé dans la section **« NON MONTABLE(S) »** de la liste des
  périphériques, avec fabricant, produit, VID:PID et numéro de série ;
- il est **jamais proposé au montage** ;
- un **rapport PDF de triage** (`rapport_usbhid_*.pdf`) est généré à chaque
  montage (trace de procédure) et copié dans le dossier du projet : il
  contient les descripteurs de tous les périphériques apparus, l'alerte
  clavier le cas échéant, le compteur et le statut des périphériques
  **protégés par l'utilisateur**.

### Protection du clavier/souris de travail

Le poste d'analyse doit rester utilisable pendant le triage. Deux
mécanismes garantissent que le clavier et la souris de travail ne sont
**jamais bloqués** :

1. **Whitelist baseline** : un périphérique déjà vu à la baseline (même
   port sysfs ou même numéro de série) n'est jamais traité comme nouveau,
   donc jamais candidat au blocage. Clavier et souris restés branchés
   pendant la baseline sont ignorés silencieusement.
2. **Whitelist persistante** (`data/usb/whitelist.txt`) : un clavier
   whitelisté (par VID:PID ou n° de série) n'est **jamais bloqué**, même
   apparu comme nouveau. C'est le mécanisme recommandé pour un clavier
   de travail débranché pendant la baseline puis rebranché : l'ajouter
   une fois via la GUI « Périphériques USB » (Accueil > Configuration),
   il reste ensuite pleinement fonctionnel à chaque montage.

Un clavier HID **non whitelisté** apparu au branchement est bloqué
automatiquement — c'est le comportement attendu pour un périphérique
suspect.

### Blacklist persistante

`data/usb/blacklist.txt` (mêmes entrées VID:PID ou n° de série) bloque
d'office un périphérique, **même non-HID** : `authorized=0` au niveau
noyau (invisible de `lsblk`, non montable), déliaison des éventuelles
interfaces clavier, message rouge à l'écran et ligne
« Blacklisté — bloqué » dans le PDF de triage. Si le seul périphérique
apparu est blacklisté, le script se termine proprement après le
rapport PDF.

### GUI « Périphériques USB »

Accueil > **Configuration** > **Périphériques USB** ouvre une fenêtre
d'inventaire : périphériques connectés (port, fabricant/produit,
VID:PID, n° de série, interface clavier, statut
Whitelisté/Blacklisté/Non listé), boutons **Whitelister (confiance)** et
**Blacklister (suspect)**, et gestion des deux listes sous forme de
tableaux (Ajouter / Retirer) avec Enregistrer.

## 🔒 Garanties forensiques

- Montage **lecture seule** au niveau filesystem **et** au niveau bloc.
- Aucune écriture possible sur le périphérique source.
- Détection robuste : retry sur `lsblk`, fallback `blkid` pour le FSTYPE.
- Les partitions non montables (MBR étendue 1K) sont écartées.

## 🖥️ Types de périphériques gérés

- **Smartphones** : mode MTP/PTP via `jmtpfs`/`simple-mtpfs`.
- **Stockage USB** : clés, disques durs externes (partition ou disque entier).
- **DVD/CD-ROM** : montés en lecture seule via `/dev/cdrom`.

## 🔗 Voir aussi

- [Démontage](demontage.md)
- [Scan complet](orchestrateur.md)
