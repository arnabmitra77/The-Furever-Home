@echo off
REM ============================================================
REM  Furever Home — Nightly Database Reminder
REM  Runs at 1am via Windows Task Scheduler
REM  Opens Google Sheet for manual review + restarts local server
REM ============================================================

echo [%date% %time%] Starting nightly Furever Home refresh... >> "f:\Pet Proj 2\refresh_log.txt"

REM Open Google Sheet in browser for review/update
start "" "https://docs.google.com/spreadsheets/d/1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80/edit"

REM Log completion
echo [%date% %time%] Sheet opened for review. >> "f:\Pet Proj 2\refresh_log.txt"

exit /b 0
