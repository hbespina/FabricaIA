@echo off
setlocal enabledelayedexpansion
title Modernization Factory V5.0

set PORT=8000
set HOST=0.0.0.0
set VENV=.venv\Scripts
set API_KEY=mf-api-key-2026
set APP_URL=http://localhost:%PORT%
set LOG_FILE=logs\factory.log

if not exist logs mkdir logs

if /I "%~1"=="start"   goto :do_start
if /I "%~1"=="stop"    goto :do_stop
if /I "%~1"=="restart" goto :do_restart
if /I "%~1"=="status"  goto :do_status
if /I "%~1"=="logs"    goto :do_logs

:main_menu
cls
echo.
echo  ==========================================
echo   MODERNIZATION FACTORY  v5.0  - OTSO
echo   AWS Bedrock Nova Pro  . RAG . 6 Agentes
echo  ==========================================
call :check_server
echo  ==========================================
echo.
echo   [1] Iniciar  Factory
echo   [2] Detener  Factory
echo   [3] Reiniciar Factory
echo   [4] Ver Estado y Metricas
echo   [5] Ver Logs en tiempo real
echo   [6] Abrir en Navegador
echo   [7] Instalar / Actualizar dependencias
echo   [8] Iniciar LocalStack (AWS offline)
echo   [9] Detener LocalStack
echo   [0] Salir
echo.
set /p CHOICE=  Opcion [0-9]:

if "!CHOICE!"=="1" goto :do_start
if "!CHOICE!"=="2" goto :do_stop
if "!CHOICE!"=="3" goto :do_restart
if "!CHOICE!"=="4" goto :do_status
if "!CHOICE!"=="5" goto :do_logs
if "!CHOICE!"=="6" goto :do_open
if "!CHOICE!"=="7" goto :do_install
if "!CHOICE!"=="8" goto :do_localstack_start
if "!CHOICE!"=="9" goto :do_localstack_stop
if "!CHOICE!"=="0" goto :eof
goto :main_menu

:check_server
    curl -s -o nul -w "%%{http_code}" --connect-timeout 2 %APP_URL%/health > "%TEMP%\mf_hc.txt" 2>nul
    set /p HTTP_CODE=<"%TEMP%\mf_hc.txt"
    if "!HTTP_CODE!"=="200" (
        echo   [ON]  Servidor CORRIENDO en %APP_URL%
    ) else (
        echo   [--]  Servidor DETENIDO
    )
    exit /b

:do_start
cls
echo.
echo  ==========================================
echo   INICIANDO FACTORY...
echo  ==========================================
echo.

netstat -ano 2>nul | findstr ":%PORT%.*LISTENING" >nul
if !ERRORLEVEL!==0 (
    echo  [!] Puerto %PORT% ya esta en uso.
    echo      Usa la opcion [2] para detener primero.
    echo.
    pause
    goto :main_menu
)

if not exist "%VENV%\python.exe" (
    echo  Creando entorno virtual...
    py -m venv .venv
    if !ERRORLEVEL! NEQ 0 (
        echo  [ERROR] No se pudo crear el entorno virtual.
        pause
        goto :main_menu
    )
)

%VENV%\python.exe -c "import fastapi, uvicorn" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo  Instalando dependencias...
    %VENV%\pip.exe install -r server\requirements.txt -q
)

if not exist "server\.env" (
    echo  [!] Falta server\.env con credenciales AWS.
    echo      Crea ese archivo antes de continuar.
    echo.
    pause
    goto :main_menu
)

echo  [1/3] Entorno OK
echo  [2/3] Iniciando backend en %APP_URL% ...
echo.

start "Factory Backend" cmd /k "%VENV%\uvicorn.exe server.main:app --host %HOST% --port %PORT% --reload"

echo  [3/3] Esperando respuesta del servidor...
set TRIES=0
:wait_loop
timeout /t 1 /nobreak >nul
set /a TRIES+=1
curl -s -o nul -w "%%{http_code}" --connect-timeout 1 %APP_URL%/health > "%TEMP%\mf_hc.txt" 2>nul
set /p HTTP_CODE=<"%TEMP%\mf_hc.txt"
if "!HTTP_CODE!"=="200" goto :start_ok
if !TRIES! LSS 15 goto :wait_loop
echo  [!] Servidor no respondio en 15s. Revisa la ventana del backend.
pause
goto :main_menu

:start_ok
echo.
echo  OK - Factory iniciada en %APP_URL%
echo.
call :fetch_metrics
echo.
set /p OB=  Abrir en navegador? [S/N]:
if /I "!OB!"=="S" start "" "%APP_URL%"
echo.
pause
goto :main_menu

:do_stop
cls
echo.
echo  ==========================================
echo   DETENIENDO FACTORY...
echo  ==========================================
echo.
set KILLED=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT%.*LISTENING"') do (
    echo  Deteniendo PID %%a...
    taskkill /F /PID %%a >nul 2>&1
    set KILLED=1
)
timeout /t 2 /nobreak >nul
netstat -ano 2>nul | findstr ":%PORT%.*LISTENING" >nul
if !ERRORLEVEL!==0 (
    echo  [!] No se pudo liberar el puerto. Intenta manualmente:
    echo      taskkill /F /IM python.exe
) else (
    if "!KILLED!"=="1" (
        echo  OK - Factory detenida.
    ) else (
        echo  La factory ya estaba detenida.
    )
)
echo.
pause
goto :main_menu

:do_restart
echo.
echo  Reiniciando...
call :do_stop_silent
timeout /t 2 /nobreak >nul
goto :do_start

:do_stop_silent
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT%.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
exit /b

:do_status
cls
echo.
echo  ==========================================
echo   ESTADO DE LA FACTORY
echo  ==========================================
echo.

curl -s -o nul -w "%%{http_code}" --connect-timeout 2 %APP_URL%/health > "%TEMP%\mf_hc.txt" 2>nul
set /p HTTP_CODE=<"%TEMP%\mf_hc.txt"

if "!HTTP_CODE!"=="200" (
    echo  [ON] Servidor CORRIENDO en %APP_URL%
    echo.
    echo  --- Proceso ---
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT%.*LISTENING"') do (
        echo  PID: %%a
    )
    echo.
    echo  --- Metricas ---
    call :fetch_metrics
) else (
    echo  [--] Servidor DETENIDO
)

echo.
echo  --- LocalStack ---
curl -s -o nul -w "%%{http_code}" --connect-timeout 2 http://localhost:4566/_localstack/health > "%TEMP%\mf_ls.txt" 2>nul
set /p LS_CODE=<"%TEMP%\mf_ls.txt"
if "!LS_CODE!"=="200" (
    echo  [ON] LocalStack CORRIENDO en http://localhost:4566
) else (
    echo  [--] LocalStack DETENIDO
)

echo.
echo  --- Entorno ---
%VENV%\python.exe --version 2>nul
echo  Puerto:  %PORT%
echo  API Key: %API_KEY%
echo  Log:     %LOG_FILE%
echo.
pause
goto :main_menu

:fetch_metrics
    %VENV%\python.exe scripts\factory_metrics.py 2>nul
    exit /b

:do_logs
cls
echo.
echo  Logs en tiempo real (Ctrl+C para volver)...
echo.
if exist "%LOG_FILE%" (
    powershell -Command "Get-Content '%LOG_FILE%' -Wait -Tail 40"
) else (
    echo  No hay log todavia. Inicia la factory primero.
    pause
)
goto :main_menu

:do_open
start "" "%APP_URL%"
goto :main_menu

:do_install
cls
echo.
echo  ==========================================
echo   INSTALANDO DEPENDENCIAS...
echo  ==========================================
echo.
if not exist "%VENV%\python.exe" (
    echo  Creando entorno virtual...
    py -m venv .venv
)
echo  Instalando paquetes...
%VENV%\pip.exe install -r server\requirements.txt --upgrade -q
echo.
echo  OK - Paquetes instalados:
%VENV%\pip.exe list 2>nul | findstr /i "fastapi uvicorn boto3 fpdf paramiko"
echo.
pause
goto :main_menu

:do_localstack_start
cls
echo.
echo  ==========================================
echo   INICIANDO LOCALSTACK...
echo  ==========================================
echo.
docker --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo  [!] Docker no encontrado. Instala Docker Desktop.
    pause
    goto :main_menu
)
set LS_COMPOSE=
if exist "docker-compose.localstack.yml" set LS_COMPOSE=docker-compose.localstack.yml
if "!LS_COMPOSE!"=="" (
    echo  [!] No se encontro docker-compose.localstack.yml
    echo      Descarga el Bundle desde la factory primero.
    pause
    goto :main_menu
)
docker compose -f "!LS_COMPOSE!" up -d
if !ERRORLEVEL!==0 (
    echo.
    echo  OK - LocalStack iniciado en http://localhost:4566
    echo  Servicios: S3, Secrets Manager, SQS, SSM
) else (
    echo  [!] Error. Verifica que Docker Desktop este corriendo.
)
echo.
pause
goto :main_menu

:do_localstack_stop
cls
echo.
echo  Deteniendo LocalStack...
docker compose -f docker-compose.localstack.yml down 2>nul
docker stop localstack 2>nul
echo  OK - LocalStack detenido.
echo.
pause
goto :main_menu
