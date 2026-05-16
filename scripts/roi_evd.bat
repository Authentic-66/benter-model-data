@echo off
title ROI Tracker - EVD
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Evangeline Downs\evd-results-2026"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%roi-logs\" mkdir "%SCRIPTS%roi-logs"
set "LOGFILE=%SCRIPTS%roi-logs\ROI_EVD_%TODAY%.txt"
echo ROI Tracker - EVD  [%TODAY%] > "%LOGFILE%"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_EVD_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :gotpicks
)
echo No picks_EVD_*.txt found in scripts folder. Run parse_evd.bat first.
echo No picks_EVD_*.txt found in scripts folder. Run parse_evd.bat first. >> "%LOGFILE%"
pause & exit /b 1

:gotpicks
:: Extract date from picks filename: picks_EVD_20260515.txt -> 20260515
set "PICKSDATE=%PICKS:picks_EVD_=%"
set "PICKSDATE=%PICKSDATE:.txt=%"

for /f "delims=" %%f in ('powershell -NoProfile -Command "Get-ChildItem '%RESDIR%\*.pdf' -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime.ToString('yyyyMMdd') -eq $env:PICKSDATE } | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name"') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found for picks date %PICKSDATE% in: %RESDIR%
echo No result PDF found for picks date %PICKSDATE% in: %RESDIR% >> "%LOGFILE%"
pause & exit /b 1

:run
echo ROI: %PICKS% + %PDF%
echo ROI: %PICKS% + %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%PICKS%" "%RESDIR%\%PDF%" 2>&1 | powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $input | Tee-Object -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo.
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
