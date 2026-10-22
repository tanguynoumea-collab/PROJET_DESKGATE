"""Capacités : settings, path_params, kind mcp, serveurs MCP."""

from __future__ import annotations

import pytest

from deskgate.core.config import ConfigError, RunnerConfig, parse_config

pytestmark = pytest.mark.unit

HEAD = f"""token_sha256 = "{"a" * 64}"
[paths]
allowed_roots = ['C:/BIM']
"""


def _parse(extra: str) -> RunnerConfig:
    return parse_config(HEAD + extra, "t.toml")


def test_python_requires_fields() -> None:
    with pytest.raises(ConfigError) as e:
        _parse("[capabilities.x]\nkind = 'python'\ntimeout_max = 10\n")
    assert "capabilities.x" in str(e.value)
    assert "exige python et entry" in str(e.value)


def test_mcp_forbids_python() -> None:
    with pytest.raises(ConfigError) as e:
        _parse("[capabilities.x]\nkind = 'mcp'\ntimeout_max = 10\npython = 'C:/p.exe'\n")
    assert "n'accepte ni python" in str(e.value)


def test_mcp_minimal() -> None:
    cap = _parse("[capabilities.x]\nkind = 'mcp'\ntimeout_max = 600\n").capabilities["x"]
    assert cap.python is None
    assert cap.entry is None


def test_settings_types_preserved() -> None:
    cfg = _parse(
        "[capabilities.x]\nkind='python'\npython='C:/p.exe'\nentry='m:f'\ntimeout_max=5\n"
        "settings = { bcf_executable = 'C:/x/deskgate-bcf.exe', threads = 4, ratio = 0.5, "
        'actif = true, noms = ["a", "b"] }\n'
    )
    s = cfg.capabilities["x"].settings
    assert s["threads"] == 4
    assert isinstance(s["threads"], int)
    assert s["ratio"] == 0.5
    assert s["actif"] is True
    assert s["noms"] == ["a", "b"]


def test_nested_settings_rejected() -> None:
    with pytest.raises(ConfigError):
        _parse(
            "[capabilities.x]\nkind='python'\npython='C:/p.exe'\nentry='m:f'\ntimeout_max=5\n"
            "settings = { t = { u = 1 } }\n"
        )


def test_path_params() -> None:
    base = "[capabilities.x]\nkind='python'\npython='C:/p.exe'\nentry='m:f'\ntimeout_max=5\n"
    assert _parse(base + 'path_params = ["ifc_a", "ifc_b"]\n').capabilities["x"].path_params == [
        "ifc_a",
        "ifc_b",
    ]
    with pytest.raises(ConfigError) as e:
        _parse(base + 'path_params = ["1x"]\n')
    assert "format invalide" in str(e.value)


def test_mcp_server_valid() -> None:
    cfg = _parse(
        "[mcp_servers.demo]\ncommand = 'C:/Python/python.exe'\nargs = [\"s.py\"]\n"
        'env = { LANG = "fr" }\nallowed_tools = ["echo"]\n'
    )
    assert cfg.mcp_servers["demo"].allowed_tools == ["echo"]


def test_mcp_server_relative_command() -> None:
    with pytest.raises(ConfigError):
        _parse("[mcp_servers.demo]\ncommand = 'python'\n")


def test_mcp_server_bad_name() -> None:
    with pytest.raises(ConfigError):
        _parse("[mcp_servers.\"a b\"]\ncommand = 'C:/p.exe'\n")


def test_mcp_env_secret_not_leaked() -> None:
    with pytest.raises(ConfigError) as e:
        _parse('[mcp_servers.demo]\ncommand = \'C:/p.exe\'\nenv = { "1BAD" = "VALEUR-SECRETE" }\n')
    assert "VALEUR-SECRETE" not in str(e.value)


_PY = "[capabilities.x]\nkind='python'\npython='C:/p.exe'\nentry='m:f'\ntimeout_max=5\n"


def test_required_files_valide() -> None:
    cfg = _parse(_PY + 'required_files = ["outil"]\nsettings = { outil = \'C:/x.exe\' }\n')
    assert cfg.capabilities["x"].required_files == ["outil"]


def test_required_files_cle_absente() -> None:
    with pytest.raises(ConfigError) as e:
        _parse(_PY + 'required_files = ["outil"]\n')
    assert "required_files" in str(e.value)


@pytest.mark.parametrize("valeur", ["3", "''"])
def test_required_files_valeur_non_chaine(valeur: str) -> None:
    with pytest.raises(ConfigError) as e:
        _parse(_PY + f'required_files = ["outil"]\nsettings = {{ outil = {valeur} }}\n')
    assert "required_files" in str(e.value)


def test_required_files_interdit_pour_mcp() -> None:
    with pytest.raises(ConfigError) as e:
        _parse("[capabilities.x]\nkind='mcp'\ntimeout_max=5\nrequired_files = ['x']\n")
    assert "ni required_files" in str(e.value)


def test_required_files_nom_invalide() -> None:
    with pytest.raises(ConfigError):
        _parse(_PY + 'required_files = ["a-b"]\n')


_SRV = "[mcp_servers.srv]\ncommand = 'C:/p.exe'\n"


def test_path_arguments_valide() -> None:
    cfg = _parse(
        _SRV + 'allowed_tools = ["read_file", "fs.write-v2"]\n'
        'path_arguments = { read_file = ["path"], "fs.write-v2" = ["path", "dest"] }\n'
    )
    assert cfg.mcp_servers["srv"].path_arguments["fs.write-v2"] == ["path", "dest"]


def test_path_arguments_outil_non_autorise() -> None:
    with pytest.raises(ConfigError) as e:
        _parse(_SRV + 'allowed_tools = ["echo"]\npath_arguments = { read_file = ["path"] }\n')
    assert "path_arguments" in str(e.value)


def test_path_arguments_liste_vide() -> None:
    with pytest.raises(ConfigError):
        _parse(_SRV + 'allowed_tools = ["read_file"]\npath_arguments = { read_file = [] }\n')


def test_path_arguments_nom_argument_invalide() -> None:
    with pytest.raises(ConfigError):
        _parse(
            _SRV + 'allowed_tools = ["read_file"]\npath_arguments = { read_file = ["a-b"] }\n'
        )


def test_mcp_path_arguments() -> None:
    cfg = _parse(
        _SRV + 'allowed_tools = ["read_file"]\npath_arguments = { read_file = ["path"] }\n'
    )
    assert cfg.mcp_path_arguments() == {"srv": {"read_file": ["path"]}}
