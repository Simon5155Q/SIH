@echo off
cd /d %~dp0legal-metrology-api
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
