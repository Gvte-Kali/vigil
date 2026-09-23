---
layout: default
parent: "Analyse"
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
de la page d'accueil est la **recherche de menaces** (`vigil_malware_hunt.sh`,
voir ci-dessous). `vigil_clamav_full_scan.sh` se lance en CLI.

## 🔗 Voir aussi

- [Scan complet](orchestrateur.md)
- [Mise à jour ClamAV](../configuration/clamav.md)

---

## 🧭 Orchestrateur « Recherche de menaces » — `vigil_malware_hunt.sh`

> `scripts/clamav/vigil_malware_hunt.sh` (bouton **« Recherche de menaces »**
> de la page d'accueil) enchaîne en un seul terminal, en **5 étapes** :
>
> 1. **Montage** du périphérique en lecture seule (interactif, triage USB inclus) ;
> 2. **Recensement** autonome (`vigil_census.sh --no-project --no-pdf` :
>    index SQLite + audit extension/MIME, sans PDF propre — les résultats
>    alimentent le rapport consolidé final) ;
> 3. **Audit de format ciblé** (`vigil_format_audit.py`) : binwalk/signatures
>    sur les fichiers dont l'extension ment (extension trompeuse) et les
>    octet-stream à forte entropie ;
> 4. **Scan antivirus ClamAV** sur tous les dossiers montés (`--all --yes`) ;
> 5. **Démontage** puis **un seul PDF consolidé** (`vigil_pdf.py --kind multi`).
>
> Le triage USB du montage (`rapport_usbhid` en montage autonome) est
> **consolidé dans ce rapport unique** pendant la chasse : aucun
> `rapport_usbhid_*.pdf` autonome n'est généré, la section « triage
> USB » (détection Rubber Ducky) ouvre le rapport consolidé. Si le montage
> s'arrête au triage (seul périphérique = clavier suspect bloqué), la
> chasse s'arrête proprement et le rapport consolidé est quand même
> généré avec cette seule section.

### Côté GUI

Depuis la page d'accueil (`vigil_main_gui.py`), le bouton **« Recherche de
menaces »** (icône `shield`, barre d'accent verte) affiche d'abord une
**boîte de confirmation** récapitulant les 5 étapes, puis lance le script
dans un terminal **Konsole**. La chasse est autonome : la GUI n'exige ni
utilisateur actif ni projet — l'opérateur est sélectionné **dans le
terminal** (voir ci-dessous).

Le scan ClamAV y est appelé avec `--no-pdf --json-out` : les journaux
clamscan sont copiés dans un dossier de collecte temporaire pour alimenter
la section antivirus du rapport consolidé, puis supprimés (comportement
identique à `--no-log`). L'option `--json-out DIR` est disponible sur
`vigil_clamav_scan.sh` pour tout autre usage d'assemblage.

### Utilisateur et opérateur

La chasse exige un **opérateur** (journal de custody) mais **pas de
projet**. Si un utilisateur est passé en argument (`--user NOM` ou
`--user=NOM`) ou qu'un utilisateur actif existe (`data/active_user`),
il est repris tel quel. Sinon, les utilisateurs configurés
(`data/users/`) sont listés et l'opérateur en choisit un par numéro
(environnement non interactif : le premier utilisateur configuré).
L'opérateur est propagé à toute la chaîne : `--user` pour le
recensement et le scan, `VIGIL_ACTIVE_USER` pour le montage/démontage —
même sans `data/active_user`.

### Overrides ClamAV

Le hunt propage les overrides au scan ClamAV : `--pdf`/`--no-pdf`,
`--log`/`--no-log`, `--no-archives`, `--size-limit`,
`--no-alert-encrypted`. En leur absence, les valeurs **forcées par
défaut** s'appliquent (contenu des archives scanné, taille illimitée
au plafond réel ClamAV, archives chiffrées signalées — voir les
sections dédiées ci-dessus).

### Ordre du rapport consolidé

Le PDF unique assemble les sections dans cet ordre : **triage USB**
(usbhid), puis les **menaces** d'abord — **ClamAV**, puis **audit de
format** —, ensuite le **recensement** (purement informatif), et la
**chaîne de custody** en toute dernière section. Seules les anomalies sont
mises en avant (menaces, extensions trompeuses, forte entropie,
archives chiffrées).

### Mode autonome (sans projet)

La chasse n'est **pas liée à un projet** : aucun projet n'est requis, aucun
projet n'est modifié (`data/active_project` n'est ni lu ni écrit), et le
rapport consolidé n'est pas copié dans un dossier de projet. La page de
garde du rapport note « Recherche de menaces » comme projet.

Tout le temporaire de la chasse vit dans un dossier unique :
`$VIGIL_BASE/hunt/` (`/opt/vigil/hunt/` par défaut — index SQLite du
recensement autonome, JSON de collecte, journaux clamscan, triage USB).
Ce dossier est **purgé au début de chaque chasse** : chaque exécution
repart d'un état propre, sans accumulation.
L'index du recensement y est écrit via `vigil_census.sh --no-project`
(sans écriture dans le `chain_of_custody.log` d'un projet : ce n'est pas
un livrable forensique projet mais un temporaire de chasse).

### Chaîne de custody de la chasse

La chasse tient **son propre journal de custody** :
`hunt/chain_of_custody.json` (JSONL, une entrée par action). Chaque
étape y est enregistrée avec horodatage, opérateur, action, statut et
détail : démarrage, montage, triage (périphérique suspect bloqué),
recensement, audit de format, scan ClamAV, démontage, clôure — en
succès comme en erreur.

Le journal est **alimenté par toute la chaîne** : la chasse exporte
`VIGIL_HUNT_CUSTODY` et `VIGIL_ACTIVE_USER`, et les sous-scripts
(montage, démontage, recensement) y écrivent leurs événements
détaillés — création du hash d’arbre SHA-256 (avec sa valeur),
passage du block device en lecture seule, montages partition par
partition, vérification d’intégrité au démontage (hash initial vs
recalculé), remise en lecture/écriture, suppression des points de
montage. L’opérateur choisi au démarrage de la chasse est propagé à
tous les sous-scripts (`--user` pour le recensement et le scan,
`VIGIL_ACTIVE_USER` pour le montage/démontage), même sans
`data/active_user`. Ce journal alimente la section « Chaîne de
custody » du rapport consolidé : **tableau chronologique**
(horodatage, opérateur, action, statut coloré, détail), répertoriée
dans le sommaire. Comme tout le contenu de `hunt/`, il est purgé au
début de chaque nouvelle chasse.

En fin de chasse, une fois le rapport PDF généré, l'opérateur peut
**exporter une archive des preuves** avant la purge, puis **tout le
contenu de `hunt/` est supprimé** (le dossier `hunt/` reste, vide, pour
la chasse suivante) — aucune trace résiduelle ne reste sur la machine
d'analyse. Le déroulé :

1. question `Exporter une archive des preuves avant suppression ? [o/N]`
   (proposée uniquement si un PDF a été généré) ;
2. si accepté : **boîte de dialogue système** de choix du dossier de
   destination (`kdialog --getexistingdirectory`, sinon
   `zenity --file-selection --directory`, sinon saisie terminal) ;
3. archive `export_menaces_<jj-mm-aaaa>_<hh>h<mm>m<ss>s.tar.gz` dans le
   dossier choisi, contenant **tout `hunt/` + le rapport PDF** de la
   chasse ;
4. fichier `.sha256` adjacent : checksum SHA-256 de l'archive au format
   `sha256sum` (vérifiable avec `sha256sum -c`) ;
5. purge complète du contenu de `hunt/`.

Si l'export échoue (destination annulée ou invalide, erreur d'archive ou
de checksum), la purge est **annulée** : les preuves restent sur place
plutôt que d'être perdues. La question et la purge ont lieu sur les
trois chemins de sortie (chasse complète, arrêt au triage avec le PDF
de triage, échec du montage — dans ce dernier cas sans PDF, la purge
directe). En mode non interactif (sans terminal), la purge a lieu sans
question.

### Nom du rapport

Après la sélection de l'utilisateur, l'opérateur peut donner un **nom** au
rapport (Entrée = nomenclature par défaut). Le fichier produit :

- sans nom : `rapport_menaces_<jj-mm-aaaa>_<hh>h<mm>m<ss>s.pdf` ;
- avec un nom : `<nom>_rapport_menaces_<jj-mm-aaaa>_<hh>h<mm>m<ss>s.pdf`.

Le nom est nettoyé automatiquement (minuscules, accents et caractères
spéciaux supprimés, espaces remplacées par des tirets) pour rester un nom
de fichier portable. Ce préfixe est transmis à `vigil_pdf.py` via
`--fname-prefix` (mode multi uniquement).
