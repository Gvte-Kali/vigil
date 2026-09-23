---
layout: default
parent: "Actions"
title: "Recherche de menaces"
nav_order: 21
---

# 🛡️ Recherche de menaces

> Bouton **« Recherche de menaces »** de la section Actions — orchestrateur
> `scripts/clamav/vigil_malware_hunt.sh`, lancé dans un terminal **Konsole**
> après une boîte de confirmation récapitulant les étapes.

---

## 📖 En résumé

La recherche de menaces (« la chasse ») est une chaîne **complète et
autonome** : on branche un périphérique, Vigil le monte en lecture seule,
recense ses fichiers, audite les suspects, les scanne avec ClamAV, démonte
le périphérique et produit **un seul rapport PDF consolidé**. Elle n'est
liée à **ni un projet ni une custody projet** — tout le temporaire vit
dans `hunt/`, purgé à chaque chasse.

---

## 🎬 Workflow complet

```text
┌─────────────────────────────────────────────────────────────────┐
│  [Bouton GUI] Recherche de menaces                              │
│      └─ boîte de confirmation (récap des 5 étapes)              │
│      └─ lancement Konsole                                      │
└───────────────┬─────────────────────────────────────────────────┘
                ▼
1/5  MONTAGE RO ──────── scripts/analyse/vigil_usb_mount.sh
                ▼
2/5  RECENSEMENT ────── scripts/analyse/vigil_census.sh
                        --no-project --no-pdf --json-out hunt/collect
                ▼
3/5  AUDIT FORMAT ────── scripts/analyse/vigil_format_audit.py
                        --index hunt/census_*.sqlite
                        --out hunt/collect/vigil_formataudit.json
                ▼
4/5  SCAN CLAMAV ─────── scripts/clamav/vigil_clamav_scan.sh
                        --all --yes --no-pdf --json-out hunt/collect
                ▼
5/5  DÉMONTAGE ────────── scripts/analyse/vigil_usb_umount.sh
                ▼
    PDF CONSOLIDÉ ─────── scripts/pdf/vigil_pdf.py --kind multi
                          (triage USB + ClamAV + audit + census + custody)
                ▼
    EXPORT PREUVES ────── archive tar.gz + .sha256 (optionnel, kdialog/zenity)
                ▼
    PURGE hunt/ ───────── rm -rf hunt/* (dossier conservé, vide)
```

---

## 🔄 Détail des 5 étapes

### Étape 1/5 — Montage en lecture seule (`vigil_usb_mount.sh`)

1. **Vérifications préalables** : présence des outils, de `/investigation`,
   des listes USB.
2. **Triage USB anti-Rubber Ducky** : demande de débrancher les
   périphériques, **baseline USB** (`lsusb`), branchement du périphérique,
   décompte de 10 s avec barre de progression (purge du tampon clavier).
   - Un clavier HID apparu au branchement et **non whitelisté** est
     **bloqué** (unbind `usbhid`) et signalé.
   - Whitelist / blacklist persistantes (`data/usb/whitelist.txt`,
     `blacklist.txt`) — gérées depuis la page
     [Périphériques USB](../configuration/peripheriques-usb.md).
   - Le rapport de triage (`rapport_usbhid`) est **consolidé** dans le PDF
     final : aucun PDF autonome n'est écrit pendant la chasse
     (`VIGIL_MOUNT_TRIAGE_JSON_OUT`).
3. **Sélection du périphérique** : liste des disques/partitions avec
   type, taille, système de fichiers.
4. **Verrouillage** : `blockdev --setro` sur le disque entier, vérification
   de l'état RO, montage **partition par partition** dans
   `/investigation/<point-de-montage>` avec
   `ro,noexec,nosuid,nodev,noatime`.
5. **Chaîne de custody** : hash d'arbre SHA-256 de chaque partition
   montée, consigné dans le journal de la chasse.

**Cas particulier — arrêt au triage** : si le seul périphérique détecté est
un clavier suspect bloqué (ou un périphérique blacklisté), la chasse
s'arrête **proprement** : rien n'est monté, le PDF consolidé est quand même
généré avec la seule section triage USB.

### Étape 2/5 — Recensement (`vigil_census.sh`)

Inventaire **intégral et neutre** de tout ce qui est monté dans
`/investigation/` :

1. Recense **tous les fichiers** : chemin, taille, dates
   (mtime/atime/ctime/btime), mode/uid/gid.
2. **Normalise les dates en UTC** et conserve une indication du système de
   fichiers (FAT = heure locale, NTFS = UTC) pour l'interprétation
   forensique.
3. **Détecte le type MIME** via `file` et normalise les types bureautiques.
4. **Dédoublonne par hash MD5** de contenu — les doublons sont **marqués**
   (`is_duplicate`, `duplicate_of`, `duplicate_group`), jamais retirés.
5. Applique **checksafe** si des bases de noms/hashes sont présentes dans
   `/stockage` (filtre fourni par l'autorité).
6. Écrit l'index **SQLite** dans `hunt/` (`--no-project` : pas de base
   dans un projet), l'exporte en TSV, le **signe** (SHA-256 + horodatage
   opérateur) — **sans PDF propre** (`--no-pdf`).

L'index SQLite (`hunt/census_*.sqlite`) alimente l'étape 3 et la section
recensement du rapport final.

### Étape 3/5 — Audit de format ciblé (`vigil_format_audit.py`)

Analyse du **contenu** des fichiers suspects sélectionnés dans l'index :

1. **Cibles — extensions trompeuses** : fichiers dont l'extension ne
   correspond pas au contenu détecté (`extension_mismatch=1` dans
   l'index) — ex. un `.jpg` qui est en réalité un exécutable.
2. **Cibles — forte entropie** : fichiers `application/octet-stream` dont
   le contenu est fortement compressible/aléatoire (données chiffrées ou
   compressées camouflées, seuil 7.5 bits/octet).
3. **Pour chaque cible** :
   - **entropie estimée** (ratio de compression zlib sur les premiers Mo) ;
   - **signatures forensiques locales**
     (`config/forensic_signatures.json`) pour identifier le contenu réel ;
   - **binwalk** (si installé) borné aux premiers Mo : détection de
   signatures internes et de **données concaténées après la fin officielle**
   du fichier (steganographie simple, padding caché).
4. Résultat : `hunt/collect/vigil_formataudit.json`, consolidé dans le
   rapport.

### Étape 4/5 — Scan antivirus (`vigil_clamav_scan.sh`)

1. Scan **récursif de tous les dossiers montés** (`--all`), sans
   confirmation (`--yes`), avec **barre de progression** (pourcentage,
   fichiers traités, infectés, temps écoulé/restant).
2. **Valeurs forcées** (sauf override CLI, voir
   [Antivirus](antivirus.md)) : contenu des archives scanné
   (`--scan-archive=yes` explicite), taille illimitée au plafond réel
   ClamAV (`--max-filesize=2047M --max-scansize=2047M`), archives
   chiffrées signalées (`--alert-encrypted`).
3. **Pas de PDF propre** (`--no-pdf`) : les journaux clamscan sont exportés
   en JSON (`--json-out hunt/collect/`) pour la section antivirus du
   rapport consolidé, puis supprimés.

### Étape 5/5 — Démontage et rapport consolidé

1. **Démontage** (`vigil_usb_umount.sh`) : vérification d'intégrité (hash
   d'arbre initial vs recalculé), démontage partition par partition,
   remise du disque en lecture/écriture, suppression des points de
   montage.
2. **Assemblage du PDF unique** (`vigil_pdf.py --kind multi`) —
   **ordre des sections** :
   1. **Triage USB** (détection Rubber Ducky) ;
   2. **ClamAV** (menaces virales) ;
   3. **Audit de format** (extensions trompeuses, entropie) ;
   4. **Recensement** (inventaire, purement informatif) ;
   5. **Chaîne de custody** (tableau chronologique).
3. **Export des preuves** (optionnel) puis **purge** de `hunt/`.

---

## 👤 Utilisateur et opérateur

La chasse exige un **opérateur** (journal de custody) mais **pas de
projet** :

- `--user NOM` (ou `--user=NOM`) en argument → utilisé tel quel ;
- sinon utilisateur actif (`data/active_user`) s'il existe ;
- sinon **liste interactive** des utilisateurs configurés
  (`data/users/`), choix par numéro ;
- environnement non interactif (stdin fermé) : le **premier** utilisateur
  configuré.

L'opérateur est **propagé à toute la chaîne** : `--user` pour le
recensement et le scan, `VIGIL_ACTIVE_USER` pour le montage/démontage —
même sans `data/active_user`.

---

## 🔒 Mode autonome (sans projet)

- Aucun projet requis ni modifié (`data/active_project` n'est ni lu ni
  écrit) ; le rapport n'est pas copié dans un dossier de projet.
- La **page de garde** du rapport note « Recherche de menaces » comme
  projet.
- Tout le temporaire vit dans `$VIGIL_BASE/hunt/` (index SQLite du
  recensement, JSON de collecte, journaux clamscan, triage USB),
  **purgé au début de chaque chasse** : chaque exécution repart d'un
  état propre.

---

## 📄 Chaîne de custody de la chasse

La chasse tient **son propre journal** : `hunt/chain_of_custody.json`
(JSONL, une entrée par action). Chaque étape y est enregistrée avec
horodatage, opérateur, action, statut et détail — **en succès comme en
erreur** : démarrage, montage, triage (périphérique suspect bloqué),
recensement, audit de format, scan ClamAV, démontage, clôture, export.

Le journal est **alimenté par toute la chaîne** : la chasse exporte
`VIGIL_HUNT_CUSTODY` et `VIGIL_ACTIVE_USER`, et les sous-scripts
(montage, démontage, recensement) y écrivent leurs événements détaillés —
création du hash d'arbre SHA-256, passage du disque en lecture seule,
montages partition par partition, vérification d'intégrité au démontage,
remise en lecture/écriture, suppression des points de montage.

Ce journal alimente la section **« Chaîne de custody »** du rapport
consolidé : tableau chronologique (horodatage, opérateur, action, statut
coloré, détail), référencée dans le sommaire.

---

## 📤 Export des preuves et purge

En fin de chasse, une fois le rapport généré :

1. Question **« Exporter une archive des preuves avant suppression ? »**
   `[o/N]` (proposée uniquement si un PDF a été généré, et seulement en
   mode interactif) ;
2. Si accepté : **boîte de dialogue système** de choix du dossier
   (`kdialog --getexistingdirectory`, sinon `zenity --file-selection
   --directory`, sinon saisie terminal) ;
3. Archive `export_menaces_<jj-mm-aaaa>_<hh>h<mm>m<ss>s.tar.gz`
   contenant **tout `hunt/` + le rapport PDF** ;
4. Fichier `.sha256` adjacent : checksum au format `sha256sum`
   (vérifiable avec `sha256sum -c`) ;
5. **Purge complète** du contenu de `hunt/` (le dossier reste, vide,
   pour la chasse suivante).

**Si l'export échoue** (destination annulée ou invalide, erreur d'archive
ou de checksum), la purge est **annulée** : les preuves restent sur place
plutôt que d'être perdues. La question et la purge ont lieu sur les trois
chemins de sortie : chasse complète, arrêt au triage (avec PDF de
triage), échec du montage (sans PDF, purge directe).

---

## 📝 Nom du rapport

Après la sélection de l'utilisateur, l'opérateur peut donner un **nom**
au rapport (Entrée = nomenclature par défaut) :

- sans nom : `rapport_menaces_<jj-mm-aaaa>_<hh>h<mm>m<ss>s.pdf` ;
- avec un nom : `<nom>_rapport_menaces_<jj-mm-aaaa>_<hh>h<mm>m<ss>s.pdf`.

Le nom est nettoyé automatiquement (minuscules, accents et caractères
spéciaux supprimés, espaces remplacées par des tirets) pour rester un nom
de fichier portable. Le préfixe est transmis à `vigil_pdf.py` via
`--fname-prefix`.

---

## 🔗 Voir aussi

- [Antivirus](antivirus.md) — options détaillées du scan ClamAV
- [Montage lecture seule](montage-lecture-seule.md) — triage USB détaillé
- [Rapports PDF](../rapports-pdf/README.md) — le générateur consolidé
