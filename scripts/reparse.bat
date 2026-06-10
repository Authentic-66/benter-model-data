@echo off
setlocal enabledelayedexpansion
title Reparse Track
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

:: ── Build date strings ────────────────────────────────────────────────────
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format MMddyyyy"') do set "PICKSDATE=%%d"
if not exist "%SCRIPTS%handicap-logs\" mkdir "%SCRIPTS%handicap-logs"

:: ── Argument check ────────────────────────────────────────────────────────
if "%~1"=="" (
    echo.
    echo   Usage: reparse.bat [TRACK_CODE]
    echo   Valid codes: CT, FP, GP, EVD, DD, FG, MVR, LRL, SAR
    echo.
    pause
    goto :eof
)

set "TRACK=%~1"
call :TOUPPER TRACK

:: ── Track directory map ───────────────────────────────────────────────────
set "PPDIR="
if /i "%TRACK%"=="CT"  set "PPDIR=%BASE%\CharlesTown\ct-pps-files"
if /i "%TRACK%"=="FP"  set "PPDIR=%BASE%\Fairmount Park\fp-pps-files"
if /i "%TRACK%"=="GP"  set "PPDIR=%BASE%\Gulfstream Park\gp-pps-files"
if /i "%TRACK%"=="EVD" set "PPDIR=%BASE%\Evangeline Downs\evd-pps-files"
if /i "%TRACK%"=="DD"  set "PPDIR=%BASE%\Delta Downs\dd-pps-files"
if /i "%TRACK%"=="FG"  set "PPDIR=%BASE%\Fair Grounds\fg-pps-files"
if /i "%TRACK%"=="MVR" set "PPDIR=%BASE%\Mahoning Valley\mvr-pps-files"
if /i "%TRACK%"=="LRL" set "PPDIR=%BASE%\Laurel Park\laurel-pp-files"
if /i "%TRACK%"=="SAR" set "PPDIR=%BASE%\Saratoga\sar-pps-files"

echo.
echo ########################################################################
echo   BENTER MODEL -- FORCE REPARSE: %TRACK%
echo ########################################################################
echo.
echo   Date     : %TODAY%
echo   Base dir : %BASE%
echo   PP dir   : %PPDIR%
echo.

if not defined PPDIR (
    echo   [ERROR] Unknown track code: %TRACK%
    echo   Valid codes: CT, FP, GP, EVD, DD, FG, MVR, LRL, SAR
    echo.
    pause
    goto :eof
)

if not exist "%PPDIR%" (
    echo   [ERROR] PP folder not found on disk:
    echo   %PPDIR%
    echo.
    pause
    goto :eof
)

:: ── Find today's PP file ──────────────────────────────────────────────────
echo   Scanning for today's PP file in:
echo   %PPDIR%
echo.
set "PDF="
for /f "delims=" %%f in ('dir /b /o-d /a-d "%PPDIR%\*.pdf" 2^>nul') do (
    if not defined PDF (
        for /f %%d in ('powershell -NoProfile -Command "(Get-Item '!PPDIR!\%%f').LastWriteTime.ToString('yyyyMMdd')"') do (
            if "%%d"=="%TODAY%" set "PDF=%%f"
        )
    )
)

if not defined PDF (
    echo   [ERROR] No PP file dated today ^(%TODAY%^) found.
    echo.
    echo   Files currently in folder:
    dir /b /a-d "%PPDIR%\*.pdf" 2>nul
    if errorlevel 1 echo     ^(none^)
    echo.
    echo   If the PP file was just downloaded, check its modification date
    echo   matches today. You can run this script with the full PDF path as
    echo   an argument if you need to force a specific file.
    echo.
    pause
    goto :eof
)

echo   Found PP file : %PDF%
echo.

:: ── Define output file paths ──────────────────────────────────────────────
set "LOGFILE=%SCRIPTS%handicap-logs\HANDICAP_%TRACK%_%TODAY%.txt"
set "PICKSFILE=%SCRIPTS%picks_%TRACK%_%PICKSDATE%.txt"

echo   Handicap log  : handicap-logs\HANDICAP_%TRACK%_%TODAY%.txt
echo   Picks file    : picks_%TRACK%_%PICKSDATE%.txt
echo.

:: ── Delete existing handicap log ──────────────────────────────────────────
if exist "%LOGFILE%" (
    echo   Deleting existing handicap log...
    del "%LOGFILE%"
    echo   [OK] Deleted HANDICAP_%TRACK%_%TODAY%.txt
) else (
    echo   No existing handicap log to delete.
)
echo.

:: ── Delete existing picks file ────────────────────────────────────────────
if exist "%PICKSFILE%" (
    echo   Deleting existing picks file...
    del "%PICKSFILE%"
    echo   [OK] Deleted picks_%TRACK%_%PICKSDATE%.txt
) else (
    echo   No existing picks file to delete.
)
echo.

:: ── Run parser ────────────────────────────────────────────────────────────
echo   Running brisnet_parser_v2.py...
echo   -----------------------------------------------------------------------
py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" %TRACK% > "%LOGFILE%"
echo   -----------------------------------------------------------------------
echo.

:: ── Verify output ─────────────────────────────────────────────────────────
if not exist "%LOGFILE%" (
    echo   [ERROR] Handicap log was not created. Parser likely crashed.
    echo   Try running manually:
    echo   py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" %TRACK%
    echo.
    pause
    goto :eof
)

echo   [OK] Handicap log created.
if exist "%PICKSFILE%" (
    echo   [OK] Picks file created: picks_%TRACK%_%PICKSDATE%.txt
) else (
    echo   [WARN] Picks file was not created -- check log for parse errors.
)
echo.

:: ── Print the card ────────────────────────────────────────────────────────
echo   -----------------------------------------------------------------------
echo   HANDICAP CARD:
echo   -----------------------------------------------------------------------
echo.
type "%LOGFILE%"

:done
echo.
echo ########################################################################
echo   REPARSE COMPLETE -- %TRACK% %TODAY%
echo ########################################################################
echo.
pause
goto :eof

:: ── Helper: uppercase a variable in-place ────────────────────────────────
:TOUPPER
for %%c in (A B C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    set "%~1=!%~1:%%c=%%c!"
)
:: Use PowerShell for reliable uppercase conversion
for /f %%u in ('powershell -NoProfile -Command "'!%~1!'.ToUpper()"') do set "%~1=%%u"
goto :eof
