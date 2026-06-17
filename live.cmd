@echo off
REM One-click live sector-rotation dashboard.
REM Starts the local server (which pulls fresh market data) and opens the browser.
cd /d "%~dp0"
py -3.11 serve_rrg.py
pause
