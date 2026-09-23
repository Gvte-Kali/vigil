---
layout: default
parent: "🖥️ Interface graphique"
nav_order: 101
---

# 🧭 Navigation parent/enfant

> Toutes les pages Vigil partagent une **fenêtre racine unique invisible**.
> La navigation est gérée par une pile (`NAV`) qui reconstruit le titre.

---

## 📖 En résumé

Ouvrir une page fille remplace le contenu du corps de la fenêtre, pousse son
label sur la pile `NAV`, ajoute un bouton **Retour**, et reconstruit le titre
sous la forme `Vigil > Configuration > Utilisateurs`. Fermer la page fille
dépile et restaure le parent. L'application se ferme proprement via `quit_app`.

---

## 🧱 Composants (`gui/vigil_gui_base.py`)

- `VigilWindow` : conteneur avec en-tête (logo + titre + bouton retour) et corps.
- `NAV` : pile globale des labels, utilisée pour reconstruire le titre.
- `header_title()` : en-tête centré (logo + titre + sous-titre).
- `Section` : cadre de catégorie repliable avec icône.
- `CategoryButton` : bouton large pleine largeur.
- `ActionButton` : bouton compact de la barre d'actions.
- `quit_app()` : fermeture propre (détruit la racine, sort de `mainloop`).

## 🔄 Cycle d'ouverture d'une page

1. La page parente appelle `window.open_child("fille.py", nav_label=...)`.
2. `VigilWindow` détruit le contenu courant, instancie la fenêtre fille
   (qui reconstruit son propre `VigilWindow`), pousse le label sur `NAV`.
3. La fille affiche un bouton **Retour** qui dépile et rouvre le parent.
