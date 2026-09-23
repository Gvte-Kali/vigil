#!/bin/bash
set -uo pipefail

# --- Export du dossier d'un projet (liste de hash SHA-256 + archive) ---
#
# Recense TOUS les fichiers du dossier du projet actif
# ($PROJECTS_DIR/$ACTIVE_PROJECT/), calcule le SHA-256 de chaque fichier,
# archive l'ensemble du dossier, puis calcule le SHA-256 de l'archive.
#
# Produit, dans le dossier de destination (defaut : /opt/vigil/rapports/) :
#   - <projet>_<stamp>.tar.gz        : archive du dossier du projet
#   - <projet>_<stamp>.sha256        : liste de hash SHA-256 de chaque fichier
#                                      du dossier du projet (format sha256sum)
#   - <projet>_<stamp>.hash_archive.sha256 : SHA-256 de l'archive elle-meme
#
# Conventions Vigil :
#   - chaine de custody (active_user obligatoire, active_project obligatoire) ;
#   - l'export est journalise dans chain_of_custody.log du projet.
#
# Usage : vigil_export_project.sh [--dest DIR]
#   --dest DIR : dossier de destination de l'archive (defaut RAPPORTS_DIR)

# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
GREY='\e[90m'
NC='\e[0m'

print_banner() {
    echo -e "${BLUE}"
    cat <<'VIGILART'
█   █ ████  ███  ███ █     █   █  █  █     █   █  █  █  ██  █     █ █   █  █   █     █   ███ ███  █████
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
RAPPORTS_DIR="$VIGIL_BASE/rapports"
STAMP=$(date +"%Y%m%d_%H%M%S")

# --- final_pause : ne ferme jamais le terminal sans lecture ---
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Export terminé avec $ERRORS erreur(s).${NC}"
    else
        echo -e "${GREEN}✅ Export terminé avec succès.${NC}"
    fi
    echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
    read -r
}

fail() {
    echo -e "${RED}❌ $1${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

# --- Utilisateur (non bloquant) ---
# L'export reste possible sans utilisateur actif. Si un utilisateur est
# sélectionné, il est tracé dans la chaîne de custody ; sinon, l'export se
# fait quand même (l'utilisateur de l'export n'empêche pas le packaging).
ACTIVE_USER="(no-user)"
[ -f "$ACTIVE_USER_FILE" ] && ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
[ -z "$ACTIVE_USER" ] && ACTIVE_USER="(no-user)"
ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
ACTIVE_ENTITY="(non configurée)"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
    [ -z "$ACTIVE_ENTITY" ] && ACTIVE_ENTITY="(non configurée)"
fi

# --- Projet obligatoire (chaine de custody) ---
if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    echo -e "${RED}❌ Un projet actif est obligatoire pour l'export (chaine de custody).${NC}"
    echo "Sélectionnez un projet via la GUI."
    exit 1
fi
PROJECT_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
if [ ! -d "$PROJECT_DIR" ] || [ ! -r "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Le dossier du projet est introuvable ou illisible : $PROJECT_DIR${NC}"
    exit 1
fi

PROJECT_LOG_DIR="$PROJECT_DIR"

# --- Logger dans la chaine de custody ---
log_action() {
    local action="$1" status="$2" message="$3" target="${4:-}"
    local timestamp
    timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Target:$target | Status:$status | Message:$message"
    echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
}

# --- Parsing des arguments ---
DEST_DIR="$RAPPORTS_DIR"
while [ $# -gt 0 ]; do
    case "$1" in
        --dest) DEST_DIR="$2"; shift 2 ;;
        *) fail "Argument inconnu : $1" ;;
    esac
done

# --- Verifier les dependances ---
for cmd in sha256sum tar find; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        fail "Outil requis absent : $cmd"
    fi
done

# --- Ecran d'accueil ---
clear
print_banner
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Export du projet                 ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
log_action "export_project" "start" "Début de l'export du projet" ""
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo -e "${BLUE}Dossier source : ${PROJECT_DIR}${NC}"
echo -e "${BLUE}Destination    : ${DEST_DIR}${NC}"
echo ""

# --- Preparer la destination ---
mkdir -p "$DEST_DIR" 2>/dev/null || fail "Impossible de créer le dossier de destination : $DEST_DIR"
if [ ! -w "$DEST_DIR" ]; then
    fail "Le dossier de destination n'est pas inscriptible : $DEST_DIR"
fi

BASE_NAME="${ACTIVE_PROJECT}_${STAMP}"
ARCHIVE="$DEST_DIR/${BASE_NAME}.tar.gz"
SHA_LIST="$DEST_DIR/${BASE_NAME}.sha256"
HASH_ARCHIVE="$DEST_DIR/${BASE_NAME}.hash_archive.sha256"

# --- Etape 1 : recensement + SHA-256 de chaque fichier du dossier du projet ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : SHA-256 de chaque fichier         ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Calcul des empreintes SHA-256 des fichiers du projet...${NC}"
echo ""

# Format sha256sum : "<hash>  <chemin_relatif_au_dossier_projet>"
# On exclut le fichier de hash lui-même (créé en destination, hors projet).
# Le fichier chain_of_custody.log sera inclus (livrable forensique).
: > "$SHA_LIST"
FILE_COUNT=0
HASH_FAIL=0
while IFS= read -r -d '' f; do
    rel="${f#$PROJECT_DIR/}"
    # On ne hashe pas un eventuel fichier de hash deja present dans le projet.
    case "$rel" in
        *.sha256) continue ;;
    esac
    hash=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
    if [ -n "$hash" ]; then
        printf '%s  %s\n' "$hash" "$rel" >> "$SHA_LIST"
        FILE_COUNT=$((FILE_COUNT + 1))
    else
        HASH_FAIL=$((HASH_FAIL + 1))
    fi
done < <(find "$PROJECT_DIR" -type f -print0 2>/dev/null)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier trouvé dans le dossier du projet.${NC}"
    log_action "export_project" "warning" "Aucun fichier à exporter" "$PROJECT_DIR"
else
    echo -e "${GREEN}✅ ${FILE_COUNT} fichier(s) recensé(s)${NC} ${GREY}(${HASH_FAIL} échec(s))${NC}"
fi
echo -e "${GREY}Liste des hash : $SHA_LIST${NC}"
echo ""

# --- Etape 2 : archivage du dossier du projet ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2 : Archivage du dossier du projet   ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Création de l'archive tar.gz...${NC}"
# On archive le contenu du dossier du projet (chemins relatifs au projet).
# La liste de hash (produite en destination) n'est PAS dans le projet, donc
# non incluse dans l'archive ; elle est livrée à côté de l'archive.
if tar -czf "$ARCHIVE" -C "$PROJECT_DIR" . 2>/dev/null; then
    ARCHIVE_SIZE=$(stat -c%s "$ARCHIVE" 2>/dev/null || echo 0)
    echo -e "${GREEN}✅ Archive créée : $ARCHIVE ($ARCHIVE_SIZE octets)${NC}"
else
    log_action "export_project" "error" "Échec de la création de l'archive" "$ARCHIVE"
    fail "Échec de la création de l'archive : $ARCHIVE"
fi
echo ""

# --- Etape 3 : SHA-256 de l'archive ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 3 : SHA-256 de l'archive             ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Calcul de l'empreinte SHA-256 de l'archive...${NC}"
ARCHIVE_HASH=$(sha256sum "$ARCHIVE" 2>/dev/null | awk '{print $1}')
if [ -z "$ARCHIVE_HASH" ]; then
    log_action "export_project" "error" "Échec du hash de l'archive" "$ARCHIVE"
    fail "Échec du calcul du SHA-256 de l'archive : $ARCHIVE"
fi
# Format sha256sum pour verification a reception (nom de l'archive seul).
printf '%s  %s\n' "$ARCHIVE_HASH" "$(basename "$ARCHIVE")" > "$HASH_ARCHIVE"
echo -e "${GREEN}✅ SHA-256 de l'archive : $ARCHIVE_HASH${NC}"
echo -e "${GREY}Fichier de vérification : $HASH_ARCHIVE${NC}"
echo ""

# --- Bilan ---
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Bilan de l'export                         ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}Projet    : ${ACTIVE_PROJECT}${NC}"
echo -e "${GREEN}Fichiers  : ${FILE_COUNT} recensé(s)${NC}"
echo -e "${GREEN}Archive   : ${ARCHIVE}${NC}"
echo -e "${GREEN}SHA-256   : ${ARCHIVE_HASH}${NC}"
echo -e "${GREEN}Liste     : ${SHA_LIST}${NC}"
echo -e "${GREEN}Vérif.    : ${HASH_ARCHIVE}${NC}"
echo ""

log_action "export_project" "success" \
    "Export terminé : ${FILE_COUNT} fichiers, archive $(basename "$ARCHIVE")" \
    "$ARCHIVE_HASH"

final_pause
