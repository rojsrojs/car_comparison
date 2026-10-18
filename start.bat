@echo off
rem Double-click to start the car comparison app. Close this window to stop it.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% app.py
if errorlevel 1 pause
