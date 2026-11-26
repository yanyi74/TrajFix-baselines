#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$TRAJFIX_ROOT/vendor/HarnessFix"
# Default is upstream dry-run; 'run' executes a real bounded smoke experiment.
mode="${1:-dry-run}"
if [[ "$mode" != run && "$mode" != dry-run ]]; then
  echo 'Usage: bash scripts/run_smoke_pipeline.sh [dry-run|run]' >&2
  exit 2
fi
args=(--dry-run)
if [[ "$mode" == run ]]; then
  : "${TRAJFIX_MODEL:?Set TRAJFIX_MODEL to a configured LiteLLM model name}"
  python "$TRAJFIX_ROOT/scripts/preflight.py" > "$TRAJFIX_ROOT/results/preflight.json"
  python -c 'import json,sys; sys.exit(not json.load(open(sys.argv[1]))["ready_for_real_run"])' "$TRAJFIX_ROOT/results/preflight.json"
  args=()
fi
exec python run_pipeline_swe.py \
  --model "${TRAJFIX_MODEL:-openai/gpt-5-mini}" \
  --analysis-model "${TRAJFIX_ANALYSIS_MODEL:-${TRAJFIX_MODEL:-openai/gpt-5-mini}}" \
  --workers 1 --cost-limit "${TRAJFIX_COST_LIMIT:-0.5}" --max-iterations 1 \
  --train-dir "$TRAJFIX_ROOT/data/smoke_dev" \
  --val-dir "$TRAJFIX_ROOT/data/smoke_val" \
  --run-label smoke_20261126 "${args[@]}"
