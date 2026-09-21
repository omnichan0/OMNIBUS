"""Small platform/capability probe used by tooling and diagnostics."""
from __future__ import annotations
import os, platform, shutil, subprocess
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
            text=True, stderr=subprocess.STDOUT, timeout=5
        ).strip()
        return {"vendor": "nvidia", "available": True, "devices": out.splitlines()}
    except Exception as exc:
        return {"vendor": "nvidia", "available": False, "error": str(exc)}

def report() -> dict:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "colab": is_colab(),
        "gpu": gpu(),
        "git": bool(shutil.which("git")),
        "docker": bool(shutil.which("docker")),
        "node": bool(shutil.which("node")),
    }

if __name__ == "__main__":
    import json
    print(json.dumps(report(), indent=2))
