from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from uuid import uuid4


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ApprovalState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    capability: str
    action: str
    target: str = "local"
    risk: RiskLevel = RiskLevel.LOW
    permissions: tuple[str, ...] = ()
    request_id: str = ""

    def __post_init__(self) -> None:
        if not self.request_id:
            object.__setattr__(self, "request_id", uuid4().hex)


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    state: ApprovalState
    reason: str
    request_id: str


class ApprovalPolicy:
    """Operator-controlled approval policy.

    The human configures the maximum risk that may proceed automatically. The
    agent evaluates the request, but cannot elevate this threshold itself.
    """

    def __init__(self, automatic_max_risk: RiskLevel = RiskLevel.MEDIUM) -> None:
        self.automatic_max_risk = automatic_max_risk

    def evaluate(self, request: ExecutionRequest, *, approved: bool = False) -> ApprovalDecision:
        if approved:
            return ApprovalDecision(ApprovalState.APPROVED, "explicit human approval", request.request_id)
        if request.risk <= self.automatic_max_risk:
            return ApprovalDecision(ApprovalState.NOT_REQUIRED, "within configured operator policy", request.request_id)
        return ApprovalDecision(ApprovalState.PENDING, "human approval required by risk policy", request.request_id)
