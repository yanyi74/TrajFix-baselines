#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
bash "$TRAJFIX_ROOT/scripts/setup_vendor.sh"
cd "$TRAJFIX_ROOT"
mkdir -p "$TRAJFIX_ROOT/results" "$TRAJFIX_ROOT/data"
runtime="${TRAJFIX_VENV:-/tmp/trajfix-baselines-venv}"
if [[ ! -x "$runtime/bin/python" ]]; then
  python3 -m venv "$runtime"
fi
if [[ ! -e "$TRAJFIX_ROOT/.venv" && ! -L "$TRAJFIX_ROOT/.venv" ]]; then
  ln -s "$runtime" "$TRAJFIX_ROOT/.venv"
fi
if [[ ! -e "$TRAJFIX_ROOT/vendor/HarnessFix/.venv" ]]; then
  ln -s "$runtime" "$TRAJFIX_ROOT/vendor/HarnessFix/.venv"
fi
if [[ -s "$TRAJFIX_ROOT/requirements.lock.txt" ]]; then
  "$runtime/bin/python" -m pip install -r "$TRAJFIX_ROOT/requirements.lock.txt"
else
  "$runtime/bin/python" -m pip install \
    -r "$TRAJFIX_ROOT/vendor/HarnessFix/requirements.txt" \
    -e "$TRAJFIX_ROOT/vendor/HarnessFix/task_agent/mini-swe-agent" swebench==4.1.0
fi
"$runtime/bin/python" -m pip check
