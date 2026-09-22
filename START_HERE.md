# OMNIBUS — Start Here

OMNIBUS is designed so a beginner can copy one command and let the installer detect the platform and resources.

## Google Colab

```python
from google.colab import drive
drive.mount('/content/drive')

!git clone https://github.com/omnichan0/OMNIBUS.git /content/OMNIBUS
%cd /content/OMNIBUS
!chmod +x install.sh
!./install.sh
```

Colab uses the automatic model choices unless you set `SOVEREIGN_CHOOSE_MODELS=1`. A public URL is optional: paste an ngrok token when asked, or press Enter for private mode. `HF_TOKEN` is not required for ordinary public GGUF downloads.

## Linux

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS
chmod +x install.sh
./install.sh
```

The installer installs or restores missing components, displays RAM and disk space, and starts the self-healing runtime.

## Replit

Replit can run a lightweight CPU profile, but it is not a replacement for a Colab GPU. In the Replit Shell:

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS
chmod +x install.sh
./install.sh
```

The installer detects Replit and automatically disables ngrok and the computer-use service. It shows available RAM and disk, then asks you to press Enter for automatic model selection or paste a small GGUF repository/file/URL. Choose a small quantized model; large models may not fit Replit memory or may be too slow.

Replit's own web URL should be used instead of ngrok. If the platform does not expose the service automatically, configure the Replit web server port for `3000`.

## Model input examples

At the model prompt, you can paste:

```text
TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF
```

or:

```text
TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
```

or a full public Hugging Face `resolve` URL. The installer resolves the choice and downloads the public GGUF with resume/retry support.

## Tokens

- `NGROK_TOKEN`: only for a public ngrok URL; Replit normally does not need it.
- `HF_TOKEN`: optional later agent credential for Hugging Face Spaces, HF MCP/tools, gated/private resources, or authenticated services.

## What gets provisioned

The bootstrap checks for and provisions the Python environment, Open WebUI, llama.cpp, Node/Cline, optional ngrok, GGUF models, caches, service supervision, and smoke tests. It uses a cached Drive environment/model/build on later Colab runs.
