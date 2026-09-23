#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Requêtes sur l'index SQLite du recensement (census_*.sqlite).

Module commun : les scripts d'analyse sélectionnent leurs fichiers dans
l'index produit par vigil_census.sh au lieu de re-parcourir /investigation
avec find + file (gain majeur sur les gros volumes).

Utilisation en CLI :
  vigil_census_query.py --index <census.sqlite> --mismatched
  vigil_census_query.py --index <census.sqlite> --octet-stream
  vigil_census_query.py --index <census.sqlite> --mime image/
  vigil_census_query.py --index <census.sqlite> --extension jpg

Sortie TSV sur stdout : chemin<TAB>taille<TAB>mime<TAB>mismatch<TAB>hash
Les chemins sont absolus (colonne `path` de la base, racine /investigation).
"""

import argparse
import glob
import os
import sqlite3
import sys

COLUMNS = "path, size, mime_type, extension_mismatch, content_hash"


def find_latest_index(project_dir):
    """Retourne la base census_*.sqlite la plus récente du dossier projet.

    Les livrables sont horodatés (census_YYYYMMDD_HHMMSS.sqlite) ; le tri
    lexicographique du suffixe correspond au tri chronologique.
    """
    if not project_dir or not os.path.isdir(project_dir):
        return ""
    candidates = glob.glob(os.path.join(project_dir, "census_*.sqlite"))
    if not candidates:
        return ""
    return max(candidates, key=lambda p: p.rsplit("_", 1)[-1])


def query_files(db_path, mismatched=False, octet_stream=False,
                mime="", extension=""):
    """Retourne la liste des fichiers de l'index selon les filtres.

    Chaque entrée est un tuple (chemin_absolu, taille, mime, mismatch,
    hash). Les chemins sont absolus (tels que recensés sous /investigation).
    """
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Index introuvable : {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        sql = f"SELECT {COLUMNS} FROM files"
        where = []
        params = []
        if mismatched:
            where.append("extension_mismatch = 1")
        if octet_stream:
            where.append("mime_type = 'application/octet-stream'")
        if mime:
            where.append("mime_type LIKE ?")
            params.append(mime.replace("%", "").replace("_", "") + "%")
        if extension:
            where.append("lower(extension) = ?")
            params.append("." + extension.lower().lstrip("."))
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY path"
        return [tuple(r) for r in cur.execute(sql, params)]
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(
        description="Requêtes sur l'index census (SQLite).")
    ap.add_argument("--index", required=True,
                    help="Chemin de la base census_*.sqlite")
    ap.add_argument("--mismatched", action="store_true",
                    help="Fichiers avec extension trompeuse")
    ap.add_argument("--octet-stream", action="store_true",
                    help="Fichiers de type application/octet-stream")
    ap.add_argument("--mime", default="",
                    help="Préfixe de type MIME (ex : image/)")
    ap.add_argument("--extension", default="",
                    help="Extension (ex : jpg)")
    args = ap.parse_args()
    if not (args.mismatched or args.octet_stream
            or args.mime or args.extension):
        print("Erreur : précisez au moins un filtre (--mismatched, "
              "--octet-stream, --mime, --extension).", file=sys.stderr)
        sys.exit(2)
    try:
        rows = query_files(args.index, mismatched=args.mismatched,
                           octet_stream=args.octet_stream,
                           mime=args.mime, extension=args.extension)
    except (OSError, sqlite3.Error) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
    for row in rows:
        print("\t".join(str(c) for c in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
