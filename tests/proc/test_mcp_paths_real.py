"""mcp.call sur un vrai serveur MCP : refus de chemin, conversion /data, env du serveur visé."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from _support.jobs import CALLBACK_URL, get, run_until_terminal
from _support.mcp_env import MINI, SECRET, mcp_config, mcp_engine
from deskgate.core.config import RunnerConfig
from deskgate.core.jobspec import JobRequestError, SubmitRequest
from deskgate.jobs import JobsService

pytestmark = [pytest.mark.proc, pytest.mark.mcp]


def _submit(
    db: Path, cfg: RunnerConfig, tool: str, arguments: dict[str, object], server: str = "mini"
) -> str:
    req = SubmitRequest.model_validate(
        {
            "capability": "mcp.call",
            "params": {"server": server, "tool": tool, "arguments": arguments},
            "callback": {"url": CALLBACK_URL},
        }
    )
    return JobsService(db_path=db, config=cfg).submit(req)


def _text(row_result: str | None) -> str:
    assert row_result
    return json.dumps(json.loads(row_result)["data"], ensure_ascii=False)


@pytest.mark.timeout(60)
def test_chemin_data_converti_et_lu(tmp_path: Path) -> None:
    cfg = mcp_config(tmp_path)
    (tmp_path / "bim" / "depot").mkdir()
    (tmp_path / "bim" / "depot" / "a.txt").write_text("contenu-a", encoding="utf-8")
    engine, db = mcp_engine(tmp_path, cfg)
    try:
        job_id = _submit(db, cfg, "read_file", {"path": "/data/depot/a.txt"})
        row = run_until_terminal(engine, db, job_id, timeout=45)
    finally:
        engine.stop()
    assert row.status == "succeeded", row.error_message
    assert "contenu-a" in _text(row.result_json)


@pytest.mark.timeout(60)
def test_write_file_recoit_le_chemin_hote(tmp_path: Path) -> None:
    cfg = mcp_config(tmp_path)
    (tmp_path / "bim" / "livrables").mkdir()
    engine, db = mcp_engine(tmp_path, cfg)
    try:
        job_id = _submit(db, cfg, "write_file", {"path": "/data/livrables/b.txt"})
        row = run_until_terminal(engine, db, job_id, timeout=45)
    finally:
        engine.stop()
    assert row.status == "succeeded", row.error_message
    assert (tmp_path / "bim" / "livrables" / "b.txt").is_file()
    text = _text(row.result_json)
    assert "/data" not in text
    assert "livrables" in text
    assert str(tmp_path.name) in text


@pytest.mark.timeout(60)
def test_dotdot_refuse_a_la_soumission(tmp_path: Path) -> None:
    cfg = mcp_config(tmp_path)
    _, db = mcp_engine(tmp_path, cfg)
    with pytest.raises(JobRequestError) as e:
        _submit(db, cfg, "read_file", {"path": "/data/../hors.txt"})
    assert (e.value.status, e.value.code) == (422, "path_outside_roots")


@pytest.mark.timeout(60)
def test_jonction_refusee_a_la_soumission(
    tmp_path: Path, junction: Callable[[Path, Path], Path]
) -> None:
    cfg = mcp_config(tmp_path)
    _, db = mcp_engine(tmp_path, cfg)
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (dehors / "secret.txt").write_text("secret", encoding="utf-8")
    junction(tmp_path / "bim" / "lien", dehors)
    with pytest.raises(JobRequestError) as e:
        _submit(db, cfg, "read_file", {"path": "/data/lien/secret.txt"})
    assert (e.value.status, e.value.code) == (422, "path_outside_roots")


@pytest.mark.timeout(60)
def test_lien_refuse_a_la_soumission(tmp_path: Path, symlink_ok: bool) -> None:
    cfg = mcp_config(tmp_path)
    _, db = mcp_engine(tmp_path, cfg)
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (dehors / "secret.txt").write_text("secret", encoding="utf-8")
    lien = tmp_path / "bim" / "slien"
    os.symlink(dehors, lien, target_is_directory=True)
    try:
        with pytest.raises(JobRequestError) as e:
            _submit(db, cfg, "read_file", {"path": "/data/slien/secret.txt"})
    finally:
        os.rmdir(lien)
    assert (e.value.status, e.value.code) == (422, "path_outside_roots")


@pytest.mark.timeout(60)
def test_jonction_modifiee_avant_lancement(
    tmp_path: Path, junction: Callable[[Path, Path], Path]
) -> None:
    cfg = mcp_config(tmp_path)
    engine, db = mcp_engine(tmp_path, cfg)
    dedans = tmp_path / "bim" / "dedans"
    dedans.mkdir()
    (dedans / "secret.txt").write_text("interne", encoding="utf-8")
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (dehors / "secret.txt").write_text("externe-interdit", encoding="utf-8")
    lien = tmp_path / "bim" / "lien"
    junction(lien, dedans)
    try:
        job_id = _submit(db, cfg, "read_file", {"path": "/data/lien/secret.txt"})
        os.rmdir(lien)
        junction(lien, dehors)
        row = run_until_terminal(engine, db, job_id, timeout=45)
    finally:
        engine.stop()
    assert row.status == "failed"
    assert row.error_code == "path_outside_roots"
    assert "externe-interdit" not in (row.result_json or "")
    result = Path(row.work_dir) / "result.json"
    assert not result.exists() or "externe-interdit" not in result.read_text(encoding="utf-8")
    assert get(db, job_id).status == "failed"


@pytest.mark.timeout(60)
def test_env_serveur_vise_avec_deux_serveurs(tmp_path: Path) -> None:
    def server(var: str, value: str) -> dict[str, object]:
        return {
            "command": sys.executable.replace("\\", "/"),
            "args": [str(MINI).replace("\\", "/")],
            "env": {var: value},
            "allowed_tools": ["env"],
        }

    cfg = mcp_config(
        tmp_path,
        servers={
            "mini": server("MINI_SECRET", SECRET),
            "autre": server("AUTRE_SECRET", "valeur-autre-77"),
        },
    )
    engine, db = mcp_engine(tmp_path, cfg)
    try:
        job_id = _submit(db, cfg, "env", {"names": ["MINI_SECRET", "AUTRE_SECRET"]})
        row = run_until_terminal(engine, db, job_id, timeout=45)
    finally:
        engine.stop()
    assert row.status == "succeeded", row.error_message
    data = json.loads(row.result_json or "{}")["data"]
    values = data["structured_content"]["values"]
    assert values["MINI_SECRET"] == SECRET
    assert values["AUTRE_SECRET"] is None
    for p in Path(row.work_dir).rglob("*"):
        if p.is_file():
            assert b"valeur-autre-77" not in p.read_bytes(), p
