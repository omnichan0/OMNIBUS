from sovereign.execution import ExecutionBackend, ExecutionProfile
from sovereign.orchestrator import Orchestrator
from sovereign.policy import ApprovalState, RiskLevel


def test_low_risk_direct_execution() -> None:
    orchestrator = Orchestrator()
    plan = orchestrator.plan("local", "print status", ["python", "-c", "print('ready')"])
    assert plan.approval.state is ApprovalState.NOT_REQUIRED
    result = orchestrator.execute(plan, timeout=10)
    assert result.returncode == 0
    assert "ready" in result.stdout


def test_high_risk_requires_approval() -> None:
    orchestrator = Orchestrator()
    plan = orchestrator.plan(
        "network", "active scan", ["python", "-c", "print('approved')"],
        target="operator-approved-lab", risk=RiskLevel.HIGH, permissions=("network.scan",),
    )
    assert plan.approval.state is ApprovalState.PENDING


def test_docker_profile_is_explicit() -> None:
    profile = ExecutionProfile(name="isolated", backend=ExecutionBackend.DOCKER, docker_image="python:3.11")
    assert profile.backend is ExecutionBackend.DOCKER
