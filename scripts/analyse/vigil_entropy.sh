#!/bin/bash
set -uo pipefail

# --- Analyse des fichiers a forte entropie ---
#
# Inspire de scalpel/bin/entropy : detection des fichiers presents une
# entropie elevee (contenu hautement aleatoire / chiffre / compresse), qui
# peuvent indiquer des donnees chiffrees, des blobs binaires ou des fichiers
# creux non identifies par leur type MIME.
#
# Le script :
#   1. detecte les candidats : fichiers de type `application/octet-stream`
#      (non identifies par `file`) de taille >= 4 Mo ;
#   2. calcule l'entropie de chaque candidat via le taux de compression zstd
#      (ratio = taille_compressee * 10000 / taille_originale) ; un ratio
#      > 9800 (98 %) signale une entropie elevee ;
#   3. verifie l'alignement sur secteur (taille % 512 == 0), indicateur
#      forensique (image disque brute, secteur, ...) ;
#   4. calcule la signature SHA-256 de chaque fichier retenu ;
#   5. genere un rapport PDF (dans /opt/vigil/rapports).
#
# La detection s'appuie sur `file` (mime type) et `zstd` (calcul d'entropie).
# Si zstd est absent, le calcul d'entropie est desactive.

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

# --- Seuil d'entropie (pourcentage * 100, ex. 9800 = 98%) ---
ENTROPY_THRESHOLD=9800

# --- Taille minimale des candidats (octets, defaut 4 Mo) ---
MIN_SIZE=4194304

# --- Parsing des arguments ---
GEN_PDF=1
COPY_TO=""
JSON_OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)              GEN_PDF=1 ;;
        --no-pdf)           GEN_PDF=0 ;;
        --copy-to)         shift; COPY_TO="${1:-}" ;;
        --copy-to=*)       COPY_TO="${1#--copy-to=}" ;;
        --threshold)       shift; ENTROPY_THRESHOLD="${1:-$ENTROPY_THRESHOLD}" ;;
        --threshold=*)     ENTROPY_THRESHOLD="${1#--threshold=}" ;;
        --min-size)        shift; MIN_SIZE="${1:-$MIN_SIZE}" ;;
        --min-size=*)      MIN_SIZE="${1#--min-size=}" ;;
        --json-out)        shift; JSON_OUT="${1:-}" ;;
        --json-out=*)      JSON_OUT="${1#--json-out=}" ;;
    esac
    shift
done

ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"

STAMP=$(date +"%Y%m%d_%H%M%S")
WORK_DIR=$(mktemp -d -t "vigil_entropy_${STAMP}.XXXXXX")
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
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:entropy_analysis | Status:$1 | Message:$2"
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

# Outil optionnel : zstd pour le calcul d'entropie
HAS_ZSTD=""
if command -v zstd >/dev/null 2>&1; then
    HAS_ZSTD="zstd"
    echo -e "${GREEN}✅ zstd détecté : calcul d'entropie disponible.${NC}"
else
    echo -e "${YELLOW}⚠️  zstd absent : calcul d'entropie désactivé.${NC}"
fi

[ "$MISSING" -gt 0 ] && fail "Dépendances obligatoires manquantes ($MISSING)."

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Analyse des fichiers à forte entropie ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
log_action "start" "Début de l\'analyse"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo -e "${BLUE}Seuil d'entropie : $((ENTROPY_THRESHOLD / 100)).$((ENTROPY_THRESHOLD % 100))% | Taille min : $((MIN_SIZE / 1048576)) Mo${NC}"
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

# --- Detection des candidats (octet-stream >= taille min) ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : Détection des candidats         ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Recherche des fichiers application/octet-stream >= $((MIN_SIZE / 1048576)) Mo...${NC}"
echo ""

# Liste des candidats via `file` (mime type application/octet-stream)
# Format TSV : chemin_absolu<TAB>mime<TAB>taille<TAB>date_modif_iso<TAB>chemin_partition<TAB>ext
CANDIDATE_LIST="$WORK_DIR/candidate_list.tsv"
: > "$CANDIDATE_LIST"
TOTAL_FILES=0
CANDIDATE_COUNT=0
while IFS= read -r -d '' f; do
    TOTAL_FILES=$((TOTAL_FILES + 1))
    SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
    [ "$SIZE" -lt "$MIN_SIZE" ] && continue
    MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
    [ "$MIME" != "application/octet-stream" ] && continue
    MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
    MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
    REL="${f#$INVESTIGATION_DIR/}"
    EXT="${f##*.}"
    [ "$EXT" = "${f##*/}" ] && EXT=""
    echo -e "${f}\t${MIME}\t${SIZE}\t${MTIME_ISO}\t${REL}\t${EXT}" >> "$CANDIDATE_LIST"
    CANDIDATE_COUNT=$((CANDIDATE_COUNT + 1))
done < <(find "$INVESTIGATION_DIR" -type f -print0 2>/dev/null)

echo -e "${GREEN}✅ ${CANDIDATE_COUNT} candidat(s) détecté(s) sur ${TOTAL_FILES} fichier(s) total.${NC}"
if [ "$CANDIDATE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun candidat trouvé.${NC}"
    log_action "success" "Aucun fichier à forte entropie trouvé"
    JSON_FILE="$WORK_DIR/resultat.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    ENTROPY_AVAIL="false"; [ -n "$HAS_ZSTD" ] && ENTROPY_AVAIL="true"
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"candidate_count":0,"entropy_count":0,"entropy_available":$ENTROPY_AVAIL,"threshold":$ENTROPY_THRESHOLD,"min_size":$MIN_SIZE,"aligned_count":0,"files":[]}
EOFJSON
    # --- Generation du rapport PDF (0 fichier) ---
    if [ "$GEN_PDF" -eq 1 ]; then
        PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
        if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
            mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
            PDF_OUT=$(python3 "$PDF_SCRIPT" --kind entropy --json "$JSON_FILE" \
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
        cp -f "$JSON_FILE" "$JSON_OUT/vigil_entropy.json" 2>/dev/null || true
    fi
    rm -f "$CANDIDATE_LIST" "$ENTROPY_LIST" 2>/dev/null || true
    rm -rf "$WORK_DIR" 2>/dev/null || true
    final_pause
    exit 0
fi
echo ""

if [ -z "$HAS_ZSTD" ]; then
    echo -e "${YELLOW}⚠️  zstd absent : impossible de calculer l'entropie.${NC}"
    echo -e "${YELLOW}    Rapport généré sans calcul d'entropie (seuil non applicable).${NC}"
    echo ""
fi

# --- Calcul de l'entropie ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2 : Calcul de l'entropie            ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Mesure du taux de compression (zstd) de chaque candidat...${NC}"
echo ""

# Liste des fichiers retenus (entropie >= seuil)
# Format TSV : chemin_absolu<TAB>mime<TAB>taille<TAB>date_modif_iso<TAB>chemin_partition<TAB>ext<TAB>entropy<TAB>aligned
ENTROPY_LIST="$WORK_DIR/entropy_list.tsv"
: > "$ENTROPY_LIST"
ENTROPY_COUNT=0

if [ -n "$HAS_ZSTD" ]; then
    while IFS=$'\t' read -r path mime size mtime rel ext; do
        [ -z "$path" ] && continue
        # Calcul : taille compressee via zstd (sans checksum, sans verifications)
        zstd_size=$(zstd -q -c --no-check < "$path" 2>/dev/null | wc -c)
        zstd_size=${zstd_size##* }
        [ -z "$zstd_size" ] && zstd_size=0
        [ "$size" -le 0 ] && continue
        entropy=$(( zstd_size * 10000 / size ))
        # Alignement sur secteur (512 octets)
        if [ $(( size % 512 )) -eq 0 ]; then
            aligned="true"
        else
            aligned="false"
        fi
        if [ "$entropy" -gt "$ENTROPY_THRESHOLD" ]; then
            echo -e "${path}\t${mime}\t${size}\t${mtime}\t${rel}\t${ext}\t${entropy}\t${aligned}" >> "$ENTROPY_LIST"
            ENTROPY_COUNT=$((ENTROPY_COUNT + 1))
        fi
    done < "$CANDIDATE_LIST"
fi

echo -e "${GREEN}✅ ${ENTROPY_COUNT} fichier(s) à forte entropie (>= $((ENTROPY_THRESHOLD / 100)).$((ENTROPY_THRESHOLD % 100))%).${NC}"
echo ""

if [ "$ENTROPY_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier ne dépasse le seuil d'entropie.${NC}"
    log_action "success" "Aucun fichier à forte entropie trouvé"
    JSON_FILE="$WORK_DIR/resultat.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    ENTROPY_AVAIL="false"; [ -n "$HAS_ZSTD" ] && ENTROPY_AVAIL="true"
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"candidate_count":$CANDIDATE_COUNT,"entropy_count":0,"entropy_available":$ENTROPY_AVAIL,"threshold":$ENTROPY_THRESHOLD,"min_size":$MIN_SIZE,"aligned_count":0,"files":[]}
EOFJSON
    # --- Generation du rapport PDF (0 fichier) ---
    if [ "$GEN_PDF" -eq 1 ]; then
        PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
        if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
            mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
            PDF_OUT=$(python3 "$PDF_SCRIPT" --kind entropy --json "$JSON_FILE" \
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
        cp -f "$JSON_FILE" "$JSON_OUT/vigil_entropy.json" 2>/dev/null || true
    fi
    rm -f "$ENTROPY_LIST" "$CANDIDATE_LIST" 2>/dev/null || true
    rm -rf "$WORK_DIR" 2>/dev/null || true
    final_pause
    exit 0
fi


# --- Statistiques par alignement et par tranche d'entropie ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 3 : Statistiques                    ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
ALIGNED_COUNT=0
HIGH_ENTROPY_COUNT=0
while IFS=$'\t' read -r path mime size mtime rel ext entropy aligned; do
    [ "$aligned" = "true" ] && ALIGNED_COUNT=$((ALIGNED_COUNT + 1))
    [ "$entropy" -ge 9900 ] && HIGH_ENTROPY_COUNT=$((HIGH_ENTROPY_COUNT + 1))
done < "$ENTROPY_LIST"

echo -e "${GREEN}✅ Répartition par alignement secteur :${NC}"
echo -e "  ${BOLD}Alignés (512 o)${NC} ${GREY}:${NC} ${BOLD}${ALIGNED_COUNT}${NC} ${GREY}fichier(s)${NC}"
echo -e "  ${BOLD}Non alignés${NC} ${GREY}:${NC} ${BOLD}$((ENTROPY_COUNT - ALIGNED_COUNT))${NC} ${GREY}fichier(s)${NC}"
echo ""
echo -e "${GREEN}✅ Tranche d'entropie maximale (>= 99%) :${NC} ${BOLD}${HIGH_ENTROPY_COUNT}${NC} ${GREY}fichier(s)${NC}"
echo ""

# --- Copie optionnelle des fichiers ---
if [ -n "$COPY_TO" ]; then
    echo -e "${BLUE}=== Copie des fichiers à forte entropie ===${NC}"
    if [ ! -d "$COPY_TO" ]; then
        mkdir -p "$COPY_TO" 2>/dev/null || {
            echo -e "${RED}❌ Impossible de créer le dossier de destination : ${COPY_TO}${NC}"
            ERRORS=$((ERRORS + 1))
        }
    fi
    if [ -d "$COPY_TO" ]; then
        COPIED=0
        while IFS=$'\t' read -r path mime size mtime rel ext entropy aligned; do
            [ -z "$path" ] && continue
            [ -f "$path" ] || continue
            cp -p "$path" "$COPY_TO/$(basename "$path")" 2>/dev/null && COPIED=$((COPIED + 1))
        done < "$ENTROPY_LIST"
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
while IFS=$'\t' read -r path mime size mtime rel ext entropy aligned; do
    [ -z "$path" ] && continue
    hash=$(sha256sum "$path" 2>/dev/null | awk '{print $1}')
    if [ -n "$hash" ]; then
        echo -e "${rel}\t${hash}" >> "$SHA_FILE"
        SHA_OK=$((SHA_OK + 1))
    else
        SHA_FAIL=$((SHA_FAIL + 1))
    fi
done < "$ENTROPY_LIST"
echo -e "${GREEN}✅ ${SHA_OK} signature(s) calculée(s)${NC} ${GREY}(${SHA_FAIL} échec(s))${NC}"
echo ""

# --- Generation du JSON pour le PDF ---
JSON_FILE="$WORK_DIR/resultat.json"
DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
ENTROPY_AVAIL="false"
[ -n "$HAS_ZSTD" ] && ENTROPY_AVAIL="true"

if command -v python3 >/dev/null 2>&1; then
    python3 - "$ENTROPY_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
           "$TOTAL_FILES" "$CANDIDATE_COUNT" "$ENTROPY_COUNT" "$ENTROPY_AVAIL" \
           "$ENTROPY_THRESHOLD" "$MIN_SIZE" <<'PYJSON'
import json, sys
entropy_list, sha_file, out, date, total, cand, cnt, ent_avail, threshold, min_size = sys.argv[1:11]

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
aligned_count = 0
try:
    with open(entropy_list, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) < 7:
                continue
            path_abs, mime, size, mtime, rel, ext, entropy = cols[0], cols[1], cols[2], cols[3], cols[4], cols[5], cols[6]
            aligned = cols[7] if len(cols) > 7 else "false"
            if aligned == "true":
                aligned_count += 1
            try:
                size_i = int(size)
            except ValueError:
                size_i = 0
            try:
                entropy_i = int(entropy)
            except ValueError:
                entropy_i = 0
            files.append({
                "path": rel,
                "sha256": sha.get(rel, ""),
                "size": size_i,
                "mtime": mtime,
                "mime": mime,
                "ext": ext,
                "entropy": entropy_i,
                "aligned": aligned == "true",
            })
except OSError:
    pass

result = {
    "date": date, "total_files": int(total), "candidate_count": int(cand),
    "entropy_count": int(cnt), "entropy_available": ent_avail == "true",
    "threshold": int(threshold), "min_size": int(min_size),
    "aligned_count": aligned_count, "files": files,
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
PYJSON
else
    cat > "$JSON_FILE" <<EOFJSON
{"date":"$DATE_ANALYSIS","total_files":$TOTAL_FILES,"candidate_count":$CANDIDATE_COUNT,"entropy_count":$ENTROPY_COUNT,"entropy_available":$ENTROPY_AVAIL,"threshold":$ENTROPY_THRESHOLD,"min_size":$MIN_SIZE,"aligned_count":$ALIGNED_COUNT,"files":[]}
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
            --kind entropy \
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
    cp -f "$JSON_FILE" "$JSON_OUT/vigil_entropy.json" 2>/dev/null || true
fi

# --- Nettoyage du dossier temporaire ---
rm -rf "$WORK_DIR" 2>/dev/null || true
log_action "success" "${ENTROPY_COUNT} fichiers à forte entropie analysés"
final_pause
