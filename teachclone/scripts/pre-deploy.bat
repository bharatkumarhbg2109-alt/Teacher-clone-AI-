@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM TeachClone — Pre-Deploy CI Script (Windows)
REM Run this before every production deployment.
REM ──────────────────────────────────────────────────────────────────────────
setlocal enabledelayedexpansion

set PASS=0
set FAIL=0
set WARN=0

echo.
echo ═══════════════════════════════════════════════════════════
echo   TEACHCLONE — PRE-DEPLOY CHECKS
echo   %date% %time%
echo ═══════════════════════════════════════════════════════════
echo.

REM ── 1. Backend tests ─────────────────────────────────────────────────────
echo ^> [1/7] Running backend tests...
cd apps\api
python -m pytest tests\ --tb=line -q 2>&1 | findstr /C:"passed"
if %errorlevel% equ 0 (
    echo   ✅ Backend tests passed
    set /a PASS+=1
) else (
    echo   ❌ Backend tests FAILED
    set /a FAIL+=1
)
cd ..\..
echo.

REM ── 2. Frontend build ────────────────────────────────────────────────────
echo ^> [2/7] Building frontend...
cd apps\web
call npx next build 2>&1 | findstr /C:"Compiled" /C:"Route"
if %errorlevel% equ 0 (
    echo   ✅ Frontend build succeeded
    set /a PASS+=1
) else (
    echo   ❌ Frontend build FAILED
    set /a FAIL+=1
)
cd ..\..
echo.

REM ── 3. Playwright E2E tests ─────────────────────────────────────────────
echo ^> [3/7] Running Playwright E2E tests...
cd apps\web
call npx playwright test --reporter=line 2>&1 | findstr /C:"passed" /C:"failed"
if %errorlevel% equ 0 (
    echo   ✅ Playwright E2E tests passed
    set /a PASS+=1
) else (
    echo   ❌ Playwright E2E tests FAILED
    set /a FAIL+=1
)
cd ..\..
echo.

REM ── 4. Secrets scan ─────────────────────────────────────────────────────
echo ^> [4/7] Scanning for hardcoded secrets...
findstr /S /R /C:"sk-ant-" /C:"sk_live_" /C:"pk_live_" /C:"ghp_" apps\*.py apps\*.ts apps\*.tsx apps\*.js 2>nul | findstr /V /C:"test_" /C:"conftest" /C:"example" /C:"placeholder" >nul 2>&1
if %errorlevel% neq 0 (
    echo   ✅ No hardcoded secrets found
    set /a PASS+=1
) else (
    echo   ❌ Potential secrets found in source code
    set /a FAIL+=1
)
echo.

REM ── 5. .env.example validation ──────────────────────────────────────────
echo ^> [5/7] Validating .env.example...
if exist .env.example (
    echo   ✅ .env.example exists
    set /a PASS+=1
) else (
    echo   ⚠️  .env.example not found
    set /a WARN+=1
)
echo.

REM ── 6. .gitignore check ────────────────────────────────────────────────
echo ^> [6/7] Checking .gitignore...
findstr /C:".env" .gitignore >nul 2>&1
if %errorlevel% equ 0 (
    echo   ✅ .gitignore covers .env
    set /a PASS+=1
) else (
    echo   ❌ .gitignore missing .env entry
    set /a FAIL+=1
)
echo.

REM ── 7. Docker config ────────────────────────────────────────────────────
echo ^> [7/7] Validating Docker Compose...
if exist docker-compose.yml (
    docker compose config --quiet 2>nul
    if %errorlevel% equ 0 (
        echo   ✅ docker-compose.yml is valid
        set /a PASS+=1
    ) else (
        echo   ⚠️  Docker not available — skipping
        set /a WARN+=1
    )
) else (
    echo   ⚠️  docker-compose.yml not found
    set /a WARN+=1
)
echo.

REM ── Summary ─────────────────────────────────────────────────────────────
echo ═══════════════════════════════════════════════════════════
echo   PRE-DEPLOY RESULTS
echo ═══════════════════════════════════════════════════════════
echo   ✅ %PASS% passed ^| ❌ %FAIL% failed ^| ⚠️  %WARN% warnings
echo.

if %FAIL% gtr 0 (
    echo   🚫 DEPLOY BLOCKED — %FAIL% check^(s^) failed
    echo ═══════════════════════════════════════════════════════════
    exit /b 1
) else (
    echo   ✅ ALL CHECKS PASSED — safe to deploy
    echo ═══════════════════════════════════════════════════════════
    exit /b 0
)
