#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SOVEREIGN_REPO_ROOT="$ROOT"

# Beginner-friendly launcher: detect the environment, install the small
# prerequisites we can safely install, and hand everything to the
# self-healing runtime bootstrap.
install_python_if_missing() {
  if command -v python3 >/dev/null 2>&1; then
    return 0
  fi

  echo "[setup] Python 3 was not found. Trying to install it automatically..."
  if command -v apt-get >/dev/null 2>&1; then
    if [ "$(id -u)" -eq 0 ]; then
      apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv
    elif command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv
    else
      echo "Please install Python 3.10+ and run this file again."
      exit 1
    fi
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache python3 py3-pip py3-virtualenv
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-virtualenv
  else
    echo "No supported package manager was found. Please install Python 3.10+ and run again."
    exit 1
  fi
}

install_python_if_missing

if [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  echo "[platform] Windows/WSL Linux environment detected"
elif [[ -n "${COLAB_RELEASE_TAG:-}" ]] || [[ -d /content/sample_data ]]; then
  echo "[platform] Google Colab detected"
elif [[ "$(uname -s)" == "Linux" ]]; then
  echo "[platform] Linux detected"
else
  echo "[platform] $(uname -s) detected"
fi

# Hugging Face is an optional agent capability, not a required GGUF download
# credential. GGUF files use public Hugging Face resolve URLs by default.
# Set HF_TOKEN in the environment only when an agent tool or gated resource
# actually requires it.
NO_TUNNEL=0
if [[ -z "${NGROK_TOKEN:-}" && -z "${NGROK_AUTHTOKEN:-}" && -t 0 ]]; then
  printf "ngrok token (optional; press Enter for private/local mode): "
  read -r NGROK_INPUT || true
  if [[ -n "${NGROK_INPUT:-}" ]]; then
    export NGROK_TOKEN="$NGROK_INPUT"
  else
    NO_TUNNEL=1
  fi
elif [[ -z "${NGROK_TOKEN:-}" && -z "${NGROK_AUTHTOKEN:-}" ]]; then
  # Non-interactive Colab cells start safely without a public tunnel unless a
  # token was explicitly provided.
  NO_TUNNEL=1
fi

ARGS=("$@")
if [[ "$NO_TUNNEL" -eq 1 ]]; then
  ARGS+=("--no-tunnel")
  echo "[setup] No ngrok token supplied; starting in private/local mode."
fi

exec python3 "$ROOT/core/sovereign_hive_factory.py" --bootstrap --run-free "${ARGS[@]}"
