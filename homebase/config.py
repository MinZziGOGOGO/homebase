"""Runtime configuration.

Settings are read from a JSON file (``config.json`` in the project root, or the
path in ``HOMEBASE_CONFIG``) and merged over the defaults below. Every optional
integration is disabled unless it is configured, so a fresh checkout runs with
just the core dashboard.
"""

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict = {
    # Weather widget location (any name wttr.in understands)
    "city": "Vienna",
    # Cards on the Services tab: [{"name", "url", "icon", "desc"}]
    "services": [],
    # Minecraft server to query, e.g. "localhost:25565" (null = card hidden)
    "minecraft_server": None,
    # Address shown by the "Copy IP" button (defaults to minecraft_server)
    "minecraft_public_address": None,
    # Show the Docker tab (needs the docker CLI on the host)
    "docker": True,
    # Directory of a shortform-ai checkout (null = Shorts tab hidden)
    "shortform_dir": None,
    # Base URL of a notification service exposing GET /notifications
    "notifications_url": None,
    # Unified search sources (each one is skipped when not configured)
    "search": {
        "mindbase_url": None,
        "wiki_url": None,
        "projects_dir": None,
        "shopping_list": None,
        "reminders_dir": None,
        "sessions_dir": None,
        "github_user": None,
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load() -> dict:
    path = Path(os.environ.get("HOMEBASE_CONFIG", PROJECT_ROOT / "config.json"))
    if not path.exists():
        return _merge(DEFAULTS, {})
    with open(path, encoding="utf-8") as f:
        return _merge(DEFAULTS, json.load(f))


def optional_path(value: str | None) -> Path | None:
    return Path(value).expanduser() if value else None


settings = load()
