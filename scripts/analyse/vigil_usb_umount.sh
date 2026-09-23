#!/bin/bash
set -uo pipefail

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

# --- Contexte actif (utilisateur + projet) : non bloquant pour le démontage ---
# Le démontage est une opération matérielle utilitaire : elle doit rester
# possible même sans utilisateur/projet actifs. Si un contexte existe, on
# l'utilise pour tracer l'action dans la chaîne de custody ; sinon, on
# démonte quand même et on n'écrit pas de log.
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="$VIGIL_BASE/data/config/system.json"

ERRORS=0

ACTIVE_USER="(no-user)"
[ -f "$ACTIVE_USER_FILE" ] && ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
[ -z "$ACTIVE_USER" ] && ACTIVE_USER="(no-user)"

ACTIVE_PROJECT="(no-project)"
[ -f "$ACTIVE_PROJECT_FILE" ] && ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
[ -z "$ACTIVE_PROJECT" ] && ACTIVE_PROJECT="(no-project)"

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

# Créer le dossier de logs s'il n'existe pas (si un projet est actif)
[ "$ACTIVE_PROJECT" != "(no-project)" ] && mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || true

# --- Vérification des privilèges root ---
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Ce script nécessite des privilèges root pour démonter les périphériques.${NC}"
    echo -e "${YELLOW}    Vérifiez la configuration sudo de l'utilisateur courant.${NC}"
fi

# --- Fonction pour logger ---
log_action() {
    local action="$1"
    local device="$2"
    local file_path="$3"
    local status="$4"
    local message="$5"

    # Chasse (recherche de menaces) : chaque evenement est journalise dans
    # hunt/chain_of_custody.json (section custody du rapport consolide),
    # meme sans projet. VIGIL_HUNT_CUSTODY est exporte par la chasse.
    if [ -n "${VIGIL_HUNT_CUSTODY:-}" ]; then
        local timestamp
        timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
        local _user="$ACTIVE_USER"
        [ -n "${VIGIL_ACTIVE_USER:-}" ] && _user="$VIGIL_ACTIVE_USER"
        if command -v jq >/dev/null 2>&1; then
            jq -c -n \
                --arg timestamp "$timestamp" \
                --arg user "$_user" \
                --arg action "$action" \
                --arg status "$status" \
                --arg message "$message" \
                --arg device "$device" \
                '{timestamp: $timestamp, user: $user, action: $action,
                  status: $status, message: $message, device: $device}' \
                >> "$VIGIL_HUNT_CUSTODY" 2>/dev/null || true
        else
            printf '{"timestamp":"%s","user":"%s","action":"%s","status":"%s","message":"%s"}\n' \
                "$timestamp" "$_user" "$action" "$status" "$message" \
                >> "$VIGIL_HUNT_CUSTODY" 2>/dev/null || true
        fi
    fi
    # Sans utilisateur ni projet actif, pas de chaîne de custody projet.
    [ "$ACTIVE_USER" = "(no-user)" ] && return
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

# --- Lister les points de montage réels sous /investigation (récursif) ---
# Les montages multi-partitions sont imbriqués (/investigation/<disk>/<part>),
# donc un simple `find -maxdepth 1` ne les détecte pas. /proc/mounts est la
# source de vérité du noyau : fichier texte listant tous les montages du
# namespace courant, sans dépendre d'aucune commande externe. On lit le
# 2e champ (point de montage) des lignes sous /investigation, puis on trie
# du plus profond au moins profond afin de démonter les enfants avant les
# parents (sinon umount renvoie "target busy"). Fallback lsblk (qui lit
# /sys) si /proc/mounts est vide pour une raison inattendue.
list_mounts_under_investigation() {
    local mounts
    mounts="$(awk '$2 ~ "^/investigation/" {print $2}' /proc/mounts 2>/dev/null)"
    if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
        mounts="$(lsblk -J -o MOUNTPOINTS 2>/dev/null \
            | grep -oE '"/investigation/[^"]*"' | tr -d '"')"
    fi
    printf '%s\n' "$mounts" \
        | awk -v base="/investigation/" 'index($0, base) == 1' \
        | awk '{ print length($0), $0 }' | sort -rn | cut -d' ' -f2-
}

# --- Pause finale : ne jamais fermer sans que l'utilisateur ait vu ---
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

# --- Nettoyer l'écran ---
clear
print_banner
echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo ""

# S'assurer que /investigation existe
sudo mkdir -p /investigation 2>/dev/null || true

# --- 1. Lister tous les points de montage sous /investigation ---
echo -e "${BLUE}=== Recherche des périphériques montés dans /investigation ===${NC}"

MOUNT_POINTS=()
while IFS= read -r dir; do
    [ -n "$dir" ] && MOUNT_POINTS+=("$dir")
done < <(list_mounts_under_investigation)

if [ ${#MOUNT_POINTS[@]} -eq 0 ]; then
    echo -e "${YELLOW}ℹ️  Aucun périphérique monté dans /investigation.${NC}"
    log_action "umount_attempt" "" "/investigation" "info" "Aucun périphérique monté"

    # --- Nettoyage des dossiers vides résiduels même si rien n'est monté ---
    CLEANED=0
    while IFS= read -r -d '' dir; do
        if [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
            sudo rmdir "$dir" 2>/dev/null && {
                echo -e "${GREEN}🧹 Dossier vide supprimé : $dir${NC}"
                CLEANED=$((CLEANED + 1))
            }
        fi
    done < <(find /investigation -mindepth 1 -depth -type d -print0 2>/dev/null)
    [ "$CLEANED" -gt 0 ] && log_action "cleanup" "" "/investigation" "success" "$CLEANED dossiers vides supprimés"

    # Rien n'est monté : le contexte actif est incohérent -> nettoyage.
    rm -f "$ACTIVE_USER_FILE" "$ACTIVE_PROJECT_FILE" 2>/dev/null || true
    log_action "clear_active" "" "/investigation" "success" "Contexte actif efface (rien monte)"
    final_pause
    exit 0
fi

echo -e "${GREEN}Périphériques montés détectés :${NC}"
for mount_point in "${MOUNT_POINTS[@]}"; do
    echo -e "${BLUE}  - ${mount_point}${NC}"
done

# --- 2. Démontage et vérification d'intégrité pour chaque périphérique ---
for MOUNT_POINT in "${MOUNT_POINTS[@]}"; do
    echo ""
    echo -e "${BLUE}--- Traitement de $MOUNT_POINT ---${NC}"

    # --- 2.1. Récupérer le périphérique associé ---
    DEVICE=$(mount | grep " ${MOUNT_POINT} " | awk '{print $1}' | head -n 1 || true)

    if [ -z "$DEVICE" ]; then
        echo -e "${YELLOW}⚠️  Impossible de déterminer le périphérique monté sur $MOUNT_POINT.${NC}"
        log_action "umount_attempt" "" "$MOUNT_POINT" "warning" "Périphérique monté introuvable"
        DEVICE=""
    fi

    # --- 2.2. Calcul du hash actuel (vérification d'intégrité) ---
    if [ -n "$DEVICE" ]; then
        echo -e "${BLUE}=== Vérification de l'intégrité pour $DEVICE ($MOUNT_POINT) ===${NC}"
        CURRENT_HASH=$(find "$MOUNT_POINT" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' 2>/dev/null || true)
        HASH_FILE="$PROJECT_LOG_DIR/device_$(basename "$DEVICE").sha256"

        if [ ! -f "$HASH_FILE" ]; then
            echo -e "${YELLOW}⚠️  Fichier de hash introuvable : $HASH_FILE${NC}"
            log_action "integrity_check" "$DEVICE" "$HASH_FILE" "warning" "Fichier de hash manquant"
        else
            STORED_HASH=$(cat "$HASH_FILE" 2>/dev/null || true)
            echo -e "${BLUE}Hash stocké :${NC} $STORED_HASH"
            echo -e "${BLUE}Hash actuel :${NC} $CURRENT_HASH"

            if [ "$CURRENT_HASH" = "$STORED_HASH" ] && [ -n "$CURRENT_HASH" ]; then
                echo -e "${GREEN}✅ Le périphérique $DEVICE n'a pas été corrompu.${NC}"
                log_action "integrity_check" "$DEVICE" "$HASH_FILE" "success" "Intégrité vérifiée : hash initial = hash recalculé ($STORED_HASH)"
            else
                echo -e "${RED}❌ ATTENTION : Le périphérique $DEVICE a été corrompu !${NC}"
                log_action "integrity_check" "$DEVICE" "$HASH_FILE" "corrupted" "Hash modifié : initial $STORED_HASH → recalculé $CURRENT_HASH — périphérique corrompu"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    fi

    # --- 2.3. Démontage du périphérique ---
    echo -e "${YELLOW}Démontage de $MOUNT_POINT...${NC}"
    UMOUNT_OK=0

    if sudo umount "$MOUNT_POINT" 2>/dev/null; then
        UMOUNT_OK=1
    else
        echo -e "${YELLOW}⚠️  Démontage normal échoué (périphérique occupé ?). Tentative de synchronisation...${NC}"
        sync 2>/dev/null || true
        # Retenter après sync
        if sudo umount "$MOUNT_POINT" 2>/dev/null; then
            UMOUNT_OK=1
        else
            echo -e "${YELLOW}⚠️  Toujours occupé. Démontage forcé (lazy umount)...${NC}"
            if sudo umount -l "$MOUNT_POINT" 2>/dev/null; then
                echo -e "${YELLOW}⚠️  Démontage lazy appliqué. Le périphérique sera libéré quand plus aucun fichier ne sera utilisé.${NC}"
                log_action "umount_lazy" "$DEVICE" "$MOUNT_POINT" "warning" "Démontage forcé (lazy)"
                UMOUNT_OK=1
            else
                echo -e "${RED}❌ Échec du démontage de $MOUNT_POINT.${NC}"
                log_action "umount" "$DEVICE" "$MOUNT_POINT" "failed" "Échec du démontage"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    fi

    if [ "$UMOUNT_OK" -eq 1 ]; then
        echo -e "${GREEN}✅ Périphérique $DEVICE démonté avec succès.${NC}"
        log_action "umount" "$DEVICE" "$MOUNT_POINT" "success" "Périphérique démonté"

        # --- 2.4. Remettre le block device en read-write s'il avait été forcé en RO ---
        if [ -n "$DEVICE" ] && [ -b "$DEVICE" ]; then
            sudo blockdev --setrw "$DEVICE" 2>/dev/null && \
                echo -e "${GREEN}✅ Block device $DEVICE remis en lecture/écriture.${NC}" || true
            log_action "set_rw" "$DEVICE" "" "success" "Block device remis en RW" 2>/dev/null || true
        fi
    fi

    # --- 2.5. Nettoyage du répertoire vide (toujours, même si umount a échoué en lazy) ---
    # Attendre un court instant que le noyau libère le point de montage
    sleep 1
    if [ -d "$MOUNT_POINT" ]; then
        if [ -z "$(ls -A "$MOUNT_POINT" 2>/dev/null)" ]; then
            sudo rmdir "$MOUNT_POINT" 2>/dev/null && {
                echo -e "${GREEN}🧹 Dossier de montage supprimé : $MOUNT_POINT${NC}"
                log_action "cleanup" "$DEVICE" "$MOUNT_POINT" "success" "Répertoire de montage supprimé"
            } || {
                echo -e "${YELLOW}⚠️  Impossible de supprimer $MOUNT_POINT (toujours occupé ?).${NC}"
                log_action "cleanup" "$DEVICE" "$MOUNT_POINT" "warning" "Répertoire non supprimé (occupé)"
            }
        else
            echo -e "${YELLOW}⚠️  $MOUNT_POINT n'est pas vide, non supprimé.${NC}"
            log_action "cleanup" "$DEVICE" "$MOUNT_POINT" "warning" "Répertoire non vide"
        fi
    fi
done

# --- 3. Vérifier qu'aucun périphérique n'est plus monté dans /investigation ---
echo ""
echo -e "${BLUE}=== Vérification finale ===${NC}"
REMAINING_MOUNTS=()
while IFS= read -r dir; do
    [ -n "$dir" ] && REMAINING_MOUNTS+=("$dir")
done < <(list_mounts_under_investigation)

if [ ${#REMAINING_MOUNTS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ Tous les périphériques ont été démontés avec succès.${NC}"
    log_action "umount_all" "" "/investigation" "success" "Tous les périphériques démontés"
else
    echo -e "${RED}❌ Certains périphériques n'ont pas pu être démontés :${NC}"
    for mount_point in "${REMAINING_MOUNTS[@]}"; do
        echo -e "${RED}  - ${mount_point}${NC}"
    done
    log_action "umount_all" "" "/investigation" "failed" "Certains périphériques toujours montés"
    ERRORS=$((ERRORS + 1))
fi

# --- 4. Nettoyage final des dossiers vides résiduels ---
CLEANED=0
while IFS= read -r -d '' dir; do
    if [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
        sudo rmdir "$dir" 2>/dev/null && {
            echo -e "${GREEN}🧹 Dossier résiduel supprimé : $dir${NC}"
            CLEANED=$((CLEANED + 1))
        }
    fi
done < <(find /investigation -mindepth 1 -depth -type d -print0 2>/dev/null)
[ "$CLEANED" -gt 0 ] && log_action "cleanup" "" "/investigation" "success" "$CLEANED dossiers résiduels supprimés"

# --- 5. Nettoyage du contexte actif (anti mauvaise manipulation) ---
# Une fois /investigation vide (tout démonté), on efface l'utilisateur et le
# projet actifs pour éviter qu'une action suivante ne s'exécute par erreur
# avec un contexte devenu incohérent.
if [ ${#REMAINING_MOUNTS[@]} -eq 0 ]; then
    rm -f "$ACTIVE_USER_FILE" "$ACTIVE_PROJECT_FILE" 2>/dev/null || true
    log_action "clear_active" "" "/investigation" "success" "Contexte actif (utilisateur/projet) effacé après démontage"
fi

final_pause
