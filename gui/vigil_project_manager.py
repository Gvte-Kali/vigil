#!/usr/bin/env python3
"""Gestion des projets.

Les projets ne sont plus lies a un utilisateur : ils sont globaux. Un
utilisateur doit tout de meme etre selectionne dans la page Outils pour
logger les actions (chaine de custody), mais cette page n'a plus besoin de
selectionner une entite ni un utilisateur.
"""

import os
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk, filedialog

import vigil_data
import vigil_gui_base as base
from vigil_gui_base import (
    VigilWindow,
    fit_geometry,
    Section,
    ActionButton,
    LabeledField,
    LabeledCombo,
    styled_tree,
    header_title,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    FONT_BODY,
    FONT_SMALL,
    PAD,
    WIDGET_PAD,
    NAV,
)


# --------------------------------------------------------------------------- #
#  Dialogue nouveau projet
# --------------------------------------------------------------------------- #

def project_dialog(parent, on_saved=None):
    dialog = tk.Toplevel(parent)
    dialog.title("Nouveau projet")
    dialog.configure(bg=COLOR_BG)
    fit_geometry(dialog, 460, 280)
    dialog.transient(parent)
    dialog.grab_set()

    frame = tk.Frame(dialog, bg=COLOR_BG, padx=PAD, pady=PAD)
    frame.pack(fill=tk.BOTH, expand=True)

    name_field = LabeledField(frame, "Nom du projet *")
    name_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))
    desc_field = LabeledField(frame, "Description")
    desc_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    def save():
        project_name = name_field.var.get().strip()
        if not project_name:
            messagebox.showerror("Erreur", "Le nom du projet est obligatoire.")
            return
        projects = vigil_data.load_projects()
        if project_name in projects:
            messagebox.showerror("Erreur", "Un projet avec ce nom existe déjà.")
            return
        data = {
            "name": project_name,
            "description": desc_field.var.get().strip(),
            "created_at": datetime.now().isoformat(),
        }
        vigil_data.save_project(project_name, data)
        messagebox.showinfo("Succès", f"Projet {project_name} créé.")
        dialog.destroy()
        if on_saved:
            on_saved()

    actions = tk.Frame(frame, bg=COLOR_BG)
    actions.pack(fill=tk.X, pady=(PAD, 0))
    ActionButton(actions, "Valider", save, success=True, icon="check").pack(side=tk.LEFT)
    ActionButton(actions, "Annuler", dialog.destroy, icon="x").pack(side=tk.LEFT,
                padx=(WIDGET_PAD, 0))


# --------------------------------------------------------------------------- #
#  Vue : liste des projets
# --------------------------------------------------------------------------- #

def show_projects_view():
    window = VigilWindow(nav_label="Projets", geometry="900x600")
    header_title(
        window.body,
        text="Projets",
        subtitle=f"Entité : {vigil_data.config_summary()}",
        icon="folder",
    ).pack(fill=tk.X, pady=(0, PAD))

    tree_frame = tk.Frame(window.body, bg=COLOR_BG)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree = styled_tree(
        tree_frame,
        [("name", "Nom", 240), ("description", "Description", 340),
         ("created_at", "Date de création", 200)],
    )
    tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    def refresh():
        for item in tree.get_children():
            tree.delete(item)
        for name, data in vigil_data.load_projects().items():
            tree.insert("", "end", values=(
                name,
                data.get("description", ""),
                data.get("created_at", ""),
            ))

    refresh()

    def selected_project():
        sel = tree.selection()
        if not sel:
            return None
        return tree.item(sel[0])["values"][0]

    def export_project():
        name = selected_project()
        if not name:
            messagebox.showwarning("Avertissement", "Sélectionnez un projet.")
            return
        dest_dir = filedialog.askdirectory(
            title="Dossier de destination de l'archive",
            initialdir="/opt/vigil/rapports")
        if not dest_dir:
            return
        script = os.path.join(vigil_data.SCRIPTS_DIR,
                              "export", "vigil_export_project.sh")
        if not os.path.exists(script):
            messagebox.showerror("Erreur", f"Script introuvable : {script}")
            return
        vigil_data.set_active(None, name)
        try:
            subprocess.Popen([
                "konsole", "-e", "bash", "-c",
                f"bash {script} --dest {dest_dir}; rc=$?; "
                f"if [ $rc -eq 0 ]; then echo -e '\\n\\e[92m"
                f"\u2713 Export terminé. Appuyez sur Entrée pour fermer...\\e[0m'; "
                f"else echo -e '\\n\\e[91m"
                f"\u2715 Export terminé avec une erreur. Appuyez sur Entrée pour fermer...\\e[0m'; fi; "
                f"read"
            ])
        except FileNotFoundError:
            messagebox.showerror("Erreur",
                                 "Konsole absent. Installez-le : sudo apt install konsole")
        except Exception as exc:
            messagebox.showerror("Erreur", f"Échec du lancement : {exc}")

    def delete_project():
        name = selected_project()
        if not name:
            messagebox.showwarning("Avertissement", "Sélectionnez un projet.")
            return
        if messagebox.askyesno("Confirmation", f"Supprimer le projet {name} ?"):
            vigil_data.delete_project(name)
            messagebox.showinfo("Succès", f"Projet {name} supprimé.")
            refresh()

    actions = tk.Frame(window.body, bg=COLOR_BG)
    actions.pack(fill=tk.X, pady=(PAD, 0))
    ActionButton(actions, "Nouveau", lambda: project_dialog(window,
                on_saved=refresh), primary=True, icon="plus").pack(side=tk.LEFT)
    ActionButton(actions, "Supprimer", delete_project, danger=True, icon="x").pack(side=tk.LEFT,
                padx=(WIDGET_PAD, 0))
    ActionButton(actions, "Exporter", export_project, icon="upload").pack(side=tk.LEFT,
                padx=(WIDGET_PAD, 0))
    ActionButton(actions, "Accueil", lambda: window.go_back(
        "vigil_main_gui.py", nav_label="Vigil"), icon="home").pack(side=tk.RIGHT)

    return window


def main():
    show_projects_view()


if __name__ == "__main__":
    main()
    base.run_mainloop()
