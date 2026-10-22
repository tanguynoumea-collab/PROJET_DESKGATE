"""Chemins D-09 : conversion conteneur/hôte, contrôles lexicaux, résolution injectée.

Le contrôle lexical est écrit à la main sur des chaînes : les aides de la bibliothèque standard
pour les noms réservés ou les chemins absolus changent de comportement selon la version de Python.
L'appartenance à une racine se décide par segments, jamais par préfixe de chaîne (`C:/BIM2`).
Limites acceptées : substitution d'une jonction entre le contrôle et l'usage, liens physiques,
noms courts 8.3 (le caractère `~` n'est pas rejeté).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from collections.abc import Mapping as AbcMapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

Resolver = Callable[[str], str]

_OUTSIDE = "path_outside_roots"
_INVALID = "path_invalid"

_CONTROL = re.compile(r"[\x00-\x1f]")
_FORBIDDEN = re.compile(r'[<>"|?*]')
_DRIVE = re.compile(r"^[A-Za-z]:/")
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
    | {"COM\u00b9", "COM\u00b2", "COM\u00b3", "LPT\u00b9", "LPT\u00b2", "LPT\u00b3"}
)


@dataclass(frozen=True)
class Mapping:
    container: str
    host: str


class PathDenied(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def default_resolver(p: str) -> str:
    return str(Path(p).resolve(strict=False))


def _check_segments(raw: object, *, host: bool) -> list[str]:
    """Contrôle lexical commun ; renvoie les segments (lecteur « C: » en tête, forme hôte)."""
    if not isinstance(raw, str) or not raw:
        raise PathDenied(_INVALID, "Chemin vide ou invalide.")
    if _CONTROL.search(raw):
        raise PathDenied(_INVALID, "Caractère interdit dans le chemin.")
    s = raw.replace("\\", "/")
    if s.startswith("//"):
        raise PathDenied(_OUTSIDE, "Chemin réseau ou de périphérique refusé.")
    if _FORBIDDEN.search(s):
        raise PathDenied(_INVALID, "Caractère interdit dans le chemin.")
    if host:
        if not _DRIVE.match(s):
            raise PathDenied(_INVALID, "Chemin hôte absolu attendu (X:/...).")
        body = s[3:]
        head = [s[0].upper() + ":"]
    else:
        if not s.startswith("/"):
            raise PathDenied(_INVALID, "Chemin conteneur absolu attendu (/...).")
        body = s[1:]
        head = []
    if body.endswith("/"):
        body = body[:-1]
    segments = body.split("/") if body else []
    if ".." in segments:
        raise PathDenied(_OUTSIDE, "Remontée de répertoire (..) refusée.")
    for seg in segments:
        if seg in ("", "."):
            raise PathDenied(_INVALID, "Segment vide ou « . » refusé.")
        if ":" in seg:
            raise PathDenied(_INVALID, "Flux alternatif ou deux-points refusé.")
        if seg.endswith((" ", ".")):
            raise PathDenied(_INVALID, "Nom terminé par un point ou un espace refusé.")
        if seg.split(".")[0].rstrip(" ").upper() in _RESERVED:
            raise PathDenied(_INVALID, "Nom de périphérique Windows réservé refusé.")
    return head + segments


def normalize_host_path(raw: str) -> str:
    return "/".join(_check_segments(raw, host=True))


def split_container_path(raw: str) -> list[str]:
    return _check_segments(raw, host=False)


def _loose(path: str) -> list[str]:
    return [s.lower() for s in path.replace("\\", "/").split("/") if s]


def _prefix(prefix: list[str], full: list[str]) -> bool:
    return len(prefix) <= len(full) and full[: len(prefix)] == prefix


def is_under(path: str, root: str) -> bool:
    return _prefix(_loose(root), _loose(path))


def container_to_host(raw: str, mappings: Sequence[Mapping]) -> str:
    segments = split_container_path(raw)
    low = [s.lower() for s in segments]
    best: tuple[int, Mapping] | None = None
    for m in mappings:
        prefix = _loose(m.container)
        if _prefix(prefix, low) and (best is None or len(prefix) > best[0]):
            best = (len(prefix), m)
    if best is None:
        raise PathDenied(_OUTSIDE, "Chemin hors des racines autorisées.")
    n, m = best
    return "/".join([normalize_host_path(m.host), *segments[n:]])


def host_to_container(host_path: str, mappings: Sequence[Mapping]) -> str:
    segments = _check_segments(host_path, host=True)
    low = [s.lower() for s in segments]
    best: tuple[int, Mapping] | None = None
    for m in mappings:
        prefix = _loose(normalize_host_path(m.host))
        if _prefix(prefix, low) and (best is None or len(prefix) > best[0]):
            best = (len(prefix), m)
    if best is None:
        raise PathDenied(_OUTSIDE, "Chemin hors des racines autorisées.")
    n, m = best
    return "/".join(["", *split_container_path(m.container), *segments[n:]])


def _clean_resolved(resolved: str) -> str:
    s = resolved.replace("\\", "/")
    if s.startswith("//?/"):
        s = s[4:]
        if s.lower().startswith("unc/"):
            raise PathDenied(_OUTSIDE, "Chemin réseau ou de périphérique refusé.")
    if s.startswith("//"):
        raise PathDenied(_OUTSIDE, "Chemin réseau ou de périphérique refusé.")
    return normalize_host_path(s)


def resolve_within_roots(
    host_path: str, roots: Sequence[str], resolver: Resolver = default_resolver
) -> str:
    lexical = normalize_host_path(host_path)
    clean_roots = [normalize_host_path(r) for r in roots]
    if not any(is_under(lexical, r) for r in clean_roots):
        raise PathDenied(_OUTSIDE, "Chemin hors des racines autorisées.")
    resolved = _clean_resolved(resolver(lexical))
    for r in clean_roots:
        if is_under(resolved, _clean_resolved(resolver(r))):
            return resolved
    raise PathDenied(_OUTSIDE, "Chemin hors des racines autorisées après résolution.")


def validate_container_path(
    raw: str,
    mappings: Sequence[Mapping],
    roots: Sequence[str],
    resolver: Resolver = default_resolver,
) -> str:
    return resolve_within_roots(container_to_host(raw, mappings), roots, resolver)


def validate_artifact_path(
    host_path: str,
    mappings: Sequence[Mapping],
    roots: Sequence[str],
    resolver: Resolver = default_resolver,
) -> str:
    resolve_within_roots(host_path, roots, resolver)
    return host_to_container(host_path, mappings)


def convert_path_params(
    params: AbcMapping[str, object],
    keys: Sequence[str],
    mappings: Sequence[Mapping],
    roots: Sequence[str],
    resolver: Resolver = default_resolver,
) -> dict[str, object]:
    """Convertit en chemins hôte validés les paramètres déclarés (chaîne ou liste de chaînes)."""
    out: dict[str, object] = dict(params)
    for key in keys:
        if key not in out:
            continue
        value = out[key]
        if isinstance(value, str):
            out[key] = validate_container_path(value, mappings, roots, resolver)
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            out[key] = [validate_container_path(v, mappings, roots, resolver) for v in value]
        else:
            raise PathDenied(
                _INVALID, f"Le paramètre {key} doit être un chemin ou une liste de chemins."
            )
    return out


def convert_mcp_arguments(
    params: AbcMapping[str, object],
    path_arguments: AbcMapping[str, AbcMapping[str, Sequence[str]]],
    mappings: Sequence[Mapping],
    roots: Sequence[str],
    resolver: Resolver = default_resolver,
) -> dict[str, object]:
    """Convertit les arguments de chemin déclarés d'un appel mcp.call (premier niveau seulement).

    Serveur, outil ou arguments inconnus ou mal typés : params renvoyés tels quels (le worker
    produit déjà invalid_params, server_not_declared ou tool_not_allowed). Les arguments non
    déclarés restent opaques.
    """
    out: dict[str, object] = dict(params)
    server, tool, args = params.get("server"), params.get("tool"), params.get("arguments")
    if not isinstance(server, str) or not isinstance(tool, str) or not isinstance(args, dict):
        return out
    keys = path_arguments.get(server, {}).get(tool, ())
    if not keys:
        return out
    typed_args = cast("dict[str, object]", args)
    out["arguments"] = convert_path_params(typed_args, list(keys), mappings, roots, resolver)
    return out
