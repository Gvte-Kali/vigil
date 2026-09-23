#!/bin/bash
set -uo pipefail

# --- Recensement et dedoublonnage des fichiers ---
#
# Inspire de scalpel/bin/census + scalpel/bin/checksafe : inventaire integral et
# neutre des fichiers presents sur le support analyse, stocke dans une base
# SQLite (dans le dossier du projet), avec dedoublonnage CONSERVE (les doublons
# sont marques, pas jetes) et logique checksafe CONSERVEE telle quelle (filtre
# par base de noms + base de hashes fournis par l'autorite).
#
# Le script :
#   1. recense tous les fichiers de /investigation/ (chemin, taille, dates
#      mtime/atime/ctime/btime, mode/uid/gid) ;
#   2. normalise les dates en UTC + conserve une indication du FS (FAT=locale,
#      NTFS=UTC) pour interpretation forensique ;
#   3. detecte le type MIME via `file` et normalise les types office (comme
#      scalpel/bin/census) ;
#   4. calcule un hash MD5 de contenu pour le dedoublonnage ;
#   5. marque les doublons (is_duplicate, duplicate_of, duplicate_group) sans
#      les retirer de l'inventaire ;
#   6. applique checksafe (filtre par base de noms + base de hashes externe)
#      si des bases sont presentes dans /stockage ;
#   7. ecrit la base SQLite dans le dossier du projet actif, l'exporte en TSV,
#      la signe (SHA-256 + horodatage operateur) et genere un rapport PDF.
#
# Conventions Vigil :
#   - lecture seule sur /investigation (jamais d'ecriture sur le support) ;
#   - chaine de custody (active_user obligatoire, active_project pour la base
#     SQLite) ;
#   - rapports PDF via scripts/pdf/vigil_pdf.py (kind=census) ;
#   - chemins relatifs a la racine de partition dans les rapports.

# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
GREY='\e[90m'
BOLD='\e[1m'
NC='\e[0m'

print_banner() {
    echo -e "${BLUE}"
    cat <<'VIGILART'
█   █ ███  ███  ███ █     
█   █  █  █    █  █     
█   █  █  █  ██  █     
 █ █   █  █   █  █     
  █   ███ ███  ██████ 
VIGILART
    echo -e "${NC}"
}

ERRORS=0

VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
export VIGIL_BASE VIGIL_DATA_DIR
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
STOCKAGE_DIR="${VIGIL_STOCKAGE_DIR:-/stockage}"
STAMP=$(date +"%Y%m%d_%H%M%S")
WORK_DIR=$(mktemp -d -t "vigil_census_${STAMP}.XXXXXX")
RAPPORTS_DIR="$VIGIL_BASE/rapports"

# --- Parsing des arguments ---
# --pdf          : forcer la generation du rapport PDF (comportement par defaut)
# --no-pdf       : desactiver la generation du rapport PDF
# --no-project   : mode autonome (recherche de menaces) : l'index SQLite est
#                  ecrit dans $VIGIL_BASE/hunt/ au lieu du dossier d'un
#                  projet, sans log de chaine de custody
# --no-dedup     : desactiver le dedoublonnage (marquage des doublons)
# --no-checksafe : desactiver le filtrage checksafe
GEN_PDF=1
DO_DEDUP=1
DO_CHECKSAFE=1
DO_NO_PROJECT=0
JSON_OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)          GEN_PDF=1 ;;
        --no-pdf)       GEN_PDF=0 ;;
        --no-dedup)     DO_DEDUP=0 ;;
        --no-checksafe) DO_CHECKSAFE=0 ;;
        --no-project)   DO_NO_PROJECT=1 ;;
        --user)    shift; HUNT_USER="${1:-}" ;;
        --user=*)  HUNT_USER="${1#--user=}" ;;
        --json-out)       shift; JSON_OUT="${1:-}" ;;
        --json-out=*)     JSON_OUT="${1#--json-out=}" ;;
    esac
    shift
done

# --- Verifier qu'un utilisateur (obligatoire) est actif ---
if [ -n "${HUNT_USER:-}" ]; then
    # Utilisateur passe en argument (chasse) : prioritaire sur le fichier.
    ACTIVE_USER="$HUNT_USER"
elif [ -f "$ACTIVE_USER_FILE" ]; then
    ACTIVE_USER=$(cat "$ACTIVE_USER_FILE")
else
    echo -e "${RED}❌ Aucun utilisateur actif sélectionné.${NC}"
    echo "Sélectionnez un utilisateur via l'interface GUI."
    exit 1
fi
ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
if [ "$DO_NO_PROJECT" -eq 1 ]; then
    # Mode autonome (recherche de menaces) : pas de projet, l'index SQLite
    # est un livrable de la chasse ecrit dans hunt/ (racine du projet,
    # purge a chaque chasse), sans log de chaine de custody.
    ACTIVE_PROJECT="(no-project)"
fi
if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    ACTIVE_PROJECT="(no-project)"
fi
ACTIVE_ENTITY="(non configurée)"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
    [ -z "$ACTIVE_ENTITY" ] && ACTIVE_ENTITY="(non configurée)"
fi
if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    if [ "$DO_NO_PROJECT" -eq 1 ]; then
        PROJECT_LOG_DIR="$VIGIL_BASE/hunt"
        mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || true
    else
        PROJECT_LOG_DIR="/tmp"
    fi
else
    PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
fi

# --- Purge des recensements precedents du projet ---
# Un recensement neant se superpose pas : les anciens livrables du meme type
# sont supprimes et remplaces par les nouveaux (evite l'accumulation de
# census_*.sqlite/.tsv, traces .sains/.doublons et rapports PDF a chaque
# montage/demontage). Les autres livrables du projet sont intacts.
if { [ "$ACTIVE_PROJECT" != "(no-project)" ] || [ "$DO_NO_PROJECT" -eq 1 ]; } \
   && [ -d "$PROJECT_LOG_DIR" ]; then
    purge_count=0
    for _f in "$PROJECT_LOG_DIR"/census_*.sqlite \
              "$PROJECT_LOG_DIR"/census_*.tsv \
              "$PROJECT_LOG_DIR"/census_*.sqlite.sha256 \
              "$PROJECT_LOG_DIR"/.sains.census_* \
              "$PROJECT_LOG_DIR"/.doublons.census_* \
              "$PROJECT_LOG_DIR"/rapport_census_*.pdf; do
        [ -e "$_f" ] || continue
        rm -f -- "$_f" && purge_count=$((purge_count + 1))
    done
    if [ "$purge_count" -gt 0 ]; then
        echo -e "${GREY}Nettoyage de $purge_count fichier(s) de recensement precedent(s) :" \
             "les nouveaux livrables les remplacent.${NC}"
    fi
fi

# --- final_pause : ne ferme jamais le terminal sans lecture ---
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Recensement terminé avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Recensement terminé sans erreur.${NC}"
    fi
}

fail() {
    echo -e "${RED}❌ $1${NC}"
    log_action "error" "$1"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

log_action() {
    # Chasse (recherche de menaces) : chaque evenement du recensement est
    # aussi journalise dans hunt/chain_of_custody.json (section custody du
    # rapport consolide). VIGIL_HUNT_CUSTODY est exporte par la chasse.
    if [ -n "${VIGIL_HUNT_CUSTODY:-}" ]; then
        local timestamp
        timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
        if command -v jq >/dev/null 2>&1; then
            jq -c -n \
                --arg timestamp "$timestamp" \
                --arg user "$ACTIVE_USER" \
                --arg action "census" \
                --arg status "$1" \
                --arg message "$2" \
                '{timestamp: $timestamp, user: $user, action: $action,
                  status: $status, message: $message}' \
                >> "$VIGIL_HUNT_CUSTODY" 2>/dev/null || true
        else
            printf '{"timestamp":"%s","user":"%s","action":"%s","status":"%s","message":"%s"}\n' \
                "$timestamp" "$ACTIVE_USER" "census" "$1" "$2" \
                >> "$VIGIL_HUNT_CUSTODY" 2>/dev/null || true
        fi
    fi
    [ "$ACTIVE_PROJECT" = "(no-project)" ] && return
    local timestamp
    timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:census | Status:$1 | Message:$2"
    echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
}

# --- Verification des dependances ---
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING=0
for cmd in file find python3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING=$((MISSING + 1))
    fi
done
# pv (barre de progression) est optionnel.
PV=""
if command -v pv >/dev/null 2>&1; then
    PV="pv"
fi
[ "$MISSING" -gt 0 ] && fail "Dépendances obligatoires manquantes ($MISSING)."

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Recensement des fichiers          ${NC}"
echo -e "${BLUE}============================================${NC}"
if [ "$DO_NO_PROJECT" -eq 1 ]; then
    echo -e "${BLUE}Projet : (sans projet)${NC}"
else
    echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
fi
log_action "start" "Début du recensement"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo ""

# --- Verifier que /investigation contient des peripheriques montes ---
echo -e "${BLUE}=== Vérification des périphériques montés ===${NC}"
MOUNTED_DIRS=0
MOUNT_INFO=""
while IFS= read -r -d '' dir; do
    # Un dossier est considere comme un peripherique monte s'il apparait
    # comme mountpoint, OU (fallback dev/test sans privileges root) s'il
    # contient des fichiers directement. /investigation ne devant contenir
    # que des points de montage, le fallback ne change rien en production.
    is_mount=0
    if mountpoint -q "$dir" 2>/dev/null; then
        is_mount=1
    elif command -v find >/dev/null 2>&1 \
         && [ -n "$(find "$dir" -maxdepth 1 -type f -print -quit 2>/dev/null)" ]; then
        is_mount=1
    fi
    if [ "$is_mount" -eq 1 ]; then
        MOUNTED_DIRS=$((MOUNTED_DIRS + 1))
        MOUNT_INFO="${MOUNT_INFO}${dir}\n"
    fi
done < <(find "$INVESTIGATION_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [ "$MOUNTED_DIRS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun périphérique monté dans /investigation/.${NC}"
    echo -e "${YELLOW}    Montez d'abord un périphérique via le menu \"Monter\".${NC}"
    fail "Aucun périphérique à recenser."
fi
echo -e "${GREEN}✅ ${MOUNTED_DIRS} périphérique(s) monté(s) dans /investigation/.${NC}"
echo ""

# --- Etape 1 : recensement des fichiers ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : Recensement des fichiers        ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Inventaire intégral des fichiers dans /investigation/...${NC}"
echo ""

# Format TSV : chemin \t taille \t atime \t mtime \t ctime \t btime \t mode \t uid \t gid
# Dates au format find (%Y%m%d%H%M) puis normalisees en UTC par la suite.
RAW_LIST="$WORK_DIR/raw_list.tsv"
: > "$RAW_LIST"

# find -printf : %p chemin | %s taille | dates a/m/c/b | %A* atime | %T* mtime |
# %C* ctime | %w btime (birth) | %f nom | %y type
# btime (%w) n'est pas supporte par tous les FS ; on le capture quand meme
# (vide si absent).
find "$INVESTIGATION_DIR" -type f -printf "%p\t%s\t%AY%Am%Ad%AH%AM\t%TY%Tm%Td%TH%TM\t%CY%Cm%Cd%CH%CM\t%w\t%m\t%u\t%g\n" 2>/dev/null \
    > "$RAW_LIST"

TOTAL_FILES=$(wc -l < "$RAW_LIST")
echo -e "${GREEN}✅ ${TOTAL_FILES} fichier(s) recensé(s).${NC}"
echo ""

if [ "$TOTAL_FILES" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier à recenser.${NC}"
    log_action "success" "Aucun fichier recensé"
    JSON_FILE="$WORK_DIR/resultat.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":0,"duplicate_count":0,"duplicate_groups":0,"safe_filtered_count":0,"checksafe_base_name":false,"checksafe_base_hash":false,"checksafe_active":false,"mime_stats":{},"mime_ext_stats":[],"dir_stats":[],"db_path":"","db_sha256":"","tsv_path":"","dup_doc":{"duplicate_groups":0,"duplicate_files":0,"redundant_copies":0,"redundant_bytes":0}}
EOFJSON
    # --- Generation du rapport PDF (0 fichier) ---
    if [ "$GEN_PDF" -eq 1 ]; then
        PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
        if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
            mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
            PDF_OUT=$(python3 "$PDF_SCRIPT" --kind census --json "$JSON_FILE" \
                --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
            if [ $? -eq 0 ] && [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
                echo -e "${GREEN}✅ Rapport PDF généré : $PDF_OUT${NC}"
                log_action "success" "Rapport PDF généré : $PDF_OUT"
                if [ -n "$PROJECT_LOG_DIR" ] && [ -d "$PROJECT_LOG_DIR" ] && [ -w "$PROJECT_LOG_DIR" ]; then
                    cp -f "$PDF_OUT" "$PROJECT_LOG_DIR/" 2>/dev/null && \
                        echo -e "${GREEN}   Rapport copié dans le dossier du projet${NC}"
                fi
            else
                echo -e "${RED}❌ Échec de la génération du rapport PDF.${NC}"
                ERRORS=$((ERRORS + 1))
            fi
        else
            echo -e "${YELLOW}⚠️  Génération PDF ignorée (python3 ou script PDF manquant).${NC}"
        fi
    fi
    # --- Copie du JSON pour rapport consolidé (mode multi) ---
    if [ -n "$JSON_OUT" ] && [ -f "$JSON_FILE" ]; then
        mkdir -p "$JSON_OUT" 2>/dev/null || true
        cp -f "$JSON_FILE" "$JSON_OUT/vigil_census.json" 2>/dev/null || true
    fi
    rm -rf "$WORK_DIR" 2>/dev/null || true
    final_pause
    exit 0
fi

# --- Etape 2 : detection MIME + normalisation ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2 : Détection des types MIME         ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Analyse des types MIME via file...${NC}"
echo ""

MIME_LIST="$WORK_DIR/mime_list.tsv"
cut -f 1 "$RAW_LIST" | file --mime-type -b -e compress -e tar -e elf -f - 2>/dev/null \
    > "$WORK_DIR/mime_types.txt"
# Normalisation des types office (identique a scalpel/bin/census).
sed -i \
    -e 's;^application/vnd.ms-powerpoint;office/microsoft.powerpoint;' \
    -e 's;^application/vnd.ms-excel;office/microsoft.excel;' \
    -e 's;^application/msword;office/microsoft.word;' \
    -e 's;^application/x-ole-storage;windows/cdfv2;' \
    -e 's;^application/encrypted;office/microsoft.encrypted;' \
    "$WORK_DIR/mime_types.txt"

# Encodage MIME (optionnel, informatif) via file --mime.
cut -f 1 "$RAW_LIST" | file --mime -b -e compress -e tar -e elf -f - 2>/dev/null \
    | sed 's/.*; charset=//' > "$WORK_DIR/mime_encodings.txt"

MIME_COUNT=$(wc -l < "$WORK_DIR/mime_types.txt")
echo -e "${GREEN}✅ ${MIME_COUNT} type(s) MIME déterminé(s).${NC}"
[ "$TOTAL_FILES" -ne "$MIME_COUNT" ] && fail "Les journaux n'ont pas le même nombre d'entrées ($TOTAL_FILES vs $MIME_COUNT)."
echo ""

# --- Etape 3 : dedoublonnage + checksafe + stockage SQLite (Python) ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 3 : Dédoublonnage + checksafe + base ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

JSON_FILE="$WORK_DIR/resultat.json"
DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
VIGIL_VERSION="vigil-census-1.0"
EXT_MAP_FILE="$VIGIL_DATA_DIR/config/ext_mime_map.json"
[ ! -f "$EXT_MAP_FILE" ] && EXT_MAP_FILE="$VIGIL_BASE/config/ext_mime_map.json"

python3 - "$RAW_LIST" "$WORK_DIR/mime_types.txt" "$WORK_DIR/mime_encodings.txt" \
          "$JSON_FILE" "$DATE_ANALYSIS" "$ACTIVE_USER" "$ACTIVE_PROJECT" \
          "$ACTIVE_ENTITY" "$PROJECT_LOG_DIR" "$INVESTIGATION_DIR" \
          "$STOCKAGE_DIR" "$DO_DEDUP" "$DO_CHECKSAFE" "$VIGIL_VERSION" \
          "$EXT_MAP_FILE" "$DO_NO_PROJECT" \
          <<'PYCENSUS'
import os
import sys
import json
import sqlite3
import hashlib
import pickle
from datetime import datetime, timezone

(raw_list, mime_types_file, mime_encodings_file, out_json, date_analysis,
 active_user, active_project, active_entity, project_log_dir,
 investigation_dir, stockage_dir, do_dedup, do_checksafe,
 vigil_version, ext_map_file, no_project) = sys.argv[1:18]
do_dedup = do_dedup == "1"
do_checksafe = do_checksafe == "1"

# --- Audit extension vs format reel (extensions trompeuses) ---
# Charge la table extension -> MIME attendus (data/config/ext_mime_map.json).
# Un fichier dont le MIME reel n'est ni dans "attendu" ni dans "tolere" est
# marque extension_mismatch=1 : son extension ment sur son contenu (ex. un
# .jpg qui est en realite un executable). Sans extension ou extension inconnue
# de la table : pas d'alerte (fichiers systeme sans extension legion).
ext_mime_map = {}
if ext_map_file and os.path.isfile(ext_map_file):
    try:
        with open(ext_map_file, "r", encoding="utf-8") as fh:
            ext_mime_map = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"  ⚠️  Table extension/MIME inexploitable : {exc}")
        ext_mime_map = {}


NORM_TO_FILE_MIME = {
    "office/microsoft.word": "application/msword",
    "office/microsoft.excel": "application/vnd.ms-excel",
    "office/microsoft.powerpoint": "application/vnd.ms-powerpoint",
    "office/microsoft.encrypted": "application/encrypted",
    "windows/cdfv2": "application/x-ole-storage",
}


def audit_extension(path, mime):
    """Retourne (mismatch, expected) pour un fichier recense.

    Les faux positifs connus sont neutralises :
    - fichier vide : file renvoie inode/x-empty, aucune extension ne peut
      mentir sur un contenu inexistant ;
    - MIME normalise par le recensement (office/microsoft.*, windows/cdfv2)
      non presents tels quels dans la table : on les remplace par leur
      equivalent file --mime-type avant comparaison.
    """
    base = os.path.basename(path)
    if "." not in base:
        return 0, ""
    ext = os.path.splitext(base)[1].lower().lstrip(".")
    entry = ext_mime_map.get(ext)
    if not entry:
        return 0, ""
    if not mime or mime == "inode/x-empty":
        return 0, ""
    mime = NORM_TO_FILE_MIME.get(mime, mime)
    expected = entry.get("attendu", []) or []
    tolerated = entry.get("tolere", []) or []
    if mime in expected or mime in tolerated:
        return 0, ", ".join(expected)
    return 1, ", ".join(expected)

investigation_dir = investigation_dir.rstrip("/") or "/investigation"


def norm_date(yyyymmddhhmm):
    """Normalise une date find (%Y%m%d%H%M) en ISO UTC.

    find renvoie les dates en temps local du système. On les convertit en UTC
    pour obtenir une reference neutre ; le FS (FAT=locale, NTFS=UTC) reste
    indique dans inventory_meta pour interpretation forensique ulterieure.
    """
    s = (yyyymmddhhmm or "").strip()
    if not s or "-" in s or len(s) < 12:
        return ""
    try:
        dt = datetime.strptime(s, "%Y%m%d%H%M")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ""


def content_hash(path):
    """Hash de contenu (SHA-256) pour le dedoublonnage.

    SHA-256 est calcule pour tous les fichiers recenses : il sert de cle de
    groupage des doublons (comparaison de contenu) et reste un livrable
    forensique exploitable directement (croisement avec les bases externes).
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


# --- Lecture du recensement brut ---
paths = []
records = []
with open(raw_list, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        cols = line.split("\t")
        # %p %s atime mtime ctime btime mode uid gid
        if len(cols) < 9:
            cols += [""] * (9 - len(cols))
        path, size = cols[0], cols[1]
        atime, mtime, ctime, btime = cols[2], cols[3], cols[4], cols[5]
        mode, uid, gid = cols[6], cols[7], cols[8]
        try:
            size_i = int(size) if size else 0
        except ValueError:
            size_i = 0
        rel = path
        if path.startswith(investigation_dir + "/"):
            rel = path[len(investigation_dir) + 1:]
        records.append({
            "path": path, "rel": rel, "size": size_i,
            "atime": norm_date(atime), "mtime": norm_date(mtime),
            "ctime": norm_date(ctime), "btime": norm_date(btime),
            "mode": mode, "uid": uid, "gid": gid,
        })
        paths.append(path)

# --- Types MIME + encodages ---
mime_types = []
with open(mime_types_file, encoding="utf-8", errors="replace") as fh:
    mime_types = [ln.rstrip("\n") for ln in fh]
mime_encodings = []
try:
    with open(mime_encodings_file, encoding="utf-8", errors="replace") as fh:
        mime_encodings = [ln.rstrip("\n") for ln in fh]
except OSError:
    mime_encodings = [""] * len(records)
if len(mime_types) < len(records):
    mime_types += [""] * (len(records) - len(mime_types))
if len(mime_encodings) < len(records):
    mime_encodings += [""] * (len(records) - len(mime_encodings))

# Extension (nom de fichier) pour le filtrage checksafe par nom.
def extension(path):
    base = os.path.basename(path)
    if "." in base:
        return os.path.splitext(base)[1].lower()
    return ""

# --- Audit extension vs MIME pour chaque fichier ---
# mime_types est parallele a records (meme ordre, meme longueur, verifie
# par le script appelant). Les mismatch alimentent le rapport census et les
# cibles du binwalk cible de la recherche de menaces.
mismatch_count = 0
mismatch_files = []
for i, rec in enumerate(records):
    mime = mime_types[i] if i < len(mime_types) else ""
    rec["extension_mismatch"], rec["expected_format"] = audit_extension(
        rec["path"], mime)
    if rec["extension_mismatch"]:
        mismatch_count += 1
        if len(mismatch_files) < 500:
            mismatch_files.append({
                "path": rec["rel"], "size": rec["size"],
                "extension": extension(rec["path"]),
                "mime_type": mime,
                "expected_format": rec["expected_format"],
            })

# --- Dedoublonnage : groupage par hash de contenu, marquage (conservation) ---
# On conserve TOUS les fichiers dans l'inventaire ; on marque les doublons
# (is_duplicate=1, duplicate_of=<representant>, duplicate_group=<id>).
# Les analyses ciblees ne traitent qu'un representant par groupe, MAIS le
# rapport documente tous les emplacements (fait forensique).
duplicate_count = 0
group_counter = 0
if do_dedup:
    print("  Calcul des hash SHA-256 (groupage des doublons)...")
    # Premier passage : calcul du hash SHA-256 de chaque fichier.
    for rec in records:
        rec["content_hash"] = content_hash(rec["path"])
else:
    for rec in records:
        rec["content_hash"] = ""

# --- checksafe : filtre par base de noms + base de hashes (CONSERVE tel quel) ---
# Sources externes recherchees dans /stockage (files.safe.name / files.safe.hash)
# — config de l'operateur/autorite, pas dans Vigil. Bases pickle (set python),
# comme scalpel/bin/checksafe. Comportement sans base : ne filtre rien.
safe_filtered_count = 0
checksafe_base_name = 0
checksafe_base_hash = 0
name_db = None
hash_db = None
if do_checksafe:
    name_path = os.path.join(stockage_dir, "files.safe.name")
    hash_path = os.path.join(stockage_dir, "files.safe.hash")
    if os.path.isfile(name_path) and os.path.getsize(name_path) > 0:
        checksafe_base_name = 1
        try:
            with open(name_path, "rb") as fh:
                name_db = pickle.load(fh)
            print(f"  Utilisation d'une base de noms externe : {name_path}")
        except Exception as exc:
            print(f"  ⚠️  Base de noms externe inexploitable : {exc}")
            name_db = None
    if os.path.isfile(hash_path) and os.path.getsize(hash_path) > 0:
        checksafe_base_hash = 1
        try:
            with open(hash_path, "rb") as fh:
                hash_db = pickle.load(fh)
            print(f"  Utilisation d'une base de signatures externe : {hash_path}")
        except Exception as exc:
            print(f"  ⚠️  Base de signatures externe inexploitable : {exc}")
            hash_db = None

# Reproduit la semantique exacte de scalpel/bin/checksafe :
#   - si la base de noms est vide (None), la signature est systematiquement
#     verifiee aupres de la base des signatures ;
#   - si la base de signatures est vide (None), toutes les entrees ressortent
#     sur stderr (pas de filtre) -> aucun fichier n'est marque sain.
def is_safe(path):
    """Retourne True si le fichier est considere sain (a retirer)."""
    name = os.path.basename(path).lower()
    if name_db is None or name in name_db:
        if hash_db is not None:
            try:
                with open(path, "rb") as fh:
                    digest = hashlib.sha1(fh.read()).digest()
                if digest in hash_db:
                    return True
            except OSError:
                return False
        # base de signatures vide -> rien n'est sain (pas de filtre)
        return False
    return False

if do_checksafe and (checksafe_base_name or checksafe_base_hash):
    print("  Filtrage checksafe en cours...")
    for rec in records:
        if is_safe(rec["path"]):
            rec["is_safe_filtered"] = 1
            safe_filtered_count += 1
        else:
            rec["is_safe_filtered"] = 0
else:
    for rec in records:
        rec["is_safe_filtered"] = 0
    if do_checksafe:
        print("  Aucune base externe trouvée : checksafe ne filtre rien "
              "(comportement attendu et documenté).")

# --- Marquage des doublons sur chaque enregistrement (conservation) ---
# On conserve TOUS les fichiers ; on marque les doublons (le premier fichier
# rencontre par hash est le representant du groupe, les suivants sont marques).
if do_dedup:
    hash_to_grp = {}
    group_id = 0
    for rec in records:
        h = rec["content_hash"]
        if not h:
            rec["is_duplicate"] = 0
            rec["duplicate_of"] = ""
            rec["duplicate_group"] = 0
            continue
        if h not in hash_to_grp:
            group_id += 1
            hash_to_grp[h] = {"group": group_id, "rep": rec["rel"], "seen": False}
        grp = hash_to_grp[h]
        rec["duplicate_group"] = grp["group"]
        if grp["seen"]:
            rec["is_duplicate"] = 1
            rec["duplicate_of"] = grp["rep"]
            duplicate_count += 1
        else:
            rec["is_duplicate"] = 0
            rec["duplicate_of"] = ""
            grp["seen"] = True
else:
    for rec in records:
        rec["is_duplicate"] = 0
        rec["duplicate_of"] = ""
        rec["duplicate_group"] = 0

# --- Stockage SQLite dans le dossier du projet ---
db_path = ""
tsv_path = ""
db_sha256 = ""
no_project = no_project == "1"
if no_project or (active_project and active_project != "(no-project)"):
    project_dir = project_log_dir
    os.makedirs(project_dir, exist_ok=True)
    db_path = os.path.join(project_dir, "census.sqlite")
    # On evite d'ecraser une base precedente : suffixe horodate.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_path = os.path.join(project_dir, f"census_{stamp}.sqlite")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT, serial TEXT, partition TEXT, fstype TEXT,
            mount_point TEXT, mount_options TEXT, blockdev_ro TEXT,
            operator TEXT, project TEXT, entity TEXT,
            started_at TEXT, ended_at TEXT, duration TEXT,
            total_files INTEGER, duplicate_count INTEGER,
            safe_filtered_count INTEGER,
            checksafe_base_name INTEGER, checksafe_base_hash INTEGER,
            tool_versions TEXT, vigil_version TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER,
            path TEXT, size INTEGER,
            mtime TEXT, atime TEXT, ctime TEXT, btime TEXT,
            mime_type TEXT, mime_encoding TEXT, extension TEXT,
            mode TEXT, uid TEXT, gid TEXT,
            device TEXT, partition TEXT,
            content_hash TEXT,
            is_duplicate INTEGER, duplicate_of TEXT, duplicate_group INTEGER,
            is_safe_filtered INTEGER,
            extension_mismatch INTEGER DEFAULT 0,
            expected_format TEXT,
            FOREIGN KEY (inventory_id) REFERENCES inventory_meta(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_mime ON files(inventory_id, mime_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(inventory_id, mtime)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_dup ON files(is_duplicate)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_mismatch ON files(extension_mismatch)")

    started_at = date_analysis
    ended_at = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
    tool_versions = "file=file; hash=sha256"
    cur.execute("""
        INSERT INTO inventory_meta (
            device, serial, partition, fstype, mount_point, mount_options,
            blockdev_ro, operator, project, entity, started_at, ended_at,
            duration, total_files, duplicate_count, safe_filtered_count,
            checksafe_base_name, checksafe_base_hash, tool_versions,
            vigil_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (investigation_dir, "", "", "", "", "", "", active_user,
          active_project, active_entity, started_at, ended_at, "",
          len(records), duplicate_count, safe_filtered_count,
          checksafe_base_name, checksafe_base_hash, tool_versions,
          vigil_version))
    inv_id = cur.lastrowid

    rows = []
    for i, rec in enumerate(records):
        rows.append((
            inv_id, rec["path"], rec["size"], rec["mtime"], rec["atime"],
            rec["ctime"], rec["btime"], mime_types[i] if i < len(mime_types) else "",
            mime_encodings[i] if i < len(mime_encodings) else "",
            extension(rec["path"]), rec["mode"], rec["uid"], rec["gid"],
            investigation_dir, "", rec["content_hash"], rec["is_duplicate"],
            rec["duplicate_of"], rec["duplicate_group"], rec["is_safe_filtered"],
            rec["extension_mismatch"], rec["expected_format"],
        ))
    cur.executemany("""
        INSERT INTO files (
            inventory_id, path, size, mtime, atime, ctime, btime,
            mime_type, mime_encoding, extension, mode, uid, gid,
            device, partition, content_hash, is_duplicate, duplicate_of,
            duplicate_group, is_safe_filtered, extension_mismatch,
            expected_format)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()

    # Export TSV derive (regenerable depuis SQLite, non canonique) pour
    # compatibilite avec les scripts d'analyse existants + audit rapide.
    tsv_path = os.path.join(project_dir, f"census_{stamp}.tsv")
    with open(tsv_path, "w", encoding="utf-8") as fh:
        fh.write("path\tsize\tmtime\tatime\tctime\tbtime\tmime_type\t"
                 "mime_encoding\textension\tmode\tuid\tgid\tcontent_hash\t"
                 "is_duplicate\tduplicate_of\tduplicate_group\tis_safe_filtered\t"
                 "extension_mismatch\texpected_format\n")
        for i, rec in enumerate(records):
            fh.write("\t".join(str(x) for x in (
                rec["rel"], rec["size"], rec["mtime"], rec["atime"],
                rec["ctime"], rec["btime"],
                mime_types[i] if i < len(mime_types) else "",
                mime_encodings[i] if i < len(mime_encodings) else "",
                extension(rec["path"]), rec["mode"], rec["uid"], rec["gid"],
                rec["content_hash"], rec["is_duplicate"], rec["duplicate_of"],
                rec["duplicate_group"], rec["is_safe_filtered"],
                rec["extension_mismatch"], rec["expected_format"])) + "\n")

    # Traces .sains.* et .doublons.* (comme scalpel/bin/census).
    sains_path = os.path.join(project_dir, f".sains.census_{stamp}")
    with open(sains_path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec["is_safe_filtered"]:
                fh.write(rec["rel"] + "\n")
    doublons_path = os.path.join(project_dir, f".doublons.census_{stamp}")
    with open(doublons_path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec["is_duplicate"]:
                fh.write(rec["rel"] + "\n")

    conn.close()

    # Signature de la base SQLite (livrable forensique) : SHA-256 + horodatage.
    sha = hashlib.sha256()
    with open(db_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    db_sha256 = sha.hexdigest()
    sig_path = os.path.join(project_dir, f"census_{stamp}.sqlite.sha256")
    with open(sig_path, "w", encoding="utf-8") as fh:
        fh.write(f"{db_sha256}  census_{stamp}.sqlite\n")
        _projet_sig = (f"projet {active_project}"
                       if not no_project else "sans projet (chasse)")
        fh.write(f"# Signé le {ended_at} par {active_user} "
                 f"(entité {active_entity}, {_projet_sig})\n")
    print(f"  Base SQLite : {db_path}")
    print(f"  Signature SHA-256 : {db_sha256}")
    if no_project:
        print("  Mode autonome : index écrit dans hunt/ (racine du projet, "
              "recherche de menaces, sans projet).")

# --- Statistiques par type MIME pour le rapport ---
mime_stats = {}
mime_ext_pairs = {}  # (mime, ext) -> count
for i, m in enumerate(mime_types[:len(records)]):
    mime_stats[m] = mime_stats.get(m, 0) + 1
    ext = extension(records[i]["path"])
    key = (m, ext)
    mime_ext_pairs[key] = mime_ext_pairs.get(key, 0) + 1
# Liste triee par count desc puis mime/ext alpha, pour le rapport PDF.
mime_ext_stats = [
    {"mime": k[0], "ext": k[1] or "", "count": v}
    for k, v in sorted(mime_ext_pairs.items(),
                       key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
]

# Doublons documentes : groupes avec plus d'un emplacement. Pour le rapport
# PDF, on ne conserve qu'un RESUME (nombre total de doublons, nombre de
# groupes et taille potentiellelement recuperable) : sur un gros disque,
# lister chaque groupe multiplie les pages. Le detail reste disponible dans
# la base SQLite (is_duplicate, duplicate_of, duplicate_group) et l'export
# TSV, livrables forensiques signes.
dup_groups = {}
if do_dedup:
    for rec in records:
        if rec["duplicate_group"]:
            g = rec["duplicate_group"]
            dup_groups.setdefault(g, []).append(rec["rel"])
multi_groups = [paths for paths in dup_groups.values() if len(paths) > 1]
dup_doc = {
    "duplicate_groups": len(multi_groups),
    "duplicate_files": sum(len(p) for p in multi_groups),
    "redundant_copies": sum(len(p) - 1 for p in multi_groups),
    "redundant_bytes": sum(
        rec["size"]
        for rec in records if rec["is_duplicate"]),
}

# Repartition par dossier : nombre de fichiers (y compris cachés) dans
# chaque dossier de l'arborescence, pour le rapport PDF. On compte par
# dossier parent exact (les sous-dossiers sont comptés séparément, pas
# récursivement : la lecture du tableau reconstitue l'arborescence).
dir_counts = {}
for rec in records:
    parent = os.path.dirname(rec["rel"]) or "."
    dir_counts[parent] = dir_counts.get(parent, 0) + 1
# Ordre purement alphabetique (insensible a la casse) : un dossier parent est
# un prefixe de ses sous-dossiers, il apparait donc avant eux naturellement.
dir_stats = [
    {"dir": d, "count": dir_counts[d]}
    for d in sorted(dir_counts,
                    key=lambda d: (d.lower(), d))
]

result = {
    "date": date_analysis,
    "total_files": len(records),
    "duplicate_count": duplicate_count,
    "duplicate_groups": len([g for g in dup_groups.values() if len(g) > 1]),
    "safe_filtered_count": safe_filtered_count,
    "checksafe_base_name": bool(checksafe_base_name),
    "checksafe_base_hash": bool(checksafe_base_hash),
    "checksafe_active": bool(do_checksafe and (checksafe_base_name or checksafe_base_hash)),
    "mime_stats": mime_stats,
    "mime_ext_stats": mime_ext_stats,
    "dir_stats": dir_stats,
    "mismatch_count": mismatch_count,
    "mismatch_files": mismatch_files,
    "db_path": db_path,
    "db_sha256": db_sha256,
    "tsv_path": tsv_path,
    "dup_doc": dup_doc,
}
with open(out_json, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)

print(f"  Fichiers recensés : {len(records)}")
print(f"  Extensions trompeuses : {mismatch_count}")
print(f"  Doublons marqués : {duplicate_count} (dans "
      f"{result['duplicate_groups']} groupe(s))")
print(f"  Fichiers sains filtrés : {safe_filtered_count}")
PYCENSUS

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Échec du traitement (recensement/dédoublonnage/SQLite).${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# --- Generation du rapport PDF ---
echo -e "${BLUE}=== Génération du rapport PDF ===${NC}"
if [ "$GEN_PDF" -eq 0 ]; then
    echo -e "${YELLOW}⏏️  Génération du rapport PDF désactivée (--no-pdf).${NC}"
else
PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
    mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
    PDF_OUT=$(python3 "$PDF_SCRIPT" \
        --kind census \
        --json "$JSON_FILE" \
        --user "$ACTIVE_USER" \
        --project "$ACTIVE_PROJECT" \
        --dir "$RAPPORTS_DIR" 2>&1)
    if [ $? -eq 0 ] && [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
        echo -e "${GREEN}✅ Rapport PDF généré : $PDF_OUT${NC}"
        log_action "success" "Rapport PDF généré : $PDF_OUT"
        # Copie du rapport PDF dans le dossier du projet (pour l'export).
        if [ -n "$PROJECT_LOG_DIR" ] && [ -d "$PROJECT_LOG_DIR" ] && [ -w "$PROJECT_LOG_DIR" ]; then
            cp -f "$PDF_OUT" "$PROJECT_LOG_DIR/" 2>/dev/null && \
                echo -e "${GREEN}   Rapport copié dans le dossier du projet : ${PROJECT_LOG_DIR}/$(basename "$PDF_OUT")${NC}"
        fi
    else
        echo -e "${RED}❌ Échec de la génération du rapport PDF.${NC}"
        echo -e "${YELLOW}    $PDF_OUT${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}⚠️  Génération PDF ignorée (python3, JSON ou script PDF manquant).${NC}"
fi
fi
echo ""

# --- Copie du JSON pour rapport consolidé (mode multi) ---
if [ -n "$JSON_OUT" ] && [ -f "$JSON_FILE" ]; then
    mkdir -p "$JSON_OUT" 2>/dev/null || true
    cp -f "$JSON_FILE" "$JSON_OUT/vigil_census.json" 2>/dev/null || true
fi

# --- Nettoyage du dossier temporaire ---
rm -rf "$WORK_DIR" 2>/dev/null || true
log_action "success" "Recensement terminé (${TOTAL_FILES} fichiers)"

final_pause
