#!/bin/bash
set -uo pipefail

# --- Analyse des fichiers image ---
#
# Inspire de scalpel/bin/images : extraction et organisation des fichiers
# image (photos) depuis les peripheriques montes dans /investigation/.
#
# Le script :
#   1. detecte tous les fichiers image dans /investigation/ (via `file`) ;
#   2. les classe par type MIME (jpeg, png, gif, ...) pour les statistiques ;
#   3. extrait les metadonnees EXIF si exiftool est disponible ;
#   4. genere un rapport PDF (dans /opt/vigil/rapports).
#
# Les fichiers de travail (liste, JSON) sont stockes dans un dossier temporaire
# nettoye a la fin. Aucun fichier n'est enregistre dans /opt/vigil/analysis.
# Les copies optionnelles des fichiers se font vers les dossiers choisis par
# l'utilisateur (options --copy-to et --copy-faces-to).

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
# --pdf          : forcer la génération du rapport PDF (comportement par défaut)
# --no-pdf       : désactiver la génération du rapport PDF
# --faces        : activer la détection des visages après l'analyse
# --copy-to DIR        : copier les fichiers images vers DIR
# --copy-faces-to DIR : copier les fichiers images avec visages vers DIR
GEN_PDF=1
DO_FACES=0
COPY_TO=""
COPY_FACES_TO=""
JSON_OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)              GEN_PDF=1 ;;
        --no-pdf)           GEN_PDF=0 ;;
        --faces)            DO_FACES=1 ;;
        --copy-to)          shift; COPY_TO="${1:-}" ;;
        --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
        --copy-faces-to)    shift; COPY_FACES_TO="${1:-}" ;;
        --copy-faces-to=*)  COPY_FACES_TO="${1#--copy-faces-to=}" ;;
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
WORK_DIR=$(mktemp -d -t "vigil_images_${STAMP}.XXXXXX")
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
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:images_analysis | Status:$1 | Message:$2"
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
# Outils optionnels
EXIFTOOL=""
if command -v exiftool >/dev/null 2>&1; then
    EXIFTOOL="exiftool"
    echo -e "${GREEN}✅ exiftool détecté : extraction EXIF disponible.${NC}"
else
    echo -e "${YELLOW}⚠️  exiftool absent : extraction EXIF désactivée.${NC}"
    echo -e "${GREY}    Installez-le : sudo apt install libimage-exiftool-perl${NC}"
fi
[ "$MISSING" -gt 0 ] && fail "Dépendances obligatoires manquantes ($MISSING)."

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Analyse des fichiers image       ${NC}"
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

# --- Detection des fichiers image ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : Détection des fichiers image     ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Recherche des fichiers image dans /investigation/...${NC}"
echo ""

# Liste des fichiers image via `file` (mime type image/*)
# Format TSV : chemin_absolu<TAB>mime<TAB>taille<TAB>date_modif_iso<TAB>chemin_partition
IMAGE_LIST="$WORK_DIR/image_list.tsv"
: > "$IMAGE_LIST"

TOTAL_FILES=0
IMAGE_COUNT=0
while IFS= read -r -d '' f; do
    TOTAL_FILES=$((TOTAL_FILES + 1))
    MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
    case "$MIME" in
        image/*)
            SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
            MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
            MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
            REL="${f#$INVESTIGATION_DIR/}"
            echo -e "${f}\t${MIME}\t${SIZE}\t${MTIME_ISO}\t${REL}" >> "$IMAGE_LIST"
            IMAGE_COUNT=$((IMAGE_COUNT + 1))
            ;;
    esac
done < <(find "$INVESTIGATION_DIR" -type f -print0 2>/dev/null)

echo -e "${GREEN}✅ ${IMAGE_COUNT} fichier(s) image détecté(s) sur ${TOTAL_FILES} fichier(s) total.${NC}"
if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier image trouvé.${NC}"
    log_action "success" "Aucun fichier image trouvé"
    JSON_FILE="$WORK_DIR/resultat.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    EXIF_AVAIL="false"; [ -n "$EXIFTOOL" ] && EXIF_AVAIL="true"
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"image_count":0,"types":{},"exif_ok":0,"exif_fail":0,"exif_available":$EXIF_AVAIL,"faces_count":0,"faces_files":[],"faces_available":false,"files":[]}
EOFJSON
    # --- Generation du rapport PDF (0 fichier) ---
    if [ "$GEN_PDF" -eq 1 ]; then
        PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
        if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
            mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
            PDF_OUT=$(python3 "$PDF_SCRIPT" --kind images --json "$JSON_FILE" \
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
        cp -f "$JSON_FILE" "$JSON_OUT/vigil_images.json" 2>/dev/null || true
    fi
    rm -f "$IMAGE_LIST" 2>/dev/null || true
    rm -rf "$WORK_DIR" 2>/dev/null || true
    final_pause
    exit 0
fi

echo ""

# --- Classement par type MIME et par taille ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# --- Statistiques par type MIME (pas de stockage, juste comptage) ---
echo -e "${BLUE}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501${NC}"
echo -e "${BLUE}  \u00c9tape 2 : Statistiques par type MIME     ${NC}"
echo -e "${BLUE}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2502501${NC}"

declare -A TYPE_COUNT
while IFS=$'\t' read -r path mime size mtime rel; do
    subtype="${mime#image/}"
    TYPE_COUNT["$subtype"]=$(( ${TYPE_COUNT["$subtype"]:-0} + 1 ))
done < "$IMAGE_LIST"

echo -e "${GREEN}\u2705 R\u00e9partition par type MIME :${NC}"
for t in "${!TYPE_COUNT[@]}"; do
    echo -e "  ${BOLD}${t}${NC} ${GREY}:${NC} ${BOLD}${TYPE_COUNT[$t]}${NC} ${GREY}fichier(s)${NC}"
done
echo ""

# --- Copie optionnelle des fichiers images ---
if [ -n "$COPY_TO" ]; then
    echo -e "${BLUE}=== Copie des fichiers images ===${NC}"
    if [ ! -d "$COPY_TO" ]; then
        mkdir -p "$COPY_TO" 2>/dev/null || {
            echo -e "${RED}\u274c Impossible de cr\u00e9er le dossier de destination : ${COPY_TO}${NC}"
            ERRORS=$((ERRORS + 1))
        }
    fi
    if [ -d "$COPY_TO" ]; then
        COPIED_IMAGES=0
        while IFS=$'\t' read -r path mime size mtime rel; do
            [ -z "$path" ] && continue
            [ -f "$path" ] || continue
            if cp -p "$path" "$COPY_TO/$(basename "$path")" 2>/dev/null; then
                COPIED_IMAGES=$((COPIED_IMAGES + 1))
            fi
        done < "$IMAGE_LIST"
        echo -e "${GREEN}\u2705 ${COPIED_IMAGES} fichier(s) image copi\u00e9(s) vers : ${COPY_TO}${NC}"
    fi
    echo ""
fi

# --- Extraction EXIF (statistiques uniquement, pas de stockage) ---
EXIF_OK=0
EXIF_FAIL=0
if [ -n "$EXIFTOOL" ]; then
    echo -e "${BLUE}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501${NC}"
    echo -e "${BLUE}  \u00c9tape 3 : Extraction des m\u00e9tadonn\u00e9es EXIF  ${NC}"
    echo -e "${BLUE}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501${NC}"
    echo -e "${YELLOW}Extraction des m\u00e9tadonn\u00e9es EXIF...${NC}"
    EXIF_OK=0
    EXIF_FAIL=0
    while IFS=$'\t' read -r path mime size mtime rel; do
        OUT=$(exiftool -short -short -short -tab -q "$path" 2>/dev/null)
        if [ -n "$OUT" ]; then
            EXIF_OK=$((EXIF_OK + 1))
        else
            EXIF_FAIL=$((EXIF_FAIL + 1))
        fi
    done < "$IMAGE_LIST"
    echo -e "${GREEN}\u2705 EXIF extraites pour ${EXIF_OK} fichier(s)${NC} ${GREY}(${EXIF_FAIL} sans EXIF)${NC}"
    echo ""
fi

# --- D\u00e9tection des visages (optionnel, --faces) -------------------------
# On lance la d\u00e9tection AVANT la g\u00e9n\u00e9ration du PDF pour pouvoir fusionner
# les r\u00e9sultats (faces_result.json) dans le rapport.
FACES_JSON=""
if [ "$DO_FACES" -eq 1 ]; then
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  D\u00e9tection des visages                     ${NC}"
    echo -e "${BLUE}============================================${NC}"
    FACES_SCRIPT="$(dirname "$0")/vigil_faces_detection.sh"
    if [ -f "$FACES_SCRIPT" ]; then
        if [ -n "$COPY_FACES_TO" ]; then
            bash "$FACES_SCRIPT" "$WORK_DIR" "$IMAGE_LIST" --copy-to "$COPY_FACES_TO" || {
                echo -e "${YELLOW}\u26a0\ufe0f  La d\u00e9tection des visages s'est termin\u00e9e avec des avertissements.${NC}"
                ERRORS=$((ERRORS + 1))
            }
        else
            bash "$FACES_SCRIPT" "$WORK_DIR" "$IMAGE_LIST" || {
                echo -e "${YELLOW}\u26a0\ufe0f  La d\u00e9tection des visages s'est termin\u00e9e avec des avertissements.${NC}"
                ERRORS=$((ERRORS + 1))
            }
        fi
        FACES_JSON="$WORK_DIR/faces_result.json"
        [ ! -f "$FACES_JSON" ] && FACES_JSON=""
    else
        echo -e "${YELLOW}\u26a0\ufe0f  Script de d\u00e9tection des visages introuvable ($FACES_SCRIPT).${NC}"
        ERRORS=$((ERRORS + 1))
    fi
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
done < "$IMAGE_LIST"
echo -e "${GREEN}✅ ${SHA_OK} signature(s) calculée(s)${NC} ${GREY}(${SHA_FAIL} échec(s))${NC}"
echo ""

# --- G\u00e9n\u00e9ration du JSON pour le PDF --------------------------------------
JSON_FILE="$WORK_DIR/resultat.json"
DATE_ANALYSIS=$(date +"%d/%m/%Y \u00e0 %H:%M:%S")

if [ -n "$EXIFTOOL" ]; then EXIF_AVAIL="true"; else EXIF_AVAIL="false"; fi

# Construction du JSON (stats + tableau files + fusion faces) via Python.
if command -v python3 >/dev/null 2>&1; then
    python3 - "$IMAGE_LIST" "$SHA_FILE" "$FACES_JSON" "$JSON_FILE" \
           "$DATE_ANALYSIS" "$TOTAL_FILES" "$IMAGE_COUNT" \
           "$EXIF_OK" "$EXIF_FAIL" "$EXIF_AVAIL" <<'PYJSON'
import json, os, sys
(image_list, sha_file, faces_json, out, date, total, count,
 exif_ok, exif_fail, exif_avail) = sys.argv[1:11]
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
types = {}
files = []
try:
    with open(image_list, encoding="utf-8") as fh:
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
result = {
    "date": date, "total_files": int(total), "image_count": int(count),
    "types": types, "exif_ok": int(exif_ok), "exif_fail": int(exif_fail),
    "exif_available": exif_avail == "true",
    "faces_count": 0, "faces_files": [], "faces_available": False,
    "files": files,
}
# Fusion du resultat de la detection des visages si present.
if faces_json and os.path.isfile(faces_json):
    try:
        with open(faces_json, encoding="utf-8") as fh:
            result.update(json.load(fh))
    except (OSError, ValueError):
        pass
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
PYJSON
else
    # Fallback sans python3 : stats seulement, pas de tableau files
    TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"image_count":$IMAGE_COUNT,"types":{$TYPES_JSON},"exif_ok":$EXIF_OK,"exif_fail":$EXIF_FAIL,"exif_available":$EXIF_AVAIL,"faces_count":0,"faces_files":[],"faces_available":false,"files":[]}
EOFJSON
fi

# --- G\u00e9n\u00e9ration du rapport PDF -------------------------------------------
echo -e "${BLUE}=== G\u00e9n\u00e9ration du rapport PDF ===${NC}"
if [ "$GEN_PDF" -eq 0 ]; then
    echo -e "${YELLOW}\u23cf\ufe0f  G\u00e9n\u00e9ration du rapport PDF d\u00e9sactiv\u00e9e (--no-pdf).${NC}"
else
PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
    mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
    PDF_OUT=$(python3 "$PDF_SCRIPT" \
        --kind images \
        --json "$JSON_FILE" \
        --user "$ACTIVE_USER" \
        --project "$ACTIVE_PROJECT" \
        --dir "$RAPPORTS_DIR" 2>&1)
    if [ $? -eq 0 ] && [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
        echo -e "${GREEN}\u2705 Rapport PDF g\u00e9n\u00e9r\u00e9 : $PDF_OUT${NC}"
        log_action "success" "Rapport PDF g\u00e9n\u00e9r\u00e9 : $PDF_OUT"
        # Copie du rapport PDF dans le dossier du projet (pour l'export).
        if [ -n "$PROJECT_LOG_DIR" ] && [ -d "$PROJECT_LOG_DIR" ] && [ -w "$PROJECT_LOG_DIR" ]; then
            cp -f "$PDF_OUT" "$PROJECT_LOG_DIR/" 2>/dev/null && \
                echo -e "${GREEN}   Rapport copi\u00e9 dans le dossier du projet : ${PROJECT_LOG_DIR}/$(basename "$PDF_OUT")${NC}"
        fi
    else
        echo -e "${RED}\u274c \u00c9chec de la g\u00e9n\u00e9ration du rapport PDF.${NC}"
        echo -e "${YELLOW}    $PDF_OUT${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}\u26a0\ufe0f  G\u00e9n\u00e9ration PDF ignor\u00e9e (python3, JSON ou script PDF manquant).${NC}"
fi
fi
echo ""

# --- Copie du JSON pour rapport consolidé (mode multi) ---
if [ -n "$JSON_OUT" ] && [ -f "$JSON_FILE" ]; then
    mkdir -p "$JSON_OUT" 2>/dev/null || true
    cp -f "$JSON_FILE" "$JSON_OUT/vigil_images.json" 2>/dev/null || true
fi

# --- Nettoyage du dossier temporaire ---
rm -rf "$WORK_DIR" 2>/dev/null || true
log_action "success" "${IMAGE_COUNT} fichiers image analys\u00e9s"

final_pause
