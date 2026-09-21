from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Iterable

from .persistence import ProviderStateStore
from .policy import ApprovalPolicy, ExecutionRequest, RiskLevel
from .registry import AdapterSpec, CapabilityRegistry, CapabilitySpec


@dataclass(frozen=True, slots=True)
class ProviderManifest:
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
        missing = [key for key in ("name", "capability") if not str(value.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Provider manifest missing: {', '.join(missing)}")
        raw_risk = value.get("risk", RiskLevel.MEDIUM)
        if not isinstance(raw_risk, RiskLevel):
            raw_risk = RiskLevel[str(raw_risk).upper()] if isinstance(raw_risk, str) else RiskLevel(int(raw_risk))
        return cls(
            name=str(value["name"]),
            capability=str(value["capability"]),
            category=str(value.get("category", "discovered")),
            discovery=tuple(str(item) for item in value.get("discovery", ())),
            entrypoint=value.get("entrypoint"),
            permissions=tuple(str(item) for item in value.get("permissions", ())),
            risk=raw_risk,
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
    ENTRYPOINT_GROUP = "omnibus.providers"

    def __init__(self, registry: CapabilityRegistry, policy: ApprovalPolicy | None = None, store: ProviderStateStore | None = None) -> None:
        self.registry = registry
        self.policy = policy or ApprovalPolicy()
        self.store = store

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
            payload = json.loads(path.read_text(encoding="utf-8"))
            for value in payload if isinstance(payload, list) else [payload]:
                if not isinstance(value, dict):
                    raise ValueError(f"Provider manifest must be an object: {path}")
                yield ProviderManifest.from_mapping(value)

    def inspect(self, manifest: ProviderManifest, *, approved: bool = False) -> DiscoveryResult:
        request = ExecutionRequest(manifest.capability, f"register provider {manifest.name}", risk=manifest.risk, permissions=manifest.permissions)
        decision = self.policy.evaluate(request, approved=approved)
        if decision.state.value == "pending":
            result = DiscoveryResult(manifest, "pending_approval", decision.reason)
        else:
            self.registry.register_discovered_capability(CapabilitySpec(manifest.capability, manifest.category, manifest.discovery or ("provider",), metadata={"provider": manifest.name, **manifest.metadata}))
            if not manifest.entrypoint:
                result = DiscoveryResult(manifest, "discovered", "manifest registered; no executable entrypoint declared")
            else:
                self.registry.register_adapter(AdapterSpec(manifest.name, manifest.capability, _load_entrypoint(manifest.entrypoint), manifest.permissions, {"provider_manifest": manifest.name, **manifest.metadata}))
                result = DiscoveryResult(manifest, "active", decision.reason)
        if self.store:
            self.store.save_result(result)
            if approved:
                self.store.save_approval(manifest, True)
        return result

    def discover(self, *, manifest_directory: str | Path | None = None, approved: bool = False) -> list[DiscoveryResult]:
        manifests = list(self.manifests_from_entrypoints())
        if manifest_directory is not None:
            manifests.extend(self.manifests_from_directory(manifest_directory))
        return [self.inspect(manifest, approved=approved or (self.store.is_approved(manifest) if self.store else False)) for manifest in manifests]
