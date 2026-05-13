@echo off
title ROI Tracker - CT
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "RESDIR=%BASE%\CharlesTown\ct-results-2026"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_CT_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :gotpicks
)
echo No picks_CT_*.txt found in scripts folder. Run parse_ct.bat first.
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
