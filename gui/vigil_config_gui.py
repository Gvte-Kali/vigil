#!/usr/bin/env python3
"""Page de configuration du systeme Vigil.

Remplace l'ancienne gestion multi-entites par une configuration statique unique :
  * logo de l'organisme (fichier image) ;
  * nom de l'entite ;
  * etablissement ;
  * adresse ;
  * telephone ;
  * email.

La page presente egalement la gestion des utilisateurs rattaches a cette entite
unique. Ces informations alimentent les rapports generes par Vigil.

La hierarchie des fenetres est refletee dans le titre de la fenetre.
"""

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import vigil_data
import vigil_gui_base as base
from vigil_gui_base import (
    VigilWindow,
    fit_geometry,
    Section,
    CategoryButton,
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
    COLOR_ACCENT,
    FONT_BODY,
    FONT_SMALL,
    FONT_BUTTON,
    PAD,
    WIDGET_PAD,
    NAV,
    quit_app,
)


# --------------------------------------------------------------------------- #
#  Dialogue utilisateur
# --------------------------------------------------------------------------- #

def user_dialog(parent, user_name=None, on_saved=None):
    """Dialogue de creation / modification d'un utilisateur."""
    dialog = tk.Toplevel(parent)
    dialog.title("Nouvel utilisateur" if not user_name else "Modifier l'utilisateur")
    dialog.configure(bg=COLOR_BG)
    fit_geometry(dialog, 460, 300)
    dialog.transient(parent)
    dialog.grab_set()

    frame = tk.Frame(dialog, bg=COLOR_BG, padx=PAD, pady=PAD)
    frame.pack(fill=tk.BOTH, expand=True)

    existing = vigil_data.load_users().get(user_name, {}) if user_name else {}
    name_field = LabeledField(frame, "Nom *", value=user_name or "",
                              readonly=bool(user_name))
    name_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    role_combo = LabeledCombo(frame, "Rôle", values=["admin", "analyst", "expert", "guest"])
    role_combo.var.set(existing.get("role", "analyst"))
    role_combo.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    def save():
        name = name_field.var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Le nom est obligatoire.")
            return
        users = vigil_data.load_users()
        if not user_name and name in users:
            messagebox.showerror("Erreur", "Cet utilisateur existe déjà.")
            return
        role = role_combo.var.get()
        data = {
            "name": name,
            "role": role,
            "created_at": existing.get("created_at", datetime.now().isoformat()),
            "permissions": {
                "can_mount": True,
                "can_scan": True,
                "can_export": role in ("admin", "expert"),
            },
        }
        vigil_data.save_user(name, data)
        messagebox.showinfo("Succès", "Utilisateur enregistré.")
        dialog.destroy()
        if on_saved:
            on_saved()

    actions = tk.Frame(frame, bg=COLOR_BG)
    actions.pack(fill=tk.X, pady=(PAD, 0))
    ActionButton(actions, "Valider", save, success=True, icon="check").pack(side=tk.LEFT)
    ActionButton(actions, "Annuler", dialog.destroy, icon="x").pack(side=tk.LEFT, padx=(WIDGET_PAD, 0))


# --------------------------------------------------------------------------- #
#  Vue : gestion des utilisateurs
# --------------------------------------------------------------------------- #

def show_users_view():
    window = VigilWindow(nav_label="Utilisateurs", geometry="900x600")
    header_title(
        window.body,
        text="Utilisateurs",
        subtitle=f"Entité : {vigil_data.config_summary()}",
        icon="circle-user",
    ).pack(fill=tk.X, pady=(0, PAD))

    tree_frame = tk.Frame(window.body, bg=COLOR_BG)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree = styled_tree(
        tree_frame,
        [("name", "Nom", 260), ("role", "Rôle", 180), ("created", "Créé le", 220)],
    )
    tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    def refresh():
        for item in tree.get_children():
            tree.delete(item)
        for name, data in vigil_data.load_users().items():
            tree.insert("", "end", values=(name, data.get("role", ""),
                                           data.get("created_at", "")))

    refresh()

    def selected_user():
        sel = tree.selection()
        if not sel:
            return None
        return tree.item(sel[0])["values"][0]

    actions = tk.Frame(window.body, bg=COLOR_BG)
    actions.pack(fill=tk.X, pady=(PAD, 0))
    ActionButton(actions, "Ajouter", lambda: user_dialog(window,
                on_saved=refresh), primary=True, icon="plus").pack(side=tk.LEFT)
    ActionButton(actions, "Modifier", lambda: (
        user_dialog(window, selected_user(), on_saved=refresh)
        if selected_user() else messagebox.showwarning("Avertissement",
        "Sélectionnez un utilisateur.")), icon="pencil").pack(side=tk.LEFT, padx=(WIDGET_PAD, 0))
    ActionButton(actions, "Supprimer", lambda: _delete_user(
        selected_user(), refresh), danger=True, icon="x").pack(side=tk.LEFT, padx=(WIDGET_PAD, 0))
    ActionButton(actions, "Retour", lambda: window.go_back(
        "vigil_config_gui.py", nav_label="Configuration"), icon="arrow-left").pack(side=tk.RIGHT)


    return window


def _delete_user(user_name, refresh):
    if not user_name:
        messagebox.showwarning("Avertissement", "Sélectionnez un utilisateur.")
        return
    if messagebox.askyesno("Confirmation", f"Supprimer l'utilisateur {user_name} ?"):
        vigil_data.delete_user(user_name)
        messagebox.showinfo("Succès", f"Utilisateur {user_name} supprimé.")
        refresh()


# --------------------------------------------------------------------------- #
#  Vue : configuration statique du systeme
# --------------------------------------------------------------------------- #

def show_config_view():
    window = VigilWindow(nav_label="Configuration", geometry="720x760", resizable=True)
    header_title(
        window.body,
        text="Configuration du système",
        subtitle="Entité, coordonnées et logo affichés sur les rapports",
        icon="settings",
    ).pack(fill=tk.X, pady=(0, PAD))

    config = vigil_data.load_config()

    info_section = Section(window.body, "Informations de l'entité", icon="image")
    info_section.pack(fill=tk.X, pady=(0, PAD))

    name_field = LabeledField(info_section.content, "Nom de l'entité *",
                              value=config.get("entity_name", ""))
    name_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    establishment_field = LabeledField(info_section.content, "Établissement",
                                       value=config.get("establishment", ""))
    establishment_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    address_field = LabeledField(info_section.content, "Adresse",
                                 value=config.get("address", ""))
    address_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    phone_field = LabeledField(info_section.content, "Téléphone",
                               value=config.get("phone", ""))
    phone_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    email_field = LabeledField(info_section.content, "Email",
                               value=config.get("email", ""))
    email_field.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    # --- Logo --------------------------------------------------------------- #
    logo_section = Section(window.body, "Logo", icon="image")
    logo_section.pack(fill=tk.X, pady=(0, PAD))

    logo_frame = tk.Frame(logo_section.content, bg=COLOR_SURFACE)
    logo_frame.pack(fill=tk.X, pady=(0, WIDGET_PAD))

    logo_display = vigil_data.logo_path(config)

    logo_preview = tk.Label(logo_frame, text="(aucun logo)", font=FONT_SMALL,
                            bg=COLOR_SURFACE_ALT, fg=COLOR_TEXT_DIM,
                            width=20, height=6, relief="flat", bd=0)
    logo_preview.pack(side=tk.LEFT, padx=(0, WIDGET_PAD))

    logo_info = tk.Frame(logo_frame, bg=COLOR_SURFACE)
    logo_info.pack(side=tk.LEFT, fill=tk.Y, expand=True)
    tk.Label(logo_info, text="Image affichée en en-tête des rapports",
             font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
             anchor="w", wraplength=320, justify="left").pack(fill=tk.X, pady=(0, WIDGET_PAD))

    logo_btns = tk.Frame(logo_info, bg=COLOR_SURFACE)
    logo_btns.pack(fill=tk.X)

    # Etat explicite du logo pour ne retraiter que les changements effectifs.
    #   "initial" : logo configure, inchangé par l'utilisateur
    #   "chosen"  : un nouveau fichier a été sélectionné (à copier)
    #   "removed" : l'utilisateur a retiré le logo (à effacer de la config)
    logo_state = {"value": "initial"}
    logo_new_path = {"value": None}

    def update_preview():
        path = None
        if logo_state["value"] == "chosen":
            path = logo_new_path["value"]
        elif logo_state["value"] == "initial":
            path = logo_display
        if path and os.path.isfile(path):
            try:
                from PIL import Image as PILImage, ImageTk
                img = PILImage.open(path)
                img.thumbnail((120, 80))
                photo = ImageTk.PhotoImage(img)
                logo_preview.configure(image=photo, text="")
                logo_preview.image = photo
            except Exception:
                logo_preview.configure(image="", text=os.path.basename(path))
                logo_preview.image = None
        else:
            logo_preview.configure(image="", text="(aucun logo)")
            logo_preview.image = None

    def choose_logo():
        path = filedialog.askopenfilename(
            title="Choisir un logo",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous", "*.*")],
        )
        if path:
            logo_state["value"] = "chosen"
            logo_new_path["value"] = path
            update_preview()

    def remove_logo():
        logo_state["value"] = "removed"
        logo_new_path["value"] = None
        update_preview()

    ActionButton(logo_btns, "Choisir un logo", choose_logo,
                 primary=True, icon="folder").pack(side=tk.LEFT)
    ActionButton(logo_btns, "Retirer", remove_logo, icon="x").pack(
        side=tk.LEFT, padx=(WIDGET_PAD, 0))

    update_preview()

    # --- Boutons d'action --------------------------------------------------- #
    def save_config():
        name = name_field.var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Le nom de l'entité est obligatoire.")
            return
        # Resolution du logo en fonction de l'etat effectif.
        rel_logo = config.get("logo", "")
        try:
            if logo_state["value"] == "chosen":
                # Nouveau fichier selectionne : on le copie dans le dossier
                # de configuration. L'ancien logo est supprime au passage.
                old_rel = config.get("logo", "")
                rel_logo = vigil_data.save_logo(logo_new_path["value"])
                if old_rel and old_rel != rel_logo:
                    vigil_data.remove_logo(old_rel)
            elif logo_state["value"] == "removed":
                old_rel = config.get("logo", "")
                vigil_data.remove_logo(old_rel)
                rel_logo = ""
            # "initial" : on conserve rel_logo tel quel (inchangé).
        except OSError as exc:
            messagebox.showerror(
                "Erreur d'écriture",
                "Impossible d'enregistrer le logo.\n\n"
                f"{exc}\n\n"
                "Vérifiez les droits sur /opt/vigil/data/config/logo.\n"
                "Astuce : sudo chown -R $USER:$USER /opt/vigil/data/config",
            )
            return
        data = {
            "entity_name": name,
            "establishment": establishment_field.var.get().strip(),
            "address": address_field.var.get().strip(),
            "phone": phone_field.var.get().strip(),
            "email": email_field.var.get().strip(),
            "logo": rel_logo,
            "configured_at": config.get("configured_at", datetime.now().isoformat()),
        }
        try:
            vigil_data.save_config(data)
        except OSError as exc:
            messagebox.showerror(
                "Erreur d'écriture",
                "La configuration n'a pas pu être enregistrée.\n\n"
                f"{exc}\n\n"
                "Vérifiez les droits sur le fichier de configuration.\n"
                "Astuce : sudo chown -R $USER:$USER /opt/vigil/data/config",
            )
            return
        messagebox.showinfo("Succès", "Configuration enregistrée.")
        window.title(NAV.title())

    actions = tk.Frame(window.body, bg=COLOR_BG)
    actions.pack(fill=tk.X, pady=(PAD, 0))
    ActionButton(actions, "Enregistrer", save_config, success=True, icon="check").pack(side=tk.LEFT)
    ActionButton(actions, "Utilisateurs", lambda: window.open_child(
        "vigil_config_gui.py", "users", nav_label="Utilisateurs"), icon="circle-user").pack(
        side=tk.LEFT, padx=(WIDGET_PAD, 0))
    ActionButton(actions, "Accueil", lambda: window.go_back(
        "vigil_main_gui.py", nav_label="Vigil"), icon="home").pack(side=tk.RIGHT)

    return window


# --------------------------------------------------------------------------- #
#  Entree
# --------------------------------------------------------------------------- #

def main():
    import sys
    args = sys.argv[1:]
    if args and args[0] == "users":
        show_users_view()
    else:
        show_config_view()


if __name__ == "__main__":
    main()
    base.run_mainloop()
