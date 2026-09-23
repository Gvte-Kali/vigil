#!/bin/bash

# --- Couleurs ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Vérifier qu'un projet, une entité et un utilisateur sont actifs ---
ACTIVE_PROJECT_FILE="/opt/vigil/data/active_project"
ACTIVE_ENTITY_FILE="/opt/vigil/data/active_entity"
ACTIVE_USER_FILE="/opt/vigil/data/active_user"
PROJECTS_DIR="/opt/vigil/data/projects"

if [[ ! -f "$ACTIVE_PROJECT_FILE" || ! -f "$ACTIVE_ENTITY_FILE" || ! -f "$ACTIVE_USER_FILE" ]]; then
    echo -e "${RED}❌ Aucun projet, entité ou utilisateur actif sélectionné.${NC}"
    exit 1
fi

ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE")
ACTIVE_ENTITY=$(cat "$ACTIVE_ENTITY_FILE")
ACTIVE_USER=$(cat "$ACTIVE_USER_FILE")
PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_ENTITY/$ACTIVE_USER/$ACTIVE_PROJECT"

# Créer le dossier de logs s'il n'existe pas
mkdir -p "$PROJECT_LOG_DIR"

# --- Fonction pour logger ---
log_action() {
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

clear
echo -e "${BLUE}=== Scan Antivirus (ClamAV) ===${NC}\n"
echo -e "${YELLOW}Note : Un périphérique doit être monté dans /investigation pour cette option.${NC}\n"

# Vérifier qu'un périphérique est monté
MOUNT_POINTS=()
while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        MOUNT_POINTS+=("$dir")
    fi
done < <(find /investigation -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [[ ${#MOUNT_POINTS[@]} -eq 0 ]]; then
    echo -e "${RED}❌ Aucun périphérique monté dans /investigation.${NC}"
    echo -e "${YELLOW}Montez d'abord un périphérique avec l'option 'Analyse Rapide'.${NC}"
    read -p "Appuyez sur Entrée pour continuer..."
    exit 0
fi

echo -e "${GREEN}Périphériques montés détectés :${NC}"
for i in "${!MOUNT_POINTS[@]}"; do
    echo -e "${BLUE}[$((i+1))]${NC} ${MOUNT_POINTS[$i]}"
done

# Sélection du périphérique à analyser
echo -ne "\nEntrez le numéro du périphérique à analyser (ou \"q\" pour annuler) : "
read -r SELECTED_NUM

if [[ "$SELECTED_NUM" == "q" ]]; then
    echo -e "Annulé."
    exit 0
fi

if ! [[ "$SELECTED_NUM" =~ ^[0-9]+$ ]] || [[ "$SELECTED_NUM" -lt 1 || "$SELECTED_NUM" -gt ${#MOUNT_POINTS[@]} ]]; then
    echo -e "${RED}❌ Numéro invalide.${NC}"
    log_action "analysis_attempt" "" "" "failed" "Numéro de périphérique invalide"
    exit 1
fi

SELECTED_MOUNT_POINT="${MOUNT_POINTS[$((SELECTED_NUM-1))]}"
DEVICE=$(mount | grep "$SELECTED_MOUNT_POINT" | awk '{print $1}' | head -n 1 || echo "")

if [[ -z "$DEVICE" ]]; then
    echo -e "${RED}❌ Impossible de déterminer le périphérique pour $SELECTED_MOUNT_POINT.${NC}"
    log_action "analysis_attempt" "" "$SELECTED_MOUNT_POINT" "failed" "Périphérique introuvable"
    exit 1
fi

# Lancer l'analyse ClamAV
echo -e "${BLUE}=== Lancement de l'analyse ClamAV sur $SELECTED_MOUNT_POINT ===${NC}"
ANALYSIS_LOG="$PROJECT_LOG_DIR/clamav_$(basename "$SELECTED_MOUNT_POINT").log"
sudo clamscan -r --bell "$SELECTED_MOUNT_POINT" | tee "$ANALYSIS_LOG"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ Analyse terminée. Rapport : ${ANALYSIS_LOG}${NC}"
    log_action "analysis" "$DEVICE" "$ANALYSIS_LOG" "success" "Analyse ClamAV terminée"
else
    echo -e "${RED}❌ Analyse ClamAV terminée avec des erreurs. Voir ${ANALYSIS_LOG}${NC}"
    log_action "analysis" "$DEVICE" "$ANALYSIS_LOG" "warning" "Analyse ClamAV terminée avec des alertes"
fi

read -p "Appuyez sur Entrée pour continuer..."
exit 0