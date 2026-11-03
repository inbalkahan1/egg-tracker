@echo off
cd /d "%~dp0"
"C:\Users\camera\Documents\masking\sam2-env\python.exe" "%~dp0collection.py"
if errorlevel 1 pause
