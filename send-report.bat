@echo off
REM ============================================================================
REM Modernization Factory - Send Report (Windows Batch Wrapper)
REM ============================================================================

setlocal enabledelayedexpansion
set "REPORT_DIR=.\modernization_reports"
set "BACKEND=http://localhost:5055"

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║   MODERNIZATION FACTORY - Envio de Reportes v2.0            ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Check if PowerShell is available
where /q powershell
if errorlevel 1 (
    echo ERROR: PowerShell no está disponible
    exit /b 1
)

REM Check if backend is running
echo [*] Verificando backend en %BACKEND%...
curl -s -f %BACKEND%/health >nul 2>&1
if errorlevel 1 (
    echo ERROR: Backend no disponible en %BACKEND%
    echo Asegúrate de iniciar: node backend-node.js
    exit /b 1
)
echo [OK] Backend activo

REM Run PowerShell script
echo [*] Iniciando envío de reporte...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\send-report.ps1" -backend "%BACKEND%" -outputDir "%REPORT_DIR%"

if errorlevel 1 (
    echo.
    echo ERROR: Fallo en el envío. Intenta nuevamente o verifica los logs.
    exit /b 1
) else (
    echo.
    echo [OK] Reporte procesado exitosamente
    exit /b 0
)

endlocal
