#!/usr/bin/env python3
"""Page de gestion des périphériques USB (whitelist / blacklist).

Vue de configuration permettant de :
  * visualiser l'inventaire USB connecté (fabricant, produit, VID:PID,
    n° de série, interface clavier HID) ;
  * whitelister les claviers/souris de travail (jamais bloqués au triage
    anti-Rubber Ducky de vigil_usb_mount.sh) ;
  * blacklister les périphériques suspects (toujours bloqués).

Les listes sont stockées dans data/usb/whitelist.txt et
data/usb/blacklist.txt (une entrée VID:PID ou n° de série par ligne).
"""

import re

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import vigil_data
from vigil_gui_base import (
    VigilWindow,
    ActionButton,
    ScrollableFrame,
    Section,
    styled_tree,
    header_title,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLOR_DANGER,
    COLOR_SUCCESS,
    FONT_BODY,
    FONT_SMALL,
    PAD,
    WIDGET_PAD,
)


def _device_key(dev):
    """Clé d'identification d'un périphérique : VID:PID puis série."""
    key = "{}:{}".format(dev.get("vid", "?"), dev.get("pid", "?"))
    serial = dev.get("serial", "")
    return key, serial


def _is_in(dev, entries):
    key, serial = _device_key(dev)
    if key in entries:
        return True
    return bool(serial) and serial in entries


def show_usb_view():
    _page_w = sum((90, 280, 110, 170, 100, 210)) + 120
    window = VigilWindow(nav_label="Configuration",
                         geometry="{}x680".format(_page_w),
                         resizable=True)
    topbar = tk.Frame(window.body, bg=COLOR_BG)
    topbar.pack(fill=tk.X, pady=(0, PAD))
    ActionButton(topbar, "Accueil",
                lambda: window.go_back("vigil_main_gui.py",
                                       nav_label="Vigil"),
                icon="home").pack(side=tk.LEFT)
    scroll = ScrollableFrame(window.body)
    scroll.pack(fill=tk.BOTH, expand=True)
    page = scroll.content
    header_title(
        page,
        text="Périphériques USB",
        subtitle="Inventaire USB et listes de confiance du triage anti-Rubber Ducky",
        icon="usb",
    ).pack(fill=tk.X, pady=(0, PAD))

    # --- Inventaire USB --------------------------------------------------- #
    inv_section = Section(page, "Périphériques connectés",
                           icon="usb")
    inv_section.pack(fill=tk.BOTH, expand=True, pady=(0, PAD))

    tree_frame = tk.Frame(inv_section.content, bg=COLOR_SURFACE)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (
        ("port", "Port", 90),
        ("name", "Périphérique", 280),
        ("vidpid", "VID:PID", 110),
        ("serial", "N° de série", 170),
        ("hid", "Clavier", 100),
        ("status", "Statut", 210),
    )
    tree = styled_tree(tree_frame, columns)
    scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tip = tk.Label(
        inv_section.content,
        text="Astuce : les périphériques whitelistés ne sont jamais bloqués "
             "au triage ; les blacklistés le sont toujours. « Clavier : OUI » "
             "signale une interface clavier HID (suspecte pour du stockage).",
        font=FONT_SMALL, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
        anchor="w", justify=tk.LEFT, wraplength=920,
    )
    tip.pack(fill=tk.X, pady=(WIDGET_PAD, 0))

    btn_row = tk.Frame(inv_section.content, bg=COLOR_SURFACE)
    btn_row.pack(fill=tk.X, pady=(WIDGET_PAD, 0))

    def _current_devices():
        return vigil_data.list_usb_devices()

    def _status_of(dev, whitelist, blacklist):
        if _is_in(dev, whitelist):
            return "Whitelisté (confiance)"
        if _is_in(dev, blacklist):
            return "Blacklisté (suspect)"
        if dev.get("hid"):
            return "Non listé — sera bloqué"
        return "Non listé (stockage)"

    def _refresh():
        for item in tree.get_children():
            tree.delete(item)
        devices = _current_devices()
        whitelist = vigil_data.load_usb_whitelist()
        blacklist = vigil_data.load_usb_blacklist()
        for dev in devices:
            hid_txt = "OUI ⚠" if dev.get("hid") else "non"
            status = _status_of(dev, whitelist, blacklist)
            tags = ()
            if dev.get("hid"):
                tags = tags + ("hid",)
            if "Blacklisté" in status:
                tags = tags + ("black",)
            elif "Whitelisté" in status:
                tags = tags + ("white",)
            tree.insert("", tk.END, values=(
                dev.get("port", ""),
                "{} {}".format(dev.get("manufacturer", ""),
                               dev.get("product", "")),
                "{}:{}".format(dev.get("vid", "?"), dev.get("pid", "?")),
                dev.get("serial", "") or "(absent)",
                hid_txt,
                status,
            ), tags=tags)
        tree.tag_configure("hid", foreground=COLOR_DANGER)
        tree.tag_configure("white", foreground=COLOR_SUCCESS)
        tree.tag_configure("black", foreground=COLOR_DANGER)
        if not devices:
            messagebox.showinfo("Inventaire", "Aucun périphérique USB détecté.")

    def _selected_dev():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Sélection",
                                   "Sélectionnez un périphérique dans la liste.")
            return None
        values = tree.item(sel[0], "values")
        return values

    def _add_to_list(loader, saver, label):
        values = _selected_dev()
        if values is None:
            return
        port, name, vidpid, serial, _hid, _status = values
        if serial == "(absent)":
            serial = ""
        entry = vidpid
        entries = loader()
        if entry not in entries:
            entries.append(entry)
        if serial and serial not in entries:
            entries.append(serial)
        saver(entries)
        log_entry = vidpid
        messagebox.showinfo(
            "Succès",
            "{} ajouté à la {} ({}).".format(name, label, log_entry))
        _fill_lists()
        _refresh()

    def _whitelist_dev():
        _add_to_list(vigil_data.load_usb_whitelist,
                     vigil_data.save_usb_whitelist, "whitelist")

    def _blacklist_dev():
        confirm = messagebox.askyesno(
            "Confirmer la blacklist",
            "Blacklister ce périphérique ?\n\n"
            "Il sera bloqué systématiquement au triage USB (frappes "
            "coupées, non montable) lors de chaque montage.")
        if not confirm:
            return
        _add_to_list(vigil_data.load_usb_blacklist,
                     vigil_data.save_usb_blacklist, "blacklist")

    ActionButton(btn_row, "Rafraîchir", _refresh).pack(
        side=tk.LEFT, padx=(0, WIDGET_PAD))
    ActionButton(btn_row, "Whitelister (confiance)", _whitelist_dev,
                 success=True, icon="check").pack(
                     side=tk.LEFT, padx=(0, WIDGET_PAD))
    ActionButton(btn_row, "Blacklister (suspect)", _blacklist_dev,
                 danger=True, icon="triangle-alert").pack(
                     side=tk.LEFT, padx=(0, WIDGET_PAD))

    # --- Listes persistantes ----------------------------------------------- #
    lists_section = Section(page, "Listes enregistrées", icon="list")
    lists_section.pack(fill=tk.BOTH, expand=True, pady=(0, PAD))

    list_cols = (("entry", "Entrée", 560),
                 ("kind", "Type", 200))

    def _list_tree(parent, label_text, on_add, on_remove):
        tk.Label(parent, text=label_text,
                 font=FONT_BODY, bg=COLOR_SURFACE, fg=COLOR_TEXT,
                 anchor="w").pack(fill=tk.X)
        frame = tk.Frame(parent, bg=COLOR_SURFACE)
        frame.pack(fill=tk.X, pady=(0, WIDGET_PAD))
        tree = styled_tree(frame, list_cols)
        tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        btns = tk.Frame(frame, bg=COLOR_SURFACE)
        btns.pack(side=tk.RIGHT, fill=tk.Y, padx=(WIDGET_PAD, 0))
        ActionButton(btns, "Ajouter", on_add,
                     icon="plus").pack(anchor=tk.N)
        ActionButton(btns, "Retirer", on_remove,
                     danger=True, icon="trash").pack(
                         anchor=tk.N, pady=(WIDGET_PAD, 0))
        return tree

    def _entry_kind(entry):
        if re.match(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$", entry):
            return "VID:PID"
        return "N° de série"

    def _fill_tree(tree, entries):
        for item in tree.get_children():
            tree.delete(item)
        for entry in entries:
            tree.insert("", tk.END, values=(entry, _entry_kind(entry)))

    def _wl_add():
        entry = _prompt_entry()
        if not entry:
            return
        entries = vigil_data.load_usb_whitelist()
        if entry not in entries:
            entries.append(entry)
            vigil_data.save_usb_whitelist(entries)
        _fill_lists()
        _refresh()

    def _wl_remove():
        _remove_entry(wl_tree, vigil_data.load_usb_whitelist,
                      vigil_data.save_usb_whitelist, "whitelist")

    def _bl_add():
        entry = _prompt_entry()
        if not entry:
            return
        entries = vigil_data.load_usb_blacklist()
        if entry not in entries:
            entries.append(entry)
            vigil_data.save_usb_blacklist(entries)
        _fill_lists()
        _refresh()

    def _bl_remove():
        _remove_entry(bl_tree, vigil_data.load_usb_blacklist,
                      vigil_data.save_usb_blacklist, "blacklist")

    wl_tree = _list_tree(lists_section.content,
                         "Whitelist (périphériques de confiance) :",
                         _wl_add, _wl_remove)
    bl_tree = _list_tree(lists_section.content,
                         "Blacklist (périphériques suspects) :",
                         _bl_add, _bl_remove)

    def _fill_lists():
        _fill_tree(wl_tree, vigil_data.load_usb_whitelist())
        _fill_tree(bl_tree, vigil_data.load_usb_blacklist())

    def _selected_entry(tree, list_name):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Sélection",
                                   "Sélectionnez une entrée dans la {}.".format(
                                       list_name))
            return None
        return tree.item(sel[0], "values")[0]

    def _remove_entry(tree, loader, saver, list_name):
        entry = _selected_entry(tree, list_name)
        if entry is None:
            return
        entries = [e for e in loader() if e != entry]
        saver(entries)
        _fill_lists()
        _refresh()

    def _prompt_entry():
        entry = simpledialog.askstring(
            "Ajouter une entrée",
            "VID:PID (ex. 2f13:d140) ou n° de série :")
        return entry.strip() if entry else None

    def _save_lists():
        wl = [wl_tree.item(i, "values")[0]
              for i in wl_tree.get_children()]
        bl = [bl_tree.item(i, "values")[0]
              for i in bl_tree.get_children()]
        vigil_data.save_usb_whitelist(wl)
        vigil_data.save_usb_blacklist(bl)
        messagebox.showinfo("Succès", "Listes USB enregistrées.")
        _refresh()

    save_row = tk.Frame(lists_section.content, bg=COLOR_SURFACE)
    save_row.pack(fill=tk.X, pady=(WIDGET_PAD, 0))
    ActionButton(save_row, "Enregistrer les listes", _save_lists,
                 success=True, icon="check").pack(side=tk.LEFT)

    _refresh()
    _fill_lists()

    return window


# ---------------------------------------------------------------------------
#  Entree
# ---------------------------------------------------------------------------

def main():
    show_usb_view()


if __name__ == "__main__":
    main()
    import vigil_gui_base as base
    base.run_mainloop()
