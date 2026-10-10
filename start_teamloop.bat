@echo off
rem Start TeamLoop in this window (Ctrl+C stops it), then open http://127.0.0.1:8790
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
start "" http://127.0.0.1:8790
%PY% -m teamloop
