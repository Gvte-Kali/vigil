---
layout: english
title: Qt execution workflows
parent: Developer reference
grand_parent: English
nav_order: 21
translation_of: development/qt-execution.md
---

# Qt workspace execution workflows

Vigil's Qt workspace uses identified SQLite operator records. An operator is selected in the header; the same identity is used for case creation, evidence registration, hashes and audit events. A matching existing name should be reused rather than silently creating a new identity.

## Execution contracts

| Workflow | Integration principle |
|---|---|
| Case and evidence | Persist through the shared `vigil/storage.py` Core |
| Census query | Read SQLite in read-only mode with bounded rows and timeout |
| Analysis scripts | Pass fixed arguments, snapshot operator/case context and write one output directory per run |
| Threat hunting / ClamAV | Preserve standalone operation and distinguish partial results |
| Device and imaging operations | Validate block identity, RO/RW and controlled privileged adapter |
| Exports and reports | Publish a complete verified archive / PDF from stable inputs |

Historic profiles and directories are not automatically merged. PTY and external terminal execution must preserve exit codes and diagnostics.

## Quick actions

ClamAV scans and signature updates use controlled execution paths. Storage may require sudo and must not silently change a forensic source's RO state. The dashboard displays observed block state separately from mount status.

## Antivirus reports

The operator selects a report name before scanning. A default is based on date/time; reports are stored under distinct run directories, preventing overwrites even when names repeat. A consolidated PDF combines USB triage, ClamAV results, limitations and conclusion. Incomplete, failed or mismatched scans are not reported as successful; older reports without metadata display unknown results.

## Signature directory

FreshClam and ClamScan should use the same Vigil profile directory beside the SQLite state database. Missing, unreadable, ambiguous or unloadable signatures block scanning rather than silently falling back to system databases. Terminal and PDF record engine revision, signature revision, age and the seven-day warning. Engine version currency is distinct from signature freshness.

```bash
vigil antivirus status
vigil antivirus update
vigil antivirus scan /path/to/file
vigil antivirus scan /path/to/file --offline
```

The `--offline` option explicitly acknowledges outdated signatures in noninteractive mode.

## Engine updates and USB import

Online updates require consent before network access and package-manager changes. On Arch, do not perform unsupported partial upgrades. Offline USB imports require read-only triage, valid official signatures, staging, rollback and verified reload without modifying the source.

See [ClamAV user guide](../clamav.md), [Qt desktop](../interface-graphique/README.md) and [session recovery](session-recovery.md).
