from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Sequence


class ExecutionBackend(StrEnum):
    DIRECT = "direct"
    DOCKER = "docker"


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: str
    backend: ExecutionBackend = ExecutionBackend.DIRECT
    allow_network: bool = True
    allow_privileged: bool = False
    working_directory: str | None = None
    environment: dict[str, str] = field(default_factory=dict)
    docker_image: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    backend: ExecutionBackend


class ExecutionError(RuntimeError):
    """Raised when an execution request cannot be started safely."""


def available_backends() -> set[ExecutionBackend]:
    available = {ExecutionBackend.DIRECT}
    if shutil.which("docker"):
        available.add(ExecutionBackend.DOCKER)
    return available


class CommandExecutor:
    """Execute approved commands using an explicitly selected backend.

    Direct execution is intentional for laptop and Colab deployments. This
    class never adds sudo implicitly; elevated execution must be represented by
    an approved command/profile configured by the operator.
    """

    def __init__(self, profile: ExecutionProfile) -> None:
        self.profile = profile

    def _docker_command(self, command: Sequence[str]) -> list[str]:
        if not self.profile.docker_image:
            raise ExecutionError("Docker execution requires an explicit image")
        if not self.profile.allow_network:
            network = ["--network", "none"]
        else:
            network = []
        return [
            "docker", "run", "--rm", *network,
            "--workdir", "/workspace",
            "-v", f"{self.profile.working_directory or os.getcwd()}:/workspace",
            self.profile.docker_image,
            *command,
        ]

    def run(self, command: Sequence[str], *, timeout: float | None = None) -> ExecutionResult:
        if not command or any(not str(part) for part in command):
            raise ExecutionError("Execution command must not be empty")
        backend = self.profile.backend
        if backend not in available_backends():
            raise ExecutionError(f"Execution backend is unavailable: {backend.value}")
        argv = list(map(str, command))
        if backend is ExecutionBackend.DOCKER:
            argv = self._docker_command(argv)
        env = os.environ.copy()
        env.update(self.profile.environment)
        completed = subprocess.run(
            argv,
            cwd=self.profile.working_directory if backend is ExecutionBackend.DIRECT else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return ExecutionResult(
            command=tuple(argv),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            backend=backend,
        )
