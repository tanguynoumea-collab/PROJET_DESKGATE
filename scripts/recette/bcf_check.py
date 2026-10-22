"""Contrôle automatique d'un BCF réel et de son clashes.json (stdlib seule).

Usage : bcf_check.py --bcf X.bcf --clashes clashes.json --template GABARIT
        --allowed building=BaJ,BaT --out preuve.json
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
FIELDS = ("building", "storey", "trade_a", "trade_b", "type_a", "type_b")
DEFAULT_TEMPLATE = "{building}/{storey}/{trade_a}-{trade_b}/{type_a} x {type_b}"
OPENINGS = {"IfcOpeningElement", "IfcOpeningStandardCase"}


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _kids(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _tag(c) == name]


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def template_regex(template: str) -> re.Pattern[str]:
    """Regex du gabarit : un groupe nommé par champ, la reprise d'un champ doit être identique."""
    seen: set[str] = set()
    out = ""
    pos = 0
    for m in re.finditer(r"\{([^{}]*)\}", template):
        name = m.group(1)
        if name not in FIELDS:
            raise SystemExit(f"champ inconnu dans le gabarit : {name!r}")
        out += re.escape(template[pos : m.start()])
        out += f"(?P={name})" if name in seen else f"(?P<{name}>[^/]+?)"
        seen.add(name)
        pos = m.end()
    out += re.escape(template[pos:])
    return re.compile(f"^{out}$")


def _check_topic(z: zipfile.ZipFile, names: set[str], folder: str, fails: list[str]) -> str:
    markup = ET.fromstring(z.read(f"{folder}/markup.bcf"))  # noqa: S314
    topic = next(iter(_kids(markup, "Topic")), None)
    title = _text(next(iter(_kids(topic, "Title")), None)) if topic is not None else ""
    tag = f"[{folder[:8]}]"
    if "(+" in title:
        fails.append(f"{tag} titre non conforme (suffixe) : {title!r}")
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


def check(
    bcf: Path,
    clashes: Path,
    template: str = DEFAULT_TEMPLATE,
    allowed: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
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
    allowed = allowed or {}
    regex = template_regex(template)
    for name in allowed:
        if name not in FIELDS:
            raise SystemExit(f"champ inconnu dans --allowed : {name!r}")
    matches = [regex.match(title) for title in titles]
    outside = [title for title, m in zip(titles, matches, strict=True) if m is None]
    if outside:
        fails.append(f"titre hors gabarit : {outside[:10]}")
    ok_allowed = 0
    bad: Counter[tuple[str, str]] = Counter()
    values: dict[str, Counter[str]] = {"building": Counter(), "storey": Counter()}
    for m in matches:
        if m is None:
            continue
        groups = m.groupdict()
        good = True
        for name, vals in allowed.items():
            if name in groups and groups[name] not in vals:
                bad[(name, groups[name])] += 1
                good = False
        ok_allowed += good
        for name, counter in values.items():
            if name in groups:
                counter[groups[name]] += 1
    for (name, value), n in sorted(bad.items()):
        fails.append(f"champ {name} hors valeurs admises : {value!r} ({n})")
    return {
        "verdict": not fails,
        "failures": fails[:50],
        "topics": len(folders),
        "groups": counts.get("groups"),
        "clashes": counts.get("clashes"),
        "template": template,
        "titles_matching": len(titles) - len(outside),
        "titles_allowed": ok_allowed,
        "warnings": warnings,
        "sample_titles": sorted(titles)[:10],
        "values_by_field": {k: dict(sorted(v.items())) for k, v in values.items() if v},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bcf", required=True)
    ap.add_argument("--clashes", required=True)
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--allowed", action="append", default=[], metavar="CHAMP=V1,V2")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    allowed: dict[str, set[str]] = {}
    for item in a.allowed:
        name, _, vals = item.partition("=")
        allowed.setdefault(name, set()).update(v for v in vals.split(",") if v)
    res = check(Path(a.bcf), Path(a.clashes), a.template, allowed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("verdict", "failures", "topics", "groups")}))
    return 0 if res["verdict"] else 1


if __name__ == "__main__":
    sys.exit(main())
