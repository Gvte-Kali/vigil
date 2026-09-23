#!/bin/bash
set -uo pipefail

# --- Analyse des fichiers video ---
#
# Inspire de scalpel/bin/videos : extraction et organisation des fichiers
# video depuis les peripheriques montes dans /investigation/.
#
# Le script :
#   1. detecte tous les fichiers video dans /investigation/ (via `file`) ;
#   2. les classe par type MIME (mp4, x-msvideo, ...) pour les statistiques ;
#   3. extrait la duree et la resolution de chaque fichier via ffprobe
#      (equivalent des metadonnees EXIF pour l'audio/video) ;
#   4. classe les fichiers par duree (courte / moyenne / longue / sans) ;
#   5. genere un rapport PDF (dans /opt/vigil/rapports).
#
# Les fichiers de travail (liste, JSON) sont stockes dans un dossier temporaire
# nettoye a la fin. Aucun fichier n'est enregistre dans /opt/vigil/analysis.
# Les copies optionnelles des fichiers se font vers le dossier choisi par
# l'utilisateur (option --copy-to).

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
█   █  █  █      █  █     
█   █  █  █  ██  █  █     
 █ █   █  █   █  █  █     
  █   ███  ███  ███ █████ 
VIGILART
    echo -e "${NC}"
}

ERRORS=0

VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
export VIGIL_BASE VIGIL_DATA_DIR
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"

# --- Parsing des arguments ---
# --pdf          : forcer la generation du rapport PDF (comportement par defaut)
# --no-pdf       : desactiver la generation du rapport PDF
# --copy-to DIR  : copier les fichiers video vers DIR
GEN_PDF=1
COPY_TO=""
JSON_OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)              GEN_PDF=1 ;;
        --no-pdf)           GEN_PDF=0 ;;
        --copy-to)          shift; COPY_TO="${1:-}" ;;
        --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
        --json-out)         shift; JSON_OUT="${1:-}" ;;
        --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
    esac
    shift
done
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
STAMP=$(date +"%Y%m%d_%H%M%S")
WORK_DIR=$(mktemp -d -t "vigil_videos_${STAMP}.XXXXXX")
RAPPORTS_DIR="$VIGIL_BASE/rapports"

# --- Verifier qu'un utilisateur (obligatoire) est actif ---
if [ ! -f "$ACTIVE_USER_FILE" ]; then
    echo -e "${RED}❌ Aucun utilisateur actif sélectionné.${NC}"
    echo "Sélectionnez un utilisateur via l'interface GUI."
    exit 1
fi
ACTIVE_USER=$(cat "$ACTIVE_USER_FILE")
ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
ACTIVE_ENTITY="(non configurée)"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
    [ -z "$ACTIVE_ENTITY" ] && ACTIVE_ENTITY="(non configurée)"
fi

# --- final_pause : ne ferme jamais le terminal sans lecture ---
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Analyse terminée avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Analyse terminée sans erreur.${NC}"
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
    local timestamp
    timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:videos_analysis | Status:$1 | Message:$2"
    echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
}

# --- Projet obligatoire (chaine de custody) ---
if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    echo -e "${RED}❌ Un projet actif est obligatoire pour cette analyse "
    echo -e "${RED}(chaîne de custody). Sélectionnez un projet via la GUI.${NC}"
    exit 1
fi
PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
if [ ! -d "$PROJECT_LOG_DIR" ] || [ ! -w "$PROJECT_LOG_DIR" ]; then
    echo -e "${RED}❌ Le dossier du projet est introuvable ou non inscriptible : $PROJECT_LOG_DIR${NC}"
    exit 1
fi

# --- Verification des dependances ---
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING=0
for cmd in file find; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING=$((MISSING + 1))
    fi
done
# Outil optionnel : ffprobe (ffmpeg) pour duree + resolution
FFPROBE=""
if command -v ffprobe >/dev/null 2>&1; then
    FFPROBE="ffprobe"
    echo -e "${GREEN}✅ ffprobe détecté : extraction durée/résolution disponible.${NC}"
else
    echo -e "${YELLOW}⚠️  ffprobe absent : extraction durée/résolution désactivée.${NC}"
    echo -e "${GREY}    Installez-le : sudo apt install ffmpeg${NC}"
fi
[ "$MISSING" -gt 0 ] && fail "Dépendances obligatoires manquantes ($MISSING)."

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Analyse des fichiers vidéo       ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
log_action "start" "Début de l\'analyse"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo ""

# --- Verifier que /investigation contient des peripheriques montes ---
echo -e "${BLUE}=== Vérification des périphériques montés ===${NC}"
MOUNTED_DIRS=0
while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        MOUNTED_DIRS=$((MOUNTED_DIRS + 1))
    fi
done < <(find "$INVESTIGATION_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [ "$MOUNTED_DIRS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun périphérique monté dans /investigation/.${NC}"
    echo -e "${YELLOW}    Montez d'abord un périphérique via le menu \"Monter\".${NC}"
    fail "Aucun périphérique à analyser."
fi
echo -e "${GREEN}✅ ${MOUNTED_DIRS} périphérique(s) monté(s) dans /investigation/.${NC}"
echo ""

# --- Detection des fichiers video ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : Détection des fichiers vidéo   ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Recherche des fichiers vidéo dans /investigation/...${NC}"
echo ""

# Liste des fichiers video via `file` (mime type video/*)
# Format TSV : chemin_absolu<TAB>mime<TAB>taille<TAB>date_modif_iso<TAB>chemin_partition
VIDEO_LIST="$WORK_DIR/video_list.tsv"
: > "$VIDEO_LIST"

TOTAL_FILES=0
VIDEO_COUNT=0
while IFS= read -r -d '' f; do
    TOTAL_FILES=$((TOTAL_FILES + 1))
    MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
    case "$MIME" in
        video/*)
            SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
            MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
            MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
            # Chemin relatif a /investigation : on garde le nom de la
            # partition (1er sous-dossier) comme racine, ex: sdb1/dossier/clip.mp4
            REL="${f#$INVESTIGATION_DIR/}"
            echo -e "${f}\t${MIME}\t${SIZE}\t${MTIME_ISO}\t${REL}" >> "$VIDEO_LIST"
            VIDEO_COUNT=$((VIDEO_COUNT + 1))
            ;;
    esac
done < <(find "$INVESTIGATION_DIR" -type f -print0 2>/dev/null)

echo -e "${GREEN}✅ ${VIDEO_COUNT} fichier(s) vidéo détecté(s) sur ${TOTAL_FILES} fichier(s) total.${NC}"
if [ "$VIDEO_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier vidéo trouvé.${NC}"
    log_action "success" "Aucun fichier vidéo trouvé"
    JSON_FILE="$WORK_DIR/resultat.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    FFPROBE_AVAIL="false"; [ -n "$FFPROBE" ] && FFPROBE_AVAIL="true"
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"video_count":0,"types":{},"duration_ok":0,"duration_fail":0,"ffprobe_available":$FFPROBE_AVAIL,"durations":{},"files":[]}
EOFJSON
    # --- Generation du rapport PDF (0 fichier) ---
    if [ "$GEN_PDF" -eq 1 ]; then
        PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
        if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
            mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
            PDF_OUT=$(python3 "$PDF_SCRIPT" --kind videos --json "$JSON_FILE" \
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
        cp -f "$JSON_FILE" "$JSON_OUT/vigil_videos.json" 2>/dev/null || true
    fi
    rm -f "$VIDEO_LIST" 2>/dev/null || true
    rm -rf "$WORK_DIR" 2>/dev/null || true
    final_pause
    exit 0
fi

echo ""

# --- Statistiques par type MIME ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2 : Statistiques par type MIME     ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

declare -A TYPE_COUNT
while IFS=$'\t' read -r path mime size mtime rel; do
    subtype="${mime#video/}"
    TYPE_COUNT["$subtype"]=$(( ${TYPE_COUNT["$subtype"]:-0} + 1 ))
done < "$VIDEO_LIST"

echo -e "${GREEN}✅ Répartition par type MIME :${NC}"
for t in "${!TYPE_COUNT[@]}"; do
    echo -e "  ${BOLD}${t}${NC} ${GREY}:${NC} ${BOLD}${TYPE_COUNT[$t]}${NC} ${GREY}fichier(s)${NC}"
done
echo ""

# --- Copie optionnelle des fichiers video ---
if [ -n "$COPY_TO" ]; then
    echo -e "${BLUE}=== Copie des fichiers vidéo ===${NC}"
    if [ ! -d "$COPY_TO" ]; then
        mkdir -p "$COPY_TO" 2>/dev/null || {
            echo -e "${RED}❌ Impossible de créer le dossier de destination : ${COPY_TO}${NC}"
            ERRORS=$((ERRORS + 1))
        }
    fi
    if [ -d "$COPY_TO" ]; then
        COPIED_VIDEOS=0
        while IFS=$'\t' read -r path mime size mtime rel; do
            [ -z "$path" ] && continue
            [ -f "$path" ] || continue
            if cp -p "$path" "$COPY_TO/$(basename "$path")" 2>/dev/null; then
                COPIED_VIDEOS=$((COPIED_VIDEOS + 1))
            fi
        done < "$VIDEO_LIST"
        echo -e "${GREEN}✅ ${COPIED_VIDEOS} fichier(s) vidéo copié(s) vers : ${COPY_TO}${NC}"
    fi
    echo ""
fi

# --- Extraction duree + resolution via ffprobe ---
DURATION_OK=0
DURATION_FAIL=0
DURATION_JSON="$WORK_DIR/durations.tsv"
: > "$DURATION_JSON"
# Repartition par duree : courte (<30min), moyenne (<90min), longue, sans
declare -A DURATION_BUCKETS
DURATION_BUCKETS["courte"]=0
DURATION_BUCKETS["moyenne"]=0
DURATION_BUCKETS["longue"]=0
DURATION_BUCKETS["sans"]=0

if [ -n "$FFPROBE" ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Étape 3 : Extraction durée & résolution   ${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Extraction des métadonnées via ffprobe...${NC}"
    while IFS=$'\t' read -r path mime size mtime rel; do
        # duree (secondes) + resolution (largeur x hauteur)
        dur=$(ffprobe -v quiet -of csv=p=0 -show_entries format=duration "$path" 2>/dev/null | tr -d '[:space:]')
        res=$(ffprobe -v quiet -of csv=p=0 -show_entries stream=width,height -select_streams v:0 "$path" 2>/dev/null | head -n1 | tr -d '[:space:]')
        if [ -z "$dur" ] || [ "$dur" = "N/A" ]; then
            DURATION_BUCKETS["sans"]=$(( ${DURATION_BUCKETS["sans"]} + 1 ))
            DURATION_FAIL=$((DURATION_FAIL + 1))
            bucket="sans"
        else
            dur_int=${dur%%.*}
            [ -z "$dur_int" ] && dur_int=0
            if [ "$dur_int" -lt 1800 ]; then bucket="courte"
            elif [ "$dur_int" -lt 5400 ]; then bucket="moyenne"
            else bucket="longue"
            fi
            DURATION_BUCKETS["$bucket"]=$(( ${DURATION_BUCKETS["$bucket"]} + 1 ))
            DURATION_OK=$((DURATION_OK + 1))
        fi
        echo -e "${path}\t${dur}\t${res}\t${bucket}" >> "$DURATION_JSON"
    done < "$VIDEO_LIST"
    echo -e "${GREEN}✅ Durée extraite pour ${DURATION_OK} fichier(s)${NC} ${GREY}(${DURATION_FAIL} sans durée)${NC}"
    echo ""
else
    # Sans ffprobe : tous les fichiers sont "sans" duree
    while IFS=$'\t' read -r path mime size mtime rel; do
        echo -e "${path}\t\t\tsans" >> "$DURATION_JSON"
    done < "$VIDEO_LIST"
    DURATION_BUCKETS["sans"]=$VIDEO_COUNT
    DURATION_FAIL=$VIDEO_COUNT
fi

# --- Calcul des signatures SHA-256 (par fichier) ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 4 : Signatures SHA-256             ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Calcul des empreintes SHA-256 des fichiers...${NC}"
SHA_FILE="$WORK_DIR/sha256.tsv"
: > "$SHA_FILE"
SHA_OK=0
SHA_FAIL=0
while IFS=$'\t' read -r path mime size mtime rel; do
    [ -z "$path" ] && continue
    hash=$(sha256sum "$path" 2>/dev/null | awk '{print $1}')
    if [ -n "$hash" ]; then
        echo -e "${rel}\t${hash}" >> "$SHA_FILE"
        SHA_OK=$((SHA_OK + 1))
    else
        SHA_FAIL=$((SHA_FAIL + 1))
    fi
done < "$VIDEO_LIST"
echo -e "${GREEN}✅ ${SHA_OK} signature(s) calculée(s)${NC} ${GREY}(${SHA_FAIL} échec(s))${NC}"
echo ""

# --- Generation du JSON pour le PDF ---
JSON_FILE="$WORK_DIR/resultat.json"
DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")

if [ -n "$FFPROBE" ]; then FFPROBE_AVAIL="true"; else FFPROBE_AVAIL="false"; fi

# Construire le JSON des buckets de duree
DUR_COURTE=${DURATION_BUCKETS["courte"]:-0}
DUR_MOYENNE=${DURATION_BUCKETS["moyenne"]:-0}
DUR_LONGUE=${DURATION_BUCKETS["longue"]:-0}
DUR_SANS=${DURATION_BUCKETS["sans"]:-0}

DUR_JSON=$(cat <<EOFDUR
{"courte":$DUR_COURTE,"moyenne":$DUR_MOYENNE,"longue":$DUR_LONGUE,"sans":$DUR_SANS}
EOFDUR
)

# Construction du tableau files (chemin + sha256 + taille + date + mime)
# via Python pour un echappement JSON correct (chemins/special chars).
if command -v python3 >/dev/null 2>&1; then
    python3 - "$VIDEO_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
           "$TOTAL_FILES" "$VIDEO_COUNT" "$DURATION_OK" "$DURATION_FAIL" \
           "$FFPROBE_AVAIL" "$DUR_JSON" <<'PYJSON'
import csv, json, sys
video_list, sha_file, out, date, total, count, dur_ok, dur_fail, ffprobe, dur_json = sys.argv[1:11]
# Index sha256 par chemin relatif de partition
sha = {}
try:
    with open(sha_file, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                sha[parts[0]] = parts[1]
except OSError:
    pass
# Comptage par type MIME
types = {}
files = []
try:
    with open(video_list, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) < 5:
                continue
            path_abs, mime, size, mtime, rel = cols[0], cols[1], cols[2], cols[3], cols[4]
            subtype = mime.split("/", 1)[1] if "/" in mime else mime
            types[subtype] = types.get(subtype, 0) + 1
            try:
                size_i = int(size)
            except ValueError:
                size_i = 0
            files.append({
                "path": rel,
                "sha256": sha.get(rel, ""),
                "size": size_i,
                "mtime": mtime,
                "mime": mime,
            })
except OSError:
    pass
import json as _j
durations = _j.loads(dur_json)
result = {
    "date": date, "total_files": int(total), "video_count": int(count),
    "types": types, "duration_ok": int(dur_ok), "duration_fail": int(dur_fail),
    "ffprobe_available": ffprobe == "true", "durations": durations,
    "files": files,
}
with open(out, "w", encoding="utf-8") as fh:
    _j.dump(result, fh, ensure_ascii=False, indent=2)
PYJSON
else
    # Fallback sans python3 : stats seulement, pas de tableau files
    TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"video_count":$VIDEO_COUNT,"types":{$TYPES_JSON},"duration_ok":$DURATION_OK,"duration_fail":$DURATION_FAIL,"ffprobe_available":$FFPROBE_AVAIL,"durations":$DUR_JSON,"files":[]}
EOFJSON
fi

# --- Generation du rapport PDF ---
echo -e "${BLUE}=== Génération du rapport PDF ===${NC}"
if [ "$GEN_PDF" -eq 0 ]; then
    echo -e "${YELLOW}⏹️  Génération du rapport PDF désactivée (--no-pdf).${NC}"
else
PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
    mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
    PDF_OUT=$(python3 "$PDF_SCRIPT" \
        --kind videos \
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
    cp -f "$JSON_FILE" "$JSON_OUT/vigil_videos.json" 2>/dev/null || true
fi

# --- Nettoyage du dossier temporaire ---
rm -rf "$WORK_DIR" 2>/dev/null || true
log_action "success" "${VIDEO_COUNT} fichiers vidéo analysés"

final_pause
