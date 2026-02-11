@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "ENTRY=%SCRIPT_DIR%rpgmv_viewer.py"

if not exist "%ENTRY%" (
  echo [ERROR] Entry script not found: %ENTRY%
  exit /b 1
)

if "%~1"=="" (
  call :RUN_VIEWER
  exit /b %errorlevel%
)

set "OVERALL=0"

:ARG_LOOP
if "%~1"=="" goto ARG_DONE

call :PROCESS_ONE "%~1"
if errorlevel 1 set "OVERALL=1"
shift
goto ARG_LOOP

:ARG_DONE
echo.
if "%OVERALL%"=="0" (
  echo Done.
) else (
  echo Some entries failed.
)

pause
exit /b %OVERALL%

:RUN_VIEWER
echo [INFO] No EXE argument detected, starting viewer...

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%ENTRY%"
  exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%ENTRY%"
  exit /b %errorlevel%
)

echo [FAIL] Failed to run Python. Please install py launcher or python.
pause
exit /b 1

:PROCESS_ONE
set "EXE=%~f1"

if "%~1"=="" exit /b 1

if /I not "%~x1"==".exe" (
  echo [SKIP] Not an EXE file: %EXE%
  exit /b 1
)

if not exist "%EXE%" (
  echo [FAIL] File not found: %EXE%
  exit /b 1
)

set "MV1=%~dp1www\data\MapInfos.json"
set "MV2=%~dp1data\MapInfos.json"
set "VX1=%~dp1Data\MapInfos.rvdata2"
set "VX2=%~dp1Data\Map*.rvdata2"
set "VX3=%~dp1Data\MapInfos.rvdata"
set "VX4=%~dp1Data\Map*.rvdata"
set "HINT="

if exist "%MV1%" set "HINT=MV/MZ (www\\data)"
if not defined HINT if exist "%MV2%" set "HINT=MV/MZ (data)"
if not defined HINT if exist "%VX1%" set "HINT=VX Ace (Data\\*.rvdata2)"
if not defined HINT if exist "%VX2%" set "HINT=VX Ace (Data\\Map*.rvdata2)"
if not defined HINT if exist "%VX3%" set "HINT=VX (Data\\*.rvdata)"
if not defined HINT if exist "%VX4%" set "HINT=VX (Data\\Map*.rvdata)"
if not defined HINT if exist "%~dp1Game.rgss3a" set "HINT=VX Ace archive (Game.rgss3a)"
if not defined HINT if exist "%~dp1Game.rgss2a" set "HINT=VX archive (Game.rgss2a)"
if not defined HINT if exist "%~dp1Game.rgssad" set "HINT=VX archive (Game.rgssad)"

if not defined HINT (
  echo [FAIL] Supported data marker not found for: %EXE%
  echo        Checked:
  echo        - %~dp1www\data\MapInfos.json
  echo        - %~dp1data\MapInfos.json
  echo        - %~dp1Data\MapInfos.rvdata2 / Map*.rvdata2
  echo        - %~dp1Data\MapInfos.rvdata / Map*.rvdata
  echo        - %~dp1Game.rgss3a / Game.rgss2a / Game.rgssad
  exit /b 1
)

echo [INFO] EXE : %EXE%
echo [INFO] DETECTED: %HINT%

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%ENTRY%" --register-exe "%EXE%"
  if not errorlevel 1 (
    echo [OK] Registered: %EXE%
    exit /b 0
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%ENTRY%" --register-exe "%EXE%"
  if not errorlevel 1 (
    echo [OK] Registered: %EXE%
    exit /b 0
  )
)

echo [FAIL] Failed to run Python. Please install py launcher or python.
exit /b 1
