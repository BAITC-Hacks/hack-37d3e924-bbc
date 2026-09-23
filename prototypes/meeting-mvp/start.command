#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
elif [[ -x ../../work/venv/bin/python ]]; then
  PYTHON=../../work/venv/bin/python
else
  echo 'Сначала выполните ./setup.sh'
  exit 1
fi
if [[ -z "${MEETING_MODEL_DIR:-}" && -d ../../work/models ]]; then
  export MEETING_MODEL_DIR="$(cd ../../work/models && pwd)"
fi
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
exec "$PYTHON" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
