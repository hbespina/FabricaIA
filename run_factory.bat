@echo off
title Modernization Factory - Startup
echo ==========================================
echo    OTSO MODERNIZATION FACTORY V3.0
echo ==========================================
echo.
echo [1/4] ¿Deseas iniciar con Docker (Microservicios)? (S/N)
set /p DOCKER_CHOICE= 
if /I "%DOCKER_CHOICE%"=="S" (
    echo Iniciando con Docker Compose...
    docker-compose up --build
    pause
    exit
)

echo [2/4] Verificando dependencias Python...
pip install fastapi uvicorn boto3 python-dotenv

echo.
echo [3/4] Iniciando Backend Proxy (Bedrock)...
start cmd /k "cd server && python main.py"

echo.
echo [4/4] Iniciando Dashboard...
start index.html

echo.
echo ==========================================
echo FACTORIA LISTA: http://localhost:8000
echo Revisa que tu archivo server/.env tenga las credenciales AWS.
echo ==========================================
pause
