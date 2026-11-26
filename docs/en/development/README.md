---
layout: english
title: Developer reference
parent: English
nav_order: 14
has_children: true
translation_of: development/README.md
---

# Development and contribution

These documents record Vigil's architecture, contracts, implementation history and migration planning. They are **engineering references**, not claims that all planned features are complete in `main`.

## Start here

1. Read the [target architecture](architecture-v2.md) and [Linux portability](linux-portability.md).
2. Review the [compatibility matrix](compatibility-matrix.md) and [baseline tests](test-baseline.md).
3. Follow the [native test guide](native-recette.md) with synthetic fixtures.
4. Consult [Device Manager](device-manager.md), [permissions](permissions-audit.md) and [session recovery](session-recovery.md).

The large [Phase 00 audit](phase-00-audit.md) and [UI specification](cahier-des-charges-interface.md) are historical design artifacts. Later work may supersede some decisions; verify against current code.

Contribute through [GitHub](https://github.com/Gvte-Kali/vigil). Only test privileged workflows on authorized disposable devices.
