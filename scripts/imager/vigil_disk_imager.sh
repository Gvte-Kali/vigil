#!/bin/bash
set -uo pipefail

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

clear_banner() {
    clear
    print_banner
}

# --- Contexte actif (utilisateur + projet) : non bloquant pour l'imagerie ---
# L'imagerie forensique reste possible sans utilisateur/projet actifs. Si un
# contexte existe, on l'utilise pour tracer l'action dans la chaîne de
# custody ; sinon, on réalise la copie quand même et on n'écrit pas de log.
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
PROJECTS_DIR="$VIGIL_BASE/data/projects"

ERRORS=0

ACTIVE_USER="(no-user)"
[ -f "$ACTIVE_USER_FILE" ] && ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
[ -z "$ACTIVE_USER" ] && ACTIVE_USER="(no-user)"

ACTIVE_PROJECT="(no-project)"
[ -f "$ACTIVE_PROJECT_FILE" ] && ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
[ -z "$ACTIVE_PROJECT" ] && ACTIVE_PROJECT="(no-project)"

if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    PROJECT_LOG_DIR="/tmp"
else
    PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
fi

# Entité (configuration statique) pour la chaine de custody.
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
CONFIG_FILE="$VIGIL_DATA_DIR/config/system.json"
ACTIVE_ENTITY="(non configurée)"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
    [ -z "$ACTIVE_ENTITY" ] && ACTIVE_ENTITY="(non configurée)"
fi

# --- Logger dans la chaine de custody ---
log_action() {
    local action="$1" status="$2" message="$3" target="${4:-}"
    # Sans utilisateur ni projet actif, pas de chaîne de custody à écrire.
    [ "$ACTIVE_USER" = "(no-user)" ] && return
    [ "$ACTIVE_PROJECT" = "(no-project)" ] && return
    local timestamp
    timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Target:$target | Status:$status | Message:$message"
    echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
}

mkdir -p /tmp 2>/dev/null || true

# --- Compteur d'erreurs global et pause finale ---
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Script terminé avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Script terminé sans erreur.${NC}"
    fi
}

fail() {
    echo -e "${RED}❌ $1${NC}"
    log_action "disk_imager" "error" "$1"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

# --- Vérification des privilèges et dépendances ---
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Ce script nécessite des privilèges root pour accéder aux disques.${NC}"
    echo -e "${YELLOW}    Vérifiez la configuration sudo de l'utilisateur courant.${NC}"
fi

clear
print_banner
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING_DEPS=0
# Dépendances communes obligatoires
for cmd in lsblk blockdev sync; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING_DEPS=$((MISSING_DEPS + 1))
    fi
done
# Dépendances spécifiques au format (vérifiées plus tard, après choix)
# On pré-scanne pour informer l'utilisateur
_HAVE_EWF=0; _HAVE_DC3DD=0; _HAVE_AFF=0
command -v ewfacquire >/dev/null 2>&1 && _HAVE_EWF=1
command -v dc3dd >/dev/null 2>&1 && _HAVE_DC3DD=1
# AFF : affcat (afflib-tools) ou affuse (fuse-af6)
command -v affcat >/dev/null 2>&1 && _HAVE_AFF=1
command -v affuse >/dev/null 2>&1 && _HAVE_AFF=1

if [ "$MISSING_DEPS" -gt 0 ]; then
    fail "Dépendances obligatoires manquantes ($MISSING_DEPS). Installez-les avant de continuer."
fi

echo -e "${GREY}Formats disponibles :${NC}"
[ "$_HAVE_EWF" -eq 1 ]    && echo -e "  ${GREEN}✅${NC} E01 (ewfacquire)" || echo -e "  ${YELLOW}⚠️${NC} E01 absent — sudo apt install ewf-tools"
[ "$_HAVE_DC3DD" -eq 1 ] && echo -e "  ${GREEN}✅${NC} RAW (dc3dd)"     || echo -e "  ${YELLOW}⚠️${NC} RAW absent — sudo apt install dc3dd"
[ "$_HAVE_AFF" -eq 1 ]   && echo -e "  ${GREEN}✅${NC} AFF (afflib)"    || echo -e "  ${YELLOW}⚠️${NC} AFF absent — sudo apt install afflib-tools"

echo ""
echo -e "${BLUE}Utilisateur : ${ACTIVE_USER}${NC}"
echo ""
log_action "disk_imager" "start" "Début de l'imagerie forensique" ""
echo -e "${YELLOW}⚠️  COPIE FORENSIQUE DE DISQUE${NC}"
echo -e "${GREY}Ce script réalise une image forensique (RAW, E01 ou AFF)${NC}"
echo -e "${GREY}d'un disque source vers un disque cible ou un emplacement local.${NC}"
echo -e "${GREY}Le disque source est ACCÉDÉ EN LECTURE SEULE uniquement.${NC}"
echo ""

clear_banner
echo -e "${BLUE}Utilisateur : ${ACTIVE_USER}${NC}"
echo ""
# ============================================================================
# 1. SÉLECTION DU DISQUE SOURCE
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sélection du disque source              ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREY}Le disque source est le disque à copier.${NC}"
echo ""

# Lister tous les disques (TYPE=disk), en excluant les loop/sr (CD-ROM).
# On affiche : device, taille, modèle, type de bus, vendor, série, removable.
SOURCE_DEVICES=()
SOURCE_NUM=0

# Détecter le disque système : celui qui porte la racine "/" ou qui contient
# la partition racine. On l'exclura de la liste des disques copiables pour
# éviter une copie de soi-même.
SYSTEM_DISK=""
_root_part=$(lsblk -ln -o NAME,MOUNTPOINT 2>/dev/null | awk '$2=="/"{print $1}' | head -1)
if [ -n "$_root_part" ]; then
    # Retrouver le disque parent (enlever les chiffres de partition)
    case "$_root_part" in
        nvme*p*|mmcblk*p*) SYSTEM_DISK=$(echo "$_root_part" | sed -E 's/p[0-9]+$//') ;;
        *)                 SYSTEM_DISK=$(echo "$_root_part" | sed -E 's/[0-9]+$//') ;;
    esac
fi
# Fallback : disque sur /boot ou /boot/efi
if [ -z "$SYSTEM_DISK" ]; then
    _boot_part=$(lsblk -ln -o NAME,MOUNTPOINT 2>/dev/null | awk '$2=="/boot"{print $1}' | head -1)
    if [ -n "$_boot_part" ]; then
        case "$_boot_part" in
            nvme*p*|mmcblk*p*) SYSTEM_DISK=$(echo "$_boot_part" | sed -E 's/p[0-9]+$//') ;;
            *)                 SYSTEM_DISK=$(echo "$_boot_part" | sed -E 's/[0-9]+$//') ;;
        esac
    fi
fi

while IFS= read -r line; do
    eval "$line"
    # Exclure les loop, cdrom et zram
    case "$NAME" in
        loop*|sr*|zram*) continue ;;
    esac
    # Exclure le disque système (on ne copie jamais le disque qui porte /)
    if [ -n "$SYSTEM_DISK" ] && [ "$NAME" = "$SYSTEM_DISK" ]; then
        continue
    fi
    # Détails enrichis via /sys et lsblk
    _vendor=$(lsblk -no VENDOR "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _serial=$(lsblk -no SERIAL "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _tran=$(lsblk -no TRAN "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _rm=$(lsblk -no RM "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _ro=$(lsblk -no RO "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    # Exclure les disques internes (RM != 1) : seuls les disques amovibles
    # (clés USB, disques externes) sont proposés à la copie forensique.
    if [ "$_rm" != "1" ]; then
        continue
    fi
    _fstype=$(lsblk -no FSTYPE "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _mount=$(lsblk -no MOUNTPOINT "/dev/$NAME" 2>/dev/null | head -n1)
    _mount=${_mount:-}
    # Nombre de partitions
    _npart=$(lsblk -ln -o NAME "/dev/$NAME" 2>/dev/null | grep -c .)
    _npart=$((_npart - 1))
    [ "$_npart" -lt 0 ] && _npart=0

    [ "$_ro" = "1" ] && _rotype="${YELLOW}[RO]${NC}" || _rotype=""

    SOURCE_DEVICES[$SOURCE_NUM]="$NAME"
    echo -e "  ${BOLD}${BLUE}[$((SOURCE_NUM+1))]${NC}  ${BOLD}/dev/$NAME${NC}  ${GREY}• Taille:${NC} ${BOLD}$SIZE${NC}  ${GREY}• Modèle:${NC} ${BOLD}${MODEL:-?}${NC} ${_rotype}"
    echo -e "       ${GREY}Bus:${NC} ${_tran:-?}  ${GREY}Vendor:${NC} ${_vendor:-?}  ${GREY}Série:${NC} ${_serial:-?}  ${GREY}(amovible)${NC}"
    echo -e "       ${GREY}Partitions:${NC} ${_npart}  ${GREY}FS:${NC} ${_fstype:-aucun}  ${GREY}Monté:${NC} ${_mount:-non}"
    echo ""
    SOURCE_NUM=$((SOURCE_NUM + 1))
done < <(lsblk -P -o NAME,TYPE,SIZE,MODEL 2>/dev/null | grep 'TYPE="disk"')

if [ "$SOURCE_NUM" -eq 0 ]; then
    fail "Aucun disque amovible (clé USB, disque externe) détecté. Branchez un périphérique à copier."
fi

while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le numéro du disque source à copier (ou \"q\" pour quitter) : ${NC}"
    read -r SOURCE_CHOICE
    if [ "$SOURCE_CHOICE" = "q" ]; then
        echo -e "${YELLOW}Annulé.${NC}"
        final_pause
        exit 0
    fi
    if ! [[ "$SOURCE_CHOICE" =~ ^[0-9]+$ ]] || [ "$SOURCE_CHOICE" -lt 1 ] || [ "$SOURCE_CHOICE" -gt "$SOURCE_NUM" ]; then
        echo -e "${RED}❌ Numéro invalide. Entrez un numéro entre 1 et $SOURCE_NUM.${NC}"
        continue
    fi
    SOURCE_DEV="/dev/${SOURCE_DEVICES[$((SOURCE_CHOICE-1))]}"
    break
done

echo ""
echo -e "${GREEN}Disque source sélectionné :${NC} ${BOLD}$SOURCE_DEV${NC}"

# Vérifier que le disque source n'est pas monté
SOURCE_MOUNTED=$(lsblk -ln -o MOUNTPOINT "$SOURCE_DEV" 2>/dev/null | grep -v '^$' | head -1 || true)
if [ -n "$SOURCE_MOUNTED" ]; then
    echo -e "${YELLOW}⚠️  Le disque source $SOURCE_DEV est monté (ex. $SOURCE_MOUNTED).${NC}"
    echo -e "${YELLOW}    Il sera forcé en lecture seule avant la copie.${NC}"
fi

# Forcer le disque source en lecture seule (garantie d'intégrité forensique)
echo -e "${YELLOW}Verrouillage du disque source en lecture seule...${NC}"
if sudo blockdev --setro "$SOURCE_DEV" 2>/dev/null; then
    echo -e "${GREEN}✅ Disque source verrouillé en lecture seule.${NC}"
else
    echo -e "${YELLOW}⚠️  blockdev --setro a échoué sur le disque source.${NC}"
fi
# Vérifier l'état RO réel : on ne continue QUE si le disque est confirmé en
# lecture seule, afin de ne jamais écrire sur le disque source (intégrité de
# la preuve). On retente le verrouillage si nécessaire.
_ro_state=$(lsblk -no RO "$SOURCE_DEV" 2>/dev/null | head -n1 | tr -d '[:space:]')
if [ "$_ro_state" != "1" ]; then
    sudo blockdev --setro "$SOURCE_DEV" 2>/dev/null || true
    _ro_state=$(lsblk -no RO "$SOURCE_DEV" 2>/dev/null | head -n1 | tr -d '[:space:]')
fi
if [ "$_ro_state" != "1" ]; then
    fail "Impossible de verrouiller le disque source $SOURCE_DEV en lecture seule. Abandon (sécurité forensique)."
fi
echo -e "${GREEN}✓ Lecture seule confirmée (RO=1) sur $SOURCE_DEV.${NC}"

# Nom de base de l'image : généré automatiquement (horodatage), sans saisie utilisateur.
IMAGE_ID="$(date +%Y%m%d%H%M%S)"

clear_banner
echo -e "${BLUE}Disque source : ${BOLD}$SOURCE_DEV${NC}"
echo ""
# ============================================================================
# 2. SÉLECTION DU FORMAT DE SORTIE
# ============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sélection du format de sortie          ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[1]${NC}  ${BOLD}RAW (dd)${NC}"
echo -e "        ${GREY}Extensions : .raw .dd .img${NC}"
echo -e "        ${GREY}Copie bit-à-bit sans compression ni métadonnées.${NC}"
echo -e "        ${GREY}Logiciels : dc3dd, dd, Autopsy, FTK Imager, X-Ways${NC}"
[ "$_HAVE_DC3DD" -eq 1 ] && echo -e "        ${GREEN}✅ dc3dd disponible${NC}" || echo -e "        ${YELLOW}⚠️ dc3dd absent — sudo apt install dc3dd${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[2]${NC}  ${BOLD}E01 (EnCase / EWF)${NC}  ${GREY}(par défaut)${NC}"
echo -e "        ${GREY}Extensions : .E01 (segments .E02, .E03 ... si > 2GiB)${NC}"
echo -e "        ${GREY}Format Expert Witness : compression + hash + métadonnées.${NC}"
echo -e "        ${GREY}Logiciels : ewfacquire, EnCase, Autopsy, FTK Imager, X-Ways, Magnet AXIOM${NC}"
[ "$_HAVE_EWF" -eq 1 ] && echo -e "        ${GREEN}✅ ewfacquire disponible${NC}" || echo -e "        ${YELLOW}⚠️ ewfacquire absent — sudo apt install ewf-tools${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[3]${NC}  ${BOLD}AFF (Advanced Forensic Format)${NC}"
echo -e "        ${GREY}Extensions : .aff .afd .afm${NC}"
echo -e "        ${GREY}Format ouvert : compression + hash + métadonnées + chiffrement optionnel.${NC}"
echo -e "        ${GREY}Logiciels : affcat, affuse, Autopsy, Sleuth Kit, aimage${NC}"
[ "$_HAVE_AFF" -eq 1 ] && echo -e "        ${GREEN}✅ afflib disponible${NC}" || echo -e "        ${YELLOW}⚠️ afflib absent — sudo apt install afflib-tools${NC}"
echo ""

while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le format de sortie (1-3) : ${NC}"
    read -r FORMAT_CHOICE
    [ -z "$FORMAT_CHOICE" ] && { echo -e "${RED}❌ Veuillez choisir un format (1, 2 ou 3).${NC}"; continue; }
    case "$FORMAT_CHOICE" in
        1)
            if [ "$_HAVE_DC3DD" -ne 1 ]; then
                echo -e "${RED}❌ dc3dd n'est pas installé. Installez-le (sudo apt install dc3dd) ou choisissez un autre format.${NC}"
                continue
            fi
            OUTPUT_FORMAT="raw"
            ACQUIRE_TOOL="dc3dd"
            # Sous-choix de l'extension de sortie pour le format RAW.
            # Le contenu est identique (copie bit-à-bit) ; seule l'extension
            # du fichier de sortie change pour s'adapter aux attentes des
            # outils tiers (Autopsy, FTK, X-Ways...).
            echo ""
            echo -e "${BLUE}Format RAW : choisissez l'extension de sortie.${NC}"
            echo -e "  ${BOLD}${BLUE}[1]${NC}  ${BOLD}.raw${NC}  ${GREY}— extension générique RAW${NC}"
            echo -e "  ${BOLD}${BLUE}[2]${NC}  ${BOLD}.dd${NC}   ${GREY}— convention dd / dc3dd${NC}"
            echo -e "  ${BOLD}${BLUE}[3]${NC}  ${BOLD}.img${NC} ${GREY}— convention image disque${NC}"
            echo ""
            while true; do
                echo -ne "${BOLD}${YELLOW}Extension RAW (1-3) [2] : ${NC}"
                read -r RAW_EXT_CHOICE
                [ -z "$RAW_EXT_CHOICE" ] && RAW_EXT_CHOICE="2"
                case "$RAW_EXT_CHOICE" in
                    1) IMAGE_EXT="raw"; break ;;
                    2) IMAGE_EXT="dd";  break ;;
                    3) IMAGE_EXT="img"; break ;;
                    *) echo -e "${RED}❌ Choix invalide : $RAW_EXT_CHOICE. Entrez 1, 2 ou 3.${NC}"; continue ;;
                esac
            done
            echo -e "${GREEN}Format : RAW (dc3dd) — extension .$IMAGE_EXT${NC}"
            ;;
        2)
            if [ "$_HAVE_EWF" -ne 1 ]; then
                echo -e "${RED}❌ ewfacquire n'est pas installé. Installez-le (sudo apt install ewf-tools) ou choisissez un autre format.${NC}"
                continue
            fi
            OUTPUT_FORMAT="ewf"
            IMAGE_EXT="E01"
            ACQUIRE_TOOL="ewfacquire"
            echo -e "${GREEN}Format : E01 (ewfacquire)${NC}"
            ;;
        3)
            if [ "$_HAVE_AFF" -ne 1 ]; then
                echo -e "${RED}❌ afflib n'est pas installé. Installez-le (sudo apt install afflib-tools) ou choisissez un autre format.${NC}"
                continue
            fi
            OUTPUT_FORMAT="aff"
            IMAGE_EXT="aff"
            ACQUIRE_TOOL="affcat"
            echo -e "${GREEN}Format : AFF (afflib) — extension .aff${NC}"
            # Note : .afd (segmenté) et .afm (multi-fichiers) nécessitent l'outil
            # 'aimage' avec des options spécifiques. Le script utilise affcat qui
            # ne produit que du .aff ; seules les extensions réellement
            # réalisables sont donc proposées.
            ;;
        *)
            echo -e "${RED}❌ Choix invalide : $FORMAT_CHOICE. Entrez 1, 2 ou 3.${NC}"
            continue
            ;;
    esac
    break
done

clear_banner
echo -e "${BLUE}Disque source : ${BOLD}$SOURCE_DEV${NC}  ${GREY}• Format : ${BOLD}$OUTPUT_FORMAT${NC}"
echo ""
# ----------------------------------------------------------------------------
# Nom de l'image
# ----------------------------------------------------------------------------
echo -e "${GREY}Donnez un nom à cette image (sans extension).${NC}"
_default_name="image_$(date +%Y%m%d_%H%M%S)"
echo -e "${GREY}Par défaut : ${_default_name}${NC}"
while true; do
    echo -ne "${BOLD}${YELLOW}Nom de l'image [${_default_name}] : ${NC}"
    read -r IMAGE_NAME
    [ -z "$IMAGE_NAME" ] && IMAGE_NAME="$_default_name"
    # Nettoyer le nom : pas de séparateur de chemin, ni d'espaces en début/fin
    IMAGE_NAME=$(echo "$IMAGE_NAME" | tr -d '/' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    if [ -z "$IMAGE_NAME" ]; then
        echo -e "${RED}❌ Nom invalide. Ressayez.${NC}"
        continue
    fi
    break
done
IMAGE_ID="$IMAGE_NAME"
echo -e "${GREEN}Nom :${NC} ${BOLD}$IMAGE_ID${NC}"

# ============================================================================
# 3. SÉLECTION DE LA CIBLE (disque externe OU local)
# ============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sélection de la cible de stockage       ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREY}Où stocker l'image forensique ?${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[1]${NC}  ${BOLD}Disque cible externe${NC}  ${GREY}(recommandé)${NC}"
echo -e "        ${GREY}Monter un disque USB/externe pour y écrire l'image${NC}"
echo -e "  ${BOLD}${BLUE}[2]${NC}  ${BOLD}Emplacement local${NC}  ${GREY}(sur ce PC — vérification d'espace stricte)${NC}"
echo -e "        ${GREY}Choix du dossier de destination (réserve 20% du disque système)${NC}"
echo ""
echo -ne "${BOLD}${YELLOW}Entrez votre choix (1-2) : ${NC}"
read -r TARGET_MODE_CHOICE

case "$TARGET_MODE_CHOICE" in
    1)
        TARGET_MODE="external"
        echo -e "${GREEN}Mode : Disque cible externe${NC}"
        ;;
    2)
        TARGET_MODE="local"
        echo -e "${GREEN}Mode : Emplacement local${NC}"
        ;;
    *)
        # Remettre le disque source en RW avant d'abandonner
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        fail "Choix invalide : $TARGET_MODE_CHOICE"
        ;;
esac

TARGET_POINT=""
_cleanup_target() {
    if [ -n "$TARGET_POINT" ] && mountpoint -q "$TARGET_POINT" 2>/dev/null; then
        sudo umount "$TARGET_POINT" 2>/dev/null || sudo umount -l "$TARGET_POINT" 2>/dev/null || true
    fi
    [ -n "$TARGET_POINT" ] && [ -d "$TARGET_POINT" ] && sudo rmdir "$TARGET_POINT" 2>/dev/null || true
}
trap _cleanup_target SIGHUP SIGINT SIGTERM

if [ "$TARGET_MODE" = "external" ]; then
    # --- 3.1. Détection du disque cible externe ---
    echo ""
    echo -e "${YELLOW}Veuillez brancher le disque cible qui accueillera la copie.${NC}"
    echo -ne "${BOLD}${YELLOW}Appuyez sur Entrée une fois le disque branché... ${NC}"
    read -r
    sleep 2

    # Lister les disques amovibles (RM=1) non montés, en excluant la source
    TARGET_DEVICES=()
    TARGET_NUM=0
    while IFS= read -r line; do
        eval "$line"
        case "$NAME" in
            loop*|sr*|zram*) continue ;;
        esac
        # Exclure le disque source
        [ "/dev/$NAME" = "$SOURCE_DEV" ] && continue
        _rm=$(lsblk -no RM "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
        _mount=$(lsblk -no MOUNTPOINT "/dev/$NAME" 2>/dev/null | head -n1)
        _mount=${_mount:-}
        # On accepte les disques amovibles OU les disques USB non source
        _tran=$(lsblk -no TRAN "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
        if [ "$_rm" = "1" ] || [ "$_tran" = "usb" ]; then
            _vendor=$(lsblk -no VENDOR "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
            _serial=$(lsblk -no SERIAL "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
            _npart=$(lsblk -ln -o NAME "/dev/$NAME" 2>/dev/null | grep -c .)
            _npart=$((_npart - 1))
            [ "$_npart" -lt 0 ] && _npart=0
            TARGET_DEVICES[$TARGET_NUM]="$NAME"
            echo -e "  ${BOLD}${BLUE}[$((TARGET_NUM+1))]${NC}  ${BOLD}/dev/$NAME${NC}  ${GREY}• Taille:${NC} ${BOLD}$SIZE${NC}  ${GREY}• Modèle:${NC} ${BOLD}${MODEL:-?}${NC}"
            echo -e "       ${GREY}Bus:${NC} ${_tran:-?}  ${GREY}Vendor:${NC} ${_vendor:-?}  ${GREY}Série:${NC} ${_serial:-?}  ${GREY}Partitions:${NC} $_npart  ${GREY}Monté:${NC} ${_mount:-non}"
            echo ""
            TARGET_NUM=$((TARGET_NUM + 1))
        fi
    done < <(lsblk -P -o NAME,TYPE,SIZE,MODEL 2>/dev/null | grep 'TYPE="disk"')

    if [ "$TARGET_NUM" -eq 0 ]; then
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        fail "Aucun disque cible externe détecté. Branchez un disque USB et réessayez."
    fi

    while true; do
        echo -ne "${BOLD}${YELLOW}Entrez le numéro du disque cible (ou \"q\" pour quitter) : ${NC}"
        read -r TARGET_CHOICE
        if [ "$TARGET_CHOICE" = "q" ]; then
            sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
            echo -e "${YELLOW}Annulé.${NC}"
            _cleanup_target
            final_pause
            exit 0
        fi
        if ! [[ "$TARGET_CHOICE" =~ ^[0-9]+$ ]] || [ "$TARGET_CHOICE" -lt 1 ] || [ "$TARGET_CHOICE" -gt "$TARGET_NUM" ]; then
            echo -e "${RED}❌ Numéro invalide. Entrez un numéro entre 1 et $TARGET_NUM.${NC}"
            continue
        fi
        TARGET_DEV="/dev/${TARGET_DEVICES[$((TARGET_CHOICE-1))]}"
        break
    done

    echo ""
    echo -e "${GREEN}Disque cible sélectionné :${NC} ${BOLD}$TARGET_DEV${NC}"

    # Déverrouiller le disque cible (il était peut-être en RO)
    sudo blockdev --setrw "$TARGET_DEV" 2>/dev/null || true

    # Chercher une partition montable sur le disque cible (1ère ou 2e partition)
    TARGET_PART=""
    for _p in 1 2 3 4 5; do
        _cand="${TARGET_DEV}${_p}"
        # nvme : nvme0n1p1
        case "$TARGET_DEV" in
            /dev/nvme*|/dev/mmcblk*) _cand="${TARGET_DEV}p${_p}" ;;
        esac
        if [ -b "$_cand" ]; then
            _fst=$(lsblk -no FSTYPE "$_cand" 2>/dev/null | head -n1 | tr -d '[:space:]')
            if [ -n "$_fst" ]; then
                TARGET_PART="$_cand"
                break
            fi
        fi
    done

    if [ -z "$TARGET_PART" ]; then
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        fail "Aucune partition montable trouvée sur $TARGET_DEV. Partitionnez/formatez le disque cible d'abord."
    fi

    echo -e "${YELLOW}Montage de la partition cible $TARGET_PART en lecture/écriture...${NC}"
    TARGET_POINT=$(mktemp -dp /tmp/ .vigilimg.XXXXXXXX)
    _mount_opts=""
    _fst=$(lsblk -no FSTYPE "$TARGET_PART" 2>/dev/null | head -n1 | tr -d '[:space:]')
    [ "$_fst" = "ntfs" ] && _mount_opts="-o big_writes"
    if ! sudo mount $_mount_opts "$TARGET_PART" "$TARGET_POINT" 2>/dev/null; then
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        _cleanup_target
        fail "Échec du montage de $TARGET_PART"
    fi

    # Vérifier qu'on peut écrire
    if ! sudo touch "$TARGET_POINT/.vigil_rw_test" 2>/dev/null; then
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        _cleanup_target
        fail "Impossible d'écrire sur la partition cible $TARGET_PART"
    fi
    sudo rm -f "$TARGET_POINT/.vigil_rw_test" 2>/dev/null || true
    echo -e "${GREEN}✅ Partition cible montée :${NC} $TARGET_PART → $TARGET_POINT"

    # Dossier d'images sur la cible
    IMAGE_DIR="$TARGET_POINT/vigil_images"
    sudo mkdir -p "$IMAGE_DIR" 2>/dev/null || {
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        _cleanup_target
        fail "Impossible de créer $IMAGE_DIR"
    }
    IMAGE_BASE="$IMAGE_DIR/$(echo "$IMAGE_ID" | tr ' /' '__')"

else
    # --- 3.2. Emplacement local : choix du dossier + vérification d'espace stricte ---
    clear_banner
    echo -e "${BLUE}Source : ${BOLD}$SOURCE_DEV${NC}  ${GREY}• Format : ${BOLD}$OUTPUT_FORMAT${NC}"
    echo ""
    echo -e "${GREY}Choisissez le dossier de destination de l'image.${NC}"
    _default_dir="/tmp/images"
    echo -e "${GREY}Par défaut : ${_default_dir}${NC}"
    while true; do
        echo -ne "${BOLD}${YELLOW}Dossier de destination [${_default_dir}] : ${NC}"
        read -r IMAGE_DIR
        [ -z "$IMAGE_DIR" ] && IMAGE_DIR="$_default_dir"
        # Nettoyer et convertir en chemin absolu
        IMAGE_DIR=$(echo "$IMAGE_DIR" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        case "$IMAGE_DIR" in
            /*) ;;
            *) IMAGE_DIR="$PWD/$IMAGE_DIR" ;;
        esac
        if [ -z "$IMAGE_DIR" ]; then
            echo -e "${RED}❌ Chemin invalide. Ressayez.${NC}"
            continue
        fi
        break
    done
    echo -e "${GREEN}Dossier :${NC} ${BOLD}$IMAGE_DIR${NC}"

    echo ""
    echo -e "${YELLOW}Vérification de l'espace disque local...${NC}"

    # Point de montage du système de fichiers qui contient le dossier choisi
    ROOT_FS=$(df --output=target "$IMAGE_DIR" 2>/dev/null | tail -1 | tr -d '[:space:]')
    [ -z "$ROOT_FS" ] && ROOT_FS="/"
    # Taille totale et disponible du système de fichiers (en octets)
    TOTAL_BYTES=$(df -B1 --output=size "$ROOT_FS" | tail -1 | tr -d '[:space:]')
    AVAIL_BYTES=$(df -B1 --output=avail "$ROOT_FS" | tail -1 | tr -d '[:space:]')
    USED_BYTES=$((TOTAL_BYTES - AVAIL_BYTES))

    # Réserve obligatoire : 20% de la taille totale du disque système
    RESERVE_BYTES=$((TOTAL_BYTES / 5))
    # Espace réellement utilisable = disponible - réserve
    USABLE_BYTES=$((AVAIL_BYTES - RESERVE_BYTES))

    # Taille du disque source en octets
    SOURCE_BYTES=$(sudo blockdev --getsize64 "$SOURCE_DEV" 2>/dev/null || echo 0)

    _fmt_human() {
        local b=$1
        if [ "$b" -ge 1073741824 ]; then
            awk -v b="$b" 'BEGIN{printf "%.1f Go", b/1073741824}'
        elif [ "$b" -ge 1048576 ]; then
            awk -v b="$b" 'BEGIN{printf "%.1f Mo", b/1048576}'
        else
            awk -v b="$b" 'BEGIN{printf "%.1f Ko", b/1024}'
        fi
    }

    echo -e "  ${GREY}Disque système (${ROOT_FS}):${NC}"
    echo -e "    ${GREY}Taille totale :${NC} ${BOLD}$(_fmt_human $TOTAL_BYTES)${NC}"
    echo -e "    ${GREY}Espace libre  :${NC} ${BOLD}$(_fmt_human $AVAIL_BYTES)${NC}"
    echo -e "    ${GREY}Réserve (20%) :${NC} ${BOLD}$(_fmt_human $RESERVE_BYTES)${NC} ${YELLOW}(gardée pour le système)${NC}"
    echo -e "    ${GREY}Espace utilisable :${NC} ${BOLD}$(_fmt_human $USABLE_BYTES)${NC}"
    echo ""
    echo -e "  ${GREY}Disque source :${NC} ${BOLD}$SOURCE_DEV${NC}  ${GREY}• Taille :${NC} ${BOLD}$(_fmt_human $SOURCE_BYTES)${NC}"
    echo ""

    if [ "$USABLE_BYTES" -le 0 ]; then
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        fail "Espace local insuffisant : la réserve de 20% n'est pas satisfaite. Utilisez un disque cible externe."
    fi

    if [ "$SOURCE_BYTES" -gt "$USABLE_BYTES" ]; then
        echo -e "${RED}❌ Espace local insuffisant.${NC}"
        echo -e "${YELLOW}   Le disque source ($(_fmt_human $SOURCE_BYTES)) est plus grand que l'espace${NC}"
        echo -e "${YELLOW}   utilisable ($(_fmt_human $USABLE_BYTES), après réserve de 20%).${NC}"
        echo -e "${YELLOW}   La compression EWF peut réduire la taille, mais ce n'est pas garanti.${NC}"
        echo ""
        echo -ne "${BOLD}${YELLOW}Continuer quand même ? (o/n) : ${NC}"
        read -r LOCAL_FORCE
        if [ "$LOCAL_FORCE" != "o" ] && [ "$LOCAL_FORCE" != "O" ] && [ "$LOCAL_FORCE" != "y" ] && [ "$LOCAL_FORCE" != "Y" ]; then
            sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
            echo -e "${YELLOW}Annulé.${NC}"
            final_pause
            exit 0
        fi
        echo -e "${YELLOW}⚠️  Poursuite sous risque de saturation du disque système.${NC}"
    else
        echo -e "${GREEN}✅ Espace local suffisant (après réserve de 20%).${NC}"
    fi

    # Création du dossier de destination local (choisi plus haut)
    mkdir -p "$IMAGE_DIR" 2>/dev/null || {
        # Réessayer via sudo si l'utilisateur n'a pas les droits
        sudo mkdir -p "$IMAGE_DIR" 2>/dev/null || {
            sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
            fail "Impossible de créer $IMAGE_DIR"
        }
    }
    IMAGE_BASE="$IMAGE_DIR/$(echo "$IMAGE_ID" | tr ' /' '__')"
fi

clear_banner
echo -e "${BLUE}Source : ${BOLD}$SOURCE_DEV${NC}  ${GREY}• Format : ${BOLD}$OUTPUT_FORMAT${NC}  ${GREY}• Cible : ${BOLD}${IMAGE_DIR}${NC}"
echo ""
# ============================================================================
# 4. ACQUISITION (selon le format choisi)
# ============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Acquisition de l'image forensique        ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Début de l'acquisition $OUTPUT_FORMAT ($ACQUIRE_TOOL) de $SOURCE_DEV...${NC}"
echo -e "${GREY}Cela peut être long selon la taille du disque et le type de bus.${NC}"
echo -e "${GREY}Le disque source est accédé en lecture seule.${NC}"
echo ""

START_TS=$(date -R)

# Description commune pour les métadonnées
_device_info=$(lsblk -d -o NAME,SIZE,VENDOR,MODEL,SERIAL,REV,TRAN "$SOURCE_DEV" 2>/dev/null | tail -1)
_description="Vigil imager | Source: $_device_info | User: $ACTIVE_USER"
_imager_error=""

case "$OUTPUT_FORMAT" in
    raw)
        # --- RAW via dc3dd : copie bit-à-bit fiable avec hash intégré ---
        # dc3dd calcule sha256 en parallèle de la copie ; l'extension de sortie
        # (.raw/.dd/.img) est choisie plus haut et portée par $IMAGE_EXT.
        IMAGE_FILE="${IMAGE_BASE}.${IMAGE_EXT}"
        echo -e "${GREY}Format RAW : copie bit-à-bit, hash SHA-256, extension .$IMAGE_EXT${NC}"
        echo -e "${GREY}Commande : dc3dd if=$SOURCE_DEV of=$IMAGE_FILE hash=sha256 ...${NC}"
        echo ""
        if sudo dc3dd if="$SOURCE_DEV" of="$IMAGE_FILE" hash=sha256 log="${IMAGE_BASE}.log" 2>&1; then
            echo ""
            echo -e "${GREEN}✅ Acquisition RAW terminée avec succès.${NC}"
        else
            _rc=$?
            echo ""
            echo -e "${RED}❌ Erreur lors de l'acquisition RAW (code $_rc).${NC}"
            ERRORS=$((ERRORS + 1))
            _imager_error="yes"
        fi
        ;;
    ewf)
        # --- E01 via ewfacquire : compression + hash + métadonnées ---
        # Options : compression best, hash sha1, segments 3GiB, mode batch (-u),
        # lecture seule (-w), verbeux (-v).
        EWF_OPTS="-c best -d sha1 -S 3GiB -u -v -w"
        echo -e "${GREY}Format E01 : compression + hash + métadonnées, extensions .E01 (.E02...)${NC}"
        echo -e "${GREY}Commande : ewfacquire $EWF_OPTS -D \"...\" -C \"$IMAGE_ID\" -t $IMAGE_BASE $SOURCE_DEV${NC}"
        echo ""
        if sudo ewfacquire $EWF_OPTS -D "$_description" -C "$IMAGE_ID" -t "$IMAGE_BASE" "$SOURCE_DEV" 2>&1; then
            echo ""
            echo -e "${GREEN}✅ Acquisition EWF terminée avec succès.${NC}"
        else
            _rc=$?
            echo ""
            echo -e "${RED}❌ Erreur lors de l'acquisition EWF (code $_rc).${NC}"
            ERRORS=$((ERRORS + 1))
            _imager_error="yes"
        fi
        ;;
    aff)
        # --- AFF via affcat : format ouvert avec compression + métadonnées ---
        # affcat lit le disque source et produit un fichier .aff. On ajoute les
        # métadonnées Vigil via affsign/affmeta si disponible, sinon via le log.
        IMAGE_FILE="${IMAGE_BASE}.aff"
        echo -e "${GREY}Format AFF : compression + métadonnées, extensions .aff/.afd/.afm${NC}"
        echo -e "${GREY}Commande : affcat -r $SOURCE_DEV > $IMAGE_FILE${NC}"
        echo ""
        # affcat -r copie en lecture seule le contenu du device vers la sortie
        # standard qu'on redirige vers le fichier .aff
        if sudo affcat -r "$SOURCE_DEV" 2>"${IMAGE_BASE}.log" | sudo dd of="$IMAGE_FILE" bs=1M 2>>"${IMAGE_BASE}.log"; then
            echo ""
            echo -e "${GREEN}✅ Acquisition AFF terminée avec succès.${NC}"
        else
            _rc=$?
            echo ""
            echo -e "${RED}❌ Erreur lors de l'acquisition AFF (code $_rc).${NC}"
            ERRORS=$((ERRORS + 1))
            _imager_error="yes"
        fi
        ;;
    *)
        echo -e "${RED}❌ Format inconnu : $OUTPUT_FORMAT${NC}"
        ERRORS=$((ERRORS + 1))
        _imager_error="yes"
        ;;
esac

STOP_TS=$(date -R)

# ============================================================================
# 4.5 CHECKSUM SHA-256 DE L'IMAGE
# ============================================================================
# Calcul d'un SHA-256 du fichier image de sortie pour vérifier l'intégrité
# du fichier de preuve (chaque segment E01/AFF est hashé séparément).
echo ""
echo -e "${YELLOW}Calcul du checksum SHA-256 de l'image...${NC}"
CHECKSUM_FILE="${IMAGE_BASE}.sha256"
_CHECKSUM_OK=1
> "$CHECKSUM_FILE" 2>/dev/null || sudo tee "$CHECKSUM_FILE" >/dev/null

case "$OUTPUT_FORMAT" in
    raw)
        _imgfile="${IMAGE_BASE}.${IMAGE_EXT}"
        if [ -f "$_imgfile" ]; then
            _sum=$(sudo sha256sum "$_imgfile" 2>/dev/null | awk '{print $1}')
            if [ -n "$_sum" ]; then
                echo "$_sum  $(basename "$_imgfile")" | sudo tee -a "$CHECKSUM_FILE" >/dev/null
                echo -e "${GREEN}✓ SHA-256 ($OUTPUT_FORMAT) :${NC} $_sum"
            else
                echo -e "${RED}❌ Échec du calcul SHA-256 de $_imgfile${NC}"
                _CHECKSUM_OK=0
            fi
        fi
        ;;
    ewf)
        # Hacher chaque segment .E01 .E02 ...
        _found_seg=0
        for _seg in "${IMAGE_BASE}".E0*; do
            [ -f "$_seg" ] || continue
            _found_seg=1
            _sum=$(sudo sha256sum "$_seg" 2>/dev/null | awk '{print $1}')
            if [ -n "$_sum" ]; then
                echo "$_sum  $(basename "$_seg")" | sudo tee -a "$CHECKSUM_FILE" >/dev/null
                echo -e "${GREEN}✓ SHA-256 ${BOLD}$(basename "$_seg")${NC}${GREEN} :${NC} $_sum"
            else
                echo -e "${RED}❌ Échec du calcul SHA-256 de $_seg${NC}"
                _CHECKSUM_OK=0
            fi
        done
        [ "$_found_seg" -eq 0 ] && { echo -e "${RED}❌ Aucun segment .E01 trouvé à hacher.${NC}"; _CHECKSUM_OK=0; }
        ;;
    aff)
        _imgfile="${IMAGE_BASE}.aff"
        if [ -f "$_imgfile" ]; then
            _sum=$(sudo sha256sum "$_imgfile" 2>/dev/null | awk '{print $1}')
            if [ -n "$_sum" ]; then
                echo "$_sum  $(basename "$_imgfile")" | sudo tee -a "$CHECKSUM_FILE" >/dev/null
                echo -e "${GREEN}✓ SHA-256 ($OUTPUT_FORMAT) :${NC} $_sum"
            else
                echo -e "${RED}❌ Échec du calcul SHA-256 de $_imgfile${NC}"
                _CHECKSUM_OK=0
            fi
        fi
        ;;
esac
if [ "$_CHECKSUM_OK" -eq 1 ]; then
    echo -e "${GREEN}✓ Checksum enregistré :${NC} $CHECKSUM_FILE"
else
    echo -e "${YELLOW}⚠️  Checksum incomplet — vérifiez l'image.${NC}"
    ERRORS=$((ERRORS + 1))
fi


# ============================================================================
# 5. VÉRIFICATION ET JOURNAL
# ============================================================================
LOG_FILE="${IMAGE_BASE}.log"
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo -e "${BLUE}=== Journal d'acquisition ===${NC}"
    # Vérifier les erreurs de lecture signalées dans le log
    if grep -i error "$LOG_FILE" 2>/dev/null | grep -qi read; then
        echo -e "${YELLOW}⚠️  Le journal signale des problèmes de lecture sur le disque source.${NC}"
    fi
else
    if [ -z "$_imager_error" ]; then
        echo -e "${YELLOW}⚠️  Journal d'acquisition introuvable ($LOG_FILE).${NC}"
    fi
fi

# Ajouter les métadonnées Vigil au journal
if [ -f "$LOG_FILE" ]; then
    {
        echo ""
        echo "=== Métadonnées Vigil ==="
        echo "Acquiry started at: $START_TS"
        echo "Acquiry completed at: $STOP_TS"
        echo "Source device: $SOURCE_DEV ($_device_info)"
        echo "Image identification: $IMAGE_ID"
        echo "User: $ACTIVE_USER"
    } | sudo tee -a "$LOG_FILE" > /dev/null 2>&1 || true
    echo -e "${GREEN}✅ Métadonnées ajoutées au journal :${NC} $LOG_FILE"
fi

# Synchroniser et nettoyer
echo ""
echo -e "${YELLOW}Synchronisation des écritures...${NC}"
sync
sleep 2

# Libérer le disque source (remise en RW)
echo -e "${YELLOW}Déverrouillage du disque source...${NC}"
sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true

# Démonter la cible si externe
_cleanup_target

echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}❌ Imagerie terminée avec $ERRORS erreur(s).${NC}"
    echo -e "${YELLOW}   Vérifiez le journal : $LOG_FILE${NC}"
else
    log_action "disk_imager" "success" "Copie forensique terminée" "$IMAGE_BASE"
    echo -e "${GREEN}✅ Copie forensique terminée avec succès.${NC}"
    case "$OUTPUT_FORMAT" in
        raw) echo -e "${GREEN}   Image :${NC} ${IMAGE_BASE}.${IMAGE_EXT}" ;;
        ewf) echo -e "${GREEN}   Image :${NC} ${IMAGE_BASE}.E01" ;;
        aff) echo -e "${GREEN}   Image :${NC} ${IMAGE_BASE}.aff" ;;
    esac
    echo -e "${GREEN}   Journal :${NC} $LOG_FILE"
    if [ "$TARGET_MODE" = "external" ]; then
        echo -e "${YELLOW}   Le disque cible peut être retiré.${NC}"
    fi
fi

final_pause
