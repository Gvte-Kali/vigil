# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
GREY='\e[90m'
BOLD='\e[1m'
NC='\e[0m'

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

usb_display_field() {
    LC_ALL=C tr -d '[:cntrl:]' | tr '|\\' '  '
}

usb_snapshot() {
    # Format : busnum:devnum|port|vid|pid|manufacturer|product|serial
    # "port" = chemin sysfs (ex. 1-2, 2-1.3) : STABLE au rebranchement sur
    # le meme port physique — utilise pour ne jamais bloquer un peripherique
    # de travail (clavier, souris) deja present a la baseline.
    local dir busnum devnum vid pid mfr prod ser safe_serial
    for dir in /sys/bus/usb/devices/*; do
        [ -d "$dir" ] || continue
        case "${dir##*/}" in *:*) continue ;; esac
        busnum=$(cat "$dir/busnum" 2>/dev/null)
        devnum=$(cat "$dir/devnum" 2>/dev/null)
        [ -z "$busnum" ] && continue
        vid=$(cat "$dir/idVendor" 2>/dev/null || echo "?")
        pid=$(cat "$dir/idProduct" 2>/dev/null || echo "?")
        mfr=$(cat "$dir/manufacturer" 2>/dev/null | usb_display_field || true)
        prod=$(cat "$dir/product" 2>/dev/null | usb_display_field || true)
        ser=$(cat "$dir/serial" 2>/dev/null || true)
        safe_serial=$(printf '%s' "$ser" | usb_display_field)
        [ "$ser" = "$safe_serial" ] || ser=""
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

triage_tee() {
    if [ "$EUID" -eq 0 ]; then
        /usr/bin/tee "$@"
    else
        /usr/bin/sudo /usr/bin/tee "$@"
    fi
}

run_usb_triage() {
    local role="${1:-}" allow_internal="${2:-}"
    local base_file after_file new_file hid_file
    local busdev port vid pid mfr prod ser devdir
    local baseline_count after_count new_count blocked unblockable protected HID_ANSWER
    base_file="$TRIAGE_DIR/usb_baseline.txt"
    after_file="$TRIAGE_DIR/usb_after.txt"
    new_file="$TRIAGE_DIR/usb_new.txt"
    hid_file="$TRIAGE_DIR/usb_hid.txt"
    prot_file="$TRIAGE_DIR/usb_protected.txt"

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $(vigil_text "Triage USB (détection Rubber Ducky)" "USB triage (Rubber Ducky detection)")${role:+ · $role}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}$(vigil_text "Débranchez les supports USB à examiner avant de relever les périphériques déjà présents." "Disconnect USB media to be examined before recording the already connected devices.")${NC}"
    echo ""
    if [ "$allow_internal" = internal ]; then
        vigil_style '1;96' "  [Entrée / Enter]  $(vigil_text "Support USB · poursuivre le triage par débranchement/rebranchement" "USB media · continue with disconnect/reconnect triage")"
        vigil_style '1;93' "  [I]               $(vigil_text "Disque interne · afficher les sources admissibles en lecture seule" "Internal disk · list eligible read-only sources")"
        vigil_style '1;90' "  [Q]               $(vigil_text "Annuler l’opération" "Cancel the operation")"
    fi
    while true; do
        if [ "$allow_internal" = internal ]; then
            printf '%s ' "$(vigil_text "Votre choix [Entrée/I/Q] :" "Your choice [Enter/I/Q]:")"
        else
            printf '%s ' "$(vigil_text "Appuyez sur Entrée après le débranchement, ou Q pour annuler :" "Press Enter after disconnecting, or Q to cancel:")"
        fi
        read -r HID_ANSWER || return 1
        case "$HID_ANSWER" in
            "") break ;;
            [qQ]) return 1 ;;
            [iI]) [ "$allow_internal" != internal ] || return 3 ;;
        esac
        vigil_style '1;91' "$(vigil_text "Choix invalide." "Invalid choice.")"
    done
    usb_snapshot > "$base_file"
    baseline_count=$(grep -cve '^[[:space:]]*$' "$base_file" 2>/dev/null)
    baseline_count=${baseline_count:-0}
    echo -e "${GREEN}✅ $(vigil_text "Baseline USB enregistrée :" "USB baseline recorded:") $baseline_count $(vigil_text "périphérique(s) présents." "device(s) present.")${NC}"
    log_action "usb_triage" "" "$base_file" "success" "Baseline USB : $baseline_count périphérique(s)"
    echo ""
    echo -e "${YELLOW}$(vigil_text "BRANCHEZ maintenant les périphériques USB à analyser." "Connect the USB devices to examine now.")${NC}"
    echo ""
    echo -ne "${BOLD}${YELLOW}$(vigil_text "Branchez tous les périphériques à analyser, puis appuyez sur Entrée..." "Connect the devices to examine and press Enter...")${NC}"
    read -r HID_ANSWER || return 1
    [[ "$HID_ANSWER" != [qQ] ]] || return 1
    # Attente de la détection noyau : 10 s avec barre de progression.
    # Le tampon clavier est purgé pendant l'attente : des Entrées tapées
    # pendant le décompte ne doivent PAS être réutilisées plus tard comme
    # réponse à un prompt (bug des doubles Entrée).
    echo -e "${BLUE}$(vigil_text "Attente de la détection par le noyau (10 s)..." "Waiting for kernel detection (10 s)...")${NC}"
    local _total=10 _elapsed=0 _fill="" _k _stage=usb
    case "$role" in
        [Ss]ource) _stage=usb-source ;;
        [Dd]estination) _stage=usb-destination ;;
    esac
    while [ "$_elapsed" -lt "$_total" ]; do
        _fill=""
        for (( _k=0; _k<_elapsed; _k++ )); do _fill="${_fill}#"; done
        if [ "${VIGIL_EMBEDDED_TERMINAL:-}" = 1 ]; then
            vigil_progress_frame "$_stage" "$((_elapsed * 100 / _total))" "$_elapsed / $_total s"
        else
            printf "\r  ${BLUE}[%-10s] %d s${NC}" "$_fill" "$_elapsed"
        fi
        # Purge du tampon clavier (Entrées anticipées)
        if [ -t 0 ]; then
            while IFS= read -r -t 0.05 < /dev/tty 2>/dev/null; do :; done
        fi
        sleep 1
        _elapsed=$((_elapsed + 1))
    done
    if [ "${VIGIL_EMBEDDED_TERMINAL:-}" = 1 ]; then
        vigil_progress_frame "$_stage" 100 "$_total / $_total s" true
    else
        printf "\r  ${BLUE}[%-10s] %d s${NC}\n" "##########" "$_total"
    fi
    usb_snapshot > "$after_file"
    after_count=$(grep -cve '^[[:space:]]*$' "$after_file" 2>/dev/null)
    after_count=${after_count:-0}
    if [ -t 1 ]; then clear; fi
    print_banner
    echo -e "${GREEN}✅ $after_count $(vigil_text "périphérique(s) USB détecté(s) au total." "USB device(s) detected in total.")${NC}"

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
        local iface ifname
        if usb_is_listed "$devdir" "$USB_BLACKLIST_FILE"; then
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
                echo "$ifname" | triage_tee "/sys/bus/usb/drivers/usbhid/unbind" >/dev/null 2>&1 || true
            done < <(usb_hid_keyboard_ifaces "$devdir")
            if echo 0 | triage_tee "$devdir/authorized" >/dev/null 2>&1; then
                echo -e "$(vigil_text "${RED}🚨 $(vigil_text "Périphérique blacklisté bloqué :" "Blocked denylisted device:")${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${YELLOW}— non analysable (blacklist)${NC}" "${RED}🚨 Blocked denylisted device:${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${YELLOW}— cannot be analyzed (denylist)${NC}")"
            else
                echo -e "${RED}🚨 $(vigil_text "Périphérique blacklisté détecté :" "Denylisted device detected:")${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${RED}$(vigil_text "— ÉCHEC du blocage, DÉBRANCHEZ-LE" "— blocking FAILED, DISCONNECT IT")${NC}"
            fi
            log_action "usb_triage_hid" "" "$devdir" "alert" "Périphérique blacklisté : ${mfr:-?} ${prod:-?} ($vid:$pid) — blocage appliqué"
            HID_BLOCKED_PORTS+=("$port")
            echo "${busdev}|${vid}|${pid}|${mfr}|${prod}|${ser}" >> "$hid_file"
            BL_COUNT=$((BL_COUNT + 1))
            continue
        fi
        if [ -n "$(usb_hid_keyboard_ifaces "$devdir")" ]; then
            if usb_is_listed "$devdir" "$USB_WHITELIST_FILE"; then
                protected=$((protected + 1))
                echo "$busdev" >> "$prot_file"
                echo -e "$(vigil_text "${GREEN}  ✅ $(vigil_text "Clavier HID whitelisté :" "Allowlisted HID keyboard:") ${BOLD}${mfr:-?} ${prod:-?}${NC}  ${GREY}($vid:$pid) — frappes actives (whitelist).${NC}" "${GREEN}  ✅ Allowlisted HID keyboard: ${BOLD}${mfr:-?} ${prod:-?}${NC}  ${GREY}($vid:$pid) — keystrokes enabled (allowlist).${NC}")"
                log_action "usb_triage_hid" "" "$devdir" "warning" "Clavier HID whitelisté (non bloqué) : ${mfr:-?} ${prod:-?} ($vid:$pid)"
                continue
            fi
            local _bar="" _i
            for (( _i=0; _i<66; _i++ )); do _bar="${_bar}━"; done
            echo ""
            echo -e "${RED}┏${_bar}┓${NC}"
            echo -e "$(vigil_text "${RED}┃  ⚠ PÉRIPHÉRIQUE SUSPECT DÉTECTÉ${NC}" "${RED}┃  ⚠ SUSPICIOUS DEVICE DETECTED${NC}")"
            echo -e "${RED}┗${_bar}┛${NC}"
            echo ""
            echo -e "  ${BOLD}$(vigil_text "Périphérique détecté :" "Device detected:")${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC}  ${GREY}($vid:$pid)${NC}"
            echo -e "$(vigil_text "  ${GREY}Un périphérique de stockage ne se présente jamais comme un clavier :${NC}" "  ${GREY}A storage device should not appear as a keyboard:${NC}")"
            echo -e "$(vigil_text "  ${GREY}par sécurité ses frappes sont BLOQUÉES automatiquement et il ne peut${NC}" "  ${GREY}for safety, its keystrokes are BLOCKED automatically and it${NC}")"
            echo -e "$(vigil_text "  ${GREY}pas être monté. Pour whitelister un clavier/souris de travail, utilisez${NC}" "  ${GREY}cannot be mounted. To allowlist a trusted keyboard/mouse, use${NC}")"
            echo -e "$(vigil_text "  ${GREY}la GUI USB (Accueil > Configuration > Périphériques USB).${NC}" "  ${GREY}the USB GUI (Home > Configuration > USB devices).${NC}")"
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
                if echo "$ifname" | triage_tee "/sys/bus/usb/drivers/usbhid/unbind" >/dev/null 2>&1; then
                    one_blocked=1
                fi
            done < <(usb_hid_keyboard_ifaces "$devdir")
            if [ "$one_blocked" -gt 0 ]; then
                blocked=$((blocked + 1))
                echo -e "${RED}🚨 $(vigil_text "Clavier HID détecté :" "HID keyboard detected:")${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${YELLOW}$(vigil_text "— frappes bloquées, non montable" "— keystrokes blocked, device cannot be mounted")${NC}"
                log_action "usb_triage_hid" "" "$devdir" "alert" "Clavier HID détecté et bloqué : ${mfr:-?} ${prod:-?} ($vid:$pid, série $ser)"
            else
                unblockable=$((unblockable + 1))
                echo -e "${RED}🚨 $(vigil_text "Clavier HID détecté :" "HID keyboard detected:")${NC} ${BOLD}${mfr:-?} ${prod:-?}${NC} ${GREY}($vid:$pid)${NC} ${RED}$(vigil_text "— ÉCHEC du blocage, DÉBRANCHEZ-LE" "— blocking FAILED, DISCONNECT IT")${NC}"
                log_action "usb_triage_hid" "" "$devdir" "alert" "Clavier HID détecté, ÉCHEC du blocage : ${mfr:-?} ${prod:-?} ($vid:$pid)"
            fi
        fi
    done < "$new_file"

    HID_PROTECTED_COUNT=$protected
    TRIAGE_NEW_COUNT=$new_count
    TRIAGE_BLOCKED=$blocked
    TRIAGE_UNBLOCKABLE=$unblockable
    if declare -F report_usb_triage >/dev/null; then
        report_usb_triage "$new_file" "$hid_file" "$prot_file" "$baseline_count" \
            "$after_count" "$new_count" "$protected" "$blocked" "$unblockable"
    fi
    if [ "$HID_ALERT_COUNT" -eq 0 ]; then
        echo ""
        echo -e "$(vigil_text "${GREEN}✅ Aucun clavier HID détecté parmi les $new_count nouveau(x) périphérique(s).${NC}" "${GREEN}✅ No HID keyboard found among the $new_count new device(s).${NC}")"
    fi
    log_action "usb_triage" "" "$after_file" "success" "Triage terminé : $new_count nouveau(x), $HID_ALERT_COUNT HID clavier, $protected protégé(s), $blocked bloqué(s)"
}

display_usb_devices() {
    # --- 3. Affichage des périphériques (regroupé par disque) ---
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "$(vigil_text "${BLUE}  ${1:-Périphériques disponibles                 }${NC}" "${BLUE}  ${1:-Available devices                       }${NC}")"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Regrouper les entrées par disque parent pour un affichage lisible.
    # Les entrées whole|rawdisk se rapportent au disque lui-même ; les
    # entrées part se rapportent au disque indiqué dans le dernier champ.
    local -A _DISK_ORDER=()
    local -a _DISK_SEQ=()
    local i KIND DEVICE_NAME DEVICE_SIZE DEVICE_MODEL FSTYPE LABEL PARTTYPE PKNAME
    local _disk_key _dsize _dmodel _key _partinfo access mode _name _vidpid _ser
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
        echo -e "$(vigil_text "  ${BOLD}${BLUE} Disque /dev/$_disk_key${NC}  ${GREY}• $(vigil_text "Taille:" "Size:")${NC} ${BOLD}$_dsize${NC}  ${GREY}• Modèle:${NC} ${BOLD}$_dmodel${NC}" "  ${BOLD}${BLUE} Disk /dev/$_disk_key${NC}  ${GREY}• Size:${NC} ${BOLD}$_dsize${NC}  ${GREY}• Model:${NC} ${BOLD}$_dmodel${NC}")"
        for i in "${!USB_DEVICES[@]}"; do
            IFS='|' read -r KIND DEVICE_NAME DEVICE_SIZE DEVICE_MODEL FSTYPE LABEL PARTTYPE PKNAME <<< "${USB_DEVICES[$i]}"
            if [ "$KIND" = "part" ]; then _key="$PKNAME"; else _key="$DEVICE_NAME"; fi
            [ "$_key" != "$_disk_key" ] && continue
            mode=${DEVICE_ACCESS[$DEVICE_NAME]:-?}
            access="${GREY}• Bloc :${NC} ${BOLD}$mode${NC}"
            case "$mode" in
                RO) access="${GREY}• Bloc :${NC} ${GREEN}RO${NC}" ;;
                RW) access="${GREY}• Bloc :${NC} ${YELLOW}RW${NC}" ;;
            esac
            if [ "$KIND" = "whole" ]; then
                echo -e "$(vigil_text "    ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD} Monter tout le disque${NC}  ${GREY}(${FSTYPE} partition(s))${NC}  $access" "    ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD} Mount entire disk${NC}  ${GREY}(${FSTYPE} partition(s))${NC}  $access")"
            elif [ "$KIND" = "disk" ]; then
                echo -e "    ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD}/dev/$DEVICE_NAME${NC}  $access"
            elif [ "$KIND" = "rawdisk" ]; then
                echo -e "    ${BOLD}${BLUE}[$((i+1))]${NC}  ${BOLD}/dev/$DEVICE_NAME${NC}  ${GREY}• FS:${NC} ${BOLD}${FSTYPE:-?}${NC}  ${GREY}• $(vigil_text "Taille:" "Size:")${NC} ${BOLD}$DEVICE_SIZE${NC}  $access"
            else
                _partinfo="${BOLD}/dev/$DEVICE_NAME${NC}"
                [ -n "$PARTTYPE" ] && [ "$PARTTYPE" != "Linux filesystem" ] && _partinfo="$_partinfo  ${GREY}[$PARTTYPE]${NC}"
                [ -n "$LABEL" ] && _partinfo="$_partinfo  ${GREY}• Vol:${NC} ${BOLD}$LABEL${NC}"
                _partinfo="$_partinfo  ${GREY}• FS:${NC} ${BOLD}${FSTYPE:-?}${NC}  ${GREY}• Taille:${NC} ${BOLD}$DEVICE_SIZE${NC}  $access"
                echo -e "    ${BOLD}${BLUE}[$((i+1))]${NC}  $_partinfo"
            fi
        done
        echo ""
    done
    # --- Périphériques HID détectés au triage (non montables) ---
    if [ "${HID_ALERT_COUNT:-0}" -gt 0 ]; then
        echo ""
        echo -e "$(vigil_text "${RED}${BOLD}🚨 PÉRIPHÉRIQUE(S) SUSPECT(S) — exclus de la sélection :${NC}" "${RED}${BOLD}🚨 SUSPICIOUS DEVICE(S) — excluded from selection:${NC}")"
        local _hid
        for _hid in "${HID_LISTING[@]}"; do
            IFS='|' read -r _name _vidpid _ser <<< "$_hid"
            echo -e "$(vigil_text "  ${RED}${BOLD}• ${_name}${NC}  ${GREY}(réf. ${_vidpid}, n° série ${_ser:-absent})${NC}" "  ${RED}${BOLD}• ${_name}${NC}  ${GREY}(ref. ${_vidpid}, serial ${_ser:-missing})${NC}")"
        done
        echo -e "$(vigil_text "${RED}    Ces périphériques se font passer pour des claviers : leurs frappes${NC}" "${RED}    These devices impersonate keyboards: their keystrokes${NC}")"
        echo -e "$(vigil_text "${RED}    sont bloquées et ils ne peuvent PAS être sélectionnés.${NC}" "${RED}    are blocked and they CANNOT be selected.${NC}")"
        if declare -F report_usb_triage >/dev/null; then
            echo -e "$(vigil_text "${RED}    Voir le rapport PDF de triage ou le rapport consolidé.${NC}" "${RED}    See the USB triage PDF or consolidated report.${NC}")"
        fi
    fi
}

# Return 2 for refresh and 1 for cancellation. The caller owns the inventory.
select_usb_device() {
    local number
    while true; do
        echo -ne "$(vigil_text "${BOLD}${YELLOW}Entrez le numéro du périphérique $1, \"r\" pour rafraîchir la liste, ou \"q\" pour quitter : ${NC}" "${BOLD}${YELLOW}Enter the device number $1, \"r\" to refresh, or \"q\" to quit: ${NC}")"
        if ! read -r number || [[ "$number" == [qQ] ]]; then
            echo -e "${YELLOW}$(vigil_text "Annulé." "Cancelled.")${NC}"
            return 1
        fi
        if [[ "$number" == [rR] ]]; then
            echo -e "$(vigil_text "${YELLOW}Rafraîchissement de la liste des périphériques...${NC}" "${YELLOW}Refreshing device list...${NC}")"
            return 2
        fi
        if [[ "$number" =~ ^[0-9]{1,8}$ ]] && (( 10#$number >= 1 && 10#$number <= DEVICE_NUM )); then
            SELECTED_INDEX=$((10#$number - 1))
            return 0
        fi
        echo -e "${RED}❌ $(vigil_text "Numéro invalide." "Invalid number.") $(vigil_text "Entrez un numéro entre 1 et $DEVICE_NUM." "Enter a number between 1 and $DEVICE_NUM.")${NC}"
    done
}

usb_is_listed() {
    local device="$1" list="$2" vid pid serial
    vid=$(cat "$device/idVendor" 2>/dev/null || true)
    pid=$(cat "$device/idProduct" 2>/dev/null || true)
    serial=$(cat "$device/serial" 2>/dev/null || true)
    grep -qxF -- "$vid:$pid" "$list" 2>/dev/null ||
        { [ -n "$serial" ] && grep -qxF -- "$serial" "$list" 2>/dev/null; }
}

triage_port_blocked() {
    local port
    for port in "${HID_BLOCKED_PORTS[@]}"; do
        [ "$1" = "$port" ] && return 0
    done
    return 1
}

triage_disk_blocked() {
    local path port
    path=$(readlink -f "/sys/block/$1" 2>/dev/null) || return 1
    while [ "$path" != / ]; do
        if [ -r "$path/idVendor" ] && [ -r "$path/idProduct" ]; then
            port=${path##*/}
            triage_port_blocked "$port" && return 0
            usb_is_listed "$path" "$USB_BLACKLIST_FILE" && return 0
        fi
        path=${path%/*}
        [ -n "$path" ] || break
    done
    return 1
}
