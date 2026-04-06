# ============================================================================
# Modernization Factory - Report Sender
# Automates sending inventory reports to backend for analysis
# Usage: .\send-report.ps1 [-reportFile "path\to\report.txt"] [-backend "http://localhost:5055"]
# ============================================================================

param(
    [string]$reportFile,
    [string]$backend = "http://localhost:5055",
    [string]$hostname = $env:COMPUTERNAME,
    [string]$outputDir = "./modernization_reports"
)

# Colors for output
$colors = @{
    'Success' = 'Green'
    'Error'   = 'Red'
    'Info'    = 'Cyan'
    'Warning' = 'Yellow'
}

function Write-Log {
    param([string]$message, [string]$level = 'Info')
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $prefix = "[$timestamp]"
    Write-Host "$prefix $message" -ForegroundColor $colors[$level]
}

# ============================================================================
# 1. Find Latest Report
# ============================================================================

function Find-LatestReport {
    param([string]$directory)
    
    Write-Log "Buscando reportes en: $directory" 'Info'
    
    if (-not (Test-Path $directory)) {
        Write-Log "ERROR: No se encontró directorio '$directory'" 'Error'
        return $null
    }
    
    $reports = Get-ChildItem -Path $directory -Filter "inventory_*.txt" | Sort-Object LastWriteTime -Descending
    if ($reports.Count -eq 0) {
        Write-Log "ERROR: No se encontraron reportes" 'Error'
        return $null
    }
    
    $latest = $reports[0]
    Write-Log "Reporte encontrado: $($latest.Name) ($('{0:F2}' -f ($latest.Length/1MB))MB)" 'Success'
    return $latest.FullName
}

# ============================================================================
# 2. Parse Report
# ============================================================================

function Parse-Report {
    param([string]$filePath)
    
    Write-Log "Analizando reporte..." 'Info'
    
    $content = Get-Content -Path $filePath -Raw
    
    # Extract key sections
    $report = @{
        'file'        = $filePath
        'size_bytes'  = (Get-Item $filePath).Length
        'hostname'    = ($content | Select-String 'HOSTNAME: (.+)' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1) -or "unknown"
        'timestamp'   = ($content | Select-String 'TIMESTAMP: (.+)' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1) -or (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        'processes'   = ($content | Select-String -Pattern 'java|python|node|mysql|postgres' | Measure-Object).Count
        'disk_usage'  = ($content | Select-String 'Usage Percentage: (\d+)' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1) -or "unknown"
    }
    
    Write-Log "  Hostname: $($report.hostname)" 'Info'
    Write-Log "  Procesos detectados: $($report.processes)" 'Info'
    Write-Log "  Uso de disco: $($report.disk_usage)%" 'Info'
    
    return $report
}

# ============================================================================
# 3. Send Report to Backend
# ============================================================================

function Send-Report {
    param(
        [string]$backendUrl,
        [string]$reportFile,
        [hashtable]$metadata
    )
    
    Write-Log "Conectando a backend: $backendUrl" 'Info'
    
    # Test backend health
    try {
        $health = Invoke-RestMethod -Uri "$backendUrl/health" -Method Get -ErrorAction Stop
        Write-Log "Backend activo: $($health.status) (v$($health.version))" 'Success'
    } catch {
        Write-Log "ERROR: Backend no disponible" 'Error'
        Write-Log "  $_" 'Error'
        return $false
    }
    
    # Read report content
    $reportContent = Get-Content -Path $reportFile -Raw
    
    # Truncate if too large (Keep first 100KB + last 50KB)
    if ($reportContent.Length -gt 200KB) {
        Write-Log "Reporte muy grande ($('{0:F2}' -f ($reportContent.Length/1MB))MB). Truncando..." 'Warning'
        $head = $reportContent.Substring(0, 100KB)
        $tail = $reportContent.Substring($reportContent.Length - 50KB)
        $reportContent = $head + "`n...[TRUNCATED]...`n" + $tail
    }
    
    # Prepare payload
    $payload = @{
        'hostname'      = $metadata.hostname
        'timestamp'     = $metadata.timestamp
        'processes'     = $metadata.processes
        'disk_usage'    = $metadata.disk_usage
        'report_size'   = $metadata.size_bytes
        'content'       = $reportContent
        'submitted_at'  = (Get-Date -Format 'o')
    }
    
    # Send to backend
    try {
        Write-Log "Enviando reporte (~$('{0:F2}' -f ($reportContent.Length/1MB))MB)..." 'Info'
        
        $response = Invoke-RestMethod `
            -Uri "$backendUrl/analyze" `
            -Method Post `
            -ContentType "application/json" `
            -Body ($payload | ConvertTo-Json -Depth 10) `
            -TimeoutSec 60 `
            -ErrorAction Stop
        
        Write-Log "✓ Reporte enviado exitosamente" 'Success'
        Write-Log "  Response: $($response | ConvertTo-Json -Compress)" 'Info'
        return $true
    } catch {
        # If /analyze doesn't exist, try /collect
        Write-Log "Endpoint /analyze no disponible, intentando /collect..." 'Warning'
        
        try {
            $response = Invoke-RestMethod `
                -Uri "$backendUrl/collect" `
                -Method Post `
                -ContentType "application/json" `
                -Body ($payload | ConvertTo-Json -Depth 10) `
                -TimeoutSec 60 `
                -ErrorAction Stop
            
            Write-Log "✓ Reporte enviado via /collect" 'Success'
            return $true
        } catch {
            Write-Log "ERROR: No se pudo enviar el reporte" 'Error'
            Write-Log "  $_" 'Error'
            return $false
        }
    }
}

# ============================================================================
# 4. Generate Summary Report
# ============================================================================

function Write-Summary {
    param([hashtable]$metadata, [bool]$success)
    
    $status = $success ? 'ÉXITO' : 'FALLÓ'
    $statusColor = $success ? 'Success' : 'Error'
    
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║         MODERNIZATION FACTORY - ENVÍO DE REPORTE          ║" -ForegroundColor Cyan
    Write-Host "╠════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║ Estado: " -NoNewline -ForegroundColor Cyan
    Write-Host "$status" -ForegroundColor $statusColor
    Write-Host "║ Hostname: $($metadata.hostname)" -ForegroundColor Cyan
    Write-Host "║ Tamaño: $('{0:F2}' -f ($metadata.size_bytes/1MB))MB" -ForegroundColor Cyan
    Write-Host "║ Timestamp: $($metadata.timestamp)" -ForegroundColor Cyan
    Write-Host "║ Procesos: $($metadata.processes)" -ForegroundColor Cyan
    Write-Host "║ Disco: $($metadata.disk_usage)%" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================================
# MAIN
# ============================================================================

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   MODERNIZATION FACTORY - Report Send Automation V2.0        ║" -ForegroundColor Magenta
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# Determine report file
if ($reportFile) {
    if (-not (Test-Path $reportFile)) {
        Write-Log "ERROR: Archivo no encontrado: $reportFile" 'Error'
        exit 1
    }
} else {
    $reportFile = Find-LatestReport -directory $outputDir
    if (-not $reportFile) {
        exit 1
    }
}

# Parse report
$metadata = Parse-Report -filePath $reportFile

# Send to backend
$success = Send-Report -backendUrl $backend -reportFile $reportFile -metadata $metadata

# Summary
Write-Summary -metadata $metadata -success $success

exit ($success ? 0 : 1)
