---
layout: default
parent: "Actions"
title: "Recherche de menaces"
nav_order: 21
---

# 🛡️ Recherche de menaces

> Bouton **« Recherche de menaces »** de la section Actions — script
> `scripts/clamav/vigil_malware_hunt.sh`, lancé dans Konsole après une
> confirmation récapitulant les 5 étapes.

---

## 📖 En résumé

En une seule action, la chasse enchaîne dans un terminal :

1. **Montage** du périphérique en lecture seule (interactif, triage USB inclus) ;
2. **Recensement** autonome (`vigil_census.sh --no-project --no-pdf` : index
   SQLite + audit extension/MIME, sans PDF propre) ;
3. **Audit de format ciblé** (`vigil_format_audit.py`) : binwalk/signatures
   sur les fichiers dont l'extension ment et les octet-stream à forte entropie ;
4. **Scan antivirus ClamAV** sur tous les dossiers montés (`--all --yes`) ;
5. **Démontage** puis **un seul PDF consolidé**
   (`vigil_pdf.py --kind multi`).

Le triage USB du montage est **consolidé dans ce rapport unique** : aucun
`rapport_usbhid_*.pdf` autonome n'est généré. Si le montage s'arrête au
triage (seul périphérique = clavier suspect bloqué), la chasse s'arrête
proprement et le rapport consolidé est quand même généré avec cette seule
section.

---

## 👤 Utilisateur et opérateur

La chasse exige un **opérateur** (journal de custody) mais **pas de
projet**. Si un utilisateur est passé en argument (`--user NOM`) ou qu'un
utilisateur actif existe (`data/active_user`), il est repris tel quel.
Sinon, les utilisateurs configurés (`data/users/`) sont listés et
l'opérateur en choisit un par numéro. L'opérateur est propagé à toute la
chaîne (`--user` pour le recensement et le scan, `VIGIL_ACTIVE_USER` pour
le montage/démontage).

---

## 🔒 Mode autonome (sans projet)

La chasse n'est **pas liée à un projet** : aucun projet n'est requis ni
modifié, et le rapport consolidé n'est pas copié dans un dossier de projet.
La page de garde du rapport note « Recherche de menaces » comme projet.

Tout le temporaire vit dans `$VIGIL_BASE/hunt/` (index SQLite du
recensement, JSON de collecte, journaux clamscan, triage USB). Ce dossier
est **purgé au début de chaque chasse**.

---

## 📄 Rapport consolidé

- **Ordre des sections** : triage USB → ClamAV → audit de format →
  recensement → chaîne de custody.
- **Nom** : sans nom, `rapport_menaces_<date>_<heure>.pdf` ; avec un nom
  saisi, `<nom>_rapport_menaces_<date>_<heure>.pdf` (nettoyé
  automatiquement).
- **Chaîne de custody** : `hunt/chain_of_custody.json` (JSONL) alimenté par
  toute la chaîne, consolidé en tableau chronologique dans le PDF.
- **Export des preuves** : en fin de chasse, archive
  `export_menaces_*.tar.gz` (tout `hunt/` + le PDF) + checksum `.sha256`,
  proposée avant la purge ; si l'export échoue, la purge est annulée.

Le détail des options ClamAV (archives, taille, archives chiffrées) est
documenté dans [Antivirus ClamAV](antivirus.md).
