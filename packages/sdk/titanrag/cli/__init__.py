"""TitanRAG Developer CLI."""

from typing import Any


def get_app() -> Any:
    from titanrag.cli.main import app

    return app


__all__ = ["get_app"]
