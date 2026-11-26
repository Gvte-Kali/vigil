---
layout: english
title: System and operators
parent: Settings and cases
grand_parent: English
nav_order: 11
translation_of: configuration/systeme.md
---

# System and operators

In the GUI and TUI, open **System → Configuration**. The main navigation groups **Dashboard** under **Workspace**, **Current case** and **Quick actions** under **Investigation**, and **Configuration** under **System**.

Configuration has three horizontal tabs:

- **Entity:** organization details and logo.
- **System:** desktop session, protection status and searchable tool diagnostics. **Automatic** selects the first compatible terminal. This terminal preference is shared by the GUI and TUI for external operations.
- **Module catalog:** module search, filters, table, inspector and draft creation.

The dashboard retains metrics, case activity, device inventory and mount status.

## Set up the entity

1. Enter organization name, institution and contact details.
2. Select an optional logo and check its preview.
3. Save the settings.

The information is used on PDF report covers. The logo is copied to `data/config/logo/`.

## Manage operators

Open **Users**, then **Add**, **Edit** or **Delete**. Names must be unique and cannot be changed after creation. Each profile has the fixed role `analyst`: it identifies the operator but **does not enforce access permissions**.

| Data | Location |
|---|---|
| Profile | `data/users/<name>/profile.json` |
| Active user | `data/active_user` |

Select the operator before running an analysis. See [Cases](projets.md) and [PDF reports](../rapports-pdf/README.md).
