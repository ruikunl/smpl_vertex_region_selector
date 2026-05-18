#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

"$PYTHON_BIN" -m smpl_vertex_region_selector.demo_data --output-dir outputs/demo
"$PYTHON_BIN" -m smpl_vertex_region_selector.preview_overlay \
  --region-map outputs/demo/region_map.demo.json \
  --vertex-map outputs/demo/demo.vertex_map.npz \
  --output-dir outputs/demo/preview \
  --write-summary

echo "Demo preview written to $ROOT/outputs/demo/preview"
