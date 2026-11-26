#!/bin/bash
# Use the normal RO mounting workflow and keep its device lease throughout.
set -uo pipefail

script_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
. "$script_root/lib/vigil-terminal.sh"
. "$script_root/lib/vigil-device-ops.sh"
vigil_device_begin
vigil_banner "$(vigil_text "Mise à jour antivirus depuis USB" "Antivirus update from USB")"

core="$script_root/../vigil/clamav.py"
python_bin="${VIGIL_REPORT_PYTHON:-python3}"
run="${VIGIL_UPDATE_RUN:?use the Vigil offline update workflow}"
export VIGIL_LEGACY_CASE_DIR="$run" VIGIL_LEGACY_PROJECT="(no-project)"
export VIGIL_MOUNT_TRIAGE_JSON_OUT="$run/usb-triage.json"

"$python_bin" "$core" mounts-clear || exit 1
cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if ! "$python_bin" "$core" mounts-clear; then
        bash "$script_root/analyse/vigil_usb_umount.sh" || status=1
    fi
    if ! "$python_bin" "$core" mounts-clear; then
        echo "$(vigil_text "Démontage non confirmé." "Unmount was not verified.")" >&2
        status=1
    fi
    if [ "$status" -eq 0 ] || [ "$status" -eq 2 ]; then
        echo "$(vigil_text "Libération du support confirmée." "USB release verified.")" | tee -a "$run/update.log"
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
sudo -v || exit 1
bash "$script_root/analyse/vigil_usb_mount.sh" || exit 1
"$python_bin" "$core" offline 2>&1 | tee -a "$run/update.log"
