---
layout: english
title: Getting started
parent: English
nav_order: 0
translation_of: getting-started.md
---

# Your first investigation with Vigil

This walkthrough uses the **Qt GUI from the `main` branch**. Work only with an authorized, disposable test device. Available operations depend on installed tools.

## Before you begin

- Vigil installed on Debian or a Debian-based Linux system; a test VM is recommended.
- An authorized operator, disposable USB media and a separate output location.
- Required dependencies checked and ClamAV signatures updated if you intend to scan.

## Walkthrough

1. **Start Vigil.** Run `vigil gui` or `vigil-gui`; check the header and status bar.
2. **Set up the organization.** Under **System → Configuration → Entity**, enter the organization details and an optional logo.
3. **Select an operator.** Choose the identity recorded for audited operations. Operator identities do not enforce access permissions.
4. **Create a case.** Open **Investigation → Current case**, create a case and explicitly activate it.
5. **Prepare the media.** Confirm the device identity, keep destination media separate and review USB protection. Do not use a production disk.
6. **Mount read-only.** Follow [USB triage and mounting](actions/montage-lecture-seule.md) into `/investigation` and check its result.
7. **Browse and preserve.** Inspect metadata, register evidence and verify the local copy and its SHA-256.
8. **Analyze.** Run a [census](actions/recensement.md) or an appropriate module. Review warnings and skipped files.
9. **Review reports.** Read the [PDF reports](rapports-pdf/README.md) and audit history. No detection does not prove a file is safe.
10. **Close safely.** Unmount in Vigil, review the restoration summary, [export the case](actions/export.md) and verify the archive checksum.

## Expected result

A case with an identified operator, verified evidence, documented results and a verifiable export. Resolve any failed read-only check, unmount or verification before disconnecting the media.

## Troubleshooting

See the [FAQ](faq.md), [installation guide](installation.md) and [USB device configuration](configuration/peripheriques-usb.md). Do not bypass read-only controls just to complete a demo.
