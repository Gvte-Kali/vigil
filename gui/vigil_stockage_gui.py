#!/usr/bin/env python3
"""Page de montage de stockage.

Permet de monter un peripherique de stockage en lecture/ecriture dans
/stockage. Une pop-up d'avertissement rappelle de ne PAS utiliser ce menu pour
un peripherique a analyser (il faut utiliser le menu "Analyse USB / Disque Dur
/ CD" qui monte en lecture seule).
"""

import os
import subprocess
import tkinter as tk
from tkinter import messagebox

import vigil_data
import vigil_gui_base as base
from vigil_gui_base import (
    VigilWindow,
    Section,
    ActionButton,
    icon_label,
    header_title,
    mounted_children,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLOR_ACCENT,
    COLOR_SUCCESS,
    COLOR_DANGER,
    CategoryButton,
    accent_button,
    FONT_BODY,
    FONT_BUTTON,
    FONT_SMALL,
    PAD,
    WIDGET_PAD,
    NAV,
)


def _run_script_in_konsole(script_path, user, project):
    if not os.path.exists(script_path):
        messagebox.showerror("Erreur", f"Script introuvable : {script_path}")
        return
    vigil_data.set_active(user, project if project else "(no-project)")
    try:
        subprocess.Popen([
            "konsole", "-e", "bash", "-c",
            f"bash {script_path}; rc=$?; "
            f"if [ $rc -eq 0 ]; then echo -e '\\n\\e[92m"
            f"✓ Outil terminé. Appuyez sur Entrée pour fermer...\\e[0m'; "
            f"else echo -e '\\n\\e[91m"
            f"✕ Outil terminé avec une erreur. Appuyez sur Entrée pour fermer...\\e[0m'; fi; "
            f"read"
        ])
    except FileNotFoundError:
        messagebox.showerror("Erreur",
                             "Konsole absent. Installez-le : sudo apt install konsole")
    except Exception as exc:
        messagebox.showerror("Erreur", f"Échec du lancement : {exc}")



def _stockage_is_mounted():
    """Renvoie True si au moins un périphérique est monté dans /stockage."""
    return bool(mounted_children("/stockage"))


def show_stockage_view():
    def _guard_mounted():
        if _stockage_is_mounted():
            messagebox.showwarning(
                "Périphérique toujours monté",
                "Un périphérique est toujours monté dans /stockage.\n\n"
                "Veuillez le démonter via le bouton « Démonter le "
                "périphérique » avant de quitter cette page, afin "
                "d'éviter toute mauvaise manipulation.")
            return True
        return False

    window = VigilWindow(nav_label="Stockage", geometry="900x600",
                         resizable=True, close_guard=_guard_mounted)

    topbar = tk.Frame(window.body, bg=COLOR_BG)
    topbar.pack(fill=tk.X, pady=(0, PAD))
    ActionButton(topbar, "Accueil",
                 lambda: window.go_back("vigil_main_gui.py",
                                         nav_label="Vigil"),
                 icon="home").pack(side=tk.LEFT)
    icon_label(topbar, "Stockage", "database",
               ("Segoe UI", 18, "bold"), COLOR_BG, COLOR_TEXT).pack(
        side=tk.LEFT, padx=(WIDGET_PAD, 0))

    header_title(
        window.body,
        text="Montage de stockage",
        subtitle="Monter un périphérique en lecture/écriture dans /stockage",
        icon="database",
    ).pack(fill=tk.X, pady=(0, PAD))

    warning = tk.Frame(window.body, bg=COLOR_SURFACE, highlightbackground="#f7768e",
                       highlightthickness=1, bd=0)
    warning.pack(fill=tk.X, pady=(0, PAD))
    icon_label(
        warning,
        "Avertissement",
        "triangle-alert",
        ("Segoe UI", 12, "bold"), COLOR_SURFACE, "#f7768e",
    ).pack(fill=tk.X, padx=PAD, pady=(PAD, WIDGET_PAD))
    tk.Label(
        warning,
        text=("Ce menu monte un périphérique en LECTURE/ÉCRITURE dans /stockage. "
              "Il est réservé au stockage de fichiers de travail.\n\n"
              "Ne montez JAMAIS ici un périphérique à analyser : utilisez plutôt "
              "le menu \"Analyse USB / Disque Dur / CD\" qui monte en lecture "
              "seule pour préserver la chaîne de custody."),
        font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
        anchor="w", justify="left",
    ).pack(fill=tk.X, padx=PAD, pady=(0, PAD))

    actions = Section(window.body, "Actions", icon="plug")
    actions.pack(fill=tk.X, pady=(0, PAD))

    user = ""
    project = ""
    try:
        active_user_file = vigil_data.ACTIVE_USER
        if os.path.isfile(active_user_file):
            with open(active_user_file, "r", encoding="utf-8") as fh:
                user = fh.read().strip()
        active_project_file = vigil_data.ACTIVE_PROJECT
        if os.path.isfile(active_project_file):
            with open(active_project_file, "r", encoding="utf-8") as fh:
                project = fh.read().strip()
    except OSError:
        pass

    def do_mount():
        confirm = messagebox.askyesno(
            "Confirmer le montage",
            "Vous allez monter un périphérique en LECTURE/ÉCRITURE dans "
            "/stockage.\n\n"
            "Ce périphérique n'est PAS destiné à l'analyse forensique.\n"
            "Pour analyser un périphérique, utilisez le menu \"Analyse USB / "
            "Disque Dur / CD\".\n\n"
            "Continuer ?")
        if not confirm:
            return
        script = os.path.join(vigil_data.SCRIPTS_DIR,
                              "stockage", "vigil_stockage_mount.sh")
        _run_script_in_konsole(script, user or "(no-user)",
                               project if project else "(no-project)")

    def do_umount():
        script = os.path.join(vigil_data.SCRIPTS_DIR,
                              "stockage", "vigil_stockage_umount.sh")
        _run_script_in_konsole(script, user or "(no-user)",
                               project if project else "(no-project)")

    accent_button(
        actions.content, COLOR_SUCCESS,
        lambda _p: CategoryButton(
            _p,
            "Monter un périphérique",
            command=do_mount,
            subtitle="Monter en lecture/écriture dans /stockage",
            success=True,
        ),
        icon_name="plug",
    )
    accent_button(
        actions.content, COLOR_DANGER,
        lambda _p: CategoryButton(
            _p,
            "Démonter le périphérique",
            command=do_umount,
            subtitle="Démonter les périphériques de /stockage",
            danger=True,
        ),
        icon_name="log-out",
    )

    return window


def main():
    show_stockage_view()


if __name__ == "__main__":
    main()
    base.run_mainloop()
