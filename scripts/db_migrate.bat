@echo off
title Benter Model DB Migration
set "SCRIPTS=%~dp0"
py -u "%SCRIPTS%db_migrate.py" %*
pause
