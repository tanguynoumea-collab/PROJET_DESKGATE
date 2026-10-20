"""Table d'attaques lexicales : aucune ligne ne doit atteindre le resolver."""

from __future__ import annotations

import pytest

from deskgate.core.paths import Mapping, PathDenied, resolve_within_roots, validate_container_path

pytestmark = pytest.mark.unit

OUT = "path_outside_roots"
INV = "path_invalid"

MAPPINGS = [Mapping("/data", "C:/BIM")]
ROOTS = ["C:/BIM"]

CONTAINER_ATTACKS: list[tuple[str, str]] = [
    ("/data/../Windows", OUT),
    ("/data/x/../../y", OUT),
    ("\\\\srv\\share\\x", OUT),
    ("//srv/share", OUT),
    ("\\\\?\\C:\\BIM\\x", OUT),
    ("\\\\.\\C:\\Windows", OUT),
    ("\\\\?\\UNC\\srv\\x", OUT),
    ("/data/CON", INV),
    ("/data/nul.txt", INV),
    ("/data/COM1", INV),
    ("/data/com\u00b9.txt", INV),
    ("/data/LPT9", INV),
    ("/data/CONIN$", INV),
    ("/data/CONOUT$", INV),
    ("/data/aux .txt", INV),
    ("/data/f.txt:stream", INV),
    ("/data/f.txt::$DATA", INV),
    ("/data/sub.", INV),
    ("/data/sub ", INV),
    ("/data/a\x00b", INV),
    ("/data/a\x1fb", INV),
    ("/data/a?b", INV),
    ("/data/a<b", INV),
    ("/data/a|b", INV),
    ("/data//x", INV),
    ("/data/./x", INV),
    ("", INV),
    ("data/x", INV),
    ("C:/BIM/x", INV),
    ("/data2/x", OUT),
    ("/datax/x", OUT),
    ("/other/x", OUT),
]

HOST_ATTACKS: list[tuple[str, str]] = [
    ("C:foo", INV),
    ("C:/BIM2/x", OUT),
    ("C:/BIM/../x", OUT),
    ("D:/x", OUT),
    ("C:/BIM/f.txt::$DATA", INV),
    ("C:/BIM/CON", INV),
    ("\\\\srv\\share\\x", OUT),
]


def _resolver_interdit(_p: str) -> str:
    raise AssertionError("ne doit pas être appelé")


def _verifie(exc: PathDenied, code: str) -> None:
    assert exc.code == code
    assert exc.message
    assert "error" not in exc.message.lower()


@pytest.mark.parametrize(
    "raw, code", CONTAINER_ATTACKS, ids=[repr(r) for r, _ in CONTAINER_ATTACKS]
)
def test_attaque_conteneur(raw: str, code: str) -> None:
    with pytest.raises(PathDenied) as info:
        validate_container_path(raw, MAPPINGS, ROOTS, _resolver_interdit)
    _verifie(info.value, code)


@pytest.mark.parametrize("raw, code", HOST_ATTACKS, ids=[repr(r) for r, _ in HOST_ATTACKS])
def test_attaque_hote(raw: str, code: str) -> None:
    with pytest.raises(PathDenied) as info:
        resolve_within_roots(raw, ROOTS, _resolver_interdit)
    _verifie(info.value, code)


def test_non_str_refuse() -> None:
    with pytest.raises(PathDenied) as info:
        validate_container_path(None, MAPPINGS, ROOTS, _resolver_interdit)  # type: ignore[arg-type]
    _verifie(info.value, INV)
