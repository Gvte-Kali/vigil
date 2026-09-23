#!/usr/bin/env python3
"""Interface principale de Vigil.

Page d'accueil avec categories : Configuration (configuration systeme +
projets), Actions (analyse des périphériques, stockage). La hierarchie des
fenetres est refletee dans le titre de la fenetre.
"""

import os
import subprocess
import tkinter as tk
from tkinter import messagebox

import vigil_data
import vigil_icons as icons
import vigil_gui_base as base
from vigil_gui_base import (
    VigilWindow,
    Section,
    ActionButton,
    CategoryButton,
    accent_button,
    header_title,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_ACCENT,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    FONT_BODY,
    FONT_TITLE,
    FONT_SMALL,
    PAD,
    WIDGET_PAD,
    quit_app,
    NAV,
)


_ACCENT_CONFIG = "#bb9af7"   # violet — configuration
_ACCENT_PROJET = "#9d7cd8"  # violet profond — projets
_ACCENT_AV_UPDATE = "#e0af68"  # ambre — mise à jour ClamAV
_ACCENT_USB = "#73daca"       # turquoise — périphériques USB
_ACCENT_ANALYSE = COLOR_ACCENT  # bleu — analyse
_ACCENT_STOCKAGE = "#7dcfff"   # cyan clair — stockage
_ACCENT_IMAGER = "#7dcfff"     # cyan clair — imagerie
_ACCENT_AV_SCAN = COLOR_SUCCESS  # vert — recherche de menaces
_ACCENT_QUIT = COLOR_DANGER


def _run_script_in_konsole(script_path, user, project):
    if not os.path.exists(script_path):
        messagebox.showerror("Erreur", f"Script introuvable : {script_path}")
        return
    if user is not None:
        vigil_data.set_active(user, project if project else "(no-project)")
    try:
        subprocess.Popen([
            "konsole", "-e", "bash", "-c",
            f"bash {script_path}; rc=$?; "
            f"if [ $rc -eq 0 ]; then echo -e '\\n\\e[92m"
            f"\u2713 Outil termin\u00e9. Appuyez sur Entr\u00e9e pour fermer...\\e[0m'; "
            f"else echo -e '\\n\\e[91m"
            f"\u2715 Outil termin\u00e9 avec une erreur. Appuyez sur Entr\u00e9e pour fermer...\\e[0m'; fi; "
            f"read"
        ])
    except FileNotFoundError:
        messagebox.showerror("Erreur",
                             "Konsole absent. Installez-le : sudo apt install konsole")
    except Exception as exc:
        messagebox.showerror("Erreur", f"\u00c9chec du lancement : {exc}")


def _active_user_project():
    user = ""
    project = ""
    try:
        if os.path.isfile(vigil_data.ACTIVE_USER):
            with open(vigil_data.ACTIVE_USER, "r", encoding="utf-8") as fh:
                user = fh.read().strip()
        if os.path.isfile(vigil_data.ACTIVE_PROJECT):
            with open(vigil_data.ACTIVE_PROJECT, "r", encoding="utf-8") as fh:
                project = fh.read().strip()
    except OSError:
        pass
    return user, project


def build_home():
    window = VigilWindow(nav_label="Vigil", geometry="500x820", resizable=False)

    # En-tête avec le logo Vigil en grand (64x64) pour l'identité visuelle.
    logo_frame = tk.Frame(window.body, bg=COLOR_BG)
    logo_frame.pack(fill=tk.X, pady=(0, PAD))
    _vigil_logo = icons.get_icon("vigil", 64)
    if _vigil_logo is not None:
        tk.Label(logo_frame, image=_vigil_logo, bg=COLOR_BG).pack()
        # Conserver la référence hors ramasse-miette.
        logo_frame._vigil_logo = _vigil_logo
    tk.Label(
        logo_frame,
        text="Vigil",
        font=FONT_TITLE,
        bg=COLOR_BG,
        fg=COLOR_TEXT,
    ).pack()
    tk.Label(
        logo_frame,
        text="Analyse forensique sécurisée de périphériques USB",
        font=FONT_SMALL,
        bg=COLOR_BG,
        fg=COLOR_TEXT_DIM,
    ).pack()

    config = Section(window.body, "Configuration", icon="settings")
    config.pack(fill=tk.X, pady=(0, PAD))

    accent_button(
        config.content, _ACCENT_CONFIG,
        lambda _p: CategoryButton(
            _p,
            "Configuration du système",
            command=lambda: window.open_child("vigil_config_gui.py", nav_label="Configuration"),
            subtitle="Entité, coordonnées, logo et utilisateurs",
        ),
        icon_name="settings",
    )

    accent_button(
        config.content, _ACCENT_PROJET,
        lambda _p: CategoryButton(
            _p,
            "Gérer les projets",
            command=lambda: window.open_child("vigil_project_manager.py", nav_label="Configuration"),
            subtitle="Créer / modifier les projets",
        ),
        icon_name="folder",
    )

    accent_button(
        config.content, _ACCENT_USB,
        lambda _p: CategoryButton(
            _p,
            "Périphériques USB",
            command=lambda: window.open_child(
                "vigil_usb_gui.py", nav_label="Configuration"),
            subtitle="Inventaire USB, whitelist et blacklist du triage",
        ),
        icon_name="usb",
    )
    accent_button(
        config.content, _ACCENT_AV_UPDATE,
        lambda _p: CategoryButton(
            _p,
            "Mettre à jour l'antivirus ClamAV",
            command=lambda: window.open_child("vigil_clamav_update_gui.py", nav_label="ClamAV"),
            subtitle="Mettre à jour les signatures virales (en ligne ou par clé USB)",
        ),
        icon_name="flask-conical",
    )

    outils = Section(window.body, "Actions", icon="list")
    outils.pack(fill=tk.X, pady=(0, PAD))

    def do_threat_hunt():
        confirm = messagebox.askyesno(
            "Confirmer la recherche de menaces",
            "Vous allez lancer une recherche de menaces complète :\n\n"
            "1. Montage du périphérique dans /investigation (lecture seule)\n"
            "2. Recensement des fichiers + détection des extensions trompeuses\n"
            "3. Analyse ciblée des fichiers suspects (contenu, entropie, binwalk)\n"
            "4. Scan antivirus ClamAV sur tous les fichiers\n"
            "5. Démontage du périphérique\n\n"
            "Un rapport PDF unique récapitule toutes les menaces détectées.\n"
            "L'utilisateur vous sera demandé dans le terminal.\n\n"
            "Continuer ?")
        if not confirm:
            return
        script = os.path.join(vigil_data.SCRIPTS_DIR,
                              "clamav", "vigil_malware_hunt.sh")
        _run_script_in_konsole(script, None, None)

    accent_button(
        outils.content, _ACCENT_AV_SCAN,
        lambda _p: CategoryButton(
            _p,
            "Recherche de menaces",
            command=do_threat_hunt,
            subtitle="Monter, recenser, auditer les fichiers suspects, "
                     "scanner (ClamAV), démonter — en une seule action",
        ),
        icon_name="shield",
    )
    accent_button(
        outils.content, _ACCENT_ANALYSE,
        lambda _p: CategoryButton(
            _p,
            "Analyser un périphérique",
            command=lambda: window.open_child("vigil_tools_gui.py", nav_label="Analyse du périphérique USB"),
            subtitle="Monter en lecture seule et analyser un périphérique",
        ),
        icon_name="search",
    )

    accent_button(
        outils.content, _ACCENT_STOCKAGE,
        lambda _p: CategoryButton(
            _p,
            "Monter un périphérique de stockage",
            command=lambda: window.open_child("vigil_stockage_gui.py", nav_label="Stockage"),
            subtitle="Monter un périphérique en lecture/écriture dans /stockage",
        ),
        icon_name="database",
    )

    accent_button(
        outils.content, _ACCENT_IMAGER,
        lambda _p: CategoryButton(
            _p,
            "Faire une copie forensique d'un disque",
            command=lambda: window.open_child("vigil_imager_gui.py", nav_label="Imagerie"),
            subtitle="Image forensique (RAW/E01/AFF) d'un disque vers cible externe ou locale",
        ),
        icon_name="copy",
    )

    def do_disk_clone():
        user, project = _active_user_project()
        confirm = messagebox.askyesno(
            "Confirmer le clonage",
            "Vous allez cloner un disque source vers un disque cible.\n\n"
            "Le disque cible sera ENTIÈREMENT ÉCRASÉ.\n\n"
            "Le disque source est accédé en lecture seule.\n"
            "Le mot de passe administrateur sera demandé.\n\n"
            "Continuer ?")
        if not confirm:
            return
        script = os.path.join(vigil_data.SCRIPTS_DIR,
                              "imager", "vigil_disk_clone.sh")
        _run_script_in_konsole(script, user or "(no-user)", project if project else "(no-project)")

    accent_button(
        outils.content, _ACCENT_IMAGER,
        lambda _p: CategoryButton(
            _p,
            "Cloner un disque dur sur un autre périphérique",
            command=do_disk_clone,
            subtitle="Copie bit-à-bit d'un disque vers un autre (cible écrasée)",
        ),
        icon_name="copy",
    )


    footer = tk.Frame(window.body, bg=COLOR_BG)
    footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(PAD, 0))
    tk.Label(
        footer,
        text="Sélectionnez une catégorie pour commencer.",
        font=FONT_SMALL,
        bg=COLOR_BG,
        fg=COLOR_TEXT_DIM,
    ).pack(side=tk.LEFT)

    quit_btn = ActionButton(
        footer,
        "Quitter",
        quit_app,
        danger=True,
        icon="power",
    )
    quit_btn.bind("<Enter>", lambda _e: quit_btn.configure(bg="#ff8da3"))
    quit_btn.bind("<Leave>", lambda _e: quit_btn.configure(bg=COLOR_DANGER))
    quit_btn.pack(side=tk.RIGHT)

    return window


if __name__ == "__main__":
    NAV.replace("Vigil")
    build_home()
    base.run_mainloop()
