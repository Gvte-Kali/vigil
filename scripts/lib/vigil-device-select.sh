#!/bin/bash
set -uo pipefail
here=$(dirname -- "${BASH_SOURCE[0]}")
. "$here/vigil-terminal.sh"
. "$here/vigil-device-triage.sh"
. "$here/vigil-device-ops.sh"

exec 3>&1 1>&2
print_banner() { vigil_logo; }
log_action() { :; }
if [ "$1" = --mounted ]; then
    shift
    DEVICE_NUM=$#
    while true; do
        echo -e "${BLUE}  $(vigil_text "Périphériques montés" "Mounted resources")${NC}"
        index=0
        for target in "$@"; do
            index=$((index + 1))
            printf '    %b[%s]%b  %q\n' "${BOLD}${BLUE}" "$index" "$NC" "$target"
        done
        select_usb_device "$(vigil_text "à démonter" "to unmount")" && break
        case $? in 2) continue ;; *) exit 1 ;; esac
    done
    printf '%s\n' "$SELECTED_INDEX" >&3
    exit 0
fi
USB_WHITELIST_FILE="$1/usb/whitelist.txt"
USB_BLACKLIST_FILE="$1/usb/blacklist.txt"
TRIAGE_DIR=$(mktemp -d -t vigil-device-select-XXXXXXXX) || exit 1
trap 'rm -rf -- "$TRIAGE_DIR"' EXIT
run_usb_triage "$2" || exit "$?"
while true; do
    detect_usb_devices || exit 1
    display_usb_devices
    select_usb_device "$(vigil_text 'à sélectionner' 'to select')" && break
    case $? in 2) continue ;; *) exit 1 ;; esac
done
IFS='|' read -r kind name _ <<< "${USB_DEVICES[$SELECTED_INDEX]}"
printf '/dev/%s\n' "$name" >&3
