# SPDX-License-Identifier: MIT
"""Capacité ifc.clash : détection hard / clearance avec ifcclash (LGPL), sans export BCF."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.selector as sel
from ifcclash import ifcclash
from lark.exceptions import LarkError

from . import render
from .bcfdoc import build_doc
from .bcfjob import write_bcf
from .context import context_guids
from .grouping import build_groups, prepare
from .naming import fallback_message, missing_message
from .params import ClashError, ClashParams, parse_params
from .spatial import project_refs, topic_titles

MEMORY_MESSAGE = "Mémoire insuffisante : réduisez la sélection ou augmentez memory_mb."
DATA_MAX_BYTES = 900_000


class _Progress:
    """Progression bornée : écart d'au moins 1 % ou 0,5 s, jamais décroissante."""

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self.last_pct = -1.0
        self.last_t = 0.0

    def __call__(self, pct: float, message: str = "", *, force: bool = False) -> None:
        pct = max(self.last_pct, min(100.0, float(pct)))
        now = time.monotonic()
        if not force and not (
            pct - self.last_pct >= 1.0 or (pct > self.last_pct and now - self.last_t >= 0.5)
        ):
            return
        self.last_pct, self.last_t = pct, now
        self.ctx.progress(round(pct, 1), message)


class DeskgateClasher(ifcclash.Clasher):
    """Pré-résout les sélecteurs, ignore l'absence de géométrie, impose check_all=True."""

    def __init__(
        self, num_threads: int, progress: _Progress, include_openings: bool = False
    ) -> None:
        settings = ifcclash.ClashSettings()
        settings.logger = logging.getLogger("deskgate_bim.clash")
        super().__init__(settings)
        self.num_threads = num_threads
        self.progress = progress
        self.include_openings = include_openings
        self.openings_excluded: dict[str, int] = {}
        self.opened: dict[str, Any] = {}
        self._added: set[tuple[int, int]] = set()
        self.selected: dict[str, set[str]] = {}
        self.found: dict[str, int] = {}
        self.with_geom: dict[str, int] = {}
        self._span: tuple[float, float] = (0.0, 45.0)

    def load_ifc(self, path: str) -> Any:
        return self.opened[path]

    def add_collision_objects(self, name: str, ifc_file: Any, source: Any) -> None:
        selector = source["selector"]
        try:
            found = set(sel.filter_elements(ifc_file, selector))
        except (LarkError, re.error) as exc:
            raise ClashError(
                "invalid_selector", f"Sélecteur {name.upper()} invalide : {selector!r}"
            ) from exc
        if not self.include_openings:
            kept = {e for e in found if not e.is_a("IfcOpeningElement")}
            self.openings_excluded[name] = (
                self.openings_excluded.get(name, 0) + len(found) - len(kept)
            )
            found = kept
        with_geom = {e for e in found if getattr(e, "Representation", None) is not None}
        self.found[name] = self.found.get(name, 0) + len(found)
        self.with_geom[name] = self.with_geom.get(name, 0) + len(with_geom)
        self.selected.setdefault(name, set()).update(e.GlobalId for e in with_geom)
        if not with_geom:
            return
        fresh = {e for e in with_geom if (id(ifc_file), e.id()) not in self._added}
        if fresh:
            it = ifcopenshell.geom.iterator(
                self.geom_settings, ifc_file, self.num_threads, include=fresh
            )
            if it.initialize():
                lo, hi = self._span
                while True:
                    self.tree.add_element(it.get())  # pyright: ignore[reportOptionalMemberAccess]
                    self.progress(lo + (hi - lo) * it.progress() / 100.0, f"géométrie {name}")
                    if not it.next():
                        break
            self._added.update((id(ifc_file), e.id()) for e in fresh)
        self.groups[name]["elements"].update({e.GlobalId: e for e in with_geom})

    def process_clash_set(self, clash_set: Any) -> None:
        self.tree = ifcopenshell.geom.tree(backend="opencascade.trianglebvh")
        self.create_group("a")
        self._span = (0.0, 45.0)
        for src in clash_set["a"]:
            src["ifc"] = self.load_ifc(src["file"])
            self.add_collision_objects("a", src["ifc"], src)
        self.progress(45, "géométrie A terminée", force=True)
        other = "a"
        if clash_set.get("b"):
            self.create_group("b")
            other = "b"
            self._span = (45.0, 90.0)
            for src in clash_set["b"]:
                src["ifc"] = self.load_ifc(src["file"])
                self.add_collision_objects("b", src["ifc"], src)
        self.progress(90, "détection", force=True)
        if not self.groups["a"]["elements"] or not self.groups[other]["elements"]:
            clash_set["clashes"] = {}
            return
        a = list(self.groups["a"]["elements"].values())
        b = list(self.groups[other]["elements"].values())
        if clash_set["mode"] == "intersection":
            results = self.tree.clash_intersection_many(  # pyright: ignore[reportOptionalMemberAccess]
                a, b, tolerance=clash_set["tolerance"], check_all=True
            )
        else:
            results = self.tree.clash_clearance_many(  # pyright: ignore[reportOptionalMemberAccess]
                a, b, clearance=clash_set["clearance"], check_all=True
            )
        clash_set["clashes"] = {
            f"{r.a.get_argument(0)}-{r.b.get_argument(0)}": {
                "a_global_id": r.a.get_argument(0),
                "b_global_id": r.b.get_argument(0),
                "a_ifc_class": r.a.is_a(),
                "b_ifc_class": r.b.is_a(),
                "a_name": r.a.get_argument(2),
                "b_name": r.b.get_argument(2),
                "type": ifcopenshell.geom.tree.get_clash_type(r.clash_type),
                "p1": list(r.p1),
                "p2": list(r.p2),
                "distance": r.distance,
            }
            for r in results
        }


def _open(path: str) -> Any:
    if not os.path.isfile(path):
        raise ClashError("ifc_not_found", f"Fichier IFC introuvable : {Path(path).name}")
    try:
        return ifcopenshell.open(path)
    except MemoryError:
        raise
    except (ifcopenshell.Error, OSError, RuntimeError, ValueError) as exc:
        raise ClashError(
            "ifc_unreadable", f"Fichier IFC illisible : {Path(path).name} ({exc})"
        ) from exc


def _warning(
    name: str, selector: str, found: int, geom: int, openings: int = 0
) -> tuple[str, dict[str, Any]]:
    code = f"selection_{name}_empty"
    msg = (
        f"Sélection {name.upper()} vide pour {selector!r} : {found} élément(s) trouvé(s), "
        f"{geom} avec géométrie."
    )
    if openings:
        msg += f" ({openings} réservation(s) exclue(s) ; include_openings: true pour les garder)"
    return code, {"code": code, "message": msg}


def _write_bcf(
    p: ClashParams,
    ctx: Any,
    clasher: DeskgateClasher,
    groups: list[dict[str, Any]],
    warnings: list[str],
    details: list[dict[str, Any]],
    progress: _Progress,
) -> int:
    progress(92, "contexte", force=True)

    def warn(code: str, message: str) -> None:
        warnings.append(code)
        details.append({"code": code, "message": message})
        ctx.log(message)

    context = context_guids(
        list(clasher.opened.values()),
        groups,
        radius=p.context_radius,
        max_context=p.max_context,
        threads=clasher.num_threads,
        warn=warn,
    )
    titles: dict[str, str] = {}
    try:
        titles, missing, fallbacks = topic_titles(
            clasher.opened, p.ifc_a, p.ifc_b, groups, p.charter.model_dump()
        )
        if missing:
            warn("charter_missing", missing_message(missing))
        if fallbacks:
            warn("label_fallback", fallback_message(fallbacks))
    except MemoryError:
        raise
    except Exception as exc:  # le nommage ne doit jamais arrêter le calcul (D-06)
        titles = {}
        warn("naming_unavailable", f"Nommage des sujets indisponible : {exc}")
    names = [Path(f).stem for f in dict.fromkeys(f for f in (p.ifc_a, p.ifc_b) if f)]
    refs = project_refs(clasher.opened, [p.ifc_a, *([p.ifc_b] if p.ifc_b else [])])
    doc = build_doc(
        groups,
        project=p.bcf_project or " ".join(["ifc.clash", *names]),
        author=p.bcf_author,
        created_at=p.created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        context=context,
        mode=p.mode,
        threshold=p.threshold,
        titles=titles,
        header_files=refs or None,
    )
    if p.snapshots:
        progress(93, "rendu des images", force=True)
        try:
            need = {
                g
                for t in doc["topics"]
                for g in (*t["guids_a"], *t["guids_b"], *t["context_guids"])
            }
            meshes = render.harvest(list(clasher.opened.values()), need, clasher.num_threads)
            size = tuple(ctx.settings.get("snapshot_size", (800, 450)))
            paths, no_geom = render.render_topics(
                doc,
                meshes,
                Path(ctx.work_dir) / "snapshots",
                size=size,
                progress=lambda i, n: progress(93 + 2.9 * i / max(n, 1), "rendu des images"),
            )
            for t in doc["topics"]:
                if t["guid"] in paths:
                    t["snapshots"] = paths[t["guid"]]
            if no_geom:
                warn(
                    "snapshots_unavailable",
                    f"{len(no_geom)} sujet(s) sans géométrie : pas d'image. "
                    f"Premiers : {', '.join(no_geom[:20])}",
                )
            del meshes
        except MemoryError:
            raise
        except Exception as exc:  # le rendu ne doit jamais arrêter le job
            warn("snapshots_unavailable", f"Images des points de vue indisponibles : {exc}")
    progress(96, "écriture du BCF", force=True)
    dst = write_bcf(ctx.settings, doc, ctx.work_dir)
    ctx.artifact(dst, "bcf")
    return len(doc["topics"])


def _run(p: ClashParams, ctx: Any) -> dict[str, Any]:
    progress = _Progress(ctx)
    progress(0, "ouverture des fichiers", force=True)
    threads = p.threads or int(ctx.settings.get("threads", 0)) or min(4, os.cpu_count() or 1)
    clasher = DeskgateClasher(threads, progress, include_openings=p.include_openings)
    for path in (p.ifc_a, p.ifc_b):
        if path and path not in clasher.opened:
            clasher.opened[path] = _open(path)
    two_sides = p.ifc_b is not None or p.selector_b is not None
    clash_set: dict[str, Any] = {
        "name": "deskgate",
        "mode": "intersection" if p.mode == "hard" else "clearance",
        "tolerance" if p.mode == "hard" else "clearance": p.threshold,
        "a": [{"file": p.ifc_a, "selector": p.selector_a}],
        "b": (
            [{"file": p.ifc_b or p.ifc_a, "selector": p.selector_b or p.selector_a}]
            if two_sides
            else []
        ),
    }
    clasher.process_clash_set(clash_set)

    warnings: list[str] = []
    details: list[dict[str, Any]] = []
    checks = [("a", p.selector_a)] + ([("b", p.selector_b or p.selector_a)] if two_sides else [])
    for name, selector in checks:
        if clasher.with_geom.get(name, 0) == 0:
            code, detail = _warning(
                name,
                selector,
                clasher.found.get(name, 0),
                clasher.with_geom.get(name, 0),
                clasher.openings_excluded.get(name, 0),
            )
            warnings.append(code)
            details.append(detail)
            ctx.log(detail["message"])

    progress(90, "post-traitement", force=True)
    sel_a = clasher.selected.get("a", set())
    sel_b = clasher.selected.get("b", set()) if two_sides else sel_a
    pairs = prepare(clash_set.get("clashes", {}).values(), sel_a, sel_b)
    total = len(pairs)
    truncated = p.max_clashes is not None and total > p.max_clashes
    if truncated:
        pairs = pairs[: p.max_clashes]
        code = "clashes_truncated"
        msg = (
            f"{len(pairs)} conflits gardés sur {total} (plafond max_clashes = {p.max_clashes}) ; "
            "relancez sans max_clashes pour tout garder."
        )
        warnings.append(code)
        details.append({"code": code, "message": msg})
        ctx.log(msg)
    groups = build_groups(pairs, p.group_radius, p.mode, p.threshold)
    data: dict[str, Any] = {
        "unit": "m",
        "mode": p.mode,
        "threshold": p.threshold,
        "counts": {
            "selection_a": len(sel_a),
            "selection_b": len(sel_b),
            "clashes": total,
            "returned": len(pairs),
            "groups": len(groups),
            "openings_excluded": sum(clasher.openings_excluded.values()),
        },
        "truncated": truncated,
        "pairs_omitted": False,
        "groups_omitted": False,
        "groups": groups,
    }
    out = Path(ctx.work_dir) / "clashes.json"
    out.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8")
    ctx.artifact(str(out), "clashes")
    bcf_topics = 0
    if p.bcf:
        if not groups:
            warnings.append("bcf_skipped_no_clash")
            msg = "Aucun conflit : BCF non produit."
            details.append({"code": "bcf_skipped_no_clash", "message": msg})
            ctx.log(msg)
        else:
            bcf_topics = _write_bcf(p, ctx, clasher, groups, warnings, details, progress)
    limit = int(ctx.settings.get("data_max_bytes", DATA_MAX_BYTES))

    def size() -> int:
        return len(json.dumps(data, ensure_ascii=False))

    def note(code: str, message: str) -> None:
        warnings.append(code)
        details.append({"code": code, "message": message})
        ctx.log(message)

    if size() > limit:
        for g in data["groups"]:
            g["clashes"] = []
        data["pairs_omitted"] = True
        note(
            "data_pairs_omitted",
            "Résultat allégé (taille) : paires omises ; clashes.json est complet.",
        )
    if size() > limit:
        all_groups = data["groups"]
        data["groups"] = []
        used = size()
        kept = 0
        if used <= limit:
            for g in all_groups:
                used += len(json.dumps(g, ensure_ascii=False)) + 1
                if used > limit:
                    break
                kept += 1
        data["groups"] = all_groups[:kept]
        data["groups_omitted"] = True
        note(
            "data_groups_omitted",
            f"Résultat allégé (taille) : {len(all_groups) - kept} groupe(s) omis ; "
            "clashes.json est complet.",
        )
    progress(100, "terminé", force=True)
    summary: dict[str, Any] = {
        "clashes": total,
        "groups": len(groups),
        "truncated": truncated,
        "pairs_omitted": data["pairs_omitted"],
        "groups_omitted": data["groups_omitted"],
        "openings_excluded": data["counts"]["openings_excluded"],
        "warnings": warnings,
        "warning_details": details,
        "mode": p.mode,
        "unit": "m",
        "ifcopenshell": ifcopenshell.version,
        "bcf": bcf_topics > 0,
        "bcf_topics": bcf_topics,
    }
    summary["tolerance" if p.mode == "hard" else "clearance"] = p.threshold
    return {"summary": summary, "data": data}


def run(params: dict[str, Any], ctx: Any) -> dict[str, Any]:
    p = parse_params(params)
    try:
        return _run(p, ctx)
    except MemoryError:
        raise ClashError("memory", MEMORY_MESSAGE) from None
