# SPDX-License-Identifier: GPL-3.0-or-later
"""Point d'entrée `deskgate-bcf write` : valide le JSON puis écrit le BCF 2.1.

Codes de sortie : 0 succès, 2 entrée invalide, 3 écriture impossible. Rien sur stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

import jsonschema

SUPPORTED = {1: "bcf-write-v1.json"}


def _err(*lines: str) -> None:
    # stderr toujours en UTF-8 : les appelants le décodent ainsi, quelle que soit la page de code
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print("\n".join(lines), file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deskgate-bcf", description="Écriture BCF 2.1 pour Deskgate.")
    sub = p.add_subparsers(dest="command", required=True)
    w = sub.add_parser("write", help="écrit un BCF depuis un JSON bcf-write-v1")
    w.add_argument("--input", required=True, help="JSON d'entrée")
    w.add_argument("--output", required=True, help="fichier .bcf à écrire")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    src = Path(args.input)
    try:
        text = src.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        _err(f"Entrée illisible : {src.name} ({type(e).__name__}).")
        return 2
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        _err(f"JSON invalide (ligne {e.lineno}, colonne {e.colno}).")
        return 2
    version = doc.get("schema_version") if isinstance(doc, dict) else None
    if isinstance(version, bool) or not isinstance(version, int) or version not in SUPPORTED:
        _err("schema_version inconnue : versions acceptées 1.")
        return 2
    schema_text = (resources.files("deskgate_bcf") / "schemas" / SUPPORTED[version]).read_text(
        encoding="utf-8"
    )
    errors = sorted(
        jsonschema.Draft202012Validator(json.loads(schema_text)).iter_errors(doc),
        key=lambda e: [str(x) for x in e.absolute_path],
    )
    if errors:
        lines = ["Entrée non conforme au contrat bcf-write-v1 :"]
        for e in errors[:10]:
            path = "/".join(str(x) for x in e.absolute_path)
            lines.append(f"- {path} : {e.message[:300]}")
        _err(*lines)
        return 2
    out = Path(args.output)
    if not out.parent.is_dir():
        _err(f"Dossier de sortie introuvable : {out.parent}.")
        return 3
    try:
        from deskgate_bcf import writer

        writer.write(doc, out)
    except Exception as e:
        _err(f"Écriture du BCF impossible : {type(e).__name__} : {str(e)[:500]}.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
