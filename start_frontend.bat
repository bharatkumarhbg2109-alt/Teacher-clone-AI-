@echo off
REM TeachClone frontend (Next.js dev server on http://localhost:3000).
cd /d "%~dp0teachclone\apps\web"
call npm run dev
pause
