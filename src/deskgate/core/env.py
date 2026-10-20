"""Environnement d'un sous-processus : liste blanche pure (règle 6)."""

from __future__ import annotations

from collections.abc import Mapping

ENV_ALLOWLIST: tuple[str, ...] = (
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "COMSPEC",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "COMPUTERNAME",
    "USERNAME",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "HOMEDRIVE",
    "HOMEPATH",
)


def build_env(base: Mapping[str, str], extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Construit l'environnement de l'enfant à partir de la liste blanche.

    Jamais `os.environ.copy()` : fuite de secrets et des variables DESKGATE_* (règle 6).
    `PYTHONUTF8=1` est posé en dernier : `extra` ne peut pas le retirer.
    """
    allowed = set(ENV_ALLOWLIST)
    env: dict[str, str] = {k.upper(): v for k, v in base.items() if k.upper() in allowed}
    if extra:
        env.update(extra)
    env["PYTHONUTF8"] = "1"
    return env
