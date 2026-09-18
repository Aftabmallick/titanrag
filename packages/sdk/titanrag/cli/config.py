from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from titanrag.sync_client import TitanClient

CONFIG_DIR = Path.home() / ".titan"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_config_path() -> Path:
    return CONFIG_FILE


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return cast(dict[str, Any], json.load(f))
    except Exception:
        return {}


def save_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Enforce strict 0600 permissions on Unix systems for security
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def get_active_client(
    override_base_url: str | None = None,
    override_api_key: str | None = None,
) -> TitanClient:
    cfg = load_config()
    base_url = override_base_url or cfg.get("base_url") or os.getenv("TITANRAG_BASE_URL", "http://localhost:8000")
    api_key = override_api_key or cfg.get("api_key") or os.getenv("TITANRAG_API_KEY")

    return TitanClient(
        base_url=base_url,
        api_key=api_key,
        token=cfg.get("token"),
    )


def get_active_workspace_id(override_workspace_id: str | None = None) -> str | None:
    if override_workspace_id:
        return override_workspace_id
    cfg = load_config()
    return cfg.get("active_workspace_id")
