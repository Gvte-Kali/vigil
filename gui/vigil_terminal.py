"""Select a desktop terminal without assuming KDE or an APT distribution."""
import shutil
import subprocess

MISSING_TERMINAL = (
    "Aucun terminal compatible trouvé (xdg-terminal-exec, Konsole, "
    "GNOME Terminal, xfce4-terminal, kitty ou xterm)."
)


def terminal_command(arguments):
    for name, options in (
        ("xdg-terminal-exec", ()),
        ("konsole", ("-e",)),
        ("gnome-terminal", ("--",)),
        ("xfce4-terminal", ("--execute",)),
        ("kitty", ()),
        ("xterm", ("-e",)),
    ):
        executable = shutil.which(name)
        if executable:
            return [executable, *options, *arguments]
    raise FileNotFoundError(MISSING_TERMINAL)


def launch_terminal(arguments):
    return subprocess.Popen(terminal_command(arguments))


def launch_script(path, *arguments):
    wrapper = (
        '"$@"; rc=$?; '
        'if [ "$rc" -eq 0 ]; then printf "\\nOutil terminé.\\n"; '
        'else printf "\\nÉchec de l’outil (code %s).\\n" "$rc"; fi; '
        'read -r -p "Appuyez sur Entrée pour fermer..."; exit "$rc"'
    )
    return launch_terminal(["bash", "-c", wrapper, "vigil", "bash", path, *arguments])
