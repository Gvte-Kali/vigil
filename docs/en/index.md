---
layout: english
title: English
nav_order: 90
has_children: true
has_toc: false
translation_of: index.md
---

# Vigil documentation

Vigil is a Linux application for examining digital media. It combines read-only
mounting, file analysis, malware scanning and PDF reports.

- [Install and launch Vigil](installation.md)
- [Reset an existing installation](reset.md)
- [Analyze a device](analysis.md)
- [Update ClamAV signatures](clamav.md)

Use the language button in the header to open the corresponding French page.
Some reference pages are currently available in French. On those pages,
**EN (Home)** returns here.

## First steps

1. Open the Qt interface with `vigil gui` or the Textual workspace with `vigil tui`.
2. Configure the organization and select an operator.
3. Create and select a case. Mount the source read-only from Vigil.
4. Run the relevant analyses, review the reports and unmount the source.
5. Export the case and verify its SHA-256 checksum.

Vigil uses software write protection. Its scope depends on the device and
protocol. A disk's block-level read-only flag does not apply to an MTP phone.
