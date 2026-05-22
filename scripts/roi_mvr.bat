@echo off
title ROI Tracker - MVR
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Mahoning Valley\mvr-2026-results"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%roi-logs\" mkdir "%SCRIPTS%roi-logs"
set "LOGFILE=%SCRIPTS%roi-logs\ROI_MVR_%TODAY%.txt"
echo ROI Tracker - MVR  [%TODAY%] > "%LOGFILE%"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_MVR_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :gotpicks
)
echo No picks_MVR_*.txt found in scripts folder. Run parse_mvr.bat first.
echo No picks_MVR_*.txt found in scripts folder. Run parse_mvr.bat first. >> "%LOGFILE%"
pause & exit /b 1

:gotpicks
for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
echo No result PDF found in: %RESDIR% >> "%LOGFILE%"
pause & exit /b 1

:run
echo ROI: %PICKS% + %PDF%
echo ROI: %PICKS% + %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%PICKS%" "%RESDIR%\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo.
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
