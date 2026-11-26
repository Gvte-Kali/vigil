---
layout: english
title: Portable case archives
parent: Developer reference
grand_parent: English
nav_order: 12
translation_of: development/case-archive.md
---

# Vigil case archive portability

## Previous limitation

Earlier archive exports captured parts of the case while the import GUI/CLI accepted only legacy folders containing `info.json`. This was insufficient for a full new-database restoration.

## v3 coverage

| Area | Export | Restore / verification |
|---|---|---|
| Case name, reference, description, IDs and timestamps | `affaire.json` | Validated schema and SQLite records |
| Operators and audit provenance | Recorded identities and events | Preserve historical authorship; map local identities separately |
| Evidence metadata and SHA-256 | Manifest and available local copies | Restore local copy permissions and verify hashes |
| Reports and analysis results | Included when available | Restore without rerunning tools |
| Missing original content | Coverage marked partial | Preserve metadata and warn that content is unavailable |

The archive includes `affaire.tar.gz` plus an external SHA-256 sidecar. Integrity checks prove equality of bytes, not identity or authenticity of the exporter.

## Safe publication

Capture a consistent snapshot; stage results before publication; validate archive members, quotas and hashes. Never follow archive paths outside the destination, special files, symlinks or conflicting duplicate entries.

## Restore

A shared import service supports GUI, CLI and TUI. Check the archive and present coverage, conflicts and space requirements before writing. Restore with a migration-aware SQLite transaction and a recoverable filesystem staging area. Do not overwrite another case or original source.

## Evidence copies

Evidence copies preserve a source-relative path where known, retain stable evidence IDs in SQLite and should not rely on volatile `/dev/sdX` names. Existing `preuves/<id>/contenu` entries remain readable through migration and historical archive compatibility. Stored evidence is read-only to ordinary access.

See [case export](../actions/export.md) and [compatibility matrix](compatibility-matrix.md).
