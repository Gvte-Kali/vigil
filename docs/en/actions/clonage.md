---
layout: english
title: Disk cloning
parent: Actions & analyses
grand_parent: English
nav_order: 15
translation_of: actions/clonage.md
---

# Disk cloning

## Vigil 2.0 workflow

Under **Quick actions → Acquisition**, choose **Clone a disk** or **Create a RAW image**. These operations open the configured terminal and request administrative authorization.

After selecting the source, Vigil invites you to attach a USB destination and refreshes the inventory. Both disks must be unmounted. The destination is explicitly authorized for writing, then its previous block mode is restored. The confirmation shows the destination path.

The clone overwrites the destination from its beginning for the **exact length of the source**. Its SHA-256 verification rereads that same range.

A RAW image can instead be written to an existing local directory or a compatible USB filesystem. The latter is mounted in a private namespace; the image is reread and a `.raw.sha256` file is written. Existing filenames are rejected.

## Vigil 1.0 workflow

Legacy script: `scripts/imager/vigil_disk_clone.sh`, via **Clone a hard disk**.

**The destination is overwritten.** Verify device paths, models, capacities and serial numbers.

1. Select the read-only source.
2. Select a destination at least as large as the source.
3. Confirm and wait for completion.
4. Review the summary and available checks.
5. Where explicitly required, choose whether to repair or extend destination partitions.

The legacy process uses `dc3dd` or `dd` as a fallback. Optional repair with `sgdisk`, `growpart` or `resize2fs` modifies the destination.

For a file-based acquisition, see [Forensic imaging](copie-forensique.md).
