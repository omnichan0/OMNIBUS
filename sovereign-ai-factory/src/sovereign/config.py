from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required for capability configuration loading.") from exc


@dataclass(slots=True)
class CapabilityConfig:
    path: Path
    capabilities: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "CapabilityConfig":
        cfg_path = Path(path)
        if not cfg_path.exists():
            raise FileNotFoundError(f"Capability config not found: {cfg_path}")
        with cfg_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        capabilities = payload.get("capabilities", [])
        return cls(path=cfg_path, capabilities=capabilities)


def load_capability_registry(path: str | Path) -> CapabilityConfig:
    return CapabilityConfig.load(path)
