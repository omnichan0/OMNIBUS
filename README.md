# OMNIBUS

OMNIBUS is the umbrella repository for a production-grade AI agent platform. The active implementation lives in `sovereign-ai-factory/`, which contains the runtime, bootstrap logic, capability registry, and install flow.

## Repository layout

```text
OMNIBUS/
  README.md
  sovereign-ai-factory/
    README.md
    pyproject.toml
    src/
    tests/
    .github/workflows/
    install.sh
    install.ps1
```

## Current focus

The project is being evolved from a monolithic prototype into a production-grade, self-maintaining AI agent foundation with:

- extension-first capability discovery
- registry-driven adapters and tool loading
- typed runtime configuration
- health checks and lifecycle supervision
- testable architecture boundaries
- explicit security and deployment guardrails

## Primary project

See the implementation in:

- `sovereign-ai-factory/README.md`
- `sovereign-ai-factory/src/sovereign/`

## Status

This repository is in active foundational refactor work. The next milestones are repository cleanup, modular architecture, secure runtime defaults, and production-grade agent orchestration.
