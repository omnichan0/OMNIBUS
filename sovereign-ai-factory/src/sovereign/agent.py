from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .registry import CapabilityRegistry, default_capability_registry


@dataclass
class AgentDecision:
    capability: str
    adapters: list[str] = field(default_factory=list)
    confidence: float = 0.0


class AgentRuntime:
    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or default_capability_registry()

    def decide_capability(self, task: str) -> str:
        normalized = task.lower()
        if any(word in normalized for word in ("code", "refactor", "python", "bug", "fix", "debug")):
            return "coding"
        if any(word in normalized for word in ("document", "rag", "search", "docs", "knowledge", "index")):
            return "document_rag"
        if any(word in normalized for word in ("research", "plan", "strategy", "compare", "analyze")):
            return "reasoning"
        return "reasoning"

    def select_adapters(self, capability_name: str) -> list[str]:
        return [adapter.name for adapter in self.registry.resolve(capability_name)]

    def execute(self, task: str, payload: dict[str, Any] | None = None) -> AgentDecision:
        capability_name = self.decide_capability(task)
        adapters = self.select_adapters(capability_name)
        if not adapters:
            raise RuntimeError(f"No adapters registered for capability: {capability_name}")
        confidence = 0.6 if capability_name == "reasoning" else 0.8
        return AgentDecision(capability=capability_name, adapters=adapters, confidence=confidence)


def create_default_runtime() -> AgentRuntime:
    return AgentRuntime()
