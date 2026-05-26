@echo off
setlocal enabledelayedexpansion
title Process All Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

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
set "CT_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\CharlesTown\ct-results-2026\*.pdf" 2^>nul') do (
    set "CT_FOUND=1"
    set "STEM=%%~nf"
    set "DIGITS=!STEM:~2,6!"
    set "MM=!DIGITS:~0,2!" & set "DD=!DIGITS:~2,2!" & set "YY=!DIGITS:~4,2!"
    set "FILEDATE=20!YY!!MM!!DD!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_CT_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results CT [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\CharlesTown\ct-results-2026\%%f" CT > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_CT_!FILEDATE!.txt
    )
)
if "!CT_FOUND!"=="0" echo   No result PDF found - skipping

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
echo.
echo ========================================================================
echo   FAIRMOUNT PARK (FP)
echo ========================================================================
set "FP_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Fairmount Park\fp-results-2026\*.pdf" 2^>nul') do (
    set "FP_FOUND=1"
    set "STEM=%%~nf"
    set "DIGITS=!STEM:~2,6!"
    set "MM=!DIGITS:~0,2!" & set "DD=!DIGITS:~2,2!" & set "YY=!DIGITS:~4,2!"
    set "FILEDATE=20!YY!!MM!!DD!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_FP_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results FP [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Fairmount Park\fp-results-2026\%%f" FP > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_FP_!FILEDATE!.txt
    )
)
if "!FP_FOUND!"=="0" echo   No result PDF found - skipping

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
echo.
echo ========================================================================
echo   GULFSTREAM PARK (GP)
echo ========================================================================
set "GP_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Gulfstream Park\gp-results-2026\*.pdf" 2^>nul') do (
    set "GP_FOUND=1"
    set "STEM=%%~nf"
    set "DIGITS=!STEM:~2,6!"
    set "MM=!DIGITS:~0,2!" & set "DD=!DIGITS:~2,2!" & set "YY=!DIGITS:~4,2!"
    set "FILEDATE=20!YY!!MM!!DD!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_GP_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results GP [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Gulfstream Park\gp-results-2026\%%f" GP > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_GP_!FILEDATE!.txt
    )
)
if "!GP_FOUND!"=="0" echo   No result PDF found - skipping

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
echo.
echo ========================================================================
echo   EVANGELINE DOWNS (EVD)
echo ========================================================================
set "EVD_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Evangeline Downs\evd-results-2026\*.pdf" 2^>nul') do (
    set "EVD_FOUND=1"
    set "STEM=%%~nf"
    set "DIGITS=!STEM:~3,6!"
    set "MM=!DIGITS:~0,2!" & set "DD=!DIGITS:~2,2!" & set "YY=!DIGITS:~4,2!"
    set "FILEDATE=20!YY!!MM!!DD!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_EVD_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results EVD [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Evangeline Downs\evd-results-2026\%%f" EVD > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_EVD_!FILEDATE!.txt
    )
)
if "!EVD_FOUND!"=="0" echo   No result PDF found - skipping

:: ── DELTA DOWNS (DD) ──────────────────────────────────────────────────────
echo.
echo ========================================================================
echo   DELTA DOWNS (DD)
echo ========================================================================
set "DD_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Delta Downs\dd-results-2025\*.pdf" 2^>nul') do (
    set "DD_FOUND=1"
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_DD_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results DD [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Delta Downs\dd-results-2025\%%f" DD > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_DD_!FILEDATE!.txt
    )
)
if "!DD_FOUND!"=="0" echo   No result PDF found - skipping

:: ── FAIR GROUNDS (FG) ─────────────────────────────────────────────────────
echo.
echo ========================================================================
echo   FAIR GROUNDS (FG)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fair Grounds\fg-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fg_datecheck
)
echo   No result PDF found - skipping
goto :mvr_section

:fg_datecheck
powershell -NoProfile -Command "if(((Get-Date)-(Get-Item '%BASE%\Fair Grounds\fg-results-2026\%PDF%').LastWriteTime).TotalDays -gt 30){1}else{0}" > "%TEMP%\stale_tmp.txt" 2>nul
set "FG_STALE=0"
for /f "usebackq" %%a in ("%TEMP%\stale_tmp.txt") do set "FG_STALE=%%a"
if "%FG_STALE%"=="1" (
    echo   No recent results found for FG - skipping
    goto :mvr_section
)
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Fair Grounds\fg-results-2026\*.pdf" 2^>nul') do (
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_FG_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results FG [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Fair Grounds\fg-results-2026\%%f" FG > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_FG_!FILEDATE!.txt
    )
)

:: ── MAHONING VALLEY (MVR) ─────────────────────────────────────────────────
:mvr_section
echo.
echo ========================================================================
echo   MAHONING VALLEY (MVR)
echo ========================================================================
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Mahoning Valley\mvr-2026-results\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :mvr_datecheck
)
echo   No result PDF found - skipping
goto :lrl_section

:mvr_datecheck
powershell -NoProfile -Command "if(((Get-Date)-(Get-Item '%BASE%\Mahoning Valley\mvr-2026-results\%PDF%').LastWriteTime).TotalDays -gt 30){1}else{0}" > "%TEMP%\stale_tmp.txt" 2>nul
set "MVR_STALE=0"
for /f "usebackq" %%a in ("%TEMP%\stale_tmp.txt") do set "MVR_STALE=%%a"
if "%MVR_STALE%"=="1" (
    echo   No recent results found for MVR - skipping
    goto :lrl_section
)
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Mahoning Valley\mvr-2026-results\*.pdf" 2^>nul') do (
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_MVR_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results MVR [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Mahoning Valley\mvr-2026-results\%%f" MVR > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_MVR_!FILEDATE!.txt
    )
)

:: ── LAUREL PARK (LRL) ────────────────────────────────────────────────────
:lrl_section
echo.
echo ========================================================================
echo   LAUREL PARK (LRL)
echo ========================================================================
set "LRL_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Laurel Park\lrl-results-2026\*.pdf" 2^>nul') do (
    set "LRL_FOUND=1"
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_LRL_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results LRL [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Laurel Park\lrl-results-2026\%%f" LRL > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_LRL_!FILEDATE!.txt
    )
)
if "!LRL_FOUND!"=="0" echo   No result PDF found - skipping

:done
echo.
echo ########################################################################
echo   ALL TRACKS PROCESSED
echo ########################################################################
echo.
pause
