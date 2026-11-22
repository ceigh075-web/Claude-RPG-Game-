@echo off
rem Runs Kindred Roads from source. Needs Python 3.11+ from https://www.python.org (tick "Add python.exe to PATH").
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% -c "import pygame" >nul 2>nul
if not %errorlevel%==0 (
  echo Installing pygame-ce (first run only)...
  %PY% -m pip install --user -r requirements.txt
)
%PY% main.py
if not %errorlevel%==0 pause
