#!/bin/sh
cd "$(dirname "$0")/backend"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
