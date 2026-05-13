@echo off
title Parse FP Past Performances
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "PPDIR=%BASE%\Fairmount Park\fp-pps-files"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%PPDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No PP file found in: %PPDIR%
pause & exit /b 1

:run
echo Parsing FP: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" FP
echo.

:: Save picks to handicap-logs
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%handicap-logs\" mkdir "%SCRIPTS%handicap-logs"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FP_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :log_picks
)
goto :done
:log_picks
copy /y "%SCRIPTS%%PICKS%" "%SCRIPTS%handicap-logs\HANDICAP_FP_%TODAY%.txt" > nul
echo Picks logged: handicap-logs\HANDICAP_FP_%TODAY%.txt
:done
echo.
pause
