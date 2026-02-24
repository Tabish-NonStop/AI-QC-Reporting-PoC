#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# If you need to point to a different backend:
# export STREAMLIT_SECRETS='{"BACKEND_URL":"http://127.0.0.1:8000"}'

streamlit run streamlit_app.py