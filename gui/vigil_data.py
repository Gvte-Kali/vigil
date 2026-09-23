#!/usr/bin/env python3
"""Couche d'acces aux donnees partagee par l'ensemble des interfaces Vigil.

Vigil utilise une configuration statique unique pour le systeme (un seul
organisme/entite) : logo, nom, etablissement, adresse, telephone et email.
Les utilisateurs sont rattaches a cette entite unique. Les projets ne sont
plus lies a un utilisateur precis, mais un utilisateur doit tout de meme etre
selectionne pour logger toute action (chaine de custody).

Aucune logique d'interface n'est presente ici : ce module expose uniquement
des fonctions pures de lecture / ecriture / suppression.

En production les chemins sont ancrees sous ``/opt/vigil``. En environnement de
developpement ils peuvent etre rediriges via les variables d'environnement
``VIGIL_BASE`` et ``VIGIL_DATA_DIR`` afin de tester sans droits root.
"""

import json
import os
import shutil
from datetime import datetime

BASE_DIR = os.environ.get("VIGIL_BASE", "/opt/vigil")
DATA_DIR = os.environ.get("VIGIL_DATA_DIR", os.path.join(BASE_DIR, "data"))
CONFIG_DIR = os.path.join(DATA_DIR, "config")
USERS_DIR = os.path.join(DATA_DIR, "users")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

CONFIG_FILE = os.path.join(CONFIG_DIR, "system.json")
LOGO_DIR = os.path.join(CONFIG_DIR, "logo")

ACTIVE_USER = os.path.join(DATA_DIR, "active_user")
ACTIVE_PROJECT = os.path.join(DATA_DIR, "active_project")
USB_DIR = os.path.join(DATA_DIR, "usb")
USB_WHITELIST_FILE = os.path.join(USB_DIR, "whitelist.txt")
USB_BLACKLIST_FILE = os.path.join(USB_DIR, "blacklist.txt")

DEFAULT_CONFIG = {
    "entity_name": "",
    "establishment": "",
    "address": "",
    "phone": "",
    "email": "",
    "logo": "",
    "configured_at": "",
}


def _ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(USERS_DIR, exist_ok=True)
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    os.makedirs(LOGO_DIR, exist_ok=True)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)


# --------------------------------------------------------------------------- #
#  Configuration statique du systeme
# --------------------------------------------------------------------------- #

def load_config():
    """Retourne le dictionnaire de configuration statique du systeme."""
    _ensure_dirs()
    if not os.path.isfile(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    config = _read_json(CONFIG_FILE)
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)
    return merged


def save_config(data):
    """Enregistre la configuration statique du systeme."""
    _ensure_dirs()
    data.setdefault("configured_at", datetime.now().isoformat())
    _write_json(CONFIG_FILE, data)


def save_logo(src_path):
    """Copie un nouveau fichier logo dans le dossier de configuration.

    Le logo existant est supprime au prealable afin d'eviter l'accumulation
    d'anciens fichiers et la collision de noms. Evite egalement la copie d'un
    fichier sur lui-meme (cas ou l'utilisateur enregistre sans changer le
    logo : la GUI ne doit de toute facon pas appeler cette fonction dans ce
    cas, mais on se protege ici egalement). Retourne le chemin relatif stocke
    dans la configuration.
    """
    _ensure_dirs()
    if not src_path or not os.path.isfile(src_path):
        return ""
    ext = os.path.splitext(src_path)[1].lower() or ".png"
    dest = os.path.join(LOGO_DIR, f"logo{ext}")
    # Suppression de tout logo precedent avant d'ecrire le nouveau.
    if os.path.isfile(dest) and not os.path.samefile(src_path, dest):
        os.remove(dest)
    if os.path.abspath(src_path) == os.path.abspath(dest):
        return os.path.relpath(dest, DATA_DIR)
    shutil.copy2(src_path, dest)
    return os.path.relpath(dest, DATA_DIR)


def remove_logo(rel_path):
    """Supprime le fichier logo correspondant au chemin relatif configure."""
    if not rel_path:
        return
    abs_path = os.path.join(DATA_DIR, rel_path)
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass


def logo_path(config=None):
    """Retourne le chemin absolu du logo configure, ou None."""
    if config is None:
        config = load_config()
    rel = config.get("logo", "")
    if not rel:
        return None
    abs_path = os.path.join(DATA_DIR, rel)
    return abs_path if os.path.isfile(abs_path) else None


def config_summary(config=None):
    """Retourne un resume textuel de l'entite (nom + etablissement)."""
    if config is None:
        config = load_config()
    name = config.get("entity_name", "") or "Entite non configuree"
    est = config.get("establishment", "")
    if est:
        return f"{name} - {est}"
    return name


# --------------------------------------------------------------------------- #
#  Utilisateurs
# --------------------------------------------------------------------------- #

def load_users():
    """Retourne les utilisateurs du systeme sous forme ``{nom: donnees}``."""
    _ensure_dirs()
    users = {}
    if not os.path.isdir(USERS_DIR):
        return users
    for name in os.listdir(USERS_DIR):
        profile_file = os.path.join(USERS_DIR, name, "profile.json")
        if os.path.isfile(profile_file):
            users[name] = _read_json(profile_file)
    return users


def save_user(name, data):
    """Cree ou met a jour un utilisateur."""
    _ensure_dirs()
    data.setdefault("name", name)
    _write_json(os.path.join(USERS_DIR, name, "profile.json"), data)


def delete_user(name):
    user_dir = os.path.join(USERS_DIR, name)
    if os.path.isdir(user_dir):
        shutil.rmtree(user_dir)


# --------------------------------------------------------------------------- #
#  Projets
# --------------------------------------------------------------------------- #

def load_projects():
    """Retourne les projets du systeme sous forme ``{nom: donnees}``.

    Les projets ne sont plus lies a un utilisateur : ils sont globaux.
    """
    _ensure_dirs()
    projects = {}
    if not os.path.isdir(PROJECTS_DIR):
        return projects
    for name in os.listdir(PROJECTS_DIR):
        info_file = os.path.join(PROJECTS_DIR, name, "info.json")
        if os.path.isfile(info_file):
            projects[name] = _read_json(info_file)
    return projects


def save_project(project_name, data):
    """Cree un projet et initialise son fichier ``chain_of_custody.log``."""
    _ensure_dirs()
    project_dir = os.path.join(PROJECTS_DIR, project_name)
    os.makedirs(project_dir, exist_ok=True)

    data.setdefault("name", project_name)
    data.setdefault("created_at", datetime.now().isoformat())

    custody_path = os.path.join(project_dir, "chain_of_custody.log")
    if not os.path.exists(custody_path):
        config = load_config()
        with open(custody_path, "w", encoding="utf-8") as handle:
            handle.write(f"# === Projet: {project_name} ===\n")
            handle.write(
                f"# Entite: {config.get('entity_name', '(non configuree)')}"
                f" | Etablissement: {config.get('establishment', '')}\n"
            )
            handle.write(f"# Cree le: {datetime.now().isoformat()}\n\n")

    _write_json(os.path.join(project_dir, "info.json"), data)


def delete_project(project_name):
    project_dir = os.path.join(PROJECTS_DIR, project_name)
    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir)


def export_project(project_name, dest_dir="/tmp"):
    """Zippe un projet (donnees + logs) et renvoie le chemin de l'archive."""
    import zipfile

    project_dir = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.isdir(project_dir):
        return None

    zip_path = os.path.join(
        dest_dir,
        f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
    )
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(project_dir):
            for file in files:
                file_path = os.path.join(root_dir, file)
                arcname = os.path.relpath(file_path, os.path.dirname(project_dir))
                zipf.write(file_path, arcname)
    return zip_path


# ---------------------------------------------------------------------------
#  Presets d'analyse (selections pre-enregistrees de scripts)
# --------------------------------------------------------------------------- #

PRESETS_FILE = os.path.join(DATA_DIR, "presets.json")


def system_presets(scripts_by_key):
    """Presets systeme : non modifiables, non supprimables. Une cle de preset
    systeme est TOUJOURS prefixee par "system:" pour eviter toute collision
    avec un preset personnalise.

    scripts_by_key : dict {cle_filtre: [chemin_script, ...]} contenant,
    pour chaque filtre peripherique (windows, xbox360...), les chemins des
    scripts GENERIQUES (sans tag) + les scripts taggues pour ce
    peripherique. Retourne {cle: [chemins...]}.
    """
    presets = {}
    for key, label in (("windows", "Windows"), ("xbox360", "XBOX 360")):
        paths = scripts_by_key.get(key, [])
        if paths:
            presets[f"system:{label}"] = sorted(set(paths))
    return presets


def load_presets():
    """Charge les presets personnalises depuis data/presets.json.

    Retourne {nom: [chemin_script, ...]}. Fichier absent -> {}.
    Fichier corrompu -> {} (l'appelant affiche l'avertissement).
    """
    if not os.path.exists(PRESETS_FILE):
        return {}
    try:
        data = _read_json(PRESETS_FILE)
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    presets = {}
    for name, paths in data.items():
        if not name or name.startswith("system:"):
            continue
        if isinstance(paths, list) and all(isinstance(p, str) for p in paths):
            presets[name] = sorted(set(paths))
    return presets


def save_presets(presets):
    """Sauvegarde les presets personnalises dans data/presets.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    _write_json(PRESETS_FILE, presets)


def create_preset(name, script_paths):
    """Ajoute (ou remplace) un preset personnalise. Retourne False si le
    nom est vide ou reserve (prefixe system:)."""
    if not name or name.startswith("system:"):
        return False
    presets = load_presets()
    presets[name] = sorted(set(script_paths))
    save_presets(presets)
    return True


def delete_preset(name):
    """Supprime un preset personnalise. Refuse les presets systeme.
    Retourne True si supprime, False sinon."""
    if not name or name.startswith("system:"):
        return False
    presets = load_presets()
    if name not in presets:
        return False
    del presets[name]
    save_presets(presets)
    return True


# --------------------------------------------------------------------------- #
#  Chaine de custody
# --------------------------------------------------------------------------- #

def append_custody(user_name, project_name, action, detail=""):
    """Ajoute une ligne horodatee au journal de custody du projet."""
    if not project_name or project_name == "(no-project)":
        return
    project_dir = os.path.join(PROJECTS_DIR, project_name)
    custody_path = os.path.join(project_dir, "chain_of_custody.log")
    os.makedirs(project_dir, exist_ok=True)
    config = load_config()
    entity = config.get("entity_name", "") or "(non configuree)"
    stamp = datetime.now().isoformat()
    line = f"[{stamp}] {entity} | {user_name} | {action}"
    if detail:
        line += f" | {detail}"
    with open(custody_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


# --------------------------------------------------------------------------- #
#  Etat actif (selection courante)
# --------------------------------------------------------------------------- #

def set_active(user_name=None, project_name=None):
    """Persiste la selection courante pour les scripts shell de montage."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if user_name is not None:
        with open(ACTIVE_USER, "w", encoding="utf-8") as handle:
            handle.write(user_name)
    if project_name is not None:
        with open(ACTIVE_PROJECT, "w", encoding="utf-8") as handle:
            handle.write(project_name)


def clear_active():
    for path in (ACTIVE_USER, ACTIVE_PROJECT):
        if os.path.exists(path):
            os.remove(path)


# --------------------------------------------------------------------------- #
#  Listes USB (whitelist / blacklist du triage anti-Rubber Ducky)
# --------------------------------------------------------------------------- #

def _read_usb_list(path):
    """Lit une liste USB (une entree VID:PID ou numero de serie par ligne)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]
    except OSError:
        return []


def _write_usb_list(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(entries))
        if entries:
            handle.write("\n")


def load_usb_whitelist():
    return _read_usb_list(USB_WHITELIST_FILE)


def load_usb_blacklist():
    return _read_usb_list(USB_BLACKLIST_FILE)


def save_usb_whitelist(entries):
    _write_usb_list(USB_WHITELIST_FILE, entries)


def save_usb_blacklist(entries):
    _write_usb_list(USB_BLACKLIST_FILE, entries)


def list_usb_devices():
    """Inventaire des peripheriques USB connectes (bus USB uniquement).

    Retourne une liste de dicts : port, vid, pid, manufacturer, product,
    serial, hid (True si interface clavier HID), iface (compteur
    d'interfaces detectees). Les hubs racines et controleurs internes ne
    sont pas listes (pas de busnum sur les interfaces, filtre sur la
    presence de idVendor).
    """
    devices = []
    base = "/sys/bus/usb/devices"
    if not os.path.isdir(base):
        return devices
    for name in sorted(os.listdir(base)):
        devdir = os.path.join(base, name)
        if not os.path.isdir(devdir) or ":" in name:
            continue
        try:
            with open(os.path.join(devdir, "busnum"), "r") as fh:
                busnum = fh.read().strip()
        except OSError:
            continue
        if not busnum:
            continue
        def _read(fname):
            try:
                with open(os.path.join(devdir, fname), "r") as fh:
                    return fh.read().strip()
            except OSError:
                return ""
        vid = _read("idVendor")
        if not vid:
            continue
        hid = False
        ifaces = 0
        for sub in os.listdir(devdir):
            subpath = os.path.join(devdir, sub)
            if not os.path.isdir(subpath) or ":" not in sub:
                continue
            ifaces += 1
            try:
                cls = open(os.path.join(subpath, "bInterfaceClass")).read().strip()
                subcls = open(os.path.join(subpath, "bInterfaceSubClass")).read().strip()
                if cls == "03" and subcls == "01":
                    hid = True
            except OSError:
                continue
        devices.append({
            "port": name,
            "vid": vid,
            "pid": _read("idProduct"),
            "manufacturer": _read("manufacturer") or "(inconnu)",
            "product": _read("product") or "(inconnu)",
            "serial": _read("serial"),
            "hid": hid,
            "ifaces": ifaces,
        })
    return devices
