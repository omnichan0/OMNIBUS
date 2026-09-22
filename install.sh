#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SOVEREIGN_REPO_ROOT="$ROOT"

say() { printf '%s\n' "$*"; }

install_python_if_missing() {
  command -v python3 >/dev/null 2>&1 && return 0
  say "[setup] Python 3 was not found. Trying to install it automatically..."
  if command -v apt-get >/dev/null 2>&1; then
    if [ "$(id -u)" -eq 0 ]; then
      apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv
    elif command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv
    else
      say "Please install Python 3.10+ and run this file again."; exit 1
    fi
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache python3 py3-pip py3-virtualenv
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-virtualenv
  else
    say "No supported package manager was found. Please install Python 3.10+ and run again."; exit 1
  fi
}

ask_tty() {
  local prompt="$1" answer=""
  if [[ -t 0 ]]; then
    printf '%s' "$prompt"; read -r answer || true
  elif [[ -r /dev/tty ]]; then
    printf '%s' "$prompt" >/dev/tty; IFS= read -r answer </dev/tty || true
  fi
  printf '%s' "$answer"
}

configure_model_choice() {
  local kind="$1" repo_var="$2" file_var="$3" choice path repo file
  [[ -n "${!repo_var:-}" || -n "${!file_var:-}" ]] && return 0
  choice="$(ask_tty "${kind} GGUF (Enter for automatic choice; paste HF repo/file or public URL): ")"
  [[ -z "$choice" ]] && return 0
  if [[ "$choice" == https://huggingface.co/*/resolve/* ]]; then
    path="${choice#https://huggingface.co/}"
    repo="${path%%/resolve/*}"
    file="${path#*/resolve/}"
    file="${file#*/}"
  elif [[ "$choice" == */*.gguf ]]; then
    repo="${choice%%/*}"; file="${choice#*/}"
  elif [[ "$choice" == */* ]]; then
    repo="$choice"; file=""
  else
    say "[setup] Unrecognized model choice; using the automatic model." >&2
    return 0
  fi
  export "$repo_var=$repo"
  [[ -n "$file" ]] && export "$file_var=$file"
  say "[setup] ${kind}: ${repo}${file:+ :: $file}" >&2
}

setup_cuda() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 0
  fi
  say "[gpu] NVIDIA GPU detected:"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

  local nvcc_path=""
  if command -v nvcc >/dev/null 2>&1; then
    nvcc_path="$(command -v nvcc)"
  else
    for candidate in /usr/local/cuda/bin/nvcc /usr/local/cuda-*/bin/nvcc; do
      if [[ -x "$candidate" ]]; then nvcc_path="$candidate"; break; fi
    done
  fi

  if [[ -z "$nvcc_path" && "${INSTALL_CUDA_TOOLKIT:-1}" == "1" && "${COLAB_RELEASE_TAG:-}" != "" ]]; then
    say "[gpu] CUDA compiler not found; trying to install the Colab CUDA toolkit..."
    if apt-get update -qq && apt-get install -y -qq nvidia-cuda-toolkit; then
      nvcc_path="$(command -v nvcc || true)"
    else
      say "[gpu] CUDA toolkit install failed; the runtime will report CPU fallback." >&2
    fi
  fi

  if [[ -n "$nvcc_path" ]]; then
    export CUDA_HOME="${CUDA_HOME:-$(dirname "$(dirname "$nvcc_path")")}" 
    export PATH="$(dirname "$nvcc_path"):$PATH"
    export LLAMA_GPU_LAYERS="${LLAMA_GPU_LAYERS:-99}"
    export SOVEREIGN_CUDA_BUILD="1"
    say "[gpu] CUDA compiler: $nvcc_path"
    "$nvcc_path" --version | tail -n 1 || true
    say "[gpu] llama.cpp will be built with CUDA and all model layers offloaded."
  else
    say "[gpu] GPU found but nvcc is unavailable; llama.cpp may fall back to CPU." >&2
    say "[gpu] To require CUDA, rerun with INSTALL_CUDA_TOOLKIT=1 or install nvcc first." >&2
  fi
}

install_python_if_missing

if [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  PLATFORM="wsl"
elif [[ -n "${COLAB_RELEASE_TAG:-}" ]] || [[ -d /content/sample_data ]]; then
  PLATFORM="colab"
elif [[ -n "${REPL_ID:-}" || -n "${REPLIT_DEV_DOMAIN:-}" || -n "${REPL_OWNER:-}" ]]; then
  PLATFORM="replit"
else
  PLATFORM="linux"
fi
say "[platform] $PLATFORM"

command -v free >/dev/null 2>&1 && say "[resources] RAM: $(free -h | awk '/^Mem:/ {print $2 " total, " $7 " available"}')"
say "[resources] Disk: $(df -h "$ROOT" | awk 'NR==2 {print $4 " free"}')"
setup_cuda

if [[ "$PLATFORM" == "replit" ]]; then
  export ENABLE_COMPUTER="${ENABLE_COMPUTER:-false}"
  export LLAMA_GPU_LAYERS="${LLAMA_GPU_LAYERS:-0}"
  say "[setup] Replit profile: CPU mode, computer-use disabled, ngrok disabled."
fi

if [[ "$PLATFORM" == "replit" || "${SOVEREIGN_CHOOSE_MODELS:-0}" == "1" ]]; then
  configure_model_choice "Reasoning" SOVEREIGN_REASONING_REPO SOVEREIGN_REASONING_FILE
  configure_model_choice "Coding" SOVEREIGN_CODER_REPO SOVEREIGN_CODER_FILE
fi

NO_TUNNEL=0
if [[ -z "${NGROK_TOKEN:-}" && -z "${NGROK_AUTHTOKEN:-}" && "$PLATFORM" != "replit" ]]; then
  token="$(ask_tty 'ngrok token (optional; press Enter for private/local mode): ')"
  if [[ -n "$token" ]]; then export NGROK_TOKEN="$token"; else NO_TUNNEL=1; fi
else
  NO_TUNNEL=1
fi

ARGS=("$@")
if [[ "$NO_TUNNEL" -eq 1 ]]; then ARGS+=("--no-tunnel"); say "[setup] No ngrok token supplied; private/local mode."; fi

exec python3 "$ROOT/core/sovereign_hive_factory.py" --bootstrap --run-free "${ARGS[@]}"
