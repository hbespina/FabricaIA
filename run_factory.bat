@echo off
setlocal enabledelayedexpansion
title Modernization Factory - Startup V3.1
echo ==========================================
echo    OTSO MODERNIZATION FACTORY V3.1
echo ==========================================
echo.

:menu
echo [1/4] ¿Deseas iniciar con Docker (Microservicios)? (S/N)
set /p DOCKER_CHOICE=
if /I "!DOCKER_CHOICE!"=="S" goto run_docker
if /I "!DOCKER_CHOICE!"=="N" goto run_local
goto menu

:run_docker
echo.
echo Intentando con Docker Compose (V2)...
docker compose up --build
if !ERRORLEVEL! EQU 0 (
    echo Docker V2 iniciado correctamente.
    pause
    exit
)

echo.
echo Fallback: Intentando con docker-compose (V1)...
docker-compose up --build
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] No se pudo iniciar Docker. Asegurate que Docker Desktop este corriendo y en el PATH.
)
pause
exit

:run_local
echo.
echo [2/4] Verificando entorno virtual...
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    py -m venv .venv
)

echo.
echo [2b/4] Instalando dependencias...
.venv\Scripts\pip install -r server\requirements.txt --only-binary :all: -q

echo.
echo [3/4] Iniciando Backend (Bedrock)...
start cmd /k ".venv\Scripts\python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [4/4] Iniciando Dashboard...
start http://localhost:8000

echo.
echo ==========================================
echo FACTORIA LISTA: http://localhost:8000
echo Revisa que tu archivo server/.env tenga las credenciales AWS.
echo ==========================================
pause
exit
