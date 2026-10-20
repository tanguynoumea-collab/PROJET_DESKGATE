"""Point d'entrée `python -m deskgate` (évite le lanceur de venv)."""

from deskgate.cli import app

if __name__ == "__main__":
    app()
