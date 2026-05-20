@echo off
title Process All Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%results-logs\" mkdir "%SCRIPTS%results-logs"

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
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_CT_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results CT [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%process_results.py' '%BASE%\CharlesTown\ct-results-2026\%PDF%' CT 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo   Results logged: results-logs\RESULTS_CT_%TODAY%.txt

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
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_FP_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results FP [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%process_results.py' '%BASE%\Fairmount Park\fp-results-2026\%PDF%' FP 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo   Results logged: results-logs\RESULTS_FP_%TODAY%.txt

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
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_GP_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results GP [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%process_results.py' '%BASE%\Gulfstream Park\gp-results-2026\%PDF%' GP 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo   Results logged: results-logs\RESULTS_GP_%TODAY%.txt

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
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_EVD_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results EVD [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $out = py -u '%SCRIPTS%process_results.py' '%BASE%\Evangeline Downs\evd-results-2026\%PDF%' EVD 2>&1; $out | Write-Host; $out | Out-File -FilePath '%LOGFILE%' -Encoding utf8 -Append"
echo   Results logged: results-logs\RESULTS_EVD_%TODAY%.txt

:done
echo.
echo ########################################################################
echo   ALL TRACKS PROCESSED
echo ########################################################################
echo.
pause
