#!/usr/bin/env python3
"""Base partagee de l'interface graphique Vigil (tkinter).

Ce module centralise :
  * le theme (couleurs, polices, dimensions) ;
  * une fenetre racine unique invisible (partagee par toutes les fenetres) ;
  * des helpers de navigation parent/enfant avec reconstruction du titre de
    fenetre a partir de la hierarchie courante (ex. « Vigil > Configuration >
    Entites ») ;
  * des widgets stylés reutilisables (boutons de categorie, champs labels,
    barre d'actions, fenetres de dialogue).

Aucune fenetre n'est lancee a l'import : on importe ce module, on construit
une fenetre via ``VigilWindow`` ou ``navigate_to``, puis on appelle
``run_mainloop`` depuis le script d'entree.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

import vigil_data
import vigil_icons as icons


# --------------------------------------------------------------------------- #
#  Indicateur de montage (/investigation + /stockage)
# --------------------------------------------------------------------------- #

MOUNT_POINTS = ("/investigation", "/stockage")


def mounted_children(base):
    """Liste les points de montage réels sous `base`.

    Les montages multi-partitions sont imbriqués (/investigation/<disk>/<part>),
    donc un simple os.listdir(base) ne les détecte pas : il ne voit que les
    enfants directs (ex. /investigation/sdc) qui ne sont pas eux-mêmes des
    points de montage. On lit /proc/mounts (source de vérité du noyau) et on
    extrait le 2e champ (point de montage) des lignes sous `base`. Fallback
    os.path.ismount sur les enfants directs si /proc/mounts est vide.
    """
    if not base:
        return []
    prefix = base.rstrip("/") + "/"
    result = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as fh:
            for line in fh:
                fields = line.split()
                if len(fields) >= 2 and fields[1].startswith(prefix):
                    name = fields[1][len(prefix):]
                    if name and name not in result:
                        result.append(name)
    except OSError:
        pass
    if not result and os.path.isdir(base):
        try:
            for name in sorted(os.listdir(base)):
                if name.startswith("."):
                    continue
                full = os.path.join(base, name)
                if os.path.isdir(full) and os.path.ismount(full):
                    result.append(name)
        except OSError:
            pass
    return sorted(result)


class MountStatusBar(tk.Frame):
    """Barre d'etat affichant l'etat de montage de /investigation et /stockage.

    Rafaichie periodiquement (toutes les 2 s) via after(). Affiche un emoji
    vert (monte) ou rouge (non monte) et la liste des peripheriques montes.
    """

    def __init__(self, parent, interval_ms=2000):
        super().__init__(parent, bg=COLOR_SURFACE_ALT, highlightbackground=COLOR_BORDER,
                         highlightthickness=1, bd=0)
        self._interval = interval_ms
        self._frames = {}
        self._labels = {}
        self._photos = {}
        for mp in MOUNT_POINTS:
            frame = tk.Frame(self, bg=COLOR_SURFACE_ALT)
            frame.pack(side=tk.LEFT, padx=WIDGET_PAD, pady=2)
            lbl = tk.Label(frame, text="", font=FONT_SMALL, bg=COLOR_SURFACE_ALT,
                          fg=COLOR_TEXT, anchor="w")
            lbl.pack(side=tk.LEFT)
            self._frames[mp] = frame
            self._labels[mp] = lbl
        self.refresh()

    def _status_photo(self, color):
        key = ("dot", 12, color)
        if key in self._photos:
            return self._photos[key]
        photo, sym = icons.icon_or_symbol("circle-dot", 12, color)
        self._photos[key] = photo
        return photo

    def refresh(self):
        for mp in MOUNT_POINTS:
            children = mounted_children(mp)
            lbl = self._labels.get(mp)
            if lbl is None:
                continue
            if children:
                color = COLOR_SUCCESS
                text = f"{mp} : {', '.join(children)}"
            else:
                color = COLOR_DANGER
                text = f"{mp} : libre"
            lbl.configure(text=text, fg=color)
            photo = self._status_photo(color)
            if photo is not None:
                lbl.configure(image=photo, compound=tk.LEFT)
            else:
                dot_sym = icons.FALLBACK.get("circle-dot", "●")
                lbl.configure(text=f"{dot_sym} {text}", image="")
        self.after(self._interval, self.refresh)



# --------------------------------------------------------------------------- #
#  Theme
# --------------------------------------------------------------------------- #

COLOR_BG = "#1e1e2e"
COLOR_SURFACE = "#2a2a3c"
COLOR_SURFACE_ALT = "#313349"
COLOR_ACCENT = "#7aa2f7"
COLOR_ACCENT_HOVER = "#8db0ff"
COLOR_DANGER = "#f7768e"
COLOR_DANGER_HOVER = "#ff8da3"
COLOR_SUCCESS = "#9ece6a"
COLOR_SUCCESS_HOVER = "#b3d97f"
COLOR_TEXT = "#c0caf5"
COLOR_TEXT_DIM = "#7e89a8"
COLOR_BORDER = "#414868"

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_HEADING = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 10)
FONT_BUTTON = ("Segoe UI", 11, "bold")

PAD = 16
WIDGET_PAD = 8


def _relative(path):
    """Chemin absolu vers un script gui, quelle que soit l'installation."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)


# --------------------------------------------------------------------------- #
#  Racine unique
# --------------------------------------------------------------------------- #

_ROOT = None
_CHILD_PROCESSES = []


def get_root():
    """Retourne la fenetre racine cachee unique de l'application."""
    global _ROOT
    if _ROOT is None:
        _ROOT = tk.Tk()
        _ROOT.withdraw()
        _ROOT.configure(bg=COLOR_BG)
    return _ROOT


def _terminate_children():
    """Termine proprement les sous-processus enfants encore vivants."""
    import signal
    for proc in list(_CHILD_PROCESSES):
        if proc.poll() is not None:
            continue
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            try:
                proc.terminate()
            except OSError:
                pass
    _CHILD_PROCESSES.clear()


def quit_app():
    """Ferme proprement toute l'application."""
    _terminate_children()
    root = get_root()
    for window in list(_ROOT_WINDOWS):
        try:
            window.destroy()
        except tk.TclError:
            pass
    root.destroy()


_ROOT_WINDOWS = []


# --------------------------------------------------------------------------- #
#  Navigation
# --------------------------------------------------------------------------- #

class NavStack:
    """Pile de navigation representant la hierarchie des fenetres ouvertes.

    Le titre de chaque fenetre est reconstruit a partir de cette pile sous la
    forme « element 0 > element 1 > ... » afin d'afficher en permanence le
    chemin courant vers l'utilisateur.
    """

    def __init__(self):
        self._stack = []

    def push(self, label):
        self._stack.append(label)

    def pop(self):
        if self._stack:
            return self._stack.pop()
        return None

    def replace(self, label):
        self._stack = [label]

    def title(self):
        return " > ".join(self._stack) if self._stack else "Vigil"

    def current(self):
        return self._stack[-1] if self._stack else None

    def depth(self):
        return len(self._stack)


NAV = NavStack()


def navigate_to(script_name, *args, replace=False):
    """Lance une fenetre enfant dans un sous-processus.

    La fenetre appelante est detruite par l'appelant apres le lancement. La
    hierarchie courante est transmise au processus enfant via la variable
    d'environnement ``VIGIL_NAV`` (elements separes par « > ») afin que
    l'enfant reconstruise sa pile de navigation et affiche le chemin complet
    dans le titre de sa fenetre.
    """
    env = os.environ.copy()
    env["VIGIL_NAV"] = NAV.title()

    cmd = [sys.executable, _relative(script_name)]
    cmd.extend(str(a) for a in args)
    # Sorties du sous-processus journalisees : une exception non geree dans
    # une fenetre enfant doit etre diagnosticable (un DEVNULL l'aurait avalee
    # totalement silencieusement).
    log_dir = os.environ.get("VIGIL_DATA_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_fh = open(os.path.join(log_dir, "gui_child.log"), "a",
                      encoding="utf-8", buffering=1)
    except OSError:
        log_fh = subprocess.DEVNULL
    try:
        proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                               stdout=log_fh, stderr=log_fh,
                               start_new_session=True)
        _CHILD_PROCESSES.append(proc)
        if log_fh is not subprocess.DEVNULL:
            log_fh.write("---- lancement {} ----\n".format(" ".join(cmd)))
            log_fh.close()
    except FileNotFoundError:
        messagebox.showerror("Erreur", f"Interpreteur introuvable : {sys.executable}")
        return False
    return True


def restore_nav_from_env():
    """Reconstruit la pile de navigation a partir de ``VIGIL_NAV``."""
    nav = os.environ.get("VIGIL_NAV")
    if nav:
        NAV._stack = [part.strip() for part in nav.split(">") if part.strip()]


# --------------------------------------------------------------------------- #
#  Fenetre de base
# --------------------------------------------------------------------------- #

def fit_geometry(widget, width, height):
    """Dimensionne une fenetre pour qu'elle soit ENTIEREMENT visible a
    l'ouverture : la taille demandee est bornee a la place disponible de
    l'ecran (marge pour barres de taches/bordures) et la fenetre est placee
    en haut a gauche de la zone utile. Aucun redimensionnement manuel ne
    doit etre necessaire, quel que soit l'ecran."""
    try:
        sw = widget.winfo_screenwidth()
        sh = widget.winfo_screenheight()
    except tk.TclError:
        sw, sh = 1920, 1080
    margin = 48  # barre des taches + decor de fenetre
    width = max(320, min(width, sw - margin))
    height = max(240, min(height, sh - margin))
    x = max(0, (sw - width) // 2 - 16)
    y = max(0, (sh - height) // 2 - 24)
    widget.geometry(f"{width}x{height}+{x}+{y}")


class VigilWindow(tk.Toplevel):
    """Fenetre tkinter de base, themedee et rattachee a la racine cachee."""

    def __init__(self, nav_label=None, geometry="900x600", resizable=True,
                 close_guard=None):
        super().__init__(get_root())
        self._close_guard = close_guard
        self.configure(bg=COLOR_BG)
        restore_nav_from_env()
        if nav_label is not None and NAV.current() != nav_label:
            NAV.push(nav_label)
        self.title(NAV.title())
        if geometry:
            try:
                _w, _h = (int(v) for v in geometry.lower().split("x"))
            except ValueError:
                _w, _h = 900, 600
            fit_geometry(self, _w, _h)
        self.minsize(640, 480)
        if not resizable:
            self.resizable(False, False)

        self._closed = False
        _ROOT_WINDOWS.append(self)
        self.protocol("WM_DELETE_WINDOW", self.safe_close)

        # Icône de l'application (titre + barre des tâches) : logo Vigil.
        _win_icon = icons.get_icon("vigil", 64)
        if _win_icon is not None:
            try:
                self.iconphoto(True, _win_icon)
            except tk.TclError:
                pass
            # Conserver une référence pour éviter le ramasse-miette de l'image.
            self._app_icon = _win_icon

        self._style_widgets()
        self.body = tk.Frame(self, bg=COLOR_BG, padx=PAD, pady=PAD)
        self.body.pack(fill=tk.BOTH, expand=True)

        self.mount_status = MountStatusBar(self)
        self.mount_status.pack(fill=tk.X, side=tk.BOTTOM, padx=PAD, pady=(0, PAD))

    # -- style ------------------------------------------------------------- #

    @staticmethod
    def _style_widgets():
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Treeview",
            background=COLOR_SURFACE,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_SURFACE,
            bordercolor=COLOR_BORDER,
            rowheight=26,
            font=FONT_BODY,
        )
        style.configure(
            "Treeview.Heading",
            background=COLOR_SURFACE_ALT,
            foreground=COLOR_TEXT,
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", "#1e1e2e")],
        )
        style.configure(
            "TCombobox",
            background=COLOR_SURFACE,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_SURFACE,
            arrowcolor=COLOR_ACCENT,
            font=FONT_BODY,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLOR_SURFACE)],
            background=[("readonly", COLOR_SURFACE)],
        )
        style.configure(
            "TCheckbutton",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            font=FONT_BODY,
        )
        style.map(
            "TCheckbutton",
            background=[("active", COLOR_BG)],
        )
        style.configure("TEntry", fieldbackground=COLOR_SURFACE, foreground=COLOR_TEXT)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)

    # -- fermeture / navigation -------------------------------------------- #

    def _guard_blocks_close(self):
        """Demande au garde de fermeture (defini par la vue) la permission.

        Le garde renvoie True si un peripherique est toujours monte et que la
        fermeture doit etre bloquee (message deja affiche par la vue).
        """
        guard = getattr(self, "_close_guard", None)
        if guard is None:
            return False
        result = guard()
        if result is None:
            return False
        return bool(result)

    def safe_close(self):
        """Fermeture croix : remonte a la fenetre parente si elle existe."""
        if self._closed:
            return
        if self._guard_blocks_close():
            return
        self._closed = True
        NAV.pop()
        try:
            _ROOT_WINDOWS.remove(self)
        except ValueError:
            pass
        if not NAV.depth():
            quit_app()
        else:
            self.destroy()

    def go_back(self, script_name, *args, nav_label=None):
        """Remonte d'un cran dans la hierarchie et relance le parent."""
        if self._closed:
            return
        if self._guard_blocks_close():
            return
        NAV.pop()
        navigate_to(script_name, *args, replace=True)
        self._closed = True
        try:
            _ROOT_WINDOWS.remove(self)
        except ValueError:
            pass
        self.destroy()

    def open_child(self, script_name, *args, nav_label=None):
        """Ouvre une fenetre enfant en conservant le parent (fenetre modale-ish).

        La fenetre enfant est lancee dans un sous-processus. Le parent reste
        ouvert, mais devient inactive tant que l'enfant est lance. On detruit
        explicitement le parent apres lancement si l'enfant doit remplacer
        la vue (comportement par defaut, conforme a la logique actuelle).
        """
        navigate_to(script_name, *args)
        self._closed = True
        try:
            _ROOT_WINDOWS.remove(self)
        except ValueError:
            pass
        self.destroy()


# --------------------------------------------------------------------------- #
#  Widgets reutilisables
# --------------------------------------------------------------------------- #

class Section(tk.Frame):
    """Cadre de categorie avec un titre et une zone de contenu."""

    def __init__(self, parent, title, emoji="", icon="", **kwargs):
        super().__init__(parent, bg=COLOR_SURFACE, highlightbackground=COLOR_BORDER,
                         highlightthickness=1, bd=0, **kwargs)
        header = tk.Frame(self, bg=COLOR_SURFACE_ALT)
        header.pack(fill=tk.X, padx=0, pady=0)
        header_inner = tk.Frame(header, bg=COLOR_SURFACE_ALT)
        header_inner.pack(fill=tk.X, padx=PAD, pady=(WIDGET_PAD, WIDGET_PAD))
        photo, sym = icons.icon_or_symbol(icon, 18, COLOR_ACCENT) if icon else (None, emoji)
        if photo is not None:
            self._icon = photo
            tk.Label(header_inner, image=photo, bg=COLOR_SURFACE_ALT).pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
            tk.Label(header_inner, text=title, font=FONT_HEADING, bg=COLOR_SURFACE_ALT, fg=COLOR_ACCENT, anchor="w").pack(side=tk.LEFT, fill=tk.X)
        else:
            label_text = f"{sym} {title}" if sym else title
            tk.Label(header_inner, text=label_text, font=FONT_HEADING, bg=COLOR_SURFACE_ALT, fg=COLOR_ACCENT, anchor="w").pack(fill=tk.X)
        self.content = tk.Frame(self, bg=COLOR_SURFACE)
        self.content.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(WIDGET_PAD, PAD))


class CategoryButton(tk.Button):
    """Bouton de categorie large, full-width, avec emoji."""

    def __init__(self, parent, text, command, emoji="", icon="", subtitle="", danger=False, success=False):
        bg = COLOR_SURFACE_ALT
        fg = COLOR_TEXT
        active_bg = COLOR_ACCENT
        active_fg = "#1e1e2e"
        if success:
            bg = COLOR_SUCCESS
            fg = "#1e1e2e"
            active_bg = COLOR_SUCCESS_HOVER
            active_fg = "#1e1e2e"
        elif danger:
            bg = COLOR_DANGER
            fg = "#1e1e2e"
            active_bg = COLOR_DANGER_HOVER
            active_fg = "#1e1e2e"

        photo, sym = icons.icon_or_symbol(icon, 18, fg) if icon else (None, emoji)
        display = f"{sym}  {text}" if sym else text
        super().__init__(
            parent,
            text=display,
            command=command,
            font=FONT_BUTTON,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=WIDGET_PAD,
            pady=WIDGET_PAD,
            anchor="w",
            justify="left",
        )
        if photo is not None:
            self._icon = photo
            self.configure(image=photo, compound=tk.LEFT, padx=WIDGET_PAD)
        if subtitle:
            self._subtitle = subtitle
        self.bind("<Enter>", lambda _e: self._on_hover(active_bg, active_fg))
        self.bind("<Leave>", lambda _e: self._on_hover(bg, fg))

    def _on_hover(self, bg, fg):
        try:
            self.configure(bg=bg, fg=fg)
        except tk.TclError:
            pass


class ActionButton(tk.Button):
    """Bouton d'action compact (barre d'actions bas)."""

    def __init__(self, parent, text, command, danger=False, primary=False,
                 success=False, icon=""):
        if danger:
            bg = COLOR_DANGER
            active_bg = COLOR_DANGER_HOVER
            fg = "#1e1e2e"
        elif success:
            bg = COLOR_SUCCESS
            active_bg = COLOR_SUCCESS_HOVER
            fg = "#1e1e2e"
        elif primary:
            bg = COLOR_ACCENT
            active_bg = COLOR_ACCENT_HOVER
            fg = "#1e1e2e"
        else:
            bg = COLOR_SURFACE_ALT
            active_bg = COLOR_ACCENT
            fg = COLOR_TEXT
        photo, sym = icons.icon_or_symbol(icon, 16, fg) if icon else (None, None)
        display = f"{sym}  {text}" if sym else text
        super().__init__(
            parent,
            text=display,
            command=command,
            font=FONT_BUTTON,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground="#1e1e2e",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=WIDGET_PAD,
            pady=WIDGET_PAD,
        )
        if photo is not None:
            self.configure(image=photo, compound=tk.LEFT)
            self._icon = photo


class LabeledField(tk.Frame):
    """Champ libelle + entree/saisie alignes."""

    def __init__(self, parent, label, value="", width=None, readonly=False):
        super().__init__(parent, bg=COLOR_SURFACE)
        tk.Label(self, text=label, font=FONT_SMALL, bg=COLOR_SURFACE,
                 fg=COLOR_TEXT_DIM, anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.var = tk.StringVar(value=value)
        entry = tk.Entry(
            self,
            textvariable=self.var,
            font=FONT_BODY,
            bg=COLOR_SURFACE_ALT,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief="flat",
            bd=0,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
        )
        if width:
            entry.configure(width=width)
        if readonly:
            entry.configure(state="readonly")
        entry.pack(fill=tk.X)


class LabeledCombo(tk.Frame):
    """Champ libelle + combobox (lecture seule)."""

    def __init__(self, parent, label, values=None, on_change=None):
        super().__init__(parent, bg=COLOR_SURFACE)
        values = values or []
        tk.Label(self, text=label, font=FONT_SMALL, bg=COLOR_SURFACE,
                 fg=COLOR_TEXT_DIM, anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.var = tk.StringVar()
        self.combo = ttk.Combobox(
            self,
            textvariable=self.var,
            values=values,
            state="readonly",
            font=FONT_BODY,
        )
        self.combo.pack(fill=tk.X)
        if on_change:
            self.combo.bind("<<ComboboxSelected>>", lambda _e: on_change())


class ActionBar(tk.Frame):
    """Barre d'actions standard en bas d'une fenetre de liste."""

    def __init__(self, parent, actions=None):
        super().__init__(parent, bg=COLOR_BG)
        if actions:
            for spec in actions:
                text, command = spec[0], spec[1]
                danger = spec[2] if len(spec) > 2 else False
                primary = spec[3] if len(spec) > 3 else False
                ActionButton(self, text, command, danger=danger, primary=primary).pack(
                    side=tk.LEFT, padx=(0, WIDGET_PAD)
                )


class CollapsibleSection(tk.Frame):
    """Section repliable : un en-tete cliquable deplie/replie le contenu."""

    def __init__(self, parent, title, emoji="", icon="", collapsed=False, on_toggle=None):
        super().__init__(parent, bg=COLOR_SURFACE, highlightbackground=COLOR_BORDER,
                         highlightthickness=1, bd=0)
        self._collapsed = collapsed
        self._on_toggle = on_toggle
        photo, sym = icons.icon_or_symbol(icon, 18, COLOR_ACCENT) if icon else (None, emoji)
        self._title_text = f"{sym} {title}" if sym else title
        self._header = tk.Frame(self, bg=COLOR_SURFACE)
        self._header.pack(fill=tk.X, padx=PAD, pady=PAD)
        self._arrow_photo_down, _ = icons.icon_or_symbol("chevron-down", 18, COLOR_ACCENT)
        self._arrow_photo_up, _ = icons.icon_or_symbol("chevron-up", 18, COLOR_ACCENT)
        self._arrow = tk.Label(
            self._header, text="",
            image=self._arrow_photo_down if not collapsed else self._arrow_photo_up,
            bg=COLOR_SURFACE,
        )
        if self._arrow.cget("image") == "":
            self._arrow.configure(text="▼" if not collapsed else "▶",
                                  font=FONT_HEADING, fg=COLOR_ACCENT)
        self._arrow.pack(side=tk.LEFT, padx=(0, WIDGET_PAD))
        if photo is not None:
            self._icon = photo
            tk.Label(self._header, image=photo, bg=COLOR_SURFACE).pack(side=tk.LEFT, padx=(0, 4))
        self._label = tk.Label(
            self._header, text=title, font=FONT_HEADING,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT, anchor="w",
        )
        self._label.pack(side=tk.LEFT, fill=tk.X)
        for w in (self._header, self._arrow, self._label):
            w.bind("<Button-1>", lambda _e: self.toggle())
        self.content = tk.Frame(self, bg=COLOR_SURFACE)
        if not collapsed:
            self.content.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))

    def toggle(self):
        self._collapsed = not self._collapsed
        if self._arrow_photo_down is not None:
            self._arrow.configure(image=self._arrow_photo_down if not self._collapsed else self._arrow_photo_up, text="")
        else:
            self._arrow.configure(text="▼" if not self._collapsed else "▶")
        if self._collapsed:
            self.content.pack_forget()
        else:
            self.content.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))
        if self._on_toggle:
            self._on_toggle(self._collapsed)

    def collapse(self):
        if not self._collapsed:
            self.toggle()

    def expand(self):
        if self._collapsed:
            self.toggle()


class ScrollableFrame(tk.Frame):
    """Cadre a barre de defilement verticale pour les pages longues."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self._canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0, bd=0)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical",
                                         command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.content = tk.Frame(self._canvas, bg=COLOR_BG)
        self._window_id = self._canvas.create_window((0, 0), window=self.content,
                                                     anchor="nw")
        self.content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._on_wheel, add="+")

    def _on_content_configure(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._window_id, width=event.width)

    def _pointer_inside(self, event):
        """Vrai si le pointeur est sur ce cadre (ou un de ses enfants)."""
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                return True
            widget = widget.master
        return False

    def _on_wheel(self, event):
        if not self._pointer_inside(event):
            return
        if isinstance(event.widget, ttk.Treeview):
            return
        if event.num == 4:
            units = -1
        elif event.num == 5:
            units = 1
        else:
            units = int(-1 * (event.delta / 120))
            if units == 0:
                units = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(units, "units")


def header_title(parent, text, subtitle="", emoji="", icon="", center=False):
    """Renvoie le widget d'en-tete titre + sous-titre."""
    frame = tk.Frame(parent, bg=COLOR_BG)
    photo, sym = icons.icon_or_symbol(icon, 22, COLOR_TEXT) if icon else (None, emoji)
    title_text = f"{sym} {text}" if sym else text
    anchor = "center" if center else "w"
    title_lbl = tk.Label(
        frame, text=title_text, font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_TEXT, anchor=anchor,
        justify="center" if center else "left",
    )
    if photo is not None:
        frame._icon = photo
        title_lbl.configure(image=photo, compound=tk.LEFT if not center else tk.TOP)
    title_lbl.pack(fill=tk.X)
    if subtitle:
        tk.Label(
            frame, text=subtitle, font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_TEXT_DIM,
            anchor=anchor, justify="center" if center else "left",
        ).pack(fill=tk.X)
    return frame


def icon_label(parent, text, icon_name, font, bg, fg, anchor="w"):
    """Renvoie un tk.Label affichant une icone SVG + texte (degradation Unicode).

    Le widget renvoye est un simple tk.Label (image + texte, compound a gauche)
    que l'appelant peut packer comme n'importe quel label. La reference de
    l'image est conservee sur le label pour eviter le ramasse-miette.
    """
    photo, sym = icons.icon_or_symbol(icon_name, 16, fg) if icon_name else (None, None)
    display = f"{sym}  {text}" if sym else text
    lbl = tk.Label(parent, text=display, font=font, bg=bg, fg=fg, anchor=anchor)
    if photo is not None:
        lbl.configure(image=photo, compound=tk.LEFT)
        lbl._icon = photo
    return lbl


def styled_tree(parent, columns):
    """Cree un Treeview themedee avec les colonnes donnees (list de tuples)."""
    tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings")
    for key, label, width in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor="w")
    return tree


def accent_button(parent, accent_color, make_button, icon_name="",
                     expand=True):
    """Encadre un bouton d'une barre d'accent verticale coloree a gauche.

    make_button est un callable qui prend le widget parent (la ligne) et
    renvoie un bouton (typiquement CategoryButton). Le bouton est enfant de la
    ligne pour que le redimensionnement pleine largeur fonctionne. Si icon_name
    est fourni, l'icone SVG est rendue en noir a l'interieur de la barre
    d'accent pour qu'elle reste visible contre la couleur vive.
    """
    row = tk.Frame(parent, bg=COLOR_SURFACE)
    row.pack(fill=tk.X, pady=(0, WIDGET_PAD))
    bar = tk.Frame(row, bg=accent_color, width=28)
    bar.pack(side=tk.LEFT, fill=tk.Y)
    bar.pack_propagate(False)
    if icon_name:
        photo, _ = icons.icon_or_symbol(icon_name, 18, "#1e1e2e")
        if photo is not None:
            lbl = tk.Label(bar, image=photo, bg=accent_color)
            lbl.pack(expand=True, pady=WIDGET_PAD)
            row._bar_icon = photo
    button = make_button(row)
    button.pack(side=tk.LEFT, fill=tk.X, expand=expand)
    return row


def run_mainloop():
    """Point d'entree commun : restaure la nav puis lance le mainloop."""
    restore_nav_from_env()
    get_root().mainloop()
