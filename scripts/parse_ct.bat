@echo off
title Parse CT Past Performances
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "PPDIR=%BASE%\CharlesTown\ct-pps-files"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%d"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%PPDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No PP file found in: %PPDIR%
pause & exit /b 1

:run
for /f %%d in ('powershell -NoProfile -Command "(Get-Item '%PPDIR%\%PDF%').LastWriteTime.ToString('yyyyMMdd')"') do set "FILEDATE=%%d"
if not "%FILEDATE%"=="%TODAY%" (
    echo File date [%FILEDATE%] does not match today [%TODAY%] - skipping CT
    pause & exit /b 0
)
echo Parsing CT: %PDF%
echo.
if not exist "%SCRIPTS%handicap-logs\" mkdir "%SCRIPTS%handicap-logs"
set "LOGFILE=%SCRIPTS%handicap-logs\HANDICAP_CT_%TODAY%.txt"
py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" CT > "%LOGFILE%"
type "%LOGFILE%"
echo.
echo Full card logged: handicap-logs\HANDICAP_CT_%TODAY%.txt
echo.
pause
