#!/bin/bash
# Use the mount triage with the acquisition's role and eligible inventory.
set -uo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
. "$base/lib/vigil-terminal.sh"
. "$base/lib/vigil-device-triage.sh"

print_banner() {
    vigil_logo "$base/../data/icons/vigil.svg"
}

# Acquisition can be performed without a case or a custody log.
log_action() { :; }

# All terminal I/O stays attached to the operator's terminal. FD 3 carries
# only the triage result back to the Python caller.
exec 3>&1 1>&2
action="$1"
TRIAGE_DIR="$2"
shift 2

case "$action" in
    triage)
        USB_BLACKLIST_FILE="$1/usb/blacklist.txt"
        USB_WHITELIST_FILE="$1/usb/whitelist.txt"
        run_usb_triage "$2" "${3:-}" || exit "$?"
        if [ "$HID_ALERT_COUNT" -gt 0 ]; then
            printf '%s\n' "${HID_LISTING[@]}" > "$TRIAGE_DIR/alerts"
        fi
        while IFS='|' read -r busdev port _; do
            [[ "$busdev" =~ ^[0-9]+:[0-9]+$ ]] && [[ "$port" =~ ^[0-9]+-[0-9]+([.][0-9]+)*$ ]] || continue
            triage_port_blocked "$port" && continue
            printf '%s|%s\n' "$port" "$busdev" >&3
        done < "$TRIAGE_DIR/usb_new.txt"
        ;;
    select)
        title="$1"
        prompt="$2"
        shift 2
        declare -a USB_DEVICES=() HID_LISTING=()
        declare -A PARENT_SIZE=() PARENT_MODEL=() DEVICE_ACCESS=()
        if [ -f "$TRIAGE_DIR/alerts" ]; then
            mapfile -t HID_LISTING < "$TRIAGE_DIR/alerts"
        fi
        HID_ALERT_COUNT=${#HID_LISTING[@]}
        for record in "$@"; do
            IFS='|' read -r kind name size model fs label parttype parent mode parent_size parent_model <<< "$record"
            DEVICE_ACCESS["$name"]="$mode"
            parent=${parent:-$name}
            PARENT_SIZE["$parent"]="$parent_size"
            PARENT_MODEL["$parent"]="$parent_model"
            USB_DEVICES+=("${record%|*|*|*}")
        done
        DEVICE_NUM=${#USB_DEVICES[@]}
        if [ "$DEVICE_NUM" -eq 0 ]; then
            echo -e "${RED}❌ Aucun périphérique admissible : $title.${NC}"
        else
            echo -e "${GREEN}✅ $DEVICE_NUM périphérique(s) détecté(s) :${NC}"
        fi
        display_usb_devices "$title"
        select_usb_device "$prompt" || exit "$?"
        printf '%s\n' "$SELECTED_INDEX" >&3
        ;;
    *) exit 4 ;;
esac
