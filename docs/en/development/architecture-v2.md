---
layout: english
title: Target architecture
parent: Developer reference
grand_parent: English
nav_order: 10
translation_of: development/architecture-v2.md
---

# Vigil 2.0 target architecture

This document captures the design derived from the specifications and [Phase 00 audit](phase-00-audit.md). The initial audit phase was a design milestone, not proof of implementation.

## Core contracts

| Component | Proposed contract and invariant |
|---|---|
| Module registry | Discover manifests from known sources, report duplicates and provenance, filter and retrieve by ID/version |
| Manifest | Versioned strict Pydantic/YAML model, bilingual labels, module ID, API version, dependencies, capabilities, inputs, outputs and resume strategy |
| Capabilities | Probe dependency, permissions, format and isolation; distinguish available, missing, degraded and forbidden |
| Case and evidence | SQLite metadata, immutable provenance, copies with integrity checks and append-only audit events |
| Execution | Validated immutable run context, events, exit status, resource tracking and recoverable errors |
| Reports | Structured results, validated hashes and PDF generation without writing to source evidence |

The GUI, CLI and Textual TUI should call shared business services. Module discovery does not grant arbitrary code execution rights. Privileged operations remain constrained to controlled capabilities.

## Lifecycle without a permanent daemon

Start a supervised session, record relevant state, run tracked operations and verify cleanup independently of the desktop window. Do not silently restore or overwrite external changes. An interrupted or unresolved operation must remain visible for recovery at next launch.

## Migration and coexistence

Keep existing scripts callable while adapters replace direct GUI-to-shell coupling. Preserve historical project directories, chain-of-custody records, manifests and source hashes. Migrate by verified increments, with a tested rollback and stable versioned schema.

## Module catalog

The community module catalog should live in a separate GitHub repository. Import must validate manifests, dependency constraints and permissions before execution. An unavailable catalog must not stop offline Core functionality.

## Session exit and system state

Record mount identity, block RO status, session ownership and the actual effects of Vigil's operations. Verify the observed final state; do not claim a clean restoration without checking.

## Portable cases

Export a versioned archive with metadata, available evidence copies, checksums, reports and audit history. Partial exports must explicitly list missing material. Import must resist archive traversal and collision, restore only permitted files and keep historical provenance distinct from current local paths.

See [archive format](case-archive.md), [Device Manager](device-manager.md) and [session recovery](session-recovery.md) for implementation details.
