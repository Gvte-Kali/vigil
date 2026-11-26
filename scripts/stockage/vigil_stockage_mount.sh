#!/bin/bash
set -uo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# --- Montage d'un peripherique de stockage dans /stockage (lecture/ecriture) ---
#
# Ce script monte un peripherique USB/Disque selectionne dans /stockage. Comme
# vigil_usb_mount.sh, il detecte les disques et leurs partitions et permet de
# monter un disque entier (toutes ses partitions) sous /stockage/<disk>/<part>.
# Il est destine au STOCKAGE de fichiers de travail, PAS a l'analyse forensique
# (montage en lecture/ecriture). Pour analyser un peripherique, utilisez plutot
# le menu "Analyse USB / Disque Dur / CD" (vigil_usb_mount.sh) qui monte en RO.

. "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-terminal.sh"
. "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-device-triage.sh"
. "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-device-ops.sh"
. "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-storage-root.sh"
vigil_device_begin

print_banner() {
    vigil_logo
}

ERRORS=0

# --- Contexte actif (utilisateur + projet) : non bloquant pour le stockage ---
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
CONFIG_FILE="$VIGIL_DATA_DIR/config/system.json"

STOCKAGE_DIR="/stockage"

ACTIVE_USER="(no-user)"
[ -f "$ACTIVE_USER_FILE" ] && ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
[ -z "$ACTIVE_USER" ] && ACTIVE_USER="(no-user)"

ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    ACTIVE_PROJECT="(no-project)"
fi

ACTIVE_ENTITY="(non configuree)"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
    [ -z "$ACTIVE_ENTITY" ] && ACTIVE_ENTITY="(non configuree)"
fi

if [ "${VIGIL_QT_STORAGE:-}" = "1" ]; then
    ACTIVE_USER="${VIGIL_ACTIVE_USER:?opérateur Vigil requis}"
    ACTIVE_PROJECT="${VIGIL_LEGACY_PROJECT:?contexte Vigil requis}"
    LOG_WRITER=(tee)
else
    LOG_WRITER=(sudo tee)
fi

if [ "${VIGIL_QT_STORAGE:-}" = "1" ]; then
    PROJECT_LOG_DIR="${VIGIL_LEGACY_CASE_DIR:?dossier de journal Vigil requis}"
elif [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    PROJECT_LOG_DIR="/tmp"
else
    PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
fi

final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        [ "${VIGIL_QT_STORAGE:-}" = "1" ] && exit 1
        echo -e "${RED}❌ Script terminé avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}$(vigil_text "Appuyez sur Entrée pour fermer ce terminal..." "Press Enter to close this terminal...")${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Script terminé sans erreur.${NC}"
    fi
}

fail() {
    echo -e "${RED}❌ $1${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

log_action() {
    local action="$1"
    local device="$2"
    local file_path="$3"
    local status="$4"
    local message="$5"

    [ "$ACTIVE_USER" = "(no-user)" ] && return
    [ "${VIGIL_QT_STORAGE:-}" != "1" ] && [ "$ACTIVE_PROJECT" = "(no-project)" ] && return
    local timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Device:$device | File:$file_path | Status:$status | Message:$message"

    echo "$log_entry" | "${LOG_WRITER[@]}" -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true

    if command -v jq >/dev/null 2>&1; then
        jq -n \
            --arg timestamp "$timestamp" \
            --arg user "$ACTIVE_USER" \
            --arg entity "$ACTIVE_ENTITY" \
            --arg project "$ACTIVE_PROJECT" \
            --arg action "$action" \
            --arg device "$device" \
            --arg file_path "$file_path" \
            --arg status "$status" \
            --arg message "$message" \
            '{timestamp: $timestamp, user: $user, entity: $entity, project: $project, action: $action, device: $device, file_path: $file_path, status: $status, message: $message}' \
        | "${LOG_WRITER[@]}" -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
    fi
}

mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || true

# --- Lister les points de montage réels sous /stockage (récursif) ---
# Les montages multi-partitions sont imbriqués (/stockage/<disk>/<part>).
# /proc/mounts est la source de vérité du noyau ; fallback lsblk (lit /sys).
list_mounts_under_stockage() {
    vigil_mounts_in_zone /stockage
}

# --- Verifications des privileges et dependances ---
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Ce script nécessite des privilèges root pour monter les périphériques.${NC}"
    echo -e "${YELLOW}    Vérifiez la configuration sudo de l'utilisateur courant.${NC}"
fi

echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING_DEPS=0
for cmd in lsblk mount find; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING_DEPS=$((MISSING_DEPS + 1))
    fi
done
# Outils optionnels (avertissement seulement)
for cmd in jq cryptsetup blockdev; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Outil optionnel absent : $cmd (certaines fonctionnalités seront désactivées)${NC}"
    fi
done
if [ "$MISSING_DEPS" -gt 0 ]; then
    fail "Dépendances obligatoires manquantes ($MISSING_DEPS)."
fi

# --- Sélection de l'utilisateur (la custody en dépend) ---
# L'utilisateur est choisi parmi les profils de la GUI (data/users/).
# 'q' quitte proprement le script à tout moment.
select_active_user() {
    local USERS_DIR="$VIGIL_BASE/data/users"
    local choices=() name profile rank answer
    if [ -d "$USERS_DIR" ]; then
        for profile in "$USERS_DIR"/*/profile.json; do
            [ -f "$profile" ] || continue
            name="${profile#"$USERS_DIR"/}"
            name="${name%/profile.json}"
            [ -n "$name" ] && choices+=("$name")
        done
    fi
    if [ "${#choices[@]}" -eq 0 ]; then
        echo -e "${RED}❌ Aucun utilisateur configuré.${NC}"
        echo -e "${GREY}Créez-le dans la GUI : Accueil > Configuration > Utilisateurs.${NC}"
        final_pause
        exit 1
    fi
    clear
    print_banner
    echo -e "${BLUE}=== Utilisateur ===${NC}"
    echo ""
    echo -e "Sélectionnez l'utilisateur qui effectue le montage :"
    echo ""
    rank=1
    for name in "${choices[@]}"; do
        echo -e "  ${BOLD}${BLUE}[$rank]${NC}  $name"
        rank=$((rank + 1))
    done
    echo ""
    echo -e "  ${BOLD}${BLUE}[q]${NC}  Quitter"
    echo ""
    while true; do
        echo -ne "${BOLD}${YELLOW}Entrez le numéro de l'utilisateur (ou 'q' pour quitter) : ${NC}"
        read -r answer
        if [ "$answer" = "q" ] || [ "$answer" = "Q" ]; then
            echo -e "${YELLOW}Quitter.${NC}"
            final_pause
            exit 0
        fi
        if [[ "$answer" =~ ^[0-9]+$ ]] && [ "$answer" -ge 1 ] && [ "$answer" -le "${#choices[@]}" ]; then
            ACTIVE_USER="${choices[$((answer - 1))]}"
            break
        fi
        echo -e "${RED}✗ $(vigil_text "Choix invalide." "Invalid choice.")${NC}"
    done
    printf '%s' "$ACTIVE_USER" > "$ACTIVE_USER_FILE" 2>/dev/null || true
}

[ "${VIGIL_QT_STORAGE:-}" = "1" ] || select_active_user

# --- Nettoyer l'ecran ---
clear
print_banner
if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    echo -e "${BLUE}$(vigil_text "Projet :" "Project:") $(vigil_text "(aucun)" "(none)")${NC}"
else
    echo -e "${BLUE}$(vigil_text "Projet :" "Project:") ${ACTIVE_PROJECT}${NC}"
fi
echo -e "${BLUE}$(vigil_text "Entité :" "Entity:") ${ACTIVE_ENTITY} | $(vigil_text "Utilisateur :" "Operator:") ${ACTIVE_USER}${NC}"
echo ""
echo -e "${YELLOW}⚠️  ATTENTION : montage en lecture/écriture.${NC}"
echo ""

# Refuse an occupied storage zone instead of implicitly unmounting it.
existing_mounts=$(list_mounts_under_stockage) || fail "État de /stockage non vérifiable."
[ -z "$existing_mounts" ] || fail "Un montage existe sous /stockage. Démontez le support d’abord."
if [ ! -e "$STOCKAGE_DIR" ] && [ ! -L "$STOCKAGE_DIR" ]; then
    sudo install -d -o root -g root -m 0755 -- "$STOCKAGE_DIR" || fail "Impossible de créer $STOCKAGE_DIR."
fi
if ! storage_error=$(vigil_storage_root_check "$STOCKAGE_DIR"); then
    printf '%s\n' "$storage_error"
    fail "$(vigil_text "Depuis un terminal, exécutez : sh $VIGIL_BASE/scripts/post-install/prepare-storage.sh"                        "From a terminal, run: sh $VIGIL_BASE/scripts/post-install/prepare-storage.sh")"
fi

# --- 0.4. Triage USB anti-Rubber Ducky (baseline + blocage HID par défaut) ---
# Même procédure que vigil_usb_mount.sh : détection des claviers HID apparus
# au branchement, blocage par défaut des frappes, whitelist/blacklist USB
# persistantes (data/usb) et rapport PDF de triage. Un stockage de travail ne
# se présente jamais en clavier : tout périphérique HID non whitelisté apparu
# après la baseline est bloqué.
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
USB_LISTS_DIR="$VIGIL_DATA_DIR/usb"
USB_WHITELIST_FILE="$USB_LISTS_DIR/whitelist.txt"
USB_BLACKLIST_FILE="$USB_LISTS_DIR/blacklist.txt"
mkdir -p "$USB_LISTS_DIR" 2>/dev/null || true
touch "$USB_WHITELIST_FILE" "$USB_BLACKLIST_FILE" 2>/dev/null || true

TRIAGE_DIR=$(mktemp -d -t "vigil_triage_stockage_XXXXXXXX") || exit 1
trap 'rm -rf -- "$TRIAGE_DIR"' EXIT
HID_BLOCKED_PORTS=()
HID_LISTING=()
HID_ALERT_COUNT=0
if [ -z "${VIGIL_DEVICE_SELECTION:-}" ]; then
    run_usb_triage "$(vigil_text "Destination" "Destination")" || exit 0
fi

# --- Helper : détection chiffrement LUKS/BitLocker ---
_is_encrypted() {
    local dev="$1"
    if command -v cryptsetup >/dev/null 2>&1 && cryptsetup isLuks "$dev" 2>/dev/null; then
        echo "LUKS"
        return 0
    fi
    local sig sig_b64
    local bitlocker_signatures=("61iQLUZWRS1GUy0=" "61KQLUZWRS1GUy0=" "61iQTVNXSU40LjE=")
    sig_b64=$(dd if="$dev" bs=11 count=1 status=none 2>/dev/null | base64 || true)
    for sig in "${bitlocker_signatures[@]}"; do
        if [ "$sig_b64" = "$sig" ]; then
            echo "BitLocker"
            return 0
        fi
    done
    echo ""
    return 1
}

# --- Helper : montage RW d'un device dans un point de montage ---
_mount_single_rw() {
    local dev="$1" mnt="$2"
    local fstype mount_opts mount_status
    if [ "${VIGIL_QT_STORAGE:-}" = "1" ]; then
        [ ! -e "$mnt" ] && [ ! -L "$mnt" ] || return 1
        [ "$(realpath -m -- "$mnt")" = "$mnt" ] || return 1
    fi
    sudo mkdir -p "$mnt" 2>/dev/null || {
        echo -e "${RED}❌ Impossible de créer le point de montage $mnt.${NC}"
        log_action "mkdir_mountpoint_stockage" "$dev" "$mnt" "failed" "Échec de la création du répertoire"
        return 1
    }
    # S'assurer que le block device n'est pas resté en lecture seule après un
    # montage forensique (vigil_usb_mount.sh fait blockdev --setro).
    if command -v blockdev >/dev/null 2>&1; then
        sudo blockdev --setrw "$dev" 2>/dev/null || true
    fi
    fstype=$(lsblk -no FSTYPE "$dev" 2>/dev/null || echo "")
    mount_opts="-o rw,nosuid,nodev"
    case "$fstype" in
        fat32|vfat) mount_opts="$mount_opts,utf8=true,flush,uid=$(id -u),gid=$(id -g)" ;;
        ext3|ext4)  mount_opts="$mount_opts" ;;
        ntfs|ntfs-3g)
            if command -v ntfs-3g >/dev/null 2>&1; then
                mount_opts="-t ntfs-3g -o rw,big_writes,nosuid,nodev,uid=$(id -u),gid=$(id -g)"
            else
                echo -e "${RED}❌ ntfs-3g absent : impossible d'écrire sur du NTFS.${NC}"
                return 1
            fi
            ;;
        exfat)
            mount_opts="$mount_opts,uid=$(id -u),gid=$(id -g)"
            if command -v mount.exfat >/dev/null 2>&1; then
                mount_opts="-t exfat -o rw,nosuid,nodev,uid=$(id -u),gid=$(id -g)"
            fi
            ;;
    esac
    if [ "${VIGIL_QT_STORAGE:-}" = "1" ]; then
        mount_opts="$mount_opts,noexec"
    fi
    mount_status=0
    vigil_mount_volume /stockage "$dev" "$mnt" $mount_opts || mount_status=$?
    if [ "$mount_status" -ne 0 ]; then
        echo -e "${RED}❌ Échec du montage de $dev → $mnt${NC}"
        log_action "mount_stockage" "$dev" "$mnt" "failed" "Échec du montage"
        sudo rmdir "$mnt" 2>/dev/null || true
        return 1
    fi
    if [ "${VIGIL_QT_STORAGE:-}" = "1" ]; then
        if ! findmnt -n -o VFS-OPTIONS --mountpoint "$mnt" | grep -Eq '(^|,)rw(,|$)'; then
            sudo umount "$mnt" || true
            echo "Montage en lecture-écriture non confirmé : $mnt"
            return 1
        fi
        case "$fstype" in
            ext2|ext3|ext4)
                if ! sudo chown "$(id -u):$(id -g)" "$mnt"; then
                    sudo umount "$mnt" || true
                    return 1
                fi
                ;;
        esac
    else
        sudo chown -R "$USER:$USER" "$mnt" 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ ${NC}${BOLD}$dev${NC}${GREEN} → $mnt${NC}"
    log_action "mount_stockage" "$dev" "$mnt" "success" "Périphérique monté en lecture/écriture"
    return 0
}

# --- 1. Detection des peripheriques USB/Disques ---
detect_usb_devices || fail "Impossible de relever les périphériques de stockage."
if [ -n "${VIGIL_DEVICE_SELECTION:-}" ]; then
    select_device_path "$VIGIL_DEVICE_SELECTION" || fail "Périphérique sélectionné indisponible."
else
    while true; do
        display_usb_devices
        select_usb_device "à monter" && break
        case $? in
            2) detect_usb_devices || fail "Impossible de relever les périphériques de stockage." ;;
            *) exit 0 ;;
        esac
    done
fi
IFS='|' read -r SELECTED_KIND SELECTED_DEVICE SELECTED_SIZE SELECTED_MODEL SELECTED_FSTYPE SELECTED_LABEL SELECTED_PARTTYPE SELECTED_PKNAME <<< "${USB_DEVICES[$SELECTED_INDEX]}"
VIGIL_DEVICE_IDENTITY=$(vigil_device_check capture /stockage "/dev/$SELECTED_DEVICE") || exit 1
export VIGIL_DEVICE_IDENTITY

echo "Montage en lecture-écriture de /dev/$SELECTED_DEVICE."
echo "$(vigil_text "Saisissez OUI (ou YES) si ce périphérique est bien un support de travail." "Type YES (or OUI) if this is a confirmed work drive.")"
if [ "${VIGIL_DEVICE_NONINTERACTIVE:-}" != 1 ]; then
    read -r confirmation || exit 0
    case "$confirmation" in OUI|YES) ;; *) exit 0 ;; esac
fi

selected="/dev/$SELECTED_DEVICE"
disk="$selected"
if [ "$SELECTED_KIND" = "part" ]; then
    parent=$(lsblk -dnro PKNAME -- "$selected") || fail "Disque parent inaccessible."
    [ -n "$parent" ] && [ "$parent" = "$SELECTED_PKNAME" ] ||
        fail "Impossible de confirmer le disque parent de $selected."
    disk="/dev/$parent"
fi
disk_info=$(lsblk -dnro TYPE,TRAN,RM -- "$disk") || fail "Disque inaccessible : $disk."
[[ "$disk_info" =~ ^disk[[:space:]]+usb[[:space:]]+[01]$ ]] ||
    fail "$disk n’est pas un disque USB confirmé."
mounts=$(lsblk -nr -o MOUNTPOINTS -- "$disk") || fail "Montages non vérifiables pour $disk."
[[ "$mounts" =~ [^[:space:]] ]] && fail "$disk contient déjà un montage. Aucun passage en écriture."
vigil_device_check mount /stockage "$selected" || exit 1
disk_ro=$(sudo blockdev --getro "$disk") || fail "État bloc non vérifiable pour $disk."
case "$disk_ro" in
    0) ;;
    1) sudo blockdev --setrw "$disk" || fail "Impossible de rendre $disk inscriptible." ;;
    *) fail "État bloc inconnu pour $disk." ;;
esac

# --- 4. Montage selon le kind d'entrée sélectionnée ---
echo -e "\n${YELLOW}$(vigil_text "Montage en lecture/écriture..." "Mounting read/write...")${NC}"
if [ "$SELECTED_KIND" = "whole" ]; then
    # Monter toutes les partitions du disque sous /stockage/<disk>/<part>
    echo -e "${YELLOW}Montage de toutes les partitions de /dev/$SELECTED_DEVICE...${NC}"
    if command -v blockdev >/dev/null 2>&1; then
        sudo blockdev --setrw "/dev/$SELECTED_DEVICE" 2>/dev/null || true
    fi
    _ok=0; _fail=0
    _parts="${DISK_PARTS["$SELECTED_DEVICE"]:-}"
    for _part in $_parts; do
        _dev="/dev/$_part"; _mnt="/stockage/$SELECTED_DEVICE/$_part"
        _enc=$(_is_encrypted "$_dev")
        if [ -n "$_enc" ]; then
            echo -e "${RED}❌ $_dev est chiffré ($_enc). Ignoré.${NC}"
            log_action "mount_attempt_stockage" "$_dev" "$_mnt" "failed" "Partition chiffrée ($_enc)"
            _fail=$((_fail + 1))
            continue
        fi
        if _mount_single_rw "$_dev" "$_mnt"; then
            _ok=$((_ok + 1))
        else
            _fail=$((_fail + 1))
        fi
    done
    echo ""
    echo -e "${GREEN}✅ $_ok partition(s) montée(s), $_fail échec(s) sous /stockage/$SELECTED_DEVICE/${NC}"
    [ "${VIGIL_QT_STORAGE:-}" = "1" ] && [ "$_fail" -gt 0 ] && ERRORS=$((_fail + ERRORS))
    log_action "mount_whole_stockage" "/dev/$SELECTED_DEVICE" "/stockage/$SELECTED_DEVICE" "success" "$_ok partition(s) montée(s), $_fail échec(s)"
else
    # Montage d'un device unique (partition ou disque sans table)
    DEVICE_PATH="/dev/$SELECTED_DEVICE"
    _enc=$(_is_encrypted "$DEVICE_PATH")
    if [ -n "$_enc" ]; then
        echo -e "${RED}❌ Ce périphérique est chiffré ($_enc).${NC}"
        echo -e "${YELLOW}Utilisez un outil de déchiffrement avant de continuer.${NC}"
        log_action "mount_attempt_stockage" "$DEVICE_PATH" "/stockage" "failed" "Périphérique chiffré ($_enc)"
        final_pause
        exit 1
    fi
    MOUNT_POINT="/stockage/$SELECTED_DEVICE"
    echo -e "${YELLOW}Montage de ${GREEN}$DEVICE_PATH${YELLOW} dans $MOUNT_POINT...${NC}"
    if ! _mount_single_rw "$DEVICE_PATH" "$MOUNT_POINT"; then
        final_pause
        exit 1
    fi
fi

# Vérifier que le montage est bien en lecture/écriture
if command -v lsblk >/dev/null 2>&1; then
    if [ "$SELECTED_KIND" = "whole" ]; then
        _check_dev="/dev/$SELECTED_DEVICE"
    else
        _check_dev="/dev/$SELECTED_DEVICE"
    fi
    RO_CHECK=$(lsblk -no RO "$_check_dev" 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "")
    if [ "$RO_CHECK" = "1" ]; then
        echo -e "${RED}❌ Le périphérique est monté en lecture seule (RO=1).${NC}"
        echo -e "${YELLOW}    Causes possibles : périphérique physique protégé en écriture${NC}"
        echo -e "${YELLOW}    (interrupteur sur la clé), ou blockdev --setro d'un scan précédent.${NC}"
        log_action "mount_stockage_ro_warn" "$_check_dev" "$STOCKAGE_DIR" "warning" "Montage en lecture seule malgré options rw"
    else
        echo -e "${GREEN}✅ Montage confirmé en lecture/écriture.${NC}"
    fi
fi

final_pause
exit 0
