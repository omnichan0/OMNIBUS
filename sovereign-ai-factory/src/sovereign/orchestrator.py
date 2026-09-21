from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .execution import CommandExecutor, ExecutionProfile, ExecutionResult
from .policy import ApprovalDecision, ApprovalPolicy, ExecutionRequest, RiskLevel
from .registry import CapabilityRegistry, load_registry


@dataclass(frozen=True, slots=True)
class Plan:
    request: ExecutionRequest
    approval: ApprovalDecision
    backend: str
    command: tuple[str, ...]


class Orchestrator:
    def __init__(self, registry: CapabilityRegistry | None = None, policy: ApprovalPolicy | None = None) -> None:
        self.registry = registry or load_registry(Path(__file__).resolve().parents[2] / "config" / "capabilities.yaml")
        self.policy = policy or ApprovalPolicy()

    def plan(self, capability: str, action: str, command: Sequence[str], *, target: str = "local", risk: RiskLevel = RiskLevel.LOW, permissions: tuple[str, ...] = (), profile: ExecutionProfile | None = None, approved: bool = False) -> Plan:
        request = ExecutionRequest(capability, action, target, risk, permissions)
        decision = self.policy.evaluate(request, approved=approved)
        selected = profile or ExecutionProfile(name=f"{capability}-direct")
        return Plan(request, decision, selected.backend.value, tuple(map(str, command)))

    def execute(self, plan: Plan, *, profile: ExecutionProfile | None = None, timeout: float | None = None) -> ExecutionResult:
        if plan.approval.state.value == "pending":
            raise PermissionError(f"Approval required for request {plan.request.request_id}")
        selected = profile or ExecutionProfile(name=f"{plan.request.capability}-direct")
        return CommandExecutor(selected).run(plan.command, timeout=timeout)
