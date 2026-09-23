#!/bin/bash
set -uo pipefail

# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
GREY='\e[90m'
BOLD='\e[1m'
NC='\e[0m'

print_banner() {
    # Couleur parametrable : print_banner (bleu) ou print_banner red (rouge)
    local _bcolor="${1:-$BLUE}"
    echo -e "$_bcolor"
    cat <<'VIGILART'
█   █ ███  ███  ███ █     
█   █  █  █      █  █     
█   █  █  █  ██  █  █     
 █ █   █  █   █  █  █     
  █   ███  ███  ███ █████ 
VIGILART
    echo -e "${NC}"
}
# --- Vérifier qu'un utilisateur (obligatoire) et un projet sont actifs ---
# --- Contexte actif (utilisateur + projet) : non bloquant pour le montage ---
# Le montage est une opération matérielle utilitaire : elle doit rester
# possible même sans utilisateur/projet actifs. Si un contexte existe, on
# l'utilise pour tracer l'action dans la chaîne de custody ; sinon, on monte
# quand même et on n'écrit pas de log.
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
USB_LISTS_DIR="$VIGIL_DATA_DIR/usb"
USB_WHITELIST_FILE="$USB_LISTS_DIR/whitelist.txt"
USB_BLACKLIST_FILE="$USB_LISTS_DIR/blacklist.txt"
mkdir -p "$USB_LISTS_DIR" 2>/dev/null || true
touch "$USB_WHITELIST_FILE" "$USB_BLACKLIST_FILE" 2>/dev/null || true
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

# --- Compteur d'erreurs global et pause finale ---
# final_pause() s'assure que le terminal (Konsole) ne se ferme jamais sans
# que l'utilisateur ait lu le message d'erreur final.
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

# error_exit : affiche un message d'erreur, incrémente le compteur et pause.
# Ne quitte PAS brutalement : l'utilisateur garde la main sur le terminal.
fail() {
    echo -e "${RED}❌ $1${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

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

# Créer les dossiers de logs et d'investigation s'ils n'existent pas
mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || {
    echo -e "${RED}❌ Impossible de créer $PROJECT_LOG_DIR${NC}"
    echo -e "${YELLOW}    Vérifiez les droits d'écriture sur $VIGIL_BASE/data/projects/${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}
sudo mkdir -p /investigation 2>/dev/null || true
sudo chmod 755 /investigation 2>/dev/null || true

# --- Vérifications des privilèges et dépendances ---
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Ce script nécessite des privilèges root pour monter les périphériques.${NC}"
    echo -e "${YELLOW}    Vérifiez la configuration sudo de l'utilisateur courant.${NC}"
fi

echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING_DEPS=0
for cmd in lsblk mount find sha256sum; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING_DEPS=$((MISSING_DEPS + 1))
    fi
done
# Outils optionnels (avertissement seulement)
for cmd in jq cryptsetup clamscan jmtpfs eject blockdev; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Outil optionnel absent : $cmd (certaines fonctionnalités seront désactivées)${NC}"
    fi
done

if [ "$MISSING_DEPS" -gt 0 ]; then
    fail "Dépendances obligatoires manquantes ($MISSING_DEPS). Installez-les avant de continuer."
fi


# --- Nettoyer l'écran ---
clear
print_banner
echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
# Chasse : VIGIL_ACTIVE_USER (operateur choisi par la chasse) prioritaire
# sur le fichier actif, affiche et utilise pour la custody.
if [ -n "${VIGIL_ACTIVE_USER:-}" ]; then
    ACTIVE_USER="$VIGIL_ACTIVE_USER"
    echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
fi
echo ""

# --- 0. Démontage automatique des périphériques existants dans /investigation ---
echo -e "${YELLOW}Démontage automatique des périphériques existants dans /investigation...${NC}"
while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    echo -e "${YELLOW}Démontage de $dir...${NC}"
    sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null && {
        echo -e "${GREEN}✅ $dir démonté et nettoyé.${NC}"
        log_action "auto_umount" "" "$dir" "success" "Démontage automatique avant nouveau montage"
    }
done < <(list_mounts_under_investigation)

# Vérifier qu'aucun périphérique n'est plus monté
REMAINING_MOUNTS=0
while IFS= read -r dir; do
    [ -n "$dir" ] && {
        REMAINING_MOUNTS=$((REMAINING_MOUNTS + 1))
        echo -e "${YELLOW}⚠️  $dir est toujours monté.${NC}"
    }
done < <(list_mounts_under_investigation)

if [ "$REMAINING_MOUNTS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Certains périphériques sont encore montés. Nouvelle tentative (lazy umount)...${NC}"
    while IFS= read -r dir; do
        [ -n "$dir" ] && sudo umount -l "$dir" 2>/dev/null || true
    done < <(list_mounts_under_investigation)
    log_action "auto_umount_all" "" "/investigation" "warning" "Démontage lazy appliqué sur restes"
fi

# Nettoyage des dossiers vides résiduels
while IFS= read -r -d '' dir; do
    [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ] && sudo rmdir "$dir" 2>/dev/null
done < <(find /investigation -mindepth 1 -depth -type d -print0 2>/dev/null)

echo -e "${GREEN}✅ Nettoyage initial terminé.${NC}"
# --- 0.5. Triage USB anti-Rubber Ducky (baseline -> branchement -> HID) ---
# Procedure en deux temps :
#   1. BASELINE : l'utilisateur DEBRANCHE les peripheriques USB, valide
#      avec Entree ; Vigil memorise l'etat USB du systeme ;
#   2. BRANCHEMENT : l'utilisateur BRANCHE les peripheriques a analyser,
#      valide avec Entree ; apres un delai de detection, Vigil compare.
# Tout peripherique APPARU entre les deux avec une interface HID clavier
# (bInterfaceClass=03, sous-classe 01) est signale, BLOQUE (deliaison du
# driver usbhid : les frappes ne sont plus transmises au systeme) et
# reference dans un rapport PDF dedie. Il apparaît dans la liste des
# périphériques comme NON MONTABLE.

usb_snapshot() {
    # Format : busnum:devnum|port|vid|pid|manufacturer|product|serial
    # "port" = chemin sysfs (ex. 1-2, 2-1.3) : STABLE au rebranchement sur
    # le meme port physique — utilise pour ne jamais bloquer un peripherique
    # de travail (clavier, souris) deja present a la baseline.
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

# Interfaces HID clavier du peripherique : chemins d'interface
# bInterfaceClass=03 (HID) bInterfaceSubClass=01 (clavier).
usb_hid_keyboard_ifaces() {
    # Les interfaces sont des sous-dossiers du peripherique, nommes
    # "<bus-port>:<config>.<interface>" (ex. 1-2:1.0 pour la 1re interface).
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

TRIAGE_DIR=$(mktemp -d -t "vigil_triage_XXXXXXXX")
HID_LISTING=()
HID_NEW_COUNT=0
HID_ALERT_COUNT=0
HID_PROTECTED_COUNT=0
HID_BLOCKED_PORTS=()
BL_COUNT=0

run_usb_triage() {
    local base_file after_file new_file hid_file
    local line busdev port vid pid mfr prod ser devdir b d
    local baseline_count after_count new_count blocked unblockable protected HID_ANSWER
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
    echo -e "${YELLOW}⚠️  Pour sécuriser l'analyse, DÉBRANCHEZ tous les périphériques USB${NC}"
    echo -e "${YELLOW}    de stockage à analyser (clé, disque...) avant de continuer.${NC}"
    echo ""
    echo -ne "${BOLD}${YELLOW}Débranchez les périphériques USB, puis appuyez sur Entrée...${NC}"
    read -r
    usb_snapshot > "$base_file"
    baseline_count=$(grep -cve '^[[:space:]]*$' "$base_file" 2>/dev/null)
    baseline_count=${baseline_count:-0}
    echo -e "${GREEN}✅ Baseline USB enregistrée : $baseline_count périphérique(s) présents.${NC}"
    log_action "usb_triage" "" "$base_file" "success" "Baseline USB : $baseline_count périphérique(s)"
    echo ""
    echo -e "${YELLOW}BRANCHEZ maintenant les périphériques USB à analyser.${NC}"
    echo ""
    echo -ne "${BOLD}${YELLOW}Branchez tous les périphériques à analyser, puis appuyez sur Entrée...${NC}"
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
    # Whitelist de securite : un peripherique DEJA VU a la baseline (meme port
    # physique ou meme numero de serie) n'est JAMAIS bloque, meme s'il expose
    # une interface clavier. Objectif : ne jamais bloquer le clavier et la
    # souris de travail du poste d'analyse, meme s'ils sont rebranches pendant
    # le triage.
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

    # Detection HID clavier des nouveaux peripheriques NON whitelistes
    # + blocage des frappes. Les peripheriques whitelistes (baseline) ne
    # passent jamais ici. BLOCAGE PAR DÉFAUT : tout clavier HID apparu au
    # branchement est bloqué sans confirmation — les Entrées en tampon ne
    # peuvent plus déclencher un mauvais choix. Le clavier/souris de
    # travail restés branchés à la baseline sont whitelistés ; un clavier
    # débranché/rebranché doit être ajouté à la whitelist via la GUI USB
    # (bouton Configuration) APRÈS l'avoir identifié comme clavier de
    # travail lors d'un précédent montage.
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
            # Un périphérique HID blacklisté est déjà couvert par le blocage HID
            # par défaut plus bas ; ici on traite le cas général : déliaison des
            # éventuelles interfaces clavier puis authorized=0 (non montable,
            # invisible de lsblk). Le port est mémorisé pour l'exclusion du
            # comptage de stockage et le rapport PDF.
            while IFS= read -r iface; do
                [ -z "$iface" ] && continue
                ifname="${iface%/}"
                ifname="${ifname##*/}"
                echo "$ifname" | sudo tee "/sys/bus/usb/drivers/usbhid/unbind" >/dev/null 2>&1 || true
            done < <(usb_hid_keyboard_ifaces "$devdir")
            if echo 0 | sudo tee "$devdir/authorized" >/dev/null 2>&1; then
                echo -e "${RED}🚨 Périphérique blacklisté bloqué :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${YELLOW}— non analysable (blacklist)${NC}"
            else
                echo -e "${RED}🚨 Périphérique blacklisté détecté :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${RED}— ÉCHEC du blocage, DÉBRANCHEZ-LE${NC}"
            fi
            log_action "usb_triage_hid" "" "$devdir" "alert" "Périphérique blacklisté : ${mfr:-?} ${prod:-?} ($vid:$pid) — blocage appliqué"
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
                log_action "usb_triage_hid" "" "$devdir" "warning" "Clavier HID whitelisté (non bloqué) : ${mfr:-?} ${prod:-?} ($vid:$pid)"
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
            # Blocage : delier le driver usbhid de chaque interface clavier
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
                log_action "usb_triage_hid" "" "$devdir" "alert" "Clavier HID détecté et bloqué : ${mfr:-?} ${prod:-?} ($vid:$pid, série $ser)"
            else
                unblockable=$((unblockable + 1))
                echo -e "${RED}🚨 Clavier HID détecté :${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${RED}— ÉCHEC du blocage, DÉBRANCHEZ-LE${NC}"
                log_action "usb_triage_hid" "" "$devdir" "alert" "Clavier HID détecté, ÉCHEC du blocage : ${mfr:-?} ${prod:-?} ($vid:$pid)"
            fi
        fi
    done < "$new_file"

    HID_PROTECTED_COUNT=$protected
    # Rapport PDF de triage (toujours généré : trace de la procedure)
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
    # Recherche de menaces uniquement : si VIGIL_MOUNT_TRIAGE_JSON_OUT est
    # defini (chemin de collecte de vigil_malware_hunt.sh), le triage est
    # consolide dans le rapport final UNIQUE (pas de PDF usbhid autonome) :
    # le JSON est copie vers le chemin demande pour etre assemble plus tard.
    if [ -n "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ]; then
        if cp -f "$USBHID_JSON" "$VIGIL_MOUNT_TRIAGE_JSON_OUT" 2>/dev/null; then
            echo -e "${GREEN}✅ Triage USB consolidé dans le rapport final (pas de PDF séparé).${NC}"
            log_action "usb_triage_json" "" "$VIGIL_MOUNT_TRIAGE_JSON_OUT" "success" "Triage USB exporté vers le rapport consolidé"
        else
            echo -e "${YELLOW}⚠️  Échec de l'export du triage USB vers le rapport consolidé.${NC}"
            log_action "usb_triage_json" "" "" "warning" "Échec de l'export du JSON de triage"
        fi
    fi
    PDF_SCRIPT="$VIGIL_BASE/scripts/pdf/vigil_pdf.py"
    if [ -z "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ] \
       && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        PDF_OUT=$(python3 "$PDF_SCRIPT" --kind usbhid --json "$USBHID_JSON" \
            --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" \
            --dir "$VIGIL_BASE/rapports" --config-dir "$VIGIL_DATA_DIR" 2>&1)
        if [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
            echo -e "${GREEN}✅ Rapport de triage USB généré : $PDF_OUT${NC}"
            log_action "usb_triage_pdf" "" "$PDF_OUT" "success" "Rapport de triage USB généré"
            if [ "$ACTIVE_PROJECT" != "(no-project)" ] && [ -d "$PROJECT_LOG_DIR" ] && [ -w "$PROJECT_LOG_DIR" ]; then
                cp -f "$PDF_OUT" "$PROJECT_LOG_DIR/" 2>/dev/null || true
            fi
        else
            echo -e "${YELLOW}⚠️  Échec de la génération du rapport de triage PDF.${NC}"
            log_action "usb_triage_pdf" "" "" "warning" "Échec de la génération du PDF de triage"
        fi
    fi
    if [ "$HID_ALERT_COUNT" -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Aucun clavier HID détecté parmi les $new_count nouveau(x) périphérique(s).${NC}"
    fi
    log_action "usb_triage" "" "$after_file" "success" "Triage terminé : $new_count nouveau(x), $HID_ALERT_COUNT HID clavier, $protected protégé(s), $blocked bloqué(s)"

    # Si le SEUL périphérique apparu est un clavier suspect bloqué, il n'y a
    # rien à monter : le rapport PDF de triage vient d'être généré, on
    # termine proprement le script. Garde : si un périphérique de stockage
    # est par ailleurs présent (ex. clé restée branchée pendant la
    # baseline), on continue normalement.
    # Compter les disques de stockage USB en excluant les périphériques
    # bloqués au triage (un ducky peut exposer une partition stockage :
    # elle ne doit pas justifier la poursuite du script). Le port USB de
    # chaque disque est résolu via /sys/block/<nom>.
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
        if [ -n "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ]; then
            echo -e "${GREEN}Le triage est consolidé dans le rapport final (recherche de menaces).${NC}"
        else
            echo -e "${GREEN}Le rapport PDF de triage a été généré (rapport_usbhid_*).${NC}"
        fi
        log_action "usb_triage_end" "" "$after_file" "alert" "Fin du montage : seul périphérique détecté = clavier suspect bloqué"
        END_AFTER_TRIAGE=1
        return 0
    fi
    # Même logique pour un périphérique BLACKLISTÉ : bloqué (authorized=0),
    # il n'apparaît plus dans lsblk — rien à monter ni analyser.
    if [ "$BL_COUNT" -gt 0 ] \
       && [ "$new_count" -eq "$BL_COUNT" ] \
       && [ "$_usb_storage_count" -eq 0 ]; then
        echo ""
        echo -e "${RED}${BOLD}🚨 Le seul périphérique détecté est BLACKLISTÉ (bloqué).${NC}"
        echo -e "${RED}Il ne peut pas être monté ni analysé. Pour l'autoriser à nouveau,${NC}"
        echo -e "${RED}retirez-le de la blacklist (Accueil > Configuration > Périphériques USB).${NC}"
        if [ -n "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ]; then
            echo -e "${GREEN}Le triage est consolidé dans le rapport final (recherche de menaces).${NC}"
        else
            echo -e "${GREEN}Le rapport PDF de triage a été généré (rapport_usbhid_*).${NC}"
        fi
        log_action "usb_triage_end" "" "$after_file" "alert" "Fin du montage : seul périphérique détecté = blacklisté bloqué"
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


# --- 1. Sélection du type de périphérique ---
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sélection du type de périphérique          ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREY}Quel type de périphérique souhaitez-vous analyser ?${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[1]${NC}  ${BOLD}Smartphone${NC}  ${GREY}(MTP/PTP)${NC}"
echo -e "  ${BOLD}${BLUE}[2]${NC}  ${BOLD}Périphérique de stockage USB${NC}  ${GREY}(clé, disque dur, etc.)${NC}"
echo -e "  ${BOLD}${BLUE}[3]${NC}  ${BOLD}Autre${NC}  ${GREY}(scanner tous les types de périphériques)${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[q]${NC}  ${BOLD}Quitter${NC}"
echo ""
echo -ne "${BOLD}${YELLOW}Entrez votre choix (1-3, q pour quitter) : ${NC}"
read -r DEVICE_TYPE_CHOICE

case "$DEVICE_TYPE_CHOICE" in
    1)
        DEVICE_MODE="smartphone"
        echo -e "${GREEN}Mode : Détection des smartphones (MTP/PTP)${NC}"
        log_action "device_type_selection" "" "" "success" "Type : Smartphone (MTP/PTP)"
        ;;
    2)
        DEVICE_MODE="usb_storage"
        echo -e "${GREEN}Mode : Périphériques de stockage USB uniquement${NC}"
        log_action "device_type_selection" "" "" "success" "Type : Stockage USB"
        ;;
    3)
        DEVICE_MODE="all"
        echo -e "${GREEN}Mode : Détection de tous les types de périphériques${NC}"
        log_action "device_type_selection" "" "" "success" "Type : Tous"
        ;;
    q|Q)
        echo -e "${YELLOW}Annulé.${NC}"
        log_action "device_type_selection" "" "" "success" "Quitter à la sélection du type de périphérique"
        final_pause
        exit 0
        ;;
    *)
        fail "Choix invalide : $DEVICE_TYPE_CHOICE"
        ;;
esac

# --- Nouvel écran avec ASCII art avant la sélection du périphérique ---
# Banniere en ROUGE si un périphérique suspect a été détecté au triage,
# bleu sinon. Le résumé du contrôle est rappelé pour les non-techniciens.
clear
if [ "$HID_ALERT_COUNT" -gt 0 ]; then
    print_banner "$RED"
    echo -e "${RED}${BOLD}  ⚠ ATTENTION : $HID_ALERT_COUNT périphérique(s) suspect(s) détecté(s)${NC}"
    echo -e "${RED}  Un périphérique se fait passer pour un clavier : ses frappes sont${NC}"
    echo -e "${RED}  bloquées et il ne peut PAS être monté. Voir le rapport PDF de triage.${NC}"
    echo ""
elif [ "$HID_PROTECTED_COUNT" -gt 0 ]; then
    print_banner "$GREEN"
    echo -e "${GREEN}${BOLD}  Contrôle USB terminé : $HID_PROTECTED_COUNT périphérique(s) protégé(s) par vos soins${NC}"
    echo -e "${GREEN}  (clavier/souris de travail) — ils fonctionnent normalement.${NC}"
    echo ""
else
    print_banner
    echo -e "${GREEN}  ✅ Contrôle USB terminé : aucun périphérique suspect détecté.${NC}"
    echo ""
fi

# --- 1.5. Autorisation des périphériques USB bloqués (authorized=0) ---
# usbguard a été purgé du système mais les périphériques branchés pendant
# qu'il tournait (ou juste branchés) restent bloqués au niveau noyau
# (authorized=0), invisibles dans lsblk. Cette fonction autorise tous les
# périphériques USB bloqués et attend que le noyau les enregistre.
authorize_blocked_usb() {
    if [ ! -d /sys/bus/usb/devices ]; then
        return 0
    fi
    local found=0
    local authfile devpath state prod mfr
    for authfile in /sys/bus/usb/devices/*/authorized; do
        [ -f "$authfile" ] || continue
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

# --- 2. Détection des périphériques selon le mode sélectionné ---

# --- 2.1. Détection des DVD/CD-ROM (uniquement en mode "Autre") ---
if [ "$DEVICE_MODE" = "all" ] && [ -e /dev/cdrom ]; then
    echo -e "${YELLOW}Recherche de lecteurs CD-ROM...${NC}"
    if command -v eject >/dev/null 2>&1 && eject -t /dev/cdrom 2>/dev/null; then
        sleep 2
        sudo mkdir -p /investigation/cdrom 2>/dev/null || true
        if mount /dev/cdrom /investigation/cdrom -o ro,noexec,nosuid,nodev,noatime 2>/dev/null; then
            echo -e "${GREEN}✅ Média optique monté dans /investigation/cdrom${NC}"
            log_action "mount" "/dev/cdrom" "/investigation/cdrom" "success" "Média optique monté en lecture seule"
            echo -e "\n${GREEN}✅ Montage terminé sans erreur.${NC}"
            exit 0
        else
            echo -e "${YELLOW}⚠️  Aucun média optique détecté ou échec du montage.${NC}"
            log_action "mount_attempt" "/dev/cdrom" "/investigation/cdrom" "warning" "Échec du montage du média optique"
            sudo rmdir /investigation/cdrom 2>/dev/null || true
        fi
    fi
fi

# --- 2.2. Détection des périphériques MTP (Smartphone ou Autre) ---
if [ "$DEVICE_MODE" = "smartphone" ] || [ "$DEVICE_MODE" = "all" ]; then
    if command -v jmtpfs >/dev/null 2>&1; then
        echo -e "${YELLOW}Recherche de périphériques MTP...${NC}"
        MTP_DEVICES=$(jmtpfs -l 2>/dev/null | grep -E "^Device [0-9]+" || true)
        if [ -n "$MTP_DEVICES" ]; then
            echo -e "${GREEN}✅ Périphérique MTP détecté :${NC}"
            echo "$MTP_DEVICES" | while IFS= read -r line; do
                echo -e "   ${line}"
            done
            sudo mkdir -p /investigation/mtp 2>/dev/null || true
            if sudo jmtpfs /investigation/mtp -o ro 2>/dev/null; then
                echo -e "${GREEN}✅ Périphérique MTP monté dans /investigation/mtp${NC}"
                log_action "mount" "MTP" "/investigation/mtp" "success" "Périphérique MTP monté en lecture seule"
                echo -e "\n${GREEN}✅ Montage terminé sans erreur.${NC}"
                exit 0
            else
                echo -e "${YELLOW}⚠️  Échec du montage MTP.${NC}"
                log_action "mount_attempt" "MTP" "/investigation/mtp" "failed" "Échec du montage MTP"
                sudo rmdir /investigation/mtp 2>/dev/null || true
            fi
        else
            echo -e "${YELLOW}⚠️  Aucun périphérique MTP détecté.${NC}"
            log_action "mount_attempt" "MTP" "" "warning" "Aucun périphérique MTP détecté"
        fi
    else
        echo -e "${YELLOW}⚠️  jmtpfs non installé. Impossible de détecter les périphériques MTP.${NC}"
        log_action "mount_attempt" "MTP" "" "warning" "jmtpfs non disponible"
    fi
fi

# --- 2.3. Détection des périphériques USB (Stockage USB ou Autre) ---
# Détection robuste avec retry automatique : on tente la détection, et si rien
# n'est trouvé on autorise les périphériques USB bloqués (authorized=0) puis
# on réessaie, jusqu'à 3 passes. On détecte les partitions ET les disques USB
# sans partition (filesystem direct sur le disque, ex. /dev/sdb sans table).
# _fs_label_parttype /dev/sdXN : renvoie "FSTYPE|LABEL|PARTTYPENAME" (valeurs
# vides si indisponibles). Fallback blkid quand lsblk ne renseigne pas FSTYPE.
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
    # Nettoyer les espaces de tête/queue sans casser le label
    fs=${fs:-}
    lbl=${lbl# }; lbl=${lbl% }
    pt=${pt# }; pt=${pt% }
    echo "$fs|$lbl|$pt"
}

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

    # 1er passage : mémoriser TRAN, MODEL et SIZE de chaque disque parent
    while IFS= read -r line; do
        eval "$line"
        if [ "$TYPE" = "disk" ]; then
            PARENT_TRAN["$NAME"]="$TRAN"
            PARENT_MODEL["$NAME"]="$MODEL"
            PARENT_SIZE["$NAME"]="$SIZE"
        fi
    done <<< "$LSBLK_OUT"

    # 2e passage : détecter les partitions non montées dont le parent est USB
    # (TRAN=usb) ou removable (RM=1) — fallback quand lsblk ne renseigne pas TRAN.
    # On enrichit chaque entrée avec FSTYPE, LABEL et PARTTYPENAME. Les partitions
    # sans filesystem détectable (ex. partitions étendues MBR de 1K) sont sautées
    # car non montables.
    while IFS= read -r line; do
        eval "$line"
        if [ "$TYPE" = "part" ] && [ -n "$PKNAME" ]; then
            PT=${PARENT_TRAN["$PKNAME"]:-}
            MODEL=${PARENT_MODEL["$PKNAME"]:-}
            if [ "$PT" = "usb" ] || [ "$RM" = "1" ]; then
                if [ -z "$MOUNTPOINT" ]; then
                    IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
                    # Sauter les partitions non montables (extended MBR, etc.)
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

    # 2bis. Insertion d'une entrée « Monter tout le disque » pour chaque disque
    # USB possédant au moins 2 partitions montables. L'entrée est préfixée
    # « whole » et porte le nom du disque parent ; le montage itérera sur ses
    # partitions (DISK_PARTS). On insère ces entrées EN TÊTE de la liste afin
    # qu'elles apparaissent avant les partitions individuelles à l'affichage.
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
        # Reconstruire USB_DEVICES : entrées whole d'abord, puis partitions
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

    # 3e passage : détecter les DISQUES USB non montés sans partition
    # (filesystem direct sur le disque, ex. clé USB formatée sans table de
    # partitions). On évite les disques système (nvme, mmc, loop, etc.) en
    # exigeant TRAN=usb ou RM=1, et on saute ceux qui ont des partitions.
    while IFS= read -r line; do
        eval "$line"
        if [ "$TYPE" = "disk" ] && [ -z "$MOUNTPOINT" ]; then
            if [ "$TRAN" = "usb" ] || [ "$RM" = "1" ]; then
                # S'assurer qu'aucune partition n'existe pour ce disque
                if ! echo "$LSBLK_OUT" | grep -q "PKNAME=\"$NAME\"" 2>/dev/null; then
                    IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
                    USB_DEVICES[$DEVICE_NUM]="rawdisk|$NAME|$SIZE|$MODEL|$FSTYPE|$LABEL||"
                    DEVICE_NUM=$((DEVICE_NUM + 1))
                fi
            fi
        fi
    done <<< "$LSBLK_OUT"
}

if [ "$DEVICE_MODE" = "usb_storage" ] || [ "$DEVICE_MODE" = "all" ]; then
    echo -e "${YELLOW}Recherche des périphériques USB/Disques...${NC}"

    # Boucle de retry : jusqu'à 3 passes. À chaque passe on tente la détection ;
    # si rien n'est trouvé on autorise les USB bloqués puis on réessaie.
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
        # Cas fréquent : un périphérique USB est déjà monté ailleurs
        # (ex. dans /stockage via le montage de stockage). On le signale et
        # on propose de le démonter pour pouvoir l'analyser en lecture seule.
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
                        log_action "umount_for_ro" "/dev/$m_name" "$m_mount" "success" "Démonté pour analyse RO"
                    else
                        echo -e "  ${RED}❌ Échec du démontage de /dev/$m_name.${NC}"
                    fi
                done
                # Replacer le disque en read-only après démontage
                for i in "${!MOUNTED_USB[@]}"; do
                    IFS='|' read -r m_name m_mount m_size m_model <<< "${MOUNTED_USB[$i]}"
                    sudo blockdev --setro "/dev/$m_name" 2>/dev/null || true
                done
                sleep 1
                # Relancer la détection une dernière fois
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
            log_action "mount_attempt" "" "/investigation" "failed" "Aucun périphérique détecté"
            if [ "$DEVICE_MODE" = "usb_storage" ]; then
                final_pause
                exit 1
            fi
        fi
    fi
fi

    # --- Helper : montage lecture seule d'un device dans un point de montage ---
    # Renvoie 0 si OK, 1 si échec. Affiche le détail et log la custody.
    _mount_single_ro() {
        local dev="$1" mnt="$2"
        local fstype mount_opts ro_check

        sudo mkdir -p "$mnt" 2>/dev/null || {
            echo -e "${RED}❌ Impossible de créer le point de montage $mnt.${NC}"
            log_action "mkdir_mountpoint" "$dev" "$mnt" "failed" "Échec de la création du répertoire"
            return 1
        }

        if command -v blockdev >/dev/null 2>&1; then
            sudo blockdev --setro "$dev" 2>/dev/null || true
        fi

        fstype=$(lsblk -no FSTYPE "$dev" 2>/dev/null || echo "")
        mount_opts="-o ro,noexec,nosuid,nodev,noatime"
        case "$fstype" in
            fat32|vfat) mount_opts="$mount_opts,utf8=true" ;;
            ext3|ext4)  mount_opts="$mount_opts,noload" ;;
            ufs)        mount_opts="$mount_opts,ufstype=ufs2" ;;
            iso9660)    mount_opts="$mount_opts,unhide" ;;
            btrfs)      mount_opts="$mount_opts,subvolid=0" ;;
        esac

        if ! sudo mount $mount_opts "$dev" "$mnt" 2>/dev/null; then
            echo -e "${RED}❌ Échec du montage de $dev → $mnt${NC}"
            sudo mount $mount_opts "$dev" "$mnt" 2>&1 || true
            log_action "mount" "$dev" "$mnt" "failed" "Échec du montage"
            sudo rmdir "$mnt" 2>/dev/null || true
            return 1
        fi

        ro_check=$(lsblk -o RO "$dev" 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "")
        if [ "$ro_check" != "1" ]; then
            echo -e "${RED}❌ $dev n'est pas monté en lecture seule !${NC}"
            sudo umount "$mnt" 2>/dev/null || true
            sudo rmdir "$mnt" 2>/dev/null || true
            command -v blockdev >/dev/null 2>&1 && sudo blockdev --setrw "$dev" 2>/dev/null || true
            log_action "mount" "$dev" "$mnt" "failed" "Périphérique non monté en lecture seule"
            return 1
        fi

        echo -e "${GREEN}✅ ${NC}${BOLD}$dev${NC}${GREEN} → $mnt${NC}"
        log_action "mount" "$dev" "$mnt" "success" "Périphérique monté en lecture seule"
        return 0
    }

    # --- Helper : vérification chiffrement LUKS/BitLocker sur un device ---
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

    # --- Helper : calcul du hash SHA-256 d'un point de montage ---
    _compute_hash() {
        local dev="$1" mnt="$2" tag="$3"
        local hash_file
        hash_file="$PROJECT_LOG_DIR/device_${tag}.sha256"
        sudo rm -f "$hash_file"
        if [ -n "$(ls -A "$mnt" 2>/dev/null)" ]; then
            find "$mnt" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' > "$hash_file" || true
            echo -e "${GREEN}✅ Hash SHA-256 ($tag) :${NC} $(cat "$hash_file" 2>/dev/null)  ${GREY}→ $hash_file${NC}"
            log_action "hash_calculation" "$dev" "$hash_file" "success" "Hash SHA-256 calculé ($tag) : $(cat "$hash_file" 2>/dev/null) — arbre complet des fichiers (find+sha256sum+sort)"
        else
            echo -e "${YELLOW}⚠️  $mnt est vide, aucun hash généré ($tag).${NC}"
            log_action "hash_calculation" "$dev" "" "warning" "$mnt est vide ($tag)"
        fi
    }

    if [ "$DEVICE_NUM" -gt 0 ]; then
    # --- Affichage des peripheriques (regroupe par disque, reutilise par 'r') ---
display_usb_devices() {
        # --- 3. Affichage des périphériques (regroupé par disque) ---
        echo ""
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}  Périphériques disponibles                 ${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""

        # Regrouper les entrées par disque parent pour un affichage lisible.
        # Les entrées whole|rawdisk se rapportent au disque lui-même ; les
        # entrées part se rapportent au disque indiqué dans le dernier champ.
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

        # Afficher disque par disque (protection set -u si tableau vide)
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
        # --- Périphériques HID détectés au triage (non montables) ---
        if [ "$HID_ALERT_COUNT" -gt 0 ]; then
            echo ""
            echo -e "${RED}${BOLD}🚨 PÉRIPHÉRIQUE(S) SUSPECT(S) — interdits de montage :${NC}"
            local _hid
            for _hid in "${HID_LISTING[@]}"; do
                IFS='|' read -r _name _vidpid _ser <<< "$_hid"
                echo -e "  ${RED}${BOLD}• ${_name}${NC}  ${GREY}(réf. ${_vidpid}, n° série ${_ser:-absent})${NC}"
            done
            echo -e "${RED}    Ces périphériques se font passer pour des claviers : leurs frappes${NC}"
            echo -e "${RED}    sont bloquées et ils ne peuvent PAS être montés. Ils sont décrits${NC}"
            echo -e "${RED}    dans le rapport de triage (PDF autonome ou section du${NC}"
            echo -e "${RED}    rapport consolidé de la recherche de menaces).${NC}"
        fi
    }

    # Affichage initial de la liste (même contenu que le « r » de rafraîchissement)
    echo -e "${GREEN}✅ $DEVICE_NUM périphérique(s) détecté(s) :${NC}"
    display_usb_devices

        # --- 4. Sélection du périphérique ---
        while true; do
            echo -ne "${BOLD}${YELLOW}Entrez le numéro du périphérique à monter, \"r\" pour rafraîchir la liste, ou \"q\" pour quitter : ${NC}"
            read -r SELECTED_NUM
            if [ "$SELECTED_NUM" = "r" ] || [ "$SELECTED_NUM" = "R" ]; then
                echo -e "${YELLOW}Rafraîchissement de la liste des périphériques...${NC}"
                detect_usb_devices
                if [ "$DEVICE_NUM" -eq 0 ]; then
                    authorize_blocked_usb
                    detect_usb_devices
                fi
                if [ "$DEVICE_NUM" -eq 0 ]; then
                    echo -e "${RED}❌ Aucun périphérique détecté. Branchez le périphérique puis appuyez de nouveau sur \"r\".${NC}"
                    continue
                fi
                echo -e "${GREEN}✅ $DEVICE_NUM périphérique(s) détecté(s) :${NC}"
                display_usb_devices
                continue
            fi

            if [ "$SELECTED_NUM" = "q" ]; then
                echo -e "${YELLOW}Annulé.${NC}"
                log_action "mount_cancelled" "" "/investigation" "success" "Montage annulé par l'utilisateur"
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

        # --- 5/6. Montage selon le kind d'entrée sélectionnée ---
        echo -e "\n${YELLOW}Montage en lecture seule...${NC}"

        if [ "$SELECTED_KIND" = "whole" ]; then
            # Monter toutes les partitions du disque sous /investigation/<disk>/<part>
            echo -e "${YELLOW}Montage de toutes les partitions de /dev/$SELECTED_DEVICE...${NC}"
            if command -v blockdev >/dev/null 2>&1; then
                if sudo blockdev --setro "/dev/$SELECTED_DEVICE" 2>/dev/null; then
                    echo -e "${GREEN}✅ Mode RO forcé au niveau block device (/dev/$SELECTED_DEVICE).${NC}"
                    log_action "set_ro" "/dev/$SELECTED_DEVICE" "" "success" "Mode RO forcé au niveau block device"
                else
                    echo -e "${YELLOW}⚠️  blockdev --setro a échoué. Poursuite avec montage read-only standard.${NC}"
                    log_action "set_ro" "/dev/$SELECTED_DEVICE" "" "warning" "blockdev --setro a échoué (non bloquant)"
                fi
            fi

            _ok=0; _fail=0
            _parts="${DISK_PARTS["$SELECTED_DEVICE"]:-}"
            for _part in $_parts; do
                _dev="/dev/$_part"; _mnt="/investigation/$SELECTED_DEVICE/$_part"
                _enc=$(_is_encrypted "$_dev")
                if [ -n "$_enc" ]; then
                    echo -e "${RED}❌ $_dev est chiffré ($_enc). Ignoré.${NC}"
                    log_action "mount_attempt" "$_dev" "$_mnt" "failed" "Partition chiffrée ($_enc)"
                    _fail=$((_fail + 1))
                    continue
                fi
                if _mount_single_ro "$_dev" "$_mnt"; then
                    _ok=$((_ok + 1))
                else
                    _fail=$((_fail + 1))
                fi
            done

            echo ""
            echo -e "${GREEN}✅ $_ok partition(s) montée(s), $_fail échec(s) sous /investigation/$SELECTED_DEVICE/${NC}"
            log_action "mount_whole" "/dev/$SELECTED_DEVICE" "/investigation/$SELECTED_DEVICE" "success" "$_ok partition(s) montée(s), $_fail échec(s)"

            # Hash global du disque (union de toutes les partitions montées)
            _compute_hash "/dev/$SELECTED_DEVICE" "/investigation/$SELECTED_DEVICE" "$SELECTED_DEVICE"

        else
            # Montage d'un device unique (partition ou disque sans table)
            DEVICE_PATH="/dev/$SELECTED_DEVICE"
            _enc=$(_is_encrypted "$DEVICE_PATH")
            if [ -n "$_enc" ]; then
                echo -e "${RED}❌ Ce périphérique est chiffré ($_enc).${NC}"
                echo -e "${YELLOW}Utilisez un outil de déchiffrement avant de continuer.${NC}"
                log_action "mount_attempt" "$DEVICE_PATH" "/investigation" "failed" "Périphérique chiffré ($_enc)"
                final_pause
                exit 1
            fi

            MOUNT_POINT="/investigation/$SELECTED_DEVICE"
            echo -e "${YELLOW}Montage de ${GREEN}$DEVICE_PATH${YELLOW} dans $MOUNT_POINT...${NC}"

            if command -v blockdev >/dev/null 2>&1; then
                if sudo blockdev --setro "$DEVICE_PATH" 2>/dev/null; then
                    echo -e "${GREEN}✅ Mode RO forcé au niveau block device.${NC}"
                    log_action "set_ro" "$DEVICE_PATH" "" "success" "Mode RO forcé au niveau block device"
                else
                    echo -e "${YELLOW}⚠️  blockdev --setro a échoué. Poursuite avec montage read-only standard.${NC}"
                    log_action "set_ro" "$DEVICE_PATH" "" "warning" "blockdev --setro a échoué (non bloquant)"
                fi
            else
                echo -e "${YELLOW}⚠️  blockdev non disponible. Montage read-only standard uniquement.${NC}"
            fi

            if ! _mount_single_ro "$DEVICE_PATH" "$MOUNT_POINT"; then
                final_pause
                exit 1
            fi

            _compute_hash "$DEVICE_PATH" "$MOUNT_POINT" "$SELECTED_DEVICE"
        fi

        # --- 8. Pause avant de quitter ---
        final_pause
        exit 0
    fi

echo -e "\n${GREEN}Script terminé.${NC}"
final_pause
