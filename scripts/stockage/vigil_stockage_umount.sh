#!/bin/bash
set -uo pipefail

# --- Demontage des peripheriques de stockage montes dans /stockage ---

# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
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

# --- Verifier qu'un utilisateur actif est selectionne ---
# --- Contexte actif (utilisateur + projet) : non bloquant pour le démontage ---
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="$VIGIL_BASE/data/config/system.json"

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

if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    PROJECT_LOG_DIR="/tmp"
else
    PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
fi

mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || true

log_action() {
    local action="$1"
    local device="$2"
    local file_path="$3"
    local status="$4"
    local message="$5"

    [ "$ACTIVE_PROJECT" = "(no-project)" ] && return
    local timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Device:$device | File:$file_path | Status:$status | Message:$message"

    echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true

    if command -v jq >/dev/null 2>&1; then
        local json_entry
        json_entry=$(jq -n \
            --arg timestamp "$timestamp" \
            --arg user "$ACTIVE_USER" \
            --arg entity "$ACTIVE_ENTITY" \
            --arg project "$ACTIVE_PROJECT" \
            --arg action "$action" \
            --arg device "$device" \
            --arg file_path "$file_path" \
            --arg status "$status" \
            --arg message "$message" \
            '{timestamp: $timestamp, user: $user, entity: $entity, project: $project, action: $action, device: $device, file_path: $file_path, status: $status, message: $message}' 2>/dev/null) || true
        [ -n "$json_entry" ] && echo "$json_entry" | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
    fi
}


# --- Lister les points de montage reels sous /stockage (recursif) ---
# Les montages multi-partitions sont imbriques (/stockage/<disk>/<part>).
# /proc/mounts est la source de verite du noyau ; fallback lsblk (lit /sys).
# Tri du plus profond au moins profond (demontage enfants avant parents).
list_mounts_under_stockage() {
    local mounts
    mounts="$(awk '$2 ~ "^/stockage/" {print $2}' /proc/mounts 2>/dev/null)"
    if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
        mounts="$(lsblk -J -o MOUNTPOINTS 2>/dev/null \
            | grep -oE '"/stockage/[^"]*"' | tr -d '"')"
    fi
    printf '%s\n' "$mounts" \
        | awk -v base="/stockage/" 'index($0, base) == 1' \
        | awk '{ print length($0), $0 }' | sort -rn | cut -d' ' -f2-
}


final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}\u274c Script termine avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entree pour fermer ce terminal...${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}\u2705 Script termine sans erreur.${NC}"
    fi
}

# --- Nettoyer l'ecran ---
clear
print_banner
if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    echo -e "${BLUE}Projet : (aucun)${NC}"
else
    echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
fi
echo -e "${BLUE}Entite : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo ""

# S'assurer que /stockage existe
sudo mkdir -p "$STOCKAGE_DIR" 2>/dev/null || true

# --- 1. Lister tous les points de montage sous /stockage ---
echo -e "${BLUE}=== Recherche des peripheriques montes dans $STOCKAGE_DIR ===${NC}"

MOUNT_POINTS=()
while IFS= read -r dir; do
    [ -n "$dir" ] && MOUNT_POINTS+=("$dir")
done < <(list_mounts_under_stockage)

if [ ${#MOUNT_POINTS[@]} -eq 0 ]; then
    echo -e "${YELLOW}\u2139\ufe0f  Aucun peripherique monte dans $STOCKAGE_DIR.${NC}"
    log_action "umount_attempt_stockage" "" "$STOCKAGE_DIR" "info" "Aucun peripherique monte"

    # Nettoyage des dossiers vides residuels
    CLEANED=0
    while IFS= read -r -d '' dir; do
        if [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
            sudo rmdir "$dir" 2>/dev/null && {
                echo -e "${GREEN}\ud83e\uddf9 Dossier vide supprime : $dir${NC}"
                CLEANED=$((CLEANED + 1))
            }
        fi
    done < <(find "$STOCKAGE_DIR" -mindepth 1 -depth -type d -print0 2>/dev/null)
    [ "$CLEANED" -gt 0 ] && log_action "cleanup_stockage" "" "$STOCKAGE_DIR" "success" "$CLEANED dossiers vides supprimes"

    # Rien n'est monté : le contexte actif est incohérent -> nettoyage.
    rm -f "$ACTIVE_USER_FILE" "$ACTIVE_PROJECT_FILE" 2>/dev/null || true
    log_action "clear_active" "" "$STOCKAGE_DIR" "success" "Contexte actif efface (rien monte)"
    final_pause
    exit 0
fi

echo -e "${GREEN}Peripheriques montes detectes :${NC}"
for mount_point in "${MOUNT_POINTS[@]}"; do
    echo -e "${BLUE}  - ${mount_point}${NC}"
done

# --- 2. Demontage de chaque peripherique ---
for MOUNT_POINT in "${MOUNT_POINTS[@]}"; do
    echo ""
    echo -e "${BLUE}--- Traitement de $MOUNT_POINT ---${NC}"

    DEVICE=$(mount | grep " ${MOUNT_POINT} " | awk '{print $1}' | head -n 1 || true)

    if [ -z "$DEVICE" ]; then
        echo -e "${YELLOW}\u26a0\ufe0f  Impossible de determiner le peripherique monte sur $MOUNT_POINT.${NC}"
        log_action "umount_attempt_stockage" "" "$MOUNT_POINT" "warning" "Peripherique monte introuvable"
    fi

    echo -e "${YELLOW}Demontage de $MOUNT_POINT...${NC}"
    UMOUNT_OK=0

    if sudo umount "$MOUNT_POINT" 2>/dev/null; then
        UMOUNT_OK=1
    else
        echo -e "${YELLOW}\u26a0\ufe0f  Demontage normal echoue (peripherique occupe ?). Synchronisation...${NC}"
        sync 2>/dev/null || true
        if sudo umount "$MOUNT_POINT" 2>/dev/null; then
            UMOUNT_OK=1
        else
            echo -e "${YELLOW}\u26a0\ufe0f  Toujours occupe. Demontage force (lazy umount)...${NC}"
            if sudo umount -l "$MOUNT_POINT" 2>/dev/null; then
                echo -e "${YELLOW}\u26a0\ufe0f  Demontage lazy applique.${NC}"
                log_action "umount_lazy_stockage" "$DEVICE" "$MOUNT_POINT" "warning" "Demontage force (lazy)"
                UMOUNT_OK=1
            else
                echo -e "${RED}\u274c Echec du demontage de $MOUNT_POINT.${NC}"
                log_action "umount_stockage" "$DEVICE" "$MOUNT_POINT" "failed" "Echec du demontage"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    fi

    if [ "$UMOUNT_OK" -eq 1 ]; then
        echo -e "${GREEN}\u2705 Peripherique $DEVICE demonte avec succes.${NC}"
        log_action "umount_stockage" "$DEVICE" "$MOUNT_POINT" "success" "Peripherique demonte"

        # Rebloquer le peripherique en lecture seule au niveau block device
        # apres usage en stockage, par securite (empeche une reecriture
        # accidentelle avant debranchement ou avant un montage forensique).
        if [ -n "$DEVICE" ] && [ -b "$DEVICE" ] && command -v blockdev >/dev/null 2>&1; then
            if sudo blockdev --setro "$DEVICE" 2>/dev/null; then
                echo -e "${GREEN}\u2705 Block device $DEVICE rebloque en lecture seule (securite).${NC}"
                log_action "set_ro_stockage" "$DEVICE" "" "success" "Block device rebloque en RO apres demontage"
            else
                echo -e "${YELLOW}\u26a0\ufe0f  blockdev --setro a echoue sur $DEVICE.${NC}"
                log_action "set_ro_stockage" "$DEVICE" "" "warning" "blockdev --setro a echoue apres demontage"
            fi
        fi
    fi

    sleep 1
    if [ -d "$MOUNT_POINT" ]; then
        if [ -z "$(ls -A "$MOUNT_POINT" 2>/dev/null)" ]; then
            sudo rmdir "$MOUNT_POINT" 2>/dev/null && {
                echo -e "${GREEN}\ud83e\uddf9 Dossier de montage supprime : $MOUNT_POINT${NC}"
                log_action "cleanup_stockage" "$DEVICE" "$MOUNT_POINT" "success" "Repertoire de montage supprime"
            } || {
                echo -e "${YELLOW}\u26a0\ufe0f  Impossible de supprimer $MOUNT_POINT (toujours occupe ?).${NC}"
                log_action "cleanup_stockage" "$DEVICE" "$MOUNT_POINT" "warning" "Repertoire non supprime (occupe)"
            }
        else
            echo -e "${YELLOW}\u26a0\ufe0f  $MOUNT_POINT n'est pas vide, non supprime.${NC}"
            log_action "cleanup_stockage" "$DEVICE" "$MOUNT_POINT" "warning" "Repertoire non vide"
        fi
    fi
done

# --- 3. Verification finale ---
echo ""
echo -e "${BLUE}=== Verification finale ===${NC}"
REMAINING_MOUNTS=()
while IFS= read -r dir; do
    [ -n "$dir" ] && REMAINING_MOUNTS+=("$dir")
done < <(list_mounts_under_stockage)

if [ ${#REMAINING_MOUNTS[@]} -eq 0 ]; then
    echo -e "${GREEN}\u2705 Tous les peripheriques ont ete demontes avec succes.${NC}"
    log_action "umount_all_stockage" "" "$STOCKAGE_DIR" "success" "Tous les peripheriques demontes"
else
    echo -e "${RED}\u274c Certains peripheriques n'ont pas pu etre demontes :${NC}"
    for mount_point in "${REMAINING_MOUNTS[@]}"; do
        echo -e "${RED}  - ${mount_point}${NC}"
    done
    log_action "umount_all_stockage" "" "$STOCKAGE_DIR" "failed" "Certains peripheriques toujours montes"
    ERRORS=$((ERRORS + 1))
fi

# --- 4. Nettoyage final des dossiers vides residuels ---
CLEANED=0
while IFS= read -r -d '' dir; do
    if [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
        sudo rmdir "$dir" 2>/dev/null && {
            echo -e "${GREEN}\ud83e\uddf9 Dossier residuel supprime : $dir${NC}"
            CLEANED=$((CLEANED + 1))
        }
    fi
done < <(find "$STOCKAGE_DIR" -mindepth 1 -depth -type d -print0 2>/dev/null)
[ "$CLEANED" -gt 0 ] && log_action "cleanup_stockage" "" "$STOCKAGE_DIR" "success" "$CLEANED dossiers residuels supprimes"

# --- 5. Nettoyage du contexte actif (anti mauvaise manipulation) ---
# Une fois /stockage vide (tout démonté), on efface l'utilisateur et le
# projet actifs pour éviter qu'une action suivante ne s'exécute par erreur
# avec un contexte devenu incohérent.
if [ ${#REMAINING_MOUNTS[@]} -eq 0 ]; then
    rm -f "$ACTIVE_USER_FILE" "$ACTIVE_PROJECT_FILE" 2>/dev/null || true
    log_action "clear_active" "" "$STOCKAGE_DIR" "success" "Contexte actif (utilisateur/projet) effacé après démontage"
fi

final_pause
