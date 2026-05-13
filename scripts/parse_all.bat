@echo off
title Parse All Tracks
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%handicap-logs\" mkdir "%SCRIPTS%handicap-logs"

echo.
echo ########################################################################
echo   BENTER MODEL -- PARSE ALL TRACKS
echo ########################################################################

:: ── CHARLES TOWN (CT) ────────────────────────────────────────────────────
echo.
echo ========================================================================
echo   CHARLES TOWN (CT)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\CharlesTown\ct-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :ct_run
)
echo   No PP file found - skipping
goto :fp_section

:ct_run
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\CharlesTown\ct-pps-files\%PDF%" CT
call :log_picks CT

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
:fp_section
echo.
echo ========================================================================
echo   FAIRMOUNT PARK (FP)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fairmount Park\fp-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fp_run
)
echo   No PP file found - skipping
goto :gp_section

:fp_run
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Fairmount Park\fp-pps-files\%PDF%" FP
call :log_picks FP

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
:gp_section
echo.
echo ========================================================================
echo   GULFSTREAM PARK (GP)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Gulfstream Park\gp-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :gp_run
)
echo   No PP file found - skipping
goto :evd_section

:gp_run
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Gulfstream Park\gp-pps-files\%PDF%" GP
call :log_picks GP

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
:evd_section
echo.
echo ========================================================================
echo   EVANGELINE DOWNS (EVD)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Evangeline Downs\evd-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :evd_run
)
echo   No PP file found - skipping
goto :done

:evd_run
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Evangeline Downs\evd-pps-files\%PDF%" EVD
call :log_picks EVD

:done
echo.
echo ########################################################################
echo   ALL TRACKS PARSED
echo ########################################################################
echo.
pause
goto :eof

:log_picks
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_%1_*.txt" 2^>nul') do (
    copy /y "%SCRIPTS%%%f" "%SCRIPTS%handicap-logs\HANDICAP_%1_%TODAY%.txt" > nul
    echo   Picks logged: handicap-logs\HANDICAP_%1_%TODAY%.txt
    exit /b
)
echo   No picks file found for %1
exit /b
