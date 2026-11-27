---
layout: default
title: Audit des autorisations
parent: Développement
nav_order: 18
grand_parent: Français
---

# Autorisations des scripts Vigil

Revue du code autour de `886ce03`. Inventaire reproductible avec
`git ls-files '*.sh' '*.py' scripts/Vigil-CLI/vigil scripts/post-install/vigil-qt scripts/privileged/vigil-mount`.
Pour localiser les appels et les mentions, utiliser
`git grep -nE '\bsudo\b|\$EUID|id -u|os\.geteuid' -- '*.sh' '*.py' scripts/privileged/vigil-mount`.
Les mentions dans une aide ou une procédure ne correspondent pas à un appel exécuté.

| Famille | Privilèges observés et politique |
|---|---|
| Montage investigation historique, `scripts/analyse/vigil_usb_mount.sh`, `vigil_usb_umount.sh` | Montage/démontage, verrouillage bloc et retour RW dans certains chemins, MTP/LUKS, sysfs USB/HID et journaux. Parcours administrateur historique. Le helper Qt remplace le montage USB ext4 et le démontage associé sous une autorisation dédiée. |
| Stockage, `scripts/stockage/vigil_stockage_{mount,umount}.sh` | Montage RW, déverrouillage, droits de destination et triage USB. Exiger l’identité du support et sa séparation des preuves avant une future délégation. |
| CLI historique, `scripts/Vigil-CLI/vigil_{mount,unmount,analyse}.sh` | Montage, MTP, bloc, antivirus et append de journaux sous sudo. `scripts/Vigil-CLI/vigil` est le brouillon de façade. Aucun droit supplémentaire attribué. |
| Acquisition et clonage, `scripts/imager/vigil_disk_{imager,clone}.sh` | Lecture brute, copie bloc, écriture de cible, verrouillage et opérations de partition. Réserver l’accès à l’administrateur avant un broker d’acquisition et des tests sur images synthétiques. |
| ClamAV historique, `scripts/clamav/vigil_clamav_scan.sh` | Appelle clamscan via sudo. Dans Qt, le scan d’un fichier accessible se fait avec les droits de l’opérateur. |
| Signatures ClamAV, `scripts/clamav/vigil_clamav_update{,_usb}.sh` | Le mode système pilote FreshClam et son service. Le mode USB peut modifier montages, état bloc et bases système. Qt limite FreshClam à son dossier de signatures et à l’exception AppArmor prévue. |
| Enchaînements, `scripts/vigil_scan_all.sh`, `scripts/clamav/vigil_{clamav_full_scan,malware_hunt}.sh` | Héritent des privilèges de leurs enfants. L’orchestration ne justifie aucun sudo générique. |
| Analyses de fichiers, tous les autres fichiers dans `scripts/analyse/` | Lecture avec les droits du compte et écriture dans les destinations de travail. Les références sudo des scripts images, audio, vidéos et visages figurent dans des conseils d’installation. Les outils Python d’index, checksafe et audit de format n’exigent pas root. |
| PDF et export, `scripts/pdf/vigil_pdf.py`, `scripts/export/vigil_export_project.sh` | Besoin de lire les dépendances et livrables, et d’écrire vers un dossier de travail. Garder les protections de destination et l’audit. |
| Installation et utilitaires, `scripts/post-install/post_install_vigil.sh`, `scripts/lsblk_wallpaper.sh`, `git-reset.sh` | Le post-install effectue une maintenance administrateur. Le papier peint peut demander une installation APT. Git nécessite les droits sur le clone uniquement. Le lanceur `vigil-qt` tourne sous l’opérateur. |
| GUI historique et Core Qt, `gui/`, `vigil/`, `tests/` | Config, opérateurs, preuves enregistrées et vues utilisent les droits utilisateur. L’ancienne GUI de configuration affiche des conseils sudo. La seule élévation depuis Qt est sudo vers les deux verbes du helper installé sous root. Les tests s’appuient sur des fixtures. |

## Zones

Le point d’ancrage **vide et démonté** `/investigation` doit être
`root:root` en `0755`. Certaines installations historiques le donnaient
à l’opérateur avec un chown récursif. Le post-install le prépare désormais
après vérification et refuse un chemin symbolique, monté ou non vide.
Cette opération vise le répertoire d’ancrage et ne change pas les droits
du volume de preuve. Les droits internes d’un système de fichiers ext4
monté restent ceux de la preuve. Les écritures dans l’affaire et les
exports utilisent les répertoires de travail de l’opérateur.

Le helper expérimental et sa règle sudo limitée restent soumis à la
[recette en VM](phase-01-transition.md). Les outils historiques dotés
d’un sudo générique n’obtiennent pas de nouvelles permissions dans
ce lot. Pour une preuve aux permissions restrictives, recetter un mode
de lecture dédié et journalisé avant sa délégation.
