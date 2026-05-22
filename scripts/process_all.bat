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
py -u "%SCRIPTS%process_results.py" "%BASE%\CharlesTown\ct-results-2026\%PDF%" CT > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
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
py -u "%SCRIPTS%process_results.py" "%BASE%\Fairmount Park\fp-results-2026\%PDF%" FP > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
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
py -u "%SCRIPTS%process_results.py" "%BASE%\Gulfstream Park\gp-results-2026\%PDF%" GP > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
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
goto :dd_section

:evd_run
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_EVD_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results EVD [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%process_results.py" "%BASE%\Evangeline Downs\evd-results-2026\%PDF%" EVD > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo   Results logged: results-logs\RESULTS_EVD_%TODAY%.txt

:: ── DELTA DOWNS (DD) ──────────────────────────────────────────────────────
:dd_section
echo.
echo ========================================================================
echo   DELTA DOWNS (DD)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Delta Downs\dd-results-2025\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :dd_run
)
echo   No result PDF found - skipping
goto :fg_section

:dd_run
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_DD_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results DD [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%process_results.py" "%BASE%\Delta Downs\dd-results-2025\%PDF%" DD > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo   Results logged: results-logs\RESULTS_DD_%TODAY%.txt

:: ── FAIR GROUNDS (FG) ─────────────────────────────────────────────────────
:fg_section
echo.
echo ========================================================================
echo   FAIR GROUNDS (FG)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fair Grounds\fg-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fg_run
)
echo   No result PDF found - skipping
goto :mvr_section

:fg_run
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_FG_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results FG [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%process_results.py" "%BASE%\Fair Grounds\fg-results-2026\%PDF%" FG > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo   Results logged: results-logs\RESULTS_FG_%TODAY%.txt

:: ── MAHONING VALLEY (MVR) ─────────────────────────────────────────────────
:mvr_section
echo.
echo ========================================================================
echo   MAHONING VALLEY (MVR)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Mahoning Valley\mvr-2026-results\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :mvr_run
)
echo   No result PDF found - skipping
goto :lrl_section

:mvr_run
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_MVR_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results MVR [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%process_results.py" "%BASE%\Mahoning Valley\mvr-2026-results\%PDF%" MVR > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo   Results logged: results-logs\RESULTS_MVR_%TODAY%.txt

:: ── LAUREL PARK (LRL) ────────────────────────────────────────────────────
:lrl_section
echo.
echo ========================================================================
echo   LAUREL PARK (LRL)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Laurel Park\lrl-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :lrl_run
)
echo   No result PDF found - skipping
goto :done

:lrl_run
set "LOGFILE=%SCRIPTS%results-logs\RESULTS_LRL_%TODAY%.txt"
powershell -NoProfile -Command "Set-Content -Path '%LOGFILE%' -Value 'Results LRL [%TODAY%]' -Encoding UTF8"
echo   File: %PDF%
echo   File: %PDF% >> "%LOGFILE%"
echo.
echo. >> "%LOGFILE%"
py -u "%SCRIPTS%process_results.py" "%BASE%\Laurel Park\lrl-results-2026\%PDF%" LRL > "%TEMP%\results_tmp.txt" 2>&1
type "%TEMP%\results_tmp.txt"
powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '%LOGFILE%' -Encoding UTF8"
echo   Results logged: results-logs\RESULTS_LRL_%TODAY%.txt

:done
echo.
echo ########################################################################
echo   ALL TRACKS PROCESSED
echo ########################################################################
echo.
pause
