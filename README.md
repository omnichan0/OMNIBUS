# OMNIBUS

<p align="center">
  <img src="assets/omnibus-banner.svg" alt="OMNIBUS — Advanced AI-Assisted Repository powered by GitHub Copilot" width="100%" />
</p>

[![Quality checks](https://github.com/omnichan0/OMNIBUS/actions/workflows/sanity.yml/badge.svg?branch=main)](https://github.com/omnichan0/OMNIBUS/actions/workflows/sanity.yml)

OMNIBUS is an extensible AI-agent platform foundation. Its primary implementation, **Sovereign AI Factory**, provides a portable runtime for capability discovery, provider adapters, policy-controlled execution, persistent state, and secure deployment across Linux, Google Colab, Windows/WSL2, and optional Docker environments.

## Highlights

- **Registry-driven capabilities** configured through YAML
- **Runtime provider discovery** through manifests and entry points
- **Risk-based approval gates** for high-risk providers and actions
- **Policy-aware execution** with direct and optional Docker backends
- **Persistent provider state** and approval records outside Git
- **Colab-friendly deployment** with optional Google Drive persistence
- **Open WebUI as the primary user interface**
- **Security-oriented defaults** for secrets, public tunnels, and authorized data sources

## Repository layout

The repository is intentionally organized as a complete project tree rather than a single documentation folder:

```text
OMNIBUS/
├── README.md
├── assets/
│   └── omnibus-banner.svg
└── sovereign-ai-factory/
    ├── README.md
    ├── pyproject.toml
    ├── config/
    │   └── capabilities.yaml
    ├── src/sovereign/
    │   ├── __init__.py
    │   ├── agent.py
    │   ├── cli.py
    │   ├── config.py
    │   ├── discovery.py
    │   ├── execution.py
    │   ├── orchestrator.py
    │   ├── persistence.py
    │   ├── policy.py
    │   └── registry.py
    ├── tests/
    ├── core/
    ├── bootstrap/
    ├── adapters/
    ├── scripts/
    ├── install.sh
    ├── install.ps1
    └── .github/workflows/
        └── sanity.yml
```

## Quick start

### Linux

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS/sovereign-ai-factory
chmod +x install.sh
./install.sh
```

### Google Colab

```bash
!git clone https://github.com/omnichan0/OMNIBUS.git /content/OMNIBUS
%cd /content/OMNIBUS/sovereign-ai-factory
!python -m pip install -e ".[dev]"
!python -m compileall -q src core bootstrap
!pytest -q
```

For the full Colab runtime, configure `HF_TOKEN` and, when a public URL is required, `NGROK_TOKEN` through Colab Secrets. Never commit credentials.

### Windows

The supported Windows path uses WSL2 so the same Linux runtime can be used. See [`sovereign-ai-factory/README.md`](sovereign-ai-factory/README.md) and `install.ps1` for the Windows setup path.

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

Capabilities are declared in [`sovereign-ai-factory/config/capabilities.yaml`](sovereign-ai-factory/config/capabilities.yaml). Providers can be discovered from JSON manifests or the `omnibus.providers` entry-point group.

Provider state defaults to `.omnibus/`; set `OMNIBUS_STATE_DIR` to use another location. Runtime credentials and state should remain outside Git.

## Supported environments

- **Linux:** native supported runtime
- **Google Colab:** supported GPU runtime; Google Drive can provide persistence
- **Windows:** use WSL2 for the Linux runtime and tooling
- **Docker:** optional isolated execution backend when Docker is installed and configured

## Validation status

The production foundation has been merged into `main` and has passed direct-execution validation in Google Colab, including compilation, automated tests, package imports, registry loading, CLI checks, platform and GPU detection, invalid provider-manifest rejection, high-risk provider approval gating, direct-execution safety checks, and orchestrator smoke execution.

Docker execution, full model downloads, llama.cpp compilation, Open WebUI startup, and public ngrok access depend on the target environment and credentials. Test those paths before using them for production workloads.

## Tester feedback

If you test OMNIBUS, please open a GitHub Issue or comment on the relevant pull request with:

- operating system and Python version
- commit or branch tested
- command or workflow used
- expected behavior
- actual behavior
- logs or traceback
- suggested improvement

Useful labels include `testing`, `bug`, `production-readiness`, and `security`.

## Security and responsible use

- Keep `HF_TOKEN`, `NGROK_TOKEN`, API keys, and other secrets outside Git.
- Expose only Open WebUI through a public tunnel unless additional endpoints are explicitly protected.
- Keep administrative, shell, computer-use, MCP, and backend endpoints local or authenticated.
- Use only public or authorized data sources.
- Review third-party licenses and provider terms before enabling integrations.

## Main project

The implementation and detailed runtime documentation are in [`sovereign-ai-factory/`](sovereign-ai-factory/).
