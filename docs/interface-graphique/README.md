# 🖥️ Interface graphique
> Vigil est piloté par une **interface graphique** (GUI) écrite en **Python / Tkinter**,
> organisée en pages parent/enfant. La hiérarchie courante s'affiche toujours dans
> le titre de la fenêtre (ex. `Vigil > Configuration > Utilisateurs`).

---

## 📖 En résumé

La GUI est une page d'accueil avec deux grandes sections : **Configuration**
(entité, projets, périphériques USB, mise à jour antivirus) et **Actions**
(recherche de menaces, analyse, stockage, copie forensique, clonage). Chaque
bouton ouvre une page fille spécialisée ou lance un script d'analyse dans un
terminal **Konsole**. Le thème est **sombre** (palette Tokyo Night), avec des
boutons à **barre d'accent colorée** et une **icône SVG** (Lucide) en noir à
l'intérieur de cette barre.

> **Konsole** est requis : les scripts d'analyse sont interactifs (choix du
> périphérique, confirmations). Le paquet `konsole` est installé par le
> post-install (`scripts/post-install/requirements.txt`).

---

## 🗂️ Pages

| Page | Fichier | Rôle |
|---|---|---|
| 🏠 Accueil | `gui/vigil_main_gui.py` | Page principale : Configuration + Actions |
| ⚙️ Configuration du système | `gui/vigil_config_gui.py` | Entité, coordonnées, logo, utilisateurs |
| 🗂 Gérer les projets | `gui/vigil_project_manager.py` | Création / modification / export des projets |
| 🔌 Périphériques USB | `gui/vigil_usb_gui.py` | Inventaire USB, whitelist / blacklist du triage |
| 🧪 Mise à jour ClamAV | `gui/vigil_clamav_update_gui.py` | Mise à jour des signatures (en ligne ou par USB) |
| 🔍 Analyse du périphérique USB | `gui/vigil_tools_gui.py` | Montage RO + analyses de fichiers + multi-scans |
| 💾 Stockage | `gui/vigil_stockage_gui.py` | Montage lecture/écriture dans `/stockage` |
| 📋 Copie forensique | `gui/vigil_imager_gui.py` | Image RAW/E01/AFF d'un disque |

Les **Actions** de l'accueil qui ne sont pas des pages : la **recherche de
menaces** (`vigil_malware_hunt.sh` — chaîne complète montage → recensement →
audit → ClamAV → démontage, rapport PDF consolidé unique) et le **clonage
bit-à-bit** (`vigil_disk_clone.sh`) sont lancées directement dans Konsole.

## 🧱 Fondations partagées

| Module | Rôle |
|---|---|
| `gui/vigil_gui_base.py` | Thème, fenêtre unique, navigation parent/enfant, widgets réutilisables |
| `gui/vigil_data.py` | Accès aux données (config statique, utilisateurs, projets, chaîne de custody) |
| `gui/vigil_icons.py` | Chargement des icônes Lucide (SVG) + fallback Unicode |

---

## 🎨 Thème et charte

- **Mode sombre** : palette Tokyo Night (`#1e1e2e` fond, `#2a2a3c` surface…).
- **Boutons** : chaque `CategoryButton` est encadré d'une **barre d'accent** verticale
  colorée (28 px) dont la teinte est sémantique (vert = succès, rouge = danger,
  cyan = imagerie, ambre = mise à jour…).
- **Icônes** : rendues en noir dans la barre colorée via `vigil_icons.icon_or_symbol()`.
- **Détails** : voir [theme.md](theme.md) et [icones.md](icones.md).

---

## 🧭 Navigation parent/enfant

La GUI utilise une **fenêtre racine unique invisible** partagée par toutes les
pages. Ouvrir une page fille remplace le contenu du corps et ajoute un bouton
**« Retour »**. Le titre de la fenêtre est reconstruit à partir de la hiérarchie
courante (pile `NAV`), ex. `Vigil > Configuration > Utilisateurs`.

Détails : voir [navigation.md](navigation.md).
