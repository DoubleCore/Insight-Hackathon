@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_acceptance_platform.ps1" %*
