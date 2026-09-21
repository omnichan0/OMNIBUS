# OMNIBUS — Start Here

OMNIBUS is designed so a beginner can copy one command, answer the ngrok question when needed, and let the installer do the work.

## Choose your path

### Google Colab (recommended for a GPU)

1. Open a new Google Colab notebook.
2. Set **Runtime → Change runtime type → T4 GPU** if a GPU is available.
3. Paste this entire cell and run it:

```python
from google.colab import drive
drive.mount('/content/drive')

!git clone https://github.com/omnichan0/OMNIBUS.git /content/OMNIBUS
%cd /content/OMNIBUS
!chmod +x install.sh
!./install.sh
```

The installer asks only for an **ngrok token** when it needs to create a public browser URL. Press **Enter** to run privately without a public tunnel.

You do **not** need an `HF_TOKEN` just to download the default GGUF models. The agent may use Hugging Face later as an optional tool—for example, for a Hugging Face Space, MCP integration, or another gated resource. Provide `HF_TOKEN` in Colab Secrets only if that later capability asks for it.

### Linux

Open a terminal and paste:

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS
chmod +x install.sh
./install.sh
```

The installer detects the package manager and installs missing runtime prerequisites where it has permission. It then installs the Python environment, Open WebUI, llama.cpp, models, Cline, and optional ngrok, starts the services, and runs smoke tests.

### Windows

Install WSL2 first in PowerShell:

```powershell
wsl --install
```

Restart if Windows asks you to. Then open Ubuntu/WSL and use the Linux instructions above. The supported runtime is Linux inside WSL2.

## What happens automatically

The bootstrap checks and provisions missing components instead of assuming they are already installed:

- system build tools, Git, cURL, CMake, compiler, `pkg-config`, and FFmpeg;
- an isolated Python 3.11 environment;
- Open WebUI and its Python dependencies;
- llama.cpp, compiled for NVIDIA CUDA when the environment provides `nvidia-smi` and `nvcc`, otherwise for CPU;
- Node.js and Cline;
- ngrok when a public tunnel is requested;
- GGUF reasoning and coding models;
- Drive-backed caches, model reuse, service supervision, and retries.

The GGUF downloader uses public Hugging Face resolve URLs by default. It discovers a suitable file, resumes interrupted transfers, retries network failures, and reuses a Drive copy when available. An HF token is not part of the normal GGUF setup. Model files are deliberately kept out of Git because they are large runtime assets.

## Tokens

- `NGROK_TOKEN` or `NGROK_AUTHTOKEN`: optional; only needed for a public URL.
- `HF_TOKEN`: optional agent capability; use it later for Hugging Face Spaces, HF MCP/tools, gated repositories, or other authenticated Hugging Face services.
- Never paste tokens into GitHub files or commit them.

If the installer cannot install a missing system package because the account has no `sudo` permission, it will say exactly what is missing. On Colab, the notebook runtime normally provides Python and the required permissions.

## After installation

The installer prints the Open WebUI address and the generated administrator credentials. Keep the credentials private and change the password after first login.

Useful commands from the repository root:

```bash
python3 core/sovereign_hive_factory.py --status
python3 core/sovereign_hive_factory.py --url
python3 core/sovereign_hive_factory.py --sync
python3 core/sovereign_hive_factory.py --stop
```

If a Colab runtime is recycled, mount Drive and run the same installer again. Cached models, the Python environment, llama.cpp, chats, and service state can be restored instead of downloaded again.
