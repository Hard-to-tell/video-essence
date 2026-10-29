@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
if defined VIDEO_ESSENCE_PYTHON (
  start "" "%VIDEO_ESSENCE_PYTHON%" "%~dp0app\launch.py"
) else if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app\launch.py"
) else (
  echo Run the installation steps in README.md first.
  pause
)
