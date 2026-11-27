---
layout: english
title: English
nav_order: 90
has_children: true
has_toc: false
translation_of: index.md
---

<div class="vigil-hero" markdown="1">

<p class="eyebrow">Vigil · User documentation</p>

# Examine. Preserve. Document.

Vigil is a Linux digital forensics workspace for inspecting media, read-only access, file analysis, evidence preservation and PDF reporting.

<span class="vigil-pill">Qt desktop interface</span><span class="vigil-pill">Evidence and SHA-256</span><span class="vigil-pill">Linux · Debian-based systems tested</span>

[Start your first investigation](getting-started.md){: .btn .btn-primary }
[Install Vigil](installation.md){: .btn }

</div>

## What would you like to do?

<div class="vigil-card-grid">
  <div class="vigil-card"><h3><a href="getting-started.html">Your first investigation</a></h3><p>Follow a practical walkthrough from opening Vigil to exporting a case.</p></div>
  <div class="vigil-card"><h3><a href="actions/README.html">Explore the tools</a></h3><p>Imaging, mounting, threat hunting, analysis and reports.</p></div>
  <div class="vigil-card"><h3><a href="configuration/README.html">Configure Vigil</a></h3><p>Organization, operators, ClamAV signatures and USB protection.</p></div>
  <div class="vigil-card"><h3><a href="faq.html">Help and troubleshooting</a></h3><p>Frequently asked questions and safe operating practices.</p></div>
</div>

## Five concepts to know

1. **Investigation source:** examined under `/investigation`, subject to software read-only protections.
2. **Case:** a context linking operator, evidence, analysis and audit records.
3. **Preserved evidence:** a controlled local copy linked to a case with a reference checksum.
4. **Working storage:** `/stockage`, used for write operations and destination media.
5. **Reports:** PDF summaries, with SQLite, TSV or log data depending on the analysis.

## Which version is covered?

<div class="vigil-note"><strong>Reference branch: <code>main</code>.</strong> The Qt GUI is the primary user workflow. The Textual TUI is usable and has undergone interactive testing on Parrot OS; full forensic validation is still ongoing. Parts of the Core still require development and testing. Published testing predominantly covers Debian-based Linux systems. Untested hardware or distributions are not certified.</div>

Review the [compatibility matrix](compatibility.md) and [security limitations](faq.md#are-investigation-sources-fully-protected) before handling real evidence.

## Further reading

- [Installation](installation.md) and [reset](reset.md)
- [Desktop interface](interface-graphique/README.md)
- [PDF reports](rapports-pdf/README.md)
- [Technical architecture](development/architecture-v2.md)
- [GitHub source code](https://github.com/Gvte-Kali/vigil)
