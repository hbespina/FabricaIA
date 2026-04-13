# Design Spec: FinOps Pro + Reorganización de Pilares

**Fecha:** 2026-04-13  
**Estado:** Aprobado  
**Alcance:** Modernization Factory v5.0

---

## 1. Contexto y Motivación

La aplicación actualmente mezcla código, IaC y costos en las páginas p1–p3, dificultando la navegación para distintos tipos de usuario (dev vs DevOps vs CFO). Con la incorporación del nuevo pilar FinOps, se aprovecha el momento para reorganizar toda la UI en 6 pilares con audiencia y propósito definidos.

---

## 2. Objetivos

1. Reorganizar el contenido existente en 6 pilares navegables sin perder funcionalidad.
2. Agregar un nuevo agente IA (`CostOptimizationAgent`) que produzca análisis de costos multi-cloud, optimización AWS (RI/Savings Plans/Spot), right-sizing y optimización del costo de migración.
3. Exponer los datos de costos en un nuevo endpoint `/finops/{scan_id}` que consulte APIs públicas de precios (AWS, Azure, GCP) con caché SQLite de 24h.
4. Renderizar el pilar FinOps en una nueva página p6 con 4 sub-secciones.

---

## 3. Estructura de Pilares

| # | Pilar | Audiencia | Contenido |
|---|-------|-----------|-----------|
| 0 | **Resumen** | Todos | Resumen ejecutivo, top-3 CVEs, estrategia — sin cambios |
| 1 | **Arquitectura** | Arquitectos | Diagrama AS-IS (Mermaid), score acoplamiento, TO-BE, risk matrix |
| 2 | **Código** | Desarrolladores | Transformaciones ANTES/DESPUÉS clase por clase, javax→jakarta, SQL→JPA, anti-patrones |
| 3 | **IaC** | DevOps / Platform | Dockerfile multi-stage, docker-compose, K8s manifests (Deployment+Service+HPA), Terraform (RDS Aurora + ECS Fargate), comandos de despliegue |
| 4 | **SRE** | SREs | Healthchecks (liveness/readiness/startup), violaciones 12-Factor App, runbook operativo |
| 5 | **FinOps** | CFO / CTO / Finance | TCO legacy vs AWS, comparativa multi-cloud, RI/Savings Plans/Spot, right-sizing, optimización costo de migración |

La reorganización de los pilares 0–4 es principalmente reordenamiento de renders del frontend. No requiere cambios en el backend ni en los agentes existentes.

---

## 4. Nuevo Agente: `CostOptimizationAgent`

### 4.1 Integración en el Pipeline

Se agrega como 7° agente al `ThreadPoolExecutor` del endpoint de análisis de artefactos Java (6° para SSH/Manual).

```
SecurityAgent    ─┐
CodeAgent        ─┤
JavaAgent        ─┤──► MigrationAgent ──► resultado fusionado → SSE → UI
CloudNativeAgent ─┤         ↑ (sprint1_mandatory de SecurityAgent)
BusinessAgent    ─┤
CostOptimizationAgent  (consume output de BusinessAgent como contexto)
```

El agente **no bloquea** a MigrationAgent — corre en paralelo y su resultado se fusiona en el payload final junto a los demás agentes.

### 4.2 Inputs

- Inventario estructurado completo (bytecode, dependencias, infra detectada)
- JSON resultado del `BusinessAgent` (TCO legacy base ya calculado)
- Budget de tokens: **3072**

### 4.3 Output JSON

```json
{
  "multicloud": {
    "aws":   { "monthly_usd": 420, "breakdown": [...], "pros": ["..."] },
    "azure": { "monthly_usd": 390, "breakdown": [...], "pros": ["..."] },
    "gcp":   { "monthly_usd": 355, "breakdown": [...], "pros": ["..."] },
    "recommendation": "gcp",
    "recommendation_rationale": "Justificación técnica basada en el stack detectado"
  },
  "aws_optimization": {
    "savings_plans_coverage": 0.72,
    "estimated_savings_pct": 34,
    "recommendations": [
      {
        "service": "ECS Fargate",
        "current": "on-demand",
        "recommended": "Compute Savings Plan 1yr no-upfront",
        "savings_usd": 87,
        "rationale": "Carga de trabajo estable detectada — sin variación de concurrencia en bytecode"
      }
    ]
  },
  "rightsizing": {
    "signals_used": ["2 EJBs stateless detectados", "no session state", "3 SQL queries simples"],
    "recommendations": [
      {
        "service": "ECS Task",
        "current_default": "2 vCPU / 4 GB",
        "recommended": "0.5 vCPU / 1 GB",
        "reason": "App stateless simple sin procesamiento pesado en bytecode"
      }
    ]
  },
  "sprint_cost": {
    "total_one_time_usd": 85000,
    "optimized_usd": 61000,
    "savings_usd": 24000,
    "optimizations": [
      {
        "action": "Paralelizar Sprint 2 (refactor) y Sprint 3 (IaC)",
        "saving_usd": 12000,
        "reason": "No hay dependencias de datos entre ambas pistas"
      },
      {
        "action": "Automatizar Sprint 0 con IaC generado por la Factory",
        "saving_usd": 8000,
        "reason": "Terraform y K8s ya generados — elimina trabajo manual de setup"
      }
    ]
  }
}
```

### 4.4 Prompt del Agente

El agente recibe el inventario + JSON del BusinessAgent y se le instruye a:
- Basar las comparativas multi-cloud en el stack **real** detectado (no genérico)
- Justificar right-sizing con **señales concretas del bytecode** (EJBs, session state, SQL patterns)
- Identificar qué sprints son paralelizables basándose en el plan de MigrationAgent
- No inventar CVEs ni versiones que no estén en el inventario

---

## 5. Nuevo Endpoint: `GET /finops/{scan_id}`

### 5.1 Responsabilidad

Complementa el análisis IA con precios reales. Se llama desde el frontend al abrir el pilar FinOps (no bloquea el análisis inicial).

### 5.2 Flujo

```
Frontend abre pilar FinOps
  └─ GET /finops/{scan_id}?region=us-east-1
       ├─ Lee CostOptimizationAgent output del análisis almacenado
       ├─ Verifica caché SQLite (tabla pricing_cache, TTL 24h)
       ├─ Si caché miss:
       │    ├─ AWS   → boto3 pricing (ya existe en /pricing/{scan_id})
       │    ├─ Azure → GET prices.azure.com/api/retail/prices (sin auth)
       │    └─ GCP   → GET cloudbilling.googleapis.com/v1/services (API Key pública)
       ├─ Normaliza precios a $/hora por servicio equivalente
       └─ Retorna: { ai_analysis, price_comparison, cache_hit, fetched_at }
```

### 5.3 Tabla de caché `pricing_cache`

```sql
CREATE TABLE IF NOT EXISTS pricing_cache (
    cloud        TEXT NOT NULL,
    service      TEXT NOT NULL,
    region       TEXT NOT NULL,
    price_usd_hr REAL NOT NULL,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (cloud, service, region)
);
```

TTL: si `fetched_at` tiene más de 24h, se refresca. Esto evita latencia repetida en cada apertura del pilar.

### 5.4 Normalización de servicios equivalentes

| Servicio lógico | AWS | Azure | GCP |
|----------------|-----|-------|-----|
| Contenedor (2vCPU/4GB) | ECS Fargate | Azure Container Apps | Cloud Run |
| Base de datos managed | RDS Aurora | Azure Database | Cloud SQL |
| Cache | ElastiCache Redis | Azure Cache for Redis | Memorystore |
| Load Balancer | ALB | Azure Load Balancer | Cloud Load Balancing |

---

## 6. UI — Pilar FinOps (p6)

### 6.1 Estructura de la página

```
┌─────────────────────────────────────────────────┐
│  FinOps Pro                                      │
│  [ Multi-Cloud ] [ AWS Optimizer ] [ Right-Sizing ] [ Sprint Cost ] │
├─────────────────────────────────────────────────┤
│  <contenido del tab activo>                      │
└─────────────────────────────────────────────────┘
```

### 6.2 Tab: Multi-Cloud

- Tabla comparativa AWS / Azure / GCP con costo mensual total
- Breakdown por servicio (contenedor, DB, cache, LB)
- Badge destacado con el cloud recomendado por la IA
- Rationale de la recomendación en texto expandible

### 6.3 Tab: AWS Optimizer

- Porcentaje de cobertura con Savings Plans recomendado
- Lista de recomendaciones por servicio: tipo actual → tipo recomendado + ahorro mensual estimado
- Identificación de workloads aptos para Spot (si aplica)

### 6.4 Tab: Right-Sizing

- Señales del inventario usadas por la IA para el análisis
- Tabla: servicio → tamaño default Factory → tamaño recomendado → ahorro estimado
- Explicación de la razón por servicio

### 6.5 Tab: Sprint Cost

- Costo one-time original vs optimizado (comparativa visual)
- Lista de optimizaciones con acción concreta, ahorro y justificación
- Total de ahorro potencial destacado

---

## 7. Reorganización del Frontend (p0–p4)

La reorganización es un refactor del frontend (`app.js`, `index.html`) que **mueve** renders existentes al pilar correcto. No modifica lógica de agentes ni endpoints.

| Contenido actual | Pilar actual | Pilar nuevo |
|-----------------|-------------|------------|
| Diagrama AS-IS Mermaid | p1 | Arquitectura (p1) — sin mover |
| Risk matrix | p1 | Arquitectura (p1) — sin mover |
| Sprints + estrategia | p2 | Arquitectura (p1) — sección "TO-BE strategy" |
| Transformaciones ANTES/DESPUÉS | p2/p3 | Código (p2) |
| javax→jakarta, SQL→JPA | p2/p3 | Código (p2) |
| Dockerfile, K8s, Terraform | p3 | IaC (p3) — sin mover |
| Healthchecks, 12-Factor | p3 | SRE (p4) |
| TCO/ROI BusinessAgent | p3/p5 | FinOps (p5) |
| Panel AWS Pricing | p3 | FinOps (p5) |

---

## 8. Fuera de Alcance (este sprint)

- Integración con credenciales reales de Azure o GCP
- Simulador what-if interactivo (recalcular al cambiar parámetros)
- Zoom detallado en pilares individuales (se hace en sprints separados)
- Cambios en los agentes existentes (SecurityAgent, CodeAgent, etc.)

---

## 9. Criterios de Éxito

1. El pipeline completa el análisis con `CostOptimizationAgent` en ≤ tiempo actual + 500ms (corre en paralelo).
2. `/finops/{scan_id}` retorna comparativa multi-cloud en < 3s (con caché hit < 200ms).
3. Los 6 pilares son navegables y cada uno muestra únicamente el contenido de su dominio.
4. El pilar FinOps muestra los 4 tabs con datos del agente IA + precios reales normalizados.
5. Sin regresiones en análisis existentes (SSH, Manual, Java artifact).
