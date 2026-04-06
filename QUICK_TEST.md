# 🧪 QUICK START: Cómo Probar - 3 Opciones

## ⚡ OPCIÓN 1: Test Más Rápido (30 segundos)

**Desde PowerShell:**
```powershell
cd c:\Users\hberrioe\Fabrica
node test-end-to-end.cjs
```

**Verás:**
```
✅ TEST 1: Validación de datos    → OK
✅ TEST 2: Stage 1 Discovery      → 5 componentes detectados
✅ TEST 3: Stage 2 Advanced       → Technical Debt 82/100
✅ TEST 4: Stage 3 IA             → Roadmap 12 meses
✅ TEST 5: Dashboard              → 6 secciones listas
✅ TEST 6: Exports                → JSON/PDF/JIRA ready

OVERALL: ✅ PASSED (27 tests, 0 errors)
```

---

## 🌐 OPCIÓN 2: Dashboard en Navegador (5 minutos)

### Paso 1️⃣: Inicia Backend
```powershell
# En PowerShell
C:/Users/hberrioe/AppData/Local/Programs/Python/Python313/python.exe backend.py

# Output:
# Modernization Factory — Backend API v2.0
# Endpoints:
#   GET  /health
#   POST /collect
#   POST /analyze
```

### Paso 2️⃣: Abre Dashboard
```
http://localhost:8000
```

### Paso 3️⃣: Ingresa Datos de Prueba

En **Tab: "Análisis de Código"**

Copia y pega esto:
```
HOSTNAME: legacy-prod-01
Java version 1.8.0_191
Oracle Database 12.2 Port 1521
WebSphere Application Server 9.0.0.0
Tomcat 8.5 Port 8080
Apache 2.4 Port 80/443
commons-dbcp-1.4.jar
axis-1.4.jar
log4j-1.2.15.jar
```

### Paso 4️⃣: Haz Clic en "Iniciar Análisis"

**Espera 150ms → Ver resultados:**

✅ Componentes: 5 detectados  
✅ Deuda Técnica: 82/100 (CRÍTICO)  
✅ Anti-patterns: 4 (MONOLITHIC, LEGACY, CIRCULAR, NO_DOCKER)  
✅ SOLID: 2.6/10 (POOR)  
✅ Data Flows: Latencia 180ms (bottleneck: DB)  

---

## 📊 OPCIÓN 3: Con Datos Reales (10-15 minutos)

### Paso 1️⃣: Recolectar Datos

**En un servidor Linux/WSL:**
```bash
# Ejecutar en sistema legacy (RHEL, Debian, Ubuntu, Solaris, AIX)
chmod +x collector.sh
./collector.sh

# Output: inventory_hostname_timestamp.txt (3-10 MB)
```

**O si estás en Windows con WSL:**
```powershell
# En PowerShell
wsl chmod +x collector.sh
wsl ./collector.sh
```

### Paso 2️⃣: Copiar Datos

```bash
# Copiar output completo
cat inventory_legacy_prod_20240330_145230.txt | clip

# O ver archivo:
cat modernization_reports/inventory_*.txt
```

### Paso 3️⃣: Pegar en Dashboard

1. Ir a http://localhost:8000
2. Tab: "Análisis de Código"
3. Pegar datos en formulario
4. Clic: "Iniciar Análisis"

### Paso 4️⃣: Obtener Reporte

**Resultados profesionales con:**
- ✅ Descubrimiento específico de tu sistema
- ✅ Deuda técnica cuantificada
- ✅ Anti-patterns identificados
- ✅ Roadmap de migración

**Exportar:**
```
Botón: "Exportar"
  ├─ JSON (para otros tools)
  ├─ PDF (para ejecutivos)
  └─ JIRA (para crear tickets)
```

---

## 📋 Checklist Rápido

- [ ] Backend corriendo: `http://localhost:8000/health` ← ✅ Debe responder
- [ ] Test simple: `node test-end-to-end.cjs` ← ✅ Debe pasar
- [ ] Dashboard abierto: `http://localhost:8000` ← ✅ Debe verse
- [ ] Datos ingresados: Fórmula completa ← ✅ Debe tener contenido
- [ ] Análisis ejecutado: Clic en botón ← ✅ Debe mostrar resultados
- [ ] Exportados: JSON/PDF/JIRA ← ✅ Debe descargar

---

## 🚨 Si Algo NO Funciona

| Problema | Fix Rápido |
|----------|-----------|
| `localhost:8000` falla | `netstat -ano \| findstr :8000` → Kill proceso viejo |
| Backend no inicia | Usa ruta completa: `C:/Python/python.exe backend.py` |
| Test falla con "require" | Usa `.cjs`: `node test-end-to-end.cjs` |
| No ve resultados | Pega DATOS antes de clic (no campo vacío) |
| AWS Bedrock error | Normal - requiere AWS credentials (skip) |

---

## 🎯 Resultado Esperado

Cuando todo funcione correctamente:

```
ENTRADA: 
  Raw data (ps aux, netstat, etc) 
  ~500- 5000 líneas

PROCESAMIENTO:
  ✅ Stage 1: Discovery (50ms)
  ✅ Stage 2: Advanced (100ms)
  ✅ Stage 3: IA (2-5s, opcional)
  
SALIDA:
  ✅ Technical Debt: 60-100/100
  ✅ Anti-patterns: 4-7 detectados
  ✅ SOLID Score: 2-5/10
  ✅ Roadmap: 4 fases, 12 meses, $1.5M
  ✅ ROI: 14 meses payback
  ✅ Exportable: JSON/PDF/JIRA
```

---

## 🎉 ¡Listo!

**Elige una opción y prueba ahora:**

1. **Fastest** ⚡ (30 seg): `node test-end-to-end.cjs`
2. **Visual** 🌐 (5 min): `http://localhost:8000` + datos
3. **Realistic** 📊 (15 min): collector.sh + dashboard

```
¿Cuál quieres probar primero?
```
