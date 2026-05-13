@echo off
title ROI Tracker - All Tracks
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

echo.
echo ########################################################################
echo   BENTER MODEL -- ROI ALL TRACKS
echo ########################################################################

:: ── CHARLES TOWN (CT) ────────────────────────────────────────────────────
echo.
echo ========================================================================
echo   CHARLES TOWN (CT)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_CT_*.txt" 2^>nul') do (
    set "CT_PICKS=%%f"
    goto :ct_picks_ok
)
echo   No picks_CT_*.txt found - run parse_ct.bat first
goto :fp_section

:ct_picks_ok
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\CharlesTown\ct-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :ct_run
)
echo   No result PDF found - skipping
goto :fp_section

:ct_run
echo   Picks: %CT_PICKS%
echo   Result: %PDF%
echo.
py "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%CT_PICKS%" "%BASE%\CharlesTown\ct-results-2026\%PDF%"

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
:fp_section
echo.
echo ========================================================================
echo   FAIRMOUNT PARK (FP)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FP_*.txt" 2^>nul') do (
    set "FP_PICKS=%%f"
    goto :fp_picks_ok
)
echo   No picks_FP_*.txt found - run parse_fp.bat first
goto :gp_section

:fp_picks_ok
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fairmount Park\fp-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fp_run
)
echo   No result PDF found - skipping
goto :gp_section

:fp_run
echo   Picks: %FP_PICKS%
echo   Result: %PDF%
echo.
py "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%FP_PICKS%" "%BASE%\Fairmount Park\fp-results-2026\%PDF%"

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
:gp_section
echo.
echo ========================================================================
echo   GULFSTREAM PARK (GP)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_GP_*.txt" 2^>nul') do (
    set "GP_PICKS=%%f"
    goto :gp_picks_ok
)
echo   No picks_GP_*.txt found - run parse_gp.bat first
goto :evd_section

:gp_picks_ok
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Gulfstream Park\gp-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :gp_run
)
echo   No result PDF found - skipping
goto :evd_section

:gp_run
echo   Picks: %GP_PICKS%
echo   Result: %PDF%
echo.
py "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%GP_PICKS%" "%BASE%\Gulfstream Park\gp-results-2026\%PDF%"

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
:evd_section
echo.
echo ========================================================================
echo   EVANGELINE DOWNS (EVD)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_EVD_*.txt" 2^>nul') do (
    set "EVD_PICKS=%%f"
    goto :evd_picks_ok
)
echo   No picks_EVD_*.txt found - run parse_evd.bat first
goto :done

:evd_picks_ok
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Evangeline Downs\evd-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :evd_run
)
echo   No result PDF found - skipping
goto :done

:evd_run
echo   Picks: %EVD_PICKS%
echo   Result: %PDF%
echo.
py "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%EVD_PICKS%" "%BASE%\Evangeline Downs\evd-results-2026\%PDF%"

:done
echo.
echo ########################################################################
echo   ALL TRACKS COMPLETE
echo ########################################################################
echo.
pause
