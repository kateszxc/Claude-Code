@echo off
REM Double-click this file to start the E-com Brand Scraper.
REM The first time it installs everything (a few minutes). Close this window to stop it.
cd /d "%~dp0"
title E-com Brand Scraper
set URL=http://localhost:3000
echo === E-com Brand Scraper ===

REM This file must sit inside the ecom-scraper folder, next to "backend" and "frontend".
if not exist "backend\requirements.txt" (
  if exist "ecom-scraper\backend\requirements.txt" (
    cd ecom-scraper
  ) else (
    echo.
    echo This file needs the rest of the scraper files next to it.
    echo.
    echo 1. On the page that just opened, switch the branch to scraper-test,
    echo    then click Code, then Download ZIP.
    echo 2. Right-click the ZIP and choose Extract All.
    echo 3. Open the extracted folder, then the ecom-scraper folder,
    echo    and double-click "Start (Windows).bat" there.
    start "" https://github.com/kateszxc/Claude-Code
    pause
    exit /b 1
  )
)

python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python isn't installed. Install it from the page that just opened.
  echo IMPORTANT: tick "Add Python to PATH" during install. Then double-click this file again.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo.
  echo Node.js isn't installed. Install the LTS version from the page that just opened,
  echo then double-click this file again.
  start "" https://nodejs.org/
  pause
  exit /b 1
)

REM --- Backend (Python) ---
cd backend
if not exist .venv (
  echo First-time setup: installing Python packages, this takes a few minutes...
  python -m venv .venv
)
if not exist .venv\installed.txt (
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Installing Python packages failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
  echo ok> .venv\installed.txt
)
if not exist .env copy .env.example .env >nul
start "" /b .venv\Scripts\python.exe server.py >nul 2>&1

REM --- Frontend (Next.js) ---
cd ..\frontend
if not exist node_modules (
  echo First-time setup: installing the interface, this takes a minute...
  call npm install --no-audit --no-fund --loglevel=error
  if errorlevel 1 (
    echo.
    echo Installing the interface failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)

REM Open the browser as soon as the page is ready
start "" /b powershell -NoProfile -Command "for($i=0;$i -lt 180;$i++){try{Invoke-WebRequest -UseBasicParsing '%URL%' -TimeoutSec 5 | Out-Null; Start-Process '%URL%'; break}catch{Start-Sleep 1}}"

echo.
echo Starting... your browser will open %URL% in a moment.
echo Keep this window open while you use the scraper. Close it to stop.
echo.
call npm run dev
