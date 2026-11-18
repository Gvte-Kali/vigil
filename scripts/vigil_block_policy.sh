# Shared by actions that change the kernel read-only flag.
vigil_protected_device() {
    local properties
    properties=$(udevadm info --query=property --name="$1") || return 0
    grep -qx 'VIGIL_USB_PROTECTED=1' <<< "$properties"
}

vigil_restore_rw() {
    if vigil_protected_device "$1"; then
        return 1
    fi
    sudo blockdev --setrw "$1"
}

vigil_storage_relock() {
    local device=$1 parent child mounts
    sudo blockdev --setro "$device" || return 1
    parent=$(lsblk -dnpo PKNAME "$device") || return 1
    if [[ -n "$parent" ]] && vigil_protected_device "$parent"; then
        # Another partition may still be in use as storage.
        while IFS= read -r child; do
            mounts=$(findmnt -rn -S "$child" -o OPTIONS) || continue
            if grep -Eq '(^|,)rw(,|$)' <<< "$mounts"; then
                return 0
            fi
        done < <(lsblk -lnpo NAME "$parent")
        sudo blockdev --setro "$parent"
    fi
}

vigil_storage_lock() {
    # Legacy standalone invocation can run before post-installation.
    [[ -e /run/vigil-storage.lock ]] || return 0
    exec {vigil_storage_fd}</run/vigil-storage.lock || return 1
    flock -n -x "$vigil_storage_fd" || {
        vigil_storage_unlock
        echo "Une autre opération de stockage est en cours." >&2
        return 1
    }
}

vigil_storage_unlock() {
    if [[ -n "${vigil_storage_fd:-}" ]]; then
        exec {vigil_storage_fd}<&-
    fi
}
