"""Small platform/capability probe used by tooling and diagnostics."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def is_colab() -> bool:
    return bool(os.getenv("COLAB_RELEASE_TAG")) or Path("/content/sample_data").exists()


def gpu() -> dict:
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return {"vendor": "none", "available": False}
    try:
        out = subprocess.check_output(
            [nvidia, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=5,
        ).strip()
        return {"vendor": "nvidia", "available": True, "devices": out.splitlines()}
    except Exception as exc:
        return {"vendor": "nvidia", "available": False, "error": str(exc)}


def _system_details() -> tuple[str, str, str]:
    """Read host details without importing platform.py under direct execution."""
    if hasattr(os, "uname"):
        details = os.uname()
        return details.sysname, details.release, details.machine
    return os.name, "unknown", "unknown"


def report() -> dict:
    system, release, machine = _system_details()
    return {
        "os": system,
        "release": release,
        "machine": machine,
        "python": sys.version.split()[0],
        "colab": is_colab(),
        "gpu": gpu(),
        "git": bool(shutil.which("git")),
        "docker": bool(shutil.which("docker")),
        "node": bool(shutil.which("node")),
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
