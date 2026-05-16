@echo off
title ROI Tracker - FP
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Fairmount Park\fp-results-2026"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%roi-logs\" mkdir "%SCRIPTS%roi-logs"
set "LOGFILE=%SCRIPTS%roi-logs\ROI_FP_%TODAY%.txt"
echo ROI Tracker - FP  [%TODAY%] > "%LOGFILE%"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FP_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :gotpicks
)
echo No picks_FP_*.txt found in scripts folder. Run parse_fp.bat first.
echo No picks_FP_*.txt found in scripts folder. Run parse_fp.bat first. >> "%LOGFILE%"
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
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%roi_tracker.py' '%SCRIPTS%%PICKS%' '%RESDIR%\%PDF%' 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo.
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
