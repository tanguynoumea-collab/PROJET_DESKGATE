"""Deskgate : passerelle locale entre n8n et les outils lourds d'un PC Windows."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("deskgate")
except PackageNotFoundError:  # paquet non installé (exécution depuis les sources)
    __version__ = "0.0.0"

__all__ = ["__version__"]
