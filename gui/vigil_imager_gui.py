#!/usr/bin/env python3
"""Page de copie forensique de disque.

Permet de réaliser une image forensique (RAW, E01 ou AFF) d'un
disque source vers un disque cible externe ou un emplacement local. Le script
shell scripts/imager/vigil_disk_imager.sh gère l'interaction CLI (choix du
disque source, format de sortie, cible, acquisition).
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
    COLOR_BG,
    COLOR_SURFACE,
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
            f"\u2713 Outil terminé. Appuyez sur Entrée pour fermer...\\e[0m'; "
            f"else echo -e '\\n\\e[91m"
            f"\u2715 Outil terminé avec une erreur. Appuyez sur Entrée pour fermer...\\e[0m'; fi; "
            f"read"
        ])
    except FileNotFoundError:
        messagebox.showerror("Erreur",
                             "Konsole absent. Installez-le : sudo apt install konsole")
    except Exception as exc:
        messagebox.showerror("Erreur", f"Échec du lancement : {exc}")



def show_imager_view():
    window = VigilWindow(nav_label="Imagerie", geometry="900x600",
                         resizable=True)

    topbar = tk.Frame(window.body, bg=COLOR_BG)
    topbar.pack(fill=tk.X, pady=(0, PAD))
    ActionButton(topbar, "Accueil",
                 lambda: window.go_back("vigil_main_gui.py",
                                         nav_label="Vigil"),
                 icon="home").pack(side=tk.LEFT)
    icon_label(topbar, "Imagerie", "hard-drive",
               ("Segoe UI", 18, "bold"), COLOR_BG, COLOR_TEXT).pack(
        side=tk.LEFT, padx=(WIDGET_PAD, 0))

    header_title(
        window.body,
        text="Copie forensique de disque",
        subtitle="Réaliser une image forensique (RAW/E01/AFF) d'un disque",
        icon="hard-drive",
    ).pack(fill=tk.X, pady=(0, PAD))

    warning = tk.Frame(window.body, bg=COLOR_SURFACE, highlightbackground="#7aa2f7",
                       highlightthickness=1, bd=0)
    warning.pack(fill=tk.X, pady=(0, PAD))
    icon_label(
        warning,
        "Information",
        "info",
        ("Segoe UI", 12, "bold"), COLOR_SURFACE, "#7aa2f7",
    ).pack(fill=tk.X, padx=PAD, pady=(PAD, WIDGET_PAD))
    tk.Label(
        warning,
        text=("Ce menu réalise une image forensique d'un disque source amovible "
              "(clé USB, disque externe). Les disques internes et le disque "
              "système ne sont jamais proposés.\n\n"
              "Le disque source est accédé en lecture seule afin de préserver "
              "l'intégrité de la preuve.\n\n"
              "Formats de sortie disponibles :\n"
              "  • RAW (dc3dd) — .raw/.dd/.img — copie bit-à-bit + hash SHA-256\n"
              "    (l'extension est choisie après le format : .raw, .dd ou .img)\n"
              "  • E01 (ewfacquire) — .E01 — compression + hash + métadonnées\n"
              "  • AFF (afflib) — .aff — format ouvert + chiffrement optionnel\n\n"
              "La cible peut être un disque externe (recommandé) ou un "
              "emplacement local (une réserve de 20% du disque système est "
              "obligatoirement conservée)."),
        font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
        anchor="w", justify="left",
    ).pack(fill=tk.X, padx=PAD, pady=(0, PAD))

    actions = Section(window.body, "Actions", icon="hard-drive")
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

    def do_image():
        confirm = messagebox.askyesno(
            "Confirmer la copie forensique",
            "Vous allez lancer une copie forensique d'un disque.\n\n"
            "Le script demandera le disque source, le format de sortie, "
            "puis la cible de stockage (disque externe ou local).\n\n"
            "Continuer ?")
        if not confirm:
            return
        script = os.path.join(vigil_data.SCRIPTS_DIR,
                              "imager", "vigil_disk_imager.sh")
        _run_script_in_konsole(script, user or "(no-user)",
                               project if project else "(no-project)")

    accent_button(
        actions.content, COLOR_SUCCESS,
        lambda _p: CategoryButton(
            _p,
            "Lancer la copie forensique",
            command=do_image,
            subtitle="Image forensique (RAW/E01/AFF) d'un disque vers cible externe ou locale",
            success=True,
        ),
        icon_name="copy",
    )

    return window


def main():
    show_imager_view()


if __name__ == "__main__":
    main()
    base.run_mainloop()
