---
layout: english
title: Compatibility and releases
parent: English
nav_order: 5
translation_of: compatibility.md
---

# Compatibility and project status

This page summarizes **documented testing**, not universal certification.

| Topic | Status |
|---|---|
| Public reference branch | `main` |
| Qt GUI | Primary documented interface |
| Textual TUI | **Experimental and currently non-functional; not for investigations** |
| Debian, Parrot and derivatives | Main testing family |
| Arch / Omarchy, Fedora, openSUSE | Portability targets; feature-by-feature testing still needed |
| Headless SSH | Technical CLI depending on the command; TUI currently non-functional |
| Physical acquisition | Requires device-specific protection and testing |

## Developer reference

The `vigil-2.0` branch contains ongoing work and is not the same as a fully verified release. See the [native testing procedure](development/native-recette.md) and [technical compatibility matrix](development/compatibility-matrix.md).

## Report an incompatibility

Include the branch and commit, distribution, kernel, desktop session, expected and actual behavior, and redacted logs. [Open a GitHub issue](https://github.com/Gvte-Kali/vigil/issues).
