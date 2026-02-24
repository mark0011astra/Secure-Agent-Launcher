from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class PolicyError(Exception):
    pass


def normalize_path(path: str | Path, base_dir: Path | None = None) -> Path:
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        root = base_dir if base_dir is not None else Path.cwd()
        raw = root / raw
    return raw.resolve(strict=False)


def is_subpath(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class Policy:
    enabled: bool
    deny_paths: tuple[Path, ...]

    @classmethod
    def from_dict(cls, data: dict, base_dir: Path | None = None) -> "Policy":
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            raise PolicyError("'enabled' must be a boolean")
        deny_values = data.get("deny_paths")
        if not isinstance(deny_values, list):
            raise PolicyError("'deny_paths' must be a list")
        deny_paths_list: list[Path] = []
        for value in deny_values:
            if not isinstance(value, (str, Path)):
                raise PolicyError("'deny_paths' entries must be strings")
            deny_paths_list.append(normalize_path(value, base_dir=base_dir))
        deny_paths = tuple(deny_paths_list)
        return cls(enabled=enabled, deny_paths=deny_paths)

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "deny_paths": [str(p) for p in self.deny_paths],
        }

    def is_denied(self, target: str | Path, base_dir: Path | None = None) -> bool:
        if not self.enabled:
            return False
        normalized = normalize_path(target, base_dir=base_dir)
        return any(is_subpath(normalized, deny) for deny in self.deny_paths)


def load_policy(path: Path) -> Policy:
    if not path.exists():
        raise PolicyError(f"Policy file was not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PolicyError("Policy file must contain a JSON object")
    return Policy.from_dict(raw)


def save_policy(path: Path, policy: Policy) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy.to_dict(), indent=2) + "\n", encoding="utf-8")
