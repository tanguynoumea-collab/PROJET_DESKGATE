"""Politique de licences par environnement (dev, bim, bcf) : copyleft fort seulement dans bcf."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from _support.plugin_envs import REPO, run_json

Row = dict[str, Any]

PROBE = Path(__file__).with_name("licenses_probe.py")
NOTICE = REPO / "plugins" / "bim" / "bcf" / "NOTICE"
STRONG = re.compile(r"\b(A?GPL)\b|GNU (General|Affero) Public License", re.I)
ALLOWED_GPL = {"bcf": {"bcf-client", "deskgate-bcf"}}


def strong_copyleft(row: Row) -> bool:
    text = " ".join([row["expr"], row["license"], *row["classifiers"]])
    return bool(STRONG.search(text)) and "Lesser" not in text and "LGPL" not in text


@pytest.fixture(scope="module")
def inventaires(plugin_envs: dict[str, Path]) -> dict[str, list[Row]]:
    return {
        "dev": cast(list[Row], run_json(Path(sys.executable), PROBE)),
        "bim": cast(list[Row], run_json(plugin_envs["bim"], PROBE)),
        "bcf": cast(list[Row], run_json(plugin_envs["bcf"], PROBE)),
    }


@pytest.mark.bim
@pytest.mark.parametrize("env", ["dev", "bim", "bcf"])
def test_aucun_copyleft_fort_hors_liste(env: str, inventaires: dict[str, list[Row]]) -> None:
    fort = {r["name"].lower() for r in inventaires[env] if strong_copyleft(r)}
    assert fort <= ALLOWED_GPL.get(env, set()), fort


@pytest.mark.bim
def test_bcf_client_absent_hors_env_bcf(inventaires: dict[str, list[Row]]) -> None:
    for env in ("dev", "bim"):
        noms = {r["name"].lower() for r in inventaires[env]}
        assert not noms & {"bcf-client", "deskgate-bcf"}, env


@pytest.mark.bim
def test_sonde_voit_bcf_client(inventaires: dict[str, list[Row]]) -> None:
    rows = [r for r in inventaires["bcf"] if r["name"].lower() == "bcf-client"]
    assert rows
    assert strong_copyleft(rows[0])


@pytest.mark.bim
def test_notice_cite_version(inventaires: dict[str, list[Row]]) -> None:
    version = next(r["version"] for r in inventaires["bcf"] if r["name"].lower() == "bcf-client")
    texte = NOTICE.read_text(encoding="utf-8")
    assert "bcf-client" in texte
    assert version in texte


@pytest.mark.unit
@pytest.mark.parametrize(
    ("row", "attendu"),
    [
        ({"expr": "GPL-3.0-or-later", "license": "", "classifiers": []}, True),
        (
            {"expr": "", "license": "", "classifiers": ["GNU General Public License v3 (GPLv3)"]},
            True,
        ),
        ({"expr": "LGPL-3.0-or-later", "license": "", "classifiers": []}, False),
        (
            {
                "expr": "",
                "license": "",
                "classifiers": ["GNU Lesser General Public License v3 or later (LGPLv3+)"],
            },
            False,
        ),
        ({"expr": "MIT", "license": "", "classifiers": []}, False),
    ],
)
def test_politique_regex(row: Row, attendu: bool) -> None:
    assert strong_copyleft(row) is attendu
