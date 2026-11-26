---
layout: english
title: Original test baseline
parent: Developer reference
grand_parent: English
nav_order: 24
translation_of: development/test-baseline.md
---

# Phase 00 test baseline

The reference environment was **Debian 13 trixie x86_64**, Git 2.56.1, Bash 5.2.37, Python 3.12.14 and SQLite 3.53.1, at commit `a2553ba`. These numbers belong to a historical execution environment, **not a present test report**.

## Recorded checks

| Test or observation | Historical result |
|---|---|
| `bash -n` on tracked shell entrypoints | 30 files passed syntax check |
| `python3 -m py_compile` on tracked Python | 14 initial files compiled |
| SQLite FTS5 temporary probe | Passed |
| `python3 -m unittest discover -s tests -v` | 2 targeted tests passed |
| Dependency detection | `file`, `jq`, Tkinter, Pillow, ReportLab, Pydantic, PyYAML, psutil found; several imaging/AV/Qt/CI tools absent |

No privileged mount, real evidence access, sudo, ClamAV, GUI, external signature update, complete export, HID or MTP test was performed during that baseline.

## Future testing plan

- RO source and RW destination identity; block and mount permissions; alias and symlink rejection.
- File parity using synthetic Unicode names, duplicates, misleading MIME, sparse/large files, corrupt archives and encrypted samples.
- RAW/E01 output verification and AFF only when supported by installed tools.
- SQLite transactions, cancellation, crash/rollback and concurrent exports.
- GUI/TUI/CLI consistency, JSON and error codes, session recovery.
- Packaging and offline scenarios on separate distribution VMs.

Keep measured results, commands and environment versions separate from proposed acceptance criteria. See [native test guide](native-recette.md) and current `tests.txt`.
