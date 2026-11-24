#!/usr/bin/bash
# Read the kernel mount view without traversing evidence directory trees.
read_investigation_mounts() {
    local targets entry target
    INVESTIGATION_MOUNTS=()
    targets=$(findmnt -rn -o TARGET) || return 1
    while IFS= read -r entry; do
        printf -v target '%b' "$entry"
        if [[ "$target" == "$1" || "$target" == "$1/"* ]]; then
            INVESTIGATION_MOUNTS+=("$target")
        fi
    done <<< "$targets"
}
