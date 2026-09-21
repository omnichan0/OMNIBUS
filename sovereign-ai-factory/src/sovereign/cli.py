from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path

from .execution import available_backends
from .policy import RiskLevel
from .registry import default_capability_registry


def _yes(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{suffix}] ").strip().lower()
    return default if not answer else answer in {"y", "yes"}


def configure_credentials(*, interactive: bool = True) -> dict[str, bool]:
    """Collect optional runtime credentials only when the feature is enabled."""
    hf_enabled = os.environ.get("HF_TOKEN", "").strip() != ""
    ngrok_enabled = os.environ.get("NGROK_TOKEN", os.environ.get("NGROK_AUTHTOKEN", "")).strip() != ""
    if not interactive:
        return {"huggingface": hf_enabled, "public_url": ngrok_enabled}

    if _yes("Enable Hugging Face Spaces, MCP, and hosted model capabilities?", hf_enabled):
        if not hf_enabled:
            token = input("HF_TOKEN (hidden input is recommended in your shell): ").strip()
            if token:
                os.environ["HF_TOKEN"] = token
                hf_enabled = True
    if _yes("Enable a public browser URL through ngrok?", ngrok_enabled):
        if not ngrok_enabled:
            token = input("NGROK_TOKEN: ").strip()
            if token:
                os.environ["NGROK_TOKEN"] = token
                ngrok_enabled = True
    return {"huggingface": hf_enabled, "public_url": ngrok_enabled}


def doctor() -> dict[str, object]:
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "backends": sorted(str(item) for item in available_backends()),
        "git": shutil.which("git") is not None,
        "docker": shutil.which("docker") is not None,
        "hf_token_configured": bool(os.environ.get("HF_TOKEN")),
        "ngrok_token_configured": bool(os.environ.get("NGROK_TOKEN") or os.environ.get("NGROK_AUTHTOKEN")),
        "capabilities": default_capability_registry().registered_capabilities(),
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omnibus", description="OMNIBUS extensible AI runtime")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="inspect runtime prerequisites")
    sub.add_parser("capabilities", help="list built-in capability contracts")
    install = sub.add_parser("install", help="configure optional providers and launch the runtime")
    install.add_argument("--non-interactive", action="store_true")
    install.add_argument("--no-tunnel", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(doctor(), indent=2))
        return 0
    if args.command == "capabilities":
        print("\n".join(default_capability_registry().registered_capabilities()))
        return 0
    if args.command == "install":
        configured = configure_credentials(interactive=not args.non_interactive)
        if args.no_tunnel:
            configured["public_url"] = False
        print(json.dumps({"configured": configured, "risk_policy_max": RiskLevel.MEDIUM.name}, indent=2))
        print("Use install.sh to launch the full Open WebUI/model bootstrap.")
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
