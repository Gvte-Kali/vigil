#!/bin/bash

# --- Couleurs ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Vérifier les arguments ---
NO_LOG=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-log)
            NO_LOG=true
            shift
            ;;
        *)
            echo "Usage: $0 [--no-log]"
            exit 1
            ;;
    esac
done

# --- Vérifier qu'un projet, une entité et un utilisateur sont actifs ---
ACTIVE_PROJECT_FILE="/opt/vigil/data/active_project"
ACTIVE_ENTITY_FILE="/opt/vigil/data/active_entity"
ACTIVE_USER_FILE="/opt/vigil/data/active_user"
PROJECTS_DIR="/opt/vigil/data/projects"

if [[ ! -f "$ACTIVE_PROJECT_FILE" || ! -f "$ACTIVE_ENTITY_FILE" || ! -f "$ACTIVE_USER_FILE" ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${RED}❌ Aucun projet, entité ou utilisateur actif sélectionné.${NC}"
    fi
    exit 1
fi

ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE")
ACTIVE_ENTITY=$(cat "$ACTIVE_ENTITY_FILE")
ACTIVE_USER=$(cat "$ACTIVE_USER_FILE")
PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_ENTITY/$ACTIVE_USER/$ACTIVE_PROJECT"

# Créer le dossier de logs s'il n'existe pas
mkdir -p "$PROJECT_LOG_DIR"

# --- Fonction pour logger (désactivée si --no-log) ---
log_action() {
    if [[ "$NO_LOG" == true ]]; then
        return
    fi

    local action="$1"
    local device="$2"
    local file_path="$3"
    local status="$4"
    local message="$5"

    local timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Device:$device | File:$file_path | Status:$status | Message:$message"

    echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null

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
    | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null
}

# --- Lister tous les périphériques montés sous /investigation ---
if [[ "$NO_LOG" == false ]]; then
    echo -e "${BLUE}=== Recherche des périphériques montés dans /investigation ===${NC}"
fi

MOUNT_POINTS=()
while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        MOUNT_POINTS+=("$dir")
    fi
done < <(find /investigation -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [[ ${#MOUNT_POINTS[@]} -eq 0 ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${RED}❌ Aucun périphérique monté dans /investigation.${NC}"
        log_action "umount_attempt" "" "/investigation" "failed" "Aucun périphérique monté"
    fi
    exit 0
fi

if [[ "$NO_LOG" == false ]]; then
    echo -e "${GREEN}Périphériques montés détectés :${NC}"
    for i in "${!MOUNT_POINTS[@]}"; do
        echo -e "${BLUE}[$((i+1))]${NC} ${MOUNT_POINTS[$i]}"
    done
fi

# --- Sélection du périphérique à démonter ---
if [[ "$NO_LOG" == false ]]; then
    echo -ne "\n${YELLOW}Entrez le numéro du périphérique à démonter (ou \"q\" pour annuler) : ${NC}"
else
    echo -ne "\nEntrez le numéro du périphérique à démonter (ou \"q\" pour annuler) : "
fi
read -r SELECTED_NUM

if [[ "$SELECTED_NUM" == "q" ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${YELLOW}Annulé.${NC}"
    fi
    exit 0
fi

if ! [[ "$SELECTED_NUM" =~ ^[0-9]+$ ]] || [[ "$SELECTED_NUM" -lt 1 || "$SELECTED_NUM" -gt ${#MOUNT_POINTS[@]} ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${RED}❌ Numéro invalide.${NC}"
    else
        echo -e "❌ Numéro invalide."
    fi
    log_action "umount_attempt" "" "" "failed" "Numéro de périphérique invalide"
    exit 1
fi

SELECTED_MOUNT_POINT="${MOUNT_POINTS[$((SELECTED_NUM-1))]}"
DEVICE=$(mount | grep "$SELECTED_MOUNT_POINT" | awk '{print $1}' | head -n 1 || echo "")

if [[ -z "$DEVICE" ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${RED}❌ Impossible de déterminer le périphérique pour $SELECTED_MOUNT_POINT.${NC}"
    else
        echo -e "❌ Impossible de déterminer le périphérique pour $SELECTED_MOUNT_POINT."
    fi
    log_action "umount_attempt" "" "$SELECTED_MOUNT_POINT" "failed" "Périphérique introuvable"
    exit 1
fi

# --- Vérification de l'intégrité ---
if [[ "$NO_LOG" == false ]]; then
    echo -e "\n${BLUE}=== Vérification de l'intégrité pour $DEVICE ($SELECTED_MOUNT_POINT) ===${NC}"
fi

CURRENT_HASH=$(find "$SELECTED_MOUNT_POINT" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' 2>/dev/null || true)
HASH_FILE="$PROJECT_LOG_DIR/device_$(basename "$DEVICE").sha256"

if [[ ! -f "$HASH_FILE" ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${RED}❌ Fichier de hash introuvable : $HASH_FILE${NC}"
        log_action "integrity_check" "$DEVICE" "$HASH_FILE" "failed" "Fichier de hash manquant"
    else
        echo -e "❌ Fichier de hash introuvable : $HASH_FILE"
    fi
else
    STORED_HASH=$(cat "$HASH_FILE" 2>/dev/null || true)
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${BLUE}Hash stocké :${NC} $STORED_HASH"
        echo -e "${BLUE}Hash actuel :${NC} $CURRENT_HASH"
    fi

    if [[ "$CURRENT_HASH" == "$STORED_HASH" ]]; then
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${GREEN}✅ Le périphérique $DEVICE n'a pas été corrompu.${NC}"
            log_action "integrity_check" "$DEVICE" "$HASH_FILE" "success" "Intégrité vérifiée"
        else
            echo -e "✅ Le périphérique $DEVICE n'a pas été corrompu."
        fi
    else
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${RED}❌ ⚠️ ATTENTION : Le périphérique $DEVICE a été corrompu !${NC}"
            log_action "integrity_check" "$DEVICE" "$HASH_FILE" "corrupted" "Hash modifié: périphérique corrompu"
        else
            echo -e "❌ ⚠️ ATTENTION : Le périphérique $DEVICE a été corrompu !"
        fi
        if [[ "$NO_LOG" == false ]]; then
            echo -ne "\n${YELLOW}Voulez-vous continuer le démontage malgré la corruption ? (o/n) : ${NC}"
        else
            echo -ne "\nVoulez-vous continuer le démontage malgré la corruption ? (o/n) : "
        fi
        read -r CONTINUE_CHOICE
        if [[ "$CONTINUE_CHOICE" != [OoYy] ]]; then
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${YELLOW}Démontage annulé.${NC}"
            else
                echo -e "Démontage annulé."
            fi
            exit 0
        fi
    fi
fi

# --- Démontage du périphérique ---
if [[ "$NO_LOG" == false ]]; then
    echo -e "${YELLOW}Démontage de $SELECTED_MOUNT_POINT...${NC}"
else
    echo -e "Démontage de $SELECTED_MOUNT_POINT..."
fi

if ! sudo umount "$SELECTED_MOUNT_POINT" 2>/dev/null; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${RED}❌ Échec du démontage de $SELECTED_MOUNT_POINT.${NC}"
        log_action "umount" "$DEVICE" "$SELECTED_MOUNT_POINT" "failed" "Échec du démontage"
    else
        echo -e "❌ Échec du démontage de $SELECTED_MOUNT_POINT."
    fi
    exit 1
fi

if [[ "$NO_LOG" == false ]]; then
    echo -e "${GREEN}✅ Périphérique $DEVICE démonté avec succès.${NC}"
    log_action "umount" "$DEVICE" "$SELECTED_MOUNT_POINT" "success" "Périphérique démonté"
else
    echo -e "✅ Périphérique $DEVICE démonté avec succès."
fi

# Nettoyer le répertoire vide
sudo rmdir "$SELECTED_MOUNT_POINT" 2>/dev/null || {
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${YELLOW}⚠️  Impossible de supprimer $SELECTED_MOUNT_POINT (non vide ou en cours d'utilisation).${NC}"
        log_action "cleanup" "$DEVICE" "$SELECTED_MOUNT_POINT" "warning" "Répertoire non supprimé"
    else
        echo -e "⚠️  Impossible de supprimer $SELECTED_MOUNT_POINT (non vide ou en cours d'utilisation)."
    fi
}

if [[ "$NO_LOG" == false ]]; then
    echo -e "\n${GREEN}Démontage terminé.${NC}"
fi
exit 0