@echo off
title Process CT Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\CharlesTown\ct-results-2026"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
pause & exit /b 1

:run
echo Processing CT: %PDF%
echo.
py "%SCRIPTS%process_results.py" "%RESDIR%\%PDF%" CT
echo.
pause
