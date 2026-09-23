# 🔍 Analyse forensique

> Une fois un périphérique monté **en lecture seule** dans `/investigation`,
> Vigil peut lancer une série d'**analyses de fichiers**. Chaque analyse est un
> script Bash indépendant, lançable seul ou via l'**orchestrateur de scans**.

---

## 📖 En résumé

1. On **monte** le périphérique en lecture seule (`vigil_usb_mount.sh`).
2. On **lance** une ou plusieurs analyses (images, vidéos, audio, bureautique,
   archives, fichiers verrouillés, forte entropie, fichiers volumineux, antivirus).
3. Chaque analyse **détecte** les fichiers concernés, calcule leur **SHA-256**,
   agrège des **statistiques**, et génère un **rapport PDF** normalisé.
4. On **démonte** le périphérique (`vigil_usb_umount.sh`).

Les rapports sont rangés dans `/opt/vigil/rapports/`. Les chemins affichés dans
les rapports conservent le **dossier racine de la partition** (nom de partition),
indicateur pertinent pour une enquête.

---

## 🗺️ Sommaire

### 📌 Montage / démontage
- [Montage en lecture seule](montage-lecture-seule.md) — `vigil_usb_mount.sh`
- [Démontage](demontage.md) — `vigil_usb_umount.sh`

### 🧪 Analyses de fichiers (script `scripts/analyse/`)
- [Recensement des fichiers](recensement.md) — `vigil_census.sh`
- [Images](images.md) — `vigil_images.sh`
- [Vidéos](videos.md) — `vigil_videos.sh`
- [Audio](audio.md) — `vigil_audio.sh`
- [Bureautique](bureautique.md) — `vigil_office.sh`
- [Archives](archives.md) — `vigil_archives.sh`
- [Fichiers verrouillés (crypto)](crypto.md) — `vigil_crypto.sh`
- [Forte entropie](entropie.md) — `vigil_entropy.sh`
- [Fichiers volumineux](volumineux.md) — `vigil_bigfiles.sh`
- [Détection des visages](visages.md) — `vigil_faces_detection.sh`

### 🛡️ Antivirus (séparé — pas de custody, pas de projet)
- [Antivirus ClamAV](antivirus.md) — `vigil_clamav_scan.sh` / `vigil_clamav_full_scan.sh`
  (lancé depuis la page d'accueil, hors page d'analyse)

### 🎼 Orchestrateur
- [Scan complet](orchestrateur.md) — `vigil_scan_all.sh`

### 📦 Export du projet
- [Export du projet](export.md) — `vigil_export_project.sh` (hash SHA-256 + archive + hash de l'archive)

---

## 📝 Projet obligatoire (chaine de custody)

Toutes les analyses de fichiers **exigent un projet actif** : sans projet
(ou projet `"(no-project)"`), le script s'arrête immédiatement avec un
message d'erreur. Le projet porte la **chaîne de custody** : chaque action
est journalisée dans `$PROJECTS_DIR/<projet>/chain_of_custody.log`.

**Exception : le scan antivirus ClamAV** (`vigil_clamav_scan.sh`) reste
lançable **sans projet**. Le scan AV n'étant pas une analyse forensique à
custody, il n'écrit pas dans la chaîne de custody et range ses rapports
dans `/opt/vigil/rapports/` (opérateur + entité seulement).

**Exception : la recherche de menaces** (`vigil_malware_hunt.sh`) est
également autonome : aucun projet requis ni modifié, tout son
temporaire (index census via `--no-project`, JSON de collecte, journaux
clamscan, triage USB) vit dans `hunt/` à la racine du dépôt, purgé
à chaque chasse.

Dans la GUI, la case « Pas de projet » a été retirée : le projet est
obligatoire pour lancer une analyse de fichiers. Le scan antivirus est
**totalement séparé** de la page d'analyse : il n'apparaît pas dans le
catalogue des scripts ni dans le multi-scan. Depuis la page d'accueil
(`vigil_main_gui.py`), l'action **« Recherche de menaces »** lance
`vigil_malware_hunt.sh` (montage → recensement → audit → scan → démontage),
autonome, sans custody et sans projet. L'utilisateur est choisi directement
dans le script (liste des utilisateurs configurés, ou `--user NOM` en
argument) : la GUI n'exige pas d'utilisateur actif.
`vigil_clamav_full_scan.sh` (montage → scan → démontage) et
`vigil_clamav_scan.sh` restent lançables en CLI, sans custody ni projet.

---

## 🧩 Points communs à toutes les analyses

- **Bannière ASCII** « VIGIL » affichée au démarrage, avec `clear`+bannière entre chaque étape.
- **Détection** via `file` (type MIME) et, selon le script, `exiftool`, `ffprobe`, `7za`, `zstd`.
- **SHA-256** de chaque fichier retenu (affiché à côté du chemin dans le rapport).
- **Statistiques** présentées **avant** la liste des fichiers dans le PDF.
- **Options** communes : `--pdf`/`--no-pdf` (rapport PDF), `--copy-to DIR` (copie des fichiers).
- **Rapport PDF** généré via le [générateur commun](../rapports-pdf/README.md) (`scripts/pdf/vigil_pdf.py`).

## 🖥️ Lancement depuis la GUI

La page **« Analyse du périphérique USB »** (`vigil_tools_gui.py`) permet :

- de **monter/démonter** un périphérique ;
- de choisir le **type de périphérique** (Tout afficher / Générique / Windows / XBOX 360)
  qui filtre dynamiquement les scripts disponibles ;
- de lancer un script **individuellement** avec ses options (cases à cocher) ;
- de **lancer plusieurs scans** (cases à cocher) en une fois.

Voir [interface-graphique](../interface-graphique/README.md).
