@echo off
REM AI Teacher Clone backend (FastAPI :8002)
call "%~dp0backend\.venv\Scripts\activate.bat"
cd /d "%~dp0backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
pause
