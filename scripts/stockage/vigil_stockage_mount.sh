#!/bin/bash
set -uo pipefail

# --- Montage d'un peripherique de stockage dans /stockage (lecture/ecriture) ---
#
# Ce script monte un peripherique USB/Disque selectionne dans /stockage. Comme
# vigil_usb_mount.sh, il detecte les disques et leurs partitions et permet de
# monter un disque entier (toutes ses partitions) sous /stockage/<disk>/<part>.
# Il est destine au STOCKAGE de fichiers de travail, PAS a l'analyse forensique
# (montage en lecture/ecriture). Pour analyser un peripherique, utilisez plutot
# le menu "Analyse USB / Disque Dur / CD" (vigil_usb_mount.sh) qui monte en RO.

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

# --- Contexte actif (utilisateur + projet) : non bloquant pour le stockage ---
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
    [ "$ACTIVE_PROJECT" = "(no-project)" ] && return
    local timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Device:$device | File:$file_path | Status:$status | Message:$message"

    echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true

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
        | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
    fi
}

mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || true

# --- Lister les points de montage réels sous /stockage (récursif) ---
# Les montages multi-partitions sont imbriqués (/stockage/<disk>/<part>).
# /proc/mounts est la source de vérité du noyau ; fallback lsblk (lit /sys).
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
        echo -e "${RED}✗ Choix invalide.${NC}"
    done
    printf '%s' "$ACTIVE_USER" > "$ACTIVE_USER_FILE" 2>/dev/null || true
}

select_active_user

# --- Nettoyer l'ecran ---
clear
print_banner
if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    echo -e "${BLUE}Projet : (aucun)${NC}"
else
    echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
fi
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo ""
echo -e "${YELLOW}⚠️  ATTENTION : montage en lecture/écriture.${NC}"
echo ""

# --- 0. Demontage automatique des peripheriques existants dans /stockage ---
echo -e "${YELLOW}Nettoyage des montages existants dans $STOCKAGE_DIR...${NC}"
sudo mkdir -p "$STOCKAGE_DIR" 2>/dev/null || true
while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    echo -e "${YELLOW}Démontage de $dir...${NC}"
    sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null && {
        echo -e "${GREEN}✅ $dir démonté et nettoyé.${NC}"
        log_action "auto_umount_stockage" "" "$dir" "success" "Démontage automatique avant nouveau montage"
    }
done < <(list_mounts_under_stockage)

# Vérifier qu'aucun peripherique n'est plus monté
REMAINING_MOUNTS=0
while IFS= read -r dir; do
    [ -n "$dir" ] && {
        REMAINING_MOUNTS=$((REMAINING_MOUNTS + 1))
        echo -e "${YELLOW}⚠️  $dir est toujours monté.${NC}"
    }
done < <(list_mounts_under_stockage)
if [ "$REMAINING_MOUNTS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Certains périphériques sont encore montés. Nouvelle tentative (lazy umount)...${NC}"
    while IFS= read -r dir; do
        [ -n "$dir" ] && sudo umount -l "$dir" 2>/dev/null || true
    done < <(list_mounts_under_stockage)
    log_action "auto_umount_all_stockage" "" "$STOCKAGE_DIR" "warning" "Démontage lazy appliqué sur restes"
fi

# Nettoyage des dossiers vides residuels
while IFS= read -r -d '' dir; do
    [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ] && sudo rmdir "$dir" 2>/dev/null
done < <(find "$STOCKAGE_DIR" -mindepth 1 -depth -type d -print0 2>/dev/null)
echo -e "${GREEN}✅ Nettoyage initial terminé.${NC}"

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

usb_snapshot() {
    # Format : busnum:devnum|port|vid|pid|manufacturer|product|serial
    # "port" = chemin sysfs (ex. 1-2, 2-1.3) : STABLE au rebranchement sur
    # le meme port physique — utilisé pour ne jamais bloquer un périphérique
    # de travail (clavier, souris) déjà présent à la baseline.
    local dir busnum devnum vid pid mfr prod ser
    for dir in /sys/bus/usb/devices/*; do
        [ -d "$dir" ] || continue
        case "${dir##*/}" in *:*) continue ;; esac
        busnum=$(cat "$dir/busnum" 2>/dev/null)
        devnum=$(cat "$dir/devnum" 2>/dev/null)
        [ -z "$busnum" ] && continue
        vid=$(cat "$dir/idVendor" 2>/dev/null || echo "?")
        pid=$(cat "$dir/idProduct" 2>/dev/null || echo "?")
        mfr=$(cat "$dir/manufacturer" 2>/dev/null || echo "")
        prod=$(cat "$dir/product" 2>/dev/null || echo "")
        ser=$(cat "$dir/serial" 2>/dev/null || echo "")
        echo "${busnum}:${devnum}|${dir##*/}|${vid}|${pid}|${mfr}|${prod}|${ser}"
    done
}

# Interfaces HID clavier du périphérique : chemins d'interface
# bInterfaceClass=03 (HID) bInterfaceSubClass=01 (clavier).
usb_hid_keyboard_ifaces() {
    local devdir="$1" iface cls sub
    for iface in "$devdir"/*/; do
        [ -d "$iface" ] || continue
        case "${iface%/}" in
            *:*) ;;
            *) continue ;;
        esac
        cls=$(cat "$iface/bInterfaceClass" 2>/dev/null)
        sub=$(cat "$iface/bInterfaceSubClass" 2>/dev/null)
        if [ "${cls:-}" = "03" ] && [ "${sub:-}" = "01" ]; then
            printf '%s\n' "$iface"
        fi
    done
}

TRIAGE_DIR=$(mktemp -d -t "vigil_triage_stockage_XXXXXXXX")
HID_LISTING=()
HID_NEW_COUNT=0
HID_ALERT_COUNT=0
HID_PROTECTED_COUNT=0
HID_BLOCKED_PORTS=()
BL_COUNT=0

run_usb_triage() {
    local base_file after_file new_file hid_file prot_file
    local line busdev port vid pid mfr prod ser devdir b d
    local baseline_count after_count new_count blocked unblockable protected
    base_file="$TRIAGE_DIR/usb_baseline.txt"
    after_file="$TRIAGE_DIR/usb_after.txt"
    new_file="$TRIAGE_DIR/usb_new.txt"
    hid_file="$TRIAGE_DIR/usb_hid.txt"
    prot_file="$TRIAGE_DIR/usb_protected.txt"

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Triage USB (détection Rubber Ducky)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Pour sécuriser le montage, DÉBRANCHEZ tous les périphériques USB${NC}"
    echo -e "${YELLOW}    à brancher (clé, disque...) avant de continuer.${NC}"
    echo ""
    echo -ne "${BOLD}${YELLOW}Débranchez les périphériques USB, puis appuyez sur Entrée...${NC}"
    read -r

    usb_snapshot > "$base_file"
    baseline_count=$(grep -cve '^[[:space:]]*$' "$base_file" 2>/dev/null)
    baseline_count=${baseline_count:-0}
    echo -e "${GREEN}✅ Baseline USB enregistrée : $baseline_count périphérique(s) présents.${NC}"
    log_action "usb_triage_stockage" "" "$base_file" "success" "Baseline USB : $baseline_count périphérique(s)"

    echo ""
    echo -e "${YELLOW}BRANCHEZ maintenant les périphériques USB à monter.${NC}"
    echo ""
    echo -ne "${BOLD}${YELLOW}Branchez tous les périphériques à monter, puis appuyez sur Entrée...${NC}"
    read -r

    # Attente de la détection noyau : 10 s avec barre de progression.
    # Le tampon clavier est purgé pendant l'attente : des Entrées tapées
    # pendant le décompte ne doivent PAS être réutilisées plus tard comme
    # réponse à un prompt (bug des doubles Entrée).
    echo -e "${BLUE}Attente de la détection par le noyau (10 s)...${NC}"
    local _total=10 _elapsed=0 _fill=""
    while [ "$_elapsed" -lt "$_total" ]; do
        _fill=""
        for (( _k=0; _k<_elapsed; _k++ )); do _fill="${_fill}#"; done
        printf "\r  ${BLUE}[%-10s] %d s${NC}" "$_fill" "$_elapsed"
        # Purge du tampon clavier (Entrées anticipées)
        while IFS= read -r -t 0.05 < /dev/tty 2>/dev/null; do :; done
        sleep 1
        _elapsed=$((_elapsed + 1))
    done
    printf "\r  ${BLUE}[%-10s] %d s${NC}\n" "##########" "$_total"

    usb_snapshot > "$after_file"
    after_count=$(grep -cve '^[[:space:]]*$' "$after_file" 2>/dev/null)
    after_count=${after_count:-0}

    clear
    print_banner
    echo -e "${GREEN}✅ $after_count périphérique(s) USB détecté(s) au total.${NC}"

    : > "$new_file"
    # Whitelist de sécurité : un périphérique DÉJÀ VU à la baseline (même port
    # physique ou même numéro de série) n'est JAMAIS bloqué, même s'il expose
    # une interface clavier. Objectif : ne jamais bloquer le clavier et la
    # souris de travail du poste, même s'ils sont rebranchés pendant le triage.
    awk -F'|' 'NR > 0 { print $2 }' "$base_file" | sort -u > "$TRIAGE_DIR/base_ports.txt"
    awk -F'|' 'NR > 0 && $7 != "" { print $7 }' "$base_file" | sort -u > "$TRIAGE_DIR/base_serials.txt"
    while IFS='|' read -r busdev port vid pid mfr prod ser; do
        [ -z "$busdev" ] && continue
        if grep -qxF "$port" "$TRIAGE_DIR/base_ports.txt" 2>/dev/null; then
            continue
        fi
        if [ -n "$ser" ] && grep -qxF "$ser" "$TRIAGE_DIR/base_serials.txt" 2>/dev/null; then
            continue
        fi
        echo "${busdev}|${port}|${vid}|${pid}|${mfr}|${prod}|${ser}" >> "$new_file"
    done < "$after_file"

    new_count=$(grep -cve '^[[:space:]]*$' "$new_file" 2>/dev/null)
    new_count=${new_count:-0}
    HID_NEW_COUNT=$new_count
    HID_ALERT_COUNT=0
    HID_PROTECTED_COUNT=0
    HID_BLOCKED_PORTS=()
    HID_LISTING=()
    : > "$hid_file"

    # Détection HID clavier des nouveaux périphériques NON whitelistés
    # + blocage des frappes. BLOCAGE PAR DÉFAUT : tout clavier HID apparu au
    # branchement est bloqué sans confirmation. Le clavier/souris de travail
    # restés branchés à la baseline sont whitelistés ; un clavier
    # débranché/rebranché doit être ajouté à la whitelist via la GUI USB
    # (Accueil > Configuration > Périphériques USB).
    blocked=0
    unblockable=0
    protected=0
    BL_COUNT=0
    : > "$prot_file"
    while IFS='|' read -r busdev port vid pid mfr prod ser; do
        [ -z "$busdev" ] && continue
        devdir="/sys/bus/usb/devices/$port"
        [ -d "$devdir" ] || continue
        _vidpid="$vid:$pid"
        if grep -qxF "$_vidpid" "$USB_BLACKLIST_FILE" 2>/dev/null \
           || { [ -n "$ser" ] && grep -qxF "$ser" "$USB_BLACKLIST_FILE" 2>/dev/null; }; then
            # Blacklist : blocage total, quel que soit le type du périphérique.
            while IFS= read -r iface; do
                [ -z "$iface" ] && continue
                ifname="${iface%/}"
                ifname="${ifname##*/}"
                echo "$ifname" | sudo tee "/sys/bus/usb/drivers/usbhid/unbind" >/dev/null 2>&1 || true
            done < <(usb_hid_keyboard_ifaces "$devdir")
            if echo 0 | sudo tee "$devdir/authorized" >/dev/null 2>&1; then
                echo -e "${RED}🚨 Périphérique blacklisté bloqué :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${YELLOW}— non montable (blacklist)${NC}"
            else
                echo -e "${RED}🚨 Périphérique blacklisté détecté :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${RED}— ÉCHEC du blocage, DÉBRANCHEZ-LE${NC}"
            fi
            log_action "usb_triage_hid_stockage" "" "$devdir" "alert" "Périphérique blacklisté : ${mfr:-?} ${prod:-?} ($vid:$pid) — blocage appliqué"
            HID_BLOCKED_PORTS+=("$port")
            echo "${busdev}|${vid}|${pid}|${mfr}|${prod}|${ser}" >> "$hid_file"
            BL_COUNT=$((BL_COUNT + 1))
            continue
        fi
        if [ -n "$(usb_hid_keyboard_ifaces "$devdir")" ]; then
            if grep -qxF "$_vidpid" "$USB_WHITELIST_FILE" 2>/dev/null \
               || { [ -n "$ser" ] && grep -qxF "$ser" "$USB_WHITELIST_FILE" 2>/dev/null; }; then
                protected=$((protected + 1))
                echo "$busdev" >> "$prot_file"
                echo -e "${GREEN}  ✅ Clavier HID whitelisté : ${BOLD}${mfr:-?} ${prod:-?}${NC}  ${GREY}($vid:$pid) — frappes actives (whitelist).${NC}"
                log_action "usb_triage_hid_stockage" "" "$devdir" "warning" "Clavier HID whitelisté (non bloqué) : ${mfr:-?} ${prod:-?} ($vid:$pid)"
                continue
            fi
            local _bar="" _i
            for (( _i=0; _i<66; _i++ )); do _bar="${_bar}━"; done
            echo ""
            echo -e "${RED}┏${_bar}┓${NC}"
            echo -e "${RED}┃  ⚠ PÉRIPHÉRIQUE SUSPECT DÉTECTÉ${NC}"
            echo -e "${RED}┗${_bar}┛${NC}"
            echo ""
            echo -e "  ${BOLD}Périphérique détecté :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC}  ${GREY}($vid:$pid)${NC}"
            echo -e "  ${GREY}Un périphérique de stockage ne se présente jamais comme un clavier :${NC}"
            echo -e "  ${GREY}par sécurité ses frappes sont BLOQUÉES automatiquement et il ne peut${NC}"
            echo -e "  ${GREY}pas être monté. Pour whitelister un clavier/souris de travail, utilisez${NC}"
            echo -e "  ${GREY}la GUI USB (Accueil > Configuration > Périphériques USB).${NC}"
            echo ""
            HID_ALERT_COUNT=$((HID_ALERT_COUNT + 1))
            echo "${busdev}|${vid}|${pid}|${mfr}|${prod}|${ser}" >> "$hid_file"
            HID_LISTING+=("${mfr:-?} ${prod:-?}|${vid}:${pid}|${ser:-}")
            HID_BLOCKED_PORTS+=("$port")
            # Blocage : délier le driver usbhid de chaque interface clavier
            local one_blocked=0
            while IFS= read -r iface; do
                [ -z "$iface" ] && continue
                ifname="${iface%/}"
                ifname="${ifname##*/}"
                if echo "$ifname" | sudo tee "/sys/bus/usb/drivers/usbhid/unbind" >/dev/null 2>&1; then
                    one_blocked=1
                fi
            done < <(usb_hid_keyboard_ifaces "$devdir")
            if [ "$one_blocked" -gt 0 ]; then
                blocked=$((blocked + 1))
                echo -e "${RED}🚨 Clavier HID détecté :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${YELLOW}— frappes bloquées, non montable${NC}"
                log_action "usb_triage_hid_stockage" "" "$devdir" "alert" "Clavier HID détecté et bloqué : ${mfr:-?} ${prod:-?} ($vid:$pid, série $ser)"
            else
                unblockable=$((unblockable + 1))
                echo -e "${RED}🚨 Clavier HID détecté :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${RED}— ÉCHEC du blocage, DÉBRANCHEZ-LE${NC}"
                log_action "usb_triage_hid_stockage" "" "$devdir" "alert" "Clavier HID détecté, ÉCHEC du blocage : ${mfr:-?} ${prod:-?} ($vid:$pid)"
            fi
        fi
    done < "$new_file"
    HID_PROTECTED_COUNT=$protected

    # Rapport PDF de triage (toujours généré : trace de la procédure)
    USBHID_JSON="$TRIAGE_DIR/usbhid.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    {
        printf '{"date": "%s", "baseline_count": %s, "after_count": %s, "new_count": %s, "hid_count": %s, "protected_count": %s, "blocked_count": %s, "block_fail_count": %s, "blacklisted_count": %s, "devices": [' \
            "$DATE_ANALYSIS" "$baseline_count" "$after_count" "$new_count" "$HID_ALERT_COUNT" "$protected" "$blocked" "$unblockable" "$BL_COUNT"
        first=1
        while IFS='|' read -r busdev port vid pid mfr prod ser; do
            [ -z "$busdev" ] && continue
            [ $first -eq 0 ] && printf ','
            first=0
            hidflag=false
            protflag=false
            blflag=false
            grep -q "^${busdev}|" "$hid_file" 2>/dev/null && hidflag=true
            grep -qxF "$busdev" "$prot_file" 2>/dev/null && protflag=true
            grep -qxF "${vid}:${pid}" "$USB_BLACKLIST_FILE" 2>/dev/null && blflag=true
            { [ -n "$ser" ] && grep -qxF "$ser" "$USB_BLACKLIST_FILE" 2>/dev/null; } && blflag=true
            printf '{"bus_dev": "%s", "vid": "%s", "pid": "%s", "manufacturer": "%s", "product": "%s", "serial": "%s", "hid": %s, "protected": %s, "blacklisted": %s}' \
                "$busdev" "$vid" "$pid" "$mfr" "$prod" "$ser" "$hidflag" "$protflag" "$blflag"
        done < "$new_file"
        printf ']}'
    } > "$USBHID_JSON"
    PDF_SCRIPT="$VIGIL_BASE/scripts/pdf/vigil_pdf.py"
    if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        PDF_OUT=$(python3 "$PDF_SCRIPT" --kind usbhid --json "$USBHID_JSON" \
            --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" \
            --dir "$VIGIL_BASE/rapports" --config-dir "$VIGIL_DATA_DIR" 2>&1)
        if [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
            echo -e "${GREEN}✅ Rapport de triage USB généré : $PDF_OUT${NC}"
            log_action "usb_triage_pdf_stockage" "" "$PDF_OUT" "success" "Rapport de triage USB généré (stockage)"
            if [ "$ACTIVE_PROJECT" != "(no-project)" ] && [ -d "$PROJECT_LOG_DIR" ] && [ -w "$PROJECT_LOG_DIR" ]; then
                cp -f "$PDF_OUT" "$PROJECT_LOG_DIR/" 2>/dev/null || true
            fi
        else
            echo -e "${YELLOW}⚠️  Échec de la génération du rapport de triage PDF.${NC}"
            log_action "usb_triage_pdf_stockage" "" "" "warning" "Échec de la génération du PDF de triage (stockage)"
        fi
    fi
    if [ "$HID_ALERT_COUNT" -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Aucun clavier HID détecté parmi les $new_count nouveau(x) périphérique(s).${NC}"
    fi
    log_action "usb_triage_stockage" "" "$after_file" "success" "Triage terminé : $new_count nouveau(x), $HID_ALERT_COUNT HID clavier, $protected protégé(s), $blocked bloqué(s)"

    # Si le SEUL périphérique apparu est un clavier suspect bloqué ou un
    # périphérique blacklisté, il n'y a rien à monter : le rapport PDF de
    # triage vient d'être généré, on termine proprement le script.
    _usb_storage_count=0
    while IFS= read -r _dsk; do
        [ -z "$_dsk" ] && continue
        _syslink=$(readlink -f "/sys/block/${_dsk}" 2>/dev/null || echo "")
        _skip=0
        for _bport in ${HID_BLOCKED_PORTS[@]+"${HID_BLOCKED_PORTS[@]}"}; do
            case "$_syslink" in
                */"$_bport"/*|*/"$_bport")
                    _skip=1
                    break
                    ;;
            esac
        done
        [ "$_skip" -eq 1 ] && continue
        _usb_storage_count=$((_usb_storage_count + 1))
    done < <(lsblk -rpn -o NAME,TYPE,TRAN,RM 2>/dev/null \
        | awk '$2=="disk" && ($3=="usb" || $4=="1") {print $1}')
    _usb_storage_count=${_usb_storage_count:-0}
    if [ "$HID_ALERT_COUNT" -gt 0 ] \
       && [ "$new_count" -eq "$HID_ALERT_COUNT" ] \
       && [ "$blocked" -gt 0 ] \
       && [ "$unblockable" -eq 0 ] \
       && [ "$_usb_storage_count" -eq 0 ]; then
        echo ""
        echo -e "${RED}${BOLD}🚨 Le seul périphérique détecté est un clavier suspect (bloqué).${NC}"
        echo -e "${RED}Il ne peut pas être monté ni analysé : débranchez-le et jugez ${NC}"
        echo -e "${RED}s'il s'agit d'un clavier de travail (relancez alors le script).${NC}"
        echo -e "${GREEN}Le rapport PDF de triage a été généré (rapport_usbhid_*).${NC}"
        log_action "usb_triage_end_stockage" "" "$after_file" "alert" "Fin du montage stockage : seul périphérique détecté = clavier suspect bloqué"
        END_AFTER_TRIAGE=1
        return 0
    fi
    if [ "$BL_COUNT" -gt 0 ] \
       && [ "$new_count" -eq "$BL_COUNT" ] \
       && [ "$_usb_storage_count" -eq 0 ]; then
        echo ""
        echo -e "${RED}${BOLD}🚨 Le seul périphérique détecté est BLACKLISTÉ (bloqué).${NC}"
        echo -e "${RED}Il ne peut pas être monté ni analysé. Pour l'autoriser à nouveau,${NC}"
        echo -e "${RED}retirez-le de la blacklist (Accueil > Configuration > Périphériques USB).${NC}"
        echo -e "${GREEN}Le rapport PDF de triage a été généré (rapport_usbhid_*).${NC}"
        log_action "usb_triage_end_stockage" "" "$after_file" "alert" "Fin du montage stockage : seul périphérique détecté = blacklisté bloqué"
        END_AFTER_TRIAGE=1
        return 0
    fi
}

END_AFTER_TRIAGE=0
run_usb_triage
if [ "$END_AFTER_TRIAGE" -eq 1 ]; then
    final_pause
    exit 0
fi

# --- 0.5. Autorisation des peripheriques USB bloques (authorized=0) ---
authorize_blocked_usb() {
    if [ ! -d /sys/bus/usb/devices ]; then
        return 0
    fi
    local found=0
    local authfile devpath state prod mfr _port _skip _vid _pid2 _ser2
    for authfile in /sys/bus/usb/devices/*/authorized; do
        [ -f "$authfile" ] || continue
        devpath="${authfile%/authorized}"
        _port="${devpath##*/}"
        # Ne JAMAIS ré-autoriser un périphérique bloqué au triage (ducky ou
        # blacklisté) : le blocage authorized=0 doit survivre au retry.
        _skip=0
        for _bport in ${HID_BLOCKED_PORTS[@]+"${HID_BLOCKED_PORTS[@]}"}; do
            [ "$_bport" = "$_port" ] && { _skip=1; break; }
        done
        if [ "$_skip" -eq 0 ]; then
            # Idem pour la blacklist persistante : un périphérique blacklisté
            # (même bloqué lors d'un montage précédent) reste bloqué.
            _vid=$(cat "$devpath/idVendor" 2>/dev/null || echo "")
            _pid2=$(cat "$devpath/idProduct" 2>/dev/null || echo "")
            _ser2=$(cat "$devpath/serial" 2>/dev/null || echo "")
            if grep -qxF "${_vid}:${_pid2}" "$USB_BLACKLIST_FILE" 2>/dev/null \
               || { [ -n "$_ser2" ] && grep -qxF "$_ser2" "$USB_BLACKLIST_FILE" 2>/dev/null; }; then
                _skip=1
            fi
        fi
        [ "$_skip" -eq 1 ] && continue
        state=$(cat "$authfile" 2>/dev/null || echo "")
        if [ "$state" = "0" ]; then
            if [ "$found" -eq 0 ]; then
                echo -e "${YELLOW}Réparation des périphériques USB bloqués (authorized=0)...${NC}"
            fi
            found=1
            devpath="${authfile%/authorized}"
            prod=$(cat "$devpath/product" 2>/dev/null || echo "?")
            mfr=$(cat "$devpath/manufacturer" 2>/dev/null || echo "?")
            if echo 1 | sudo tee "$authfile" >/dev/null 2>&1; then
                echo -e "  ${GREEN}✅ Autorisé :${NC} ${GREY}${mfr} / ${prod}${NC}"
            else
                echo -e "  ${RED}❌ Échec d'autorisation :${NC} ${GREY}${mfr} / ${prod}${NC}"
            fi
        fi
    done
    if [ "$found" -eq 1 ]; then
        echo -e "${YELLOW}    Attente de la reconnaissance par le noyau...${NC}"
        udevadm settle --timeout=10 2>/dev/null || sleep 2
        sleep 1
    fi
    return $found
}

# --- Helper : FSTYPE|LABEL|PARTTYPENAME ---
_fs_label_parttype() {
    local dev="$1"
    local fs lbl pt
    fs=$(lsblk -no FSTYPE "$dev" 2>/dev/null | head -n1 | tr -d '[:space:]')
    if [ -z "$fs" ] && command -v blkid >/dev/null 2>&1; then
        fs=$(blkid -o value -s TYPE "$dev" 2>/dev/null | head -n1 | tr -d '[:space:]')
    fi
    lbl=$(lsblk -no LABEL "$dev" 2>/dev/null | head -n1)
    if [ -z "$lbl" ] && command -v blkid >/dev/null 2>&1; then
        lbl=$(blkid -o value -s LABEL "$dev" 2>/dev/null | head -n1)
    fi
    pt=$(lsblk -no PARTTYPENAME "$dev" 2>/dev/null | head -n1)
    fs=${fs:-}
    lbl=${lbl# }; lbl=${lbl% }
    pt=${pt# }; pt=${pt% }
    echo "$fs|$lbl|$pt"
}

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
    local fstype mount_opts
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
        fat32|vfat) mount_opts="$mount_opts,utf8=true,flush" ;;
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
            if command -v mount.exfat >/dev/null 2>&1; then
                mount_opts="-t exfat -o rw,nosuid,nodev,uid=$(id -u),gid=$(id -g)"
            fi
            ;;
    esac
    if ! sudo mount $mount_opts "$dev" "$mnt" 2>/dev/null; then
        echo -e "${RED}❌ Échec du montage de $dev → $mnt${NC}"
        sudo mount $mount_opts "$dev" "$mnt" 2>&1 || true
        log_action "mount_stockage" "$dev" "$mnt" "failed" "Échec du montage"
        sudo rmdir "$mnt" 2>/dev/null || true
        return 1
    fi
    sudo chown -R "$USER:$USER" "$mnt" 2>/dev/null || true
    echo -e "${GREEN}✅ ${NC}${BOLD}$dev${NC}${GREEN} → $mnt${NC}"
    log_action "mount_stockage" "$dev" "$mnt" "success" "Périphérique monté en lecture/écriture"
    return 0
}

# --- 1. Detection des peripheriques USB/Disques ---
detect_usb_devices() {
    declare -gA USB_DEVICES
    declare -gA PARENT_TRAN
    declare -gA PARENT_MODEL
    declare -gA PARENT_SIZE
    declare -gA DISK_PARTS
    declare -gA DISK_PARTCOUNT
    DEVICE_NUM=0
    USB_DEVICES=()
    PARENT_TRAN=()
    PARENT_MODEL=()
    PARENT_SIZE=()
    DISK_PARTS=()
    DISK_PARTCOUNT=()
    MOUNTED_NUM=0
    MOUNTED_USB=()

    local LSBLK_OUT line NAME TYPE PKNAME MOUNTPOINT TRAN RM SIZE MODEL PT FSTYPE LABEL PARTTYPE
    LSBLK_OUT=$(lsblk -P -o NAME,TYPE,PKNAME,MOUNTPOINT,TRAN,RM,SIZE,MODEL 2>/dev/null || true)

    while IFS= read -r line; do
        eval "$line"
        if [ "$TYPE" = "disk" ]; then
            PARENT_TRAN["$NAME"]="$TRAN"
            PARENT_MODEL["$NAME"]="$MODEL"
            PARENT_SIZE["$NAME"]="$SIZE"
        fi
    done <<< "$LSBLK_OUT"

    while IFS= read -r line; do
        eval "$line"
        if [ "$TYPE" = "part" ] && [ -n "$PKNAME" ]; then
            PT=${PARENT_TRAN["$PKNAME"]:-}
            MODEL=${PARENT_MODEL["$PKNAME"]:-}
            if [ "$PT" = "usb" ] || [ "$RM" = "1" ]; then
                if [ -z "$MOUNTPOINT" ]; then
                    IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
                    if [ -n "$FSTYPE" ]; then
                        USB_DEVICES[$DEVICE_NUM]="part|$NAME|$SIZE|$MODEL|$FSTYPE|$LABEL|$PARTTYPE|$PKNAME"
                        DEVICE_NUM=$((DEVICE_NUM + 1))
                        DISK_PARTS["$PKNAME"]="${DISK_PARTS["$PKNAME"]:-}$NAME "
                        DISK_PARTCOUNT["$PKNAME"]=$((${DISK_PARTCOUNT["$PKNAME"]:-0} + 1))
                    fi
                else
                    MOUNTED_USB[$MOUNTED_NUM]="$NAME|$MOUNTPOINT|$SIZE|$MODEL"
                    MOUNTED_NUM=$((MOUNTED_NUM + 1))
                fi
            fi
        fi
    done <<< "$LSBLK_OUT"

    # Insertion « Monter tout le disque » pour chaque disque USB >= 2 partitions
    if [ "${#DISK_PARTS[@]}" -gt 0 ]; then
        local _new_list=()
        for i in "${!USB_DEVICES[@]}"; do _new_list+=("${USB_DEVICES[$i]}"); done
        local _inserted=()
        for disk in "${!DISK_PARTS[@]}"; do
            local cnt=${DISK_PARTCOUNT["$disk"]:-0}
            if [ "$cnt" -ge 2 ]; then
                local dsize=${PARENT_SIZE["$disk"]:-?}
                local dmodel=${PARENT_MODEL["$disk"]:-?}
                _inserted+=("whole|$disk|$dsize|$dmodel|$cnt|")
            fi
        done
        USB_DEVICES=()
        DEVICE_NUM=0
        for e in "${_inserted[@]}"; do
            USB_DEVICES[$DEVICE_NUM]="$e"
            DEVICE_NUM=$((DEVICE_NUM + 1))
        done
        for e in "${_new_list[@]}"; do
            USB_DEVICES[$DEVICE_NUM]="$e"
            DEVICE_NUM=$((DEVICE_NUM + 1))
        done
    fi

    # Disques USB sans partition (filesystem direct)
    while IFS= read -r line; do
        eval "$line"
        if [ "$TYPE" = "disk" ] && [ -z "$MOUNTPOINT" ]; then
            if [ "$TRAN" = "usb" ] || [ "$RM" = "1" ]; then
                if ! echo "$LSBLK_OUT" | grep -q "PKNAME=\"$NAME\"" 2>/dev/null; then
                    IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
                    USB_DEVICES[$DEVICE_NUM]="rawdisk|$NAME|$SIZE|$MODEL|$FSTYPE|$LABEL||"
                    DEVICE_NUM=$((DEVICE_NUM + 1))
                fi
            fi
        fi
    done <<< "$LSBLK_OUT"
}

echo ""
echo -e "${BLUE}=== Détection des périphériques ===${NC}"
echo -e "${YELLOW}Recherche des périphériques USB/Disques...${NC}"

ATTEMPT=0
MAX_ATTEMPTS=3
while [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    ATTEMPT=$((ATTEMPT + 1))
    detect_usb_devices
    if [ "$DEVICE_NUM" -gt 0 ]; then
        break
    fi
    if [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
        echo -e "${GREY}    (tentative $ATTEMPT/$MAX_ATTEMPTS : aucun périphérique, vérification des USB bloqués...)${NC}"
        authorize_blocked_usb
    fi
done

if [ "$DEVICE_NUM" -eq 0 ]; then
    echo -e "${RED}❌ Aucun périphérique USB/Disque non monté détecté.${NC}"
    if [ "$MOUNTED_NUM" -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}⚠️  ${MOUNTED_NUM} périphérique(s) USB déjà monté(s) :${NC}"
        for i in "${!MOUNTED_USB[@]}"; do
            IFS='|' read -r m_name m_mount m_size m_model <<< "${MOUNTED_USB[$i]}"
            echo -e "  ${BOLD}/dev/$m_name${NC}  ${GREY}• Monté dans :${NC} ${BOLD}$m_mount${NC}  ${GREY}• Taille :${NC} ${BOLD}$m_size${NC}"
        done
        echo ""
        echo -ne "${BOLD}${YELLOW}Démonter ces périphériques et relancer la détection ? (o/n, q pour quitter) : ${NC}"
        read -r UM_ANSWER
        if [ "$UM_ANSWER" = "q" ] || [ "$UM_ANSWER" = "Q" ]; then
            echo -e "${YELLOW}Quitter.${NC}"
            final_pause
            exit 0
            fi
        if [ "$UM_ANSWER" = "o" ] || [ "$UM_ANSWER" = "O" ] || [ "$UM_ANSWER" = "y" ] || [ "$UM_ANSWER" = "Y" ]; then
            for i in "${!MOUNTED_USB[@]}"; do
                IFS='|' read -r m_name m_mount m_size m_model <<< "${MOUNTED_USB[$i]}"
                echo -e "${YELLOW}Démontage de /dev/$m_name ($m_mount)...${NC}"
                if sudo umount "$m_mount" 2>/dev/null; then
                    echo -e "  ${GREEN}✅ /dev/$m_name démonté.${NC}"
                    log_action "umount_for_stockage" "/dev/$m_name" "$m_mount" "success" "Démonté pour stockage RW"
                else
                    echo -e "  ${RED}❌ Échec du démontage de /dev/$m_name.${NC}"
                fi
            done
            sleep 1
            detect_usb_devices
        fi
    fi
    if [ "$DEVICE_NUM" -eq 0 ]; then
        echo ""
        echo -e "${YELLOW}Diagnostic : si votre clé USB est branchée mais invisible dans lsblk :${NC}"
        echo -e "${GREY}  • Vérifiez : lsblk (la clé doit apparaître, ex. /dev/sdb)${NC}"
        echo -e "${GREY}  • Vérifiez : sudo dmesg | tail -20 (cherchez 'authorized' ou 'not authorized')${NC}"
        echo -e "${GREY}  • Vérifiez : systemctl is-enabled usbguard (doit être disabled/masked)${NC}"
        echo -e "${GREY}  • Débranchez puis rebranchez physiquement la clé${NC}"
        log_action "mount_attempt_stockage" "" "$STOCKAGE_DIR" "failed" "Aucun périphérique détecté"
        final_pause
        exit 1
    fi
fi

# --- 2. Affichage des peripheriques (regroupé par disque) ---
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Périphériques disponibles                  ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
declare -A _DISK_ORDER=()
_DISK_SEQ=()
for i in "${!USB_DEVICES[@]}"; do
    IFS='|' read -r KIND DEVICE_NAME DEVICE_SIZE DEVICE_MODEL FSTYPE LABEL PARTTYPE PKNAME <<< "${USB_DEVICES[$i]}"
    if [ "$KIND" = "part" ]; then
        _disk_key="$PKNAME"
    else
        _disk_key="$DEVICE_NAME"
    fi
    if [ -z "${_DISK_ORDER[$_disk_key]:-}" ]; then
        _DISK_ORDER[$_disk_key]="${#_DISK_SEQ[@]}"
        _DISK_SEQ+=("$_disk_key")
    fi
done
for _disk_key in ${_DISK_SEQ[@]+"${_DISK_SEQ[@]}"}; do
    _dsize=${PARENT_SIZE["$_disk_key"]:-?}
    _dmodel=${PARENT_MODEL["$_disk_key"]:-?}
    echo -e "  ${BOLD}${BLUE} Disque /dev/$_disk_key${NC}  ${GREY}• Taille:${NC} ${BOLD}$_dsize${NC}  ${GREY}• Modèle:${NC} ${BOLD}$_dmodel${NC}"
    for i in "${!USB_DEVICES[@]}"; do
        IFS='|' read -r KIND DEVICE_NAME DEVICE_SIZE DEVICE_MODEL FSTYPE LABEL PARTTYPE PKNAME <<< "${USB_DEVICES[$i]}"
        if [ "$KIND" = "part" ]; then _key="$PKNAME"; else _key="$DEVICE_NAME"; fi
        [ "$_key" != "$_disk_key" ] && continue
        if [ "$KIND" = "whole" ]; then
            echo -e "    ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD} Monter tout le disque${NC}  ${GREY}(${FSTYPE} partition(s))${NC}"
        elif [ "$KIND" = "rawdisk" ]; then
            echo -e "    ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD}/dev/$DEVICE_NAME${NC}  ${GREY}• FS:${NC} ${BOLD}${FSTYPE:-?}${NC}  ${GREY}• Taille:${NC} ${BOLD}$DEVICE_SIZE${NC}"
        else
            _partinfo="${BOLD}/dev/$DEVICE_NAME${NC}"
            [ -n "$PARTTYPE" ] && [ "$PARTTYPE" != "Linux filesystem" ] && _partinfo="$_partinfo  ${GREY}[$PARTTYPE]${NC}"
            [ -n "$LABEL" ] && _partinfo="$_partinfo  ${GREY}• Vol:${NC} ${BOLD}$LABEL${NC}"
            _partinfo="$_partinfo  ${GREY}• FS:${NC} ${BOLD}${FSTYPE:-?}${NC}  ${GREY}• Taille:${NC} ${BOLD}$DEVICE_SIZE${NC}"
            echo -e "    ${BOLD}${BLUE}[$((i+1))]${NC}  $_partinfo"
        fi
    done
    echo ""
done

# Périphériques HID détectés au triage (non montables)
if [ "$HID_ALERT_COUNT" -gt 0 ]; then
    echo ""
    echo -e "${RED}${BOLD}🚨 PÉRIPHÉRIQUE(S) SUSPECT(S) — interdits de montage :${NC}"
    _hid=""
    for _hid in ${HID_LISTING[@]+"${HID_LISTING[@]}"}; do
        IFS='|' read -r _name _vidpid _ser <<< "$_hid"
        echo -e "  ${RED}${BOLD}• ${_name}${NC}  ${GREY}(réf. ${_vidpid}, n° série ${_ser:-absent})${NC}"
    done
    echo -e "${RED}    Ces périphériques se font passer pour des claviers : leurs frappes${NC}"
    echo -e "${RED}    sont bloquées et ils ne peuvent PAS être montés. Ils sont décrits${NC}"
    echo -e "${RED}    dans le rapport PDF de triage (rapport_usbhid_*).${NC}"
fi

# --- 3. Selection du peripherique ---
while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le numéro du périphérique à monter (ou \"q\" pour quitter) : ${NC}"
    read -r SELECTED_NUM
    if [ "$SELECTED_NUM" = "q" ]; then
        echo -e "${YELLOW}Annulé.${NC}"
        log_action "mount_cancelled_stockage" "" "$STOCKAGE_DIR" "success" "Montage annulé par l'utilisateur"
        final_pause
        exit 0
    fi
    if ! [[ "$SELECTED_NUM" =~ ^[0-9]+$ ]] || [ "$SELECTED_NUM" -lt 1 ] || [ "$SELECTED_NUM" -gt "$DEVICE_NUM" ]; then
        echo -e "${RED}❌ Numéro invalide. Entrez un numéro entre 1 et $DEVICE_NUM.${NC}"
        continue
    fi
    SELECTED_INDEX=$((SELECTED_NUM-1))
    IFS='|' read -r SELECTED_KIND SELECTED_DEVICE SELECTED_SIZE SELECTED_MODEL SELECTED_FSTYPE SELECTED_LABEL SELECTED_PARTTYPE SELECTED_PKNAME <<< "${USB_DEVICES[$SELECTED_INDEX]}"
    break
done

# --- 4. Montage selon le kind d'entrée sélectionnée ---
echo -e "\n${YELLOW}Montage en lecture/écriture...${NC}"
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
