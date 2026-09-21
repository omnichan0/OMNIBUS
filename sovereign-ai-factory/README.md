# Sovereign AI Factory

Sovereign AI Factory is the primary OMNIBUS runtime: a portable, adaptive AI platform built around **Open WebUI as the primary user interface**. It discovers and composes capabilities through MCP, adapters, local models, Hugging Face resources, and authorized APIs.

## What it provides

- YAML-driven capability contracts instead of hard-coded providers
- Runtime discovery through provider manifests and Python entry points
- Policy-based approval for high-risk providers and execution requests
- Persistent provider manifests and approval decisions outside Git
- Direct execution for laptop and Colab deployments
- Optional Docker execution when Docker is available
- Colab/Drive-aware bootstrap support for local models and Open WebUI
- Lifecycle supervision, health checks, RAG, and hive runtime components

## Quick start

### Install on Linux

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS/sovereign-ai-factory
chmod +x install.sh
./install.sh
```

### Validate in Google Colab

```bash
!git clone https://github.com/omnichan0/OMNIBUS.git /content/OMNIBUS
%cd /content/OMNIBUS/sovereign-ai-factory
!python -m pip install -e ".[dev]"
!python -m compileall -q src core bootstrap
!pytest -q
!omnibus doctor
!omnibus capabilities
```

For the full Colab bootstrap, mount Google Drive when persistence is desired and provide `HF_TOKEN` and `NGROK_TOKEN` through Colab Secrets. The public tunnel is optional; use `--no-tunnel` for local-only operation.

## Runtime commands

From `sovereign-ai-factory/`:

```bash
# Inspect prerequisites and configured capabilities
omnibus doctor
omnibus capabilities

# Discover provider manifests
omnibus discover --manifest-dir ./providers

# Launch the full runtime without a public tunnel
omnibus install --non-interactive --no-tunnel

# Operate the Colab/local service stack directly
python core/sovereign_hive_factory.py --status
python core/sovereign_hive_factory.py --smoke-test
python core/sovereign_hive_factory.py --sync
python core/sovereign_hive_factory.py --stop
```

## Configuration

Capabilities are declared in [`config/capabilities.yaml`](config/capabilities.yaml). Providers can be discovered from JSON manifests or the `omnibus.providers` entry-point group.

Provider state defaults to `.omnibus/`; set `OMNIBUS_STATE_DIR` to use another location. Runtime credentials and state should remain outside Git.

## Supported environments

- **Linux:** native supported runtime
- **Google Colab:** supported GPU runtime; Google Drive can provide persistence
- **Windows:** use WSL2 for the Linux runtime and tooling
- **Docker:** optional isolated execution backend when Docker is installed and configured

## Validation status

The production foundation is merged into `main` and has passed direct-execution validation in Google Colab, including compilation, automated tests, package imports, registry loading, CLI checks, platform/GPU probing, manifest validation, approval gating, and execution safety checks.

Docker execution, full model downloads, llama.cpp compilation, Open WebUI startup, and public ngrok access depend on the target environment and credentials. Test those paths before using them for a production deployment.

## Secrets and security

Never commit secrets. Configure these at runtime as needed:

- `HF_TOKEN` for Hugging Face-backed capabilities
- `NGROK_TOKEN` or `NGROK_AUTHTOKEN` for a public tunnel
- `SOVEREIGN_API_KEY` and `WEBUI_SECRET_KEY` for protected services

The public tunnel should expose Open WebUI only. Keep administrative, shell, computer-use, MCP, and backend endpoints local or explicitly protected. Use public or authorized data sources and review third-party licenses and terms.

## Reporting issues

When testing, please open a GitHub Issue or comment on the relevant pull request with your environment, commit, command, expected result, actual result, logs, and suggested improvement. Useful labels include `testing`, `bug`, `production-readiness`, and `security`.
