#!/bin/bash
set -uo pipefail

# --- Analyse des fichiers volumineux ---
#
# Inspire de scalpel/bin/bigfiles : detection des fichiers de taille >= N Mo
# (defaut 512 Mo), en ecartant les fichiers video (traites par le script
# dedie). Le script detecte egalement les fichiers creux (sparse), c'est-a-dire
# dont le contenu reel est compose d'octets nuls (espaces non alloues), ce qui
# est un indicateur forensique important (image disque, fichier efface, ...).
#
# Le script :
#   1. detecte tous les fichiers de taille >= --min-size Mo (defaut 512),
#      sauf les fichiers video (type MIME video/*) ;
#   2. detecte les fichiers creux (octets nuls uniquement) ;
#   3. calcule la signature SHA-256 de chaque fichier retenu ;
#   4. genere un rapport PDF (dans /opt/vigil/rapports).

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

# --- Taille minimale (en Mo, defaut 512) ---
MIN_SIZE_MB=512

# --- Parsing des arguments ---
GEN_PDF=1
COPY_TO=""
MIN_SIZE_MB=512
JSON_OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)              GEN_PDF=1 ;;
        --no-pdf)           GEN_PDF=0 ;;
        --copy-to)         shift; COPY_TO="${1:-}" ;;
        --copy-to=*)       COPY_TO="${1#--copy-to=}" ;;
        --min-size)        shift; MIN_SIZE_MB="${1:-$MIN_SIZE_MB}" ;;
        --min-size=*)      MIN_SIZE_MB="${1#--min-size=}" ;;
        --json-out)        shift; JSON_OUT="${1:-}" ;;
        --json-out=*)      JSON_OUT="${1#--json-out=}" ;;
    esac
    shift
done

# Validation : MIN_SIZE_MB doit etre un entier positif
case "$MIN_SIZE_MB" in
    ''|*[!0-9]*) fail_invalid=1 ;;
    *) fail_invalid=0 ;;
esac
if [ "$fail_invalid" -eq 1 ] || [ "$MIN_SIZE_MB" -le 0 ]; then
    echo -e "${RED}❌ --min-size doit être un entier positif (en Mo).${NC}"
    exit 1
fi
MIN_SIZE_BYTES=$((MIN_SIZE_MB * 1024 * 1024))

ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"

STAMP=$(date +"%Y%m%d_%H%M%S")
WORK_DIR=$(mktemp -d -t "vigil_bigfiles_${STAMP}.XXXXXX")
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
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:bigfiles_analysis | Status:$1 | Message:$2"
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
for cmd in file find stat; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING=$((MISSING + 1))
    fi
done
[ "$MISSING" -gt 0 ] && fail "Dépendances obligatoires manquantes ($MISSING)."

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Analyse des fichiers volumineux   ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
log_action "start" "Début de l\'analyse"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo -e "${BLUE}Taille minimale : ${MIN_SIZE_MB} Mo | Fichiers vidéo exclus${NC}"
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

# --- Detection des fichiers volumineux ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : Détection des fichiers volumineux${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Recherche des fichiers >= ${MIN_SIZE_MB} Mo (vidéos exclues)...${NC}"
echo ""

# Liste des fichiers volumineux via `file` (exclusion video/*)
# Format TSV : chemin_absolu<TAB>mime<TAB>taille<TAB>date_modif_iso<TAB>chemin_partition<TAB>ext
BIGFILE_LIST="$WORK_DIR/bigfile_list.tsv"
: > "$BIGFILE_LIST"
TOTAL_FILES=0
BIGFILE_COUNT=0
while IFS= read -r -d '' f; do
    TOTAL_FILES=$((TOTAL_FILES + 1))
    SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
    [ "$SIZE" -lt "$MIN_SIZE_BYTES" ] && continue
    MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
    # Exclusion des fichiers video (traites par le script dedie)
    case "$MIME" in
        video/*) continue ;;
    esac
    MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
    MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
    REL="${f#$INVESTIGATION_DIR/}"
    EXT="${f##*.}"
    [ "$EXT" = "${f##*/}" ] && EXT=""
    echo -e "${f}\t${MIME}\t${SIZE}\t${MTIME_ISO}\t${REL}\t${EXT}" >> "$BIGFILE_LIST"
    BIGFILE_COUNT=$((BIGFILE_COUNT + 1))
done < <(find "$INVESTIGATION_DIR" -type f -print0 2>/dev/null)

echo -e "${GREEN}✅ ${BIGFILE_COUNT} fichier(s) volumineux détecté(s) sur ${TOTAL_FILES} fichier(s) total.${NC}"
if [ "$BIGFILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier volumineux trouvé.${NC}"
    log_action "success" "Aucun fichier volumineux trouvé"
    JSON_FILE="$WORK_DIR/resultat.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"bigfile_count":0,"sparse_count":0,"min_size_mb":$MIN_SIZE_MB,"types":{},"files":[]}
EOFJSON
    # --- Generation du rapport PDF (0 fichier) ---
    if [ "$GEN_PDF" -eq 1 ]; then
        PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
        if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
            mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
            PDF_OUT=$(python3 "$PDF_SCRIPT" --kind bigfiles --json "$JSON_FILE" \
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
        cp -f "$JSON_FILE" "$JSON_OUT/vigil_bigfiles.json" 2>/dev/null || true
    fi
    rm -f "$BIGFILE_LIST" 2>/dev/null || true
    rm -rf "$WORK_DIR" 2>/dev/null || true
    final_pause
    exit 0
fi

echo ""

# --- Detection des fichiers creux (sparse) ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2 : Détection des fichiers creux    ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Vérification des fichiers creux (octets nuls)...${NC}"
echo ""

# Un fichier creux ne contient que des octets nuls : en supprimant les \0,
# il ne reste rien, donc `read -rsN1` echoue (aucun caractere a lire).
# Format TSV : chemin_absolu<TAB>mime<TAB>taille<TAB>date_modif_iso<TAB>chemin_partition<TAB>ext<TAB>is_sparse
SPARSE_LIST="$WORK_DIR/sparse_list.tsv"
: > "$SPARSE_LIST"
SPARSE_COUNT=0
NON_SPARSE_COUNT=0
while IFS=$'\t' read -r path mime size mtime rel ext; do
    [ -z "$path" ] && continue
    is_sparse="false"
    # Detection fichier creux : si tr -d '\0' laisse un contenu non vide,
    # read -rsN1 reussit -> fichier non creux. Sinon -> creux.
    set +o pipefail
    if tr -d '\0' < "$path" 2>/dev/null | read -rsN1 _; then
        is_sparse="false"
        NON_SPARSE_COUNT=$((NON_SPARSE_COUNT + 1))
    else
        is_sparse="true"
        SPARSE_COUNT=$((SPARSE_COUNT + 1))
    fi
    set -o pipefail
    echo -e "${path}\t${mime}\t${size}\t${mtime}\t${rel}\t${ext}\t${is_sparse}" >> "$SPARSE_LIST"
done < "$BIGFILE_LIST"

echo -e "${GREEN}✅ Fichiers creux (octets nuls uniquement) : ${SPARSE_COUNT}${NC}"
echo -e "${GREEN}✅ Fichiers non creux : ${NON_SPARSE_COUNT}${NC}"
echo ""

# --- Statistiques ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 3 : Statistiques                    ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Répartition par type :${NC}"
echo -e "  ${BOLD}Fichiers creux${NC} ${GREY}:${NC} ${BOLD}${SPARSE_COUNT}${NC} ${GREY}fichier(s)${NC}"
echo -e "  ${BOLD}Fichiers non creux${NC} ${GREY}:${NC} ${BOLD}${NON_SPARSE_COUNT}${NC} ${GREY}fichier(s)${NC}"
echo ""

# Statistiques par type MIME
declare -A TYPE_COUNT
while IFS=$'\t' read -r path mime size mtime rel ext is_sparse; do
    subtype="${mime#*/}"
    [ "$subtype" = "$mime" ] && subtype="$mime"
    TYPE_COUNT["$subtype"]=$(( ${TYPE_COUNT["$subtype"]:-0} + 1 ))
done < "$SPARSE_LIST"
if [ "${#TYPE_COUNT[@]}" -gt 0 ]; then
    echo -e "${GREEN}✅ Répartition par type MIME :${NC}"
    for t in "${!TYPE_COUNT[@]}"; do
        echo -e "  ${BOLD}${t}${NC} ${GREY}:${NC} ${BOLD}${TYPE_COUNT[$t]}${NC} ${GREY}fichier(s)${NC}"
    done
    echo ""
fi

# --- Copie optionnelle des fichiers ---
if [ -n "$COPY_TO" ]; then
    echo -e "${BLUE}=== Copie des fichiers volumineux ===${NC}"
    if [ ! -d "$COPY_TO" ]; then
        mkdir -p "$COPY_TO" 2>/dev/null || {
            echo -e "${RED}❌ Impossible de créer le dossier de destination : ${COPY_TO}${NC}"
            ERRORS=$((ERRORS + 1))
        }
    fi
    if [ -d "$COPY_TO" ]; then
        COPIED=0
        while IFS=$'\t' read -r path mime size mtime rel ext is_sparse; do
            [ -z "$path" ] && continue
            [ -f "$path" ] || continue
            cp -p "$path" "$COPY_TO/$(basename "$path")" 2>/dev/null && COPIED=$((COPIED + 1))
        done < "$SPARSE_LIST"
        echo -e "${GREEN}✅ ${COPIED} fichier(s) copié(s) vers : ${COPY_TO}${NC}"
    fi
    echo ""
fi

# --- Calcul des signatures SHA-256 ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 4 : Signatures SHA-256             ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Calcul des empreintes SHA-256 des fichiers...${NC}"
SHA_FILE="$WORK_DIR/sha256.tsv"
: > "$SHA_FILE"
SHA_OK=0
SHA_FAIL=0
while IFS=$'\t' read -r path mime size mtime rel ext is_sparse; do
    [ -z "$path" ] && continue
    hash=$(sha256sum "$path" 2>/dev/null | awk '{print $1}')
    if [ -n "$hash" ]; then
        echo -e "${rel}\t${hash}" >> "$SHA_FILE"
        SHA_OK=$((SHA_OK + 1))
    else
        SHA_FAIL=$((SHA_FAIL + 1))
    fi
done < "$SPARSE_LIST"
echo -e "${GREEN}✅ ${SHA_OK} signature(s) calculée(s)${NC} ${GREY}(${SHA_FAIL} échec(s))${NC}"
echo ""

# --- Generation du JSON pour le PDF ---
JSON_FILE="$WORK_DIR/resultat.json"
DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")

if command -v python3 >/dev/null 2>&1; then
    python3 - "$SPARSE_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
           "$TOTAL_FILES" "$BIGFILE_COUNT" "$SPARSE_COUNT" "$MIN_SIZE_MB" <<'PYJSON'
import json, sys
sparse_list, sha_file, out, date, total, count, sparse_cnt, min_mb = sys.argv[1:9]

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

files = []
types = {}
sparse_count = 0
try:
    with open(sparse_list, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) < 6:
                continue
            path_abs, mime, size, mtime, rel, ext = cols[0], cols[1], cols[2], cols[3], cols[4], cols[5]
            is_sparse = cols[6] if len(cols) > 6 else "false"
            if is_sparse == "true":
                sparse_count += 1
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
                "ext": ext,
                "is_sparse": is_sparse == "true",
            })
except OSError:
    pass

result = {
    "date": date, "total_files": int(total), "bigfile_count": int(count),
    "sparse_count": sparse_count, "min_size_mb": int(min_mb),
    "types": types, "files": files,
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
PYJSON
else
    TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"bigfile_count":$BIGFILE_COUNT,"sparse_count":$SPARSE_COUNT,"min_size_mb":$MIN_SIZE_MB,"types":{$TYPES_JSON},"files":[]}
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
            --kind bigfiles \
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
    cp -f "$JSON_FILE" "$JSON_OUT/vigil_bigfiles.json" 2>/dev/null || true
fi

# --- Nettoyage du dossier temporaire ---
rm -rf "$WORK_DIR" 2>/dev/null || true
log_action "success" "${BIGFILE_COUNT} fichiers volumineux analysés"
final_pause
