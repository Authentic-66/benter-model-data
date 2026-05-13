@echo off
title Update Model Workbook
set "SCRIPTS=%~dp0"

echo.
echo ########################################################################
echo   BENTER MODEL -- UPDATE WORKBOOK
echo ########################################################################
echo.
echo   Reading handicap-logs, results-logs, and roi-logs...
echo   Writing sheets to benter_model_master.xlsx
echo.

py "%SCRIPTS%update_workbook.py"

echo.
pause
