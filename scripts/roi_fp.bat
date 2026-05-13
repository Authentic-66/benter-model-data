@echo off
title ROI Tracker - FP
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\Fairmount Park\fp-results-2026"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FP_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :gotpicks
)
echo No picks_FP_*.txt found in scripts folder. Run parse_fp.bat first.
pause & exit /b 1

:gotpicks
for /f "delims=" %%f in ('dir /b /o-d /a-d "%RESDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No result PDF found in: %RESDIR%
pause & exit /b 1

:run
echo ROI: %PICKS% + %PDF%
echo.
py "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%PICKS%" "%RESDIR%\%PDF%"
echo.
pause
