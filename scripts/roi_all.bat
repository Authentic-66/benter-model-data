@echo off
title ROI Tracker - All Tracks
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%roi-logs\" mkdir "%SCRIPTS%roi-logs"
set "LOGFILE=%SCRIPTS%roi-logs\ROI_ALL_%TODAY%.txt"
echo ROI All Tracks  [%TODAY%] > "%LOGFILE%"

echo.
echo ########################################################################
echo   BENTER MODEL -- ROI ALL TRACKS
echo ########################################################################
echo. >> "%LOGFILE%"
echo ######################################################################## >> "%LOGFILE%"
echo   BENTER MODEL -- ROI ALL TRACKS >> "%LOGFILE%"
echo ######################################################################## >> "%LOGFILE%"

:: ── CHARLES TOWN (CT) ────────────────────────────────────────────────────
echo.
echo ========================================================================
echo   CHARLES TOWN (CT)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   CHARLES TOWN (CT) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_CT_*.txt" 2^>nul') do (
    set "CT_PICKS=%%f"
    goto :ct_picks_ok
)
echo   No picks_CT_*.txt found - run parse_ct.bat first
echo   No picks_CT_*.txt found - run parse_ct.bat first >> "%LOGFILE%"
goto :fp_section

:ct_picks_ok
:: picks_CT_MMDDYYYY.txt — "picks_CT_" prefix is 9 chars
set "DATERAW=%CT_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
:: CT result PDF: CT[MM][DD][YY]USA.pdf
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\CharlesTown\ct-results-2026\CT%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :ct_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping CT
echo   No result PDF found for picks date %PICKSDATE% - skipping CT >> "%LOGFILE%"
goto :fp_section

:ct_run
echo   Picks: %CT_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %CT_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%CT_PICKS%" "%BASE%\CharlesTown\ct-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :fp_section

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
:fp_section
echo.
echo ========================================================================
echo   FAIRMOUNT PARK (FP)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   FAIRMOUNT PARK (FP) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FP_*.txt" 2^>nul') do (
    set "FP_PICKS=%%f"
    goto :fp_picks_ok
)
echo   No picks_FP_*.txt found - run parse_fp.bat first
echo   No picks_FP_*.txt found - run parse_fp.bat first >> "%LOGFILE%"
goto :gp_section

:fp_picks_ok
:: picks_FP_MMDDYYYY.txt — "picks_FP_" prefix is 9 chars
set "DATERAW=%FP_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
set "FP_DIR=%BASE%\Fairmount Park\fp-results-2026"
:: FP result PDF: FP[MM][DD][YY]USA.pdf
for /f "delims=" %%f in ('dir /b /a-d "%FP_DIR%\FP%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fp_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping FP
echo   No result PDF found for picks date %PICKSDATE% - skipping FP >> "%LOGFILE%"
goto :gp_section

:fp_run
echo   Picks: %FP_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %FP_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
set "FP_PICKS_PATH=%SCRIPTS%%FP_PICKS%"
set "FP_PDF_PATH=%FP_DIR%\%PDF%"
py -u "%SCRIPTS%roi_tracker.py" "%FP_PICKS_PATH%" "%FP_PDF_PATH%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :gp_section

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
:gp_section
echo.
echo ========================================================================
echo   GULFSTREAM PARK (GP)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   GULFSTREAM PARK (GP) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_GP_*.txt" 2^>nul') do (
    set "GP_PICKS=%%f"
    goto :gp_picks_ok
)
echo   No picks_GP_*.txt found - run parse_gp.bat first
echo   No picks_GP_*.txt found - run parse_gp.bat first >> "%LOGFILE%"
goto :sar_section

:gp_picks_ok
:: picks_GP_MMDDYYYY.txt — "picks_GP_" prefix is 9 chars
set "DATERAW=%GP_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
:: GP result PDF: GP[MM][DD][YY]USA.pdf
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Gulfstream Park\gp-results-2026\GP%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :gp_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping GP
echo   No result PDF found for picks date %PICKSDATE% - skipping GP >> "%LOGFILE%"
goto :sar_section

:gp_run
echo   Picks: %GP_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %GP_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%GP_PICKS%" "%BASE%\Gulfstream Park\gp-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :sar_section

:: ── SARATOGA (SAR) ───────────────────────────────────────────────────────
:sar_section
echo.
echo ========================================================================
echo   SARATOGA (SAR)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   SARATOGA (SAR) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_SAR_*.txt" 2^>nul') do (
    set "SAR_PICKS=%%f"
    goto :sar_picks_ok
)
echo   No picks_SAR_*.txt found - run parse_sar.bat first
echo   No picks_SAR_*.txt found - run parse_sar.bat first >> "%LOGFILE%"
goto :sa_section

:sar_picks_ok
:: picks_SAR_MMDDYYYY.txt -- "picks_SAR_" prefix is 10 chars
set "DATERAW=%SAR_PICKS:~10,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
:: SAR result PDF: SAR[MM][DD][YY]USA.pdf
set "SAR_DIR=%BASE%\Saratoga\sar-results-2026"
for /f "delims=" %%f in ('dir /b /a-d "%SAR_DIR%\SAR%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :sar_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping SAR
echo   No result PDF found for picks date %PICKSDATE% - skipping SAR >> "%LOGFILE%"
goto :sa_section

:sar_run
echo   Picks: %SAR_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %SAR_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
set "SAR_PICKS_PATH=%SCRIPTS%%SAR_PICKS%"
set "SAR_PDF_PATH=%SAR_DIR%\%PDF%"
py -u "%SCRIPTS%roi_tracker.py" "%SAR_PICKS_PATH%" "%SAR_PDF_PATH%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :sa_section

:: ── SANTA ANITA (SA) ─────────────────────────────────────────────────────
:sa_section
echo.
echo ========================================================================
echo   SANTA ANITA (SA)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   SANTA ANITA (SA) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_SA_*.txt" 2^>nul') do (
    set "SA_PICKS=%%f"
    goto :sa_picks_ok
)
echo   No picks_SA_*.txt found - run parse_sa.bat first
echo   No picks_SA_*.txt found - run parse_sa.bat first >> "%LOGFILE%"
goto :evd_section

:sa_picks_ok
:: picks_SA_MMDDYYYY.txt -- "picks_SA_" prefix is 9 chars
set "DATERAW=%SA_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
set "SA_DIR=%BASE%\Santa Anita\sa-results-2026"
:: Try alternate format first: SA[MM][DD][YY]USA.pdf
for /f "delims=" %%f in ('dir /b /a-d "%SA_DIR%\SA%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :sa_run
)
:: Fallback to standard format: YYYYMMDD-usa-sa-a-d.standard.pdf
for /f "delims=" %%f in ('dir /b /a-d "%SA_DIR%\%PICKSDATE%-usa-sa-*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :sa_run
)
:: Also check 2025 directory
set "SA_DIR=%BASE%\Santa Anita\sa-results-2025"
for /f "delims=" %%f in ('dir /b /a-d "%SA_DIR%\%PICKSDATE%-usa-sa-*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :sa_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping SA
echo   No result PDF found for picks date %PICKSDATE% - skipping SA >> "%LOGFILE%"
goto :evd_section

:sa_run
echo   Picks: %SA_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %SA_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
set "SA_PICKS_PATH=%SCRIPTS%%SA_PICKS%"
set "SA_PDF_PATH=%SA_DIR%\%PDF%"
py -u "%SCRIPTS%roi_tracker.py" "%SA_PICKS_PATH%" "%SA_PDF_PATH%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :evd_section

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
:evd_section
echo.
echo ========================================================================
echo   EVANGELINE DOWNS (EVD)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   EVANGELINE DOWNS (EVD) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_EVD_*.txt" 2^>nul') do (
    set "EVD_PICKS=%%f"
    goto :evd_picks_ok
)
echo   No picks_EVD_*.txt found - run parse_evd.bat first
echo   No picks_EVD_*.txt found - run parse_evd.bat first >> "%LOGFILE%"
goto :dd_section

:evd_picks_ok
:: picks_EVD_MMDDYYYY.txt — "picks_EVD_" prefix is 10 chars
set "DATERAW=%EVD_PICKS:~10,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
:: EVD result PDF: EVD[MM][DD][YY]USA.pdf
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Evangeline Downs\evd-results-2026\EVD%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :evd_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping EVD
echo   No result PDF found for picks date %PICKSDATE% - skipping EVD >> "%LOGFILE%"
goto :dd_section

:evd_run
echo   Picks: %EVD_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %EVD_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%EVD_PICKS%" "%BASE%\Evangeline Downs\evd-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :dd_section

:: ── DELTA DOWNS (DD) ──────────────────────────────────────────────────────
:dd_section
echo.
echo ========================================================================
echo   DELTA DOWNS (DD)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   DELTA DOWNS (DD) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_DD_*.txt" 2^>nul') do (
    set "DD_PICKS=%%f"
    goto :dd_picks_ok
)
echo   No picks_DD_*.txt found - run parse_dd.bat first
echo   No picks_DD_*.txt found - run parse_dd.bat first >> "%LOGFILE%"
goto :fg_section

:dd_picks_ok
:: picks_DD_MMDDYYYY.txt — "picks_DD_" prefix is 9 chars
:: DD result PDF: YYYYMMDD-usa-ded-a-d.standard.pdf
set "DATERAW=%DD_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Delta Downs\dd-results-2025\%PICKSDATE%-usa-*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :dd_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping DD
echo   No result PDF found for picks date %PICKSDATE% - skipping DD >> "%LOGFILE%"
goto :fg_section

:dd_run
echo   Picks: %DD_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %DD_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%DD_PICKS%" "%BASE%\Delta Downs\dd-results-2025\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :fg_section

:: ── FAIR GROUNDS (FG) ─────────────────────────────────────────────────────
:fg_section
echo.
echo ========================================================================
echo   FAIR GROUNDS (FG)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   FAIR GROUNDS (FG) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FG_*.txt" 2^>nul') do (
    set "FG_PICKS=%%f"
    goto :fg_picks_ok
)
echo   No picks_FG_*.txt found - run parse_fg.bat first
echo   No picks_FG_*.txt found - run parse_fg.bat first >> "%LOGFILE%"
goto :mvr_section

:fg_picks_ok
:: picks_FG_MMDDYYYY.txt — "picks_FG_" prefix is 9 chars
:: FG result PDF: YYYYMMDD-usa-fg-a-d.standard.pdf
set "DATERAW=%FG_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Fair Grounds\fg-results-2026\%PICKSDATE%-usa-*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fg_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping FG
echo   No result PDF found for picks date %PICKSDATE% - skipping FG >> "%LOGFILE%"
goto :mvr_section

:fg_run
echo   Picks: %FG_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %FG_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%FG_PICKS%" "%BASE%\Fair Grounds\fg-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :mvr_section

:: ── MAHONING VALLEY (MVR) ─────────────────────────────────────────────────
:mvr_section
echo.
echo ========================================================================
echo   MAHONING VALLEY (MVR)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   MAHONING VALLEY (MVR) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_MVR_*.txt" 2^>nul') do (
    set "MVR_PICKS=%%f"
    goto :mvr_picks_ok
)
echo   No picks_MVR_*.txt found - run parse_mvr.bat first
echo   No picks_MVR_*.txt found - run parse_mvr.bat first >> "%LOGFILE%"
goto :lrl_section

:mvr_picks_ok
:: picks_MVR_MMDDYYYY.txt — "picks_MVR_" prefix is 10 chars
:: MVR result PDF: YYYYMMDD-usa-mvr-a-d.standard.pdf
set "DATERAW=%MVR_PICKS:~10,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Mahoning Valley\mvr-2026-results\%PICKSDATE%-usa-*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :mvr_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping MVR
echo   No result PDF found for picks date %PICKSDATE% - skipping MVR >> "%LOGFILE%"
goto :lrl_section

:mvr_run
echo   Picks: %MVR_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %MVR_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%MVR_PICKS%" "%BASE%\Mahoning Valley\mvr-2026-results\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :lrl_section

:: ── LAUREL PARK (LRL) ────────────────────────────────────────────────────
:lrl_section
echo.
echo ========================================================================
echo   LAUREL PARK (LRL)
echo ========================================================================
echo. >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
echo   LAUREL PARK (LRL) >> "%LOGFILE%"
echo ======================================================================== >> "%LOGFILE%"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_LRL_*.txt" 2^>nul') do (
    set "LRL_PICKS=%%f"
    goto :lrl_picks_ok
)
echo   No picks_LRL_*.txt found - run parse_lrl.bat first
echo   No picks_LRL_*.txt found - run parse_lrl.bat first >> "%LOGFILE%"
goto :done

:lrl_picks_ok
:: picks_LRL_MMDDYYYY.txt — "picks_LRL_" prefix is 10 chars
:: LRL result PDF: YYYYMMDD-usa-lrl-a-d.standard.pdf
set "DATERAW=%LRL_PICKS:~10,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Laurel Park\lrl-results-2026\%PICKSDATE%-usa-*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :lrl_run
)
echo   No result PDF found for picks date %PICKSDATE% - skipping LRL
echo   No result PDF found for picks date %PICKSDATE% - skipping LRL >> "%LOGFILE%"
goto :done

:lrl_run
echo   Picks: %LRL_PICKS%
echo   Result: %PDF%
echo.
echo   Picks: %LRL_PICKS% >> "%LOGFILE%"
echo   Result: %PDF% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%LRL_PICKS%" "%BASE%\Laurel Park\lrl-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
goto :done

:done
echo.
echo ########################################################################
echo   ALL TRACKS COMPLETE
echo ########################################################################
echo.
echo. >> "%LOGFILE%"
echo ######################################################################## >> "%LOGFILE%"
echo   ALL TRACKS COMPLETE >> "%LOGFILE%"
echo ######################################################################## >> "%LOGFILE%"
echo. >> "%LOGFILE%"
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
