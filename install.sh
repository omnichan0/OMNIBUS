#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SOVEREIGN_REPO_ROOT="$ROOT"

# Beginner-friendly launcher. It detects the host, installs what it safely can,
# shows the available disk/RAM, and lets the user choose smaller GGUFs on
# constrained hosts such as Replit.
install_python_if_missing() {
  command -v python3 >/dev/null 2>&1 && return 0
  echo "[setup] Python 3 was not found. Trying to install it automatically..."
  if command -v apt-get >/dev/null 2>&1; then
    if [ "$(id -u)" -eq 0 ]; then
      apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv
    elif command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv
    else
      echo "Please install Python 3.10+ and run this file again."; exit 1
    fi
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache python3 py3-pip py3-virtualenv
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-virtualenv
  else
    echo "No supported package manager was found. Please install Python 3.10+ and run again."; exit 1
  fi
}

ask_tty() {
  local prompt="$1" answer=""
  if [[ -t 0 ]]; then
    printf "%s" "$prompt"
    read -r answer || true
  elif [[ -r /dev/tty ]]; then
    printf "%s" "$prompt" >/dev/tty
    IFS= read -r answer </dev/tty || true
  fi
  printf "%s" "$answer"
}

# Accept either a Hugging Face repo/file choice or a full public resolve URL.
# The runtime then resolves/downloads the file normally; HF_TOKEN is not needed
# for public GGUFs.
configure_model_choice() {
  local kind="$1" repo_var="$2" file_var="$3" current_repo="$4"
  local choice repo file path
  [[ -n "${!repo_var:-}" || -n "${!file_var:-}" ]] && return 0
  choice="$(ask_tty "${kind} GGUF (Enter for automatic choice; paste HF repo/file or URL): ")"
  [[ -z "$choice" ]] && return 0
  if [[ "$choice" == https://huggingface.co/*/resolve/*/* ]]; then
    path="${choice#https://huggingface.co/}"
    repo="${path%%/resolve/*}"
    file="${path#*/resolve/}"
    file="${file#*/}"
  elif [[ "$choice" == */*.gguf ]]; then
    repo="${choice%%/*}"
    file="${choice#*/}":
  elif [[ "$choice" == */* ]]; then
    repo="$choice"
    file=""
  else
    echo "[setup] Ignoring unrecognised model choice; using the automatic choice." >&2
    return 0
  fi
  export "$repo_var=$repo"
  [[ -n "$file" ]] && export "$file_var=$file"
  echo "[setup] ${kind}: ${repo}${file:+ :: $file}" >&2
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
echo "[platform] $PLATFORM"

if command -v free >/dev/null 2>&1; then
  echo "[resources] RAM: $(free -h | awk '/^Mem:/ {print $2 " total, " $7 " available"}')"
fi
echo "[resources] Disk: $(df -h "$ROOT" | awk 'NR==2 {print $4 " free"}')"

# Replit normally supplies its own public URL and is commonly CPU-only.
if [[ "$PLATFORM" == "replit" ]]; then
  export ENABLE_COMPUTER="${ENABLE_COMPUTER:-false}"
  export LLAMA_GPU_LAYERS="${LLAMA_GPU_LAYERS:-0}"
  echo "[setup] Replit profile: private ngrok disabled, computer service disabled, CPU inference selected."
fi

if [[ "$PLATFORM" == "replit" || "${SOVEREIGN_CHOOSE_MODELS:-0}" == "1" ]]; then
  configure_model_choice "Reasoning" SOVEREIGN_REASONING_REPO SOVEREIGN_REASONING_FILE "${SOVEREIGN_REASONING_REPO:-}"
  configure_model_choice "Coding" SOVEREIGN_CODER_REPO SOVEREIGN_CODER_FILE "${SOVEREIGN_CODER_REPO:-}"
fi

NO_TUNNEL=0
if [[ -z "${NGROK_TOKEN:-}" && -z "${NGROK_AUTHTOKEN:-}" && "$PLATFORM" != "replit" ]]; then
  token="$(ask_tty "ngrok token (optional; press Enter for private/local mode): ")"
  if [[ -n "$token" ]]; then export NGROK_TOKEN="$token"; else NO_TUNNEL=1; fi
else
  NO_TUNNEL=1
fi

ARGS=("$@")
[[ "$NO_TUNNEL" -eq 1 ]] && ARGS+=("--no-tunnel")
[[ "$NO_TUNNEL" -eq 1 ]] && echo "[setup] No ngrok token supplied; starting in private/local mode."

exec python3 "$ROOT/core/sovereign_hive_factory.py" --bootstrap --run-free "${ARGS[@]}"
