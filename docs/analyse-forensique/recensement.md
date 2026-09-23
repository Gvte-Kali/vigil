---
layout: default
parent: "Analyse"
nav_order: 204
---

# 📋 Recensement des fichiers — `vigil_census.sh`

> `scripts/analyse/vigil_census.sh` réalise l'inventaire intégral et neutre des
> fichiers présents sur le périphérique monté dans `/investigation/`, les
> stocke dans une base **SQLite** (dans le dossier du projet), avec
> **dédoublonnage conservé** (les doublons sont marqués, pas jetés) et la
> logique **checksafe** conservée telle quelle (filtre par base de noms +
> base de hashes fournie par l'autorité).

Inspiré de `scalpel/bin/census` + `scalpel/bin/checksafe`.

---

## 📖 En résumé

Le script :

1. **recense** tous les fichiers de `/investigation/` (chemin, taille, dates
   mtime/atime/ctime/btime, mode/uid/gid) ;
2. **normalise** les dates en UTC (le FS — FAT=locale, NTFS=UTC — est conservé
   dans `inventory_meta` pour interprétation forensique) ;
3. **détecte** le type MIME via `file` et normalise les types Office (comme
   `scalpel/bin/census` : PowerPoint/Excel/Word → `office/...`, OLE →
   `windows/cdfv2`, chiffré → `office/microsoft.encrypted`) ;
4. calcule un **hash SHA-256** de contenu pour le
   dédoublonnage — `SHA-256` reste réservé aux fichiers réellement
   retenus/analysés par les scripts ciblés ;
5. **marque** les doublons (`is_duplicate`, `duplicate_of`, `duplicate_group`)
   sans les retirer de l'inventaire ;
6. applique **checksafe** (base de noms + base de hashes externe) si des bases
   sont présentes dans `/stockage` ;
7. écrit la base **SQLite** dans le dossier du projet actif, l'exporte en
   **TSV**, la **signe** (SHA-256 + horodatage opérateur) et génère un
   rapport PDF.

> ℹ️ L'**inventaire détaillé** de chaque fichier (chemin, hash SHA-256, taille,
> dates, type MIME, marquage des doublons/filtrage checksafe) est stocké dans la
> **base SQLite** et l'**export TSV** du dossier du projet — pas dans le PDF.
> Le rapport PDF se concentre sur les statistiques, le filtrage checksafe et
> les faits forensiques (doublons documentés) ; il se termine par une page de
> validation/signature de l'opérateur.

Le recensement est conçu pour être lancé **en tête** de la chaîne d'analyses :
les analyses ciblées peuvent ensuite consommer l'export TSV / la base SQLite.

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--no-dedup` | désactiver le marquage des doublons |
| `--no-checksafe` | désactiver le filtrage checksafe |

## 🔄 Déroulement

1. Bannière, puis **vérification** des périphériques montés dans `/investigation/`.
2. **Recensement** intégral via `find -printf` (chemin, taille, dates, mode/uid/gid).
3. **Détection MIME** via `file` + normalisation des types Office.
4. **Dédoublonnage** : groupage par hash de contenu, marquage des doublons
   (conservation, pas de suppression de l'inventaire).
5. **checksafe** : filtre par base de noms + base de hashes (`/stockage`).
6. **Base SQLite** dans le dossier du projet + export TSV + signature SHA-256.
7. **Rapport PDF** (statistiques **avant** la liste des fichiers + faits
   forensiques sur les doublons documentés).

## 🗄️ Base SQLite (livrable forensique)

La base est écrite dans le dossier du projet actif
(`$VIGIL_BASE/data/projects/<projet>/census_<horodatage>.sqlite`), jamais dans
`/investigation` (lecture seule) ni à la racine. Schéma :

- **`inventory_meta`** (1 ligne par recensement) : `device`, `serial`,
  `partition`, `fstype`, `mount_point`, `mount_options`, `blockdev_ro`,
  `operator`, `project`, `entity`, `started_at`, `ended_at`, `duration`,
  `total_files`, `duplicate_count`, `safe_filtered_count`,
  `checksafe_base_name` (présente ?), `checksafe_base_hash` (présente ?),
  `tool_versions`, `vigil_version`.
- **`files`** (1 ligne par fichier) : `id`, `inventory_id` (FK), `path`,
  `size`, `mtime`, `atime`, `ctime`, `btime`, `mime_type`, `mime_encoding`,
  `extension`, `mode`, `uid`, `gid`, `device`, `partition`, `content_hash`
  (SHA-256), `is_duplicate`, `duplicate_of`, `duplicate_group`,
  `is_safe_filtered`.
- **Index** : `(inventory_id, mime_type)`, `(inventory_id, mtime)`,
  `(content_hash)`, `(is_duplicate)`.

`python3 sqlite3` = stdlib : **zéro dépendance** à ajouter. La base est elle-même
un livrable forensique : signée en **SHA-256** + horodatage opérateur
(fichier `.sha256` accolé), comme une image disque.

### Un seul recensement par projet

Chaque exécution **remplace** la précédente : au démarrage, Vigil supprime
du dossier du projet les livrables du recensement antérieur
(`census_*.sqlite`, `census_*.tsv`, signatures `.sha256`, traces
`.sains.census_*` / `.doublons.census_*` et copie `rapport_census_*.pdf`)
avant d'écrire les nouveaux. Les montages/démontages successifs et les
relances du script n'accumulent donc **qu'un seul jeu de fichiers de
recensement** ; les autres livrables du projet (rapports des autres
analyses, custody, export) ne sont pas touchés.

### Mode autonome (`--no-project`, recherche de menaces)

L'orchestrateur « Recherche de menaces » appelle le recensement avec
`--no-project` : aucun projet n'est requis ni modifié, et l'index
SQLite + TSV + signature sont écrits dans `hunt/` (à la racine du
dépôt, purgé au début de chaque chasse) au lieu du dossier d'un projet.
Ce n'est pas un livrable forensique de projet : aucun événement de
chaîne de custody n'est tracé, et le dossier du projet actif n'est pas
touché. La purge « un seul recensement » s'applique à `hunt/` de la
même façon.

## 🔁 Dédoublonnage (conservé, marqué au lieu de jeté)

- Le mécanisme de groupage par contenu est conservé (comparaison par hash de
  contenu SHA-256 ; `duff` de scalpel comparait par taille puis octets).
- **Changement de sémantique** : on ne retire pas les doublons de
  l'inventaire. On les **marque** : `is_duplicate=1`, `duplicate_of=<représentant>`,
  `duplicate_group=<id>`.
- Les analyses ciblées ne traitent qu'un **représentant** par groupe (gain de
  temps), MAIS le rapport **documente tous les emplacements** (« cette image
  existait en 3 exemplaires ») — fait forensique.

## 🛡️ Logique checksafe (conservée telle quelle)

Reprise à l'identique de `scalpel/bin/checksafe` (filtre par base de noms +
base de hashes). Point non négociable : les autorités ont des bases que Vigil
n'a pas.

- Bases externes recherchées dans `/stockage` (`files.safe.name` /
  `files.safe.hash`) — config de l'opérateur/autorité, **pas dans Vigil**.
- Bases au format pickle (set Python), comme `scalpel/bin/checksafe`.
- **Comportement sans base** : checksafe ne filtre rien (tout reste à
  analyser) — c'est attendu et **documenté dans le rapport** (base absente).
- Sémantique exacte de scalpel : si la base de noms est vide (`None`), la
  signature est systématiquement vérifiée auprès de la base des signatures ;
  si la base des signatures est vide, rien n'est marqué sain (pas de filtre).
- **Journalisation** dans la chaîne de custody : base utilisée ou non, nombre
  de fichiers retirés comme « sains ».
- Production des fichiers `.sains.*` et `.doublons.*` (trace), comme
  `scalpel/bin/census`.

## 🔗 Voir aussi

- [Orchestrateur](orchestrateur.md) — `vigil_scan_all.sh`
- [Générateur PDF](../rapports-pdf/README.md)

---

## 🕵️ Audit des extensions trompeuses

Depuis la phase 4, le recensement compare l'extension de chaque fichier au
format réel de son contenu (via `file --mime-type` et la table
`config/ext_mime_map.json`) :

- `extension_mismatch=1` : l'extension **ment** sur le contenu (ex. un
  `.jpg` qui est en réalité un exécutable Windows) ;
- `expected_format` : le format attendu pour cette extension.

Les fichiers sans extension ou avec extension inconnue de la table ne sont
pas flagués (les fichiers système sans extension sont légion — bruit trop
important).

Faux positifs neutralisés :

- **fichier vide** (0 octet) : `file` renvoie `inode/x-empty`, aucune
  extension ne peut mentir sur un contenu inexistant → jamais flagué ;
- **MIME normalisé par le recensement** (`office/microsoft.*`,
  `windows/cdfv2`) : ces étiquettes sont internes à Vigil (sed de
  normalisation), la table `ext_mime_map.json` compare les MIME bruts de
  `file --mime-type`. Le recensement remplace donc les étiquettes normalisées
  par leur équivalent `file` avant comparaison (ex. un `.doc` LibreOffice,
  détecté `application/x-ole-storage` puis affiché `windows/cdfv2`, est
  comparé comme `application/x-ole-storage`, un format toléré).

Ces colonnes sont stockées dans la base SQLite et l'export TSV du projet,
affichées dans une section « Extensions trompeuses » du rapport PDF, et
servent de cibles à l'audit de format ciblé de la recherche de menaces.

> ℹ️ Les scripts d'analyse peuvent requêter l'index via
> `scripts/analyse/vigil_census_query.py` (`--mismatched`, `--octet-stream`,
> `--mime image/`, `--extension jpg`) au lieu de re-parcourir /investigation.

---

## 🧪 Recherche de menaces — `vigil_malware_hunt.sh`

> `scripts/clamav/vigil_malware_hunt.sh` est l'orchestrateur « Recherche de
> menaces » de la page d'accueil : montage lecture seule → recensement
> autonome (`--no-project`, index temporaire dans `hunt/`, sans PDF
> propre) → audit de format ciblé
> (`vigil_format_audit.py` : binwalk + signatures forensiques locales sur
> les extensions trompeuses et les octet-stream à forte entropie) → scan
> ClamAV → démontage → **un seul rapport PDF consolidé**.

L'audit de format (`vigil_format_audit.py`) cible uniquement :

1. les fichiers avec extension trompeuse (`extension_mismatch=1`) ;
2. les fichiers `application/octet-stream` à forte entropie (≥ 7.5,
   échantillon 4 Mo — données chiffrées/compressées).

Pour chaque cible : entropie Shannon, ratio de compression, signatures
forensiques locales (`config/forensic_signatures.json` : PE, ZIP, 7z, EVTX,
LZMA...) et binwalk ciblé (si installé, borné aux premiers 8 Mo). Un
exécutable renommé `.jpg` sera identifié « Executable Windows (PE/COFF) »
dans le rapport.
