# Sovereign AI Factory

A portable, adaptive AI runtime built around **Open WebUI as the single
primary UI**. The backend is designed to discover and compose capabilities
through MCP, adapters, local models, Hugging Face resources, and APIs.

## Design principles

- **One UI:** Open WebUI.
- **No provider lock-in:** models and services are capabilities, not
  hard-coded application branches.
- **Runtime discovery:** when a task needs a capability such as video,
  research, browser automation, globe/geospatial data, or image generation,
  the system can discover suitable implementations instead of assuming one
  fixed provider.
- **Portable:** Linux is the native runtime; Windows uses WSL2 for the same
  Linux stack; Google Colab is a supported GPU runtime.
- **Persistent where possible:** Colab state can live on Google Drive.
- **Secrets stay out of Git:** HF and ngrok credentials come from runtime
  secret stores/environment variables.
- **Authorized integrations:** public or authorized data sources only;
  third-party repositories must be used according to their licenses/terms.

## Quick start — Linux / Colab

    git clone YOUR_REPO_URL
    cd sovereign-ai
    chmod +x install.sh
    ./install.sh

For Colab, put `HF_TOKEN` and `NGROK_TOKEN` in Colab Secrets before running
the bootstrap.

## Windows

Run `install.ps1`. The supported Windows path uses WSL2 so the same Linux
runtime and repository are used.

## Current core

`core/sovereign_hive_factory.py` is the supplied Sovereign Hive Factory
engine. It provides the current Colab/Drive-persistent service stack,
supervisor, Open WebUI, llama.cpp, model handling, RAG/hive services,
Cline integration, and ngrok plumbing.

The surrounding repository is intentionally structured so MCP and future
adapters/capability discovery can be added without turning Open WebUI into
a collection of competing frontends.

## Secrets

Required for the full Hugging Face-backed capability set:

    HF_TOKEN

Required for a public ngrok URL:

    NGROK_TOKEN

Never commit either secret.

## Useful commands

    python3 core/sovereign_hive_factory.py --status
    python3 core/sovereign_hive_factory.py --url
    python3 core/sovereign_hive_factory.py --smoke-test
    python3 core/sovereign_hive_factory.py --sync
    python3 core/sovereign_hive_factory.py --stop

## Important security note

The public tunnel should expose Open WebUI only. Administrative, shell,
computer-use, MCP, and backend endpoints should remain local or explicitly
protected. Review adapter licenses, provider terms, and access controls
before enabling new capabilities.
