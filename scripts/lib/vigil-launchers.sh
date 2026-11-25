# Launcher ownership checks and publication for the site installer.
launcher_conflict() {
    printf 'Vigil: conflit de lanceur / launcher conflict: %s\n' "$1" >&2
    return 1
}

vigil_wrapper() {
    local file="$1" target="$2" site="$3" interpreter
    [ -f "$file" ] && [ ! -L "$file" ] && [ "$(stat -c '%s' -- "$file")" -le 1024 ] || return 1
    IFS= read -r interpreter < "$file" || return 1
    case "$interpreter" in
        "#!$site/.venv/bin/python"|"#!$site/.venv/bin/python3"|"#!$site/.venv/bin/python3."[0-9]*) ;;
        *) return 1 ;;
    esac
    local module="${target%:*}" function="${target#*:}"
    cmp -s -- "$file" <(printf '%s\n' "$interpreter" '# -*- coding: utf-8 -*-' 'import re' 'import sys' \
        "from $module import $function" "if __name__ == '__main__':" \
        "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])" "    sys.exit($function())")
}

vigil_owned_launcher() {
    local file="$1" site="$2" target
    if [ -L "$file" ]; then
        target=$(readlink -- "$file") || return 1
        case "$target" in /*) ;; *) target="$(dirname -- "$file")/$target" ;; esac
        case "$(realpath -sm -- "$target")" in
            "$site/.venv/bin/vigil"|"$site/.venv/bin/vigil-gui"|\
            "$site/.venv/bin/vigil2"|"$site/.venv/bin/vigil2-gui"|\
            "$site/scripts/post-install/vigil-qt"|"$site/gui/vigil_main_gui.py"|\
            "$site/scripts/Vigil-CLI/vigil") return 0 ;;
        esac
        return 1
    fi
    vigil_wrapper "$file" vigil.cli:app "$site" ||
        vigil_wrapper "$file" vigil.session:main "$site" ||
        vigil_wrapper "$file" vigil.desktop:main "$site" ||
        { [ -f "$file" ] && { cmp -s -- "$file" "$site/scripts/Vigil-CLI/vigil" ||
                             cmp -s -- "$file" "$site/scripts/post-install/vigil-qt"; }; }
}

vigil_managed_desktop() {
    local file="$1" site="$2" local_bin="$3"
    [ ! -L "$file" ] && [ -f "$file" ] && [ "$(grep -c '^Exec=' "$file")" -eq 1 ] &&
        grep -Fxq '[Desktop Entry]' "$file" && grep -Fxq 'Name=Vigil' "$file" &&
        grep -Fxq 'Type=Application' "$file" &&
        grep -Fxq -e "Exec=$local_bin/vigil" -e "Exec=$local_bin/vigil-gui" -e "Exec=$site/scripts/post-install/vigil-qt" \
            -e "Exec=python3 $site/gui/vigil_main_gui.py" "$file"
}

vigil_launchers_preflight() {
    local site="$1" local_bin="$2" system_bin="$3" desktop="$4" file
    for file in "$local_bin/vigil" "$local_bin/vigil-gui" "$system_bin/vigil" "$site/.venv/bin/vigil" "$site/.venv/bin/vigil-gui" \
                "$site/.venv/bin/vigil2" "$site/.venv/bin/vigil2-gui" "$HOME/.local/bin/vigil"; do
        if [ -e "$file" ] || [ -L "$file" ]; then
            vigil_owned_launcher "$file" "$site" || { launcher_conflict "$file"; return 1; }
        fi
    done
    file=$(type -P vigil || true)
    if [ -n "$file" ]; then
        file="$(realpath -m -- "$(dirname -- "$file")")/${file##*/}"
    fi
    case "$file" in
        ""|"$local_bin/vigil"|"$system_bin/vigil"|"$site/.venv/bin/vigil"|"$HOME/.local/bin/vigil") ;;
        *) launcher_conflict "$file (PATH)"; return 1 ;;
    esac
    if [ -e "$desktop" ] || [ -L "$desktop" ]; then
        vigil_managed_desktop "$desktop" "$site" "$local_bin" || { launcher_conflict "$desktop"; return 1; }
    fi
}

vigil_publish_link() {
    if [ -e "$2" ] || [ -L "$2" ]; then
        sudo ln -sfnT -- "$1" "$2"
    else
        sudo ln -sT -- "$1" "$2"
    fi
}

vigil_publish_launchers() {
    local site="$1" local_bin="$2" system_bin="$3" desktop="$4" file temporary
    vigil_launchers_preflight "$@" || return 1
    vigil_wrapper "$site/.venv/bin/vigil" vigil.cli:app "$site" ||
        { launcher_conflict "$site/.venv/bin/vigil"; return 1; }
    vigil_wrapper "$site/.venv/bin/vigil-gui" vigil.session:main "$site" ||
        { launcher_conflict "$site/.venv/bin/vigil-gui"; return 1; }
    "$site/.venv/bin/vigil" --version || return 1
    vigil_publish_link "$site/.venv/bin/vigil" "$local_bin/vigil" || return 1
    vigil_publish_link "$site/scripts/post-install/vigil-qt" "$local_bin/vigil-gui" || return 1
    # An older PATH entry must not continue to open Tk or Qt.
    for file in "$system_bin/vigil" "$system_bin/vigil2" "$local_bin/vigil2" \
                "$system_bin/vigil2-gui" "$local_bin/vigil2-gui"; do
        if [ -e "$file" ] || [ -L "$file" ]; then
            if vigil_owned_launcher "$file" "$site"; then
                sudo rm -- "$file" || return 1
            else
                printf 'Vigil: lanceur tiers conservé / third-party launcher retained: %s\n' "$file" >&2
            fi
        fi
    done
    for file in "$HOME/.local/bin/vigil" "$site/.venv/bin/vigil2" "$site/.venv/bin/vigil2-gui" \
                "$HOME/.local/bin/vigil2" "$HOME/.local/bin/vigil2-gui"; do
        if { [ -e "$file" ] || [ -L "$file" ]; } && vigil_owned_launcher "$file" "$site"; then
            rm -- "$file" || return 1
        fi
    done
    if [ -f "$desktop" ]; then
        temporary=$(mktemp) || return 1
        if ! awk -v launcher="$local_bin/vigil-gui" \
                '/^Exec=/ { $0 = "Exec=" launcher } { print }' "$desktop" > "$temporary" ||
           ! sudo install -m 0644 -- "$temporary" "$desktop"; then
            rm -- "$temporary"
            return 1
        fi
        rm -- "$temporary"
    fi
    "$local_bin/vigil" --help >/dev/null || return 1
    hash -r
    file=$(type -P vigil || true)
    if [ -z "$file" ] || [ "$(realpath -m -- "$file")" != "$site/.venv/bin/vigil" ]; then
        printf 'Vigil: PATH utilise / resolves to %s. Ajoutez / add %s to PATH.\n' "${file:-(none)}" "$local_bin" >&2
        return 1
    fi
}

vigil_install_cli() {
    local site="$1"
    vigil_launchers_preflight "$@" || return 1
    if [ ! -x "$site/.venv/bin/python" ]; then
        python3 -m venv "$site/.venv" || return 1
    fi
    "$site/.venv/bin/python" -m pip install -e "$site[desktop]" || return 1
    vigil_publish_launchers "$@"
}
