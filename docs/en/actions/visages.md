---
layout: english
title: Face detection
parent: Actions & analyses
grand_parent: English
nav_order: 28
translation_of: actions/visages.md
---

# Face detection

Identify image regions that **may contain faces** without identifying the people shown.

Enable `--faces` in the [image-analysis workflow](images.md). Use `--copy-faces-to DIR` to preserve selected images in working storage.

`scripts/analyse/vigil_faces_detection.sh` receives the working directory and an image TSV list. It prefers `facedetect` and falls back to OpenCV (`cv2`). Results are written to `faces_result.json`.

## Limitations

- Tiny images (8192 square pixels or less) are skipped.
- False positives and missed detections are possible.
- If neither backend is available, face detection is disabled while ordinary image analysis continues.
