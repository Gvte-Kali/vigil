---
layout: english
title: Case export
parent: Actions & analyses
grand_parent: English
nav_order: 20
translation_of: actions/export.md
---

# Export and restore a case

## Vigil 2.0

From **Current case → Export case**, select **Create complete archive** and a destination. The export directory contains `affaire.tar.gz` and `affaire.tar.gz.sha256`. Equivalent CLI:

```bash
vigil cases export ID DESTINATION --operator NAME
```

To import, open **Case Manager → Import → Import a Vigil 2.0 archive**, select the TAR.GZ file and confirm after validation. CLI equivalents:

```bash
vigil cases verify-archive PATH
vigil cases import-archive PATH --operator NAME
```

A Vigil 1.0 folder containing `info.json` uses the separate legacy import. A **partial archive** retains metadata for evidence whose local copies are missing and reports those items as unavailable. Present copies are verified and restored with Linux `0400` permissions. See the [archive contract](../development/case-archive.md) for v3/v2 compatibility, conflicts and recovery.

## Vigil 1.0

Under **Manage projects**, select a project and **Export**. Legacy script: `scripts/export/vigil_export_project.sh`; `--dest DIR` overrides the default `/opt/vigil/rapports/`.

| File | Purpose |
|---|---|
| `<project>_<time>.tar.gz` | Project archive |
| `<project>_<time>.sha256` | File checksums, excluding `.sha256` |
| `<project>_<time>.hash_archive.sha256` | Archive checksum |

Export events are recorded in the project log.

## Verify on receipt

Run `sha256sum -c NAME.hash_archive.sha256` in the archive directory, then check the extracted file manifest from the extraction root. A checksum demonstrates integrity by comparison, not the sender's identity.

See [Projects](../configuration/projets.md).
