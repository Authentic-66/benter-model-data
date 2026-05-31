@echo off
title Reparse Track
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"

if "%~1"=="" (
    echo.
    echo   Usage: reparse.bat [TRACK_CODE]
    echo   Valid codes: CT, FP, GP, EVD, DD, FG, MVR, LRL
    echo.
    pause
    goto :eof
)

set "TRACK=%~1"
set "PPDIR="

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"
if not exist "%SCRIPTS%handicap-logs\" mkdir "%SCRIPTS%handicap-logs"

if /i "%TRACK%"=="CT"  ( set "PPDIR=%BASE%\CharlesTown\ct-pps-files"            & set "TRACK=CT"  )
if /i "%TRACK%"=="FP"  ( set "PPDIR=%BASE%\Fairmount Park\fp-pps-files"          & set "TRACK=FP"  )
if /i "%TRACK%"=="GP"  ( set "PPDIR=%BASE%\Gulfstream Park\gp-pps-files"         & set "TRACK=GP"  )
if /i "%TRACK%"=="EVD" ( set "PPDIR=%BASE%\Evangeline Downs\evd-pps-files"       & set "TRACK=EVD" )
if /i "%TRACK%"=="DD"  ( set "PPDIR=%BASE%\Delta Downs\dd-pps-files"             & set "TRACK=DD"  )
if /i "%TRACK%"=="FG"  ( set "PPDIR=%BASE%\Fair Grounds\fg-pps-files"            & set "TRACK=FG"  )
if /i "%TRACK%"=="MVR" ( set "PPDIR=%BASE%\Mahoning Valley\mvr-pps-files"        & set "TRACK=MVR" )
if /i "%TRACK%"=="LRL" ( set "PPDIR=%BASE%\Laurel Park\laurel-pp-files"          & set "TRACK=LRL" )

echo.
echo ########################################################################
echo   BENTER MODEL -- FORCE REPARSE: %TRACK%
echo ########################################################################
echo.
echo   Base dir : %BASE%
echo   PP dir   : %PPDIR%
echo.

if not defined PPDIR (
    echo   [ERROR] Unknown track code: %TRACK%
    echo   Valid codes: CT, FP, GP, EVD, DD, FG, MVR, LRL
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

echo   Scanning: %PPDIR%
echo.

for /f "delims=" %%f in ('dir /b /o-d /a-d "%PPDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo   [ERROR] No PDF files found in that folder.
echo.
pause
goto :eof

:run
set "LOGFILE=%SCRIPTS%handicap-logs\HANDICAP_%TRACK%_%TODAY%.txt"
echo   PP file  : %PDF%
echo   Full path: %PPDIR%\%PDF%
echo   Log file : %LOGFILE%
if exist "%LOGFILE%" echo   [NOTE] Overwriting existing log.
echo.
echo   Running parser...
py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" %TRACK% > "%LOGFILE%"
echo.
if exist "%LOGFILE%" (
    echo   [OK] Log written -- %LOGFILE%
) else (
    echo   [ERROR] Log file was not created. Parser may have failed.
    goto :done
)
echo.
type "%LOGFILE%"

:done
echo.
echo ########################################################################
echo   REPARSE COMPLETE
echo ########################################################################
echo.
pause
