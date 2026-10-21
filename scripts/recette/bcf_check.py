"""Contrôle automatique d'un BCF réel et de son clashes.json (stdlib seule).

Usage : bcf_check.py --bcf X.bcf --clashes clashes.json --trigrams BaJ,BaT --out preuve.json
Code de sortie 0 si le verdict est vrai, 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PNG = bytes.fromhex("89504e470d0a1a0a")
TITLE = re.compile(r"^[^/]+/[^/]+/[^/]+-[^/]+/.+ x .+$")
OPENINGS = {"IfcOpeningElement", "IfcOpeningStandardCase"}


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _kids(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _tag(c) == name]


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _check_topic(z: zipfile.ZipFile, names: set[str], folder: str, fails: list[str]) -> str:
    markup = ET.fromstring(z.read(f"{folder}/markup.bcf"))  # noqa: S314
    topic = next(iter(_kids(markup, "Topic")), None)
    title = _text(next(iter(_kids(topic, "Title")), None)) if topic is not None else ""
    tag = f"[{folder[:8]}]"
    if not TITLE.match(title) or "(+" in title:
        fails.append(f"{tag} titre non conforme : {title!r}")
    for member in ("viewpoint.bcfv", "snapshot.png"):
        if f"{folder}/{member}" not in names:
            fails.append(f"{tag} membre absent : {member}")
    header = next(iter(_kids(markup, "Header")), None)
    files = _kids(header, "File") if header is not None else []
    if not any(len(f.get("IfcProject", "")) == 22 for f in files):
        fails.append(f"{tag} Header/File sans IfcProject de 22 caractères")
    views = _kids(markup, "Viewpoints")
    if len(views) != 2:
        fails.append(f"{tag} {len(views)} points de vue au lieu de 2")
    guids: set[str] = set()
    indexes: list[str] = []
    for v in views:
        guids.add(v.get("Guid", ""))
        indexes.append(_text(next(iter(_kids(v, "Index")), None)))
        name = _text(next(iter(_kids(v, "Snapshot")), None))
        member = f"{folder}/{name}"
        if not name or member not in names:
            fails.append(f"{tag} PNG manquant pour le point de vue {v.get('Guid', '')[:8]}")
        elif not z.read(member).startswith(PNG):
            fails.append(f"{tag} {name} n'est pas un PNG")
    if views and sorted(indexes) != ["0", "1"]:
        fails.append(f"{tag} Index {indexes} au lieu de 0 et 1")
    comments = _kids(markup, "Comment")
    linked = [
        c for c in comments if any(_tag(x) == "Viewpoint" and x.get("Guid") in guids for x in c)
    ]
    if len(comments) != 2 or len(linked) != 2:
        fails.append(f"{tag} commentaires : {len(comments)} dont {len(linked)} liés (attendu 2)")
    return title


def check(bcf: Path, clashes: Path, trigrams: set[str]) -> dict[str, Any]:
    fails: list[str] = []
    data = json.loads(clashes.read_text(encoding="utf-8"))
    counts = data.get("counts", {})
    titles: list[str] = []
    with zipfile.ZipFile(bcf) as z:
        names = set(z.namelist())
        folders = sorted(n[: -len("/markup.bcf")] for n in names if n.endswith("/markup.bcf"))
        for folder in folders:
            titles.append(_check_topic(z, names, folder, fails))
    if len(folders) != counts.get("groups"):
        fails.append(f"sujets {len(folders)} != groupes {counts.get('groups')}")
    if data.get("truncated") is not False:
        fails.append("clashes.json tronqué")
    if counts.get("clashes") != counts.get("returned"):
        fails.append(f"clashes {counts.get('clashes')} != returned {counts.get('returned')}")
    if any(
        c.get("a_ifc_class") in OPENINGS or c.get("b_ifc_class") in OPENINGS
        for g in data.get("groups", [])
        for c in g.get("clashes", [])
    ):
        fails.append("paire IfcOpeningElement présente")
    result = clashes.parent / "result.json"
    warnings: list[str] = []
    if result.is_file():
        summary = json.loads(result.read_text(encoding="utf-8")).get("summary", {})
        warnings = [str(w) for w in summary.get("warnings", [])]
        if "snapshots_unavailable" in warnings:
            fails.append("avertissement snapshots_unavailable dans le résumé")
    with_tri = sum(1 for t in titles if t.split("/")[0] in trigrams)
    if with_tri != len(titles):
        fails.append(f"titres avec trigramme {with_tri} sur {len(titles)}")
    storeys = Counter(t.split("/")[1] for t in titles if t.count("/") >= 1)
    return {
        "verdict": not fails,
        "failures": fails[:50],
        "topics": len(folders),
        "groups": counts.get("groups"),
        "clashes": counts.get("clashes"),
        "titles_with_trigram": with_tri,
        "warnings": warnings,
        "sample_titles": sorted(titles)[:10],
        "storeys": dict(sorted(storeys.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bcf", required=True)
    ap.add_argument("--clashes", required=True)
    ap.add_argument("--trigrams", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = check(Path(a.bcf), Path(a.clashes), {t for t in a.trigrams.split(",") if t})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("verdict", "failures", "topics", "groups")}))
    return 0 if res["verdict"] else 1


if __name__ == "__main__":
    sys.exit(main())
