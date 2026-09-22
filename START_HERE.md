# OMNIBUS — Start Here

## Colab: GPU-first startup

1. In Colab choose **Runtime → Change runtime type → T4 GPU**.
2. Paste this one cell:

```python
from google.colab import drive
drive.mount('/content/drive')

!rm -rf /content/OMNIBUS
!git clone https://github.com/omnichan0/OMNIBUS.git /content/OMNIBUS
%cd /content/OMNIBUS
!chmod +x install.sh
!./install.sh
```

The installer will:

- detect the T4 with `nvidia-smi`;
- locate or install the CUDA compiler when possible;
- build llama.cpp with CUDA rather than CPU when `nvcc` is available;
- set all model layers for GPU offload (`LLAMA_GPU_LAYERS=99`);
- print the GPU and CUDA status before building;
- restore a matching cached build from Drive on later runs.

A public URL is optional. Paste an ngrok token when asked, or press **Enter** for private mode. `HF_TOKEN` is not required for public GGUF downloads; it is reserved for later authenticated Hugging Face agent tools, Spaces, MCP integrations, or gated resources.

## Linux

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS
chmod +x install.sh
./install.sh
```

The installer detects the platform, GPU, RAM, and disk, then provisions the missing runtime components.

## Replit

```bash
git clone https://github.com/omnichan0/OMNIBUS.git
cd OMNIBUS
chmod +x install.sh
./install.sh
```

Replit is treated as a lightweight CPU profile: ngrok and computer-use are disabled, and the installer displays available RAM and disk. It asks for a model repository/file or public GGUF URL when model selection is enabled. Use a small quantized model; Colab is the better environment for large GPU models.

## Model selection

Set `SOVEREIGN_CHOOSE_MODELS=1` before starting if you want to choose models on Colab/Linux. Replit asks automatically. At the prompt, press Enter for the default or paste:

```text
TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF
TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
https://huggingface.co/<repo>/resolve/main/<file>.gguf
```

Public GGUF downloads use Hugging Face resolve URLs with resume/retry support and do not require `HF_TOKEN`.

## If the output says CPU fallback

A T4 is visible only when `nvidia-smi` works. CUDA compilation additionally needs `nvcc`. Run:

```python
!nvidia-smi
!which nvcc || true
!nvcc --version || true
```

If `nvidia-smi` works but `nvcc` does not, the installer tries the CUDA toolkit installation automatically. If that fails, it reports CPU fallback instead of pretending the GPU is being used.
