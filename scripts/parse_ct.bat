@echo off
title Parse CT Past Performances
set "SCRIPTS=%~dp0"
for %%d in ("%SCRIPTS%..") do set "BASE=%%~fd"
set "PPDIR=%BASE%\CharlesTown\ct-pps-files"

for /f "delims=" %%f in ('dir /b /o-d /a-d "%PPDIR%\*.pdf" 2^>nul') do (
    set "PDF=%%f"
    goto :run
)
echo No PP file found in: %PPDIR%
pause & exit /b 1

:run
echo Parsing CT: %PDF%
echo.
py "%SCRIPTS%brisnet_parser_v2.py" "%PPDIR%\%PDF%" CT
echo.
pause
