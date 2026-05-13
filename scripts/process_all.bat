@echo off
title Process All Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

echo.
echo ########################################################################
echo   BENTER MODEL -- PROCESS ALL RESULTS
echo ########################################################################

:: ── CHARLES TOWN (CT) ────────────────────────────────────────────────────
echo.
echo ========================================================================
echo   CHARLES TOWN (CT)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\CharlesTown\ct-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :ct_run
)
echo   No result PDF found - skipping
goto :fp_section

:ct_run
echo   File: %PDF%
echo.
py "%SCRIPTS%process_results.py" "%BASE%\CharlesTown\ct-results-2026\%PDF%" CT

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
:fp_section
echo.
echo ========================================================================
echo   FAIRMOUNT PARK (FP)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fairmount Park\fp-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fp_run
)
echo   No result PDF found - skipping
goto :gp_section

:fp_run
echo   File: %PDF%
echo.
py "%SCRIPTS%process_results.py" "%BASE%\Fairmount Park\fp-results-2026\%PDF%" FP

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
:gp_section
echo.
echo ========================================================================
echo   GULFSTREAM PARK (GP)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Gulfstream Park\gp-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :gp_run
)
echo   No result PDF found - skipping
goto :evd_section

:gp_run
echo   File: %PDF%
echo.
py "%SCRIPTS%process_results.py" "%BASE%\Gulfstream Park\gp-results-2026\%PDF%" GP

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
:evd_section
echo.
echo ========================================================================
echo   EVANGELINE DOWNS (EVD)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Evangeline Downs\evd-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :evd_run
)
echo   No result PDF found - skipping
goto :done

:evd_run
echo   File: %PDF%
echo.
py "%SCRIPTS%process_results.py" "%BASE%\Evangeline Downs\evd-results-2026\%PDF%" EVD

:done
echo.
echo ########################################################################
echo   ALL TRACKS PROCESSED
echo ########################################################################
echo.
pause
