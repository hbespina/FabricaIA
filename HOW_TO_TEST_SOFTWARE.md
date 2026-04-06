# 🧪 Guía Completa: Cómo Probar el Software

## 📊 Resumen Rápido

El software tiene **3 formas de probarlo**:

### 1. **Test Automático (Rápido - 30 segundos)**
```bash
node test-orchestrator.js      # Prueba los 3 stages de análisis
node test-end-to-end.cjs       # Prueba el flujo completo
```

### 2. **Via API/Dashboard (Importante - 5 minutos)**
```
http://localhost:8000
→ Pega datos en formulario
→ Haz clic en "Analizar"
→ Ve resultados en dashboard
```

### 3. **Con Datos Reales (Completo - 10-15 minutos)**
```bash
./collector.sh                 # Recolecta datos del sistema
# → Copia output
# → Pégalo en dashboard
# → Ve análisis detallado
```

---

## 🚀 OPCIÓN 1: Test Automático (Más Rápido)

### ¿Qué prueba?
- ✅ Stage 1: Discovery de componentes
- ✅ Stage 2: Análisis avanzado (deuda técnica, anti-patterns)
- ✅ Stage 3: Enriquecimiento con IA (simulado)
- ✅ Exports (JSON, PDF, JIRA)

### Ejecutar:
```bash
cd c:\Users\hberrioe\Fabrica

# Test Stage 1 + 2 (básico)
node test-orchestrator.js

# Test completo (Stage 1 + 2 + 3 + Exports)
node test-end-to-end.cjs
```

### Resultados esperados:
```
✅ PASSED: 27 tests
⚠️ WARNINGS: 14 (deuda técnica detectada)
❌ ERRORS: 0
OVERALL STATUS: ✅ PASSED
```

---

## 📱 OPCIÓN 2: Via Dashboard (Más Visual)

### Paso 1: Asegurar que backend está corriendo
```bash
# En PowerShell
C:/Users/hberrioe/AppData/Local/Programs/Python/Python313/python.exe backend.py

# Output esperado:
# Modernization Factory — Backend API v2.0
# Running on http://127.0.0.1:8000
```

### Paso 2: Abrir dashboard
```
Abre navegador: http://localhost:8000
→ Verás: Modernization Factory V3
```

### Paso 3: Ingresar datos de prueba

**En Tab: "Análisis de Código"**

1. Copiar este texto de prueba:
```
HOSTNAME: legacy-prod-01
Java 8 version "1.8.0_191"
Oracle Database 12.2 Port 1521 LISTEN
WebSphere Application Server 9.0.0.0
Tomcat 8.5.65 Port 8080
Apache 2.4 Port 80/443
commons-dbcp-1.4.jar
axis-1.4.jar
log4j-1.2.15.jar
```

2. Pegar en el formulario
3. Hacer clic: **"Iniciar Análisis Forense"**

### Paso 4: Ver resultados

El dashboard mostrará:
- ✅ Componentes detectados (5)
- ✅ Technical Debt Score (82/100)
- ✅ Anti-patterns (4 detectados)
- ✅ Data flows con latencias
- ✅ SOLID Analysis (2.6/10)

---

## 🔍 OPCIÓN 3: Con Datos Reales (Más Realista)

### Paso 1: Recolectar datos

**Opción A: Desde máquina local (WSL - Windows Subsystem for Linux)**
```bash
# Abre WSL
wsl

# Ejecuta collector.sh
chmod +x collector.sh
./collector.sh

# Guarda output
cat inventory_*.txt | clip  # Copia al portapapeles
```

**Opción B: Desde servidor remoto (SSH)**
```bash
# Desde tu máquina Windows
ssh user@legacy-server "bash -s" < collector.sh > local_data.txt

# Luego: cat local_data.txt | clip
```

**Opción C: Usar datos de muestra**
```bash
# Ya tenemos datos en test-end-to-end.cjs
# Simplemente ejecuta el test
node test-end-to-end.cjs
```

### Paso 2: Procesar datos en dashboard

1. Copiar output del collector.sh
2. En http://localhost:8000 → Tab "Análisis de Código"
3. Pegar en el formulario
4. Hacer clic: **"Iniciar Análisis"**

### Paso 3: Esperar resultados

**Sin IA (150ms):**
- Stage 1: Discovery
- Stage 2: Advanced Analysis
→ Resultados locales

**Con IA (2-5s, opcional):**
- Stage 3: AWS Bedrock enriquecimiento
→ Roadmap de migración + presupuesto

### Paso 4: Exportar resultados

```bash
# En dashboard, botón: "Exportar"

📥 JSON (para importar a Excel/tools)
📥 PDF (para presentar a ejecutivos)
📥 JIRA (para crear tickets automáticamente)
```

---

## 📊 FLUJO VISUAL COMPLETO

```
┌─────────────────────────────────────────────┐
│ Esquema 1: EJECUTAR TEST AUTOMÁTICO        │
└─────────────────────────────────────────────┘

node test-orchestrator.js
    ↓
Stage 1: Discovery (50ms)
  ✓ Detecta 5 componentes
  ✓ Identifica flags
    ↓
Stage 2: Advanced (100ms)
  ✓ Deuda Técnica: 82/100
  ✓ Anti-patterns: 4
  ✓ SOLID: 2.6/10
    ↓
Stage 3: IA (Simulado)
  ✓ Executive Summary
  ✓ Roadmap 12 meses
    ↓
✅ Reporte total


┌─────────────────────────────────────────────┐
│ Esquema 2: VÍA DASHBOARD                   │
└─────────────────────────────────────────────┘

1. Inicia backend
   python backend.py → http://localhost:8000
    ↓
2. Abre http://localhost:8000 en navegador
    ↓
3. Tab "Análisis de Código" → Pega datos
    ↓
4. Clic: "Iniciar Análisis"
    ↓ (150ms sin IA, 2-5s con IA)
    ↓
5. Ve resultados en dashboard
    ↓
6. Exporta: JSON / PDF / JIRA


┌─────────────────────────────────────────────┐
│ Esquema 3: CON DATOS REALES (collector.sh) │
└─────────────────────────────────────────────┘

1. ./collector.sh (en Linux/WSL/remoto)
    ↓
2. Copiar output (3-10 MB típico)
    ↓
3. Pegar en dashboard
    ↓
4. Análisis procesa datos REALES
    ↓
5. Resultados profesionales
    ↓
6. Exporta para ejecutivos
```

---

## ✅ Checklist de Validación

### Test 1: ¿Funciona Stage 1 (Discovery)?
- [ ] Detecta `java`
- [ ] Detecta `oracle`
- [ ] Detecta `apache`
- [ ] Detecta `websphere`
- [ ] Detecta `tomcat`

### Test 2: ¿Funciona Stage 2 (Advanced)?
- [ ] Calcula Deuda Técnica (0-100)
- [ ] Detecta anti-patterns (4+)
- [ ] Calcula SOLID scores
- [ ] Analiza data flows
- [ ] Genera recomendaciones

### Test 3: ¿Funciona Dashboard?
- [ ] Backend corriendo (`http://localhost:8000`)
- [ ] Formulario acepta input
- [ ] Botón "Analizar" funciona
- [ ] Resultados se muestran
- [ ] Puede exportar JSON

### Test 4: ¿Funciona con Datos Reales?
- [ ] collector.sh genera output (>1MB)
- [ ] Dashboard procesa sin errores
- [ ] Resultados coinciden con data
- [ ] Recomendaciones son realistas

---

## 🐛 Troubleshooting

### Problema: Backend no inicia
```bash
# Error: python: not found

Solución:
C:/Users/hberrioe/AppData/Local/Programs/Python/Python313/python.exe backend.py
```

### Problema: http://localhost:8000 no responde
```bash
# Error: Connection refused

Solución:
1. Verifica que backend está corriendo: netstat -ano | findstr :8000
2. Si no hay proceso, inicia manualmente
3. Si hay proceso, mata y reinicia: taskkill /PID xxxx /F
```

### Problema: Test falla con "require is not defined"
```bash
# Error: ES module scope

Solución:
node test-end-to-end.cjs      # Usa .cjs (no .js)
```

### Problema: Dashboard vacío
```bash
# No hay datos

Solución:
1. Abre DevTools (F12)
2. Console → Busca errores
3. Asegúrate de que backend responde: http://localhost:8000/health
4. Completa formulario CON DATOS antes de hacer clic
```

---

## 📈 Métricas de Éxito

Cuando todo funcione correctamente, verás:

```
✅ Stage 1 (Discovery):
   - 5-10 componentes detectados
   - Flags correctos (legacy=true, monolithic=true, etc)
   - 50ms execution time

✅ Stage 2 (Advanced):
   - Technical Debt: 60-100 (si es legacy)
   - Anti-patterns: 4-7 los comunes
   - SOLID avg: 2-4 (si es legacy)
   - Recomendaciones específicas

✅ Stage 3 (IA - si habilitada):
   - Roadmap con 4 fases
   - Presupuesto $1.2M - $1.8M
   - ROI 14-18 meses
   - Métricas proyectadas

✅ Dashboard:
   - Todas las secciones visibles
   - Gráficos renderizados
   - Exports funcionando
   - Sin errores en console
```

---

## 🎯 Próximos Pasos

Después de probar exitosamente:

1. **Integra el Orchestrator en app.js:**
   ```javascript
   const orchestrator = new UnifiedAnalysisOrchestrator(rawData);
   const report = await orchestrator.executeFullAnalysis();
   ```

2. **Habilita AWS Bedrock (opcional):**
   ```bash
   export AWS_BEDROCK_ENABLED=true
   export AWS_REGION=us-east-1
   cd server && python main.py
   ```

3. **Procesa datos reales en producción:**
   - Ejecuta collector.sh en servidores legacy
   - Procesa con el software
   - Exporta reportes para stakeholders
   - Ejecuta roadmap de migración

---

## 📞 Soporte Rápido

| Problema | Solución |
|----------|----------|
| Backend no inicia | Usa ruta completa de Python |
| Localhost:8000 no responde | Verifica puerto con netstat |
| Dashboard vacío | Pane datos en formulario |
| Test falla | Usa `test-end-to-end.cjs` (no .js) |
| AWS Bedrock falla | Normal - requiere credentials |
| No ve resultados | F5 para refrescar página |

---

## 🎉 ¡Listo!

**Resumen de pruebas:**

- ✅ Test automático: `node test-end-to-end.cjs` (30s)
- ✅ Via dashboard: `http://localhost:8000` (5m)
- ✅ Con datos reales: `./collector.sh` (10m)
- ✅ Exportar reportes: Botones en dashboard

**Todo debe funcionar sin errores.** Si algo falla, revisa troubleshooting arriba.

¡Que disfrutes probando el software profesional! 🚀
