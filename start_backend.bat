@echo off
REM TeachClone backend (FastAPI :8000)
cd /d "%~dp0teachclone\apps\api"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
