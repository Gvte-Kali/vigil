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
        set -- --format symbols --colors 256 --size 32x12 "${1:-/opt/vigil/data/icons/vigil.svg}"
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

# Bash maintenance UI.
vigil_maintenance_language() {
    case "${VIGIL_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}}" in
        fr*) VIGIL_LANG=fr ;; *) VIGIL_LANG=en ;;
    esac
}
vigil_maintenance_start() {
    vigil_maintenance_language
    VIGIL_LOG=$(mktemp "$HOME/vigil-$1.XXXXXX.log") || return 1
    VIGIL_TOTAL=$2
    VIGIL_DONE=0
    VIGIL_STAGE=''
    VIGIL_STARTED=$SECONDS
    vigil_logo
    vigil_style '1;96' "$3"
    printf '%s: %s\n' "$(vigil_text Journal Log)" "$VIGIL_LOG"
}
vigil_maintenance_step() {
    if [ -n "$VIGIL_STAGE" ]; then
        VIGIL_DONE=$((VIGIL_DONE + 1))
        vigil_style 32 "[ OK ] $VIGIL_STAGE ($((SECONDS-VIGIL_STAGE_START))s)"
    fi
    VIGIL_STAGE=$1
    VIGIL_STAGE_START=$SECONDS
    vigil_maintenance_bar
}
vigil_maintenance_bar() {
    local percent filled bar
    percent=$((100 * VIGIL_DONE / VIGIL_TOTAL))
    filled=$((percent / 5))
    bar=$(printf '%*s' "$filled" '' | tr ' ' '#')$(printf '%*s' "$((20-filled))" '' | tr ' ' '-')
    vigil_style 36 "[$bar] $percent% | $VIGIL_STAGE"
}
vigil_maintenance_run() {
    # Keep the command in the foreground so sudo and signals retain their semantics.
    local ticker='' status=0
    if [ -t 1 ] && [ "${TERM:-dumb}" != dumb ]; then
        (
            trap 'exit 0' TERM INT
            while sleep 1; do
                printf '\r\033[2K[ ... ] %s (%ss)' "$VIGIL_STAGE" "$((SECONDS-VIGIL_STAGE_START))"
            done
        ) &
        ticker=$!
    fi
    "$@" >>"$VIGIL_LOG" 2>&1 || status=$?
    if [ -n "$ticker" ]; then
        kill "$ticker" 2>/dev/null || :
        wait "$ticker" 2>/dev/null || :
        printf '\r\033[2K'
    fi
    return "$status"
}
vigil_maintenance_finish() {
    vigil_maintenance_step "$(vigil_text Terminé Complete)"
    VIGIL_STAGE=''
    printf '%s: %ss\n' "$(vigil_text Durée Duration)" "$((SECONDS-VIGIL_STARTED))"
}
vigil_maintenance_exit() {
    local status=$1
    if [ "$status" -ne 0 ]; then
        vigil_style 31 "[ FAIL ] $VIGIL_STAGE"
        tail -n 20 "$VIGIL_LOG" >&2
        printf '%s: %s\n' "$(vigil_text Journal Log)" "$VIGIL_LOG" >&2
    fi
}
