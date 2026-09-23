---
layout: default
parent: "Analyse"
nav_order: 262
---

# 📌 Démontage — `vigil_usb_umount.sh`

> `scripts/analyse/vigil_usb_umount.sh` démonte proprement les périphériques montés
> en lecture seule dans `/investigation` et déverrouille l'accès bloc.

---

## 📖 En résumé

Le script liste les points de montage actifs sous `/investigation`, démonte
chacun (`umount`), puis relâche le verrou lecture seule du device bloc associé
(`blockdev --setrw`). Aucune donnée n'est altérée : le démontage est une
opération en lecture seule sur le périphérique.

---

## 🔄 Déroulement

1. **Bannière ASCII** « VIGIL ».
2. **Liste** des points de montage sous `/investigation`.
3. **Démontage** de chaque point (`umount`).
4. **Déverrouillage** du device bloc (`blockdev --setrw`).
5. **Bilan** : succès/échecs par device.

## 🔗 Voir aussi

- [Montage en lecture seule](montage-lecture-seule.md)
