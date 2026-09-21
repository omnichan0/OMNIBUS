"""Sovereign AI runtime foundation package."""

from .agent import AgentDecision, AgentRuntime, create_default_runtime
from .config import CapabilityConfig, load_capability_registry
from .discovery import DiscoveryResult, ProviderDiscovery, ProviderManifest
from .execution import CommandExecutor, ExecutionBackend, ExecutionProfile, ExecutionResult
from .orchestrator import Orchestrator, Plan
from .persistence import ProviderStateStore
from .policy import ApprovalDecision, ApprovalPolicy, ApprovalState, ExecutionRequest, RiskLevel
from .registry import AdapterSpec, CapabilityRegistry, CapabilitySpec, load_registry


def doctor() -> dict[str, object]:
    """Run the CLI diagnostics without eagerly importing the CLI module."""
    from .cli import doctor as run_doctor

    return run_doctor()


__all__ = [
    "AdapterSpec", "AgentDecision", "AgentRuntime", "ApprovalDecision", "ApprovalPolicy",
    "ApprovalState", "CapabilityConfig", "CapabilityRegistry", "CapabilitySpec",
    "CommandExecutor", "DiscoveryResult", "ExecutionBackend", "ExecutionProfile",
    "ExecutionRequest", "ExecutionResult", "Orchestrator", "Plan", "ProviderDiscovery",
    "ProviderManifest", "ProviderStateStore", "RiskLevel", "create_default_runtime", "doctor",
    "load_capability_registry", "load_registry",
]
