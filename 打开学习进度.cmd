@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0learning-dashboard\launch.ps1"
if errorlevel 1 pause
