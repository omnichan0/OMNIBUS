from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    name: str
    category: str
    discovery: tuple[str, ...] = ()
    authorization: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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

    def register_capability(self, spec: CapabilitySpec) -> None:
        self._capabilities[spec.name] = spec
        self._adapters.setdefault(spec.name, [])

    def register_adapter(self, adapter: AdapterSpec) -> None:
        if adapter.capability not in self._capabilities:
            self.register_capability(
                CapabilitySpec(
                    name=adapter.capability,
                    category="dynamic",
                    discovery=("registry",),
                    metadata={"auto_registered": True},
                )
            )
        self._adapters.setdefault(adapter.capability, []).append(adapter)

    def capability(self, name: str) -> CapabilitySpec | None:
        return self._capabilities.get(name)

    def adapters_for(self, capability_name: str) -> list[AdapterSpec]:
        return list(self._adapters.get(capability_name, ()))

    def registered_capabilities(self) -> list[str]:
        return sorted(self._capabilities)

    def resolve(self, capability_name: str) -> list[AdapterSpec]:
        adapters = self.adapters_for(capability_name)
        if not adapters:
            return []
        return sorted(adapters, key=lambda a: (len(a.required_permissions), a.name))


def default_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register_capability(
        CapabilitySpec(
            name="reasoning",
            category="model",
            discovery=("local_model", "huggingface", "openai_compatible"),
            authorization="internal",
            metadata={"default_model": "reasoning"},
        )
    )
    registry.register_capability(
        CapabilitySpec(
            name="coding",
            category="model",
            discovery=("local_model", "huggingface", "openai_compatible"),
            authorization="internal",
            metadata={"default_model": "coder"},
        )
    )
    registry.register_capability(
        CapabilitySpec(
            name="document_rag",
            category="knowledge",
            discovery=("local_service", "mcp"),
            authorization="read:knowledge",
            metadata={"retrieval": "lexical"},
        )
    )
    return registry
