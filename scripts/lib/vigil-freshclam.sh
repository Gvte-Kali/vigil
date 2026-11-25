# Grant FreshClam access only to Vigil's operator-owned signature directory.
vigil_prepare_freshclam() {
    local signature_dir="$1"
    local profile="${2:-/etc/apparmor.d/usr.bin.freshclam}"
    local local_profile="${3:-/etc/apparmor.d/local/usr.bin.freshclam}"
    local rule parser

    if [ "$(realpath -m -- "$signature_dir")" != "$signature_dir" ]; then
        printf 'Dossier de signatures non canonique / Noncanonical signature directory: %s\n' "$signature_dir" >&2
        return 1
    fi
    mkdir -p -m 0700 -- "$(dirname -- "$signature_dir")" "$signature_dir" || return 1
    [ -f "$profile" ] || return 0
    if [ -x /usr/sbin/apparmor_parser ]; then
        parser=/usr/sbin/apparmor_parser
    elif [ -x /sbin/apparmor_parser ]; then
        parser=/sbin/apparmor_parser
    elif ! parser=$(command -v apparmor_parser); then
        printf '%s\n' 'apparmor_parser indisponible / unavailable. Voir / See docs/configuration/clamav.md.' >&2
        return 1
    fi
    if ! grep -Eq '^[[:space:]]*#?include([[:space:]]+if exists)?[[:space:]]+<local/usr.bin.freshclam>' "$profile"; then
        printf 'FreshClam : inclusion locale manquante / missing local include: %s\n' "$profile" >&2
        return 1
    fi
    sudo install -d -m 0755 -- "$(dirname -- "$local_profile")" || return 1
    sudo touch -- "$local_profile" || return 1
    for rule in "owner $signature_dir/ rw," "owner $signature_dir/** rwk,"; do
        if ! sudo grep -Fxq -- "$rule" "$local_profile"; then
            printf '\n%s\n' "$rule" | sudo tee -a -- "$local_profile" >/dev/null || return 1
        fi
    done
    if [ "$(cat /sys/module/apparmor/parameters/enabled 2>/dev/null || true)" = Y ]; then
        sudo "$parser" -r "$profile" || return 1
    fi
}
