from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Iterable

from .policy import ApprovalPolicy, ExecutionRequest, RiskLevel
from .registry import AdapterSpec, CapabilityRegistry, CapabilitySpec


@dataclass(frozen=True, slots=True)
class ProviderManifest:
    """Declarative description supplied by a provider or repository adapter."""

    name: str
    capability: str
    category: str = "discovered"
    discovery: tuple[str, ...] = ()
    entrypoint: str | None = None
    permissions: tuple[str, ...] = ()
    risk: RiskLevel = RiskLevel.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ProviderManifest":
        required = ("name", "capability")
        missing = [key for key in required if not str(value.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Provider manifest missing: {', '.join(missing)}")
        risk = value.get("risk", RiskLevel.MEDIUM)
        if not isinstance(risk, RiskLevel):
            risk = RiskLevel[str(risk).upper()] if isinstance(risk, str) else RiskLevel(int(risk))
        return cls(
            name=str(value["name"]),
            capability=str(value["capability"]),
            category=str(value.get("category", "discovered")),
            discovery=tuple(str(item) for item in value.get("discovery", ())),
            entrypoint=value.get("entrypoint"),
            permissions=tuple(str(item) for item in value.get("permissions", ())),
            risk=risk,
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    manifest: ProviderManifest
    state: str
    reason: str


def _load_entrypoint(reference: str) -> Any:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"Invalid provider entrypoint: {reference!r}")
    target: Any = importlib.import_module(module_name)
    for part in attribute.split("."):
        target = getattr(target, part)
    return target


class ProviderDiscovery:
    """Discover declared providers without silently granting execution access.

    Providers publish manifests through Python entry points or JSON manifest
    files. Discovery is declarative; approval is required before an adapter is
    made active when its risk exceeds the operator policy.
    """

    ENTRYPOINT_GROUP = "omnibus.providers"

    def __init__(self, registry: CapabilityRegistry, policy: ApprovalPolicy | None = None) -> None:
        self.registry = registry
        self.policy = policy or ApprovalPolicy()

    def manifests_from_entrypoints(self) -> Iterable[ProviderManifest]:
        discovered = entry_points()
        providers = discovered.select(group=self.ENTRYPOINT_GROUP) if hasattr(discovered, "select") else discovered.get(self.ENTRYPOINT_GROUP, ())
        for provider in providers:
            value = provider.load()
            raw = value() if callable(value) else value
            yield ProviderManifest.from_mapping(raw if isinstance(raw, dict) else vars(raw))

    def manifests_from_directory(self, directory: str | Path) -> Iterable[ProviderManifest]:
        root = Path(directory).expanduser()
        if not root.exists():
            return
        for path in sorted(root.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            values = payload if isinstance(payload, list) else [payload]
            for value in values:
                if not isinstance(value, dict):
                    raise ValueError(f"Provider manifest must be an object: {path}")
                yield ProviderManifest.from_mapping(value)

    def inspect(self, manifest: ProviderManifest, *, approved: bool = False) -> DiscoveryResult:
        request = ExecutionRequest(
            capability=manifest.capability,
            action=f"register provider {manifest.name}",
            risk=manifest.risk,
            permissions=manifest.permissions,
        )
        decision = self.policy.evaluate(request, approved=approved)
        if decision.state.value == "pending":
            return DiscoveryResult(manifest, "pending_approval", decision.reason)
        self.registry.register_discovered_capability(
            CapabilitySpec(
                name=manifest.capability,
                category=manifest.category,
                discovery=manifest.discovery or ("provider",),
                metadata={"provider": manifest.name, **manifest.metadata},
            )
        )
        if not manifest.entrypoint:
            return DiscoveryResult(manifest, "discovered", "manifest registered; no executable entrypoint declared")
        implementation = _load_entrypoint(manifest.entrypoint)
        self.registry.register_adapter(
            AdapterSpec(
                name=manifest.name,
                capability=manifest.capability,
                implementation=implementation,
                required_permissions=manifest.permissions,
                metadata={"provider_manifest": manifest.name, **manifest.metadata},
            )
        )
        return DiscoveryResult(manifest, "active", decision.reason)

    def discover(self, *, manifest_directory: str | Path | None = None, approved: bool = False) -> list[DiscoveryResult]:
        manifests = list(self.manifests_from_entrypoints())
        if manifest_directory is not None:
            manifests.extend(self.manifests_from_directory(manifest_directory))
        return [self.inspect(manifest, approved=approved) for manifest in manifests]
