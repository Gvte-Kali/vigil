---
layout: english
title: Cases and legacy projects
parent: Settings and cases
grand_parent: English
nav_order: 12
translation_of: configuration/projets.md
---

# Cases and projects

A **Vigil 2.0 case** groups an investigation, preserved evidence, checksums, analysis results, PDF reports and audit records.

## Create a case in Qt

1. Open **Investigation → Current case**, then the case manager.
2. Select **Create case** and enter its name and any offered metadata.
3. Select the new case and explicitly activate it.
4. Browse evidence and reports under the case tabs.

Listing, creating, importing and deleting cases are separate from operations on the active case.

## Import and export

For a Vigil 2.0 archive, select **Import → Import a Vigil 2.0 archive** and choose the TAR.GZ file. Validation previews coverage and available evidence copies. Confirm restoration, then activate the case.

A historical folder with `info.json` uses **Import a legacy Vigil 1.0 project**. See [Export](../actions/export.md).

## Vigil 1.0 projects

The legacy **Manage projects** screen stores results and `chain_of_custody.log` under `data/projects/<project>/`. These projects are shared by operators. Rerunning census may replace earlier outputs: export before rerunning if they must be retained.

[Threat hunting](../actions/menaces.md) has a standalone workflow with no active case.
