@echo off
title Process EVD Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Evangeline Downs\evd-results-2026"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%results-logs\" mkdir "%SCRIPTS%results-logs"
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_EVD_%TODAY%.txt"
echo Results EVD  [%TODAY%] > "%LOGFILE%"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
echo No result PDF found in: %RESDIR% >> "%LOGFILE%"
pause & exit /b 1

:run
echo Processing EVD: %PDF%
echo Processing EVD: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%process_results.py' '%RESDIR%\%PDF%' EVD 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo.
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
