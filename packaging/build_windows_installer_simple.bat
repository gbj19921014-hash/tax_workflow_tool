@echo off
setlocal

set "TOOL_DIR=%~dp0.."
for %%I in ("%TOOL_DIR%") do set "TOOL_DIR=%%~fI"
set "ROOT_DIR=%TOOL_DIR%\.."
for %%I in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fI"
set "LOG_FILE=%ROOT_DIR%\build_windows_installer.log"

echo Building installer. Please keep this window open.
echo Tool folder: %TOOL_DIR%
echo Root folder: %ROOT_DIR%
echo Log file: %LOG_FILE%
echo.

cd /d "%ROOT_DIR%"

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found.
  echo Please reinstall Python and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

where powershell >nul 2>nul
if errorlevel 1 (
  echo ERROR: PowerShell was not found.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%TOOL_DIR%\packaging\build_windows_installer.ps1" > "%LOG_FILE%" 2>&1

if errorlevel 1 (
  echo.
  echo ERROR: Build failed.
  echo Please send me the last lines of this log:
  echo %LOG_FILE%
  echo.
  type "%LOG_FILE%"
  pause
  exit /b 1
)

echo.
echo Done. Please check:
echo %ROOT_DIR%\dist\installer\A1-A3税务工作流安装包.exe
pause
