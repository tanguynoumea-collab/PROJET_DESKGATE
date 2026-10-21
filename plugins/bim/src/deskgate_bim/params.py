# SPDX-License-Identifier: MIT
"""Paramètres validés de la capacité ifc.clash et erreurs classées."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

ISO_8601 = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$"
)


class ClashError(Exception):
    """Erreur classée : `error_code` est lu par le SDK et devient `error.type`."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


Key = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Code = Annotated[str, StringConstraints(min_length=1, max_length=32)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class Trades(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: Code | None = None
    b: Code | None = None


class Charter(BaseModel):
    """Charte de nommage des sujets (D-05) : valeurs IFC -> codes courts."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    buildings: dict[Key, Code] = Field(default_factory=dict, max_length=500)
    levels: dict[Key, Code] = Field(default_factory=dict, max_length=500)
    trades: Trades = Field(default_factory=Trades)
    labels: dict[Key, Label] = Field(default_factory=dict, max_length=500)


class ClashParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ifc_a: str = Field(min_length=1)
    ifc_b: str | None = None
    selector_a: str = Field(min_length=1, max_length=2000)
    selector_b: str | None = Field(default=None, max_length=2000)
    mode: Literal["hard", "clearance"]
    tolerance: float | None = Field(default=None, ge=0, le=1)
    clearance: float | None = Field(default=None, gt=0, le=10)
    group_radius: float = Field(default=2.0, ge=0, le=1000)
    max_clashes: int | None = Field(default=None, ge=1, le=1_000_000)
    include_openings: bool = False
    threads: int | None = Field(default=None, ge=1, le=64)
    bcf: bool = False
    bcf_author: str = Field(default="deskgate", min_length=1, max_length=256)
    bcf_project: str | None = Field(default=None, min_length=1, max_length=256)
    created_at: str | None = Field(default=None, pattern=ISO_8601)
    context_radius: float = Field(default=5.0, ge=0, le=1000)
    max_context: int = Field(default=500, ge=0, le=5000)
    charter: Charter = Field(default_factory=Charter)

    @model_validator(mode="after")
    def _threshold(self) -> ClashParams:
        if self.mode == "hard":
            if self.tolerance is None:
                raise ValueError("mode hard : tolerance (m) obligatoire")
            if self.clearance is not None:
                raise ValueError("mode hard : clearance non admis")
        else:
            if self.clearance is None:
                raise ValueError("mode clearance : clearance (m) obligatoire")
            if self.tolerance is not None:
                raise ValueError("mode clearance : tolerance non admis")
        return self

    @property
    def threshold(self) -> float:
        value = self.tolerance if self.mode == "hard" else self.clearance
        return float(value or 0.0)


def parse_params(raw: dict[str, Any]) -> ClashParams:
    try:
        return ClashParams.model_validate(raw)
    except ValidationError as exc:
        parts: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"])
            if err["type"] == "extra_forbidden":
                parts.append(f"paramètre inconnu : {loc}")
            elif err["type"] == "value_error":
                parts.append(str(err["msg"]).removeprefix("Value error, "))
            elif err["type"] == "missing":
                parts.append(f"paramètre manquant : {loc}")
            else:
                parts.append(f"paramètre invalide : {loc}")
        raise ClashError("invalid_params", " ; ".join(parts)) from None
