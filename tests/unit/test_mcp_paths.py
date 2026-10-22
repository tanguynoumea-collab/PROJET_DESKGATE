"""Conversion pure des arguments de chemin des appels mcp.call."""

from __future__ import annotations

import pytest

from deskgate.core.paths import Mapping, PathDenied, convert_mcp_arguments

pytestmark = pytest.mark.unit

MAPPINGS = (Mapping(container="/data", host="C:/BIM"),)
ROOTS = ["C:/BIM"]
DECL = {"srv": {"read_file": ["path", "many"]}}


def _conv(params: dict[str, object]) -> dict[str, object]:
    return convert_mcp_arguments(params, DECL, MAPPINGS, ROOTS, lambda p: p)


def _call(arguments: object, tool: str = "read_file") -> dict[str, object]:
    return {"server": "srv", "tool": tool, "arguments": arguments}


def test_argument_declare_converti() -> None:
    out = _conv(_call({"path": "/data/depot/a.txt", "n": 3}))
    assert out == _call({"path": "C:/BIM/depot/a.txt", "n": 3})


def test_liste_convertie() -> None:
    out = _conv(_call({"many": ["/data/a", "/data/b"]}))
    assert out["arguments"] == {"many": ["C:/BIM/a", "C:/BIM/b"]}


def test_argument_declare_absent_ignore() -> None:
    assert _conv(_call({"x": 1})) == _call({"x": 1})


def test_dotdot_refuse() -> None:
    with pytest.raises(PathDenied) as e:
        _conv(_call({"path": "/data/../x"}))
    assert e.value.code == "path_outside_roots"


def test_hors_racine_refuse() -> None:
    with pytest.raises(PathDenied) as e:
        _conv(_call({"path": "C:/Windows/x"}))
    assert e.value.code in {"path_outside_roots", "path_invalid"}


def test_type_invalide() -> None:
    with pytest.raises(PathDenied) as e:
        _conv(_call({"path": 3}))
    assert e.value.code == "path_invalid"


def test_argument_non_declare_opaque() -> None:
    src = _call({"text": "/data/../x"})
    assert _conv(src) == src


def test_argument_imbrique_inchange() -> None:
    src = _call({"opts": {"path": "/data/../x"}})
    assert _conv(src) == src


@pytest.mark.parametrize(
    "params",
    [
        {"server": "zz", "tool": "read_file", "arguments": {"path": "/data/../x"}},
        {"server": 3, "tool": "read_file", "arguments": {}},
        {"server": "srv", "tool": "echo", "arguments": {"path": "/data/../x"}},
        {"server": "srv", "tool": "read_file"},
        {"server": "srv", "tool": "read_file", "arguments": [1]},
    ],
)
def test_entrees_inconnues_inchangees(params: dict[str, object]) -> None:
    assert _conv(params) == params


def test_params_entree_non_modifies() -> None:
    src = _call({"path": "/data/a"})
    _conv(src)
    assert src["arguments"] == {"path": "/data/a"}
