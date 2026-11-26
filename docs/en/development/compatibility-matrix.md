---
layout: english
title: Feature compatibility matrix
parent: Developer reference
grand_parent: English
nav_order: 14
translation_of: development/compatibility-matrix.md
---

# Vigil 2.0 feature compatibility matrix

**Scope:** an original static audit referenced commit `a2553ba`. Its status labels described what had been identified then, not the current release state.

## Historical parity assessment

The original 27 planned capabilities cover:

1. Module registry and versioned manifests.
2. CLI coverage, module management and system capability checks.
3. Cases, evidence explorer, interactive timeline and global search.
4. Tags, annotations, favorites and artifact correlation.
5. Job queue, retry/recovery and resource tracking.
6. Existing disk-image analysis, RO protection audit and Windows artifact extraction.
7. Guided carving and evidence integrity verification.
8. Custom reports, execution history, integrity manifest and investigation report.
9. Unified workspace, themes/density and advanced tables.

These capabilities ranged from partially implemented to absent at the original audit. **Do not treat the list as a release feature list.** Compare against source, tests and the current [Textual parity report](tui-parity.md).

## Compatibility testing

| Area | Minimum verification |
|---|---|
| GUI and TUI | Same Core validation, case selection, operation result and error states |
| CLI | Scriptable JSON, stable errors and meaningful exit codes |
| Source protection | Valid block identity, read-only mounts and no evidence writes |
| Acquisition | Correct source/destination, hash scope, failures and cleanup |
| Archives | Round-trip restore, partial coverage and safe extraction |
| Distributions | Separate native tests on Debian-family, Fedora, Arch and openSUSE |
| Session safety | Normal exit, crashes, recovery and conflicting resource ownership |

For actual command lines and test fixtures use [test baseline](test-baseline.md) and [native test guide](native-recette.md).
