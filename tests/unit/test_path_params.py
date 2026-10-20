"""Conversion pure des paramètres de chemin déclarés."""

from __future__ import annotations

import pytest

from deskgate.core.env import mcp_env_var
from deskgate.core.paths import Mapping, PathDenied, convert_path_params

pytestmark = pytest.mark.unit

MAPPINGS = (Mapping(container="/data", host="C:/BIM"),)
ROOTS = ["C:/BIM"]


def _conv(params: dict[str, object]) -> dict[str, object]:
    return convert_path_params(params, ["ifc_a", "ifc_b"], MAPPINGS, ROOTS, lambda p: p)


def test_converts_and_keeps_others() -> None:
    src: dict[str, object] = {"ifc_a": "/data/depot/a.ifc", "n": 3}
    assert _conv(src) == {"ifc_a": "C:/BIM/depot/a.ifc", "n": 3}
    assert src["ifc_a"] == "/data/depot/a.ifc"


def test_list_converted() -> None:
    out = _conv({"ifc_b": ["/data/a.ifc", "/data/b.ifc"]})
    assert out["ifc_b"] == ["C:/BIM/a.ifc", "C:/BIM/b.ifc"]


def test_absent_key_ignored() -> None:
    assert _conv({"x": 1}) == {"x": 1}


def test_dotdot_denied() -> None:
    with pytest.raises(PathDenied):
        _conv({"ifc_a": "/data/../x"})


def test_outside_denied() -> None:
    with pytest.raises(PathDenied) as e:
        _conv({"ifc_a": "/autre/x"})
    assert e.value.code == "path_outside_roots"


@pytest.mark.parametrize("value", [3, ["a", 3]])
def test_wrong_type(value: object) -> None:
    with pytest.raises(PathDenied) as e:
        _conv({"ifc_a": value})
    assert e.value.code == "path_invalid"
    assert "ifc_a" in e.value.message


def test_mcp_env_var() -> None:
    assert mcp_env_var("demo-1", "Lang") == "DESKGATE_MCPENV__DEMO-1__LANG"
