# 🚀 Cómo Ejecutar el Análisis - Guía Rápida

## **OPCIÓN 1: Demo Rápida (Ahora mismo)**

1. Abre: http://localhost:8000/demo-analysis.html
2. Haz clic en las pestañas para ver:
   - ✅ **Etapa 1**: Stack descubierto (5 componentes)
   - ✅ **Etapa 2**: Análisis avanzado (deuda técnica, anti-patrones, SOLID, flujos)
   - ✅ **Etapa 3**: Roadmap IA (plan 3 fases + presupuesto)
   - ✅ **Resumen**: Métricas ejecutivas

**Tiempo: <1 segundo** (Todas las 3 etapas pre-calculadas)

---

## **OPCIÓN 2: Análisis con Datos de Ejemplo**

### Paso 1: Llenar formulario
1. Ve a: http://localhost:8000
2. Busca tab: **"Pegar Datos"**
3. Copia el contenido de [sample-data.txt](./sample-data.txt)
4. Pega en el formulario

### Paso 2: Ejecutar análisis
Click en botón: **"Iniciar Análisis Forense"**

### Paso 3: Ver resultados
El portal mostrará:
- 📊 **Página 0**: Hallazgos de código
- 🏗️ **Página 1**: Infraestructura + Scores (TCO, ROI)
- 📋 **Página 2**: Plan de migración por sprints
- ⚙️ **Página 3**: IaC Generator (Terraform, K8s, Docker)

**Tiempo: 150ms** (Todas las 3 etapas en local)

---

## **OPCIÓN 3: Datos Reales desde tu Servidor**

### Método A: Copiar/Pegar (Fácil)
```bash
# En tu servidor RHEL/Debian/Ubuntu/AIX:
chmod +x collector.sh
./collector.sh

# Se genera archivo en: ./modernization_reports/inventory_HOSTNAME_TIMESTAMP.txt
# Descargalo y pegalo en el portal (OPCIÓN 2)
```

### Método B: SSH Directo (Automático)
En el portal, tab **"Conectar SSH"**:

```
┌─────────────────────────────────┐
│ Hostname: prod-app-server-01    │
│ Usuario: root                   │
│ Password: ••••••••              │
│ Port: 22                        │
└─────────────────────────────────┘
```

Click: **"Conectar y Recolectar"** → El análisis se ejecuta automáticamente

**Resultado: Análisis completo en 150ms + 3-5s si AWS Bedrock activado**

---

## **Qué Recibes en Cada Análisis**

### ✅ ETAPA 1: Descubrimiento (50ms)
```
✓ 5 componentes detectados:
  • Java Runtime (port 8080) → Modernize to Quarkus
  • Oracle Database (port 1521) → RDS Custom
  • Apache HTTPD (port 80) → NGINX/ALB
  • NiFi Integration → EventBridge
  • PostgreSQL (port 5432) → Aurora
```

### ✅ ETAPA 2: Análisis Avanzado (100ms)
```
Deuda Técnica: 72/100 (ALTO)
├─ 7 Anti-patrones
├─ God Class: 2847 LOC
├─ 156 TODO comments
├─ 23% Test coverage
├─ SOLID Score: 42/100
└─ Flujos con latencias reales
```

### ✅ ETAPA 3: IA + Roadmap (3-5s)
```
Plan 3 Fases - Total: $195k inversión
├─ Fase 1 (Meses 1-2): Estabilización $45k
├─ Fase 2 (Meses 3-4): Containerización $62k
└─ Fase 3 (Meses 5-6): AWS EKS $88k

Ahorro Anual: $195k (57% menos TCO)
Payback: 12 meses
ROI 3 años: $585k
```

---

## **Comandos Rápidos**

### Ejecutar collector.sh en servidor remoto:
```bash
# Opción 1: Directo (requiere acceso SSH)
ssh root@servidor.com "chmod +x ~/collector.sh && ~/collector.sh"

# Opción 2: Con scp (copiar primero)
scp collector.sh root@servidor.com:~/
ssh root@servidor.com "./collector.sh"

# Opción 3: One-liner bash
bash <(curl -s http://localhost:8000/collector.sh) 
```

### Generar datos locales:
```bash
# Simular reporte Linux en Windows Git Bash:
ps -aux | grep -E "java|python|node" > /tmp/sample.txt
netstat -ano | grep LISTEN >> /tmp/sample.txt
```

---

## **Troubleshooting**

| Problema | Solución |
|----------|----------|
| Backend no responde | `netstat -ano \| findstr :8000` → Verificar puerto |
| Análisis tarda mucho | Normal si datos > 50MB (150ms típico) |
| No ve resultados | Verificar datos pegados tengan mínimo 50 caracteres |
| SSH no conecta | Verificar usuario/contraseña/puerto SSH abierto |

---

## **URLs Rápidas**

| URL | Propósito |
|-----|----------|
| http://localhost:8000 | Portal principal (manual o SSH) |
| http://localhost:8000/demo-analysis.html | Demo con datos pre-calculados |
| http://localhost:8000/health | Verificar backend vivo |

---

## ✅ Resumen: 3 Pasos

1. **Demo**: Abre http://localhost:8000/demo-analysis.html (0 segundos)
2. **Datos Ejemplo**: Pega sample-data.txt en http://localhost:8000 (150ms)
3. **Datos Reales**: Ejecuta collector.sh + pega resultado (150ms)

**¡Listo! Ya tienes tus 3 etapas de análisis ejecutándose.** 🎉
