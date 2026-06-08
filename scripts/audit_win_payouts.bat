@echo off
title Audit Win Payouts
set "SCRIPTS=%~dp0"
py -u "%SCRIPTS%audit_win_payouts.py" %*
pause
