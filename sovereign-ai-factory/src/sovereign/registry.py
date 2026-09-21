from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import CapabilityConfig


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    name: str
    category: str
    discovery: tuple[str, ...] = ()
    authorization: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "CapabilitySpec":
        name = str(value.get("id", "")).strip()
        if not name:
            raise ValueError("Capability entries require a non-empty id")
        raw_discovery = value.get("discovery", ())
        if isinstance(raw_discovery, str):
            raw_discovery = (raw_discovery,)
        if not isinstance(raw_discovery, (list, tuple)):
            raise ValueError(f"Capability '{name}' discovery must be a list")
        known = {"id", "category", "discovery", "authorization"}
        metadata = {key: item for key, item in value.items() if key not in known}
        return cls(
            name=name,
            category=str(value.get("category", "general")),
            discovery=tuple(str(item) for item in raw_discovery),
            authorization=value.get("authorization"),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    name: str
    capability: str
    implementation: Callable[..., Any]
    required_permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self.implementation(*args, **kwargs)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilitySpec] = {}
        self._adapters: dict[str, list[AdapterSpec]] = {}

    @classmethod
    def from_config(cls, config: CapabilityConfig) -> "CapabilityRegistry":
        registry = cls()
        for raw in config.capabilities:
            registry.register_capability(CapabilitySpec.from_mapping(raw))
        return registry

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CapabilityRegistry":
        return cls.from_config(CapabilityConfig.load(path))

    def register_capability(self, spec: CapabilitySpec, *, replace: bool = False) -> None:
        if spec.name in self._capabilities and not replace:
            return
        self._capabilities[spec.name] = spec
        self._adapters.setdefault(spec.name, [])

    def register_discovered_capability(self, spec: CapabilitySpec) -> None:
        self.register_capability(spec, replace=True)

    def register_adapter(self, adapter: AdapterSpec) -> None:
        if adapter.capability not in self._capabilities:
            self.register_discovered_capability(
                CapabilitySpec(
                    name=adapter.capability,
                    category="dynamic",
                    discovery=("adapter",),
                    metadata={"auto_registered": True},
                )
            )
        adapters = self._adapters.setdefault(adapter.capability, [])
        if not any(existing.name == adapter.name for existing in adapters):
            adapters.append(adapter)

    def capability(self, name: str) -> CapabilitySpec | None:
        return self._capabilities.get(name)

    def adapters_for(self, capability_name: str) -> list[AdapterSpec]:
        return list(self._adapters.get(capability_name, ()))

    def registered_capabilities(self) -> list[str]:
        return sorted(self._capabilities)

    def resolve(self, capability_name: str) -> list[AdapterSpec]:
        return sorted(
            self.adapters_for(capability_name),
            key=lambda adapter: (len(adapter.required_permissions), adapter.name),
        )


def load_registry(path: str | Path) -> CapabilityRegistry:
    """Load capabilities from the operator-controlled YAML configuration."""
    return CapabilityRegistry.from_yaml(path)
