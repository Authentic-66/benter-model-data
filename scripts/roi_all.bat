@echo off
title ROI Tracker - All Tracks
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%roi-logs\" mkdir "%SCRIPTS%roi-logs"
set "LOGFILE=%SCRIPTS%roi-logs\ROI_ALL_%TODAY%.txt"
echo ROI All Tracks  [%TODAY%] > "%LOGFILE%"

call :log ""
call :log "########################################################################"
call :log "  BENTER MODEL -- ROI ALL TRACKS"
call :log "########################################################################"

:: ── CHARLES TOWN (CT) ────────────────────────────────────────────────────
call :log ""
call :log "========================================================================"
call :log "  CHARLES TOWN (CT)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_CT_*.txt" 2^>nul') do (
    set "CT_PICKS=%%f"
    goto :ct_picks_ok
)
call :log "  No picks_CT_*.txt found - run parse_ct.bat first"
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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping CT"
goto :fp_section

:ct_run
call :log "  Picks: %CT_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%CT_PICKS%" "%BASE%\CharlesTown\ct-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
:fp_section
call :log ""
call :log "========================================================================"
call :log "  FAIRMOUNT PARK (FP)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FP_*.txt" 2^>nul') do (
    set "FP_PICKS=%%f"
    goto :fp_picks_ok
)
call :log "  No picks_FP_*.txt found - run parse_fp.bat first"
goto :gp_section

:fp_picks_ok
:: picks_FP_MMDDYYYY.txt — "picks_FP_" prefix is 9 chars
set "DATERAW=%FP_PICKS:~9,8%"
set "MM=%DATERAW:~0,2%"
set "DD=%DATERAW:~2,2%"
set "YY=%DATERAW:~6,2%"
set "YYYY=%DATERAW:~4,4%"
set "PICKSDATE=%YYYY%%MM%%DD%"
:: FP result PDF: FP[MM][DD][YY]USA.pdf
for /f "delims=" %%f in ('dir /b /a-d "%BASE%\Fairmount Park\fp-results-2026\FP%MM%%DD%%YY%USA.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fp_run
)
call :log "  No result PDF found for picks date %PICKSDATE% - skipping FP"
goto :gp_section

:fp_run
call :log "  Picks: %FP_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%FP_PICKS%" "%BASE%\Fairmount Park\fp-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
:gp_section
call :log ""
call :log "========================================================================"
call :log "  GULFSTREAM PARK (GP)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_GP_*.txt" 2^>nul') do (
    set "GP_PICKS=%%f"
    goto :gp_picks_ok
)
call :log "  No picks_GP_*.txt found - run parse_gp.bat first"
goto :evd_section

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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping GP"
goto :evd_section

:gp_run
call :log "  Picks: %GP_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%GP_PICKS%" "%BASE%\Gulfstream Park\gp-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
:evd_section
call :log ""
call :log "========================================================================"
call :log "  EVANGELINE DOWNS (EVD)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_EVD_*.txt" 2^>nul') do (
    set "EVD_PICKS=%%f"
    goto :evd_picks_ok
)
call :log "  No picks_EVD_*.txt found - run parse_evd.bat first"
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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping EVD"
goto :dd_section

:evd_run
call :log "  Picks: %EVD_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%EVD_PICKS%" "%BASE%\Evangeline Downs\evd-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── DELTA DOWNS (DD) ──────────────────────────────────────────────────────
:dd_section
call :log ""
call :log "========================================================================"
call :log "  DELTA DOWNS (DD)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_DD_*.txt" 2^>nul') do (
    set "DD_PICKS=%%f"
    goto :dd_picks_ok
)
call :log "  No picks_DD_*.txt found - run parse_dd.bat first"
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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping DD"
goto :fg_section

:dd_run
call :log "  Picks: %DD_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%DD_PICKS%" "%BASE%\Delta Downs\dd-results-2025\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── FAIR GROUNDS (FG) ─────────────────────────────────────────────────────
:fg_section
call :log ""
call :log "========================================================================"
call :log "  FAIR GROUNDS (FG)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_FG_*.txt" 2^>nul') do (
    set "FG_PICKS=%%f"
    goto :fg_picks_ok
)
call :log "  No picks_FG_*.txt found - run parse_fg.bat first"
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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping FG"
goto :mvr_section

:fg_run
call :log "  Picks: %FG_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%FG_PICKS%" "%BASE%\Fair Grounds\fg-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── MAHONING VALLEY (MVR) ─────────────────────────────────────────────────
:mvr_section
call :log ""
call :log "========================================================================"
call :log "  MAHONING VALLEY (MVR)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_MVR_*.txt" 2^>nul') do (
    set "MVR_PICKS=%%f"
    goto :mvr_picks_ok
)
call :log "  No picks_MVR_*.txt found - run parse_mvr.bat first"
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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping MVR"
goto :lrl_section

:mvr_run
call :log "  Picks: %MVR_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%MVR_PICKS%" "%BASE%\Mahoning Valley\mvr-2026-results\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:: ── LAUREL PARK (LRL) ────────────────────────────────────────────────────
:lrl_section
call :log ""
call :log "========================================================================"
call :log "  LAUREL PARK (LRL)"
call :log "========================================================================"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_LRL_*.txt" 2^>nul') do (
    set "LRL_PICKS=%%f"
    goto :lrl_picks_ok
)
call :log "  No picks_LRL_*.txt found - run parse_lrl.bat first"
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
call :log "  No result PDF found for picks date %PICKSDATE% - skipping LRL"
goto :done

:lrl_run
call :log "  Picks: %LRL_PICKS%"
call :log "  Result: %PDF%"
call :log ""
py -u "%SCRIPTS%roi_tracker.py" "%SCRIPTS%%LRL_PICKS%" "%BASE%\Laurel Park\lrl-results-2026\%PDF%" > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"

:done
call :log ""
call :log "########################################################################"
call :log "  ALL TRACKS COMPLETE"
call :log "########################################################################"
call :log ""
echo Log saved: %LOGFILE%
echo Log saved: %LOGFILE% >> "%LOGFILE%"
echo.
pause
goto :eof

:log
echo(%~1
echo(%~1 >> "%LOGFILE%"
exit /b
