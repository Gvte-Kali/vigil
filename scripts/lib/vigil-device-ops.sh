# Adapter for the Core lease and kernel-backed device validations.
_vigil_device_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)

vigil_device_check() {
    /usr/bin/python3 -I -c '
import sys
sys.path.insert(0, sys.argv.pop(1))
from vigil.device_manager import shell_check
sys.exit(shell_check(sys.argv[1:]))
' "$_vigil_device_root" "$@"
}

vigil_mounts_in_zone() {
    /usr/bin/python3 -I -c '
import sys
sys.path.insert(0, sys.argv.pop(1))
from vigil.device_manager import mounted_resources
targets = {item["mountpoint"] for item in mounted_resources() if item["zone"] == sys.argv[1]}
for target in sorted(targets, key=lambda target: (-target.count("/"), target)):
    if "\n" in target or "\r" in target:
        raise SystemExit("Unsupported mount path / chemin de montage non pris en charge")
    print(target)
' "$_vigil_device_root" "$1"
}

vigil_device_lease() {
    local inherited=${VIGIL_DEVICE_LEASE:-}
    if [[ "$inherited" =~ ^[0-9]+$ ]] && [ "/proc/self/fd/$inherited" -ef /run/lock ]; then
        flock -n -x "$inherited"
    else
        exec {inherited}</run/lock || return 1
        flock -n -x "$inherited" || return 1
        export VIGIL_DEVICE_LEASE="$inherited"
    fi
}

vigil_device_begin() {
    vigil_device_lease || {
        echo "Périphériques Vigil occupés / Vigil devices are busy" >&2
        exit 1
    }
    if [ "${VIGIL_DEVICE_NONINTERACTIVE:-}" = 1 ]; then
        sudo() { /usr/bin/sudo -n "$@"; }
        clear() { :; }
    fi
}

vigil_mount_volume() {
    local zone="$1" device="$2" target="$3"
    shift 3
    case "$target" in "$zone"/*) ;; *) return 1 ;; esac
    [ "$(realpath -e -- "$target")" = "$target" ] || return 1
    if ! sudo mount "$@" -- "$device" "$target"; then
        return 1
    fi
    if ! VIGIL_VERIFY_DEVICE="$device" vigil_device_check verify "$zone" "$target"; then
        sudo umount -- "$target" || true
        return 1
    fi
}

vigil_unmount_target() {
    local zone="$1" target="$2"
    local VIGIL_DEVICE_MOUNT_ID=${VIGIL_DEVICE_MOUNT_ID:-}
    if [ -z "$VIGIL_DEVICE_MOUNT_ID" ]; then
        VIGIL_DEVICE_MOUNT_ID=$(vigil_device_check mount-id "$zone" "$target") || return 1
    fi
    export VIGIL_DEVICE_MOUNT_ID
    vigil_device_check unmount "$zone" "$target" || return 1
    sudo umount -- "$target" 2>/dev/null && return 0
    sync 2>/dev/null || true
    vigil_device_check unmount "$zone" "$target" && sudo umount -- "$target"
}

detect_usb_devices() {
    declare -gA USB_DEVICES=() PARENT_MODEL=() PARENT_SIZE=() DEVICE_ACCESS=()
    declare -gA DISK_PARTS=() DISK_PARTCOUNT=()
    local -a raw_disks=()
    DEVICE_NUM=0
    MOUNTED_NUM=0
    MOUNTED_USB=()

    local record kind name size model fs label parttype parent inventory i disk e
    inventory=$(/usr/bin/python3 -I "$_vigil_device_root/scripts/lib/vigil_block_inventory.py") || return 1
    while IFS= read -r record; do
        IFS='|' read -r kind name size model fs label parttype parent <<< "$record"
        case "$kind" in
            parent)
                PARENT_SIZE["$name"]="$size"
                PARENT_MODEL["$name"]="$model"
                DEVICE_ACCESS["$name"]="$fs"
                ;;
            access) DEVICE_ACCESS["$name"]="$size" ;;
            mounted)
                MOUNTED_USB[$MOUNTED_NUM]="${record#*|}"
                MOUNTED_NUM=$((MOUNTED_NUM + 1))
                ;;
            part)
                triage_disk_blocked "$parent" && continue
                USB_DEVICES[$DEVICE_NUM]="$record"
                DEVICE_NUM=$((DEVICE_NUM + 1))
                DISK_PARTS["$parent"]="${DISK_PARTS["$parent"]:-}$name "
                DISK_PARTCOUNT["$parent"]=$((${DISK_PARTCOUNT["$parent"]:-0} + 1))
                ;;
            rawdisk)
                triage_disk_blocked "$name" || raw_disks+=("$record")
                ;;
        esac
    done <<< "$inventory"

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

    for record in "${raw_disks[@]}"; do
        USB_DEVICES[$DEVICE_NUM]="$record"
        DEVICE_NUM=$((DEVICE_NUM + 1))
    done
}

select_device_path() {
    local index kind name
    for index in "${!USB_DEVICES[@]}"; do
        IFS='|' read -r kind name _ <<< "${USB_DEVICES[$index]}"
        if [ "/dev/$name" = "$1" ]; then
            SELECTED_INDEX=$index
            return 0
        fi
    done
    return 1
}

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
            devpath="${authfile%/authorized}"
            triage_port_blocked "${devpath##*/}" && continue
            usb_is_listed "$devpath" "$USB_BLACKLIST_FILE" && continue
            if [ "$found" -eq 0 ]; then
                echo -e "${YELLOW}Réparation des périphériques USB bloqués (authorized=0)...${NC}"
            fi
            found=1
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

report_usb_triage() {
    local new_file="$1" hid_file="$2" prot_file="$3" baseline_count="$4"
    local after_count="$5" new_count="$6" protected="$7" blocked="$8" unblockable="$9"
    local USBHID_JSON DATE_ANALYSIS PDF_SCRIPT PDF_OUT
    local busdev port vid pid mfr prod ser first hidflag protflag blflag
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
}
