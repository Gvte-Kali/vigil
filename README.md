# Vigil

[Français](#français) · [English](#english) · [Documentation](https://gvte-kali.github.io/vigil/)

## Français

**Vigil** est un environnement Linux d'investigation numérique : triage USB, montage en lecture seule, analyse de fichiers, conservation de preuves, empreintes SHA-256 et rapports PDF.

**État du projet :** la documentation utilisateur se base sur la branche `main` et la GUI Qt. La TUI Textual est expérimentale et non fonctionnelle à ce stade ; elle ne doit pas être utilisée pour des investigations. Plusieurs fonctionnalités du Core restent en développement ou en recette. Les essais de référence ont surtout été réalisés sur Debian et ses dérivés.

**Pour commencer :** [documentation](https://gvte-kali.github.io/vigil/) · [installation](https://gvte-kali.github.io/vigil/installation/README.html) · [première investigation](https://gvte-kali.github.io/vigil/getting-started.html) · [FAQ](https://gvte-kali.github.io/vigil/faq.html).

### Essayer la GUI dans un environnement utilisateur

```bash
git clone --branch main https://github.com/Gvte-Kali/vigil.git
cd vigil
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil doctor
.venv/bin/vigil-gui
```

Cette installation ne prépare pas les protections privilégiées ni les montages système. Pour un poste forensique dédié, consulter la [procédure Debian/Parrot](https://gvte-kali.github.io/vigil/installation/README.html).

Les protections RO sont logicielles et ne remplacent pas systématiquement un bloqueur d'écriture matériel. Un SHA-256 vérifie l'intégrité par comparaison ; une analyse antivirus négative ne garantit pas l'absence de menace.

## English

**Vigil** is a Linux digital forensics workspace for USB triage, read-only media mounting, file analysis, preserved evidence, SHA-256 integrity checking and PDF reports.

**Project status:** user documentation targets the `main` branch and Qt GUI. The Textual TUI is experimental and not functional at this stage; do not use it for investigations. Parts of the Core are still under development or validation. Reference testing has mainly covered Debian-based Linux systems.

**Start here:** [documentation](https://gvte-kali.github.io/vigil/en/) · [installation](https://gvte-kali.github.io/vigil/en/installation.html) · [first investigation](https://gvte-kali.github.io/vigil/en/getting-started.html) · [FAQ](https://gvte-kali.github.io/vigil/en/faq.html).

### Try Qt in a user-owned environment

```bash
git clone --branch main https://github.com/Gvte-Kali/vigil.git
cd vigil
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil doctor
.venv/bin/vigil-gui
```

This does not configure privileged system protection or mounts. For a dedicated workstation see the [Debian/Parrot installation guide](https://gvte-kali.github.io/vigil/en/installation.html).

Read-only software controls are not always a substitute for a physical write blocker. SHA-256 demonstrates comparative integrity rather than authenticity; a clean antivirus result does not guarantee harmless content.

## Development

- Repository: [Gvte-Kali/vigil](https://github.com/Gvte-Kali/vigil)
- Development branch: `vigil-2.0`
- [Architecture and contributor reference (FR)](https://gvte-kali.github.io/vigil/development/README.html) / [English](https://gvte-kali.github.io/vigil/en/development/README.html)
- License: [GNU GPL v3](LICENSE)
