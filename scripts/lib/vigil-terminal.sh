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

vigil_text() {
    if [ "${VIGIL_LANG:-fr}" = en ]; then
        printf '%s' "$2"
    else
        printf '%s' "$1"
    fi
}

# For internal stage identifiers and numeric/ASCII details only.
vigil_progress_frame() {
    printf '\036VIGIL_PROGRESS {"stage":"%s","percent":%d,"detail":"%s","done":%s}\n' \
        "$1" "$2" "$3" "${4:-false}"
}

# Bash maintenance UI; existing POSIX callers need not invoke these functions.
vigil_maintenance_start() {
    VIGIL_LOG=$(mktemp "$HOME/vigil-$1.XXXXXX.log") || return 1
    VIGIL_TOTAL=$2
    VIGIL_DONE=0
    VIGIL_STAGE=''
    vigil_banner "$3"
    printf 'Log: %s\n' "$VIGIL_LOG"
}
vigil_maintenance_step() {
    if [ -n "$VIGIL_STAGE" ]; then
        VIGIL_DONE=$((VIGIL_DONE + 1))
        if [ -t 1 ] && [ "${TERM:-dumb}" != dumb ]; then printf '\r\033[2K'; fi
        vigil_style 32 "[ OK ] $VIGIL_STAGE"
    fi
    VIGIL_STAGE=$1
    vigil_maintenance_bar
}
vigil_maintenance_bar() {
    local percent filled bar
    percent=$((100 * VIGIL_DONE / VIGIL_TOTAL))
    filled=$((percent / 5))
    bar=$(printf '%20s' '' | tr ' ' '-')
    if [ "$filled" -gt 0 ]; then
        bar=$(printf '%*s' "$filled" '' | tr ' ' '#')$(printf '%*s' "$((20-filled))" '' | tr ' ' '-')
    fi
    printf '[%s] %3d%% | %s' "$bar" "$percent" "$VIGIL_STAGE"
    if [ ! -t 1 ] || [ "${TERM:-dumb}" = dumb ]; then printf '\n'; fi
}
vigil_maintenance_run() {
    "$@" >>"$VIGIL_LOG" 2>&1
}
vigil_maintenance_finish() {
    vigil_maintenance_step 'Terminé / Complete'
    printf '\n'
}
vigil_maintenance_exit() {
    local status=$1
    if [ "$status" -ne 0 ]; then
        printf '\n'
        vigil_style 31 "[ FAIL ] $VIGIL_STAGE"
        tail -n 20 "$VIGIL_LOG" >&2
        printf 'Log: %s\n' "$VIGIL_LOG" >&2
    fi
}
