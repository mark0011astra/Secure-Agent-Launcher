from __future__ import annotations

import json
from pathlib import Path

APP_NAME = "agent-locker"
DEFAULT_DENY_PATHS = [
    "~/.ssh",
    "~/.aws",
    "~/.gnupg",
    "~/Library/Keychains",
]


def default_policy_data() -> dict[str, object]:
    return {
        "enabled": True,
        "deny_paths": DEFAULT_DENY_PATHS.copy(),
    }


def default_policy_path() -> Path:
    return Path.home() / ".config" / APP_NAME / "policy.json"


def default_audit_log_path() -> Path:
    return Path.home() / ".local" / "state" / APP_NAME / "audit.log"


def write_default_policy(path: Path, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        if path.stat().st_size > 0:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(default_policy_data(), indent=2) + "\n", encoding="utf-8")
