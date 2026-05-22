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
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\CharlesTown\ct-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping CT
    goto :fp_section
)
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
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Fairmount Park\fp-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping FP
    goto :gp_section
)
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
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Gulfstream Park\gp-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping GP
    goto :evd_section
)
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
goto :dd_section

:evd_run
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Evangeline Downs\evd-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping EVD
    goto :dd_section
)
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Evangeline Downs\evd-pps-files\%PDF%" EVD
call :log_picks EVD

:: ── DELTA DOWNS (DD) ──────────────────────────────────────────────────────
:dd_section
echo.
echo ========================================================================
echo   DELTA DOWNS (DD)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Delta Downs\dd-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :dd_run
)
echo   No PP file found - skipping
goto :fg_section

:dd_run
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Delta Downs\dd-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping DD
    goto :fg_section
)
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Delta Downs\dd-pps-files\%PDF%" DD
call :log_picks DD

:: ── FAIR GROUNDS (FG) ─────────────────────────────────────────────────────
:fg_section
echo.
echo ========================================================================
echo   FAIR GROUNDS (FG)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fair Grounds\fg-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fg_run
)
echo   No PP file found - skipping
goto :mvr_section

:fg_run
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Fair Grounds\fg-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping FG
    goto :mvr_section
)
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Fair Grounds\fg-pps-files\%PDF%" FG
call :log_picks FG

:: ── MAHONING VALLEY (MVR) ─────────────────────────────────────────────────
:mvr_section
echo.
echo ========================================================================
echo   MAHONING VALLEY (MVR)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Mahoning Valley\mvr-pps-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :mvr_run
)
echo   No PP file found - skipping
goto :lrl_section

:mvr_run
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Mahoning Valley\mvr-pps-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping MVR
    goto :lrl_section
)
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Mahoning Valley\mvr-pps-files\%PDF%" MVR
call :log_picks MVR

:: ── LAUREL PARK (LRL) ────────────────────────────────────────────────────
:lrl_section
echo.
echo ========================================================================
echo   LAUREL PARK (LRL)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Laurel Park\laurel-pp-files\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :lrl_run
)
echo   No PP file found - skipping
goto :done

:lrl_run
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%BASE%\Laurel Park\laurel-pp-files\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo   File date [%FILEDATE%] does not match today [%TODAY%] - skipping LRL
    goto :done
)
echo   File: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%BASE%\Laurel Park\laurel-pp-files\%PDF%" LRL
call :log_picks LRL

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
