#!/usr/bin/env bash
# Source this file; runtime dependencies live on local disk because the shared
# filesystem returned I/O errors during venv creation.
TRAJFIX_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TRAJFIX_ROOT
export MSWEA_GLOBAL_CONFIG_DIR="$TRAJFIX_ROOT/.runtime/mini-config"
export MSWEA_SILENT_STARTUP=1
export HF_HOME="$TRAJFIX_ROOT/.runtime/huggingface"
export LITELLM_LOCAL_MODEL_COST_MAP=True
export PYTHONPATH="$TRAJFIX_ROOT/vendor/HarnessFix${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$TRAJFIX_ROOT/.venv/bin:$PATH"
if [[ -x /tmp/trajfix-docker/bin/docker ]]; then
  export PATH="/tmp/trajfix-docker/bin:$PATH"
  export DOCKER_HOST=unix:///tmp/trajfix-docker/run/docker.sock
fi
