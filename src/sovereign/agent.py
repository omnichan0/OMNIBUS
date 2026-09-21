from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import CapabilityRegistry, load_registry


@dataclass
class AgentDecision:
    capability: str
    adapters: list[str] = field(default_factory=list)
    confidence: float = 0.0


class AgentRuntime:
    """Route tasks using the configured registry, never a hard-coded catalog."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def decide_capability(self, task: str) -> str:
        """Choose the best configured capability using metadata and task text.

        Capability IDs, categories, and aliases are supplied by configuration;
        adding a YAML entry is enough to make a new capability eligible.
        """
        normalized = task.casefold()
        candidates: list[tuple[int, str]] = []
        for name in self.registry.registered_capabilities():
            spec = self.registry.capability(name)
            if spec is None:
                continue
            searchable = {name, spec.category, *spec.discovery}
            aliases = spec.metadata.get("aliases", ())
            if isinstance(aliases, str):
                aliases = (aliases,)
            searchable.update(str(alias) for alias in aliases)
            score = sum(1 for term in searchable if term.casefold() in normalized)
            if score:
                candidates.append((score, name))
        if not candidates:
            raise LookupError("No configured capability matches the task")
        return max(candidates, key=lambda item: (item[0], item[1]))[1]

    def select_adapters(self, capability_name: str) -> list[str]:
        return [adapter.name for adapter in self.registry.resolve(capability_name)]

    def execute(self, task: str, payload: dict[str, Any] | None = None) -> AgentDecision:
        del payload
        capability_name = self.decide_capability(task)
        adapters = self.select_adapters(capability_name)
        if not adapters:
            raise RuntimeError(f"No adapters registered for capability: {capability_name}")
        return AgentDecision(capability=capability_name, adapters=adapters, confidence=1.0)


def create_default_runtime(config_path: str | Path | None = None) -> AgentRuntime:
    """Create a runtime from an explicit YAML file or the project config."""
    path = Path(config_path) if config_path else Path(__file__).resolve().parents[2] / "config" / "capabilities.yaml"
    return AgentRuntime(load_registry(path))
