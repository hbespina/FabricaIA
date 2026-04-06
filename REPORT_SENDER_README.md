# Automation Report Sender - Guía de Uso

## 📋 Descripción

Automation Report Sender automatiza el proceso de recopilar reportes de modernización y enviarlos al backend para análisis. Detecta automáticamente las últimas coleções y las procesa.

## 🚀 Inicio Rápido

### Opción 1: Usar el Batch Script (Recomendado para Windows)

```bash
.\send-report.bat
```

Este script:
- ✅ Verifica que el backend esté corriendo
- ✅ Encuentra el último reporte generado
- ✅ Envía el reporte al endpoint `/analyze`
- ✅ Muestra resumen de resultados

### Opción 2: Ejecutar directamente con PowerShell

```powershell
# Enviar el último reporte
.\send-report.ps1

# Enviar un reporte específico
.\send-report.ps1 -reportFile ".\modernization_reports\inventory_myhost_20260330_120000.txt"

# Usar un backend diferente
.\send-report.ps1 -backend "http://192.168.1.100:5055"
```

## 📊 Flujo de Trabajo Completo

```
1. Generar Reporte (Linux/Mac)
   └─ chmod +x collector.sh && ./collector.sh
   └─ Crea: inventory_HOSTNAME_TIMESTAMP.txt

2. Enviar Reporte (Windows)
   └─ .\send-report.bat
   └─ Detecta último reporte
   └─ Envía a http://localhost:5055/analyze

3. Recibir Análisis
   └─ Backend procesa el reporte
   └─ Identifica frameworks, bases de datos, riesgos
   └─ Retorna insights de modernización
```

## 📝 Requisitos Previos

### Frontend
- Windows 10+
- PowerShell 5.0+
- curl (incluido en Windows 10+)

### Backend
- Node.js 18+
- Dependencias: `npm install express cors ssh2`
- Puerto 5055 disponible

### Generador de Reportes
- Bash shell (Linux/Mac/WSL)
- Permisos de ejecución: `chmod +x collector.sh`

## 🔄 Ejemplo de Flujo Completo

### Paso 1: Generar reporte (en servidor Linux)
```bash
$ chmod +x collector.sh
$ ./collector.sh
# Genera: ./modernization_reports/inventory_myserver_20260330_143022.txt
```

### Paso 2: Enviar reporte (en Windows con el archivo generado)
```powershell
PS> .\send-report.bat
```

### Paso 3: Ver resultados
```json
{
  "success": true,
  "hostname": "myserver",
  "analysis_id": "myserver-1703950622000",
  "insights": {
    "frameworks": {
      "java": 5,
      "nodejs": 0,
      "python": 2
    },
    "databases": {
      "oracle": 1,
      "postgres": 0
    },
    "risks": [
      "Legacy Java frameworks detected (Struts/Axis) - candidates for modernization",
      "Oracle database detected - consider cloud-native alternatives"
    ]
  }
}
```

## 📤 Estructura del Reporte

El script envía un JSON con:

```json
{
  "hostname": "servidor-produccion",
  "timestamp": "2026-03-30T14:30:22.000Z",
  "processes": 245,
  "disk_usage": 72,
  "report_size": 5242880,
  "content": "reporte completo...",
  "submitted_at": "2026-03-30T14:35:00.000Z"
}
```

## 🔍 Análisis Automático

El backend identifica automáticamente:

### Frameworks
- Java: Tomcat, JBoss, Spring, Hibernate, Axis, Struts
- Node.js: npm, package.json
- Python: pip, requirements.txt, Django, Flask
- .NET: mono, dotnet
- PHP: Laravel, Symfony

### Bases de Datos
- Oracle
- MySQL/MariaDB
- PostgreSQL
- MongoDB

### Contenedores
- Docker
- Kubernetes
- Podman

### Riesgos Detectados
- ⚠️ Legacy frameworks
- ⚠️ Alto uso de disco
- ⚠️ Bases de datos legacy
- ⚠️ Vulnerabilidades potenciales

## ⚙️ Configuración Avanzada

### Variable de entorno para ruta del reporte
```powershell
$env:REPORT_DIR = "C:\backups\reports"
.\send-report.ps1
```

### Enviar a backend remoto
```powershell
.\send-report.ps1 -backend "https://migration-api.company.com"
```

### Procesar archivo específico
```powershell
.\send-report.ps1 -reportFile "C:\reports\inventory_2026-03-30.txt"
```

## 📊 Monitoreo

### Ver reportes disponibles
```powershell
Get-ChildItem .\modernization_reports\*.txt | Sort-Object LastWriteTime
```

### Verificar backend
```powershell
curl http://localhost:5055/health
```

### Monitorear logs del backend
```bash
# En terminal del backend (Node.js)
node backend-node.js
# Ver logs en tiempo real
```

## 🔧 Troubleshooting

### Error: "Backend no disponible"
```powershell
# Solución: Iniciar el backend
node backend-node.js
```

### Error: "No se encontraron reportes"
```powershell
# Solución: Verificar que collector.sh ha sido ejecutado
# y que los reportes están en .\modernization_reports\
```

### Error: "Reporte muy grande"
El script automáticamente:
- Detecta reportes > 200KB
- Trunca elegantemente
- Mantiene datos más importantes

### Timeout en el envío
```powershell
# Para archivos muy grandes, aumentar timeout manualmente
# Editar send-report.ps1, línea ~120:
# -TimeoutSec 300  # Cambiar de 60 a 300 segundos
```

## 🔐 Seguridad

### Limitaciones de Tamaño
- Máximo reporte: 200MB
- Se trunca automáticamente a 150MB para envío
- Mantiene primeros 100KB + últimos 50KB

### Validación
- ✅ Hostname requerido
- ✅ Contenido del reporte requerido
- ✅ Validación de backend activo
- ✅ Manejo de errores en conexión

## 📈 Casos de Uso

### Use Case 1: Auditoría Diaria
```powershell
# Crear tarea programada de Windows
# Ejecutar cada día a las 2 AM
# Action: powershell -File ".\send-report.ps1"
```

### Use Case 2: Evaluación de Flota
```bash
# En servidor Linux
for host in server1 server2 server3; do
    ssh $host "./collector.sh"
done

# Luego en Windows
.\send-report.bat  # Envía todos los reportes
```

### Use Case 3: Migración Automatizada
```powershell
# 1. Generar reporte
# 2. Analizar
# 3. Generar plan de migración
# 4. Ejecutar transformaciones

while ($true) {
    .\send-report.ps1
    Start-Sleep -Seconds 3600  # Cada hora
}
```

## 📚 Archivos Relacionados

- `collector.sh` - Script de recopilación (Linux)
- `backend-node.js` - API de análisis (Node.js)
- `send-report.ps1` - Script de envío (PowerShell)
- `send-report.bat` - Wrapper ejecutable (DOS)
- `modernization_reports/` - Directorio de reportes

## 🎯 Próximos Pasos

1. ✅ Generar reportes con `collector.sh`
2. ✅ Enviar con `send-report.bat`
3. ⏳ Implementar almacenamiento de análisis
4. ⏳ Dashboard de visualización
5. ⏳ Generación automática de planes de migración

## 📞 Support

Para problemas:
1. Verificar logs del backend: `node backend-node.js` (con salida de consola)
2. Validar formato del reporte: `Get-Content .\modernization_reports\inventory_*.txt | head -30`
3. Verificar conectividad: `curl http://localhost:5055/health`

---

**Modernization Factory v2.0** | 2026
