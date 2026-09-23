#!/bin/bash

# --- Couleurs ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Vérifier les arguments ---
NO_LOG=false
DEVICE_MODE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            DEVICE_MODE="$2"
            shift 2
            ;;
        --no-log)
            NO_LOG=true
            shift
            ;;
        *)
            echo "Usage: $0 --mode [smartphone|usb_storage|all] [--no-log]"
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

# Créer les dossiers de logs et d'investigation s'ils n'existent pas
mkdir -p "$PROJECT_LOG_DIR"
sudo mkdir -p /investigation
sudo chmod 755 /investigation

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

# --- Démontage automatique des périphériques existants ---
if [[ "$NO_LOG" == false ]]; then
    echo -e "${YELLOW}Démontage automatique des périphériques existants dans /investigation...${NC}"
fi

while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${YELLOW}Démontage de $dir...${NC}"
        fi
        sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${GREEN}✅ $dir démonté et nettoyé.${NC}"
            log_action "auto_umount" "" "$dir" "success" "Démontage automatique avant nouveau montage"
        fi
    fi
done < <(find /investigation -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

# Vérifier qu'aucun périphérique n'est plus monté
REMAINING_MOUNTS=0
while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        REMAINING_MOUNTS=$((REMAINING_MOUNTS + 1))
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${RED}❌ $dir est toujours monté.${NC}"
        fi
    fi
done < <(find /investigation -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [[ $REMAINING_MOUNTS -gt 0 ]]; then
    if [[ "$NO_LOG" == false ]]; then
        log_action "auto_umount_all" "" "/investigation" "failed" "Certains périphériques toujours montés"
    fi
    exit 1
fi

if [[ "$NO_LOG" == false ]]; then
    echo -e "${GREEN}✅ Tous les périphériques existants ont été démontés.${NC}"
fi

# --- Détection des périphériques selon le mode ---
if [[ "$NO_LOG" == false ]]; then
    echo -e "\n${BLUE}=== Détection des périphériques (Mode: $DEVICE_MODE) ===${NC}"
fi

# --- Détection des DVD/CD-ROM (uniquement en mode "all") ---
if [[ "$DEVICE_MODE" == "all" ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${YELLOW}Recherche de lecteurs CD-ROM...${NC}"
    fi
    if [[ -e /dev/cdrom ]]; then
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${YELLOW}Lecteur CD-ROM détecté. Vérification du média...${NC}"
        fi
        if eject -t /dev/cdrom 2>/dev/null; then
            sleep 2
            if mount /dev/cdrom /investigation/cdrom -o ro,noexec,nosuid,nodev,noatime 2>/dev/null; then
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${GREEN}✅ Média optique monté dans /investigation/cdrom${NC}"
                    log_action "mount" "/dev/cdrom" "/investigation/cdrom" "success" "Média optique monté en lecture seule"
                fi
                if [[ "$NO_LOG" == false ]]; then
                    sudo clamscan -r --bell /investigation/cdrom > "$PROJECT_LOG_DIR/clamav_cdrom.log" 2>&1
                    log_action "post_mount_analysis" "/dev/cdrom" "$PROJECT_LOG_DIR/clamav_cdrom.log" "success" "Analyse ClamAV terminée"
                fi
                exit 0
            else
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${RED}❌ Aucun média optique détecté ou échec du montage.${NC}"
                    log_action "mount_attempt" "/dev/cdrom" "/investigation/cdrom" "failed" "Échec du montage du média optique"
                fi
                exit 1
            fi
        fi
    fi
fi

# --- Détection des périphériques MTP (Smartphone ou All) ---
if [[ "$DEVICE_MODE" == "smartphone" || "$DEVICE_MODE" == "all" ]]; then
    if command -v jmtpfs &>/dev/null; then
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${YELLOW}Recherche de périphériques MTP...${NC}"
        fi
        MTP_DEVICES=$(jmtpfs -l 2>/dev/null | grep -E "^Device [0-9]+" || true)
        if [[ -n "$MTP_DEVICES" ]]; then
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${GREEN}✅ Périphérique(s) MTP détecté(s) :${NC}"
                echo "$MTP_DEVICES" | while IFS= read -r line; do
                    echo -e "   ${line}"
                done
            fi
            sudo mkdir -p /investigation/mtp
            if sudo jmtpfs /investigation/mtp -o ro 2>/dev/null; then
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${GREEN}✅ Périphérique MTP monté dans /investigation/mtp${NC}"
                    log_action "mount" "MTP" "/investigation/mtp" "success" "Périphérique MTP monté en lecture seule"
                fi
                exit 0
            else
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${RED}❌ Échec du montage MTP.${NC}"
                    log_action "mount_attempt" "MTP" "/investigation/mtp" "failed" "Échec du montage MTP"
                fi
                sudo rmdir /investigation/mtp 2>/dev/null
                exit 1
            fi
        else
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${YELLOW}⚠️  Aucun périphérique MTP détecté.${NC}"
                log_action "mount_attempt" "MTP" "" "failed" "Aucun périphérique MTP détecté"
            fi
            exit 1
        fi
    else
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${YELLOW}⚠️  jmtpfs non installé. Impossible de détecter les périphériques MTP.${NC}"
            log_action "mount_attempt" "MTP" "" "failed" "jmtpfs non disponible"
        fi
        exit 1
    fi
fi

# --- Détection des périphériques USB (USB Storage ou All) ---
if [[ "$DEVICE_MODE" == "usb_storage" || "$DEVICE_MODE" == "all" ]]; then
    if [[ "$NO_LOG" == false ]]; then
        echo -e "${YELLOW}Recherche des périphériques USB/Disques...${NC}"
    fi
    declare -A USB_DEVICES
    DEVICE_NUM=0

    # Lire les périphériques bloc et filtrer les partitions USB
    while IFS=$'\t' read -r NAME TYPE PKNAME MOUNTPOINT _; do
        if [[ "$TYPE" == "part" && -z "$MOUNTPOINT" && -n "$PKNAME" ]]; then
            TRAN=$(lsblk -dno TRAN "/dev/$PKNAME" 2>/dev/null || echo "")
            if [[ "$TRAN" == "usb" ]]; then
                SIZE=$(lsblk -dno SIZE "/dev/$NAME" 2>/dev/null || echo "")
                MODEL=$(lsblk -dno MODEL "/dev/$PKNAME" 2>/dev/null || echo "")
                USB_DEVICES[$DEVICE_NUM]="$NAME|$SIZE|$MODEL"
                ((DEVICE_NUM++))
            fi
        fi
    done < <(lsblk -lno NAME,TYPE,PKNAME,MOUNTPOINT 2>/dev/null)

    if [[ $DEVICE_NUM -eq 0 ]]; then
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${RED}❌ Aucun périphérique USB/Disque non monté détecté.${NC}"
            log_action "mount_attempt" "" "/investigation" "failed" "Aucun périphérique détecté"
        fi
        exit 1
    else
        # --- Affichage des périphériques ---
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${GREEN}Périphériques disponibles :${NC}"
            for i in "${!USB_DEVICES[@]}"; do
                IFS='|' read -r DEVICE_NAME DEVICE_SIZE DEVICE_MODEL <<< "${USB_DEVICES[$i]}"
                echo -e "${BLUE}[$((i+1))]${NC} /dev/$DEVICE_NAME - Taille: $DEVICE_SIZE | Modèle: $DEVICE_MODEL"
            done
        fi

        # --- Sélection du périphérique ---
        while true; do
            if [[ "$NO_LOG" == false ]]; then
                echo -ne "\n${YELLOW}Entrez le numéro du périphérique à monter (ou \"q\" pour annuler) : ${NC}"
            else
                echo -ne "\nEntrez le numéro du périphérique à monter (ou \"q\" pour annuler) : "
            fi
            read -r SELECTED_NUM

            if [[ "$SELECTED_NUM" == "q" ]]; then
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${YELLOW}Annulé.${NC}"
                fi
                exit 0
            fi

            if ! [[ "$SELECTED_NUM" =~ ^[0-9]+$ ]] || [[ "$SELECTED_NUM" -lt 1 || "$SELECTED_NUM" -gt $DEVICE_NUM ]]; then
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${RED}❌ Numéro invalide. Veuillez entrer un numéro entre 1 et $DEVICE_NUM.${NC}"
                else
                    echo -e "❌ Numéro invalide. Veuillez entrer un numéro entre 1 et $DEVICE_NUM."
                fi
                continue
            fi

            SELECTED_INDEX=$((SELECTED_NUM-1))
            IFS='|' read -r SELECTED_DEVICE DEVICE_SIZE DEVICE_MODEL <<< "${USB_DEVICES[$SELECTED_INDEX]}"
            DEVICE_PATH="/dev/$SELECTED_DEVICE"
            break
        done

        # --- Vérification des partitions chiffrées ---
        if cryptsetup isLuks "$DEVICE_PATH" 2>/dev/null; then
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${RED}❌ Ce périphérique est chiffré (LUKS).${NC}"
                echo -e "${YELLOW}Utilisez un outil de déchiffrement avant de continuer.${NC}"
                log_action "mount_attempt" "$DEVICE_PATH" "/investigation" "failed" "Périphérique chiffré (LUKS)"
            else
                echo -e "❌ Ce périphérique est chiffré (LUKS)."
            fi
            exit 1
        fi

        BITLOCKER_SIGNATURES=("61iQLUZWRS1GUy0=" "61KQLUZWRS1GUy0=" "61iQTVNXSU40LjE=")
        DEVICE_SIGNATURE=$(dd if="$DEVICE_PATH" bs=11 count=1 status=none 2>/dev/null | base64 || true)
        for sig in "${BITLOCKER_SIGNATURES[@]}"; do
            if [[ "$DEVICE_SIGNATURE" == "$sig" ]]; then
                if [[ "$NO_LOG" == false ]]; then
                    echo -e "${RED}❌ Ce périphérique est chiffré (BitLocker).${NC}"
                    echo -e "${YELLOW}Utilisez un outil de déchiffrement avant de continuer.${NC}"
                    log_action "mount_attempt" "$DEVICE_PATH" "/investigation" "failed" "Périphérique chiffré (BitLocker)"
                else
                    echo -e "❌ Ce périphérique est chiffré (BitLocker)."
                fi
                exit 1
            fi
        done

        # --- Montage en lecture seule ---
        MOUNT_POINT="/investigation/${SELECTED_DEVICE}"
        if [[ "$NO_LOG" == false ]]; then
            echo -e "\n${YELLOW}Montage de ${GREEN}$DEVICE_PATH${YELLOW} dans $MOUNT_POINT...${NC}"
        else
            echo -e "\nMontage de $DEVICE_PATH dans $MOUNT_POINT..."
        fi

        # Créer le point de montage
        sudo mkdir -p "$MOUNT_POINT" || {
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${RED}❌ Impossible de créer le point de montage $MOUNT_POINT.${NC}"
                log_action "mkdir_mountpoint" "$DEVICE_PATH" "$MOUNT_POINT" "failed" "Échec de la création du répertoire"
            else
                echo -e "❌ Impossible de créer le point de montage $MOUNT_POINT."
            fi
            exit 1
        }

        # Forcer la RO au niveau block device
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${YELLOW}Forçage du mode lecture seule au niveau block device...${NC}"
        fi
        if ! sudo blockdev --setro "$DEVICE_PATH" 2>/dev/null; then
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${RED}❌ Impossible de forcer le mode RO sur $DEVICE_PATH.${NC}"
                log_action "set_ro" "$DEVICE_PATH" "" "failed" "Échec de blockdev --setro"
            else
                echo -e "❌ Impossible de forcer le mode RO sur $DEVICE_PATH."
            fi
            exit 1
        fi
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${GREEN}✅ Mode RO forcé au niveau block device.${NC}"
            log_action "set_ro" "$DEVICE_PATH" "" "success" "Mode RO forcé au niveau block device"
        fi

        # Déterminer les options de montage
        FSTYPE=$(lsblk -no FSTYPE "$DEVICE_PATH" 2>/dev/null || echo "")
        MOUNT_OPTS="-o ro,noexec,nosuid,nodev,noatime"
        case "$FSTYPE" in
            fat32|vfat) MOUNT_OPTS="$MOUNT_OPTS,utf8=true" ;;
            ext3|ext4)  MOUNT_OPTS="$MOUNT_OPTS,noload" ;;
            ufs)        MOUNT_OPTS="$MOUNT_OPTS,ufstype=ufs2" ;;
            iso9660)    MOUNT_OPTS="$MOUNT_OPTS,unhide" ;;
            btrfs)      MOUNT_OPTS="$MOUNT_OPTS,subvolid=0" ;;
        esac
        if [[ "$NO_LOG" == false ]]; then
            echo -e "${YELLOW}Options de montage : $MOUNT_OPTS${NC}"
        fi

        # Monter le périphérique
        if ! sudo mount $MOUNT_OPTS "$DEVICE_PATH" "$MOUNT_POINT" 2>/dev/null; then
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${RED}❌ Échec du montage de $DEVICE_PATH.${NC}"
                echo -e "${YELLOW}Détails :${NC}"
                sudo mount $MOUNT_OPTS "$DEVICE_PATH" "$MOUNT_POINT" 2>&1
                log_action "mount" "$DEVICE_PATH" "$MOUNT_POINT" "failed" "Échec du montage"
            else
                echo -e "❌ Échec du montage de $DEVICE_PATH."
            fi
            exit 1
        fi

        # Vérifier que le périphérique est bien en lecture seule
        RO_CHECK=$(lsblk -o RO "$DEVICE_PATH" | tail -n 1 | awk '{print $1}' || echo "")
        if [[ "$RO_CHECK" != "1" ]]; then
            if [[ "$NO_LOG" == false ]]; then
                echo -e "${RED}❌ Le périphérique $DEVICE_PATH n'est pas monté en lecture seule !${NC}"
                log_action "mount" "$DEVICE_PATH" "$MOUNT_POINT" "failed" "Périphérique non monté en lecture seule"
            else
                echo -e "❌ Le périphérique $DEVICE_PATH n'est pas monté en lecture seule !"
            fi
            sudo umount "$MOUNT_POINT" 2>/dev/null
            sudo rmdir "$MOUNT_POINT" 2>/dev/null
            exit 1
        fi

        if [[ "$NO_LOG" == false ]]; then
            echo -e "${GREEN}✅ Périphérique monté avec succès :${NC} $DEVICE_PATH → $MOUNT_POINT"
            log_action "mount" "$DEVICE_PATH" "$MOUNT_POINT" "success" "Périphérique monté en lecture seule"

            # --- Calcul du hash SHA-256 ---
            echo -e "\n${BLUE}=== Calcul du hash SHA-256 ===${NC}"
            HASH_FILE="$PROJECT_LOG_DIR/device_${SELECTED_DEVICE}.sha256"
            sudo rm -f "$HASH_FILE"

            if [[ -n $(ls -A "$MOUNT_POINT" 2>/dev/null) ]]; then
                find "$MOUNT_POINT" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' > "$HASH_FILE"
                echo -e "${GREEN}✅ Hash SHA-256 stocké dans :${NC} $HASH_FILE"
                echo -e "${BLUE}Hash :${NC} $(cat "$HASH_FILE")"
                log_action "hash_calculation" "$DEVICE_PATH" "$HASH_FILE" "success" "Hash SHA-256 calculé"
            else
                echo -e "${YELLOW}⚠️  $MOUNT_POINT est vide, aucun hash généré.${NC}"
                log_action "hash_calculation" "$DEVICE_PATH" "" "warning" "$MOUNT_POINT est vide"
            fi

            # --- Analyse Post-Montage (Optionnelle) ---
            echo -ne "\n${YELLOW}Voulez-vous lancer une analyse automatique (ClamAV) sur ce périphérique ? (o/n) : ${NC}"
            read -r ANALYSIS_CHOICE

            if [[ "$ANALYSIS_CHOICE" =~ ^[OoYy]$ ]]; then
                echo -e "${BLUE}=== Lancement de l'analyse ClamAV ===${NC}"
                ANALYSIS_LOG="$PROJECT_LOG_DIR/clamav_${SELECTED_DEVICE}.log"
                sudo clamscan -r --bell "$MOUNT_POINT" > "$ANALYSIS_LOG" 2>&1
                if [[ $? -eq 0 ]]; then
                    echo -e "${GREEN}✅ Analyse terminée. Rapport : ${ANALYSIS_LOG}${NC}"
                    log_action "post_mount_analysis" "$DEVICE_PATH" "$ANALYSIS_LOG" "success" "Analyse ClamAV terminée"
                else
                    echo -e "${RED}❌ Analyse ClamAV terminée avec des erreurs. Voir ${ANALYSIS_LOG}${NC}"
                    log_action "post_mount_analysis" "$DEVICE_PATH" "$ANALYSIS_LOG" "warning" "Analyse ClamAV terminée avec des alertes"
                fi
            fi
        else
            echo -e "✅ Périphérique monté avec succès : $DEVICE_PATH → $MOUNT_POINT"
        fi
    fi
fi

if [[ "$NO_LOG" == false ]]; then
    echo -e "\n${GREEN}Montage terminé.${NC}"
fi
exit 0