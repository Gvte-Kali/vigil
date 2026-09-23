#!/bin/bash
set -uo pipefail

# --- Scan antivirus complet : montage -> scan ClamAV -> demontage ---
#
# Enchaine 3 etapes dans un seul terminal :
#   1. Montage d'un peripherique dans /investigation (interactif)
#   2. Scan antivirus ClamAV sur tous les dossiers montes (non-interactif)
#   3. Demontage de /investigation
#
# L'utilisateur choisit le peripherique a monter (etape 1), puis le scan
# s'execute automatiquement, puis le peripherique est demonte.
#
# Utilisateur : passe en argument (--user NOM) ou choisi interactivement
# parmi les utilisateurs configures ; le script ne demande jamais de saisir
# un nom libre.

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

print_options_table() {
    echo -e "${BOLD}  Récapitulatif${NC}"
    echo -e "${GREY}  ---------------------------------${NC}"
    echo -e "  Utilisateur : ${BOLD}${ACTIVE_USER}${NC}"
    echo -e "  Archives    : ${BOLD}contenu scanné${NC}"
    echo -e "  Taille max  : ${BOLD}$([ "$SIZE_MODE" = "limit" ] && echo "limitée (512 Mo max)" || echo "illimitée (2047 Mo max)")${NC}"
    echo -e "  Chiffrées   : ${BOLD}signalées${NC}"
    echo ""
}

# --- Utilisateur : passe en argument ou choisi interactivement ---
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
USERS_DIR="$VIGIL_BASE/data/users"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
SELECTED_USER=""
ACTIVE_USER=""

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MOUNT_SCRIPT="$SCRIPT_DIR/analyse/vigil_usb_mount.sh"
SCAN_SCRIPT="$SCRIPT_DIR/clamav/vigil_clamav_scan.sh"
UMOUNT_SCRIPT="$SCRIPT_DIR/analyse/vigil_usb_umount.sh"

ERRORS=0
# --- Parsing des arguments (transmis au scan ClamAV) ---
# --pdf/--no-pdf : activer/désactiver le rapport PDF consolidé
# --log/--no-log : conserver/ne pas conserver le fichier journal clamscan
# --user NOM     : utilisateur passe directement (pas de sélection interactive)
SCAN_ARGS=()
SIZE_SET=0
SIZE_MODE="unlimited"
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)    SCAN_ARGS+=(--pdf) ;;
        --no-pdf) SCAN_ARGS+=(--no-pdf) ;;
        --log)    SCAN_ARGS+=(--log) ;;
        --no-log) SCAN_ARGS+=(--no-log) ;;
        --user)
            shift
            SELECTED_USER="${1:-}"
            ;;
        --user=*)
            SELECTED_USER="${1#--user=}"
            ;;
        --archives)    SCAN_ARGS+=(--archives) ;;
        --no-archives) SCAN_ARGS+=(--no-archives) ;;
        --size-unlimited) SCAN_ARGS+=(--size-unlimited); SIZE_SET=1; SIZE_MODE="unlimited" ;;
        --size-limit)     SCAN_ARGS+=(--size-limit); SIZE_SET=1; SIZE_MODE="limit" ;;
        --alert-encrypted)    SCAN_ARGS+=(--alert-encrypted) ;;
        --no-alert-encrypted) SCAN_ARGS+=(--no-alert-encrypted) ;;
    esac
    shift
done

# --- Options transmises au scan ClamAV ---
# Archives (contenu scanné, --scan-archive=yes explicite), alerte sur les
# archives chiffrées et taille illimitée (plafond réel ClamAV : 2047M)
# sont FORCÉS par défaut, sans question interactive. Les flags
# --no-archives / --no-alert-encrypted / --size-limit restent des overrides
# CLI, propagés via SCAN_ARGS au scan ClamAV.
clear
print_banner

echo -e "${BLUE}=== Utilisateur ===${NC}"
echo ""

# --- Sélection de l'utilisateur ---
# Si un utilisateur a été passé en argument (--user), l'utiliser tel quel.
# Sinon, lister les utilisateurs configurés ($VIGIL_BASE/data/users) et
# laisser l'opérateur en choisir un par numéro. Le script ne demande jamais
# de saisir un nom libre : seuls les utilisateurs configurés sont acceptés.
if [ -n "$SELECTED_USER" ]; then
    ACTIVE_USER="$SELECTED_USER"
    echo -e "${GREY}--user : utilisateur fourni en argument.${NC}"
    echo -e "  ${BOLD}${ACTIVE_USER}${NC}"
else
    # Lister les utilisateurs configurés (un dossier par utilisateur, avec
    # un fichier profile.json, comme dans la page Configuration de la GUI).
    USERS_LIST=()
    if [ -d "$USERS_DIR" ]; then
        while IFS= read -r -d '' udir; do
            [ -f "$udir/profile.json" ] && USERS_LIST+=("$(basename "$udir")")
        done < <(find "$USERS_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null | sort -z)
    fi

    if [ "${#USERS_LIST[@]}" -eq 0 ]; then
        echo -e "${RED}❌ Aucun utilisateur configuré.${NC}"
        echo "Créez un utilisateur via la page Configuration de la GUI"
        echo "(Configuration du système → Utilisateurs)."
        echo ""
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    fi

    # Environnement non interactif (stdin fermé) : utiliser l'utilisateur
    # actif s'il existe, sinon prendre le premier utilisateur configuré.
    if ! [ -t 0 ]; then
        if [ -f "$ACTIVE_USER_FILE" ]; then
            ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
        fi
        if [ -z "$ACTIVE_USER" ] || ! printf '%s\n' "${USERS_LIST[@]}" | grep -qx "$ACTIVE_USER"; then
            ACTIVE_USER="${USERS_LIST[0]}"
        fi
        echo -e "${GREY}Mode non interactif : utilisateur « ${ACTIVE_USER} » sélectionné automatiquement.${NC}"
    else
        echo -e "${GREY}Sélectionnez l'utilisateur qui effectue le scan :${NC}"
        echo ""
        for idx in "${!USERS_LIST[@]}"; do
            echo -e "  ${BOLD}${BLUE}[$((idx+1))]${NC}  ${BOLD}${USERS_LIST[$idx]}${NC}"
        done
        echo -e "  ${BOLD}${BLUE}[q]${NC}  ${BOLD}Quitter${NC}"
        echo ""
        while true; do
            echo -ne "${BOLD}${YELLOW}Entrez le numéro de l'utilisateur (ou 'q' pour quitter) : ${NC}"
            read -r CHOICE
            [ -z "$CHOICE" ] && continue
            if [ "$CHOICE" = "q" ]; then
                echo -e "${YELLOW}Annulé.${NC}"
                exit 0
            fi
            if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt "${#USERS_LIST[@]}" ]; then
                echo -e "${RED}❌ Numéro invalide : $CHOICE${NC}"
                continue
            fi
            ACTIVE_USER="${USERS_LIST[$((CHOICE-1))]}"
            break
        done
    fi
fi

echo ""

# --- Plus aucune question après le choix de l'utilisateur ---
# Le scan du contenu des archives, le signalement des archives chiffrées et
# le mode de taille (illimité, plafond 2047M) sont FORCÉS par défaut.
# Les flags --no-archives / --no-alert-encrypted / --size-limit restent
# disponibles en override CLI et sont propagés via SCAN_ARGS au scan.

clear
print_banner
echo -e "${BOLD}Scan antivirus complet — Étape 1/3 : Montage du périphérique${NC}"
echo ""
print_options_table

if [ ! -f "$MOUNT_SCRIPT" ]; then
    echo -e "${RED}❌ Script de montage introuvable : $MOUNT_SCRIPT${NC}"
    ERRORS=$((ERRORS + 1))
    echo ""
    echo -e "${RED}❌ Scan terminé avec $ERRORS erreur(s).${NC}"
    echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
    read -r
    exit 1
fi

bash "$MOUNT_SCRIPT"
_mount_rc=$?
if [ "$_mount_rc" -ne 0 ]; then
    echo -e "${RED}❌ Échec du montage (code $_mount_rc). Abandon du scan.${NC}"
    ERRORS=$((ERRORS + 1))
    echo ""
    echo -e "${RED}❌ Scan terminé avec $ERRORS erreur(s).${NC}"
    echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
    read -r
    exit 1
fi

# Verifier qu'au moins un peripherique est monte dans /investigation
_mounted=0
while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        _mounted=1
        break
    fi
done < <(find /investigation -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [ "$_mounted" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun périphérique monté dans /investigation. Scan antivirus ignoré.${NC}"
    ERRORS=$((ERRORS + 1))
    echo ""
    echo -e "${RED}❌ Scan terminé avec $ERRORS erreur(s).${NC}"
    echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
    read -r
    exit 1
fi

# --- Etape 2 : Scan antivirus ---
clear
print_banner
echo -e "${BOLD}Scan antivirus complet — Étape 2/3 : Scan antivirus ClamAV${NC}"
echo ""
print_options_table

if [ ! -f "$SCAN_SCRIPT" ]; then
    echo -e "${RED}❌ Script de scan introuvable : $SCAN_SCRIPT${NC}"
    ERRORS=$((ERRORS + 1))
else
    # Mode non-interactif : tous les dossiers, confirmation auto, commentaire vide.
    # L'utilisateur sélectionné est propagé au scan pour le rapport PDF.
    bash "$SCAN_SCRIPT" "${SCAN_ARGS[@]}" --all --yes --comment "" --user "$ACTIVE_USER"
    _scan_rc=$?
    if [ "$_scan_rc" -ne 0 ]; then
        echo -e "${RED}❌ Le scan antivirus a signalé une erreur (code $_scan_rc).${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

# --- Etape 3 : Demontage ---
clear
print_banner
echo -e "${BOLD}Scan antivirus complet — Étape 3/3 : Démontage du périphérique${NC}"
echo ""
print_options_table

if [ ! -f "$UMOUNT_SCRIPT" ]; then
    echo -e "${RED}❌ Script de démontage introuvable : $UMOUNT_SCRIPT${NC}"
    ERRORS=$((ERRORS + 1))
else
    bash "$UMOUNT_SCRIPT"
    _umount_rc=$?
    if [ "$_umount_rc" -ne 0 ]; then
        echo -e "${RED}❌ Le démontage a signalé une erreur (code $_umount_rc).${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

# --- Resume final ---
echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}❌ Scan antivirus complet terminé avec $ERRORS erreur(s).${NC}"
else
    echo -e "${GREEN}✅ Scan antivirus complet terminé avec succès.${NC}"
fi
echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
read -r
if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi
exit 0
