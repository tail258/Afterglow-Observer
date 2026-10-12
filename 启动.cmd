@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
where py.exe >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0app.py" %*
goto done
:use_python
python "%~dp0app.py" %*
:done
if errorlevel 1 pause
