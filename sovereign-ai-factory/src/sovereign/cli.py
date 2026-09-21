from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from .discovery import ProviderDiscovery
from .execution import available_backends
from .persistence import ProviderStateStore
from .policy import RiskLevel
from .registry import load_registry


def _yes(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{suffix}] ").strip().lower()
    return default if not answer else answer in {"y", "yes"}


def _secret(prompt: str) -> str:
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _registry():
    return load_registry(_project_root() / "config" / "capabilities.yaml")


def _state_store() -> ProviderStateStore:
    return ProviderStateStore(os.environ.get("OMNIBUS_STATE_DIR", str(_project_root() / ".omnibus")))


def configure_credentials(*, interactive: bool = True) -> dict[str, bool]:
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    ngrok_token = os.environ.get("NGROK_TOKEN", os.environ.get("NGROK_AUTHTOKEN", "")).strip()
    result = {"huggingface": bool(hf_token), "public_url": bool(ngrok_token)}
    if not interactive:
        return result
    if _yes("Enable Hugging Face Spaces, MCP, and hosted model capabilities?", result["huggingface"]) and not hf_token:
        hf_token = _secret("HF_TOKEN (hidden): ").strip()
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
            result["huggingface"] = True
    if _yes("Enable a public browser URL through ngrok?", result["public_url"]) and not ngrok_token:
        ngrok_token = _secret("NGROK_TOKEN (hidden): ").strip()
        if ngrok_token:
            os.environ["NGROK_TOKEN"] = ngrok_token
            result["public_url"] = True
    return result


def doctor() -> dict[str, object]:
    return {"platform": platform.platform(), "python": platform.python_version(), "backends": sorted(str(item) for item in available_backends()), "git": shutil.which("git") is not None, "docker": shutil.which("docker") is not None, "hf_token_configured": bool(os.environ.get("HF_TOKEN")), "ngrok_token_configured": bool(os.environ.get("NGROK_TOKEN") or os.environ.get("NGROK_AUTHTOKEN")), "capabilities": _registry().registered_capabilities()}


def discover(manifest_directory: str | None, approve: bool) -> int:
    results = ProviderDiscovery(_registry(), store=_state_store()).discover(manifest_directory=manifest_directory, approved=approve)
    print(json.dumps([{"name": item.manifest.name, "capability": item.manifest.capability, "state": item.state, "reason": item.reason} for item in results], indent=2))
    return 0


def launch_bootstrap(*, no_tunnel: bool = False) -> int:
    core = _project_root() / "core" / "sovereign_hive_factory.py"
    if not core.exists():
        raise FileNotFoundError(f"Bootstrap runtime not found: {core}")
    command = [os.environ.get("PYTHON", "python3"), str(core), "--bootstrap", "--run-free"]
    if no_tunnel:
        command.append("--no-tunnel")
    return subprocess.call(command, cwd=_project_root())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omnibus", description="OMNIBUS extensible AI runtime")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="inspect runtime prerequisites")
    sub.add_parser("capabilities", help="list configured capability contracts")
    found = sub.add_parser("discover", help="discover provider manifests")
    found.add_argument("--manifest-dir")
    found.add_argument("--approve", action="store_true", help="approve discovered providers allowed by this invocation")
    install = sub.add_parser("install", help="configure providers and launch the runtime")
    install.add_argument("--non-interactive", action="store_true")
    install.add_argument("--no-tunnel", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(doctor(), indent=2)); return 0
    if args.command == "capabilities":
        print("\n".join(_registry().registered_capabilities())); return 0
    if args.command == "discover":
        return discover(args.manifest_dir, args.approve)
    if args.command == "install":
        configured = configure_credentials(interactive=not args.non_interactive)
        if args.no_tunnel:
            configured["public_url"] = False
        print(json.dumps({"configured": configured, "risk_policy_max": RiskLevel.MEDIUM.name}, indent=2))
        return launch_bootstrap(no_tunnel=args.no_tunnel)
    build_parser().print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
