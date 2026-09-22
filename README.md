# OMNIBUS

<p align="center">
  <img src="assets/omnibus-banner.svg" alt="OMNIBUS — Advanced AI-Assisted Repository powered by GitHub Copilot" width="100%" />
</p>

OMNIBUS is an extensible AI-agent platform foundation built around Sovereign AI Factory.

> **Start here:** [`START_HERE.md`](START_HERE.md)

## One-cell Colab startup

```python
from google.colab import drive
drive.mount('/content/drive')

!rm -rf /content/OMNIBUS
!git clone https://github.com/omnichan0/OMNIBUS.git /content/OMNIBUS
%cd /content/OMNIBUS
!chmod +x install.sh
!./install.sh
```

Choose a T4 GPU in Colab first. The installer detects NVIDIA/CUDA, tries to provision `nvcc`, builds llama.cpp with CUDA when possible, uses `LLAMA_GPU_LAYERS=99`, and reports whether the final build is CUDA or CPU. Drive caches prevent repeating the expensive build on later sessions.

## Linux

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS
chmod +x install.sh
./install.sh
```

## Replit

Replit is supported as a lightweight CPU profile. It disables ngrok and computer-use, reports RAM/disk, and lets the user choose a small GGUF repository/file or public URL. For large models and fast inference, use Colab with a T4 instead.

## Tokens and models

`NGROK_TOKEN` is only for a public URL. `HF_TOKEN` is not required for public GGUF downloads; it is an optional credential for later Hugging Face Spaces, MCP/tools, gated/private resources, or other authenticated agent capabilities.

The installer reuses cached models and builds, resumes downloads, retries failures, and runs smoke tests before declaring the runtime online.

## Runtime commands

```bash
python3 core/sovereign_hive_factory.py --status
python3 core/sovereign_hive_factory.py --url
python3 core/sovereign_hive_factory.py --sync
python3 core/sovereign_hive_factory.py --stop
```
