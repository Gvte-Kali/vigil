# Presentation for human-facing scripts. Safe to source from POSIX sh.
vigil_style() {
    if [ -t 1 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        printf '\033[%sm%s\033[0m\n' "$1" "$2"
    else
        printf '%s\n' "$2"
    fi
}

vigil_banner() {
    vigil_style 96 '█   █ ███  ███  ███ █
█   █  █  █      █  █
█   █  █  █  ██  █  █
 █ █   █  █   █  █  █
  █   ███  ███  ███ █████'
    printf '\n'
    vigil_style '1;96' "$1"
    printf '\n'
}
