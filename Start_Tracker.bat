@echo off
cd /d "%~dp0"
"C:\Users\camera\Documents\masking\sam2-env\python.exe" "%~dp0tracker.py"
if errorlevel 1 pause
