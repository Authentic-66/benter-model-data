@echo off
setlocal enabledelayedexpansion
title Process All Results
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

if not exist "%SCRIPTS%results-logs\" mkdir "%SCRIPTS%results-logs"
set "ALLLOG=%SCRIPTS%process_all_log.txt"
echo Process All Log -- %DATE% %TIME% > "!ALLLOG!"

echo.
echo. >> "!ALLLOG!"
echo ########################################################################
echo ######################################################################## >> "!ALLLOG!"
echo   BENTER MODEL -- PROCESS ALL RESULTS
echo   BENTER MODEL -- PROCESS ALL RESULTS >> "!ALLLOG!"
echo ########################################################################
echo ######################################################################## >> "!ALLLOG!"

:: ── CHARLES TOWN (CT) ────────────────────────────────────────────────────
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   CHARLES TOWN (CT)
echo   CHARLES TOWN (CT) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
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
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results CT [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\CharlesTown\ct-results-2026\%%f" CT > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_CT_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_CT_!FILEDATE!.txt >> "!ALLLOG!"
    )
)
if "!CT_FOUND!"=="0" (
    echo   No result PDF found - skipping
    echo   No result PDF found - skipping >> "!ALLLOG!"
)

:: ── FAIRMOUNT PARK (FP) ──────────────────────────────────────────────────
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   FAIRMOUNT PARK (FP)
echo   FAIRMOUNT PARK (FP) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
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
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results FP [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Fairmount Park\fp-results-2026\%%f" FP > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_FP_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_FP_!FILEDATE!.txt >> "!ALLLOG!"
    )
)
if "!FP_FOUND!"=="0" (
    echo   No result PDF found - skipping
    echo   No result PDF found - skipping >> "!ALLLOG!"
)

:: ── GULFSTREAM PARK (GP) ─────────────────────────────────────────────────
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   GULFSTREAM PARK (GP)
echo   GULFSTREAM PARK (GP) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
set "GP_FOUND=0"
dir /b /o-n /a-d "%BASE%\Gulfstream Park\gp-results-2026\*.pdf" > "%TEMP%\gp_pdfs.txt" 2>nul
for /f "usebackq delims=" %%f in ("%TEMP%\gp_pdfs.txt") do (
    set "GP_FOUND=1"
    set "STEM=%%~nf"
    rem Detect filename format: GP prefix, then MM.DD.YY (dot at position 2), then YYYYMMDD.
    if "!STEM:~0,2!"=="GP" (
        rem Format: GP[MM][DD][YY]USA.pdf  e.g. GP050826USA.pdf
        set "DIGITS=!STEM:~2,6!"
        set "MM=!DIGITS:~0,2!" & set "DD=!DIGITS:~2,2!" & set "YY=!DIGITS:~4,2!"
        set "FILEDATE=20!YY!!MM!!DD!"
    ) else if "!STEM:~2,1!"=="." (
        rem Format: MM.DD.YY GP Results.pdf  e.g. 01.08.26 GP Results.pdf
        set "MM=!STEM:~0,2!" & set "DD=!STEM:~3,2!" & set "YY=!STEM:~6,2!"
        set "FILEDATE=20!YY!!MM!!DD!"
    ) else (
        rem Format: YYYYMMDD-usa-gp-a-d.standard.pdf
        set "FILEDATE=!STEM:~0,8!"
    )
    echo   [GP] File    : %%f
    echo   [GP] File    : %%f >> "!ALLLOG!"
    echo   [GP] FILEDATE: !FILEDATE!
    echo   [GP] FILEDATE: !FILEDATE! >> "!ALLLOG!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_GP_!FILEDATE!.txt"
    echo   [GP] LOGFILE : !LOGFILE!
    echo   [GP] LOGFILE : !LOGFILE! >> "!ALLLOG!"
    if exist "!LOGFILE!" (
        echo   [GP] STATUS  : LOG EXISTS -- skipping
        echo   [GP] STATUS  : LOG EXISTS -- skipping >> "!ALLLOG!"
        echo   Already processed: %%f - skipping
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        echo   [GP] STATUS  : LOG NOT FOUND -- processing
        echo   [GP] STATUS  : LOG NOT FOUND -- processing >> "!ALLLOG!"
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results GP [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Gulfstream Park\gp-results-2026\%%f" GP > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_GP_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_GP_!FILEDATE!.txt >> "!ALLLOG!"
    )
)
if "!GP_FOUND!"=="0" (
    echo   No result PDF found - skipping
    echo   No result PDF found - skipping >> "!ALLLOG!"
)

:: ── EVANGELINE DOWNS (EVD) ───────────────────────────────────────────────
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   EVANGELINE DOWNS (EVD)
echo   EVANGELINE DOWNS (EVD) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
set "EVD_FOUND=0"
dir /b /o-n /a-d "%BASE%\Evangeline Downs\evd-results-2026\*.pdf" > "%TEMP%\evd_pdfs.txt" 2>nul
for /f "usebackq delims=" %%f in ("%TEMP%\evd_pdfs.txt") do (
    set "EVD_FOUND=1"
    set "STEM=%%~nf"
    set "DIGITS=!STEM:~3,6!"
    set "MM=!DIGITS:~0,2!" & set "DD=!DIGITS:~2,2!" & set "YY=!DIGITS:~4,2!"
    set "FILEDATE=20!YY!!MM!!DD!"
    echo   [EVD] File    : %%f
    echo   [EVD] File    : %%f >> "!ALLLOG!"
    echo   [EVD] STEM    : !STEM!
    echo   [EVD] STEM    : !STEM! >> "!ALLLOG!"
    echo   [EVD] DIGITS  : !DIGITS!  ^(MM=!MM! DD=!DD! YY=!YY!^)
    echo   [EVD] DIGITS  : !DIGITS!  ^(MM=!MM! DD=!DD! YY=!YY!^) >> "!ALLLOG!"
    echo   [EVD] FILEDATE: !FILEDATE!
    echo   [EVD] FILEDATE: !FILEDATE! >> "!ALLLOG!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_EVD_!FILEDATE!.txt"
    echo   [EVD] LOGFILE : !LOGFILE!
    echo   [EVD] LOGFILE : !LOGFILE! >> "!ALLLOG!"
    if exist "!LOGFILE!" (
        echo   [EVD] STATUS  : LOG EXISTS -- skipping
        echo   [EVD] STATUS  : LOG EXISTS -- skipping >> "!ALLLOG!"
        echo   Already processed: %%f - skipping
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        echo   [EVD] STATUS  : LOG NOT FOUND -- processing
        echo   [EVD] STATUS  : LOG NOT FOUND -- processing >> "!ALLLOG!"
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results EVD [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Evangeline Downs\evd-results-2026\%%f" EVD > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_EVD_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_EVD_!FILEDATE!.txt >> "!ALLLOG!"
    )
)
if "!EVD_FOUND!"=="0" (
    echo   No result PDF found - skipping
    echo   No result PDF found - skipping >> "!ALLLOG!"
)

:: ── DELTA DOWNS (DD) ──────────────────────────────────────────────────────
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   DELTA DOWNS (DD)
echo   DELTA DOWNS (DD) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
set "DD_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Delta Downs\dd-results-2025\*.pdf" 2^>nul') do (
    set "DD_FOUND=1"
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_DD_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results DD [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Delta Downs\dd-results-2025\%%f" DD > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_DD_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_DD_!FILEDATE!.txt >> "!ALLLOG!"
    )
)
if "!DD_FOUND!"=="0" (
    echo   No result PDF found - skipping
    echo   No result PDF found - skipping >> "!ALLLOG!"
)

:: ── FAIR GROUNDS (FG) ─────────────────────────────────────────────────────
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   FAIR GROUNDS (FG)
echo   FAIR GROUNDS (FG) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Fair Grounds\fg-results-2026\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :fg_datecheck
)
echo   No result PDF found - skipping
echo   No result PDF found - skipping >> "!ALLLOG!"
goto :mvr_section

:fg_datecheck
powershell -NoProfile -Command "if(((Get-Date)-(Get-Item '%BASE%\Fair Grounds\fg-results-2026\%PDF%').LastWriteTime).TotalDays -gt 30){1}else{0}" > "%TEMP%\stale_tmp.txt" 2>nul
set "FG_STALE=0"
for /f "usebackq" %%a in ("%TEMP%\stale_tmp.txt") do set "FG_STALE=%%a"
if "%FG_STALE%"=="1" (
    echo   No recent results found for FG - skipping
    echo   No recent results found for FG - skipping >> "!ALLLOG!"
    goto :mvr_section
)
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Fair Grounds\fg-results-2026\*.pdf" 2^>nul') do (
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_FG_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results FG [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Fair Grounds\fg-results-2026\%%f" FG > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_FG_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_FG_!FILEDATE!.txt >> "!ALLLOG!"
    )
)

:: ── MAHONING VALLEY (MVR) ─────────────────────────────────────────────────
:mvr_section
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   MAHONING VALLEY (MVR)
echo   MAHONING VALLEY (MVR) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%BASE%\Mahoning Valley\mvr-2026-results\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :mvr_datecheck
)
echo   No result PDF found - skipping
echo   No result PDF found - skipping >> "!ALLLOG!"
goto :lrl_section

:mvr_datecheck
powershell -NoProfile -Command "if(((Get-Date)-(Get-Item '%BASE%\Mahoning Valley\mvr-2026-results\%PDF%').LastWriteTime).TotalDays -gt 30){1}else{0}" > "%TEMP%\stale_tmp.txt" 2>nul
set "MVR_STALE=0"
for /f "usebackq" %%a in ("%TEMP%\stale_tmp.txt") do set "MVR_STALE=%%a"
if "%MVR_STALE%"=="1" (
    echo   No recent results found for MVR - skipping
    echo   No recent results found for MVR - skipping >> "!ALLLOG!"
    goto :lrl_section
)
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Mahoning Valley\mvr-2026-results\*.pdf" 2^>nul') do (
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_MVR_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results MVR [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Mahoning Valley\mvr-2026-results\%%f" MVR > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_MVR_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_MVR_!FILEDATE!.txt >> "!ALLLOG!"
    )
)

:: ── LAUREL PARK (LRL) ────────────────────────────────────────────────────
:lrl_section
echo.
echo. >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
echo   LAUREL PARK (LRL)
echo   LAUREL PARK (LRL) >> "!ALLLOG!"
echo ========================================================================
echo ======================================================================== >> "!ALLLOG!"
set "LRL_FOUND=0"
for /f "delims=" %%f in ('dir /b /o-n /a-d "%BASE%\Laurel Park\lrl-results-2026\*.pdf" 2^>nul') do (
    set "LRL_FOUND=1"
    set "STEM=%%~nf"
    set "FILEDATE=!STEM:~0,8!"
    set "LOGFILE=%SCRIPTS%results-logs\RESULTS_LRL_!FILEDATE!.txt"
    if exist "!LOGFILE!" (
        echo   Already processed: %%f - skipping
        echo   Already processed: %%f - skipping >> "!ALLLOG!"
    ) else (
        powershell -NoProfile -Command "Set-Content -Path '!LOGFILE!' -Value 'Results LRL [!FILEDATE!]' -Encoding UTF8"
        echo   File: %%f
        echo   File: %%f >> "!ALLLOG!"
        echo   File: %%f >> "!LOGFILE!"
        echo.
        echo. >> "!ALLLOG!"
        echo. >> "!LOGFILE!"
        py -u "%SCRIPTS%process_results.py" "%BASE%\Laurel Park\lrl-results-2026\%%f" LRL > "%TEMP%\results_tmp.txt" 2>&1
        type "%TEMP%\results_tmp.txt"
        type "%TEMP%\results_tmp.txt" >> "!ALLLOG!"
        powershell -NoProfile -Command "Get-Content '%TEMP%\results_tmp.txt' | Add-Content -Path '!LOGFILE!' -Encoding UTF8"
        echo   Results logged: results-logs\RESULTS_LRL_!FILEDATE!.txt
        echo   Results logged: results-logs\RESULTS_LRL_!FILEDATE!.txt >> "!ALLLOG!"
    )
)
if "!LRL_FOUND!"=="0" (
    echo   No result PDF found - skipping
    echo   No result PDF found - skipping >> "!ALLLOG!"
)

:done
echo.
echo. >> "!ALLLOG!"
echo ########################################################################
echo ######################################################################## >> "!ALLLOG!"
echo   ALL TRACKS PROCESSED
echo   ALL TRACKS PROCESSED >> "!ALLLOG!"
echo ########################################################################
echo ######################################################################## >> "!ALLLOG!"
echo.
echo. >> "!ALLLOG!"
echo Log saved to: !ALLLOG!
pause
