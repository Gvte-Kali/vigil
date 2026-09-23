#!/bin/bash
set -uo pipefail

# --- Mise a jour des bases virales ClamAV depuis un peripherique USB ---
#
# Pour les postes isoles (hors reseau) : on recupere les fichiers de bases
# (bytecode.cvd, daily.cvd, main.cvd) depuis une cle USB branchee a la main.
# Le peripherique est monte en lecture seule (blockdev --setro) dans /stockage,
# on cherche les fichiers .cvd, on les copie dans le DatabaseDirectory ClamAV,
# puis on demonte et rebloque le peripherique.

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

ERRORS=0
STOCKAGE_DIR="/stockage"
CVD_FILES=("bytecode.cvd" "daily.cvd" "main.cvd")

final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Mise à jour terminée avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Mise à jour terminée sans erreur.${NC}"
    fi
}

fail() {
    echo -e "${RED}❌ $1${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Mise à jour ClamAV par USB         ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# --- Verifier les dependances ---
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING=0
for cmd in lsblk mount umount find blockdev clamscan clamconf; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING=$((MISSING + 1))
    fi
done
[ "$MISSING" -gt 0 ] && fail "Dépendances manquantes ($MISSING). Installez clamav et util-linux."

# --- Determiner le DatabaseDirectory ClamAV ---
DB_DIR=$(clamconf 2>/dev/null | sed -nE 's/^\s*DatabaseDirectory\s*=\s*"?([^"]*)"?\s*$/\1/p' | tail -1)
[ -z "$DB_DIR" ] && DB_DIR="/var/lib/clamav"
echo -e "${GREEN}✅ DatabaseDirectory ClamAV : $DB_DIR${NC}"
echo ""

# --- Etape 1 : debrancher tous les peripheriques ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 1 : Débranchement                     ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}⚠️  Débranchez ${BOLD}TOUS${NC}${YELLOW} les périphériques USB actuellement connectés.${NC}"
echo -e "${GREY}    (clés USB, disques durs externes, etc.)${NC}"
echo ""
echo -ne "${BOLD}${YELLOW}Appuyez sur Entrée une fois tous les périphériques débranchés...${NC}"
read -r

# Demonter tout ce qui pourrait rester dans /stockage
sudo mkdir -p "$STOCKAGE_DIR" 2>/dev/null || true
while IFS= read -r -d '' dir; do
    if mountpoint -q "$dir" 2>/dev/null; then
        DEVICE=$(mount | grep " ${dir} " | awk '{print $1}' | head -n 1 || true)
        echo -e "${YELLOW}Démontage de $dir...${NC}"
        sudo umount "$dir" 2>/dev/null || sudo umount -l "$dir" 2>/dev/null || true
        if [ -n "$DEVICE" ] && [ -b "$DEVICE" ]; then
            sudo blockdev --setrw "$DEVICE" 2>/dev/null || true
        fi
        sudo rmdir "$dir" 2>/dev/null || true
    fi
done < <(find "$STOCKAGE_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

# Nettoyage des dossiers vides residuels
while IFS= read -r -d '' dir; do
    [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ] && sudo rmdir "$dir" 2>/dev/null
done < <(find "$STOCKAGE_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)
echo -e "${GREEN}✅ /stockage nettoyé.${NC}"
echo ""

# --- Etape 2 : brancher le peripherique avec les bases ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 2 : Branchement du périphérique       ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Branchez maintenant le périphérique USB contenant les bases ClamAV.${NC}"
echo -e "${GREY}    (fichiers bytecode.cvd, daily.cvd, main.cvd à la racine ou dans un sous-dossier)${NC}"
echo ""
echo -e "${BOLD}${YELLOW}Appuyez sur Entrée une fois le périphérique branché...${NC}"
read -r

echo -e "${GREY}    Attente de la détection du périphérique (8 secondes)...${NC}"
sleep 8

# --- Etape 3 : detection du peripherique USB ---
echo ""
echo -e "${BLUE}=== Détection des périphériques USB ===${NC}"
echo -e "${YELLOW}Recherche des périphériques USB/Disques...${NC}"

declare -A USB_DEVICES
declare -A PARENT_TRAN
declare -A PARENT_MODEL
DEVICE_NUM=0

LSBLK_OUT=$(lsblk -P -o NAME,TYPE,PKNAME,MOUNTPOINT,TRAN,RM,SIZE,MODEL 2>/dev/null || true)

while IFS= read -r line; do
    eval "$line"
    if [ "$TYPE" = "disk" ]; then
        PARENT_TRAN["$NAME"]="$TRAN"
        PARENT_MODEL["$NAME"]="$MODEL"
    fi
done <<< "$LSBLK_OUT"

while IFS= read -r line; do
    eval "$line"
    if [ "$TYPE" = "part" ] && [ -z "$MOUNTPOINT" ] && [ -n "$PKNAME" ]; then
        PT=${PARENT_TRAN["$PKNAME"]:-}
        MODEL=${PARENT_MODEL["$PKNAME"]:-}
        if [ "$PT" = "usb" ] || [ "$RM" = "1" ]; then
            USB_DEVICES[$DEVICE_NUM]="$NAME|$SIZE|$MODEL"
            DEVICE_NUM=$((DEVICE_NUM + 1))
        fi
    fi
done <<< "$LSBLK_OUT"

if [ "$DEVICE_NUM" -eq 0 ]; then
    echo -e "${RED}❌ Aucun périphérique USB/Disque non monté détecté.${NC}"
    echo -e "${YELLOW}    Vérifiez que le périphérique est bien branché et reconnu par le système.${NC}"
    echo -e "${YELLOW}    (lsblk doit le lister ; sinon, problème matériel ou de port USB)${NC}"
    fail "Aucun périphérique USB détecté."
fi

# --- Affichage des peripheriques ---
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Périphériques disponibles                   ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
for i in "${!USB_DEVICES[@]}"; do
    IFS='|' read -r DEVICE_NAME DEVICE_SIZE DEVICE_MODEL <<< "${USB_DEVICES[$i]}"
    echo -e "  ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD}/dev/$DEVICE_NAME${NC}  ${GREY}• Taille:${NC} ${BOLD}$DEVICE_SIZE${NC}  ${GREY}• Modèle:${NC} ${BOLD}$DEVICE_MODEL${NC}"
done
echo ""

# --- Selection du peripherique ---
while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le numéro du périphérique contenant les bases (ou \"q\" pour quitter) : ${NC}"
    read -r SELECTED_NUM

    if [ "$SELECTED_NUM" = "q" ]; then
        echo -e "${YELLOW}Annulé.${NC}"
        final_pause
        exit 0
    fi

    if ! [[ "$SELECTED_NUM" =~ ^[0-9]+$ ]] || [ "$SELECTED_NUM" -lt 1 ] || [ "$SELECTED_NUM" -gt "$DEVICE_NUM" ]; then
        echo -e "${RED}❌ Numéro invalide. Entrez un numéro entre 1 et $DEVICE_NUM.${NC}"
        continue
    fi

    SELECTED_INDEX=$((SELECTED_NUM-1))
    IFS='|' read -r SELECTED_DEVICE DEVICE_SIZE DEVICE_MODEL <<< "${USB_DEVICES[$SELECTED_INDEX]}"
    DEVICE_PATH="/dev/$SELECTED_DEVICE"
    break
done

# --- Etape 4 : montage en lecture seule ---
MOUNT_POINT="$STOCKAGE_DIR/${SELECTED_DEVICE}"
echo -e "\n${YELLOW}Montage de ${GREEN}$DEVICE_PATH${YELLOW} dans $MOUNT_POINT (lecture seule)...${NC}"

sudo mkdir -p "$MOUNT_POINT" 2>/dev/null || fail "Impossible de créer le point de montage $MOUNT_POINT."

# Forcer le RO au niveau block device
if command -v blockdev >/dev/null 2>&1; then
    sudo blockdev --setro "$DEVICE_PATH" 2>/dev/null || echo -e "${YELLOW}⚠️  blockdev --setro a échoué (non bloquant).${NC}"
fi

# Determiner les options de montage
FSTYPE=$(lsblk -no FSTYPE "$DEVICE_PATH" 2>/dev/null || echo "")
MOUNT_OPTS="-o ro,noexec,nosuid,nodev,noatime"
case "$FSTYPE" in
    fat32|vfat) MOUNT_OPTS="$MOUNT_OPTS,utf8=true" ;;
    ext3|ext4)  MOUNT_OPTS="$MOUNT_OPTS,noload" ;;
    ntfs)       MOUNT_OPTS="$MOUNT_OPTS" ;;
    exfat)      MOUNT_OPTS="$MOUNT_OPTS" ;;
esac

if ! sudo mount $MOUNT_OPTS "$DEVICE_PATH" "$MOUNT_POINT" 2>/dev/null; then
    echo -e "${RED}❌ Échec du montage de $DEVICE_PATH.${NC}"
    sudo mount $MOUNT_OPTS "$DEVICE_PATH" "$MOUNT_POINT" 2>&1 || true
    sudo blockdev --setrw "$DEVICE_PATH" 2>/dev/null || true
    sudo rmdir "$MOUNT_POINT" 2>/dev/null || true
    fail "Échec du montage."
fi

echo -e "${GREEN}✅ Périphérique monté en lecture seule : $DEVICE_PATH → $MOUNT_POINT${NC}"
echo ""

# --- Etape 5 : recherche des fichiers .cvd ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 5 : Recherche des bases              ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Recherche des fichiers : ${BOLD}${CVD_FILES[*]}${NC}"
echo ""

FOUND_FILES=()
for cvd in "${CVD_FILES[@]}"; do
    FOUND_PATH=$(find "$MOUNT_POINT" -maxdepth 3 -type f -iname "$cvd" 2>/dev/null | head -n 1 || true)
    if [ -n "$FOUND_PATH" ]; then
        FILE_SIZE=$(ls -lh "$FOUND_PATH" 2>/dev/null | awk '{print $5}')
        echo -e "  ${GREEN}✅ ${BOLD}$cvd${NC} ${GREEN}trouvé :${NC} ${GREY}${FOUND_PATH}${NC} ${GREY}(${BOLD}${FILE_SIZE}${NC}${GREY})${NC}"
        FOUND_FILES+=("$cvd|$FOUND_PATH")
    else
        echo -e "  ${RED}❌ ${BOLD}$cvd${NC} ${RED}non trouvé${NC}"
    fi
done

if [ "${#FOUND_FILES[@]}" -eq 0 ]; then
    echo ""
    echo -e "${RED}❌ Aucun fichier de base ClamAV trouvé sur le périphérique.${NC}"
    echo -e "${YELLOW}    Vérifiez que les fichiers bytecode.cvd, daily.cvd, main.cvd${NC}"
    echo -e "${YELLOW}    sont présents sur le périphérique USB (racine ou sous-dossier).${NC}"

    # Demonter avant de quitter
    sudo umount "$MOUNT_POINT" 2>/dev/null || sudo umount -l "$MOUNT_POINT" 2>/dev/null || true
    sudo blockdev --setrw "$DEVICE_PATH" 2>/dev/null || true
    sudo rmdir "$MOUNT_POINT" 2>/dev/null || true
    fail "Aucune base ClamAV trouvée sur le périphérique."
fi

echo ""
echo -e "${GREEN}${BOLD}${#FOUND_FILES[@]}${NC}${GREEN} fichier(s) de base trouvés.${NC}"
echo ""

# --- Etape 6 : copie des fichiers dans le DatabaseDirectory ClamAV ---
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Étape 6 : Copie des bases vers ClamAV       ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Copie des fichiers vers $DB_DIR...${NC}"
echo ""

COPIED=0
for entry in "${FOUND_FILES[@]}"; do
    CVD_NAME="${entry%%|*}"
    CVD_PATH="${entry#*|}"
    echo -e "${YELLOW}Copie de ${BOLD}$CVD_NAME${NC}${YELLOW}...${NC}"
    sudo cp "$CVD_PATH" "$DB_DIR/$CVD_NAME" 2>/dev/null && {
        sudo chown clamav:clamav "$DB_DIR/$CVD_NAME" 2>/dev/null || true
        sudo chmod 644 "$DB_DIR/$CVD_NAME" 2>/dev/null || true
        echo -e "  ${GREEN}✅ $CVD_NAME copié vers $DB_DIR/${CVD_NAME}${NC}"
        COPIED=$((COPIED + 1))
    } || {
        echo -e "  ${RED}❌ Échec de la copie de $CVD_NAME${NC}"
        ERRORS=$((ERRORS + 1))
    }
done

echo ""

# --- Etape 7 : demontage du peripherique ---
echo -e "${BLUE}=== Démontage du périphérique ===${NC}"
sudo umount "$MOUNT_POINT" 2>/dev/null || sudo umount -l "$MOUNT_POINT" 2>/dev/null || true
sleep 1
sudo rmdir "$MOUNT_POINT" 2>/dev/null || true

# Rebloquer le peripherique en RO puis remettre en RW (etat propre)
if [ -b "$DEVICE_PATH" ]; then
    sudo blockdev --setrw "$DEVICE_PATH" 2>/dev/null || true
    echo -e "${GREEN}✅ Périphérique démonté, block device remis en lecture/écriture.${NC}"
fi

echo ""

# --- Etape 8 : test EICAR ---
if [ "$COPIED" -gt 0 ]; then
    echo -e "${BLUE}=== Test sur signature EICAR ===${NC}"
    EICAR='WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo='
    EICAR_TMP=$(mktemp 2>/dev/null || echo "/tmp/vigil_eicar_$$.tmp")
    echo "$EICAR" | base64 -d > "$EICAR_TMP" 2>/dev/null
    clamscan --no-summary --infected "$EICAR_TMP" >"${EICAR_TMP}.out" 2>&1
    EICAR_RC=$?
    EICAR_OUT=$(cat "${EICAR_TMP}.out" 2>/dev/null)
    rm -f "$EICAR_TMP" "${EICAR_TMP}.out" 2>/dev/null
    if [ "$EICAR_RC" = "1" ] || echo "$EICAR_OUT" | grep -qi "eicar\|FOUND"; then
        echo -e "${GREEN}✅ Test EICAR réussi : ClamAV détecte correctement les signatures.${NC}"
    else
        echo -e "${RED}❌ Le test EICAR a échoué : les bases virales pourraient être incorrectes.${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
fi

# --- Etat des bases ---
echo -e "${BLUE}=== État des bases ===${NC}"
clamscan --version 2>/dev/null || true
[ -d "$DB_DIR" ] && ls -lh "$DB_DIR"/*.cvd "$DB_DIR"/*.cld 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || true

echo ""
echo -e "${YELLOW}⚠️  Vous pouvez maintenant débrancher le périphérique USB.${NC}"

final_pause
