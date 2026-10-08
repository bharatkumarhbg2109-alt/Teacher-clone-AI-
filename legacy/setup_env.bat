@echo off
echo [SETUP] Creating isolated Python virtual environment...
python -m venv --system-site-packages "%~dp0backend\.venv"
call "%~dp0backend\.venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r "%~dp0backend\requirements.txt"
echo [SETUP] Backend venv ready.
pause
