@echo off
title Process FP Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Fairmount Park\fp-results-2026"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
pause & exit /b 1

:run
echo Processing FP: %PDF%
echo.
py "%SCRIPTS%process_results.py" "%RESDIR%\%PDF%" FP
echo.
pause
