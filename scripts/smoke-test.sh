#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/bootstrap/platform.py"
python3 "$ROOT/core/sovereign_hive_factory.py" --smoke-test
