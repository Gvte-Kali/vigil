---
layout: default
parent: "Configuration"
title: "Mise à jour ClamAV"
nav_order: 14
---

# 🧪 Mise à jour ClamAV

> Bouton **« Mettre à jour l'antivirus ClamAV »** de la section
> Configuration — page `gui/vigil_clamav_update_gui.py`.

---

## 📖 En résumé

Mise à jour des **signatures virales** ClamAV, en ligne ou par clé USB
(postes isolés hors réseau). La page GUI propose le choix du mode puis
lance le script correspondant dans Konsole.

---

## 🔄 Mode en ligne (`vigil_clamav_update.sh`)

Pour un poste connecté :

1. bannière, puis arrêt temporaire du service `clamav-freshclam`
   (sinon le daemon bloque la base) ;
2. **`freshclam`** : téléchargement des bases (main, daily, bytecode)
   dans le `DatabaseDirectory` ClamAV ;
3. redémarrage du service ;
4. affichage des versions de bases installées.

---

## 🔌 Mode par clé USB (`vigil_clamav_update_usb.sh`)

Pour un poste **isolé** (air-gapped) — les bases sont préparées sur un
poste connecté puis transportées :

1. **Triage USB** anti-Rubber Ducky (baseline, branchement, 10 s — même
   procédure que le montage d'analyse) ;
2. **sélection** du périphérique contenant les `.cvd` ;
3. **verrouillage lecture seule** du périphérique (`blockdev --setro`) ;
4. montage dans `/stockage`, **copie** des fichiers `.cvd` (main,
   daily, bytecode) vers le `DatabaseDirectory` ClamAV ;
5. **démontage** et re-blocage du périphérique ;
6. affichage des versions installées.

---

## 🎬 Workflow type

```text
[Bouton GUI] Mettre à jour l'antivirus ClamAV
    └─ choix du mode :
         ├─ [En ligne]  → vigil_clamav_update.sh
         │     └─ stop freshclam → freshclam → start freshclam
         └─ [Par clé USB] → vigil_clamav_update_usb.sh
               └─ triage USB → montage RO → copie .cvd → démontage
```

---

## 🔗 Voir aussi

- [Antivirus](../actions/antivirus.md) — le scan ClamAV lui-même
- [Périphériques USB](peripheriques-usb.md) — les listes du triage
