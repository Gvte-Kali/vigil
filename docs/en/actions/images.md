---
layout: english
title: Images and EXIF
parent: Actions & analyses
grand_parent: English
nav_order: 21
translation_of: actions/images.md
---

# Images and EXIF metadata

Find image files and extract available date, camera and GPS metadata using `exiftool`.

Select an operator and case, mount the source, then launch the image module in the legacy analysis page.

Script: `scripts/analyse/vigil_images.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Enable the PDF report (default) or disable it |
| `--copy-to DIR` | Copy matching images to working storage |
| `--faces` | Detect candidate face regions afterward |
| `--copy-faces-to DIR` | Copy images containing detected candidate faces |

Reports contain statistics, image paths and SHA-256 values; they are normally written to `/opt/vigil/rapports/`. EXIF metadata may be missing or manipulated. [Face detection](visages.md) does not identify a person.

See [PDF reports](../rapports-pdf/README.md).
