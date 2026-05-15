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
py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" CT
echo.

:: Save picks to handicap-logs
if not exist "%SCRIPTS%handicap-logs\" mkdir "%SCRIPTS%handicap-logs"
for /f "delims=" %%f in ('dir /b /o-d /a-d "%SCRIPTS%picks_CT_*.txt" 2^>nul') do (
    set "PICKS=%%f"
    goto :log_picks
)
goto :done
:log_picks
copy /y "%SCRIPTS%%PICKS%" "%SCRIPTS%handicap-logs\HANDICAP_CT_%TODAY%.txt" > nul
echo Picks logged: handicap-logs\HANDICAP_CT_%TODAY%.txt
:done
echo.
pause
