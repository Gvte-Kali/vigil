---
layout: english
title: Analyze a device
parent: English
nav_order: 3
translation_of: actions/analyse.md
---

# Analyze a device

The primary Qt workflow starts under **Investigation → Current case**, then uses its file browser, evidence and analysis panels.

## Before running

- Choose an **operator** and create or activate a **case**.
- Identify the source, verify RO protections, and keep a separate destination for results.
- Check that the selected module's dependencies are installed.

## Qt workflow

1. Open **Current case** and explicitly activate the selected case.
2. Use the mount action and follow [USB triage and RO mounting](actions/montage-lecture-seule.md) under `/investigation`.
3. Browse folders and inspect metadata and previews.
4. Register selected files as evidence with SHA-256.
5. Open **Analyses** and run the [file census](actions/recensement.md) or an available module.
6. Review the outcome and [PDF reports](rapports-pdf/README.md).
7. [Unmount](actions/demontage.md) the source and [export](actions/export.md) the case.

## Choose a module

| Need | Module |
|---|---|
| File inventory, duplicates, misleading extensions | [Census](actions/recensement.md) |
| Image metadata | [Images](actions/images.md), [Faces](actions/visages.md) |
| Media files | [Video](actions/videos.md), [Audio](actions/audio.md) |
| Documents and containers | [Office files](actions/bureautique.md), [Archives](actions/archives.md) |
| Protection and binary data | [Encrypted files](actions/crypto.md), [Entropy](actions/entropie.md) |
| Large files | [Large files](actions/volumineux.md) |
| Preset sequence | [Orchestrator](actions/orchestrateur.md) |

## Historical scripts

Several module pages describe the Vigil 1.0 screen **Analyze a device**, with a user/project context and files under `data/projects/<project>/`. Qt adapters use newer Core services too. Do not assume every historical path applies to a new case.

Standalone ClamAV scanning and [threat hunting](actions/menaces.md) need not have an active case.

## Audit

Check operator attribution and recorded case events. SHA-256 compares bytes; it does not authenticate the producer.
