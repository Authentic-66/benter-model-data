@echo off
title Process CT Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\CharlesTown\ct-results-2026"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%results-logs\" mkdir "%SCRIPTS%results-logs"
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_CT_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results CT [%TODAY%]' -Encoding UTF8"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
echo No result PDF found in: %RESDIR% >> "%LOGFILE%"
pause & exit /b 1

:run
echo Processing CT: %PDF%
echo Processing CT: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; py -u '%SCRIPTS%process_results.py' '%RESDIR%\%PDF%' CT 2>&1 | ForEach-Object { Write-Host $_; $_ } | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo.
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
