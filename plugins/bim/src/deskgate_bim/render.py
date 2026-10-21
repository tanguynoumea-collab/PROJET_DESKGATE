# SPDX-License-Identifier: MIT
"""Rendu logiciel hors écran des points de vue BCF (Pillow + numpy, sans GPU), déterministe."""

from __future__ import annotations

import io
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

# Sommets float64 monde (n, 3), faces int32 (m, 3). Jamais de simple précision (0,25 m perdus).
Mesh = tuple[np.ndarray, np.ndarray]
RGBA = tuple[int, int, int, int]

NEAR = 0.05
LIGHT = np.array([-0.4, 0.3, 0.85]) / np.linalg.norm([-0.4, 0.3, 0.85])
DEFAULT_SIZE = (800, 450)


def harvest(ifc_files: list[Any], guids: set[str], threads: int) -> dict[str, Mesh]:
    """Maillages en coordonnées monde des éléments demandés, premier fichier gagnant."""
    import ifcopenshell.geom

    store: dict[str, Mesh] = {}
    for f in ifc_files:
        els = []
        for g in sorted(guids):
            if g in store:
                continue
            try:
                e = f.by_guid(g)
            except RuntimeError:
                continue
            if getattr(e, "Representation", None):
                els.append(e)
        if not els:
            continue
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        it = ifcopenshell.geom.iterator(settings, f, max(1, int(threads)), include=els)
        if not it.initialize():
            continue
        while True:
            shape = it.get()
            geo = shape.geometry
            store[shape.guid] = (
                np.array(geo.verts, dtype=np.float64).reshape(-1, 3),
                np.array(geo.faces, dtype=np.int32).reshape(-1, 3),
            )
            if not it.next():
                break
    return store


def argb_to_rgba(argb: str) -> RGBA:
    return (
        int(argb[2:4], 16),
        int(argb[4:6], 16),
        int(argb[6:8], 16),
        int(argb[0:2], 16),
    )


def _clip_near(tri: np.ndarray) -> np.ndarray | None:
    """Sutherland-Hodgman contre z >= NEAR pour un triangle (3, 3) ; None si hors champ."""
    out: list[np.ndarray] = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        a_in, b_in = a[2] >= NEAR, b[2] >= NEAR
        if a_in:
            out.append(a)
        if a_in != b_in:
            t = (NEAR - a[2]) / (b[2] - a[2])
            out.append(a + t * (b - a))
    return np.array(out) if len(out) >= 3 else None


def _project(
    meshes: list[tuple[RGBA, Mesh]],
    pos: np.ndarray,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
    f: float,
    size: tuple[int, int],
) -> tuple[list[Any], np.ndarray, np.ndarray, np.ndarray]:
    """Polygones écran, profondeurs, ombrages et couleurs (RGB) des triangles visibles."""
    r, u, d = basis
    w, h = size
    aspect = w / h
    polys: list[Any] = []
    depths: list[float] = []
    shades: list[float] = []
    colors: list[tuple[int, int, int]] = []

    def screen(p: np.ndarray) -> np.ndarray:
        sx = (f * p[..., 0] / p[..., 2] / aspect + 1) * w / 2
        sy = (1 - f * p[..., 1] / p[..., 2]) * h / 2
        return np.stack([sx, sy], axis=-1)

    for rgba, (verts, faces) in meshes:
        if len(faces) == 0:
            continue
        rel = verts - pos
        cam = np.stack([rel @ r, rel @ u, rel @ d], axis=1)
        tris = cam[faces]
        n = np.cross(
            verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]]
        )
        ln = np.linalg.norm(n, axis=1)
        ln[ln == 0] = 1.0
        shade = 0.55 + 0.45 * np.abs((n / ln[:, None]) @ LIGHT)
        front = (tris[:, :, 2] >= NEAR).sum(axis=1)
        full = front == 3
        if full.any():
            sc = screen(tris[full])
            for k, idx in enumerate(np.nonzero(full)[0]):
                polys.append(sc[k])
                depths.append(float(tris[idx, :, 2].mean()))
                shades.append(float(shade[idx]))
                colors.append(rgba[:3])
        for idx in np.nonzero((front == 1) | (front == 2))[0]:
            poly = _clip_near(tris[idx])
            if poly is None:
                continue
            polys.append(screen(poly))
            depths.append(float(poly[:, 2].mean()))
            shades.append(float(shade[idx]))
            colors.append(rgba[:3])
    return (
        polys,
        np.array(depths, dtype=np.float64),
        np.array(shades, dtype=np.float64),
        np.array(colors, dtype=np.float64).reshape(-1, 3),
    )


def _layer(
    meshes: list[tuple[RGBA, Mesh]],
    alpha: int | None,
    pos: np.ndarray,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
    f: float,
    size: tuple[int, int],
) -> Any:
    from PIL import Image, ImageDraw

    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    polys, depth, shade, colors = _project(meshes, pos, basis, f, size)
    if not polys:
        return layer
    order = np.lexsort((np.arange(len(depth)), -depth))  # plus loin d'abord, départage par indice
    draw = ImageDraw.Draw(layer)
    a = 255 if alpha is None else alpha
    for i in order:
        c = (colors[i] * shade[i]).astype(int)
        draw.polygon(
            [tuple(p) for p in polys[i].tolist()], fill=(int(c[0]), int(c[1]), int(c[2]), a)
        )
    return layer


def render_view(
    camera: dict[str, Any],
    opaque: list[tuple[RGBA, Mesh]],
    context: list[Mesh] | None = None,
    context_rgba: RGBA = (176, 176, 176, 64),
    size: tuple[int, int] = DEFAULT_SIZE,
) -> bytes:
    """PNG d'un point de vue : contexte gris transparent puis objets opaques par-dessus."""
    from PIL import Image

    w, h = int(size[0]), int(size[1])
    if not (16 <= w <= 4096 and 16 <= h <= 4096):
        raise ValueError("taille d'image invalide")
    pos = np.array(camera["position"], dtype=np.float64)
    d = np.array(camera["direction"], dtype=np.float64)
    d /= np.linalg.norm(d)
    r = np.cross(d, np.array(camera["up"], dtype=np.float64))
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    f = 1.0 / math.tan(math.radians(float(camera.get("field_of_view", 60.0))) / 2)
    basis = (r, u, d)
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    if context:
        layer = _layer([(context_rgba, m) for m in context], context_rgba[3], pos, basis, f, (w, h))
        img = Image.alpha_composite(img, layer)
    if opaque:
        img = Image.alpha_composite(img, _layer(opaque, None, pos, basis, f, (w, h)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", compress_level=6, optimize=False)
    return buf.getvalue()


def render_topics(
    doc: dict[str, Any],
    meshes: dict[str, Mesh],
    out_dir: Path,
    size: tuple[int, int] = DEFAULT_SIZE,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Écrit deux PNG par sujet ; renvoie les chemins relatifs et les sujets sans géométrie."""
    colors = doc["colors"]
    rgba_a, rgba_b = argb_to_rgba(colors["a"]), argb_to_rgba(colors["b"])
    rgba_ctx = argb_to_rgba(colors["context"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    topics = doc["topics"]
    for i, t in enumerate(topics):
        opaque = [(rgba_a, meshes[g]) for g in t["guids_a"] if g in meshes] + [
            (rgba_b, meshes[g]) for g in t["guids_b"] if g in meshes
        ]
        if not opaque:
            missing.append(t["guid"])
        else:
            ctx = [meshes[g] for g in t["context_guids"] if g in meshes]
            cam = t["camera"]
            only = render_view(cam, opaque, None, rgba_ctx, size)
            both = render_view(cam, opaque, ctx, rgba_ctx, size)
            (out_dir / f"{t['guid']}-1.png").write_bytes(only)
            (out_dir / f"{t['guid']}-2.png").write_bytes(both)
            result[t["guid"]] = {
                "only": f"{out_dir.name}/{t['guid']}-1.png",
                "context": f"{out_dir.name}/{t['guid']}-2.png",
            }
        if progress:
            progress(i + 1, len(topics))
    return result, sorted(missing)
