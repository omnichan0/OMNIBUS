# OMNIBUS

<p align="center">
  <img src="assets/omnibus-banner.svg" alt="OMNIBUS — Advanced AI-Assisted Repository powered by GitHub Copilot" width="100%" />
</p>

[![Quality checks](https://github.com/omnichan0/OMNIBUS/actions/workflows/sanity.yml/badge.svg?branch=main)](https://github.com/omnichan0/OMNIBUS/actions/workflows/sanity.yml)

OMNIBUS is an extensible AI-agent platform foundation. Its primary implementation, **Sovereign AI Factory**, provides a portable runtime for capability discovery, provider adapters, policy-controlled execution, local models, and Open WebUI integration.

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
└── 
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
cd OMNIBUS
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

The supported Windows path uses WSL2 so the same Linux runtime can be used. See `README.md` and `install.ps1` for the Windows setup path.

## Validation status

The production foundation has been merged into `main` and has passed the following checks in Google Colab/direct-execution mode:

- Python compilation and automated tests
- Package import and capability-registry checks
- CLI diagnostics and capability listing
- Platform and GPU detection
- Invalid provider-manifest rejection
- High-risk provider approval gating
- Direct-execution safety checks
- Orchestrator smoke execution

Docker execution and full model/Open WebUI bootstrap are environment-specific follow-up tests and are not represented by the direct-execution validation badge.

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

The implementation and detailed runtime documentation are in [``]().
