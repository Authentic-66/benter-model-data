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
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\CharlesTown\ct-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :ct_run
)
call :log "  No result PDF found - skipping"
goto :fp_section

:ct_run
call :log "  Picks: %CT_PICKS%"
call :log "  Result: %PDF%"
call :log ""
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%roi_tracker.py' '%SCRIPTS%%CT_PICKS%' '%BASE%\CharlesTown\ct-results-2026\%PDF%' 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"

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
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fairmount Park\fp-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fp_run
)
call :log "  No result PDF found - skipping"
goto :gp_section

:fp_run
call :log "  Picks: %FP_PICKS%"
call :log "  Result: %PDF%"
call :log ""
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%roi_tracker.py' '%SCRIPTS%%FP_PICKS%' '%BASE%\Fairmount Park\fp-results-2026\%PDF%' 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"

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
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Gulfstream Park\gp-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :gp_run
)
call :log "  No result PDF found - skipping"
goto :evd_section

:gp_run
call :log "  Picks: %GP_PICKS%"
call :log "  Result: %PDF%"
call :log ""
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%roi_tracker.py' '%SCRIPTS%%GP_PICKS%' '%BASE%\Gulfstream Park\gp-results-2026\%PDF%' 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"

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
goto :done

:evd_picks_ok
:: Extract date from picks filename: picks_EVD_20260515.txt -> 20260515
set "PICKSDATE=%EVD_PICKS:picks_EVD_=%"
set "PICKSDATE=%PICKSDATE:.txt=%"
for /f "delims=" %%f in ('powershell -NoProfile -Command "Get-ChildItem '%BASE%\Evangeline Downs\evd-results-2026\*.pdf' -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime.ToString('yyyyMMdd') -eq $env:PICKSDATE } | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name"') do (
    set "PDF=%%f"
    goto :evd_run
)
call :log "  No result PDF found for picks date %PICKSDATE% - skipping"
goto :done

:evd_run
call :log "  Picks: %EVD_PICKS%"
call :log "  Result: %PDF%"
call :log ""
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%roi_tracker.py' '%SCRIPTS%%EVD_PICKS%' '%BASE%\Evangeline Downs\evd-results-2026\%PDF%' 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"

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
