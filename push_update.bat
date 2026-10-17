@echo off
REM Usage: push_update.bat            (default message)
REM        push_update.bat "my message"
set MSG=%~1
if "%MSG%"=="" set MSG=Add orders database, Case Detective, action verification and smart handover
git add -A
git commit -m "%MSG%"
git push
echo Pushed. Render will redeploy automatically.
