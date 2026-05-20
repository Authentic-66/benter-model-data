@echo off
title Process FP Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Fairmount Park\fp-results-2026"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%results-logs\" mkdir "%SCRIPTS%results-logs"
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_FP_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results FP [%TODAY%]' -Encoding UTF8"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
echo No result PDF found in: %RESDIR% >> "%LOGFILE%"
pause & exit /b 1

:run
echo Processing FP: %PDF%
echo Processing FP: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%process_results.py" "%RESDIR%\%PDF%" FP > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo.
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
