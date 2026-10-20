"""Configuration `runner.toml` : modèles stricts, messages français sans fuite de valeur.

Noyau pur : le fichier est lu par `load_config`, tout le reste travaille sur du texte.
Les messages d'erreur citent le chemin complet de la clé fautive, jamais sa valeur.
"""

from __future__ import annotations

import ipaddress
import re
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic_core import PydanticCustomError

from deskgate.core.paths import (
    Mapping,
    PathDenied,
    is_under,
    normalize_host_path,
    split_container_path,
)


class ConfigError(Exception):
    code = "invalid_config"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _host_root(value: str) -> str:
    try:
        return normalize_host_path(value)
    except PathDenied as exc:
        raise PydanticCustomError("path_invalid", "{msg}", {"msg": exc.message}) from None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PathMapping(Strict):
    container: str
    host: str

    @field_validator("container")
    @classmethod
    def _container(cls, v: str) -> str:
        try:
            return "/" + "/".join(split_container_path(v))
        except PathDenied as exc:
            raise ValueError(exc.message) from None

    @field_validator("host")
    @classmethod
    def _host(cls, v: str) -> str:
        try:
            return normalize_host_path(v)
        except PathDenied as exc:
            raise ValueError(exc.message) from None


class Paths(Strict):
    allowed_roots: list[Annotated[str, AfterValidator(_host_root)]] = Field(min_length=1)
    mapping: list[PathMapping] = []

    @field_validator("mapping")
    @classmethod
    def _inside_roots(cls, v: list[PathMapping], info: ValidationInfo) -> list[PathMapping]:
        if "allowed_roots" not in info.data:
            return v
        roots: list[str] = info.data["allowed_roots"]
        for i, m in enumerate(v):
            if not any(is_under(m.host, root) for root in roots):
                raise PydanticCustomError(
                    "mapping_outside_roots",
                    "le chemin hôte du mapping {index} n'est sous aucune racine autorisée",
                    {"index": i},
                )
        return v


class Capability(Strict):
    kind: Literal["python"]
    python: Annotated[str, AfterValidator(_host_root)]
    entry: Annotated[
        str,
        StringConstraints(
            pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$"
        ),
    ]
    timeout_max: int = Field(gt=0, le=43200)
    pythonpath: list[Annotated[str, AfterValidator(_host_root)]] = []
    memory_mb: int | None = Field(default=None, ge=16)
    resource: str = "default"


class RunnerConfig(Strict):
    allow_non_loopback: bool = False
    host: str = "127.0.0.1"
    port: int = Field(8765, ge=1, le=65535)
    token_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    paths: Paths
    callback_allowed_hosts: list[str] = []
    capabilities: dict[str, Capability] = {}
    work_root: Annotated[str, AfterValidator(_host_root)] | None = None

    @field_validator("work_root")
    @classmethod
    def _work_root_inside_roots(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is None or "paths" not in info.data:
            return v
        roots: list[str] = info.data["paths"].allowed_roots
        if not any(is_under(v, root) for root in roots):
            raise PydanticCustomError(
                "work_root_outside_roots",
                "work_root doit être sous une racine autorisée",
            )
        return v

    def effective_work_root(self) -> str:
        return self.work_root or f"{self.paths.allowed_roots[0]}/travail"

    @field_validator("host")
    @classmethod
    def _host(cls, v: str, info: ValidationInfo) -> str:
        try:
            addr = ipaddress.IPv4Address(v)
        except ValueError:
            raise ValueError("adresse IPv4 littérale attendue (ex. 127.0.0.1)") from None
        if not addr.is_loopback and not info.data.get("allow_non_loopback", False):
            raise ValueError(
                "adresse non locale refusée : ajoutez allow_non_loopback = true "
                "pour écouter sur une autre interface"
            )
        return v

    def listen_warnings(self) -> tuple[str, ...]:
        if ipaddress.IPv4Address(self.host).is_loopback:
            return ()
        return ("listen_non_loopback",)

    def mappings(self) -> tuple[Mapping, ...]:
        return tuple(Mapping(container=m.container, host=m.host) for m in self.paths.mapping)


_MESSAGES = {
    "extra_forbidden": "clé inconnue",
    "missing": "clé obligatoire absente",
    "int_parsing": "entier attendu",
    "int_type": "entier attendu",
    "bool_parsing": "booléen attendu (true ou false)",
    "bool_type": "booléen attendu (true ou false)",
    "string_type": "chaîne attendue",
    "list_type": "liste attendue",
    "dict_type": "table attendue",
    "model_type": "table attendue",
    "greater_than_equal": "valeur trop petite",
    "greater_than": "doit être strictement positif",
    "less_than_equal": "valeur trop grande",
    "string_pattern_mismatch": "format invalide",
    "too_short": "liste vide non autorisée",
    "literal_error": "valeur non autorisée",
}


def _format_errors(exc: ValidationError, source: str) -> str:
    lines = []
    for e in exc.errors(include_input=False, include_url=False, include_context=False):
        key = ".".join(str(p) for p in e["loc"])
        kind = e["type"]
        if kind in _MESSAGES:
            text = _MESSAGES[kind]
        elif kind == "value_error":
            text = e["msg"].removeprefix("Value error, ")
        else:
            text = e["msg"]
        lines.append(f"- {key} : {text}")
    return f"Configuration invalide ({source}) :\n" + "\n".join(lines)


_POS = re.compile(r"line (\d+), column (\d+)")


def _toml_position(exc: tomllib.TOMLDecodeError) -> tuple[Any, Any]:
    line = getattr(exc, "lineno", None)
    col = getattr(exc, "colno", None)
    if line is None or col is None:
        found = _POS.search(str(exc))
        line, col = (found.group(1), found.group(2)) if found else ("?", "?")
    return line, col


def parse_config(text: str, source: str) -> RunnerConfig:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        line, col = _toml_position(exc)
        raise ConfigError(
            f"Fichier {source} illisible (ligne {line}, colonne {col}) : vérifiez la syntaxe "
            "TOML ; pour un chemin Windows, utilisez 'C:/BIM' ou 'C:\\BIM' entre apostrophes."
        ) from None
    try:
        return RunnerConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_format_errors(exc, source)) from None


def load_config(path: Path) -> RunnerConfig:
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise ConfigError(
            f"Fichier de configuration introuvable : {path}. Copiez le gabarit "
            "runner.example.toml du paquet et générez un jeton avec `deskgate dev-token`."
        ) from None
    except PermissionError:
        raise ConfigError(f"Lecture refusée : {path}.") from None
    except UnicodeDecodeError:
        raise ConfigError(f"{path} n'est pas encodé en UTF-8.") from None
    return parse_config(text, str(path))
