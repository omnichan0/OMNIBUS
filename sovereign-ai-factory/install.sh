#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SOVEREIGN_REPO_ROOT="$ROOT"

echo "============================================================"
echo " SOVEREIGN AI FACTORY"
echo " Adaptive bootstrap"
echo "============================================================"

if [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  echo "[platform] Windows/WSL Linux environment detected"
elif [[ -n "${COLAB_RELEASE_TAG:-}" ]] || [[ -d /content/sample_data ]]; then
  echo "[platform] Google Colab detected"
elif [[ "$(uname -s)" == "Linux" ]]; then
  echo "[platform] Linux detected"
else
  echo "[platform] $(uname -s) detected"
fi

command -v python3 >/dev/null 2>&1 || {
  echo "Python 3 is required. Install Python 3.10+ and rerun."
  exit 1
}

# Secrets are runtime inputs; never commit them to this repository.
if [[ -z "${HF_TOKEN:-}" ]]; then
  echo
  echo "[!] HF_TOKEN is not present in the environment."
  echo "    Configure it in your runtime secret store, then rerun."
  echo "    Colab: use Colab Secrets named HF_TOKEN."
  echo "    Linux: export HF_TOKEN='...'"
  echo
fi

if [[ -z "${NGROK_TOKEN:-}" && -z "${NGROK_AUTHTOKEN:-}" ]]; then
  echo
  echo "[!] NGROK_TOKEN is not present."
  echo "    The factory can run locally, but a public URL requires ngrok."
  echo "    Colab: use a secret named NGROK_TOKEN."
  echo "    Linux: export NGROK_TOKEN='...'"
  echo
fi

exec python3 "$ROOT/core/sovereign_hive_factory.py" --bootstrap --run-free "$@"
