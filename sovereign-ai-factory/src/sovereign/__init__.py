"""Sovereign AI runtime foundation package."""

from .agent import AgentDecision, AgentRuntime, create_default_runtime
from .cli import doctor
from .config import CapabilityConfig, load_capability_registry
from .discovery import DiscoveryResult, ProviderDiscovery, ProviderManifest
from .execution import CommandExecutor, ExecutionBackend, ExecutionProfile, ExecutionResult
from .orchestrator import Orchestrator, Plan
from .policy import ApprovalDecision, ApprovalPolicy, ApprovalState, ExecutionRequest, RiskLevel
from .registry import AdapterSpec, CapabilityRegistry, CapabilitySpec, load_registry

__all__ = [
    "AdapterSpec", "AgentDecision", "AgentRuntime", "ApprovalDecision", "ApprovalPolicy",
    "ApprovalState", "CapabilityConfig", "CapabilityRegistry", "CapabilitySpec",
    "CommandExecutor", "DiscoveryResult", "ExecutionBackend", "ExecutionProfile",
    "ExecutionRequest", "ExecutionResult", "Orchestrator", "Plan", "ProviderDiscovery",
    "ProviderManifest", "RiskLevel", "create_default_runtime", "doctor",
    "load_capability_registry", "load_registry",
]
