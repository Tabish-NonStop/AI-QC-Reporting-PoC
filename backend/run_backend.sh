#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -c "import yaml; print('Loaded config OK')" >/dev/null

HOST=$(python -c "import yaml;print(yaml.safe_load(open('config.yaml'))['host'])")
PORT=$(python -c "import yaml;print(yaml.safe_load(open('config.yaml'))['port'])")

uvicorn app:app --host "$HOST" --port "$PORT" --reload