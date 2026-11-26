# Shared preflight for the unmounted storage root. Never follows a symlink.
vigil_storage_root_check() {
    if [ ! -d "$1" ] || [ -L "$1" ] || [ "$(realpath -e -- "$1")" != "$1" ]; then
        vigil_text "$1 doit être un répertoire réel accessible." "$1 must be a real, accessible directory."
        return 1
    fi
    if ! metadata=$(stat -c '%u:%g:%a' -- "$1"); then
        vigil_text "Permissions de $1 non vérifiables." "Could not verify $1 permissions."
        return 1
    fi
    if [ "$metadata" != "0:0:755" ]; then
        vigil_text "$1 : propriétaire:groupe:mode $metadata, attendu 0:0:755 (root:root 0755)." \
                   "$1: owner:group:mode $metadata, expected 0:0:755 (root:root 0755)."
        return 1
    fi
}
