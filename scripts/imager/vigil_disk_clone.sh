#!/bin/bash
set -uo pipefail

# --- Clonage bit-a-bit d'un disque vers un autre peripherique ---
#
# Copie le contenu integral d'un disque source vers un disque cible, secteur
# par secteur, via dc3dd. Le disque source est verrouille en lecture seule
# (blockdev --setro) afin de ne jamais l'alterer. Le disque cible doit etre
# au moins aussi grand que le disque source (securite anti-depassement).
#
# Apres la copie, si de l'espace non assigne reste sur le disque cible, le
# script propose de reparer/etendre les partitions (growpart + resize2fs pour
# ext, ou reparation MBR/GPT) pour exploiter le reste du disque.

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

# --- Contexte actif (utilisateur + projet) : non bloquant pour le clonage ---
# Le clonage forensique reste possible sans utilisateur/projet actifs. Si un
# contexte existe, on l'utilise pour tracer l'action dans la chaîne de
# custody ; sinon, on réalise la copie quand même et on n'écrit pas de log.
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
PROJECTS_DIR="$VIGIL_BASE/data/projects"

ERRORS=0

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
    log_action "disk_clone" "error" "$1"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

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

_fmt_human() {
    local b=$1
    if [ "$b" -ge 1099511627776 ]; then
        awk -v b="$b" 'BEGIN{printf "%.1f To", b/1099511627776}'
    elif [ "$b" -ge 1073741824 ]; then
        awk -v b="$b" 'BEGIN{printf "%.1f Go", b/1073741824}'
    elif [ "$b" -ge 1048576 ]; then
        awk -v b="$b" 'BEGIN{printf "%.1f Mo", b/1048576}'
    else
        awk -v b="$b" 'BEGIN{printf "%.1f Ko", b/1024}'
    fi
}

# --- Verification des privileges et dependances ---
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Ce script nécessite des privilèges root pour accéder aux disques.${NC}"
    echo -e "${YELLOW}    Vérifiez la configuration sudo de l'utilisateur courant.${NC}"
fi

clear
print_banner
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING_DEPS=0
for cmd in lsblk blockdev sync; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING_DEPS=$((MISSING_DEPS + 1))
    fi
done
if ! command -v dc3dd >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  dc3dd absent — sudo apt install dc3dd (recommandé pour la fiabilité)${NC}"
    echo -e "${GREY}    Fallback possible via dd si dc3dd n'est pas installé.${NC}"
fi
if [ "$MISSING_DEPS" -gt 0 ]; then
    fail "Dépendances obligatoires manquantes ($MISSING_DEPS). Installez-les avant de continuer."
fi

echo ""
echo -e "${BLUE}Utilisateur : ${ACTIVE_USER}${NC}"
echo ""
echo -e "${YELLOW}⚠️  CLONAGE DE DISQUE${NC}"
echo -e "${GREY}Copie bit-à-bit d'un disque source vers un disque cible.${NC}"
echo -e "${GREY}Le disque source est ACCÉDÉ EN LECTURE SEULE uniquement.${NC}"
echo -e "${GREY}Le disque cible est ENTIÈREMENT ÉCRASÉ.${NC}"
echo ""

# ============================================================================
# 1. SELECTION DU DISQUE SOURCE
# ============================================================================
clear_banner
echo -e "${BLUE}Utilisateur : ${ACTIVE_USER}${NC}"
echo ""
log_action "disk_clone" "start" "Début du clonage forensique" ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1/4 : Sélection du disque source   ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREY}Le disque source est le disque à copier (lecture seule).${NC}"
echo ""

SOURCE_DEVICES=()
SOURCE_SIZES=()
SOURCE_NUM=0

# Detecter le disque systeme (porte /) pour l'exclure.
SYSTEM_DISK=""
_root_part=$(lsblk -ln -o NAME,MOUNTPOINT 2>/dev/null | awk '$2=="/"{print $1}' | head -1)
if [ -n "$_root_part" ]; then
    case "$_root_part" in
        nvme*p*|mmcblk*p*) SYSTEM_DISK=$(echo "$_root_part" | sed -E 's/p[0-9]+$//') ;;
        *)                 SYSTEM_DISK=$(echo "$_root_part" | sed -E 's/[0-9]+$//') ;;
    esac
fi
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
    case "$NAME" in
        loop*|sr*|zram*) continue ;;
    esac
    # Exclure le disque systeme
    if [ -n "$SYSTEM_DISK" ] && [ "$NAME" = "$SYSTEM_DISK" ]; then
        continue
    fi
    _vendor=$(lsblk -no VENDOR "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _serial=$(lsblk -no SERIAL "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _tran=$(lsblk -no TRAN "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _rm=$(lsblk -no RM "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _ro=$(lsblk -no RO "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _fstype=$(lsblk -no FSTYPE "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _mount=$(lsblk -no MOUNTPOINT "/dev/$NAME" 2>/dev/null | head -n1)
    _mount=${_mount:-}
    _npart=$(lsblk -ln -o NAME "/dev/$NAME" 2>/dev/null | grep -c .)
    _npart=$((_npart - 1))
    [ "$_npart" -lt 0 ] && _npart=0
    _bytes=$(sudo blockdev --getsize64 "/dev/$NAME" 2>/dev/null || echo 0)
    [ "$_ro" = "1" ] && _rotype="${YELLOW}[RO]${NC}" || _rotype=""
    [ "$_rm" = "1" ] && _rmtype="${GREY}(amovible)${NC}" || _rmtype="${GREY}(interne)${NC}"

    SOURCE_DEVICES[$SOURCE_NUM]="$NAME"
    SOURCE_SIZES[$SOURCE_NUM]="$_bytes"
    echo -e "  ${BOLD}${BLUE}[$((SOURCE_NUM+1))]${NC}  ${BOLD}/dev/$NAME${NC}  ${GREY}• Taille:${NC} ${BOLD}$SIZE${NC}  ${GREY}• Modèle:${NC} ${BOLD}${MODEL:-?}${NC} ${_rotype}"
    echo -e "       ${GREY}Bus:${NC} ${_tran:-?}  ${GREY}Vendor:${NC} ${_vendor:-?}  ${GREY}Série:${NC} ${_serial:-?}  ${_rmtype}"
    echo -e "       ${GREY}Partitions:${NC} ${_npart}  ${GREY}FS:${NC} ${_fstype:-aucun}  ${GREY}Monté:${NC} ${_mount:-non}"
    echo ""
    SOURCE_NUM=$((SOURCE_NUM + 1))
done < <(lsblk -P -o NAME,TYPE,SIZE,MODEL 2>/dev/null | grep 'TYPE="disk"')

if [ "$SOURCE_NUM" -eq 0 ]; then
    fail "Aucun disque source détecté (hors disque système). Branchez un périphérique à cloner."
fi

while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le numéro du disque source à cloner (ou \"q\" pour quitter) : ${NC}"
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
    SOURCE_BYTES=${SOURCE_SIZES[$((SOURCE_CHOICE-1))]}
    break
done

echo ""
echo -e "${GREEN}Disque source sélectionné :${NC} ${BOLD}$SOURCE_DEV${NC} (${BOLD}$(_fmt_human $SOURCE_BYTES)${NC})"

# Verifier que le disque source n'est pas monte
SOURCE_MOUNTED=$(lsblk -ln -o MOUNTPOINT "$SOURCE_DEV" 2>/dev/null | grep -v '^$' | head -1 || true)
if [ -n "$SOURCE_MOUNTED" ]; then
    echo -e "${YELLOW}⚠️  Le disque source $SOURCE_DEV est monté (ex. $SOURCE_MOUNTED).${NC}"
    echo -e "${YELLOW}    Il sera forcé en lecture seule avant la copie.${NC}"
fi

# Verrouiller le disque source en lecture seule (garantie d'integrite)
echo -e "${YELLOW}Verrouillage du disque source en lecture seule...${NC}"
if sudo blockdev --setro "$SOURCE_DEV" 2>/dev/null; then
    echo -e "${GREEN}✅ Disque source verrouillé en lecture seule.${NC}"
else
    echo -e "${YELLOW}⚠️  blockdev --setro a échoué sur le disque source.${NC}"
fi
_ro_state=$(lsblk -no RO "$SOURCE_DEV" 2>/dev/null | head -n1 | tr -d '[:space:]')
if [ "$_ro_state" != "1" ]; then
    sudo blockdev --setro "$SOURCE_DEV" 2>/dev/null || true
    _ro_state=$(lsblk -no RO "$SOURCE_DEV" 2>/dev/null | head -n1 | tr -d '[:space:]')
fi
if [ "$_ro_state" != "1" ]; then
    fail "Impossible de verrouiller le disque source $SOURCE_DEV en lecture seule. Abandon (sécurité)."
fi
echo -e "${GREEN}✓ Lecture seule confirmée (RO=1) sur $SOURCE_DEV.${NC}"

# ============================================================================
# 2. SELECTION DU DISQUE CIBLE
# ============================================================================
clear_banner
echo -e "${BLUE}Source : ${BOLD}$SOURCE_DEV${NC}  ${GREY}• Taille :${NC} ${BOLD}$(_fmt_human $SOURCE_BYTES)${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2/4 : Sélection du disque cible     ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREY}Le disque cible recevra la copie (ENTIÈREMENT ÉCRASÉ).${NC}"
echo -e "${GREY}Il doit être au moins aussi grand que la source ($(_fmt_human $SOURCE_BYTES)).${NC}"
echo ""

TARGET_DEVICES=()
TARGET_SIZES=()
TARGET_NUM=0

while IFS= read -r line; do
    eval "$line"
    case "$NAME" in
        loop*|sr*|zram*) continue ;;
    esac
    # Exclure le disque systeme
    if [ -n "$SYSTEM_DISK" ] && [ "$NAME" = "$SYSTEM_DISK" ]; then
        continue
    fi
    # Exclure le disque source
    [ "/dev/$NAME" = "$SOURCE_DEV" ] && continue
    _vendor=$(lsblk -no VENDOR "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _serial=$(lsblk -no SERIAL "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _tran=$(lsblk -no TRAN "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _rm=$(lsblk -no RM "/dev/$NAME" 2>/dev/null | head -n1 | tr -d '[:space:]')
    _mount=$(lsblk -no MOUNTPOINT "/dev/$NAME" 2>/dev/null | head -n1)
    _mount=${_mount:-}
    _bytes=$(sudo blockdev --getsize64 "/dev/$NAME" 2>/dev/null || echo 0)
    [ "$_rm" = "1" ] && _rmtype="${GREY}(amovible)${NC}" || _rmtype="${GREY}(interne)${NC}"

    # Avertir si la cible est trop petite (en rouge), OK si >= source
    if [ "$_bytes" -ge "$SOURCE_BYTES" ]; then
        _sizetag="${GREEN}✓ ${BOLD}$SIZE${NC}  ${GREY}(taille OK)${NC}"
    else
        _sizetag="${RED}✗ ${BOLD}$SIZE${NC}  ${RED}(trop petit — source: $(_fmt_human $SOURCE_BYTES))${NC}"
    fi

    TARGET_DEVICES[$TARGET_NUM]="$NAME"
    TARGET_SIZES[$TARGET_NUM]="$_bytes"
    echo -e "  ${BOLD}${BLUE}[$((TARGET_NUM+1))]${NC}  ${BOLD}/dev/$NAME${NC}  ${GREY}• Taille:${NC} ${BOLD}${MODEL:-?}${NC} ${_sizetag}"
    echo -e "       ${GREY}Bus:${NC} ${_tran:-?}  ${GREY}Vendor:${NC} ${_vendor:-?}  ${GREY}Série:${NC} ${_serial:-?}  ${_rmtype}"
    echo -e "       ${GREY}Monté:${NC} ${_mount:-non}"
    echo ""
    TARGET_NUM=$((TARGET_NUM + 1))
done < <(lsblk -P -o NAME,TYPE,SIZE,MODEL 2>/dev/null | grep 'TYPE="disk"')

if [ "$TARGET_NUM" -eq 0 ]; then
    sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
    fail "Aucun disque cible détecté. Branchez un disque cible (au moins $(_fmt_human $SOURCE_BYTES))."
fi

while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le numéro du disque cible (ou \"q\" pour quitter) : ${NC}"
    read -r TARGET_CHOICE
    if [ "$TARGET_CHOICE" = "q" ]; then
        sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
        echo -e "${YELLOW}Annulé.${NC}"
        final_pause
        exit 0
    fi
    if ! [[ "$TARGET_CHOICE" =~ ^[0-9]+$ ]] || [ "$TARGET_CHOICE" -lt 1 ] || [ "$TARGET_CHOICE" -gt "$TARGET_NUM" ]; then
        echo -e "${RED}❌ Numéro invalide. Entrez un numéro entre 1 et $TARGET_NUM.${NC}"
        continue
    fi
    TARGET_DEV="/dev/${TARGET_DEVICES[$((TARGET_CHOICE-1))]}"
    TARGET_BYTES=${TARGET_SIZES[$((TARGET_CHOICE-1))]}
    break
done

echo ""
echo -e "${GREEN}Disque cible sélectionné :${NC} ${BOLD}$TARGET_DEV${NC} (${BOLD}$(_fmt_human $TARGET_BYTES)${NC})"

# --- Securite anti-depassement : la cible doit etre >= source ---
if [ "$TARGET_BYTES" -lt "$SOURCE_BYTES" ]; then
    echo ""
    echo -e "${RED}❌ Disque cible trop petit.${NC}"
    echo -e "${YELLOW}   Source : $(_fmt_human $SOURCE_BYTES) ($SOURCE_DEV)${NC}"
    echo -e "${YELLOW}   Cible  : $(_fmt_human $TARGET_BYTES) ($TARGET_DEV)${NC}"
    echo -e "${YELLOW}   Le disque cible ne peut pas contenir toute la source.${NC}"
    sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
    fail "Disque cible insuffisant. Branchez un disque d'au moins $(_fmt_human $SOURCE_BYTES)."
fi

if [ "$TARGET_BYTES" -eq "$SOURCE_BYTES" ]; then
    echo -e "${GREEN}✓ Taille cible identique à la source : copie exacte.${NC}"
else
    _diff=$((TARGET_BYTES - SOURCE_BYTES))
    echo -e "${GREEN}✓ Taille cible suffisante.${NC} ${GREY}Espace restant après copie : $(_fmt_human $_diff).${NC}"
fi

# Verifier que le disque cible n'est pas monte
TARGET_MOUNTED=$(lsblk -ln -o MOUNTPOINT "$TARGET_DEV" 2>/dev/null | grep -v '^$' | head -1 || true)
if [ -n "$TARGET_MOUNTED" ]; then
    echo -e "${YELLOW}⚠️  Le disque cible $TARGET_DEV est monté (ex. $TARGET_MOUNTED).${NC}"
    echo -e "${YELLOW}    Démontage des partitions cibles...${NC}"
    while IFS= read -r mp; do
        [ -n "$mp" ] && sudo umount "$mp" 2>/dev/null || true
    done < <(lsblk -ln -o MOUNTPOINT "$TARGET_DEV" 2>/dev/null)
fi

# Deverrouiller la cible en lecture/écriture
sudo blockdev --setrw "$TARGET_DEV" 2>/dev/null || true

# ============================================================================
# 3. CONFIRMATION + COPIE
# ============================================================================
clear_banner
echo -e "${BLUE}Source : ${BOLD}$SOURCE_DEV${NC}  ${GREY}• ${BOLD}$(_fmt_human $SOURCE_BYTES)${NC}"
echo -e "${BLUE}Cible  : ${BOLD}$TARGET_DEV${NC}  ${GREY}• ${BOLD}$(_fmt_human $TARGET_BYTES)${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 3/4 : Clonage bit-à-bit            ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${RED}⚠️  ATTENTION : le disque cible $TARGET_DEV sera ENTIÈREMENT ÉCRASÉ.${NC}"
echo -e "${RED}    Toutes les données présentes dessus seront définitivement perdues.${NC}"
echo ""
echo -ne "${BOLD}${YELLOW}Confirmer le clonage de $SOURCE_DEV vers $TARGET_DEV ? (oui/non) : ${NC}"
read -r CONFIRM
if [ "$CONFIRM" != "oui" ] && [ "$CONFIRM" != "o" ] && [ "$CONFIRM" != "O" ]; then
    sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
    echo -e "${YELLOW}Annulé.${NC}"
    final_pause
    exit 0
fi

echo ""
START_TS=$(date -R)
echo -e "${YELLOW}Début du clonage bit-à-bit de $SOURCE_DEV vers $TARGET_DEV...${NC}"
echo -e "${GREY}Cela peut être long selon la taille du disque et le type de bus.${NC}"
echo -e "${GREY}Le disque source est accédé en lecture seule.${NC}"
echo ""

_clone_error=""
if command -v dc3dd >/dev/null 2>&1; then
    echo -e "${GREY}Outil : dc3dd (copie bit-à-bit + hash SHA-256)${NC}"
    if sudo dc3dd if="$SOURCE_DEV" of="$TARGET_DEV" hash=sha256 2>&1; then
        echo ""
        echo -e "${GREEN}✅ Clonage terminé avec succès.${NC}"
    else
        _rc=$?
        echo ""
        echo -e "${RED}❌ Erreur lors du clonage (code $_rc).${NC}"
        ERRORS=$((ERRORS + 1))
        _clone_error="yes"
    fi
else
    echo -e "${GREY}Outil : dd (fallback, dc3dd absent)${NC}"
    if sudo dd if="$SOURCE_DEV" of="$TARGET_DEV" bs=1M status=progress 2>&1; then
        echo ""
        echo -e "${GREEN}✅ Clonage terminé avec succès.${NC}"
    else
        _rc=$?
        echo ""
        echo -e "${RED}❌ Erreur lors du clonage (code $_rc).${NC}"
        ERRORS=$((ERRORS + 1))
        _clone_error="yes"
    fi
fi

STOP_TS=$(date -R)

# Synchroniser les écritures
echo ""
echo -e "${YELLOW}Synchronisation des écritures...${NC}"
sync
sleep 2

# ============================================================================
# 4. REPARATION / EXTENSION (si espace non assigné restant sur la cible)
# ============================================================================
clear_banner
echo -e "${BLUE}Source : ${BOLD}$SOURCE_DEV${NC}  ${GREY}• ${BOLD}$(_fmt_human $SOURCE_BYTES)${NC}"
echo -e "${BLUE}Cible  : ${BOLD}$TARGET_DEV${NC}  ${GREY}• ${BOLD}$(_fmt_human $TARGET_BYTES)${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 4/4 : Réparation des partitions     ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Verifier s'il reste de l'espace non assigne sur la cible (cible > source)
if [ "$TARGET_BYTES" -gt "$SOURCE_BYTES" ] && [ -z "$_clone_error" ]; then
    _diff=$((TARGET_BYTES - SOURCE_BYTES))
    echo -e "${GREY}Espace non assigné restant sur la cible : ${BOLD}$(_fmt_human $_diff)${NC}${GREY}.${NC}"
    echo -e "${GREY}Le disque cible est plus grand que la source : le schéma de partitions${NC}"
    echo -e "${GREY}copié ne couvre pas tout le disque. On peut réparer/étendre la dernière${NC}"
    echo -e "${GREY}partition pour exploiter cet espace, ou corriger la table GPT/MBR.${NC}"
    echo ""
    echo -e "  ${BOLD}${BLUE}[1]${NC}  ${BOLD}Réparer la table de partitions (GPT/MBR)${NC}"
    echo -e "        ${GREY}Corrige les warnings de table et réaligne la fin du disque.${NC}"
    echo -e "  ${BOLD}${BLUE}[2]${NC}  ${BOLD}Réparer + étendre la dernière partition${NC}"
    echo -e "        ${GREY}Corrige la table puis étend la dernière partition sur l'espace libre.${NC}"
    echo -e "  ${BOLD}${BLUE}[3]${NC}  ${BOLD}Ne rien faire${NC}  ${GREY}(conserver l'espace non assigné)${NC}"
    echo ""
    echo -ne "${BOLD}${YELLOW}Choix (1-3) [3] : ${NC}"
    read -r REPAIR_CHOICE
    [ -z "$REPAIR_CHOICE" ] && REPAIR_CHOICE=3
    case "$REPAIR_CHOICE" in
        1)
            echo ""
            echo -e "${YELLOW}Réparation de la table de partitions sur $TARGET_DEV...${NC}"
            if command -v sgdisk >/dev/null 2>&1; then
                sudo sgdisk -e "$TARGET_DEV" 2>&1 && \
                    echo -e "${GREEN}✓ Table GPT corrigée (secondary GPT déplacé en fin de disque).${NC}" || \
                    echo -e "${YELLOW}⚠️  sgdisk -e a échoué. Tentez parted ou fdisk manuellement.${NC}"
            elif command -v parted >/dev/null 2>&1; then
                sudo parted -s "$TARGET_DEV" print 2>&1
                echo -e "${YELLOW}⚠️  sgdisk absent. Utilisez 'sudo parted -s ${TARGET_DEV} rescue' ou fdisk pour corriger la table.${NC}"
            else
                echo -e "${YELLOW}⚠️  sgdisk/parted absents. Installez gdisk ou parted pour réparer la table.${NC}"
            fi
            ;;
        2)
            echo ""
            echo -e "${YELLOW}Réparation de la table + extension de la dernière partition...${NC}"
            # 1. Reparer la table GPT/MBR
            if command -v sgdisk >/dev/null 2>&1; then
                sudo sgdisk -e "$TARGET_DEV" 2>&1 && \
                    echo -e "${GREEN}✓ Table corrigée via sgdisk -e.${NC}" || \
                    echo -e "${YELLOW}⚠️  sgdisk -e a échoué.${NC}"
            else
                echo -e "${YELLOW}⚠️  sgdisk absent, table non réparée automatiquement.${NC}"
            fi
            # 2. Identifier la derniere partition (numero le plus eleve)
            _lastpart=$(lsblk -ln -o NAME,TYPE "$TARGET_DEV" 2>/dev/null | awk '$2=="part"{print $1}' | tail -1)
            if [ -n "$_lastpart" ]; then
                _partnum=$(echo "$_lastpart" | sed -E 's/.*[a-z]([0-9]+)$/\1/')
                _partdev=""
                case "$TARGET_DEV" in
                    /dev/nvme*|/dev/mmcblk*) _partdev="${TARGET_DEV}p${_partnum}" ;;
                    *)                        _partdev="${TARGET_DEV}${_partnum}" ;;
                esac
                echo -e "${GREY}Dernière partition détectée : $_partdev (n° $_partnum)${NC}"
                # growpart (package cloud-guest-utils) si dispo
                if command -v growpart >/dev/null 2>&1; then
                    if sudo growpart "$TARGET_DEV" "$_partnum" 2>&1; then
                        echo -e "${GREEN}✓ Partition $_partnum étendue via growpart.${NC}"
                        # Redimensionner le FS si ext2/3/4
                        _fst=$(lsblk -no FSTYPE "$_partdev" 2>/dev/null | head -n1 | tr -d '[:space:]')
                        case "$_fst" in
                            ext2|ext3|ext4)
                                if command -v resize2fs >/dev/null 2>&1; then
                                    sudo e2fsck -fy "$_partdev" 2>&1 || true
                                    sudo resize2fs "$_partdev" 2>&1 && \
                                        echo -e "${GREEN}✓ Système de fichiers redimensionné (resize2fs).${NC}" || \
                                        echo -e "${YELLOW}⚠️  resize2fs a échoué sur $_partdev.${NC}"
                                else
                                    echo -e "${YELLOW}⚠️  resize2fs absent (installez e2fsprogs).${NC}"
                                fi
                                ;;
                            xfs)
                                # xfs se redimensionne apres montage
                                echo -e "${YELLOW}⚠️  FS xfs : montez la partition puis 'xfs_growfs'.${NC}"
                                ;;
                            "")
                                echo -e "${GREY}Aucun FS détecté sur $_partdev (partition brute).${NC}"
                                ;;
                            *)
                                echo -e "${GREY}FS $_fst : redimensionnement manuel requis.${NC}"
                                ;;
                        esac
                    else
                        echo -e "${YELLOW}⚠️  growpart a échoué sur $TARGET_DEV partition $_partnum.${NC}"
                    fi
                else
                    echo -e "${YELLOW}⚠️  growpart absent. Installez cloud-guest-utils ou étendez via parted/fdisk manuellement.${NC}"
                fi
            else
                echo -e "${YELLOW}⚠️  Aucune partition détectée sur $TARGET_DEV. Rien à étendre.${NC}"
            fi
            ;;
        3)
            echo -e "${GREY}Aucune réparation : l'espace non assigné est conservé.${NC}"
            ;;
        *)
            echo -e "${RED}❌ Choix invalide : $REPAIR_CHOICE. Aucune réparation effectuée.${NC}"
            ;;
    esac
else
    if [ -n "$_clone_error" ]; then
        echo -e "${YELLOW}⚠️  Clonage en erreur : réparation ignorée.${NC}"
    else
        echo -e "${GREY}Le disque cible a la même taille que la source : aucun espace non assigné.${NC}"
    fi
fi

# ============================================================================
# 5. LIBERATION + RESUME
# ============================================================================
echo ""
echo -e "${YELLOW}Déverrouillage du disque source...${NC}"
sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true

echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}❌ Clonage terminé avec $ERRORS erreur(s).${NC}"
    echo -e "${YELLOW}   Source : $SOURCE_DEV | Cible : $TARGET_DEV${NC}"
else
    echo -e "${GREEN}✅ Clonage terminé avec succès.${NC}"
    echo -e "${GREEN}   Source : ${BOLD}$SOURCE_DEV${NC} ${GREEN}-> Cible :${NC} ${BOLD}$TARGET_DEV${NC}"
    echo -e "${GREEN}   Début : $START_TS${NC}"
    echo -e "${GREEN}   Fin   : $STOP_TS${NC}"
    echo -e "${YELLOW}   Le disque cible peut être retiré.${NC}"
fi

final_pause
