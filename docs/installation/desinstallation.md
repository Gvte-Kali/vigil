---
layout: default
parent: Installation
title: Remise à zéro
---

# Désinstaller Vigil sur Debian ou Parrot

Fermez Vigil et les terminaux d’opérations, démontez les volumes et débranchez les supports après restitution confirmée. Sauvegardez les affaires externes au site séparément. Exécutez depuis le compte opérateur.

```bash
cd /opt/vigil
bash scripts/post-install/uninstall.sh --dry-run
bash scripts/post-install/uninstall.sh --keep-data
```

La conservation est le mode par défaut : archive dans ~/vigil-uninstall.*. Pour supprimer définitivement les données du site, utilisez :

```bash
bash scripts/post-install/uninstall.sh --dry-run --purge --purge-dependencies
bash scripts/post-install/uninstall.sh --purge --purge-dependencies
```

Relisez la simulation APT avant de confirmer UNINSTALL puis PURGE. Les dépendances sont facultatives et limitées à l’inventaire des ajouts APT ; conservez les paquets partagés. Aucun autoremove automatique. L’option --legacy inclut les anciennes archives du site. Les zones non vides sont conservées.

Le journal ~/vigil-uninstall.*.log est conservé même en mode purge. Les résidus affichés doivent être examinés. Une session active bloque la suppression ; fermez Vigil puis revérifiez. VIGIL_LANG=fr ou en force la langue.

Pour les installations historiques, restaurez UDisks2 uniquement à partir de son état initial connu ; examinez les anciennes règles sudoers avec visudo, les favoris Dolphin et les réglages RDP. Ne réinitialisez pas aveuglément les services. Sans inventaire APT fiable, conservez les paquets.

Après désinstallation, revenez dans votre dossier personnel, exécutez hash -r et vérifiez type -a vigil vigil-gui vigil-tui. Suivez ensuite le [guide d’installation](README.md).
