---
layout: default
parent: "Analyse"
title: "Antivirus"
nav_order: 265
---

# 🧪 Antivirus ClamAV — `vigil_clamav_scan.sh`

> `scripts/clamav/vigil_clamav_scan.sh` scanne les dossiers montés dans
> `/investigation/` à la recherche de **malwares** avec ClamAV (`clamscan`).

---

## 📖 En résumé

Le script liste les dossiers montés, permet de scanner **un dossier, plusieurs,
ou tous**, affiche une **barre de progression** pendant le scan (pourcentage,
fichiers traités, infectés, temps écoulé, temps restant estimé), colorise
la sortie (infectés / erreurs / avertissements), et génère
un **rapport PDF consolidé unique** rassemblant tous les dossiers scannés
(résumé global + détail par dossier + menaces). En mode non-interactif
(`--all --yes`), il scanne tous les dossiers sans confirmation — c'est ce
qu'utilise l'orchestrateur de scans.

Par défaut, **aucun fichier journal** `clamav_*.log` n'est écrit sur disque
(`--no-log`). La sortie clamscan est capturée temporairement le temps de
générer le PDF, puis supprimée. Utilisez `--log` pour conserver le journal
dans `$VIGIL_BASE/rapports/`. En mode interactif, l'opérateur choisit de
conserver un journal et de générer le PDF.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | génère / désactive le rapport PDF consolidé (activé par défaut) |
| `--log` / `--no-log` | conserve / ne conserve pas le journal `clamav_*.log` (désactivé par défaut) |
| `--all` | scanne tous les dossiers (non-interactif) |
| `--comment TXT` | commentaire du scan (non-interactif) |
| `--yes` | répond oui aux confirmations (non-interactif) |
| `--user NOM` | utilisateur effectuant le scan (écrase l'utilisateur actif) |
| `--archives` / `--no-archives` | scan du contenu des archives (voir ci-dessous) |
| `--size-unlimited` / `--size-limit` | mode de taille des fichiers (voir ci-dessous) |
| `--alert-encrypted` / `--no-alert-encrypted` | signaler les archives chiffrées (voir ci-dessous) |

## 🗜️ Scan du contenu des archives

**clamscan scanne déjà le contenu des archives par défaut**
(`--scan-archive=yes`, voir `clamscan --help`) : via libclamav, un zip (ou
7z, rar, tar, etc.) est ouvert, chaque fichier interne est extrait **en
mémoire** et scanné individuellement avec les signatures virales — c'est
pourquoi chaque fichier d'un zip est analysé avec ses propres signatures,
indépendamment de la signature du zip lui-même.

Le scan du contenu des archives est **forcé par défaut** : plus de
question interactive, et `--scan-archive=yes` est passé **explicitement**
à clamscan (on ne compte pas sur le défaut implicite de libclamav, qui
peut varier selon la version ou la configuration). `--no-archives`
(override CLI uniquement) transmet `--scan-archive=no` : les archives
ne sont pas ouvertes et seul le fichier zip est scanné — utile pour
accélérer le scan de gros volumes sans archives.

## 📐 Taille des fichiers scannés

**Par défaut, clamscan saute les fichiers de plus de 25 Mo**
(`--max-filesize=25M`) et ne scanne que les 100 premiers Mo du contenu
d'une archive (`--max-scansize=100M`). Sur une clé contenant de gros
fichiers (ISO, vidéos, images disque...), ceux-ci ne sont donc **pas
analysés** par défaut.

La taille est **illimitée par défaut, sans question interactive** :

| Mode | Options clamscan | Effet |
|---|---|---|
| Illimité (**défaut**, appliqué d'office) | `--max-filesize=2047M --max-scansize=2047M` | tous les fichiers, même volumineux, analysés intégralement — 2047 Mo est le plafond **réel** de ClamAV (2 GiB - 1 = 2147483647 octets) : au-delà, libclamav refuse de scanner et émet un warning |
| Limité (override CLI `--size-limit`) | `--max-filesize=512M --max-scansize=512M` | fichiers et contenu d'archive de plus de 512 Mo ignorés — assez large pour ne rien sauter d'utile (archives comprises) tout en évitant les fichiers monumentaux |

Les options utilisées figurent sur le rapport PDF (traçabilité).

## 🔒 Archives chiffrées

**clamscan ne peut pas ouvrir une archive protégée par mot de passe**
(zip `-P`, rar, 7z chiffrés). Sans option particulière, une telle archive
est **ignorée en silence** : aucun résultat, aucun avertissement — le
rapport ne montre rien alors que son contenu n'a pas été analysé.

Le signalement des archives chiffrées est **forcé par défaut** : plus de
question interactive. `--alert-encrypted` est transmis à clamscan :
l'archive est alors signalée comme `Heuristics.Encrypted.Zip` (ou
`.Rar`, `.7z`...) et figure dans les menaces du rapport PDF —
l'opérateur sait explicitement qu'elle n'a pas pu être analysée.
`--no-alert-encrypted` (override CLI uniquement) désactive ce
signalement. Les menaces dans les archives **non chiffrées** sont, elles,
détectées et listées normalement (ClamAV extrait et scanne le contenu
en mémoire, signatures de contenu comme de hachage).

## 🔄 Déroulement

1. **Bannière ASCII** « VIGIL » suivie d'un **tableau récapitulatif**
   des options (utilisateur, archives, taille max, archives chiffrées,
   journal, PDF) après chaque `clear`.
2. **Liste** des dossiers sous `/investigation/`.
3. **Sélection** interactive (ou `--all`).
4. **Comptage** des fichiers du dossier (alimente la barre).
5. **Scan** récursif via `clamscan`, avec barre de progression :
   `[#####.............................]  42% 123/292 fichiers | infectés : 0 | écoulé 00:02:14 | reste ~00:03:01`.
   clamscan n'offre pas d'option de progression : le scan s'effectue donc
   sans `--infected` afin d'imprimer chaque fichier (`chemin: OK`), ce qui
   alimente la barre. Les menaces et erreurs s'affichent au fil de l'eau ;
   les fichiers OK sont comptés silencieusement. Le journal conserve la
   sortie complète. Remarque : le comptage initial ne voit pas l'intérieur
   des archives ; sur des archives volumineuses, le pourcentage reste une
   estimation (plafonnée à 99 % pendant le scan). Sur un gros périphérique,
   le comptage préalable (`find`) peut prendre un peu de temps.
6. **Rapport PDF consolidé** (un seul PDF pour tous les dossiers scannés).

## 🎼 Variante « scan complet »

`scripts/clamav/vigil_clamav_full_scan.sh` **enchaine** en un seul terminal :

1. montage d'un périphérique (`vigil_usb_mount.sh`) ;
2. scan antivirus (`vigil_clamav_scan.sh --all --yes --comment ""`) ;
3. démontage (`vigil_usb_umount.sh`).

Il propage `--pdf`/`--no-pdf`, `--log`/`--no-log`, `--user`,
`--archives`/`--no-archives`, `--size-unlimited`/`--size-limit` et
`--alert-encrypted`/`--no-alert-encrypted` au scan ClamAV (PDF activé
par défaut, journal désactivé par défaut). Le scan du contenu des
archives (`--scan-archive=yes` explicite), le signalement des archives
chiffrées et la taille illimitée (plafond réel ClamAV : 2047M) sont
**forcés par défaut, sans aucune question** après le choix de
l'utilisateur. Un **tableau récapitulatif** des options s'affiche après
chaque bannière d'étape (1/3, 2/3, 3/3).

**Utilisateur** : le script ne demande jamais de saisir un nom libre. Si un
utilisateur est passé en argument (`--user NOM` ou `--user=NOM`), il est
utilisé tel quel. Sinon, les utilisateurs configurés (`data/users/`) sont
listés et l'opérateur en choisit un par numéro. Sans utilisateur configuré,
le script s'arrête avec un message explicite. En environnement non
interactif (stdin fermé), l'utilisateur actif est repris s'il existe, sinon
le premier utilisateur configuré est sélectionné automatiquement.

Ce script n'est pas branché sur un bouton de la GUI : l'action antivirus
de la page d'accueil est la **recherche de menaces**
(`vigil_malware_hunt.sh` — voir [Recherche de menaces](menaces.md)).
`vigil_clamav_full_scan.sh` se lance en CLI.


## 🔗 Voir aussi

- [Recherche de menaces](menaces.md) — le bouton de l'accueil
- [Scan complet](orchestrateur.md)
- [Mise à jour ClamAV](../configuration/clamav.md)
