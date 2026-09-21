from sovereign.discovery import ProviderDiscovery
from sovereign.policy import RiskLevel
from sovereign.registry import CapabilityRegistry


def test_json_provider_is_discovered_and_registered(tmp_path) -> None:
    manifest_dir = tmp_path / "providers"
    manifest_dir.mkdir()
    (manifest_dir / "image.json").write_text(
        '{"name": "image-provider", "capability": "image_generation", "category": "media", "discovery": ["repository"], "risk": "LOW"}',
        encoding="utf-8",
    )
    registry = CapabilityRegistry()
    results = ProviderDiscovery(registry).discover(manifest_directory=manifest_dir)
    assert [result.state for result in results] == ["discovered"]
    assert registry.capability("image_generation") is not None


def test_high_risk_provider_requires_approval(tmp_path) -> None:
    manifest_dir = tmp_path / "providers"
    manifest_dir.mkdir()
    (manifest_dir / "shell.json").write_text(
        '{"name": "shell-provider", "capability": "workspace", "risk": "HIGH", "permissions": ["filesystem.write"]}',
        encoding="utf-8",
    )
    registry = CapabilityRegistry()
    results = ProviderDiscovery(registry).discover(manifest_directory=manifest_dir)
    assert results[0].state == "pending_approval"
    assert results[0].manifest.risk is RiskLevel.HIGH
    assert registry.capability("workspace") is None


def test_approved_provider_becomes_active_without_entrypoint(tmp_path) -> None:
    manifest_dir = tmp_path / "providers"
    manifest_dir.mkdir()
    (manifest_dir / "approved.json").write_text(
        '{"name": "approved-provider", "capability": "custom", "risk": "HIGH"}',
        encoding="utf-8",
    )
    registry = CapabilityRegistry()
    results = ProviderDiscovery(registry).discover(manifest_directory=manifest_dir, approved=True)
    assert results[0].state == "discovered"
    assert results[0].manifest.risk is RiskLevel.HIGH
    assert registry.capability("custom") is not None
