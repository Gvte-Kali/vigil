#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit de format cible : extensions trompeuses + forte entropie + binwalk.

Complete le scan ClamAV en verifiant le CONTENU des fichiers suspects
selectionnes dans l'index census :

  1. cibles = fichiers avec extension trompeuse (extension_mismatch=1) ;
  2. cibles += fichiers application/octet-stream a forte entropie (donnees
     chiffrees/compressees camoufleans) ;
  3. pour chaque cible :
     - entropie estimee (ratio de compression zlib sur les premiers Mo) ;
     - verification des signatures forensiques locales (config/
       forensic_signatures.json) pour identifier le contenu reel ;
     - binwalk cible (si installe) borne aux premiers Mo, pour detecter
       les signatures internes / donnees concatenees apres la fin officielle.

Sortie : JSON exploite par vigil_pdf.py (--kind formataudit) et consolide
dans le rapport de recherche de menaces.

Usage :
  vigil_format_audit.py --index census.sqlite --out resultat.json \
      [--investigation /investigation] [--max-entropy 7.5]
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vigil_census_query import query_files  # noqa: E402

CHUNK = 1 << 20
ENTROPY_SAMPLE_BYTES = 4 << 20
BINWALK_SAMPLE_BYTES = 8 << 20
HIGH_ENTROPY_THRESHOLD = 7.5


def load_signatures(signatures_file):
    signatures = []
    if signatures_file and os.path.isfile(signatures_file):
        try:
            with open(signatures_file, encoding="utf-8") as fh:
                data = json.load(fh)
            for sig in data.get("signatures", []):
                try:
                    pattern = bytes.fromhex(sig.get("hex", ""))
                except ValueError:
                    continue
                if pattern:
                    signatures.append({
                        "nom": sig.get("nom", "signature"),
                        "description": sig.get("description", ""),
                        "pattern": pattern,
                    })
        except (OSError, ValueError) as exc:
            print(f"  ⚠️  Base de signatures inexploitable : {exc}",
                  file=sys.stderr)
    return signatures


def entropy_score(path):
    """Entropie Shannon sur un echantillon des premiers Mo du fichier.

    Estimation robuste pour le triage : chiffre/comprime -> proche de 8.0,
    texte/executable -> nettement plus bas.
    """
    import zlib
    try:
        with open(path, "rb") as fh:
            data = fh.read(ENTROPY_SAMPLE_BYTES)
    except OSError:
        return 0.0
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    ent = 0.0
    for c in counts:
        if c:
            p = c / total
            ent -= p * math.log2(p)
    return ent


def compression_ratio(path):
    """Ratio de compression zlib sur un echantillon (heuristique rapide).

    Un fichier chiffre ou compresse ne se recompresse presque pas (ratio
    proche de 1.0) ; un texte ou un executable se compresse bien.
    """
    import zlib
    try:
        with open(path, "rb") as fh:
            data = fh.read(ENTROPY_SAMPLE_BYTES)
    except OSError:
        return 1.0
    if not data:
        return 1.0
    compressed = zlib.compress(data)
    return len(compressed) / len(data)


def match_signatures(path, signatures):
    """Retourne les signatures locales trouvees au debut du fichier."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(512)
    except OSError:
        return []
    found = []
    for sig in signatures:
        if sig["pattern"] in head:
            found.append(sig["nom"])
    return found


def binwalk_scan(path, sample_bytes=BINWALK_SAMPLE_BYTES):
    """Scan binwalk cible, borne aux premiers Mo du fichier.

    Retourne (ok, findings) : findings est une liste de signatures internes
    (description + offset). binwalk absent = (False, []) sans erreur : le
    scan continue avec les signatures locales uniquement.
    """
    binwalk = shutil.which("binwalk")
    if not binwalk:
        return False, []
    try:
        with open(path, "rb") as fh:
            data = fh.read(sample_bytes)
    except OSError:
        return False, []
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [binwalk, tmp_path],
            capture_output=True, text=True, timeout=60)
        findings = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("DECIMAL") or \
                        line.startswith("-" * 10):
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2 and parts[0].isdigit():
                    offset = int(parts[0])
                    desc = parts[1].strip()
                    if offset > 0:
                        findings.append({"offset": offset,
                                         "description": desc})
        return True, findings
    except (subprocess.TimeoutExpired, OSError):
        return False, []
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def audit_file(path, size, mime, mismatch, signatures, use_binwalk=True):
    """Audit complet d'une cible : entropie + signatures + binwalk."""
    result = {
        "path": path,
        "size": size,
        "mime_type": mime,
        "extension_mismatch": mismatch,
        "entropy": round(entropy_score(path), 2),
        "compression_ratio": round(compression_ratio(path), 3),
        "signatures": match_signatures(path, signatures),
        "binwalk": [],
        "binwalk_available": False,
        "high_entropy": False,
    }
    ent = result["entropy"]
    ratio = result["compression_ratio"]
    if ent >= HIGH_ENTROPY_THRESHOLD and ratio >= 0.95:
        result["high_entropy"] = True
    if use_binwalk:
        ok, findings = binwalk_scan(path)
        result["binwalk_available"] = ok
        result["binwalk"] = findings
    return result


def main():
    ap = argparse.ArgumentParser(
        description="Audit de format cible (extensions trompeuses + "
                    "entropie + binwalk) sur l'index census.")
    ap.add_argument("--index", required=True,
                    help="Base census_*.sqlite du projet actif")
    ap.add_argument("--out", required=True,
                    help="Fichier JSON de resultat")
    ap.add_argument("--investigation", default="/investigation",
                    help="Racine des peripheriques montes")
    ap.add_argument("--signatures", default="",
                    help="Base de signatures JSON (defaut : config/ du depot)")
    ap.add_argument("--max-files", type=int, default=500,
                    help="Nombre maximum de fichiers audites en detail")
    ap.add_argument("--no-binwalk", action="store_true",
                    help="Desactiver le scan binwalk cible")
    args = ap.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    signatures_file = args.signatures or os.path.join(
        script_dir, "..", "..", "config", "forensic_signatures.json")
    signatures = load_signatures(signatures_file)

    # --- Selection des cibles dans l'index ---
    try:
        mismatched = query_files(args.index, mismatched=True)
        octet_streams = query_files(args.index, octet_stream=True)
    except (OSError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)

    seen = {}
    for path, size, mime, mismatch, _h in mismatched:
        seen[path] = (path, size, mime, mismatch)
    for path, size, mime, mismatch, _h in octet_streams:
        if path not in seen:
            seen[path] = (path, size, mime, mismatch)
    targets = sorted(seen.values())

    print(f"  Cibles : {len(seen)} fichier(s) "
          f"({len(mismatched)} extension(s) trompeuse(s), "
          f"{len(octet_streams)} octet-stream)")

    # --- Audit de chaque cible ---
    audited = []
    high_entropy_count = 0
    binwalk_hits = 0
    binwalk_available = False
    for path, size, mime, mismatch in targets[:args.max_files]:
        if not os.path.isfile(path):
            continue
        res = audit_file(path, size, mime, mismatch, signatures,
                         use_binwalk=not args.no_binwalk)
        audited.append(res)
        if res["high_entropy"]:
            high_entropy_count += 1
        if res["binwalk"]:
            binwalk_hits += 1
        if res["binwalk_available"]:
            binwalk_available = True
    skipped = max(0, len(targets) - args.max_files)

    result = {
        "date": __import__("datetime").datetime.now().strftime(
            "%d/%m/%Y à %H:%M:%S"),
        "total_targets": len(targets),
        "audited": len(audited),
        "skipped": skipped,
        "mismatch_count": len(mismatched),
        "high_entropy_count": high_entropy_count,
        "binwalk_hits": binwalk_hits,
        "binwalk_available": binwalk_available,
        "signatures_active": len(signatures),
        "files": audited,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"  Audit terminé : {len(audited)} fichier(s) audité(s), "
          f"{high_entropy_count} à forte entropie, "
          f"{binwalk_hits} avec signatures internes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
