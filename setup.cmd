@echo off
setlocal
cd /d "%~dp0"
set "TASK_PYTHON=.venv\Scripts\python.exe"
set "TASK_BASE="
set "PIP_CACHE_DIR=%CD%\.cache\pip"
set "CHECK_PYTHON=import struct, sys; sys.exit(sys.version_info[:2] != (3, 12) or struct.calcsize('P') != 8)"

if exist "%TASK_PYTHON%" (
  "%TASK_PYTHON%" -I -c "%CHECK_PYTHON%" >nul 2>&1
  if errorlevel 1 (
    echo The existing .venv uses an unavailable or incompatible Python. Rename it, then rerun setup.cmd.
    exit /b 1
  )
  for /f "delims=" %%I in ('.venv\Scripts\python.exe -I -c "import sys; print(sys._base_executable)"') do set "TASK_BASE=%%I"
  goto create_venv
)
python -I -c "%CHECK_PYTHON%" >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('python -I -c "import sys; print(sys._base_executable)"') do set "TASK_BASE=%%I"
  goto create_venv
)
py -3.12 -I -c "%CHECK_PYTHON%" >nul 2>&1
if errorlevel 1 (
  echo Install 64-bit Python 3.12 and make it available through python or py -3.12.
  exit /b 1
)
py -3.12 -I -m venv .venv
goto install

:create_venv
if not defined TASK_BASE (
  echo Could not locate the base Python 3.12 executable.
  exit /b 1
)
"%TASK_BASE%" -I -m venv .venv

:install
if errorlevel 1 exit /b 1
"%TASK_PYTHON%" -I -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
"%TASK_PYTHON%" -I -m pip check
exit /b %errorlevel%
