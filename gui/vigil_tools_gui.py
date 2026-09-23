#!/usr/bin/env python3
"""Page d'analyse du périphérique USB.

Permet de lancer les outils forensiques apres avoir choisi, dans l'ordre :
  1. l'utilisateur (obligatoire, pour logger toute action) ;
  2. le projet (obligatoire, chaîne de custody).

L'entite provient de la configuration statique du systeme
(voir vigil_config_gui.py). Le scan antivirus ClamAV n'est PAS géré ici :
il est accessible séparément sur la page d'accueil (pas de custody, pas de
projet).

Le menu deroulant « Analyse fichiers » liste les scripts disponibles avec
une nomenclature « OS - Action ». La selection d'un script affiche
dynamiquement des parametres (cases a cocher) propres a ce script, par
exemple la generation d'un rapport PDF ou la detection des visages.

La section « Lancer plusieurs scans » presente les scripts dans un tableau
ou l'on coche/decoche chaque analyse d'un clic ; les presets (selections
pre-enregistrees) sont gérés dans une fenetre dediee.
"""

import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

import vigil_data
import vigil_gui_base as base
import vigil_icons as icons
from vigil_gui_base import (
    VigilWindow,
    fit_geometry,
    Section,
    CollapsibleSection,
    ScrollableFrame,
    ActionButton,
    CategoryButton,
    accent_button,
    icon_label,
    LabeledCombo,
    header_title,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLOR_ACCENT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_BORDER,
    FONT_BODY,
    FONT_SMALL,
    FONT_BUTTON,
    PAD,
    WIDGET_PAD,
    NAV,
)


# --------------------------------------------------------------------------- #
#  Catalogue des scripts d'analyse
# --------------------------------------------------------------------------- #
#
# Chaque script est decrit par un tuple :
#   (label, chemin_relatif, [parametres], [peripheriques])
# Un parametre est un tuple :
#   (cle_cli, libelle, valeur_par_defaut, type)
# - cle_cli : argument passe au script si l'option est activee (opt-in).
# - libelle : texte affiche a cote de la case.
# - defaut  : 0 (decoche) ou 1 (coche) par defaut.
# - type    : "check" (case simple) ou "dir" (case + champ + bouton
#             Parcourir toujours visibles a cote de la case).
# - peripheriques : liste optionnelle des types de peripheriques compatibles
#   (ex: ["windows", "xbox360"]). Si absent ou vide, le script est generique
#   et affiche quel que soit le filtre.

DEVICE_FILTERS = [
    ("all", "Tout afficher"),
    ("generic", "Générique"),
    ("windows", "Windows"),
    ("xbox360", "XBOX 360"),
]

SCRIPTS = [
    (
        "Generique - Recensement des fichiers",
        "analyse/vigil_census.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--no-dedup", "Désactiver le marquage des doublons", 0, "check"),
            ("--no-checksafe", "Désactiver le filtrage checksafe", 0, "check"),
        ],
    ),
    (
        "Generique - Analyse des fichiers image",
        "analyse/vigil_images.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie de toutes les images", 0, "dir"),
            ("--faces", "Détecter les visages sur les images", 0, "check"),
            ("--copy-faces-to", "Enregistrer une copie des images contenant des visages", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers vidéo",
        "analyse/vigil_videos.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie de toutes les vidéos", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers audio",
        "analyse/vigil_audio.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie de tous les fichiers audio", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers bureautiques",
        "analyse/vigil_office.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie de tous les fichiers bureautiques", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers archives",
        "analyse/vigil_archives.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie de toutes les archives", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers verrouillés (crypto)",
        "analyse/vigil_crypto.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie des fichiers verrouillés", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers à forte entropie",
        "analyse/vigil_entropy.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie des fichiers à forte entropie", 0, "dir"),
        ],
    ),
    (
        "Generique - Analyse des fichiers volumineux",
        "analyse/vigil_bigfiles.sh",
        [
            ("--pdf", "Générer un rapport PDF", 1, "check"),
            ("--copy-to", "Enregistrer une copie des fichiers volumineux", 0, "dir"),
        ],
    ),
]

# Indice du script par defaut selectionne
DEFAULT_SCRIPT_INDEX = 0

# Mapping script -> (kind PDF, nom du JSON attendu dans le dossier de
# collecte). Utilise par le mode "plusieurs scans" pour assembler un seul
# rapport PDF consolide via vigil_pdf.py --kind multi.
_SCRIPT_KIND = {
    "analyse/vigil_census.sh": ("census", "vigil_census.json"),
    "analyse/vigil_images.sh": ("images", "vigil_images.json"),
    "analyse/vigil_videos.sh": ("videos", "vigil_videos.json"),
    "analyse/vigil_audio.sh": ("audio", "vigil_audio.json"),
    "analyse/vigil_office.sh": ("office", "vigil_office.json"),
    "analyse/vigil_archives.sh": ("archives", "vigil_archives.json"),
    "analyse/vigil_crypto.sh": ("crypto", "vigil_crypto.json"),
    "analyse/vigil_entropy.sh": ("entropy", "vigil_entropy.json"),
    "analyse/vigil_bigfiles.sh": ("bigfiles", "vigil_bigfiles.json"),
}


# --------------------------------------------------------------------------- #
#  Filtre peripherique : logique UNIQUE, partagee par le menu deroulant
#  individuel (_AnalysisRunner) et la section multi-scans (_filter_labels_for).
#    'all'     : tous les scripts (generiques + taggues) ;
#    'generic' : uniquement les scripts sans tag peripherique ;
#    filtre specifique (windows, xbox360, ...) : scripts GENERIQUES + scripts
#    taggues pour ce peripherique — les analyses generiques (recensement,
#    images, videos...) s'appliquent a tout type de support.
# --------------------------------------------------------------------------- #

def visible_script_labels(scripts, device_key):
    """Labels de scripts visibles pour une cle de filtre peripherique
    ('all', 'generic', 'windows', 'xbox360', ...), tries alphabetiquement.
    Fonction pure : testable sans Tk (cf. todo_tests.txt, etape 1.1)."""
    visible = []
    for spec in scripts:
        devices = spec[3] if len(spec) > 3 else []
        if device_key == "all":
            visible.append(spec[0])
        elif device_key == "generic":
            if not devices:
                visible.append(spec[0])
        elif not devices or device_key in devices:
            # Filtre specifique : generiques (sans tag) + scripts taggues
            # pour ce peripherique.
            visible.append(spec[0])
    return sorted(visible)


def device_key_for_label(device_filters, label):
    """Retourne la cle de filtre associee a un libelle ('Windows' -> ...)."""
    for key, lbl in device_filters:
        if lbl == label:
            return key
    return "all"


# --------------------------------------------------------------------------- #
#  Lancement des scripts
# --------------------------------------------------------------------------- #

def _run_script_in_konsole(script_path, user, project, extra_args=None):
    """Lance un script shell dans Konsole en enregistrant l'etat actif."""
    if not os.path.exists(script_path):
        messagebox.showerror("Erreur", f"Script introuvable : {script_path}")
        return
    vigil_data.set_active(user, project if project else "(no-project)")
    if project:
        vigil_data.append_custody(user, project, "lancement_outil",
                                  detail=os.path.basename(script_path))
    args_str = " ".join(extra_args) if extra_args else ""
    try:
        subprocess.Popen([
            "konsole", "-e", "bash", "-c",
            f"bash {script_path} {args_str}; rc=$?; "
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


# --------------------------------------------------------------------------- #
#  Vue principale
# --------------------------------------------------------------------------- #

def _investigation_is_mounted():
    """Renvoie True si au moins un périphérique est monté dans /investigation.

    Les montages multi-partitions sont imbriqués (/investigation/<disk>/<part>),
    donc un simple `find -maxdepth 1` ne les détecte pas. /proc/mounts est la
    source de vérité du noyau : on lit directement ce fichier (2e champ =
    point de montage), sans dépendre d'aucune commande externe. Fallback
    `lsblk` (qui lit /sys) si /proc/mounts est vide.
    """
    base = "/investigation/"
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as fh:
            for line in fh:
                fields = line.split()
                if len(fields) >= 2 and fields[1].startswith(base):
                    return True
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "MOUNTPOINTS"],
            capture_output=True, text=True
        ).stdout
    except Exception:
        return False
    return base in out


def show_tools_view():
    def _guard_mounted():
        if _investigation_is_mounted():
            messagebox.showwarning(
                "Périphérique toujours monté",
                "Un périphérique est toujours monté dans /investigation.\n\n"
                "Veuillez le démonter via le bouton « Démonter » avant de "
                "quitter la page d'analyse, afin de préserver la chaîne de "
                "custody et d'éviter toute mauvaise manipulation.")
            return True
        return False

    window = VigilWindow(nav_label="Analyse du périphérique USB",
                         geometry="900x900", resizable=True,
                         close_guard=_guard_mounted)
    topbar = tk.Frame(window.body, bg=COLOR_BG)
    topbar.pack(fill=tk.X, pady=(0, PAD))
    ActionButton(topbar, "Accueil",
                 lambda: window.go_back("vigil_main_gui.py",
                                        nav_label="Vigil"),
                 icon="home").pack(side=tk.LEFT)
    icon_label(topbar, "Analyse du périphérique USB", "search",
               ("Segoe UI", 18, "bold"), COLOR_BG, COLOR_TEXT).pack(
        side=tk.LEFT, padx=(WIDGET_PAD, 0))

    scroll = ScrollableFrame(window.body)
    scroll.pack(fill=tk.BOTH, expand=True)
    page = scroll.content

    # --- Contexte (utilisateur + projet) ---
    contexte = CollapsibleSection(page, "Contexte", icon="info")
    contexte.pack(fill=tk.X, pady=(0, PAD))

    config = vigil_data.load_config()
    entity_label = tk.Label(
        contexte.content,
        text=f"Entité : {vigil_data.config_summary(config)}",
        font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, anchor="w",
    )
    entity_label.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    user_combo = LabeledCombo(contexte.content, "1. Utilisateur",
                              values=sorted(vigil_data.load_users().keys()))
    user_combo.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    project_combo = LabeledCombo(contexte.content, "2. Projet",
                                 values=sorted(vigil_data.load_projects().keys()))
    project_combo.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    def current_selection():
        user = user_combo.var.get()
        project = project_combo.var.get()
        return user, project

    def context_complete():
        user, project = current_selection()
        return bool(user and project)

    def maybe_auto_collapse():
        if context_complete():
            contexte.collapse()

    user_combo.combo.bind("<<ComboboxSelected>>", lambda _e: maybe_auto_collapse())
    project_combo.combo.bind("<<ComboboxSelected>>", lambda _e: maybe_auto_collapse())

    # Les scripts d'analyse exigent un projet actif (chaîne de custody). Le
    # montage/démontage USB est une opération matérielle utilitaire : elle ne
    # bloque pas sur l'utilisateur/projet (contexte transmis si disponible).
    # Le scan antivirus ClamAV est géré séparément sur la page d'accueil.

    def require_context(script_name=None):
        user, project = current_selection()
        if not user:
            messagebox.showwarning("Sélection incomplète",
                                   "Sélectionnez un utilisateur.")
            return None, None
        if not project:
            messagebox.showwarning("Sélection incomplète",
                                   "Un projet actif est obligatoire pour cette "
                                   "analyse (chaîne de custody).")
            return None, None
        return user, project

    def launch_optional(script_name):
        """Lance un script sans bloquer sur l'utilisateur/projet (montage USB)."""
        user, project = current_selection()
        script_path = os.path.join(vigil_data.SCRIPTS_DIR, script_name)
        _run_script_in_konsole(script_path, user or "(no-user)",
                               project if project else "(no-project)")

    def launch(script_name, extra_args):
        user, project = require_context(script_name)
        if user is None:
            return
        script_path = os.path.join(vigil_data.SCRIPTS_DIR, script_name)
        _run_script_in_konsole(script_path, user, project, extra_args)

    # --- Section montage / demontage USB ---
    usb_section = Section(page, "Monter / démonter le périphérique USB",
                          icon="plug")
    usb_section.pack(fill=tk.X, pady=(0, PAD))
    accent_button(
        usb_section.content, COLOR_SUCCESS,
        lambda _p: CategoryButton(
            _p,
            "Monter",
            command=lambda: launch_optional("analyse/vigil_usb_mount.sh"),
            subtitle="Monter un périphérique en lecture seule dans /investigation",
            success=True,
        ),
        icon_name="plug",
        expand=False,
    )
    accent_button(
        usb_section.content, COLOR_DANGER,
        lambda _p: CategoryButton(
            _p,
            "Démonter",
            command=lambda: launch_optional("analyse/vigil_usb_umount.sh"),
            subtitle="Démonter les périphériques montés dans /investigation",
            danger=True,
        ),
        icon_name="log-out",
        expand=False,
    )

    # --- Section Analyse (script + parametres dynamiques) ---
    analysis_section = Section(page, "Analyse", icon="search")
    analysis_section.pack(fill=tk.X, pady=(0, PAD))

    # Filtre par type de peripherique : limite les scripts affiches dans le
    # menu deroulant selon le type de peripherique analyse.
    filter_row = tk.Frame(analysis_section.content, bg=COLOR_SURFACE)
    filter_row.pack(fill=tk.X, pady=(0, WIDGET_PAD))
    tk.Label(filter_row, text="Périphérique :", font=FONT_SMALL, bg=COLOR_SURFACE,
             fg=COLOR_TEXT_DIM).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
    device_var = tk.StringVar()
    device_filter_combo = ttk.Combobox(
        filter_row, textvariable=device_var, state="readonly", font=FONT_BODY,
        values=[label for _key, label in DEVICE_FILTERS])
    device_filter_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
    device_filter_combo.set(DEVICE_FILTERS[0][1])

    runner = _AnalysisRunner(analysis_section.content, SCRIPTS, launch,
                              device_var, DEVICE_FILTERS)
    runner.build()

    # --- Section "Lancer plusieurs scans" ---
    # Tableau des scripts d'analyse : on choisit les scans à lancer en
    # cliquant sur les lignes, puis on les exécute tous d'un coup dans un
    # même terminal. Le tableau suit le filtre de périphérique de la
    # section Analyse ; les presets sont gérés dans une fenêtre dédiée.
    multi_section = CollapsibleSection(page, "Lancer plusieurs scans",
                                       icon="check-square", collapsed=True)
    multi_section.pack(fill=tk.X, pady=(0, PAD))

    multi_intro = tk.Label(
        multi_section.content,
        text="Cliquez sur une ligne du tableau pour cocher ou décocher "
             "une analyse, puis lancez. Le tableau suit le filtre "
             "périphérique ci-dessus ; le bouton « Gérer les presets » "
             "sélectionne les analyses pour vous.",
        font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, anchor="w",
    )
    multi_intro.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    # --- Presets : sélections pré-enregistrées de scripts à exécuter ---
    # Un menu déroulant dans cette page applique directement un preset
    # (pas besoin d'ouvrir une fenêtre). La fenêtre « Gérer les presets »
    # ne sert qu'à créer / modifier / supprimer : presets système
    # (Windows / XBOX 360 : génériques + scripts taggés, non supprimables)
    # + presets personnalisés (data/presets.json).

    def _all_presets():
        """Retourne {cle: [chemins...]} : presets système + personnalisés.

        Clés système préfixées "system:" (non modifiables/supprimables).
        """
        by_key = {}
        for key in ("windows", "xbox360"):
            paths = [spec[1] for spec in SCRIPTS
                     if not (spec[3] if len(spec) > 3 else [])
                     or key in (spec[3] if len(spec) > 3 else [])]
            by_key[key] = paths
        presets = vigil_data.system_presets(by_key)
        presets.update(vigil_data.load_presets())
        return presets

    def _device_text(spec):
        """Colonne Périphérique du tableau : Générique ou tags concaténés."""
        devices = spec[3] if len(spec) > 3 else []
        if not devices:
            return "Générique"
        names = {"windows": "Windows", "xbox360": "XBOX 360"}
        return " + ".join(names.get(d, d.capitalize()) for d in devices)

    def _preset_display_labels():
        """Libellés affichables des presets (préfixe system: retiré)."""
        presets = _all_presets()
        labels = []
        seen = set()
        for key in sorted(presets):
            label = key[7:] if key.startswith("system:") else key
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return labels

    def _apply_preset_by_name(name):
        """Applique un preset au tableau principal (depuis le menu déroulant
        ou depuis la fenêtre de gestion) : bascule le filtre sur « Tout
        afficher » et coche exactement ses analyses — la sélection lancée
        est toujours intégralement visible. Retourne True si appliqué."""
        presets = _all_presets()
        key = f"system:{name}" if f"system:{name}" in presets else name
        paths = presets.get(key, [])
        by_path = {spec[1]: spec[0] for spec in SCRIPTS}
        labels = [by_path[p] for p in paths if p in by_path]
        if not labels:
            messagebox.showwarning(
                "Preset vide",
                f"Le preset « {name} » ne contient aucune analyse connue "
                "du catalogue.")
            return False
        device_var.set(DEVICE_FILTERS[0][1])
        runner.set_device_filter(DEVICE_FILTERS[0][1])
        for lbl in multi_checked:
            multi_checked[lbl] = False
        for lbl in labels:
            multi_checked[lbl] = True
        applied_preset[0] = name
        _refresh_multi_table()
        _refresh_multi_params()
        return True

    def _open_preset_manager():
        """Fenêtre dédiée de gestion des presets : créer, modifier,
        supprimer. L'application se fait via le menu déroulant de la page
        d'analyse (pas ici)."""
        manager = tk.Toplevel(window, bg=COLOR_BG)
        manager.title("Vigil — Presets d'analyse")
        fit_geometry(manager, 760, 720)
        manager.minsize(640, 520)
        manager.transient(window)
        manager.grab_set()

        def _close_manager():
            manager.grab_release()
            manager.destroy()

        manager.protocol("WM_DELETE_WINDOW", _close_manager)

        # Contenu défilant : canvas + barre de défilement verticale. La
        # molette est captée au niveau de la fenêtre (présente dans les
        # bindtags de tous les enfants) ; les Treeview gardent leur propre
        # défilement interne (on ne les double-parcours pas).
        scroll_host = tk.Frame(manager, bg=COLOR_BG)
        scroll_host.pack(fill=tk.BOTH, expand=True)
        manager_canvas = tk.Canvas(scroll_host, bg=COLOR_BG,
                                   highlightthickness=0, bd=0)
        manager_vsb = ttk.Scrollbar(scroll_host, orient=tk.VERTICAL,
                                    command=manager_canvas.yview)
        manager_canvas.configure(yscrollcommand=manager_vsb.set)
        manager_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        manager_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        manager_content = tk.Frame(manager_canvas, bg=COLOR_BG)
        manager_win = manager_canvas.create_window(
            (0, 0), window=manager_content, anchor="nw")
        manager_content.bind(
            "<Configure>",
            lambda e: manager_canvas.configure(
                scrollregion=manager_canvas.bbox("all")))
        manager_canvas.bind(
            "<Configure>",
            lambda e: manager_canvas.itemconfig(manager_win, width=e.width))

        def _on_manager_wheel(event, delta=None):
            if isinstance(event.widget, ttk.Treeview):
                return
            if delta is None:
                delta = event.delta
            manager_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        manager.bind("<MouseWheel>", _on_manager_wheel)
        # X11 : la molette emet Button-4 (haut) / Button-5 (bas)
        manager.bind("<Button-4>",
                    lambda e: _on_manager_wheel(e, delta=120))
        manager.bind("<Button-5>",
                    lambda e: _on_manager_wheel(e, delta=-120))

        tk.Label(manager_content, text="Presets d'analyse", font=FONT_BUTTON,
                 bg=COLOR_BG, fg=COLOR_TEXT, anchor="w"
                 ).pack(fill=tk.X, padx=PAD, pady=(PAD, 0))
        tk.Label(manager_content,
                 text="Créer, modifier ou supprimer des presets. Pour "
                      "appliquer un preset, utilisez le menu déroulant "
                      "« Preset » de la page d'analyse.",
                 font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_TEXT_DIM, anchor="w"
                 ).pack(fill=tk.X, padx=PAD)

        # --- Presets existants : supprimer / éditer (sélection) ---
        existing_frame = tk.Frame(manager_content, bg=COLOR_SURFACE)
        existing_frame.pack(fill=tk.X, padx=PAD, pady=PAD)
        tk.Label(existing_frame,
                 text="Presets existants — sélection = charger dans le "
                      "formulaire ci-dessous",
                 font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
                 anchor="w"
                 ).pack(fill=tk.X, padx=WIDGET_PAD, pady=(WIDGET_PAD, 0))
        preset_list_frame = tk.Frame(existing_frame, bg=COLOR_SURFACE)
        preset_list_frame.pack(fill=tk.BOTH, expand=True, padx=WIDGET_PAD,
                               pady=WIDGET_PAD)
        preset_tree = ttk.Treeview(preset_list_frame,
                                   columns=("nom", "type", "nombre"),
                                   show="headings", height=5,
                                   selectmode="browse")
        preset_tree.heading("nom", text="Nom")
        preset_tree.heading("type", text="Type")
        preset_tree.heading("nombre", text="Analyses")
        preset_tree.column("nom", width=220, anchor="w")
        preset_tree.column("type", width=110, anchor="w")
        preset_tree.column("nombre", width=80, anchor="center", stretch=False)
        preset_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preset_scroll = ttk.Scrollbar(preset_list_frame, orient=tk.VERTICAL,
                                      command=preset_tree.yview)
        preset_tree.configure(yscrollcommand=preset_scroll.set)
        preset_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _refresh_existing(selected=None):
            preset_tree.delete(*preset_tree.get_children())
            presets = _all_presets()
            for key in sorted(presets):
                name = key[7:] if key.startswith("system:") else key
                ptype = "Système" if key.startswith("system:") else "Personnalisé"
                iid = preset_tree.insert("", "end",
                                         values=(name, ptype, len(presets[key])))
                if selected and name == selected:
                    preset_tree.selection_set(iid)

        def _selected_preset():
            sel = preset_tree.selection()
            if not sel:
                return None
            return preset_tree.item(sel[0], "values")[0]

        def _delete_from_manager():
            name = _selected_preset()
            if not name:
                messagebox.showwarning("Preset", "Sélectionnez un preset à "
                                       "supprimer.", parent=manager)
                return
            presets = _all_presets()
            if f"system:{name}" in presets:
                messagebox.showwarning("Suppression refusée",
                                       f"« {name} » est un preset système : "
                                       "non supprimable.", parent=manager)
                return
            if not vigil_data.delete_preset(name):
                messagebox.showwarning("Suppression refusée",
                                       f"« {name} » est introuvable.",
                                       parent=manager)
                return
            _refresh_existing()
            messagebox.showinfo("Preset supprimé",
                                f"« {name} » supprimé.", parent=manager)

        existing_btns = tk.Frame(existing_frame, bg=COLOR_SURFACE)
        existing_btns.pack(fill=tk.X, padx=WIDGET_PAD, pady=(0, WIDGET_PAD))
        tk.Button(existing_btns, text="Supprimer le preset sélectionné",
                  command=_delete_from_manager,
                  font=FONT_BUTTON, bg=COLOR_DANGER, fg="#1e1e2e",
                  relief="flat", bd=0, cursor="hand2",
                  padx=WIDGET_PAD, pady=WIDGET_PAD
                  ).pack(side=tk.LEFT)

        # --- Création : cocher les scripts un par un ---
        create_frame = tk.Frame(manager_content, bg=COLOR_SURFACE)
        create_frame.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))
        tk.Label(create_frame, text="Créer / modifier un preset — cochez les "
                                    "analyses à inclure :",
                 font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
                 anchor="w").pack(fill=tk.X, padx=WIDGET_PAD,
                                 pady=(WIDGET_PAD, 0))
        scripts_frame = tk.Frame(create_frame, bg=COLOR_SURFACE)
        scripts_frame.pack(fill=tk.BOTH, expand=True, padx=WIDGET_PAD,
                           pady=WIDGET_PAD)
        script_tree = ttk.Treeview(scripts_frame,
                                  columns=("coche", "analyse", "device"),
                                  show="headings", height=10,
                                  selectmode="none")
        script_tree.heading("coche", text="✓")
        script_tree.heading("analyse", text="Analyse")
        script_tree.heading("device", text="Périphérique")
        script_tree.column("coche", width=32, minwidth=32, anchor="center",
                           stretch=False)
        script_tree.column("analyse", width=300, anchor="w")
        script_tree.column("device", width=110, anchor="w", stretch=False)
        script_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        script_scroll = ttk.Scrollbar(scripts_frame, orient=tk.VERTICAL,
                                      command=script_tree.yview)
        script_tree.configure(yscrollcommand=script_scroll.set)
        script_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # État initial de la création = sélection courante du tableau
        # principal (scripts jamais affichés : non cochés).
        checks = {spec[0]: bool(multi_checked.get(spec[0], False))
                  for spec in SCRIPTS}

        def _refresh_script_tree():
            script_tree.delete(*script_tree.get_children())
            for spec in SCRIPTS:
                mark = "✔" if checks.get(spec[0]) else ""
                script_tree.insert("", "end", iid=spec[0],
                                   values=(mark, spec[0], _device_text(spec)))

        def _on_script_click(event):
            iid = script_tree.identify_row(event.y)
            if iid and iid in checks:
                checks[iid] = not checks[iid]
                script_tree.set(iid, "coche", "✔" if checks[iid] else "")

        script_tree.bind("<Button-1>", _on_script_click)
        _refresh_script_tree()

        name_row = tk.Frame(create_frame, bg=COLOR_SURFACE)
        name_row.pack(fill=tk.X, padx=WIDGET_PAD, pady=(0, WIDGET_PAD))
        tk.Label(name_row, text="Nom du preset :", font=FONT_SMALL,
                 bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM
                 ).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
        name_entry = tk.Entry(name_row, font=FONT_BODY,
                              bg=COLOR_SURFACE, fg=COLOR_TEXT,
                              relief="flat", bd=2)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _load_preset_for_edit(name):
            """Pré-remplit le formulaire d'édition avec un preset existant."""
            presets = _all_presets()
            key = f"system:{name}" if f"system:{name}" in presets else name
            paths = presets.get(key, [])
            by_path = {spec[1]: spec[0] for spec in SCRIPTS}
            for lbl in checks:
                checks[lbl] = False
            for p in paths:
                if p in by_path:
                    checks[by_path[p]] = True
            _refresh_script_tree()
            name_entry.delete(0, tk.END)
            name_entry.insert(0, name)

        def _on_preset_select(_e=None):
            name = _selected_preset()
            if name:
                _load_preset_for_edit(name)

        preset_tree.bind("<<TreeviewSelect>>", _on_preset_select)

        def _save_from_manager():
            name = name_entry.get().strip()
            checked = [lbl for lbl in checks if checks[lbl]]
            if not checked:
                messagebox.showwarning("Aucune analyse sélectionnée",
                                       "Cochez au moins une analyse dans le "
                                       "tableau.", parent=manager)
                return
            if not name:
                messagebox.showwarning("Nom manquant",
                                       "Saisissez un nom de preset.",
                                       parent=manager)
                return
            if name.startswith("system:"):
                messagebox.showerror("Nom réservé",
                                     "Le préfixe « system: » est réservé.",
                                     parent=manager)
                return
            presets = _all_presets()
            if f"system:{name}" in presets:
                messagebox.showerror("Nom déjà pris",
                                     "Un preset système porte déjà ce nom "
                                     "— choisissez un autre nom.",
                                     parent=manager)
                return
            by_label = {spec[0]: spec[1] for spec in SCRIPTS}
            paths = [by_label[lbl] for lbl in checked if lbl in by_label]
            replacing = name in vigil_data.load_presets()
            if replacing:
                if not messagebox.askyesno(
                        "Remplacer",
                        f"Le preset « {name} » existe déjà. Le remplacer ?",
                        parent=manager):
                    return
            vigil_data.create_preset(name, paths)
            name_entry.delete(0, tk.END)
            _refresh_existing(selected=name)
            _refresh_preset_combo()
            messagebox.showinfo(
                "Preset enregistré",
                f"Preset « {name} » "
                + ("remplacé" if replacing else "créé")
                + f" avec {len(paths)} analyse(s).", parent=manager)

        def _clear_form():
            for lbl in checks:
                checks[lbl] = False
            _refresh_script_tree()
            name_entry.delete(0, tk.END)
            preset_tree.selection_remove(preset_tree.selection())

        save_row = tk.Frame(create_frame, bg=COLOR_SURFACE)
        save_row.pack(fill=tk.X, padx=WIDGET_PAD, pady=(0, WIDGET_PAD))
        tk.Button(save_row, text="Enregistrer le preset",
                  command=_save_from_manager,
                  font=FONT_BUTTON, bg=COLOR_ACCENT, fg="#1e1e2e",
                  relief="flat", bd=0, cursor="hand2",
                  padx=WIDGET_PAD, pady=WIDGET_PAD
                  ).pack(side=tk.RIGHT)
        tk.Button(save_row, text="Vider le formulaire",
                  command=_clear_form,
                  font=FONT_BUTTON, bg=COLOR_SURFACE_ALT, fg=COLOR_TEXT,
                  relief="flat", bd=0, cursor="hand2",
                  padx=WIDGET_PAD, pady=WIDGET_PAD
                  ).pack(side=tk.RIGHT, padx=(0, WIDGET_PAD))

        _refresh_existing()

    # Tableau des scans : une ligne par script visible sous le filtre
    # courant. Cliquer sur une ligne la coche/décoche. L'état persiste
    # entre les changements de filtre (dictionnaire label -> bool).
    multi_checked = {}        # label -> bool (état coché persistant)
    applied_preset = [None]   # dernier preset appliqué (traçabilité custody)

    # Ligne de sélection rapide d'un preset : menu déroulant + Appliquer,
    # sans ouvrir la fenêtre de gestion (création/édition/suppression).
    preset_quick_row = tk.Frame(multi_section.content, bg=COLOR_SURFACE)
    preset_quick_row.pack(fill=tk.X, pady=(0, WIDGET_PAD))
    tk.Label(preset_quick_row, text="Preset :", font=FONT_SMALL,
             bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM
             ).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
    preset_quick_var = tk.StringVar()
    preset_quick_combo = ttk.Combobox(preset_quick_row,
                                      textvariable=preset_quick_var,
                                      state="readonly", font=FONT_BODY,
                                      values=_preset_display_labels())
    preset_quick_combo.pack(side=tk.LEFT, fill=tk.X, expand=True,
                            padx=(0, WIDGET_PAD))
    if _preset_display_labels():
        preset_quick_var.set(_preset_display_labels()[0])

    def _refresh_preset_combo(selected=None):
        """Met à jour le menu déroulant des presets de la page d'analyse."""
        labels = _preset_display_labels()
        preset_quick_combo.configure(values=labels)
        if selected and selected in labels:
            preset_quick_var.set(selected)
        elif labels and preset_quick_var.get() not in labels:
            preset_quick_var.set(labels[0])
        elif not labels:
            preset_quick_var.set("")

    def _apply_quick_preset(_e=None):
        name = preset_quick_var.get()
        if not name:
            messagebox.showwarning("Preset", "Aucun preset disponible.")
            return
        if _apply_preset_by_name(name):
            messagebox.showinfo(
                "Preset appliqué",
                f"« {name} » : analyses cochées dans le tableau "
                "(filtre basculé sur « Tout afficher »).")

    tk.Button(preset_quick_row, text="Appliquer",
              command=_apply_quick_preset,
              font=FONT_BUTTON, bg=COLOR_SUCCESS, fg="#1e1e2e",
              relief="flat", bd=0, cursor="hand2",
              padx=WIDGET_PAD, pady=WIDGET_PAD
              ).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
    tk.Button(preset_quick_row, text="Gérer…",
              command=_open_preset_manager,
              font=FONT_BUTTON, bg=COLOR_SURFACE_ALT, fg=COLOR_TEXT,
              relief="flat", bd=0, cursor="hand2",
              padx=WIDGET_PAD, pady=WIDGET_PAD
              ).pack(side=tk.LEFT)
    preset_quick_combo.bind("<<ComboboxSelected>>", lambda _e: None)

    multi_table_frame = tk.Frame(multi_section.content, bg=COLOR_SURFACE)
    multi_table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, WIDGET_PAD))

    multi_tree = ttk.Treeview(multi_table_frame,
                              columns=("coche", "analyse", "device"),
                              show="headings", selectmode="none")
    multi_tree.heading("coche", text="✓")
    multi_tree.heading("analyse", text="Analyse")
    multi_tree.heading("device", text="Périphérique")
    multi_tree.column("coche", width=32, minwidth=32, anchor="center",
                      stretch=False)
    multi_tree.column("analyse", width=300, minwidth=180, anchor="w")
    multi_tree.column("device", width=110, minwidth=90, anchor="w",
                      stretch=False)
    multi_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    multi_scroll = ttk.Scrollbar(multi_table_frame, orient=tk.VERTICAL,
                                 command=multi_tree.yview)
    multi_tree.configure(yscrollcommand=multi_scroll.set)
    multi_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _filter_labels_for(device_label):
        """Labels de scripts visibles pour un filtre périphérique — logique
        partagée avec _AnalysisRunner.set_device_filter (visible_script_labels)."""
        device_key = device_key_for_label(DEVICE_FILTERS, device_label)
        return visible_script_labels(SCRIPTS, device_key)

    def _refresh_multi_table():
        """Reconstruit le tableau selon le filtre périphérique."""
        multi_tree.delete(*multi_tree.get_children())
        visible_labels = _filter_labels_for(device_var.get())
        by_label = {s[0]: s for s in SCRIPTS}
        for label in visible_labels:
            if label not in multi_checked:
                multi_checked[label] = True
            mark = "✔" if multi_checked[label] else ""
            multi_tree.insert("", "end", iid=label,
                              values=(mark, label,
                                      _device_text(by_label[label])))
        if not visible_labels:
            multi_tree.insert("", "end", values=(
                "", "Aucun script disponible pour ce type de périphérique.",
                ""))

    def _on_multi_click(event):
        """Clic sur une ligne : bascule cochée/décochée."""
        iid = multi_tree.identify_row(event.y)
        if iid and iid in multi_checked:
            multi_checked[iid] = not multi_checked[iid]
            multi_tree.set(iid, "coche", "✔" if multi_checked[iid] else "")
            applied_preset[0] = None
            _refresh_multi_params()

    multi_tree.bind("<Button-1>", _on_multi_click)

    # --- Paramètres des analyses cochées ---
    # Panneau reconstruit à chaque changement de coche : une sous-section
    # par analyse cochée, listant ses paramètres (mêmes widgets que le
    # lanceur individuel : case simple ou case + champ dossier + Parcourir).
    # Un paramètre identique entre plusieurs analyses cochées n'est qu'une
    # seule ligne partagée (ex : « Générer un rapport PDF ») : cocher/décocher
    # s'applique à toutes les analyses qui le proposent.
    multi_params_frame = tk.Frame(multi_section.content, bg=COLOR_SURFACE)
    multi_params_frame.pack(fill=tk.X, pady=(0, WIDGET_PAD))
    multi_param_vars = {}   # libellé -> {"var": IntVar, "entry_info": ...}

    def _params_of(spec):
        """Liste (cli_key, libelle, defaut, type) d'un script."""
        out = []
        for param in spec[2]:
            if len(param) >= 4:
                out.append((param[0], param[1], param[2], param[3]))
            else:
                out.append((param[0], param[1], param[2], "check"))
        return out

    def _refresh_multi_params():
        """Reconstruit le panneau des paramètres pour les analyses cochées."""
        for child in multi_params_frame.winfo_children():
            child.destroy()
        multi_param_vars.clear()
        visible_labels = _filter_labels_for(device_var.get())
        by_label = {s[0]: s for s in SCRIPTS}
        filtered = []  # (spec, [(cli_key, libelle, defaut, type), ...])
        for lbl in visible_labels:
            if not multi_checked.get(lbl) or lbl not in by_label:
                continue
            params = [p for p in _params_of(by_label[lbl])
                      if p[0] != "--pdf"]
            if params:
                filtered.append((by_label[lbl], params))
        if not filtered:
            return
        # Paramètres de toutes les analyses cochées, regroupés par libellé :
        # une ligne partagée si plusieurs analyses proposent le même libellé
        # (ex : « Générer un rapport PDF »), sinon une ligne par analyse.
        groups = []   # [(libelle, [(spec, cli_key, defaut, type), ...]), ...]
        seen = {}
        for spec, params in filtered:
            for cli_key, libelle, defaut, ptype in params:
                if libelle not in seen:
                    seen[libelle] = len(groups)
                    groups.append((libelle, []))
                groups[seen[libelle]][1].append((spec, cli_key, defaut, ptype))
        tk.Label(multi_params_frame, text="Paramètres des analyses cochées :",
                 font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
                 anchor="w").pack(fill=tk.X, pady=(0, WIDGET_PAD))
        for libelle, members in groups:
            shared = len(members) > 1
            var = tk.IntVar(value=1 if any(m[2] for m in members) else 0)
            row = tk.Frame(multi_params_frame, bg=COLOR_SURFACE)
            row.pack(fill=tk.X, padx=(WIDGET_PAD, 0), pady=(0, 4))
            suffix = f"  ({len(members)} analyses)" if shared else ""
            cb = ttk.Checkbutton(row, text=libelle + suffix, variable=var)
            cb.pack(side=tk.LEFT)
            entry_info = None
            has_dir = any(m[3] == "dir" for m in members)
            if has_dir:
                dir_var = tk.StringVar()

                def browse(dir_var=dir_var, var=var):
                    d = filedialog.askdirectory(
                        title="Sélectionner le dossier de destination")
                    if d:
                        dir_var.set(d)
                    if not var.get():
                        var.set(1)
                browse_btn = tk.Button(row, text="Parcourir", command=browse,
                                       font=FONT_SMALL, bg=COLOR_SURFACE_ALT,
                                       fg=COLOR_TEXT, activebackground=COLOR_ACCENT,
                                       activeforeground="#1e1e2e", relief="flat",
                                       bd=0, cursor="hand2", padx=WIDGET_PAD,
                                       pady=2)
                browse_photo, browse_sym = icons.icon_or_symbol(
                    "folder", 14, COLOR_TEXT)
                if browse_photo is not None:
                    browse_btn.configure(image=browse_photo, compound=tk.LEFT)
                    browse_btn._icon = browse_photo
                browse_btn.pack(side=tk.RIGHT)
                entry = tk.Entry(row, textvariable=dir_var, font=FONT_SMALL,
                                 bg=COLOR_SURFACE_ALT, fg=COLOR_TEXT,
                                 insertbackground=COLOR_TEXT,
                                 relief="flat", bd=0,
                                 highlightbackground=COLOR_BORDER,
                                 highlightthickness=1)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True,
                           padx=WIDGET_PAD)
                entry_info = {"dir_var": dir_var}
            multi_param_vars[libelle] = {
                "var": var, "entry_info": entry_info,
                "members": [(m[0][0], m[1]) for m in members],
            }

    def _set_all_visible(state):
        for lbl in _filter_labels_for(device_var.get()):
            multi_checked[lbl] = state
        applied_preset[0] = None
        _refresh_multi_table()
        _refresh_multi_params()

    multi_table_btns = tk.Frame(multi_section.content, bg=COLOR_SURFACE)
    multi_table_btns.pack(fill=tk.X, pady=(0, WIDGET_PAD))
    tk.Button(multi_table_btns, text="Tout cocher",
              command=lambda: _set_all_visible(True),
              font=FONT_BUTTON, bg=COLOR_SURFACE, fg=COLOR_TEXT,
              relief="flat", bd=0, cursor="hand2",
              padx=WIDGET_PAD, pady=WIDGET_PAD
              ).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
    tk.Button(multi_table_btns, text="Tout décocher",
              command=lambda: _set_all_visible(False),
              font=FONT_BUTTON, bg=COLOR_SURFACE, fg=COLOR_TEXT,
              relief="flat", bd=0, cursor="hand2",
              padx=WIDGET_PAD, pady=WIDGET_PAD
              ).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
    tk.Button(multi_table_btns, text="Gérer les presets…",
              command=_open_preset_manager,
              font=FONT_BUTTON, bg=COLOR_SURFACE, fg=COLOR_TEXT,
              relief="flat", bd=0, cursor="hand2",
              padx=WIDGET_PAD, pady=WIDGET_PAD
              ).pack(side=tk.LEFT)

    _refresh_multi_table()
    _refresh_multi_params()

    def _extra_args_for(spec):
        """Arguments CLI du script selon le panneau de paramètres : pour
        chaque paramètre du script dont le libellé est présent dans le
        panneau, la case (et le dossier éventuel) décide du passage.
        Le PDF individuel n'est pas proposé : le multi-scans génère déjà
        un rapport consolidé (--no-pdf --json-out imposés)."""
        args = []
        for cli_key, libelle, _defaut, ptype in _params_of(spec):
            if cli_key == "--pdf":
                continue
            info = multi_param_vars.get(libelle)
            if info is None or not info["var"].get():
                continue
            args.append(cli_key)
            if ptype == "dir" and info["entry_info"]:
                d = info["entry_info"]["dir_var"].get().strip()
                if d:
                    args.append(d)
        return args

    def _launch_selected():
        by_label = {s[0]: s for s in SCRIPTS}
        # Scripts cochés ET visibles dans le tableau : appliquer un preset
        # bascule le filtre sur « Tout afficher », donc la sélection lancée
        # est toujours intégralement visible.
        visible_labels = _filter_labels_for(device_var.get())
        selected = [by_label[lbl] for lbl in visible_labels
                    if multi_checked.get(lbl) and lbl in by_label]
        if not selected:
            messagebox.showwarning("Aucune analyse sélectionnée",
                                   "Cochez au moins une analyse à lancer.")
            return
        # Vérifie que chaque script sélectionné est mappé à un kind PDF.
        missing = [spec[1] for spec in selected if spec[1] not in _SCRIPT_KIND]
        if missing:
            messagebox.showerror(
                "Configuration incomplète",
                "Scripts sans correspondance PDF :\n" + "\n".join(missing))
            return
        # Tous les scripts de cette page exigent un projet (chaîne de custody).
        user, project = require_context("analyse/vigil_usb_mount.sh")
        if user is None:
            return
        safe_project = project if project else "(no-project)"
        vigil_data.set_active(user, safe_project)
        if project:
            names = ", ".join(os.path.basename(spec[1]) for spec in selected)
            detail = names
            preset_label = applied_preset[0]
            if preset_label:
                detail = f"preset={preset_label} : {names}"
            vigil_data.append_custody(user, project, "lancement_multi_scans",
                                      detail=detail)
        # --- Flux rapport consolidé : un seul PDF pour tous les scans ---
        # Chaque script est lancé avec --no-pdf --json-out <collect_dir> (pas
        # de PDF individuel, JSON copié dans un dossier temporaire). À la fin,
        # vigil_pdf.py --kind multi assemble un seul rapport avec sommaire.
        scripts_dir = vigil_data.SCRIPTS_DIR
        pdf_script = os.path.join(scripts_dir, "pdf", "vigil_pdf.py")
        rapports_dir = os.path.join(vigil_data.BASE_DIR, "rapports")

        def shq(s):
            return s.replace("'", "'\"'\"'")

        run_steps = []
        for spec in selected:
            kind, json_name = _SCRIPT_KIND[spec[1]]
            script_path = os.path.join(scripts_dir, spec[1])
            extra = "".join(f" '{shq(a)}'" for a in _extra_args_for(spec))
            run_steps.append(
                f"echo '' | bash '{shq(script_path)}' "
                f"--no-pdf --json-out \"$COLLECT_DIR\"{extra}; "
                f"if [ -f \"$COLLECT_DIR/{json_name}\" ]; then "
                f"SECTIONS+=({kind}:ok:$COLLECT_DIR/{json_name}); "
                f"else SECTIONS+=({kind}:error:); fi")
        run_block = " ; ".join(run_steps)
        user_q = shq(user)
        project_q = shq(safe_project)
        proj_dir = ""
        if project:
            proj_dir = os.path.join(vigil_data.BASE_DIR, "data",
                                    "projects", project)

        # Assemblage final : génération du PDF consolidé + copie projet.
        # $COLLECT_DIR (mktemp) et noms JSON ne contiennent pas d'espaces : on
        # accumule SEC_ARGS (chaîne non quotée) et le word-splitting est sûr.
        pdf_gen_block = (
            f"if [ ${{#SECTIONS[@]}} -gt 0 ] && [ -f '{shq(pdf_script)}' ] && "
            f"command -v python3 >/dev/null 2>&1; then "
            f"SEC_ARGS=''; for s in \"${{SECTIONS[@]}}\"; do "
            f"SEC_ARGS=\"$SEC_ARGS --section $s\"; done; "
            f"MULTI_PDF=$(python3 '{shq(pdf_script)}' --kind multi "
            f"$SEC_ARGS --user '{user_q}' --project '{project_q}' "
            f"--dir '{shq(rapports_dir)}' 2>&1); "
            f"if [ $? -eq 0 ] && [ -n \"$MULTI_PDF\" ] && [ -f \"$MULTI_PDF\" ]; then "
            f"echo -e '\\n\\e[92m✅ Rapport PDF consolidé : '$MULTI_PDF'\\e[0m'; "
        )
        if proj_dir:
            pdf_gen_block += (
                f"if [ -d '{shq(proj_dir)}' ] && [ -w '{shq(proj_dir)}' ]; then "
                f"cp -f \"$MULTI_PDF\" '{shq(proj_dir)}/' 2>/dev/null && "
                f"echo -e '\\e[92m   Rapport copié dans le dossier du projet\\e[0m'; fi; "
            )
        pdf_gen_block += (
            "else echo -e '\\n\\e[91m❌ Échec de la génération "
            "du rapport PDF consolidé.\\e[0m'; "
            "echo -e '\\e[93m'$MULTI_PDF'\\e[0m'; fi; "
            "else echo -e '\\n\\e[91m❌ python3 ou script PDF manquant.\\e[0m'; fi"
        )
        cmd = (
            "COLLECT_DIR=$(mktemp -d -t vigil_multi.XXXXXX); "
            "declare -a SECTIONS=(); "
            f"{run_block}; "
            f"{pdf_gen_block}; "
            'rm -rf "$COLLECT_DIR" 2>/dev/null'
        )
        try:
            subprocess.Popen([
                "konsole", "-e", "bash", "-c",
                f"{cmd}; rc=$?; "
                f"if [ $rc -eq 0 ]; then echo -e '\\n\\e[92m"
                f"✓ Scans terminés. Appuyez sur Entrée pour fermer...\\e[0m'; "
                f"else echo -e '\\n\\e[91m"
                f"✕ Scans terminés avec une erreur. Appuyez sur Entrée pour fermer...\\e[0m'; fi; "
                f"read"
            ])
        except FileNotFoundError:
            messagebox.showerror("Erreur",
                                 "Konsole absent. Installez-le : sudo apt install konsole")
        except Exception as exc:
            messagebox.showerror("Erreur", f"Échec du lancement : {exc}")

    multi_btn_row = tk.Frame(multi_section.content, bg=COLOR_SURFACE)
    multi_btn_row.pack(fill=tk.X, pady=(WIDGET_PAD, 0))
    launch_photo, launch_sym = icons.icon_or_symbol("play", 16, "#1e1e2e")
    launch_display = f"{launch_sym}  Lancer les analyses sélectionnées" if launch_sym else "Lancer les analyses sélectionnées"
    multi_btn = tk.Button(
        multi_btn_row, text=launch_display, command=_launch_selected,
        font=FONT_BUTTON, bg=COLOR_SUCCESS, fg="#1e1e2e",
        activebackground=COLOR_SUCCESS_HOVER, activeforeground="#1e1e2e",
        relief="flat", bd=0, cursor="hand2",
        padx=WIDGET_PAD, pady=WIDGET_PAD,
    )
    if launch_photo is not None:
        multi_btn.configure(image=launch_photo, compound=tk.LEFT)
        multi_btn._icon = launch_photo
    multi_btn.pack(fill=tk.X)

    # Re-filtrer les scripts quand le type de peripherique change : met à
    # jour à la fois le menu déroulant individuel et les cases à cocher.
    def _on_device_change(_e=None):
        runner.set_device_filter(device_var.get())
        _refresh_multi_table()
        _refresh_multi_params()
    device_filter_combo.bind("<<ComboboxSelected>>", _on_device_change)

    return window


class _AnalysisRunner:
    """Selection d'un script d'analyse + parametres dynamiques + bouton Lancer.

    La selection d'un script dans le menu deroulant reaffiche dynamiquement
    les parametres (cases a cocher) associes a ce script. Les parametres sont
    reconstruits a chaque changement de selection.
    """

    def __init__(self, parent, scripts, launch_fn, device_var=None,
                 device_filters=None):
        self.parent = parent
        self.scripts = scripts  # liste de tuples (label, path, params[, devices])
        self.launch_fn = launch_fn
        self.var = tk.StringVar()
        self._by_label = {s[0]: s for s in scripts}
        self._params_frame = None
        self._param_vars = []  # liste de dicts decrivant chaque parametre
        self._combo = None
        self._device_var = device_var
        self._device_filters = device_filters or [("all", "Tout afficher")]
        # Liste des scripts actuellement visibles (apres filtre peripherique)
        self._visible_labels = sorted(s[0] for s in scripts)

    def _device_key_for_label(self, label):
        """Retourne la cle de filtre associee a un libelle de filtre."""
        return device_key_for_label(self._device_filters, label)

    def set_device_filter(self, filter_label):
        """Filtre les scripts affiches selon le type de peripherique choisi.
        - 'Tout afficher' (all) : tous les scripts (generiques + taggues).
        - 'Generique' : uniquement les scripts sans tag de peripherique.
        - Filtre specifique (windows, xbox360, ...) : scripts GENERIQUES +
          scripts taggues pour ce peripherique (les analyses generiques
          s'appliquent a tout type de support).
        Logique partagee avec la section multi-scans : visible_script_labels.
        """
        device_key = self._device_key_for_label(filter_label)
        self._visible_labels = visible_script_labels(self.scripts, device_key)
        if self._combo is not None:
            self._combo.configure(values=self._visible_labels)
        # Reinitialiser la selection si le script actuel n'est plus visible
        if self.var.get() not in self._visible_labels:
            if self._visible_labels:
                self.var.set(self._visible_labels[0])
                self._on_script_change()
            else:
                self.var.set("")
                if self._params_frame is not None:
                    for child in self._params_frame.winfo_children():
                        child.destroy()
                    self._param_vars = []
                    tk.Label(
                        self._params_frame,
                        text="Aucun script disponible pour ce type de "
                             "périphérique.",
                        font=FONT_SMALL, bg=COLOR_SURFACE,
                        fg=COLOR_TEXT_DIM, anchor="w",
                    ).pack(fill=tk.X)

    def build(self):
        # Ligne 1 : menu deroulant + bouton Lancer
        row = tk.Frame(self.parent, bg=COLOR_SURFACE)
        row.pack(fill=tk.X, pady=(0, WIDGET_PAD))
        tk.Label(row, text="Script :", font=FONT_SMALL, bg=COLOR_SURFACE,
                 fg=COLOR_TEXT_DIM).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
        combo = ttk.Combobox(row, textvariable=self.var,
                            values=self._visible_labels,
                            state="readonly", font=FONT_BODY)
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, WIDGET_PAD))
        self._combo = combo
        launch_btn = tk.Button(
            row, text="Lancer", command=self._launch,
            font=FONT_BUTTON, bg=COLOR_SUCCESS, fg="#1e1e2e",
            activebackground=COLOR_SUCCESS_HOVER, activeforeground="#1e1e2e",
            relief="flat", bd=0, cursor="hand2", padx=WIDGET_PAD, pady=WIDGET_PAD,
        )
        launch_photo, launch_sym = icons.icon_or_symbol("play", 16, "#1e1e2e")
        if launch_photo is not None:
            launch_btn.configure(image=launch_photo, compound=tk.LEFT)
            launch_btn._icon = launch_photo
        launch_btn.pack(side=tk.LEFT)

        # Cadre des parametres (reconstruit dynamiquement)
        self._params_frame = tk.Frame(self.parent, bg=COLOR_SURFACE)
        self._params_frame.pack(fill=tk.X, pady=(WIDGET_PAD, 0))

        combo.bind("<<ComboboxSelected>>", lambda _e: self._on_script_change())
        # Selection par defaut
        if self._visible_labels:
            self.var.set(self._visible_labels[DEFAULT_SCRIPT_INDEX]
                         if DEFAULT_SCRIPT_INDEX < len(self._visible_labels)
                         else self._visible_labels[0])
            self._on_script_change()

    def _on_script_change(self):
        for child in self._params_frame.winfo_children():
            child.destroy()
        self._param_vars = []
        label = self.var.get()
        spec = self._by_label.get(label)
        if not spec:
            return
        params = spec[2]
        if not params:
            tk.Label(self._params_frame, text="Aucun paramètre pour ce script.",
                     font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
                     anchor="w").pack(fill=tk.X)
            return
        tk.Label(self._params_frame, text="Paramètres :",
                 font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
                 anchor="w").pack(fill=tk.X, pady=(0, WIDGET_PAD))
        for param in params:
            if len(param) >= 4:
                cli_key, libelle, defaut, ptype = param[0], param[1], param[2], param[3]
            else:
                cli_key, libelle, defaut = param
                ptype = "check"
            self._build_param(cli_key, libelle, defaut, ptype)

    def _build_param(self, cli_key, libelle, defaut, ptype):
        """Construit un parametre : case simple ou case + selecteur dossier.

        Tous les parametres sont affiches en permanence. Pour le type 'dir',
        le bouton Parcourir (a droite) et le champ (au milieu) sont toujours
        visibles a cote de la case a cocher (a gauche).
        """
        var = tk.IntVar(value=defaut)
        row = tk.Frame(self._params_frame, bg=COLOR_SURFACE)
        row.pack(fill=tk.X, padx=(WIDGET_PAD, 0), pady=(0, 4))
        cb = ttk.Checkbutton(row, text=libelle, variable=var)
        cb.pack(side=tk.LEFT)
        entry_info = None
        if ptype == "dir":
            dir_var = tk.StringVar()

            def browse():
                d = filedialog.askdirectory(
                    title="Sélectionner le dossier de destination")
                if d:
                    dir_var.set(d)
                if not var.get():
                    var.set(1)
            browse_btn = tk.Button(row, text="Parcourir", command=browse,
                                   font=FONT_SMALL, bg=COLOR_SURFACE_ALT,
                                   fg=COLOR_TEXT, activebackground=COLOR_ACCENT,
                                   activeforeground="#1e1e2e", relief="flat",
                                   bd=0, cursor="hand2", padx=WIDGET_PAD, pady=2)
            browse_photo, browse_sym = icons.icon_or_symbol("folder", 14, COLOR_TEXT)
            if browse_photo is not None:
                browse_btn.configure(image=browse_photo, compound=tk.LEFT)
                browse_btn._icon = browse_photo
            browse_btn.pack(side=tk.RIGHT)
            entry = tk.Entry(row, textvariable=dir_var, font=FONT_SMALL,
                             bg=COLOR_SURFACE_ALT, fg=COLOR_TEXT,
                             insertbackground=COLOR_TEXT, relief="flat",
                             bd=0, highlightbackground=COLOR_BORDER,
                             highlightthickness=1)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=WIDGET_PAD)
            entry_info = {"dir_var": dir_var}
        self._param_vars.append({
            "cli_key": cli_key, "var": var, "type": ptype,
            "entry_info": entry_info,
        })

    def _launch(self):
        label = self.var.get()
        if not label:
            messagebox.showwarning("Aucun script",
                                   "Sélectionnez un script à lancer.")
            return
        spec = self._by_label.get(label)
        if not spec:
            return
        script_path = spec[1]
        extra_args = []
        for p in self._param_vars:
            if not p["var"].get():
                continue
            if p["type"] == "dir":
                d = p["entry_info"]["dir_var"].get().strip()
                if d:
                    extra_args.append(p["cli_key"])
                    extra_args.append(d)
            else:
                extra_args.append(p["cli_key"])
        self.launch_fn(script_path, extra_args)

def main():
    show_tools_view()


if __name__ == "__main__":
    main()
    base.run_mainloop()
