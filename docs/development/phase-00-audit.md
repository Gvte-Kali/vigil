---
layout: default
title: Audit initial — phase 00
parent: Développement
nav_order: 19
---

# Phase 00 — Audit de Vigil 2.0

Référence `a2553bada827cd0e521541b51a4bbc853d416788`. Nouveau clone, `git status -sb` initial `## main...origin/main`. `git branch -a` recensait main, anylinux et deux branches vibe, aucune vigil-2.0. Livrables sur vigil-2.0. `git ls-files` et `find .. -name AGENTS.md` confirment la structure et l'absence d'AGENTS.md racine ou imbriqué dans le clone. AGENTS.md et SPECIFICATIONS.md joints cadrent la méthode et la cible. Le todo.txt suivi est la feuille de route et conserve l'historique. Licence GPL version 3 (`LICENSE:1`).

## Inventaire

Le dépôt suit gui/ (Tkinter), scripts/{Vigil-CLI,analyse,clamav,export,imager,pdf,post-install,stockage}, config/ (deux JSON), data/icons, docs/ (Jekyll) et les fichiers racine. Les chemins installés sont des contrats historiques à vérifier lors d'une recette paquet. L'index statique en fin de document recense les 44 fichiers Bash/Python, avec lignes des options, dépendances détectées et appels littéraux. Les branches interactives et les dépendances implicites se lisent dans le fichier cité.

| Entrée ou famille | Contrat observé |
|---|---|
| Accueil | `gui/vigil_main_gui.py:54,124,180,200,239` ouvre les pages Tk et lance chasse/clonage dans Konsole. `gui/vigil_gui_base.py:41,273,342` lit les montages, lance les pages enfants Python et pose l'icône. |
| Analyse GUI | `gui/vigil_tools_gui.py:87–180,390–402,1090–1170` registre statique de neuf analyses génériques, filtres Windows/XBOX 360/générique/tous, montage/démontage, multi-scan généré côté GUI avec sections PDF. `gui/vigil_data.py:252–315` presets système et personnalisés JSON. Les tags de périphériques relèvent du filtre GUI, vérifier l'affectation lors de chaque ajout. |
| Données et projets | `gui/vigil_data.py:24–45,159–218,335` configuration JSON, profils, fichiers actifs globaux, dossiers projets et custody. `gui/vigil_project_manager.py:64–180` crée, sélectionne, exporte en Konsole et supprime. `gui/vigil_config_gui.py:198–307` gère le logo d'entité et son aperçu, `gui/vigil_usb_gui.py:333` expose l'interface USB. |
| CLI | `scripts/Vigil-CLI/vigil:1–20` est un brouillon de variables. Les trois scripts frères montent, scannent et démontent avec dialogue terminal, chemins fixes, fichiers actifs dont active_entity et logs projet. Le post-install attribue la commande installée `vigil` au GUI (`scripts/post-install/post_install_vigil.sh:96–100,147`). |
| Analyses de fichiers | Recensement à partir de la racine d'investigation, MIME, SHA-256, doublons, checksafe, SQLite/TSV/hash/JSON/PDF (`scripts/analyse/vigil_census.sh:85–93,279,361,679–799,903–934`). Images et EXIF, détection de visages facultative via helper, audio/vidéo avec ffprobe, Office, archives/7za, chiffrement, entropie et gros fichiers/sparse. Les huit analyseurs produisent des listes/JSON/PDF, plusieurs copient avec `--copy-to`. Images possède aussi `--faces` et `--copy-faces-to`, gros fichiers `--min-size`, entropie `--threshold` et `--min-size`. |
| Requête et audit format | `scripts/analyse/vigil_census_query.py:27–105` SQLite et filtres MIME préfixe/extension/mismatch/octet-stream, TSV stdout, codes 0/1/2. `scripts/analyse/vigil_format_audit.py:196–216` index, destination JSON, racine, signatures, budget et mode sans binwalk. Le référentiel signatures se trouve dans config/ au niveau du dépôt. Census cherche ext_mime_map sous la racine de données (`vigil_census.sh:369`), alors que Git le suit sous config/. Vérifier copie de déploiement et fallback. |
| Orchestration | `scripts/vigil_scan_all.sh:53–86,166–231` hauteurs de chemins relatives aux scripts, census puis ClamAV et huit autres analyses, collecte temporaire et PDF multi. La chasse appelle mount/census/audit/scan/unmount/PDF et gère son export (`scripts/clamav/vigil_malware_hunt.sh:57–85,148–180,436`). |
| ClamAV | Scan interactif ou `--all --yes`, options PDF/log, opérateur/commentaire, archives, chiffrement, taille et collecte JSON/log (`scripts/clamav/vigil_clamav_scan.sh:128–151,436–444,623`). Full scan enchaîne montage, scan et démontage (57–87). Update réseau et test EICAR temporaire (update:95), update USB monte dans /stockage (update_usb:36,207–224). GUI update lance ces parcours. |
| Supports | `scripts/analyse/vigil_usb_mount.sh:190–197,308,527,745–769,1182–1241` triage HID et montage bloc/MTP, PDF, journaux. Unmount peut remettre RW (277). Stockage a son propre montage RW, triage, démontage et commandes bloc (`scripts/stockage/vigil_stockage_mount.sh:43–45,310,515,691–693,963–964`, `vigil_stockage_umount.sh:215–220`). |
| Imagerie | GUI imager vers acquisition terminal. Entrées interactives, source bloc et cible disque/dossier. RAW via dc3dd, branche E01, branche AFF annoncée via affcat et dd, logs/hashes par fichier ou segment (`scripts/imager/vigil_disk_imager.sh:416–572,681–799,817`). La branche AFF ne prouve pas la production d'un conteneur AFF valide. Clone bloc-à-bloc dc3dd/dd, vérification de taille et réparation géométrie optionnelle (`scripts/imager/vigil_disk_clone.sh:351,415–427,476–518`). |
| Export et PDF | `scripts/export/vigil_export_project.sh:111–117,130–211` dossier projet → tar.gz, SHA-256 fichiers, hash d'archive. `scripts/pdf/vigil_pdf.py:291–306,680–724,2277–2307` entrées JSON et logs, sections, contexte, destination et préfixe, sortie PDF ReportLab, logo configuré via Pillow. |
| Exploitation | `scripts/post-install/requirements.txt:1–101` inventorie les paquets APT. `scripts/post-install/post_install_vigil.sh:15–16,43,89–147` liste de repli, RDP optionnel, répertoires, sudoers, entrée desktop. `scripts/lsblk_wallpaper.sh:9–32` apt/feh, inventaire lsblk et rendu ImageMagick dans /tmp. `git-reset.sh:1` maintenance Git à lire statiquement. |

Les scripts ordinaires lisent en général `/investigation`, utilisent `/stockage` pour les copies/bases externes et `/opt/vigil/rapports` pour les PDF. Les variantes sont explicites dans l'index. Le contexte et les résultats résident surtout dans `/opt/vigil/data` et les dossiers de projets. Le lanceur chasse tient une custody JSONL dans `$VIGIL_BASE/hunt/chain_of_custody.json` (`vigil_malware_hunt.sh:148,226`). `log_action` relie les scripts à `chain_of_custody.log` et aux journaux d'actions, avec des écritures best-effort dans plusieurs scripts (`vigil_census.sh:181–206`, `vigil_usb_mount.sh:101–134`).

## Identité visuelle

| Asset suivi | SHA-256 |
|---|---|
| `data/icons/vigil.svg` | `9cc9ddbbd7b67d8df8e74f368b9c6c0fe7e6c7c495a95c2a93d4b12d386637ff` |
| `docs/favicon.ico` | `f4a4e1de522a9a75533b3d7473dc5048f8c5d2649da4b604ae2455772ade1f2d` |

Source vectorielle versionnée depuis 24902a3, favicon versionné depuis 71a4d0a (`git log --all --oneline -- data/icons/vigil.svg docs/favicon.ico`). Usages observés : accueil (`gui/vigil_main_gui.py:93–100`), icône de fenêtres (`gui/vigil_gui_base.py:342–346`), chargement dans `gui/vigil_icons.py:78–100`, installation hicolor et entrée desktop (`post_install_vigil.sh:131–149`), favicon Pages (`docs/_config.yml:14–16`). Le logo d'entité est un fichier choisi par l'utilisateur (`gui/vigil_data.py:90–130`, `vigil_pdf.py:680–724`). Pour Qt, charger le SVG suivi et comparer les deux empreintes à la recette ; conserver l'entrée desktop et le favicon.

## Risques et mesures

| Priorité | Constat et preuve | Mesure |
|---|---|---|
| P0 | NOPASSWD global et opérations root génériques (`post_install_vigil.sh:102–121`). | Broker root-owned, groupe dédié et politiques d'opérations, chemins et arguments validés. Audit des propriétaires avant déploiement. |
| P0 | Checksafe charge des pickles extérieurs (`vigil_census.sh:569–621`). | SQLite/TSV avec schéma et tailles bornés ; préserver le filtrage par nom/hash ; import à partir de données structurées de confiance. |
| P0 | Montage peut continuer si blockdev échoue et quelques chemins remettent RW (`vigil_usb_mount.sh:995–1022,1182–1241`, `vigil_disk_clone.sh:257–264,380,399`). | Liens parent/enfants et identité noyau vérifiés à l'ouverture puis avant opération ; strict refuse, triage expose état et consentement ; nettoyage des ressources possédées. |
| P0 | MTP passe `-o ro` à jmtpfs (`vigil_usb_mount.sh:745–769`). | Statut protocole séparé, acquisition de copie conditionnelle et analyse de la copie. |
| P0 | Destinations de copie, export et image résolues par différents chemins, avec validation hétérogène (`vigil_images.sh:61–75`, `vigil_disk_imager.sh:512–572`, `vigil_export_project.sh:111–145`). | Vérifier descripteurs/chemins réels, identités de montage et bloc, alias et races avant écriture. Créer les nouvelles sorties sous une racine autorisée via des descripteurs. |
| P1 | Fichiers actifs relus, recensement supprime des résultats précédents, chasse s'appuie sur son répertoire partagé (`vigil_data.py:33–34`, `vigil_census.sh:138–152`, `vigil_malware_hunt.sh:148,436`). | Identifiant de run, contexte figé et livrables immuables. |
| P1 | Lancements Konsole et processus enfants, visibilité partielle (`vigil_tools_gui.py:228–249,1167`, `vigil_gui_base.py:273`). | Groupe détenu, statut et code retour tracés, annulation et réconciliation en phases 02/05. |
| P1 | Manifestes et tar issus de lectures séparées du dossier vivant (`vigil_export_project.sh:154–211`). | Lot figé, manifeste vérifié sur contenu exact, publication atomique et conservation des échecs. |
| P1 | ClamAV plafonné à 512/2047 M selon mode, archives et chiffrement conditionnels (`vigil_clamav_scan.sh:138–143,436–444`). | Distinguer détecté, non détecté et non analysé ; publier compteurs disponibles, plafonds, chiffrement, refus et erreurs. |
| P1 | Parseurs de preuves et aperçu logo via Pillow (`vigil_format_audit.py:196–216`, `vigil_config_gui.py:228–244`). | Aperçu de preuve inerte, parseurs isolés, quotas et limites de type ; tester fichiers corrompus et très volumineux. |
| P2 | Paquets conditionnels et liste de repli, outils présents dans la liste et variables selon distribution (`requirements.txt:1–101`, `post_install_vigil.sh:15–16`). | Capabilities versionnées et recette sur les trois distributions ; signaler chaque dégradation. |

## Décisions historiques examinées

1. Garder le recensement explicite. Le chemin standard de montage est indépendant du census ; la chasse appelle les deux (`vigil_malware_hunt.sh:61–65,436`). Une option après validation du montage est faisable via le service d'exécution, avec choix PDF, consentement, capacité vérifiée et conservation des runs avant activation. Coût en I/O et impact sur le délai de montage à mesurer.
2. Réutiliser l'index si identité et fraîcheur vérifiables. `find_latest_index` compare le dernier segment après underscore (heure seule, risque inter-jours), et `query_files` ouvre SQLite sans mode RO explicite ni vérification d'identité ou sélection d'inventaire (`vigil_census_query.py:27–73`). Exiger identifiant d'acquisition/partition, identifiant du montage et génération, schéma, complétude, métadonnées et horodatage UTC, digest et profil de collecte. Sur mutation, horodatage ambigu, filtre incomplet ou erreur, journaliser le motif et lancer l'analyse standalone autorisée. Prévoir tests de sélection inter-jours et de discordance d'une source remontée au même chemin.
3. Étendre l'audit avec raisons structurées et distinction entre extension absente, contenu générique, signature inconnue, discordance, erreur d'accès et budget atteint. Le détecteur actuel cible mismatch et octet-stream (`vigil_format_audit.py:196–216` et index ci-dessous). Tester texte UTF-8/UTF-16, fichiers système sans extension et fichiers vides ; listes d'exceptions et heuristiques versionnées, faux positifs visibles, identité du détecteur conservée. Prioriser la revue humaine avec seuils mesurés.

## Index statique des sources

Généré avec `git ls-files` et recherche par expressions régulières dans les fichiers suivis. Une ligne est un repère syntaxique, y compris les commentaires et branches conditionnelles. Les références dynamiques se lisent dans les parcours ci-dessus.

### `git-reset.sh`

`1` #!/bin/bash

### `gui/vigil_clamav_update_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (1)</summary>

```text
158: def main():
```

</details>

<details><summary>Dépendances (7)</summary>

```text
10: import os
11: import subprocess
12: import tkinter as tk
13: from tkinter import messagebox
15: import vigil_data
16: import vigil_gui_base as base
17: from vigil_gui_base import (
```

</details>

<details><summary>Chemins, formats et appels (5)</summary>

```text
5: 1. Mise a jour en ligne (freshclam) -- le script vigil_clamav_update.sh ;
6: 2. Mise a jour par peripherique USB -- le script vigil_clamav_update_usb.sh
70: lambda: window.go_back("vigil_main_gui.py",
110: "clamav", "vigil_clamav_update.sh")
112: "clamav", "vigil_clamav_update_usb.sh")
```

</details>

### `gui/vigil_config_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (2)</summary>

```text
340: def main():
342: args = sys.argv[1:]
```

</details>

<details><summary>Dépendances (9)</summary>

```text
18: import os
19: import tkinter as tk
20: from datetime import datetime
21: from tkinter import filedialog, messagebox, ttk
23: import vigil_data
24: import vigil_gui_base as base
25: from vigil_gui_base import (
236: from PIL import Image as PILImage, ImageTk
341: import sys
```

</details>

<details><summary>Chemins, formats et appels (3)</summary>

```text
144: "vigil_config_gui.py", nav_label="Configuration"), icon="arrow-left").pack(side=tk.RIGHT)
328: "vigil_config_gui.py", "users", nav_label="Utilisateurs"), icon="circle-user").pack(
331: "vigil_main_gui.py", nav_label="Vigil"), icon="home").pack(side=tk.RIGHT)
```

</details>

### `gui/vigil_data.py`

`1` #!/usr/bin/env python3

<details><summary>Dépendances (5)</summary>

```text
18: import json
19: import os
20: import shutil
21: from datetime import datetime
229: import zipfile
```

</details>

<details><summary>Chemins, formats et appels (3)</summary>

```text
23: BASE_DIR = os.environ.get("VIGIL_BASE", "/opt/vigil")
30: CONFIG_FILE = os.path.join(CONFIG_DIR, "system.json")
252: PRESETS_FILE = os.path.join(DATA_DIR, "presets.json")
```

</details>

<details><summary>Privilèges et custody (3)</summary>

```text
199: """Cree un projet et initialise son fichier ``chain_of_custody.log``."""
207: custody_path = os.path.join(project_dir, "chain_of_custody.log")
335: custody_path = os.path.join(project_dir, "chain_of_custody.log")
```

</details>

### `gui/vigil_gui_base.py`

`1` #!/usr/bin/env python3

<details><summary>Dépendances (8)</summary>

```text
18: import os
19: import sys
20: import subprocess
21: import tkinter as tk
22: from tkinter import ttk, messagebox
24: import vigil_data
25: import vigil_icons as icons
179: import signal
```

</details>

<details><summary>Chemins, formats et appels (1)</summary>

```text
32: MOUNT_POINTS = ("/investigation", "/stockage")
```

</details>

### `gui/vigil_icons.py`

`1` #!/usr/bin/env python3

<details><summary>Dépendances (3)</summary>

```text
4: import os
5: import tkinter as tk
69: import cairosvg
```

</details>

### `gui/vigil_imager_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (1)</summary>

```text
159: def main():
```

</details>

<details><summary>Dépendances (7)</summary>

```text
10: import os
11: import subprocess
12: import tkinter as tk
13: from tkinter import messagebox
15: import vigil_data
16: import vigil_gui_base as base
17: from vigil_gui_base import (
```

</details>

<details><summary>Chemins, formats et appels (3)</summary>

```text
6: shell scripts/imager/vigil_disk_imager.sh gère l'interaction CLI (choix du
71: lambda: window.go_back("vigil_main_gui.py",
140: "imager", "vigil_disk_imager.sh")
```

</details>

### `gui/vigil_main_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Dépendances (8)</summary>

```text
9: import os
10: import subprocess
11: import tkinter as tk
12: from tkinter import messagebox
14: import vigil_data
15: import vigil_icons as icons
16: import vigil_gui_base as base
17: from vigil_gui_base import (
```

</details>

<details><summary>Chemins, formats et appels (9)</summary>

```text
124: command=lambda: window.open_child("vigil_config_gui.py", nav_label="Configuration"),
135: command=lambda: window.open_child("vigil_project_manager.py", nav_label="Configuration"),
147: "vigil_usb_gui.py", nav_label="Configuration"),
157: command=lambda: window.open_child("vigil_clamav_update_gui.py", nav_label="ClamAV"),
181: "clamav", "vigil_malware_hunt.sh")
200: command=lambda: window.open_child("vigil_tools_gui.py", nav_label="Analyse du périphérique USB"),
211: command=lambda: window.open_child("vigil_stockage_gui.py", nav_label="Stockage"),
222: command=lambda: window.open_child("vigil_imager_gui.py", nav_label="Imagerie"),
240: "imager", "vigil_disk_clone.sh")
```

</details>

### `gui/vigil_project_manager.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (1)</summary>

```text
185: def main():
```

</details>

<details><summary>Dépendances (9)</summary>

```text
10: import os
11: import subprocess
12: import sys
13: import tkinter as tk
14: from datetime import datetime
15: from tkinter import messagebox, ttk, filedialog
17: import vigil_data
18: import vigil_gui_base as base
19: from vigil_gui_base import (
```

</details>

<details><summary>Chemins, formats et appels (2)</summary>

```text
140: "export", "vigil_export_project.sh")
180: "vigil_main_gui.py", nav_label="Vigil"), icon="home").pack(side=tk.RIGHT)
```

</details>

### `gui/vigil_stockage_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (1)</summary>

```text
188: def main():
```

</details>

<details><summary>Dépendances (7)</summary>

```text
10: import os
11: import subprocess
12: import tkinter as tk
13: from tkinter import messagebox
15: import vigil_data
16: import vigil_gui_base as base
17: from vigil_gui_base import (
```

</details>

<details><summary>Chemins, formats et appels (3)</summary>

```text
89: lambda: window.go_back("vigil_main_gui.py",
152: "stockage", "vigil_stockage_mount.sh")
158: "stockage", "vigil_stockage_umount.sh")
```

</details>

### `gui/vigil_tools_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (1)</summary>

```text
1396: def main():
```

</details>

<details><summary>Dépendances (9)</summary>

```text
23: import os
24: import subprocess
25: import tkinter as tk
26: from tkinter import messagebox, ttk, filedialog
28: import vigil_data
29: import vigil_gui_base as base
30: import vigil_icons as icons
31: from vigil_gui_base import (
1138: f"command -v python3 >/dev/null 2>&1; then "
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
9: (voir vigil_config_gui.py). Le scan antivirus ClamAV n'est PAS géré ici :
90: "analyse/vigil_census.sh",
99: "analyse/vigil_images.sh",
109: "analyse/vigil_videos.sh",
117: "analyse/vigil_audio.sh",
125: "analyse/vigil_office.sh",
133: "analyse/vigil_archives.sh",
141: "analyse/vigil_crypto.sh",
149: "analyse/vigil_entropy.sh",
157: "analyse/vigil_bigfiles.sh",
170: # rapport PDF consolide via vigil_pdf.py --kind multi.
172: "analyse/vigil_census.sh": ("census", "vigil_census.json"),
173: "analyse/vigil_images.sh": ("images", "vigil_images.json"),
174: "analyse/vigil_videos.sh": ("videos", "vigil_videos.json"),
175: "analyse/vigil_audio.sh": ("audio", "vigil_audio.json"),
176: "analyse/vigil_office.sh": ("office", "vigil_office.json"),
177: "analyse/vigil_archives.sh": ("archives", "vigil_archives.json"),
178: "analyse/vigil_crypto.sh": ("crypto", "vigil_crypto.json"),
179: "analyse/vigil_entropy.sh": ("entropy", "vigil_entropy.json"),
180: "analyse/vigil_bigfiles.sh": ("bigfiles", "vigil_bigfiles.json"),
261: source de vérité du noyau : on lit directement ce fichier (2e champ =
302: lambda: window.go_back("vigil_main_gui.py",
390: command=lambda: launch_optional("analyse/vigil_usb_mount.sh"),
402: command=lambda: launch_optional("analyse/vigil_usb_umount.sh"),
1090: user, project = require_context("analyse/vigil_usb_mount.sh")
1106: # vigil_pdf.py --kind multi assemble un seul rapport avec sommaire.
1108: pdf_script = os.path.join(scripts_dir, "pdf", "vigil_pdf.py")
```

</details>

### `gui/vigil_usb_gui.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (1)</summary>

```text
333: def main():
```

</details>

<details><summary>Dépendances (6)</summary>

```text
15: import re
17: import tkinter as tk
18: from tkinter import messagebox, simpledialog, ttk
20: import vigil_data
21: from vigil_gui_base import (
339: import vigil_gui_base as base
```

</details>

<details><summary>Chemins, formats et appels (2)</summary>

```text
8: anti-Rubber Ducky de vigil_usb_mount.sh) ;
63: lambda: window.go_back("vigil_main_gui.py",
```

</details>

### `scripts/Vigil-CLI/vigil`

`1` #!/bin/bash

<details><summary>Chemins, formats et appels (6)</summary>

```text
15: ENTITIES_DIR="/opt/vigil/data/entities"
16: PROJECTS_DIR="/opt/vigil/data/projects"
17: SCRIPT_DIR="/opt/vigil/scripts"
18: ACTIVE_PROJECT_FILE="/opt/vigil/data/active_project"
19: ACTIVE_ENTITY_FILE="/opt/vigil/data/active_entity"
20: ACTIVE_USER_FILE="/opt/vigil/data/active_user"
```

</details>

### `scripts/Vigil-CLI/vigil_analyse.sh`

`1` #!/bin/bash

<details><summary>Interface (9)</summary>

```text
43: --arg timestamp "$timestamp" \
44: --arg user "$ACTIVE_USER" \
45: --arg entity "$ACTIVE_ENTITY" \
46: --arg project "$ACTIVE_PROJECT" \
47: --arg action "$action" \
48: --arg device "$device" \
49: --arg file_path "$file_path" \
50: --arg status "$status" \
51: --arg message "$message" \
```

</details>

<details><summary>Chemins, formats et appels (6)</summary>

```text
11: ACTIVE_PROJECT_FILE="/opt/vigil/data/active_project"
12: ACTIVE_ENTITY_FILE="/opt/vigil/data/active_entity"
13: ACTIVE_USER_FILE="/opt/vigil/data/active_user"
14: PROJECTS_DIR="/opt/vigil/data/projects"
24: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_ENTITY/$ACTIVE_USER/$ACTIVE_PROJECT"
106: ANALYSIS_LOG="$PROJECT_LOG_DIR/clamav_$(basename "$SELECTED_MOUNT_POINT").log"
```

</details>

<details><summary>Privilèges et custody (4)</summary>

```text
30: log_action() {
40: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null
53: | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null
107: sudo clamscan -r --bell "$SELECTED_MOUNT_POINT" | tee "$ANALYSIS_LOG"
```

</details>

### `scripts/Vigil-CLI/vigil_mount.sh`

`1` #!/bin/bash

<details><summary>Interface (11)</summary>

```text
17: --mode)
21: --no-log)
73: --arg timestamp "$timestamp" \
74: --arg user "$ACTIVE_USER" \
75: --arg entity "$ACTIVE_ENTITY" \
76: --arg project "$ACTIVE_PROJECT" \
77: --arg action "$action" \
78: --arg device "$device" \
79: --arg file_path "$file_path" \
80: --arg status "$status" \
81: --arg message "$message" \
```

</details>

<details><summary>Dépendances (1)</summary>

```text
165: if command -v jmtpfs &>/dev/null; then
```

</details>

<details><summary>Chemins, formats et appels (15)</summary>

```text
33: ACTIVE_PROJECT_FILE="/opt/vigil/data/active_project"
34: ACTIVE_ENTITY_FILE="/opt/vigil/data/active_entity"
35: ACTIVE_USER_FILE="/opt/vigil/data/active_user"
36: PROJECTS_DIR="/opt/vigil/data/projects"
48: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_ENTITY/$ACTIVE_USER/$ACTIVE_PROJECT"
169: MTP_DEVICES=$(jmtpfs -l 2>/dev/null | grep -E "^Device [0-9]+" || true)
219: TRAN=$(lsblk -dno TRAN "/dev/$PKNAME" 2>/dev/null || echo "")
221: SIZE=$(lsblk -dno SIZE "/dev/$NAME" 2>/dev/null || echo "")
222: MODEL=$(lsblk -dno MODEL "/dev/$PKNAME" 2>/dev/null || echo "")
272: DEVICE_PATH="/dev/$SELECTED_DEVICE"
289: DEVICE_SIGNATURE=$(dd if="$DEVICE_PATH" bs=11 count=1 status=none 2>/dev/null | base64 || true)
304: MOUNT_POINT="/investigation/${SELECTED_DEVICE}"
341: FSTYPE=$(lsblk -no FSTYPE "$DEVICE_PATH" 2>/dev/null || echo "")
387: HASH_FILE="$PROJECT_LOG_DIR/device_${SELECTED_DEVICE}.sha256"
406: ANALYSIS_LOG="$PROJECT_LOG_DIR/clamav_${SELECTED_DEVICE}.log"
```

</details>

<details><summary>Privilèges et custody (15)</summary>

```text
52: sudo mkdir -p /investigation
53: sudo chmod 755 /investigation
56: log_action() {
70: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null
83: | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null
96: sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null
148: sudo clamscan -r --bell /investigation/cdrom > "$PROJECT_LOG_DIR/clamav_cdrom.log" 2>&1
177: sudo mkdir -p /investigation/mtp
189: sudo rmdir /investigation/mtp 2>/dev/null
312: sudo mkdir -p "$MOUNT_POINT" || {
359: sudo mount $MOUNT_OPTS "$DEVICE_PATH" "$MOUNT_POINT" 2>&1
376: sudo umount "$MOUNT_POINT" 2>/dev/null
377: sudo rmdir "$MOUNT_POINT" 2>/dev/null
388: sudo rm -f "$HASH_FILE"
407: sudo clamscan -r --bell "$MOUNT_POINT" > "$ANALYSIS_LOG" 2>&1
```

</details>

### `scripts/Vigil-CLI/vigil_unmount.sh`

`1` #!/bin/bash

<details><summary>Interface (10)</summary>

```text
16: --no-log)
66: --arg timestamp "$timestamp" \
67: --arg user "$ACTIVE_USER" \
68: --arg entity "$ACTIVE_ENTITY" \
69: --arg project "$ACTIVE_PROJECT" \
70: --arg action "$action" \
71: --arg device "$device" \
72: --arg file_path "$file_path" \
73: --arg status "$status" \
74: --arg message "$message" \
```

</details>

<details><summary>Chemins, formats et appels (8)</summary>

```text
28: ACTIVE_PROJECT_FILE="/opt/vigil/data/active_project"
29: ACTIVE_ENTITY_FILE="/opt/vigil/data/active_entity"
30: ACTIVE_USER_FILE="/opt/vigil/data/active_user"
31: PROJECTS_DIR="/opt/vigil/data/projects"
43: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_ENTITY/$ACTIVE_USER/$ACTIVE_PROJECT"
149: CURRENT_HASH=$(find "$SELECTED_MOUNT_POINT" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' 2>/dev/null || true)
150: HASH_FILE="$PROJECT_LOG_DIR/device_$(basename "$DEVICE").sha256"
160: STORED_HASH=$(cat "$HASH_FILE" 2>/dev/null || true)
```

</details>

<details><summary>Privilèges et custody (4)</summary>

```text
49: log_action() {
63: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null
76: | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null
222: sudo rmdir "$SELECTED_MOUNT_POINT" 2>/dev/null || {
```

</details>

### `scripts/analyse/vigil_archives.sh`

`1` #!/bin/bash

<details><summary>Interface (13)</summary>

```text
51: --pdf)              GEN_PDF=1 ;;
52: --no-pdf)           GEN_PDF=0 ;;
53: --copy-to)          shift; COPY_TO="${1:-}" ;;
54: --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
55: --json-out)         shift; JSON_OUT="${1:-}" ;;
56: --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
214: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
341: archive_list, sha_file, out, date, total, count, prot_cnt, prot_avail, prot_file = sys.argv[1:10]
417: --kind archives \
418: --json "$JSON_FILE" \
419: --user "$ACTIVE_USER" \
420: --project "$ACTIVE_PROJECT" \
421: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (8)</summary>

```text
77: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
123: for cmd in file find stat; do
124: if ! command -v "$cmd" >/dev/null 2>&1; then
131: if command -v 7za >/dev/null 2>&1; then
211: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
336: if command -v python3 >/dev/null 2>&1; then
340: import json, sys
414: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
40: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
41: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
43: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
60: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
61: PROJECTS_DIR="$VIGIL_BASE/data/projects"
62: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
63: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
66: RAPPORTS_DIR="$VIGIL_BASE/rapports"
75: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
78: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
114: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
176: ARCHIVE_LIST="$WORK_DIR/archive_list.tsv"
183: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
186: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
187: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
188: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
189: REL="${f#$INVESTIGATION_DIR/}"
202: JSON_FILE="$WORK_DIR/resultat.json"
203: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
210: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
283: PROTECTED_FILE="$WORK_DIR/protected.tsv"
313: SHA_FILE="$WORK_DIR/sha256.tsv"
331: JSON_FILE="$WORK_DIR/resultat.json"
332: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
337: python3 - "$ARCHIVE_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
402: TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
413: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
101: log_action() {
105: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_audio.sh`

`1` #!/bin/bash

<details><summary>Interface (13)</summary>

```text
60: --pdf)              GEN_PDF=1 ;;
61: --no-pdf)           GEN_PDF=0 ;;
62: --copy-to)          shift; COPY_TO="${1:-}" ;;
63: --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
64: --json-out)         shift; JSON_OUT="${1:-}" ;;
65: --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
226: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
390: audio_list, sha_file, out, date, total, count, dur_ok, dur_fail, ffprobe, dur_json = sys.argv[1:11]
460: --kind audio \
461: --json "$JSON_FILE" \
462: --user "$ACTIVE_USER" \
463: --project "$ACTIVE_PROJECT" \
464: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (9)</summary>

```text
86: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
134: for cmd in file find; do
135: if ! command -v "$cmd" >/dev/null 2>&1; then
142: if command -v ffprobe >/dev/null 2>&1; then
223: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
385: if command -v python3 >/dev/null 2>&1; then
389: import json, sys
432: import json as _j
457: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
46: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
47: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
49: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
69: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
70: PROJECTS_DIR="$VIGIL_BASE/data/projects"
71: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
72: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
75: RAPPORTS_DIR="$VIGIL_BASE/rapports"
84: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
87: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
125: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
188: AUDIO_LIST="$WORK_DIR/audio_list.tsv"
195: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
198: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
199: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
200: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
203: REL="${f#$INVESTIGATION_DIR/}"
214: JSON_FILE="$WORK_DIR/resultat.json"
215: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
222: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
298: DURATION_JSON="$WORK_DIR/durations.tsv"
349: SHA_FILE="$WORK_DIR/sha256.tsv"
367: JSON_FILE="$WORK_DIR/resultat.json"
368: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
386: python3 - "$AUDIO_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
445: TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
456: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
112: log_action() {
116: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_bigfiles.sh`

`1` #!/bin/bash

<details><summary>Interface (15)</summary>

```text
58: --pdf)              GEN_PDF=1 ;;
59: --no-pdf)           GEN_PDF=0 ;;
60: --copy-to)         shift; COPY_TO="${1:-}" ;;
61: --copy-to=*)       COPY_TO="${1#--copy-to=}" ;;
62: --min-size)        shift; MIN_SIZE_MB="${1:-$MIN_SIZE_MB}" ;;
63: --min-size=*)      MIN_SIZE_MB="${1#--min-size=}" ;;
64: --json-out)        shift; JSON_OUT="${1:-}" ;;
65: --json-out=*)      JSON_OUT="${1#--json-out=}" ;;
231: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
370: sparse_list, sha_file, out, date, total, count, sparse_cnt, min_mb = sys.argv[1:9]
443: --kind bigfiles \
444: --json "$JSON_FILE" \
445: --user "$ACTIVE_USER" \
446: --project "$ACTIVE_PROJECT" \
447: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (7)</summary>

```text
100: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
148: for cmd in file find stat; do
149: if ! command -v "$cmd" >/dev/null 2>&1; then
228: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
366: if command -v python3 >/dev/null 2>&1; then
369: import json, sys
440: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
42: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
43: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
46: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
81: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
82: PROJECTS_DIR="$VIGIL_BASE/data/projects"
83: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
84: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
88: RAPPORTS_DIR="$VIGIL_BASE/rapports"
97: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
101: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
139: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
194: BIGFILE_LIST="$WORK_DIR/bigfile_list.tsv"
200: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
202: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
207: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
208: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
209: REL="${f#$INVESTIGATION_DIR/}"
220: JSON_FILE="$WORK_DIR/resultat.json"
221: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
227: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
270: SPARSE_LIST="$WORK_DIR/sparse_list.tsv"
345: SHA_FILE="$WORK_DIR/sha256.tsv"
363: JSON_FILE="$WORK_DIR/resultat.json"
364: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
367: python3 - "$SPARSE_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
428: TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
439: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
126: log_action() {
130: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_census.sh`

`1` #!/bin/bash

<details><summary>Interface (21)</summary>

```text
85: --pdf)          GEN_PDF=1 ;;
86: --no-pdf)       GEN_PDF=0 ;;
87: --no-dedup)     DO_DEDUP=0 ;;
88: --no-checksafe) DO_CHECKSAFE=0 ;;
89: --no-project)   DO_NO_PROJECT=1 ;;
90: --user)    shift; HUNT_USER="${1:-}" ;;
91: --user=*)  HUNT_USER="${1#--user=}" ;;
92: --json-out)       shift; JSON_OUT="${1:-}" ;;
93: --json-out=*)     JSON_OUT="${1#--json-out=}" ;;
188: --arg timestamp "$timestamp" \
189: --arg user "$ACTIVE_USER" \
190: --arg action "census" \
191: --arg status "$1" \
192: --arg message "$2" \
307: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
389: vigil_version, ext_map_file, no_project) = sys.argv[1:18]
907: --kind census \
908: --json "$JSON_FILE" \
909: --user "$ACTIVE_USER" \
910: --project "$ACTIVE_PROJECT" \
911: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (15)</summary>

```text
120: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
186: if command -v jq >/dev/null 2>&1; then
212: for cmd in file find python3; do
213: if ! command -v "$cmd" >/dev/null 2>&1; then
220: if command -v pv >/dev/null 2>&1; then
252: elif command -v find >/dev/null 2>&1 \
304: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
378: import os
379: import sys
380: import json
381: import sqlite3
382: import hashlib
383: import pickle
384: from datetime import datetime, timezone
904: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (26)</summary>

```text
31: #   - rapports PDF via scripts/pdf/vigil_pdf.py (kind=census) ;
57: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
58: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
60: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
61: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
62: PROJECTS_DIR="$VIGIL_BASE/data/projects"
63: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
64: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
65: STOCKAGE_DIR="${VIGIL_STOCKAGE_DIR:-/stockage}"
68: RAPPORTS_DIR="$VIGIL_BASE/rapports"
109: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
121: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
126: PROJECT_LOG_DIR="$VIGIL_BASE/hunt"
129: PROJECT_LOG_DIR="/tmp"
132: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
279: RAW_LIST="$WORK_DIR/raw_list.tsv"
296: JSON_FILE="$WORK_DIR/resultat.json"
297: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
303: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
340: MIME_LIST="$WORK_DIR/mime_list.tsv"
356: MIME_COUNT=$(wc -l < "$WORK_DIR/mime_types.txt")
366: JSON_FILE="$WORK_DIR/resultat.json"
367: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
369: EXT_MAP_FILE="$VIGIL_DATA_DIR/config/ext_mime_map.json"
372: python3 - "$RAW_LIST" "$WORK_DIR/mime_types.txt" "$WORK_DIR/mime_encodings.txt" \
903: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (3)</summary>

```text
179: log_action() {
181: # aussi journalise dans hunt/chain_of_custody.json (section custody du
206: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_census_query.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (6)</summary>

```text
76: def main():
79: ap.add_argument("--index", required=True,
81: ap.add_argument("--mismatched", action="store_true",
83: ap.add_argument("--octet-stream", action="store_true",
85: ap.add_argument("--mime", default="",
87: ap.add_argument("--extension", default="",
```

</details>

<details><summary>Dépendances (5)</summary>

```text
19: import argparse
20: import glob
21: import os
22: import sqlite3
23: import sys
```

</details>

<details><summary>Chemins, formats et appels (5)</summary>

```text
6: l'index produit par vigil_census.sh au lieu de re-parcourir /investigation
10: vigil_census_query.py --index <census.sqlite> --mismatched
11: vigil_census_query.py --index <census.sqlite> --octet-stream
12: vigil_census_query.py --index <census.sqlite> --mime image/
13: vigil_census_query.py --index <census.sqlite> --extension jpg
```

</details>

### `scripts/analyse/vigil_crypto.sh`

`1` #!/bin/bash

<details><summary>Interface (13)</summary>

```text
51: --pdf)              GEN_PDF=1 ;;
52: --no-pdf)           GEN_PDF=0 ;;
53: --copy-to)          shift; COPY_TO="${1:-}" ;;
54: --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
55: --json-out)         shift; JSON_OUT="${1:-}" ;;
56: --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
215: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
354: locked_list, sha_file, out, date, total, cand, locked, lock_avail = sys.argv[1:9]
420: --kind crypto \
421: --json "$JSON_FILE" \
422: --user "$ACTIVE_USER" \
423: --project "$ACTIVE_PROJECT" \
424: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (8)</summary>

```text
77: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
123: for cmd in file find stat; do
124: if ! command -v "$cmd" >/dev/null 2>&1; then
131: if command -v 7za >/dev/null 2>&1; then
212: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
350: if command -v python3 >/dev/null 2>&1; then
353: import json, sys
417: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
40: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
41: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
43: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
60: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
61: PROJECTS_DIR="$VIGIL_BASE/data/projects"
62: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
63: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
66: RAPPORTS_DIR="$VIGIL_BASE/rapports"
75: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
78: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
114: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
177: CANDIDATE_LIST="$WORK_DIR/candidate_list.tsv"
184: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
187: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
188: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
189: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
190: REL="${f#$INVESTIGATION_DIR/}"
203: JSON_FILE="$WORK_DIR/resultat.json"
204: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
211: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
250: LOCKED_LIST="$WORK_DIR/locked_list.tsv"
329: SHA_FILE="$WORK_DIR/sha256.tsv"
347: JSON_FILE="$WORK_DIR/resultat.json"
348: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
351: python3 - "$LOCKED_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
405: TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
416: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
101: log_action() {
105: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_entropy.sh`

`1` #!/bin/bash

<details><summary>Interface (18)</summary>

```text
66: --pdf)              GEN_PDF=1 ;;
67: --no-pdf)           GEN_PDF=0 ;;
68: --copy-to)         shift; COPY_TO="${1:-}" ;;
69: --copy-to=*)       COPY_TO="${1#--copy-to=}" ;;
70: --threshold)       shift; ENTROPY_THRESHOLD="${1:-$ENTROPY_THRESHOLD}" ;;
71: --threshold=*)     ENTROPY_THRESHOLD="${1#--threshold=}" ;;
72: --min-size)        shift; MIN_SIZE="${1:-$MIN_SIZE}" ;;
73: --min-size=*)      MIN_SIZE="${1#--min-size=}" ;;
74: --json-out)        shift; JSON_OUT="${1:-}" ;;
75: --json-out=*)      JSON_OUT="${1#--json-out=}" ;;
238: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
325: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
425: entropy_list, sha_file, out, date, total, cand, cnt, ent_avail, threshold, min_size = sys.argv[1:11]
500: --kind entropy \
501: --json "$JSON_FILE" \
502: --user "$ACTIVE_USER" \
503: --project "$ACTIVE_PROJECT" \
504: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (9)</summary>

```text
99: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
147: for cmd in file find stat; do
148: if ! command -v "$cmd" >/dev/null 2>&1; then
156: if command -v zstd >/dev/null 2>&1; then
235: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
322: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
420: if command -v python3 >/dev/null 2>&1; then
424: import json, sys
497: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (29)</summary>

```text
48: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
49: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
52: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
80: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
81: PROJECTS_DIR="$VIGIL_BASE/data/projects"
82: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
83: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
87: RAPPORTS_DIR="$VIGIL_BASE/rapports"
96: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
100: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
138: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
203: CANDIDATE_LIST="$WORK_DIR/candidate_list.tsv"
209: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
211: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
213: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
214: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
215: REL="${f#$INVESTIGATION_DIR/}"
226: JSON_FILE="$WORK_DIR/resultat.json"
227: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
234: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
281: ENTROPY_LIST="$WORK_DIR/entropy_list.tsv"
313: JSON_FILE="$WORK_DIR/resultat.json"
314: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
321: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
397: SHA_FILE="$WORK_DIR/sha256.tsv"
415: JSON_FILE="$WORK_DIR/resultat.json"
416: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
421: python3 - "$ENTROPY_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
496: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
125: log_action() {
129: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_faces_detection.sh`

`1` #!/bin/bash

<details><summary>Interface (2)</summary>

```text
172: selected_file = sys.argv[1]
173: faces_list = sys.argv[2]
```

</details>

<details><summary>Dépendances (6)</summary>

```text
80: if command -v facedetect >/dev/null 2>&1; then
83: elif command -v python3 >/dev/null 2>&1 && python3 -c "import cv2" 2>/dev/null; then
162: import sys
163: import os
164: import cv2
240: if command -v jq >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (11)</summary>

```text
10: #   $1 : le dossier d'analyse (OUTPUT_DIR) créé par vigil_images.sh
45: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
46: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
47: ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null || echo "(inconnu)")
109: ALL_IMAGES=$(cut -f1 "$IMAGE_LIST" 2>/dev/null | grep -v '^$' || true)
110: TOTAL_CANDIDATES=$(echo "$ALL_IMAGES" | grep -c '.' 2>/dev/null || echo 0)
141: FACES_LIST="$FACES_DIR/.faces_${STAMP}.txt"
159: SELECTED_FILE="$FACES_DIR/.selected_${STAMP}.txt"
161: python3 - "$SELECTED_FILE" "$FACES_LIST" <<'PYEOF' || ERRORS=$((ERRORS+1))
201: FACES_FOUND=$(grep -c '.' "$FACES_LIST" 2>/dev/null || echo 0)
239: FACES_JSON="$OUTPUT_DIR/faces_result.json"
```

</details>

### `scripts/analyse/vigil_format_audit.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (7)</summary>

```text
196: def main():
200: ap.add_argument("--index", required=True,
202: ap.add_argument("--out", required=True,
204: ap.add_argument("--investigation", default="/investigation",
206: ap.add_argument("--signatures", default="",
208: ap.add_argument("--max-files", type=int, default=500,
210: ap.add_argument("--no-binwalk", action="store_true",
```

</details>

<details><summary>Dépendances (11)</summary>

```text
26: import argparse
27: import json
28: import math
29: import os
30: import shutil
31: import subprocess
32: import sys
35: from vigil_census_query import query_files  # noqa: E402
72: import zlib
98: import zlib
139: import tempfile
```

</details>

<details><summary>Chemins, formats et appels (2)</summary>

```text
18: Sortie : JSON exploite par vigil_pdf.py (--kind formataudit) et consolide
22: vigil_format_audit.py --index census.sqlite --out resultat.json \
```

</details>

### `scripts/analyse/vigil_images.sh`

`1` #!/bin/bash

<details><summary>Interface (16)</summary>

```text
61: --pdf)              GEN_PDF=1 ;;
62: --no-pdf)           GEN_PDF=0 ;;
63: --faces)            DO_FACES=1 ;;
64: --copy-to)          shift; COPY_TO="${1:-}" ;;
65: --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
66: --copy-faces-to)    shift; COPY_FACES_TO="${1:-}" ;;
67: --copy-faces-to=*)  COPY_FACES_TO="${1#--copy-faces-to=}" ;;
68: --json-out)         shift; JSON_OUT="${1:-}" ;;
69: --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
228: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
388: exif_ok, exif_fail, exif_avail) = sys.argv[1:11]
462: --kind images \
463: --json "$JSON_FILE" \
464: --user "$ACTIVE_USER" \
465: --project "$ACTIVE_PROJECT" \
466: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (8)</summary>

```text
90: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
138: for cmd in file find; do
139: if ! command -v "$cmd" >/dev/null 2>&1; then
146: if command -v exiftool >/dev/null 2>&1; then
225: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
382: if command -v python3 >/dev/null 2>&1; then
386: import json, os, sys
459: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (31)</summary>

```text
43: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
44: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
46: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
73: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
74: PROJECTS_DIR="$VIGIL_BASE/data/projects"
75: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
76: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
79: RAPPORTS_DIR="$VIGIL_BASE/rapports"
88: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
91: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
129: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
192: IMAGE_LIST="$WORK_DIR/image_list.tsv"
199: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
202: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
203: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
204: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
205: REL="${f#$INVESTIGATION_DIR/}"
216: JSON_FILE="$WORK_DIR/resultat.json"
217: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
224: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
312: OUT=$(exiftool -short -short -short -tab -q "$path" 2>/dev/null)
332: FACES_SCRIPT="$(dirname "$0")/vigil_faces_detection.sh"
335: bash "$FACES_SCRIPT" "$WORK_DIR" "$IMAGE_LIST" --copy-to "$COPY_FACES_TO" || {
340: bash "$FACES_SCRIPT" "$WORK_DIR" "$IMAGE_LIST" || {
345: FACES_JSON="$WORK_DIR/faces_result.json"
358: SHA_FILE="$WORK_DIR/sha256.tsv"
376: JSON_FILE="$WORK_DIR/resultat.json"
377: DATE_ANALYSIS=$(date +"%d/%m/%Y \u00e0 %H:%M:%S")
383: python3 - "$IMAGE_LIST" "$SHA_FILE" "$FACES_JSON" "$JSON_FILE" \
447: TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
458: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
116: log_action() {
120: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_office.sh`

`1` #!/bin/bash

<details><summary>Interface (13)</summary>

```text
88: --pdf)              GEN_PDF=1 ;;
89: --no-pdf)           GEN_PDF=0 ;;
90: --copy-to)          shift; COPY_TO="${1:-}" ;;
91: --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
92: --json-out)         shift; JSON_OUT="${1:-}" ;;
93: --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
259: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
371: office_list, sha_file, out, date, total, count = sys.argv[1:7]
441: --kind office \
442: --json "$JSON_FILE" \
443: --user "$ACTIVE_USER" \
444: --project "$ACTIVE_PROJECT" \
445: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (7)</summary>

```text
114: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
174: for cmd in file find stat; do
175: if ! command -v "$cmd" >/dev/null 2>&1; then
256: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
367: if command -v python3 >/dev/null 2>&1; then
370: import json, sys
438: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
48: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
49: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
51: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
97: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
98: PROJECTS_DIR="$VIGIL_BASE/data/projects"
99: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
100: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
103: RAPPORTS_DIR="$VIGIL_BASE/rapports"
112: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
115: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
165: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
219: OFFICE_LIST="$WORK_DIR/office_list.tsv"
235: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
236: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
237: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
238: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
239: REL="${f#$INVESTIGATION_DIR/}"
248: JSON_FILE="$WORK_DIR/resultat.json"
249: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
255: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
344: SHA_FILE="$WORK_DIR/sha256.tsv"
362: JSON_FILE="$WORK_DIR/resultat.json"
363: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
368: python3 - "$OFFICE_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
425: CAT_JSON=$(for c in "${!CAT_COUNT[@]}"; do printf '"%s":%s,' "$c" "${CAT_COUNT[$c]}"; done | sed 's/,$//')
426: EXT_JSON=$(for e in "${!EXT_COUNT[@]}"; do printf '"%s":%s,' "$e" "${EXT_COUNT[$e]}"; done | sed 's/,$//')
437: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
140: log_action() {
144: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/analyse/vigil_usb_mount.sh`

`1` #!/bin/bash

<details><summary>Interface (17)</summary>

```text
110: --arg timestamp "$timestamp" \
111: --arg user "$_user" \
112: --arg action "$action" \
113: --arg status "$status" \
114: --arg message "$message" \
115: --arg device "$device" \
136: --arg timestamp "$timestamp" \
137: --arg user "$ACTIVE_USER" \
138: --arg entity "$ACTIVE_ENTITY" \
139: --arg project "$ACTIVE_PROJECT" \
140: --arg action "$action" \
141: --arg device "$device" \
142: --arg file_path "$file_path" \
143: --arg status "$status" \
144: --arg message "$message" \
529: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" \
530: --dir "$VIGIL_BASE/rapports" --config-dir "$VIGIL_DATA_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (18)</summary>

```text
57: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
108: if command -v jq >/dev/null 2>&1; then
134: if command -v jq >/dev/null 2>&1; then
162: if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
190: for cmd in lsblk mount find sha256sum; do
191: if ! command -v "$cmd" >/dev/null 2>&1; then
197: for cmd in jq cryptsetup clamscan jmtpfs eject blockdev; do
198: if ! command -v "$cmd" >/dev/null 2>&1; then
527: && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
727: if command -v eject >/dev/null 2>&1 && eject -t /dev/cdrom 2>/dev/null; then
745: if command -v jmtpfs >/dev/null 2>&1; then
785: if [ -z "$fs" ] && command -v blkid >/dev/null 2>&1; then
789: if [ -z "$lbl" ] && command -v blkid >/dev/null 2>&1; then
995: if command -v blockdev >/dev/null 2>&1; then
1022: command -v blockdev >/dev/null 2>&1 && sudo blockdev --setrw "$dev" 2>/dev/null || true
1035: if command -v cryptsetup >/dev/null 2>&1 && cryptsetup isLuks "$dev" 2>/dev/null; then
1182: if command -v blockdev >/dev/null 2>&1; then
1232: if command -v blockdev >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (22)</summary>

```text
34: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
35: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
36: USB_LISTS_DIR="$VIGIL_DATA_DIR/usb"
37: USB_WHITELIST_FILE="$USB_LISTS_DIR/whitelist.txt"
38: USB_BLACKLIST_FILE="$USB_LISTS_DIR/blacklist.txt"
41: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
42: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
43: PROJECTS_DIR="$VIGIL_BASE/data/projects"
44: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
58: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
63: PROJECT_LOG_DIR="/tmp"
65: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
490: USBHID_JSON="$TRIAGE_DIR/usbhid.json"
491: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
513: # defini (chemin de collecte de vigil_malware_hunt.sh), le triage est
525: PDF_SCRIPT="$VIGIL_BASE/scripts/pdf/vigil_pdf.py"
747: MTP_DEVICES=$(jmtpfs -l 2>/dev/null | grep -E "^Device [0-9]+" || true)
818: LSBLK_OUT=$(lsblk -P -o NAME,TYPE,PKNAME,MOUNTPOINT,TRAN,RM,SIZE,MODEL 2>/dev/null || true)
842: IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
898: IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
1219: DEVICE_PATH="/dev/$SELECTED_DEVICE"
1229: MOUNT_POINT="/investigation/$SELECTED_DEVICE"
```

</details>

<details><summary>Privilèges et custody (19)</summary>

```text
93: log_action() {
101: # hunt/chain_of_custody.json (section custody du rapport consolide),
132: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
146: | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
179: sudo mkdir -p /investigation 2>/dev/null || true
180: sudo chmod 755 /investigation 2>/dev/null || true
226: sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null && {
729: sudo mkdir -p /investigation/cdrom 2>/dev/null || true
738: sudo rmdir /investigation/cdrom 2>/dev/null || true
753: sudo mkdir -p /investigation/mtp 2>/dev/null || true
762: sudo rmdir /investigation/mtp 2>/dev/null || true
960: sudo blockdev --setro "/dev/$m_name" 2>/dev/null || true
989: sudo mkdir -p "$mnt" 2>/dev/null || {
996: sudo blockdev --setro "$dev" 2>/dev/null || true
1011: sudo mount $mount_opts "$dev" "$mnt" 2>&1 || true
1013: sudo rmdir "$mnt" 2>/dev/null || true
1020: sudo umount "$mnt" 2>/dev/null || true
1021: sudo rmdir "$mnt" 2>/dev/null || true
1057: sudo rm -f "$hash_file"
```

</details>

### `scripts/analyse/vigil_usb_umount.sh`

`1` #!/bin/bash

<details><summary>Interface (15)</summary>

```text
85: --arg timestamp "$timestamp" \
86: --arg user "$_user" \
87: --arg action "$action" \
88: --arg status "$status" \
89: --arg message "$message" \
90: --arg device "$device" \
112: --arg timestamp "$timestamp" \
113: --arg user "$ACTIVE_USER" \
114: --arg entity "$ACTIVE_ENTITY" \
115: --arg project "$ACTIVE_PROJECT" \
116: --arg action "$action" \
117: --arg device "$device" \
118: --arg file_path "$file_path" \
119: --arg status "$status" \
120: --arg message "$message" \
```

</details>

<details><summary>Dépendances (4)</summary>

```text
47: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
83: if command -v jq >/dev/null 2>&1; then
109: if command -v jq >/dev/null 2>&1; then
138: if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (11)</summary>

```text
30: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
31: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
32: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
33: PROJECTS_DIR="$VIGIL_BASE/data/projects"
34: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
48: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
53: PROJECT_LOG_DIR="/tmp"
55: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
223: CURRENT_HASH=$(find "$MOUNT_POINT" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' 2>/dev/null || true)
224: HASH_FILE="$PROJECT_LOG_DIR/device_$(basename "$DEVICE").sha256"
230: STORED_HASH=$(cat "$HASH_FILE" 2>/dev/null || true)
```

</details>

<details><summary>Privilèges et custody (9)</summary>

```text
68: log_action() {
76: # hunt/chain_of_custody.json (section custody du rapport consolide),
107: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
122: [ -n "$json_entry" ] && echo "$json_entry" | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
168: sudo mkdir -p /investigation 2>/dev/null || true
186: sudo rmdir "$dir" 2>/dev/null && {
277: sudo blockdev --setrw "$DEVICE" 2>/dev/null && \
288: sudo rmdir "$MOUNT_POINT" 2>/dev/null && {
326: sudo rmdir "$dir" 2>/dev/null && {
```

</details>

### `scripts/analyse/vigil_videos.sh`

`1` #!/bin/bash

<details><summary>Interface (13)</summary>

```text
59: --pdf)              GEN_PDF=1 ;;
60: --no-pdf)           GEN_PDF=0 ;;
61: --copy-to)          shift; COPY_TO="${1:-}" ;;
62: --copy-to=*)        COPY_TO="${1#--copy-to=}" ;;
63: --json-out)         shift; JSON_OUT="${1:-}" ;;
64: --json-out=*)       JSON_OUT="${1#--json-out=}" ;;
225: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" --dir "$RAPPORTS_DIR" 2>&1)
388: video_list, sha_file, out, date, total, count, dur_ok, dur_fail, ffprobe, dur_json = sys.argv[1:11]
458: --kind videos \
459: --json "$JSON_FILE" \
460: --user "$ACTIVE_USER" \
461: --project "$ACTIVE_PROJECT" \
462: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (9)</summary>

```text
85: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
133: for cmd in file find; do
134: if ! command -v "$cmd" >/dev/null 2>&1; then
141: if command -v ffprobe >/dev/null 2>&1; then
222: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
383: if command -v python3 >/dev/null 2>&1; then
387: import csv, json, sys
430: import json as _j
455: if [ -f "$JSON_FILE" ] && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
45: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
46: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
48: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
68: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
69: PROJECTS_DIR="$VIGIL_BASE/data/projects"
70: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
71: INVESTIGATION_DIR="${VIGIL_INVESTIGATION_DIR:-/investigation}"
74: RAPPORTS_DIR="$VIGIL_BASE/rapports"
83: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
86: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
124: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
187: VIDEO_LIST="$WORK_DIR/video_list.tsv"
194: MIME=$(file --mime-type -b "$f" 2>/dev/null || echo "")
197: SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
198: MTIME=$(stat -c%Y "$f" 2>/dev/null || echo 0)
199: MTIME_ISO=$(date -d "@$MTIME" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "")
202: REL="${f#$INVESTIGATION_DIR/}"
213: JSON_FILE="$WORK_DIR/resultat.json"
214: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
221: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
297: DURATION_JSON="$WORK_DIR/durations.tsv"
347: SHA_FILE="$WORK_DIR/sha256.tsv"
365: JSON_FILE="$WORK_DIR/resultat.json"
366: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
384: python3 - "$VIDEO_LIST" "$SHA_FILE" "$JSON_FILE" "$DATE_ANALYSIS" \
443: TYPES_JSON=$(for t in "${!TYPE_COUNT[@]}"; do printf '"%s":%s,' "$t" "${TYPE_COUNT[$t]}"; done | sed 's/,$//')
454: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
111: log_action() {
115: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
```

</details>

### `scripts/clamav/vigil_clamav_full_scan.sh`

`1` #!/bin/bash

<details><summary>Interface (12)</summary>

```text
71: --pdf)    SCAN_ARGS+=(--pdf) ;;
72: --no-pdf) SCAN_ARGS+=(--no-pdf) ;;
73: --log)    SCAN_ARGS+=(--log) ;;
74: --no-log) SCAN_ARGS+=(--no-log) ;;
75: --user)
79: --user=*)
82: --archives)    SCAN_ARGS+=(--archives) ;;
83: --no-archives) SCAN_ARGS+=(--no-archives) ;;
84: --size-unlimited) SCAN_ARGS+=(--size-unlimited); SIZE_SET=1; SIZE_MODE="unlimited" ;;
85: --size-limit)     SCAN_ARGS+=(--size-limit); SIZE_SET=1; SIZE_MODE="limit" ;;
86: --alert-encrypted)    SCAN_ARGS+=(--alert-encrypted) ;;
87: --no-alert-encrypted) SCAN_ARGS+=(--no-alert-encrypted) ;;
```

</details>

<details><summary>Chemins, formats et appels (11)</summary>

```text
50: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
51: USERS_DIR="$VIGIL_BASE/data/users"
52: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
56: SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
57: MOUNT_SCRIPT="$SCRIPT_DIR/analyse/vigil_usb_mount.sh"
58: SCAN_SCRIPT="$SCRIPT_DIR/clamav/vigil_clamav_scan.sh"
59: UMOUNT_SCRIPT="$SCRIPT_DIR/analyse/vigil_usb_umount.sh"
137: ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
193: bash "$MOUNT_SCRIPT"
237: bash "$SCAN_SCRIPT" "${SCAN_ARGS[@]}" --all --yes --comment "" --user "$ACTIVE_USER"
256: bash "$UMOUNT_SCRIPT"
```

</details>

### `scripts/clamav/vigil_clamav_scan.sh`

`1` #!/bin/bash

<details><summary>Interface (26)</summary>

```text
18: # Usage : vigil_clamav_scan.sh [--pdf|--no-pdf] [--all] [--comment TXT] [--yes] [--user NOM] [--archives|--no-archives] [--json-out DIR]
128: --pdf)        GEN_PDF=1; PDF_SET=1 ;;
129: --no-pdf)     GEN_PDF=0; PDF_SET=1 ;;
130: --log)        GEN_LOG=1; LOG_SET=1 ;;
131: --no-log)     GEN_LOG=0; LOG_SET=1 ;;
132: --all)        SCAN_ALL=1 ;;
133: --comment)    shift; SCAN_COMMENT="${1:-}"; COMMENT_SET=1 ;;
134: --comment=*) SCAN_COMMENT="${1#--comment=}"; COMMENT_SET=1 ;;
135: --yes)        AUTO_YES=1 ;;
136: --user)       shift; ARG_USER="${1:-}" ;;
137: --user=*)     ARG_USER="${1#--user=}" ;;
138: --archives)   SCAN_ARCHIVES=1; ARCHIVES_SET=1 ;;
139: --no-archives) SCAN_ARCHIVES=0; ARCHIVES_SET=1 ;;
140: --size-unlimited) SIZE_MODE="unlimited"; SIZE_SET=1 ;;
141: --size-limit)     SIZE_MODE="limit"; SIZE_SET=1 ;;
142: --alert-encrypted)    ALERT_ENC=1; ALERT_ENC_SET=1 ;;
143: --no-alert-encrypted) ALERT_ENC=0; ALERT_ENC_SET=1 ;;
144: --json-out)    shift; JSON_OUT_DIR="${1:-}" ;;
145: --json-out=*)  JSON_OUT_DIR="${1#--json-out=}" ;;
616: --kind clamav \
618: --user "$ACTIVE_USER" \
619: --project "" \
620: --action "$ACTION_LABEL" \
621: --options="--recursive --bell $CLAM_OPTS" \
622: --comment "$SCAN_COMMENT" \
623: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (3)</summary>

```text
164: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
289: if ! command -v clamscan >/dev/null 2>&1; then
614: elif command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (19)</summary>

```text
18: # Usage : vigil_clamav_scan.sh [--pdf|--no-pdf] [--all] [--comment TXT] [--yes] [--user NOM] [--archives|--no-archives] [--json-out DIR]
94: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
95: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
149: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
150: CONFIG_FILE="$VIGIL_DATA_DIR/config/system.json"
151: INVESTIGATION_DIR="/investigation"
152: RAPPORTS_DIR="$VIGIL_BASE/rapports"
165: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
198: # le journal : le générateur PDF (vigil_pdf.py) n'en utilise que le résumé
292: echo -e "${YELLOW}    Puis mettez à jour les bases : sudo bash $(dirname "$0")/vigil_clamav_update.sh${NC}"
299: DB_DIR=$(clamconf 2>/dev/null | sed -nE 's/^\s*DatabaseDirectory\s*=\s*"?([^"]*)"?\s*$/\1/p' | tail -1)
308: echo -e "  ${GREY}Mettez à jour les bases :${NC} ${BOLD}sudo bash $(dirname "$0")/vigil_clamav_update.sh${NC}"
516: TOTAL_FILES=$(find "$target" -type f 2>/dev/null | wc -l)
522: RAPPORT="$RAPPORTS_DIR/clamav_${target_name}_${STAMP}.log"
527: TMP_LOG="$(mktemp --tmpdir "clamav_${target_name}_${STAMP}.XXXXXX.log" 2>/dev/null || echo "/tmp/clamav_${target_name}_${STAMP}_$$.log")"
553: INFECTED=$(grep -i "Infected files:" "$LOG_FILE" 2>/dev/null | awk -F: '{print $2}' | xargs || echo "0")
555: SCANNED=$(grep -i "Scanned files:" "$LOG_FILE" 2>/dev/null | awk -F: '{print $2}' | xargs || echo "0")
576: # (clamav_<dossier>.log) pour etre assembles par vigil_pdf.py --kind multi.
604: PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
```

</details>

<details><summary>Privilèges et custody (1)</summary>

```text
544: sudo clamscan --recursive --bell $CLAM_OPTS "$target" 2>&1 \
```

</details>

### `scripts/clamav/vigil_clamav_update.sh`

`1` #!/bin/bash

<details><summary>Interface (1)</summary>

```text
10: # Usage : vigil_clamav_update.sh
```

</details>

<details><summary>Dépendances (2)</summary>

```text
59: for cmd in freshclam clamscan; do
60: if ! command -v "$cmd" >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (4)</summary>

```text
10: # Usage : vigil_clamav_update.sh
95: EICAR_TMP=$(mktemp 2>/dev/null || echo "/tmp/vigil_eicar_$$.tmp")
102: EICAR_OUT=$(cat "${EICAR_TMP}.out" 2>/dev/null)
122: DB_DIR=$(clamconf 2>/dev/null | sed -nE 's/^\s*DatabaseDirectory\s*=\s*"?([^"]*)"?\s*$/\1/p' | tail -1)
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
71: sudo systemctl stop clamav-freshclam 2>/dev/null || true
115: sudo systemctl start clamav-freshclam 2>/dev/null || true
```

</details>

### `scripts/clamav/vigil_clamav_update_usb.sh`

`1` #!/bin/bash

<details><summary>Dépendances (3)</summary>

```text
69: for cmd in lsblk mount umount find blockdev clamscan clamconf; do
70: if ! command -v "$cmd" >/dev/null 2>&1; then
207: if command -v blockdev >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (10)</summary>

```text
36: STOCKAGE_DIR="/stockage"
78: DB_DIR=$(clamconf 2>/dev/null | sed -nE 's/^\s*DatabaseDirectory\s*=\s*"?([^"]*)"?\s*$/\1/p' | tail -1)
137: LSBLK_OUT=$(lsblk -P -o NAME,TYPE,PKNAME,MOUNTPOINT,TRAN,RM,SIZE,MODEL 2>/dev/null || true)
196: DEVICE_PATH="/dev/$SELECTED_DEVICE"
201: MOUNT_POINT="$STOCKAGE_DIR/${SELECTED_DEVICE}"
212: FSTYPE=$(lsblk -no FSTYPE "$DEVICE_PATH" 2>/dev/null || echo "")
241: FOUND_PATH=$(find "$MOUNT_POINT" -maxdepth 3 -type f -iname "$cvd" 2>/dev/null | head -n 1 || true)
243: FILE_SIZE=$(ls -lh "$FOUND_PATH" 2>/dev/null | awk '{print $5}')
311: EICAR_TMP=$(mktemp 2>/dev/null || echo "/tmp/vigil_eicar_$$.tmp")
315: EICAR_OUT=$(cat "${EICAR_TMP}.out" 2>/dev/null)
```

</details>

<details><summary>Privilèges et custody (18)</summary>

```text
94: sudo mkdir -p "$STOCKAGE_DIR" 2>/dev/null || true
99: sudo umount "$dir" 2>/dev/null || sudo umount -l "$dir" 2>/dev/null || true
101: sudo blockdev --setrw "$DEVICE" 2>/dev/null || true
103: sudo rmdir "$dir" 2>/dev/null || true
204: sudo mkdir -p "$MOUNT_POINT" 2>/dev/null || fail "Impossible de créer le point de montage $MOUNT_POINT."
208: sudo blockdev --setro "$DEVICE_PATH" 2>/dev/null || echo -e "${YELLOW}⚠️  blockdev --setro a échoué (non bloquant).${NC}"
223: sudo mount $MOUNT_OPTS "$DEVICE_PATH" "$MOUNT_POINT" 2>&1 || true
224: sudo blockdev --setrw "$DEVICE_PATH" 2>/dev/null || true
225: sudo rmdir "$MOUNT_POINT" 2>/dev/null || true
258: sudo umount "$MOUNT_POINT" 2>/dev/null || sudo umount -l "$MOUNT_POINT" 2>/dev/null || true
259: sudo blockdev --setrw "$DEVICE_PATH" 2>/dev/null || true
260: sudo rmdir "$MOUNT_POINT" 2>/dev/null || true
280: sudo cp "$CVD_PATH" "$DB_DIR/$CVD_NAME" 2>/dev/null && {
281: sudo chown clamav:clamav "$DB_DIR/$CVD_NAME" 2>/dev/null || true
282: sudo chmod 644 "$DB_DIR/$CVD_NAME" 2>/dev/null || true
295: sudo umount "$MOUNT_POINT" 2>/dev/null || sudo umount -l "$MOUNT_POINT" 2>/dev/null || true
297: sudo rmdir "$MOUNT_POINT" 2>/dev/null || true
301: sudo blockdev --setrw "$DEVICE_PATH" 2>/dev/null || true
```

</details>

### `scripts/clamav/vigil_malware_hunt.sh`

`1` #!/bin/bash

<details><summary>Interface (23)</summary>

```text
76: --pdf)    SCAN_ARGS+=(--pdf) ;;
77: --no-pdf) SCAN_ARGS+=(--no-pdf) ;;
78: --log)    SCAN_ARGS+=(--log) ;;
79: --no-log) SCAN_ARGS+=(--no-log) ;;
80: --user)   shift; ACTIVE_USER="${1:-}" ;;
81: --user=*) ACTIVE_USER="${1#--user=}" ;;
82: --no-archives)        SCAN_ARGS+=(--no-archives) ;;
83: --size-limit)         SCAN_ARGS+=(--size-limit) ;;
84: --no-alert-encrypted) SCAN_ARGS+=(--no-alert-encrypted) ;;
177: --getexistingdirectory "$HOME" 2>/dev/null || true)
180: --file-selection --directory 2>/dev/null || true)
239: --arg timestamp "$timestamp" \
240: --arg user "$ACTIVE_USER" \
241: --arg action "$action" \
242: --arg status "$status" \
243: --arg message "$message" \
353: --user "$ACTIVE_USER" \
354: --project "Recherche de menaces" \
355: --fname-prefix "$FNAME_PREFIX" \
356: --dir "$RAPPORTS_DIR" 2>&1)
429: --user "$ACTIVE_USER" --json-out "$COLLECT_DIR"
452: --out "$COLLECT_DIR/vigil_formataudit.json"
474: --user "$ACTIVE_USER" --no-pdf --json-out "$COLLECT_DIR"
```

</details>

<details><summary>Dépendances (4)</summary>

```text
175: if command -v kdialog >/dev/null 2>&1; then
178: elif command -v zenity >/dev/null 2>&1; then
234: if command -v jq >/dev/null 2>&1; then
297: command -v python3 >/dev/null 2>&1 || {
```

</details>

<details><summary>Chemins, formats et appels (24)</summary>

```text
16: #   6. UN SEUL rapport PDF consolide (vigil_pdf.py --kind multi) :
23: # SQLite du recensement (vigil_census.sh --no-project) est un livrable
57: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
58: USERS_DIR="$VIGIL_BASE/data/users"
59: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
60: SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
61: MOUNT_SCRIPT="$SCRIPT_DIR/analyse/vigil_usb_mount.sh"
62: UMOUNT_SCRIPT="$SCRIPT_DIR/analyse/vigil_usb_umount.sh"
63: CENSUS_SCRIPT="$SCRIPT_DIR/analyse/vigil_census.sh"
64: AUDIT_SCRIPT="$SCRIPT_DIR/analyse/vigil_format_audit.py"
65: SCAN_SCRIPT="$SCRIPT_DIR/clamav/vigil_clamav_scan.sh"
66: PDF_SCRIPT="$SCRIPT_DIR/pdf/vigil_pdf.py"
67: RAPPORTS_DIR="$VIGIL_BASE/rapports"
90: ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
141: # il est ecrit dans hunt/ (via vigil_census.sh --no-project) et
147: HUNT_DIR="$VIGIL_BASE/hunt"
148: CUSTODY_JSON="$VIGIL_BASE/hunt/chain_of_custody.json"
322: COLLECT_DIR="$HUNT_DIR/collect"
375: bash "$MOUNT_SCRIPT"
428: bash "$CENSUS_SCRIPT" --no-project --no-pdf \
436: CENSUS_DB=$(ls -t "$HUNT_DIR"/census_*.sqlite 2>/dev/null | head -1 || true)
451: python3 "$AUDIT_SCRIPT" --index "$CENSUS_DB" \
473: bash "$SCAN_SCRIPT" "${SCAN_ARGS[@]}" --all --yes --comment "" \
492: bash "$UMOUNT_SCRIPT"
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
148: CUSTODY_JSON="$VIGIL_BASE/hunt/chain_of_custody.json"
226: # statut, detail) dans hunt/chain_of_custody.json (JSONL, un objet par
```

</details>

### `scripts/export/vigil_export_project.sh`

`1` #!/bin/bash

<details><summary>Interface (2)</summary>

```text
20: # Usage : vigil_export_project.sh [--dest DIR]
111: --dest) DEST_DIR="$2"; shift 2 ;;
```

</details>

<details><summary>Dépendances (3)</summary>

```text
79: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
117: for cmd in sha256sum tar find; do
118: if ! command -v "$cmd" >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (16)</summary>

```text
20: # Usage : vigil_export_project.sh [--dest DIR]
40: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
41: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
44: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
45: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
46: PROJECTS_DIR="$VIGIL_BASE/data/projects"
47: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
48: RAPPORTS_DIR="$VIGIL_BASE/rapports"
77: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
80: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
90: PROJECT_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
143: ARCHIVE="$DEST_DIR/${BASE_NAME}.tar.gz"
144: SHA_LIST="$DEST_DIR/${BASE_NAME}.sha256"
145: HASH_ARCHIVE="$DEST_DIR/${BASE_NAME}.hash_archive.sha256"
193: ARCHIVE_SIZE=$(stat -c%s "$ARCHIVE" 2>/dev/null || echo 0)
206: ARCHIVE_HASH=$(sha256sum "$ARCHIVE" 2>/dev/null | awk '{print $1}')
```

</details>

<details><summary>Privilèges et custody (4)</summary>

```text
18: #   - l'export est journalise dans chain_of_custody.log du projet.
99: log_action() {
104: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
156: # Le fichier chain_of_custody.log sera inclus (livrable forensique).
```

</details>

### `scripts/imager/vigil_disk_clone.sh`

`1` #!/bin/bash

<details><summary>Dépendances (10)</summary>

```text
92: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
132: for cmd in lsblk blockdev sync; do
133: if ! command -v "$cmd" >/dev/null 2>&1; then
138: if ! command -v dc3dd >/dev/null 2>&1; then
413: if command -v dc3dd >/dev/null 2>&1; then
480: if command -v sgdisk >/dev/null 2>&1; then
484: elif command -v parted >/dev/null 2>&1; then
495: if command -v sgdisk >/dev/null 2>&1; then
513: if command -v growpart >/dev/null 2>&1; then
520: if command -v resize2fs >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (13)</summary>

```text
47: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
48: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
49: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
50: PROJECTS_DIR="$VIGIL_BASE/data/projects"
83: PROJECT_LOG_DIR="/tmp"
85: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
89: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
90: CONFIG_FILE="$VIGIL_DATA_DIR/config/system.json"
93: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
240: SOURCE_DEV="/dev/${SOURCE_DEVICES[$((SOURCE_CHOICE-1))]}"
249: SOURCE_MOUNTED=$(lsblk -ln -o MOUNTPOINT "$SOURCE_DEV" 2>/dev/null | grep -v '^$' | head -1 || true)
343: TARGET_DEV="/dev/${TARGET_DEVICES[$((TARGET_CHOICE-1))]}"
370: TARGET_MOUNTED=$(lsblk -ln -o MOUNTPOINT "$TARGET_DEV" 2>/dev/null | grep -v '^$' | head -1 || true)
```

</details>

<details><summary>Privilèges et custody (14)</summary>

```text
98: log_action() {
106: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
264: sudo blockdev --setro "$SOURCE_DEV" 2>/dev/null || true
326: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
334: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
358: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
380: sudo blockdev --setrw "$TARGET_DEV" 2>/dev/null || true
399: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
481: sudo sgdisk -e "$TARGET_DEV" 2>&1 && \
485: sudo parted -s "$TARGET_DEV" print 2>&1
496: sudo sgdisk -e "$TARGET_DEV" 2>&1 && \
521: sudo e2fsck -fy "$_partdev" 2>&1 || true
522: sudo resize2fs "$_partdev" 2>&1 && \
570: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
```

</details>

### `scripts/imager/vigil_disk_imager.sh`

`1` #!/bin/bash

<details><summary>Dépendances (7)</summary>

```text
61: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
112: for cmd in lsblk blockdev sync; do
113: if ! command -v "$cmd" >/dev/null 2>&1; then
121: command -v ewfacquire >/dev/null 2>&1 && _HAVE_EWF=1
122: command -v dc3dd >/dev/null 2>&1 && _HAVE_DC3DD=1
124: command -v affcat >/dev/null 2>&1 && _HAVE_AFF=1
125: command -v affuse >/dev/null 2>&1 && _HAVE_AFF=1
```

</details>

<details><summary>Chemins, formats et appels (21)</summary>

```text
36: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
37: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
38: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
39: PROJECTS_DIR="$VIGIL_BASE/data/projects"
52: PROJECT_LOG_DIR="/tmp"
54: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
58: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
59: CONFIG_FILE="$VIGIL_DATA_DIR/config/system.json"
62: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
241: SOURCE_DEV="/dev/${SOURCE_DEVICES[$((SOURCE_CHOICE-1))]}"
249: SOURCE_MOUNTED=$(lsblk -ln -o MOUNTPOINT "$SOURCE_DEV" 2>/dev/null | grep -v '^$' | head -1 || true)
389: IMAGE_NAME=$(echo "$IMAGE_NAME" | tr -d '/' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
497: TARGET_DEV="/dev/${TARGET_DEVICES[$((TARGET_CHOICE-1))]}"
530: TARGET_POINT=$(mktemp -dp /tmp/ .vigilimg.XXXXXXXX)
550: IMAGE_DIR="$TARGET_POINT/vigil_images"
556: IMAGE_BASE="$IMAGE_DIR/$(echo "$IMAGE_ID" | tr ' /' '__')"
571: IMAGE_DIR=$(echo "$IMAGE_DIR" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
588: ROOT_FS=$(df --output=target "$IMAGE_DIR" 2>/dev/null | tail -1 | tr -d '[:space:]')
596: RESERVE_BYTES=$((TOTAL_BYTES / 5))
601: SOURCE_BYTES=$(sudo blockdev --getsize64 "$SOURCE_DEV" 2>/dev/null || echo 0)
655: IMAGE_BASE="$IMAGE_DIR/$(echo "$IMAGE_ID" | tr ' /' '__')"
```

</details>

<details><summary>Privilèges et custody (19)</summary>

```text
67: log_action() {
75: echo "$log_entry" | tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
267: sudo blockdev --setro "$SOURCE_DEV" 2>/dev/null || true
427: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
435: sudo umount "$TARGET_POINT" 2>/dev/null || sudo umount -l "$TARGET_POINT" 2>/dev/null || true
479: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
487: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
505: sudo blockdev --setrw "$TARGET_DEV" 2>/dev/null || true
525: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
535: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
542: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
546: sudo rm -f "$TARGET_POINT/.vigil_rw_test" 2>/dev/null || true
551: sudo mkdir -p "$IMAGE_DIR" 2>/dev/null || {
552: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
624: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
637: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
650: sudo mkdir -p "$IMAGE_DIR" 2>/dev/null || {
651: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
853: sudo blockdev --setrw "$SOURCE_DEV" 2>/dev/null || true
```

</details>

### `scripts/lsblk_wallpaper.sh`

`1` #!/bin/bash

<details><summary>Dépendances (2)</summary>

```text
5: if ! command -v convert &> /dev/null; then
9: if ! command -v feh &> /dev/null; then
```

</details>

<details><summary>Privilèges et custody (2)</summary>

```text
7: sudo apt install -y imagemagick
11: sudo apt install -y feh
```

</details>

### `scripts/pdf/vigil_pdf.py`

`1` #!/usr/bin/env python3

<details><summary>Interface (16)</summary>

```text
12: --json <resultat.json>  (images, videos)
13: --log  <scan.log>        (clamav) \
14: --user "..." --project "..." --dir <dossier_rapports> \
2277: def main():
2281: ap.add_argument("--kind", required=True,
2284: ap.add_argument("--json", default="",
2286: ap.add_argument("--log", default=[], action="append",
2289: ap.add_argument("--section", default=[], action="append",
2294: ap.add_argument("--user", default="")
2295: ap.add_argument("--project", default="")
2296: ap.add_argument("--action", default="", help="Action sur infectés (clamav)")
2297: ap.add_argument("--options", default="", help="Options clamscan (clamav)")
2298: ap.add_argument("--comment", default="",
2300: ap.add_argument("--dir", default="/opt/vigil/rapports",
2302: ap.add_argument("--fname-prefix", default="",
2305: ap.add_argument("--config-dir", default="",
```

</details>

<details><summary>Dépendances (8)</summary>

```text
21: import argparse
22: import json
23: import os
24: import re
25: from datetime import datetime
672: import re as _re
686: from PIL import Image as PILImage
2278: import sys
```

</details>

<details><summary>Chemins, formats et appels (1)</summary>

```text
11: vigil_pdf.py --kind images|videos|clamav \
```

</details>

<details><summary>Privilèges et custody (1)</summary>

```text
2105: # chain_of_custody.json est un JSONL (un objet par
```

</details>

### `scripts/post-install/post_install_vigil.sh`

`1` #!/bin/bash

<details><summary>Dépendances (3)</summary>

```text
71: if command -v usbguard-daemon >/dev/null 2>&1 || dpkg -l usbguard >/dev/null 2>&1; then
157: if command -v kbuildsycoca6 >/dev/null 2>&1; then
159: elif command -v kbuildsycoca5 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (8)</summary>

```text
15: REQUIREMENTS_FILE="/opt/vigil/scripts/post-install/requirements.txt"
96: # --- 6.1. Lien symbolique vigil -> vigil_main_gui.py ---
98: sudo ln -sf /opt/vigil/gui/vigil_main_gui.py /usr/local/bin/vigil
99: sudo chmod +x /opt/vigil/gui/vigil_main_gui.py
100: echo "✅ Lien symbolique /usr/local/bin/vigil créé (pointe vers /opt/vigil/gui/vigil_main_gui.py)."
104: SUDOERS_FILE="/etc/sudoers.d/vigil"
147: Exec=python3 /opt/vigil/gui/vigil_main_gui.py
169: PLACES_FILE="$HOME/.local/share/user-places.xbel"
```

</details>

<details><summary>Privilèges et custody (31)</summary>

```text
6: sudo mkdir -p /investigation /stockage /opt/vigil/{data,scripts,logs,rapports}
7: sudo chown -R "$USER:$USER" /investigation /stockage /opt/vigil
8: sudo chmod -R 755 /investigation /stockage /opt/vigil
19: sudo apt update
23: sudo apt install -y $PKGS
28: sudo apt update
29: sudo apt install -y $FALLBACK_PKGS
46: sudo systemctl enable --now xrdp
47: sudo ufw allow 3389/tcp
57: sudo systemctl mask udisks2.service
58: sudo systemctl stop udisks2.service
59: sudo tee /etc/udisks2/udisks2.conf << 'EOF'
63: sudo systemctl daemon-reload
73: sudo systemctl disable --now usbguard 2>/dev/null || true
74: sudo apt-get -y purge usbguard 2>/dev/null || true
75: sudo rm -f /etc/udev/rules.d/*usbguard* /lib/udev/rules.d/*usbguard* /usr/lib/udev/rules.d/*usbguard* 2>/dev/null || true
76: sudo udevadm control --reload-rules 2>/dev/null || true
77: sudo udevadm trigger 2>/dev/null || true
85: sudo chmod 755 /investigation
86: sudo chown $USER:$USER /investigation
98: sudo ln -sf /opt/vigil/gui/vigil_main_gui.py /usr/local/bin/vigil
99: sudo chmod +x /opt/vigil/gui/vigil_main_gui.py
119: sudo install -m 0440 /tmp/vigil-sudoers "$SUDOERS_FILE" && rm -f /tmp/vigil-sudoers
124: sudo rm -f "$SUDOERS_FILE"
133: sudo mkdir -p /usr/share/icons/hicolor/scalable/apps
134: sudo install -m 0644 /opt/vigil/data/icons/vigil.svg /usr/share/icons/hicolor/scalable/apps/vigil.svg
135: sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
137: sudo touch /usr/share/icons/hicolor
143: sudo tee /usr/share/applications/vigil.desktop >/dev/null <<DESKTOP_EOF
154: sudo update-desktop-database 2>/dev/null || true
211: sudo freshclam
```

</details>

### `scripts/stockage/vigil_stockage_mount.sh`

`1` #!/bin/bash

<details><summary>Interface (11)</summary>

```text
103: --arg timestamp "$timestamp" \
104: --arg user "$ACTIVE_USER" \
105: --arg entity "$ACTIVE_ENTITY" \
106: --arg project "$ACTIVE_PROJECT" \
107: --arg action "$action" \
108: --arg device "$device" \
109: --arg file_path "$file_path" \
110: --arg status "$status" \
111: --arg message "$message" \
514: --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" \
515: --dir "$VIGIL_BASE/rapports" --config-dir "$VIGIL_DATA_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (16)</summary>

```text
57: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
101: if command -v jq >/dev/null 2>&1; then
125: if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
142: for cmd in lsblk mount find; do
143: if ! command -v "$cmd" >/dev/null 2>&1; then
149: for cmd in jq cryptsetup blockdev; do
150: if ! command -v "$cmd" >/dev/null 2>&1; then
512: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
647: if [ -z "$fs" ] && command -v blkid >/dev/null 2>&1; then
651: if [ -z "$lbl" ] && command -v blkid >/dev/null 2>&1; then
664: if command -v cryptsetup >/dev/null 2>&1 && cryptsetup isLuks "$dev" 2>/dev/null; then
692: if command -v blockdev >/dev/null 2>&1; then
701: if command -v ntfs-3g >/dev/null 2>&1; then
709: if command -v mount.exfat >/dev/null 2>&1; then
963: if command -v blockdev >/dev/null 2>&1; then
1006: if command -v lsblk >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (27)</summary>

```text
9: # vigil_usb_mount.sh, il detecte les disques et leurs partitions et permet de
13: # le menu "Analyse USB / Disque Dur / CD" (vigil_usb_mount.sh) qui monte en RO.
39: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
40: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
41: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
42: PROJECTS_DIR="$VIGIL_BASE/data/projects"
43: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
45: STOCKAGE_DIR="/stockage"
51: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
58: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
63: PROJECT_LOG_DIR="/tmp"
65: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
259: # Même procédure que vigil_usb_mount.sh : détection des claviers HID apparus
264: VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
265: USB_LISTS_DIR="$VIGIL_DATA_DIR/usb"
266: USB_WHITELIST_FILE="$USB_LISTS_DIR/whitelist.txt"
267: USB_BLACKLIST_FILE="$USB_LISTS_DIR/blacklist.txt"
489: USBHID_JSON="$TRIAGE_DIR/usbhid.json"
490: DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
511: PDF_SCRIPT="$VIGIL_BASE/scripts/pdf/vigil_pdf.py"
691: # montage forensique (vigil_usb_mount.sh fait blockdev --setro).
746: LSBLK_OUT=$(lsblk -P -o NAME,TYPE,PKNAME,MOUNTPOINT,TRAN,RM,SIZE,MODEL 2>/dev/null || true)
764: IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
810: IFS='|' read -r FSTYPE LABEL PARTTYPE <<< "$(_fs_label_parttype "/dev/$NAME")"
988: DEVICE_PATH="/dev/$SELECTED_DEVICE"
997: MOUNT_POINT="/stockage/$SELECTED_DEVICE"
1012: RO_CHECK=$(lsblk -no RO "$_check_dev" 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "")
```

</details>

<details><summary>Privilèges et custody (11)</summary>

```text
87: log_action() {
99: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
113: | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
226: sudo mkdir -p "$STOCKAGE_DIR" 2>/dev/null || true
230: sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null && {
685: sudo mkdir -p "$mnt" 2>/dev/null || {
693: sudo blockdev --setrw "$dev" 2>/dev/null || true
716: sudo mount $mount_opts "$dev" "$mnt" 2>&1 || true
718: sudo rmdir "$mnt" 2>/dev/null || true
721: sudo chown -R "$USER:$USER" "$mnt" 2>/dev/null || true
964: sudo blockdev --setrw "/dev/$SELECTED_DEVICE" 2>/dev/null || true
```

</details>

### `scripts/stockage/vigil_stockage_umount.sh`

`1` #!/bin/bash

<details><summary>Interface (9)</summary>

```text
78: --arg timestamp "$timestamp" \
79: --arg user "$ACTIVE_USER" \
80: --arg entity "$ACTIVE_ENTITY" \
81: --arg project "$ACTIVE_PROJECT" \
82: --arg action "$action" \
83: --arg device "$device" \
84: --arg file_path "$file_path" \
85: --arg status "$status" \
86: --arg message "$message" \
```

</details>

<details><summary>Dépendances (4)</summary>

```text
49: if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
75: if command -v jq >/dev/null 2>&1; then
100: if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
215: if [ -n "$DEVICE" ] && [ -b "$DEVICE" ] && command -v blockdev >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (10)</summary>

```text
31: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
32: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
33: ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
34: PROJECTS_DIR="$VIGIL_BASE/data/projects"
35: CONFIG_FILE="$VIGIL_BASE/data/config/system.json"
37: STOCKAGE_DIR="/stockage"
43: ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
50: ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
55: PROJECT_LOG_DIR="/tmp"
57: PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
```

</details>

<details><summary>Privilèges et custody (7)</summary>

```text
62: log_action() {
73: echo "$log_entry" | sudo tee -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true
88: [ -n "$json_entry" ] && echo "$json_entry" | sudo tee -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
134: sudo mkdir -p "$STOCKAGE_DIR" 2>/dev/null || true
152: sudo rmdir "$dir" 2>/dev/null && {
229: sudo rmdir "$MOUNT_POINT" 2>/dev/null && {
267: sudo rmdir "$dir" 2>/dev/null && {
```

</details>

### `scripts/vigil_scan_all.sh`

`1` #!/bin/bash

<details><summary>Interface (6)</summary>

```text
61: --pdf)     GEN_PDF=1 ;;
62: --no-pdf)  GEN_PDF=0 ;;
227: --kind multi \
229: --user "$ACTIVE_USER" \
230: --project "$ACTIVE_PROJECT" \
231: --dir "$RAPPORTS_DIR" 2>&1)
```

</details>

<details><summary>Dépendances (1)</summary>

```text
221: if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
```

</details>

<details><summary>Chemins, formats et appels (19)</summary>

```text
22: # via vigil_pdf.py --kind multi, assemblant toutes les sections + un sommaire.
68: VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
69: ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
76: ACTIVE_PROJECT=$(cat "$VIGIL_BASE/data/active_project" 2>/dev/null || echo "")
81: RAPPORTS_DIR="$VIGIL_BASE/rapports"
82: PDF_SCRIPT="$SCRIPT_DIR/pdf/vigil_pdf.py"
86: COLLECT_DIR=$(mktemp -d -t "vigil_multi_${STAMP}.XXXXXX" 2>/dev/null || echo "/tmp/vigil_multi_$$")
166: "$SCRIPT_DIR/analyse/vigil_census.sh" "vigil_census.json" --no-pdf --json-out "$COLLECT_DIR"
171: echo "" | bash "$SCRIPT_DIR/clamav/vigil_clamav_scan.sh" --no-pdf --log --all --yes --comment "" 2>&1
178: CLAM_LOG=$(ls -t "$RAPPORTS_DIR"/clamav_*_${CLAM_STAMP}.log 2>/dev/null | head -1)
191: "$SCRIPT_DIR/analyse/vigil_images.sh" "vigil_images.json" --no-pdf --json-out "$COLLECT_DIR"
194: "$SCRIPT_DIR/analyse/vigil_videos.sh" "vigil_videos.json" --no-pdf --json-out "$COLLECT_DIR"
197: "$SCRIPT_DIR/analyse/vigil_audio.sh" "vigil_audio.json" --no-pdf --json-out "$COLLECT_DIR"
200: "$SCRIPT_DIR/analyse/vigil_office.sh" "vigil_office.json" --no-pdf --json-out "$COLLECT_DIR"
203: "$SCRIPT_DIR/analyse/vigil_archives.sh" "vigil_archives.json" --no-pdf --json-out "$COLLECT_DIR"
206: "$SCRIPT_DIR/analyse/vigil_crypto.sh" "vigil_crypto.json" --no-pdf --json-out "$COLLECT_DIR"
209: "$SCRIPT_DIR/analyse/vigil_entropy.sh" "vigil_entropy.json" --no-pdf --json-out "$COLLECT_DIR"
212: "$SCRIPT_DIR/analyse/vigil_bigfiles.sh" "vigil_bigfiles.json" --no-pdf --json-out "$COLLECT_DIR"
236: PROJ_DIR="$VIGIL_BASE/data/projects/$ACTIVE_PROJECT"
```

</details>
