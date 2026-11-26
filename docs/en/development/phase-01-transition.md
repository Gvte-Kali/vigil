---
layout: english
title: Privilege transition
parent: Developer reference
grand_parent: English
nav_order: 20
translation_of: development/phase-01-transition.md
---

# Vigil privilege transition

On an existing workstation, an administrator must inspect `/etc/sudoers.d/vigil` and any copies of earlier Vigil sudoers rules. Save the original outside sudoers include paths. Remove only rules proven to belong to Vigil and validate all remaining rules with `visudo -c`.

## Prepare storage without touching evidence

Close Vigil and verify mount zones are unused before changing `/stockage`. Do not chmod a source or silently remount investigation evidence writable. Keep the distinction between `/investigation` RO and `/stockage` RW explicit.

## Experimental ext4 mounting broker

Early development included a narrowly scoped ext4 mount helper. It must not be interpreted as a complete universal device manager. Check helper ownership, root-owned directory ancestry, allowed operation names, expected device identity and mount-point limits before any privileged invocation.

## Qt development flow

The Qt GUI can use a controlled execution adapter, preserve the operator context and report the exact subprocess exit result. A cancelled operation must not produce an implied success event.

## Shutdown reporting

The session supervisor captures relevant initial state and tracks its own mutations. An independent caretaker can finish recovery work after Qt exits or crashes, without killing ongoing acquisition tasks. Restoration is limited to resources Vigil changed and is verified against the observed final system state.

## Validation

Use isolated VMs and disposable test drives to exercise stale sudoers rules, absent helpers, mounting conflicts, unexpected GUI closure and safe recovery. See [permissions audit](permissions-audit.md) and [session recovery](session-recovery.md).
