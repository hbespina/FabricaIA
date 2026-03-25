@echo off
title Modernization Factory - Startup
echo ==========================================
echo    OTSO MODERNIZATION FACTORY V3.0
echo ==========================================
echo.
echo [1/3] Verificando dependencias Python...
pip install fastapi uvicorn boto3 python-dotenv

echo.
echo [2/3] Iniciando Backend Proxy (Bedrock)...
start cmd /k "cd server && python main.py"

echo.
echo [3/3] Iniciando Dashboard...
start index.html

echo.
echo ==========================================
echo FACTORIA LISTA: http://localhost:8000
echo Revisa que tu archivo server/.env tenga las credenciales AWS.
echo ==========================================
pause
