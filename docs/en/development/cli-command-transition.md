---
layout: english
title: Command naming migration
parent: Developer reference
grand_parent: English
nav_order: 13
translation_of: development/cli-command-transition.md
---

# Vigil command-name migration

## Background

The `vigil2` spelling previously appeared in Python entrypoints, desktop launchers, shell scripts, documentation, tests and a Qt settings key. A historic `vigil` launcher was also used for the GUI, creating PATH conflicts.

## Supported command family

| Command | Meaning |
|---|---|
| `vigil` | Textual workspace by default in an interactive terminal |
| `vigil tui` / `vigil-tui` | Explicit Textual interface |
| `vigil gui` / `vigil-gui` | Qt desktop interface |
| `vigil --help` / `--version` | CLI information |
| `vigil cases ...`, `vigil devices ...` | Scriptable subcommands |

Only project-owned launchers may be replaced. Use a preflight check for `/usr/local/bin`, `/usr/bin` and user bin directories. Never remove unrelated binaries named `vigil`.

## Installation and migration

The site installer publishes managed wrappers based on the project's venv. Updaters must be idempotent and preserve cases and settings. The old Qt `Vigil2` preference key can be read for one-time migration without advertising an obsolete public command.

## Verification

Run the CLI help and version checks, exercise both GUI/TUI entrypoints, test owned/unowned PATH collisions and validate JSON output has no banner or ANSI escape sequences. See [installation](../installation.md) and the [native test procedure](native-recette.md).
