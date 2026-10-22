"""Les exemples de la phase 4 du gabarit runner.example.toml sont du TOML valide."""

from __future__ import annotations

from importlib import resources

import pytest

from deskgate.core.config import parse_config

pytestmark = pytest.mark.unit

START = "# >>> exemples phase 4"
END = "# <<< exemples phase 4"


def _split() -> tuple[str, list[str]]:
    text = (resources.files("deskgate") / "runner.example.toml").read_text(encoding="utf-8")
    head, _, rest = text.partition(START)
    block, _, _ = rest.partition(END)
    assert block, "bloc d'exemples absent"
    return head, block.splitlines()


def _activate(lines: list[str]) -> str:
    out: list[str] = []
    for line in lines:
        if line.startswith("# #"):  # commentaire explicatif : reste un commentaire
            out.append(line[2:])
        elif line == "#":
            out.append("")
        elif line.startswith("# "):
            out.append(line[2:])
    return "\n".join(out)


def test_exemples_phase_4_valides() -> None:
    head, block = _split()
    cfg = parse_config(head + "\n" + _activate(block), "runner.example.toml")
    clash = cfg.capabilities["ifc.clash"]
    assert clash.kind == "python"
    assert clash.path_params == ["ifc_a", "ifc_b"]
    assert clash.required_files == ["bcf_executable"]
    assert str(clash.settings["bcf_executable"]).endswith("deskgate-bcf.exe")
    assert cfg.capabilities["mcp.call"].kind == "mcp"
    assert "demo" in cfg.mcp_servers
