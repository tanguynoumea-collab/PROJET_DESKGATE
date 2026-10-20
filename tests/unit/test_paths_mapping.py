"""Conversion conteneur/hôte par segments et résolution avec resolver factice."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from deskgate.core.paths import (
    Mapping,
    PathDenied,
    container_to_host,
    host_to_container,
    is_under,
    resolve_within_roots,
    validate_artifact_path,
    validate_container_path,
)

pytestmark = pytest.mark.unit

M = [Mapping("/data", "C:/BIM")]
ROOTS = ["C:/BIM"]


def _resolver(table: dict[str, str]) -> Callable[[str], str]:
    return lambda p: table.get(p, p)


def test_aller() -> None:
    assert container_to_host("/data/x/y.ifc", M) == "C:/BIM/x/y.ifc"
    assert container_to_host("/data", M) == "C:/BIM"
    assert container_to_host("/data/", M) == "C:/BIM"


def test_retour() -> None:
    assert host_to_container("C:/BIM/x/y.ifc", M) == "/data/x/y.ifc"
    assert host_to_container("c:\\bim\\X\\y.ifc", M) == "/data/X/y.ifc"
    assert host_to_container("C:/BIM", M) == "/data"


@pytest.mark.parametrize("raw", ["/data2/x", "/datax/x", "/other/x"])
def test_conteneur_hors_mapping(raw: str) -> None:
    with pytest.raises(PathDenied) as info:
        container_to_host(raw, M)
    assert info.value.code == "path_outside_roots"


def test_hote_frere_refuse() -> None:
    with pytest.raises(PathDenied) as info:
        host_to_container("C:/BIM2/x", M)
    assert info.value.code == "path_outside_roots"


def test_is_under() -> None:
    assert not is_under("C:/BIM2/x", "C:/BIM")
    assert is_under("C:/BIM", "c:/bim")
    assert is_under("c:/bim/X/y", "C:/BIM")


def test_prefixe_win32_retire() -> None:
    r = _resolver({"C:/BIM/x": "\\\\?\\C:\\BIM\\x"})
    assert resolve_within_roots("C:/BIM/x", ROOTS, r) == "C:/BIM/x"


def test_resolu_hors_racine() -> None:
    r = _resolver({"C:/BIM/x": "D:\\outside\\x"})
    with pytest.raises(PathDenied) as info:
        resolve_within_roots("C:/BIM/x", ROOTS, r)
    assert info.value.code == "path_outside_roots"


@pytest.mark.parametrize("cible", ["\\\\srv\\share\\x", "\\\\?\\UNC\\srv\\share\\x"])
def test_resolu_unc(cible: str) -> None:
    r = _resolver({"C:/BIM/x": cible})
    with pytest.raises(PathDenied) as info:
        resolve_within_roots("C:/BIM/x", ROOTS, r)
    assert info.value.code == "path_outside_roots"


def test_racine_jonction() -> None:
    r = _resolver({"C:/BIM": "E:/real/BIM", "C:/BIM/x": "E:/real/BIM/x"})
    assert resolve_within_roots("C:/BIM/x", ROOTS, r) == "E:/real/BIM/x"
    assert validate_container_path("/data/x", M, ROOTS, r) == "E:/real/BIM/x"


def test_artefact() -> None:
    assert validate_artifact_path("C:/BIM/out/a.json", M, ROOTS, _resolver({})) == "/data/out/a.json"
    with pytest.raises(PathDenied):
        validate_artifact_path("D:/out/a.json", M, ROOTS, _resolver({}))
