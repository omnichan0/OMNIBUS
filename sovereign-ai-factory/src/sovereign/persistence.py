from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .discovery import DiscoveryResult, ProviderManifest


class ProviderStateStore:
    """Persist discovered provider manifests and approval decisions outside Git."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser()
        self.manifests_dir = self.root / "providers"
        self.approvals_path = self.root / "approvals.json"

    def save_result(self, result: DiscoveryResult) -> None:
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        path = self.manifests_dir / f"{result.manifest.name}.json"
        payload = asdict(result.manifest) | {"state": result.state, "reason": result.reason}
        payload["risk"] = result.manifest.risk.name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def save_approval(self, manifest: ProviderManifest, approved: bool) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        approvals = self.load_approvals()
        approvals[manifest.name] = {"approved": approved, "capability": manifest.capability, "risk": manifest.risk.name}
        self.approvals_path.write_text(json.dumps(approvals, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def load_approvals(self) -> dict[str, Any]:
        if not self.approvals_path.exists():
            return {}
        payload = json.loads(self.approvals_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Approval store must contain an object: {self.approvals_path}")
        return payload

    def is_approved(self, manifest: ProviderManifest) -> bool:
        record = self.load_approvals().get(manifest.name, {})
        return bool(record.get("approved", False))
