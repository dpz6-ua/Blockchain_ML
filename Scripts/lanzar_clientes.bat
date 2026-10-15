@echo off
set EXP=%1
if "%EXP%"=="" set EXP=E3
set RUNS=%2
if "%RUNS%"=="" set RUNS=3
set SERVER_IP=%3
if "%SERVER_IP%"=="" set SERVER_IP=192.168.1.53
set START_RUN=%4
if "%START_RUN%"=="" set START_RUN=1

powershell -ExecutionPolicy Bypass -File "%~dp0lanzar_clientes.ps1" -Exp "%EXP%" -Runs %RUNS% -ServerIp "%SERVER_IP%" -StartRun %START_RUN%

