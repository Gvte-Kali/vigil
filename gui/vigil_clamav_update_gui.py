#!/usr/bin/env python3
"""Page de mise a jour de ClamAV.

Deux boutons :
  1. Mise a jour en ligne (freshclam) -- le script vigil_clamav_update.sh ;
  2. Mise a jour par peripherique USB -- le script vigil_clamav_update_usb.sh
     pour les postes isoles.
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
    CategoryButton,
    accent_button,
    icon_label,
    header_title,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLOR_ACCENT,
    COLOR_SUCCESS,
    COLOR_DANGER,
    FONT_BODY,
    FONT_BUTTON,
    FONT_SMALL,
    PAD,
    WIDGET_PAD,
)


def _run_script_in_konsole(script_path):
    if not os.path.exists(script_path):
        messagebox.showerror("Erreur", f"Script introuvable : {script_path}")
        return
    try:
        subprocess.Popen([
            "konsole", "-e", "bash", "-c",
            f"bash {script_path}; rc=$?; "
            f"if [ $rc -eq 0 ]; then echo -e '\\n\\e[92m"
            f"✓ Mise à jour terminée. Appuyez sur Entrée pour fermer...\\e[0m'; "
            f"else echo -e '\\n\\e[91m"
            f"✕ Mise à jour terminée avec une erreur. Appuyez sur Entrée pour fermer...\\e[0m'; fi; "
            f"read"
        ])
    except FileNotFoundError:
        messagebox.showerror("Erreur",
                             "Konsole absent. Installez-le : sudo apt install konsole")
    except Exception as exc:
        messagebox.showerror("Erreur", f"Échec du lancement : {exc}")



def show_clamav_update_view():
    window = VigilWindow(nav_label="ClamAV", geometry="900x600",
                         resizable=True)

    topbar = tk.Frame(window.body, bg=COLOR_BG)
    topbar.pack(fill=tk.X, pady=(0, PAD))
    ActionButton(topbar, "Accueil",
                 lambda: window.go_back("vigil_main_gui.py",
                                         nav_label="Vigil"),
                 icon="home").pack(side=tk.LEFT)
    icon_label(topbar, "Mise à jour ClamAV", "flask-conical",
               ("Segoe UI", 18, "bold"), COLOR_BG, COLOR_TEXT).pack(
        side=tk.LEFT, padx=(WIDGET_PAD, 0))

    header_title(
        window.body,
        text="Mise à jour de l'antivirus ClamAV",
        subtitle="Télécharger les signatures virales en ligne ou depuis une clé USB",
        icon="flask-conical",
    ).pack(fill=tk.X, pady=(0, PAD))

    info = tk.Frame(window.body, bg=COLOR_SURFACE, highlightbackground=COLOR_ACCENT,
                    highlightthickness=1, bd=0)
    info.pack(fill=tk.X, pady=(0, PAD))
    icon_label(
        info,
        "Information",
        "info",
        ("Segoe UI", 12, "bold"), COLOR_SURFACE, COLOR_ACCENT,
    ).pack(fill=tk.X, padx=PAD, pady=(PAD, WIDGET_PAD))
    tk.Label(
        info,
        text=("La base de signatures virales doit être à jour pour que les "
              "scans Antivirus soient fiables.\n\n"
              "• En ligne : téléchargement direct via freshclam (machine "
              "connectée à Internet).\n"
              "• Par clé USB : pour les postes isolés, les fichiers "
              "bytecode.cvd, daily.cvd et main.cvd sont copiés depuis une "
              "clé USB branchée à la main."),
        font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
        anchor="w", justify="left",
    ).pack(fill=tk.X, padx=PAD, pady=(0, PAD))

    actions = Section(window.body, "Actions", icon="list")
    actions.pack(fill=tk.X, pady=(0, PAD))

    update_online = os.path.join(vigil_data.SCRIPTS_DIR,
                                  "clamav", "vigil_clamav_update.sh")
    update_usb = os.path.join(vigil_data.SCRIPTS_DIR,
                               "clamav", "vigil_clamav_update_usb.sh")

    def do_online():
        confirm = messagebox.askyesno(
            "Mise à jour en ligne",
            "Lancer la mise à jour en ligne des signatures ClamAV ?\n\n"
            "La machine doit être connectée à Internet.\n"
            "Le mot de passe administrateur sera demandé.")
        if confirm:
            _run_script_in_konsole(update_online)

    def do_usb():
        confirm = messagebox.askyesno(
            "Mise à jour par clé USB",
            "Lancer la mise à jour des signatures ClamAV depuis une clé USB ?\n\n"
            "Le script vous demandera de débrancher puis de rebrancher la clé "
            "contenant les fichiers de base.\n"
            "Le mot de passe administrateur sera demandé.")
        if confirm:
            _run_script_in_konsole(update_usb)

    accent_button(
        actions.content, COLOR_SUCCESS,
        lambda _p: CategoryButton(
            _p,
            "Mise à jour en ligne",
            command=do_online,
            subtitle="Téléchargement direct via freshclam (machine connectée)",
            success=True,
        ),
        icon_name="upload",
    )
    accent_button(
        actions.content, COLOR_ACCENT,
        lambda _p: CategoryButton(
            _p,
            "Mise à jour par clé USB",
            command=do_usb,
            subtitle="Postes isolés : copie des fichiers .cvd depuis une clé USB",
        ),
        icon_name="database",
    )

    return window


def main():
    show_clamav_update_view()


if __name__ == "__main__":
    main()
    base.run_mainloop()
