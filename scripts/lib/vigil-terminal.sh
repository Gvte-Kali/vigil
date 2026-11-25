# Presentation for human-facing scripts. Safe to source from POSIX sh.
vigil_style() {
    if [ -t 1 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        printf '\033[%sm%s\033[0m\n' "$1" "$2"
    else
        printf '%s\n' "$2"
    fi
}

vigil_logo() {
    if [ -t 1 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        set -- --format symbols --colors 256 --size 40x20 "${1:-/opt/vigil/data/icons/vigil.svg}"
        if [ "$(id -u)" = 0 ]; then
            # Parse the SVG without administrator privileges.
            case "${SUDO_UID:-}:${SUDO_GID:-}" in
                :*|*:|*[!0-9:]*|0:*) ;;
                *) /usr/bin/setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --clear-groups \
                       /usr/bin/chafa "$@" 2>/dev/null && return 0 ;;
            esac
            /usr/sbin/runuser -u nobody -- /usr/bin/chafa "$@" 2>/dev/null && return 0
        elif command -v chafa >/dev/null 2>&1; then
            chafa "$@" 2>/dev/null && return 0
        fi
    fi
    vigil_style 96 'Vigil'
}

vigil_banner() {
    vigil_logo
    printf '\n'
    vigil_style '1;96' "$1"
    printf '\n'
}
