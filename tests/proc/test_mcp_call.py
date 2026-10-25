"""mcp.call : appel, refus, erreur d'outil et secrets hors disque (Engine réel)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _support.jobs import get, run_until_terminal, submit
from _support.mcp_env import SECRET, mcp_config, mcp_engine
from deskgate import store

pytestmark = [pytest.mark.proc, pytest.mark.mcp]


def _run(
    tmp_path: Path,
    params: dict[str, object],
    *,
    allowed: tuple[str, ...] | None = None,
) -> tuple[store.JobRow, dict[str, object]]:
    cfg = mcp_config(tmp_path, allowed=allowed) if allowed else mcp_config(tmp_path)
    engine, db = mcp_engine(tmp_path, cfg)
    try:
        job_id = submit(db, cfg, "mcp.call", params)
        row = run_until_terminal(engine, db, job_id, timeout=45)
    finally:
        engine.stop()
    result = json.loads(row.result_json) if row.result_json else {}
    return get(db, job_id), result


def _texts(result: dict[str, object]) -> str:
    data = result["data"]
    assert isinstance(data, dict)
    return json.dumps(data, ensure_ascii=False)


@pytest.mark.timeout(60)
def test_echo(tmp_path: Path) -> None:
    row, result = _run(
        tmp_path, {"server": "mini", "tool": "echo", "arguments": {"text": "bonjour é"}}
    )
    assert row.status == "succeeded", row.error_message
    assert result["summary"] == {"server": "mini", "tool": "echo", "is_error": False}
    assert "bonjour é" in _texts(result)


@pytest.mark.timeout(60)
def test_add(tmp_path: Path) -> None:
    row, result = _run(tmp_path, {"server": "mini", "tool": "add", "arguments": {"a": 2, "b": 3}})
    assert row.status == "succeeded", row.error_message
    assert "5" in _texts(result)


@pytest.mark.timeout(90)
def test_reponse_volumineuse_marqueur_artefact(tmp_path: Path) -> None:
    row, result = _run(tmp_path, {"server": "mini", "tool": "big", "arguments": {"n": 950_000}})
    assert row.status == "succeeded", row.error_message
    assert result["data"] == {"truncated": True, "artifact": "mcp_result"}
    artifacts = result["artifacts"]
    assert isinstance(artifacts, list)
    arts = [a for a in artifacts if a["kind"] == "mcp_result"]
    assert len(arts) == 1
    assert arts[0]["path"].startswith("/data/")
    assert arts[0]["path"].endswith("/mcp-result.json")
    assert row.work_dir is not None
    contenu = json.loads((Path(row.work_dir) / "mcp-result.json").read_text(encoding="utf-8"))
    assert "structured_content" in contenu
    assert "content" in contenu


SEUIL = 900_000  # DATA_MAX_BYTES de workers/mcp_call.py, en octets UTF-8


@pytest.mark.timeout(120)
def test_reponse_multioctet_deportee(tmp_path: Path) -> None:
    """DS3-1 : « € » = 3 octets ; moins de caractères que le seuil, plus d'octets."""
    row, result = _run(
        tmp_path, {"server": "mini", "tool": "big", "arguments": {"n": 350_000, "char": "€"}}
    )
    assert row.status == "succeeded", (row.error_code, row.error_message)
    assert result["data"] == {"truncated": True, "artifact": "mcp_result"}
    artifacts = result["artifacts"]
    assert isinstance(artifacts, list)
    assert [a["kind"] for a in artifacts].count("mcp_result") == 1
    assert row.work_dir is not None
    contenu = json.loads((Path(row.work_dir) / "mcp-result.json").read_text(encoding="utf-8"))
    texte = json.dumps(contenu, ensure_ascii=False, allow_nan=False)
    assert len(texte) <= SEUIL < len(texte.encode("utf-8"))


@pytest.mark.timeout(90)
def test_reponse_multioctet_sous_seuil_en_ligne(tmp_path: Path) -> None:
    row, result = _run(
        tmp_path, {"server": "mini", "tool": "big", "arguments": {"n": 100_000, "char": "€"}}
    )
    assert row.status == "succeeded", (row.error_code, row.error_message)
    data = result["data"]
    assert isinstance(data, dict)
    assert "structured_content" in data and "content" in data
    assert "€" * 1000 in _texts(result)
    artifacts = result["artifacts"]
    assert isinstance(artifacts, list)
    assert all(a["kind"] != "mcp_result" for a in artifacts)


@pytest.mark.timeout(60)
def test_erreur_outil(tmp_path: Path) -> None:
    row, _ = _run(tmp_path, {"server": "mini", "tool": "erreur", "arguments": {}})
    assert row.status == "failed"
    assert row.error_code == "plugin_error"
    assert (row.error_message or "").startswith("tool_error : ")


@pytest.mark.timeout(60)
def test_serveur_non_declare(tmp_path: Path) -> None:
    row, _ = _run(tmp_path, {"server": "inconnu", "tool": "echo", "arguments": {}})
    assert row.status == "failed"
    assert (row.error_message or "").startswith("server_not_declared : ")


@pytest.mark.timeout(60)
def test_outil_non_autorise(tmp_path: Path) -> None:
    row, _ = _run(
        tmp_path,
        {"server": "mini", "tool": "sleep", "arguments": {"seconds": 1}},
        allowed=("echo",),
    )
    assert row.status == "failed"
    assert (row.error_message or "").startswith("tool_not_allowed : ")


@pytest.mark.timeout(60)
def test_arguments_invalides(tmp_path: Path) -> None:
    row, _ = _run(tmp_path, {"server": "mini", "tool": "echo", "arguments": "x"})
    assert row.status == "failed"
    assert (row.error_message or "").startswith("invalid_params : ")


@pytest.mark.timeout(60)
def test_env_atteint_serveur_sans_deskgate_ni_disque(tmp_path: Path) -> None:
    row, result = _run(
        tmp_path, {"server": "mini", "tool": "env", "arguments": {"names": ["MINI_SECRET"]}}
    )
    assert row.status == "succeeded", row.error_message
    text = _texts(result)
    assert "valeur-secrete-mcp-42" in text  # le serveur voit la valeur
    assert '\\"deskgate\\": []' in text or '"deskgate": []' in text
    # result.json porte la valeur renvoyée par l'outil (attendu) ; on contrôle le reste.
    work = Path(row.work_dir)
    leaks = [
        p
        for p in work.rglob("*")
        if p.is_file() and p.name != "result.json" and SECRET.encode() in p.read_bytes()
    ]
    assert not leaks, leaks
