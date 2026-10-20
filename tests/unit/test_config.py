"""Configuration runner.toml : valeurs par défaut, refus clairs, aucune fuite de valeur."""

from __future__ import annotations

from pathlib import Path

import pytest

from deskgate.core.config import ConfigError, load_config, parse_config

pytestmark = pytest.mark.unit

TOKEN = "a" * 64

BASE = f"""
token_sha256 = "{TOKEN}"
[paths]
allowed_roots = ['C:/BIM']
[[paths.mapping]]
container = "/data"
host = "C:/BIM"
"""


def _with(extra_root: str = "", extra_tail: str = "") -> str:
    return f"{extra_root}\n{BASE}\n{extra_tail}"


def _err(text: str) -> str:
    with pytest.raises(ConfigError) as info:
        parse_config(text, "test.toml")
    return info.value.message


def test_minimal_defaults() -> None:
    cfg = parse_config(BASE, "test.toml")
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8765
    assert cfg.allow_non_loopback is False
    assert cfg.listen_warnings() == ()
    assert cfg.mappings()[0].container == "/data"
    assert cfg.mappings()[0].host == "C:/BIM"


def test_loopback_refused_without_option() -> None:
    msg = _err(f'host = "192.168.1.10"\n{BASE}')
    assert "host" in msg
    assert "allow_non_loopback" in msg


def test_loopback_allowed_with_option_warns() -> None:
    cfg = parse_config(f'allow_non_loopback = true\nhost = "192.168.1.10"\n{BASE}', "t")
    assert cfg.listen_warnings() == ("listen_non_loopback",)


@pytest.mark.parametrize("host", ["localhost", "::1"])
def test_loopback_host_must_be_ipv4_literal(host: str) -> None:
    msg = _err(f'host = "{host}"\n{BASE}')
    assert "host" in msg
    assert "IPv4" in msg


@pytest.mark.parametrize("port", ["0", "70000", '"abc"'])
def test_port_invalid(port: str) -> None:
    assert "port" in _err(f"port = {port}\n{BASE}")


def test_unknown_root_key() -> None:
    msg = _err(f"bogus = 1\n{BASE}")
    assert "bogus" in msg
    assert "clé inconnue" in msg


def test_unknown_nested_mapping_key() -> None:
    text = BASE.replace('host = "C:/BIM"', 'host = "C:/BIM"\nprot = 1')
    assert "paths.mapping.0.prot" in _err(text)


def test_unknown_capability_key() -> None:
    cap = (
        "[capabilities.fake]\n"
        'kind = "python"\npython = "C:/venv/python.exe"\nentry = "pkg.mod"\n'
        "timeout_max = 600\nbogus = 1\n"
    )
    assert "capabilities.fake.bogus" in _err(BASE + cap)


def test_token_missing() -> None:
    text = BASE.replace(f'token_sha256 = "{TOKEN}"', "")
    msg = _err(text)
    assert "token_sha256" in msg
    assert "clé obligatoire absente" in msg


def test_token_malformed_not_leaked() -> None:
    msg = _err(BASE.replace(TOKEN, "SECRETVALUE"))
    assert "token_sha256" in msg
    assert "SECRETVALUE" not in msg


def test_toml_syntax_error() -> None:
    msg = _err("port = ")
    assert "illisible" in msg
    assert "ligne" in msg


@pytest.mark.parametrize("root", ["'\\\\srv\\share'", "'C:foo'"])
def test_allowed_roots_invalid(root: str) -> None:
    text = BASE.replace("['C:/BIM']", f"[{root}]")
    assert "paths.allowed_roots.0" in _err(text)


def test_mapping_outside_roots() -> None:
    msg = _err(BASE.replace('host = "C:/BIM"', 'host = "D:/ailleurs"'))
    assert "paths.mapping" in msg
    assert "racine" in msg


def test_mapping_container_needs_slash() -> None:
    msg = _err(BASE.replace('container = "/data"', 'container = "data"'))
    assert "paths.mapping.0.container" in msg


def test_capability_valid() -> None:
    cap = (
        "[capabilities.fake]\n"
        'kind = "python"\npython = "C:/venv/python.exe"\nentry = "pkg.mod"\ntimeout_max = 600\n'
    )
    cfg = parse_config(BASE + cap, "t")
    assert cfg.capabilities["fake"].timeout_max == 600
    assert cfg.capabilities["fake"].resource == "default"


@pytest.mark.parametrize(("key", "value"), [("timeout_max", "0"), ("kind", '"shell"')])
def test_capability_invalid(key: str, value: str) -> None:
    fields = {
        "kind": '"python"',
        "python": '"C:/venv/python.exe"',
        "entry": '"pkg.mod"',
        "timeout_max": "600",
        key: value,
    }
    cap = "[capabilities.fake]\n" + "".join(f"{k} = {v}\n" for k, v in fields.items())
    assert f"capabilities.fake.{key}" in _err(BASE + cap)


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as info:
        load_config(tmp_path / "absent.toml")
    assert "introuvable" in info.value.message


def test_load_config_not_utf8(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ConfigError) as info:
        load_config(p)
    assert "UTF-8" in info.value.message


def test_load_config_ok(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_text(BASE, encoding="utf-8")
    assert load_config(p).port == 8765
