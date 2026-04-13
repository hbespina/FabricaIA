# FinOps Pro + Reorganización de Pilares — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar un `CostOptimizationAgent` con comparativa multi-cloud (AWS/Azure/GCP), optimización RI/Spot y right-sizing, exponer los resultados en un endpoint `/finops/{scan_id}` con caché, y reorganizar el frontend en 6 pilares navegables (Resumen, Arquitectura, Código, IaC, SRE, FinOps).

**Architecture:** Un 7° agente especializado se integra al `ThreadPoolExecutor` de `_run_bedrock_job()` corriendo en Stage 2 (junto a MigrationAgent), consumiendo el output de BusinessAgent como contexto. Un nuevo endpoint `/finops/{scan_id}` llama APIs públicas de precios de Azure y GCP (sin auth), combina con la AWS Pricing API ya existente, y cachea resultados en una nueva tabla SQLite `pricing_cache` con TTL de 24h. En el frontend, dos nuevas páginas (`p-sre` y `p-finops`) reciben el contenido correspondiente movido de `p3`, y el nav se renombra para reflejar los pilares.

**Tech Stack:** FastAPI + boto3 (ya existentes), `requests` (Python stdlib-compatible), SQLite (ya existente), HTML/CSS/JS vanilla (ya existente).

---

## Mapa de Archivos

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `server/main.py` | Modificar | Agregar tabla `pricing_cache`, prompt `_AGENT_COST_OPT_PROMPT`, función `run_cost_optimization()`, wirear al pipeline Stage 2, endpoint `/finops/{scan_id}`, helpers Azure/GCP |
| `index.html` | Modificar | Renombrar nav n0–n3, agregar items n-sre y n-finops, agregar páginas `p-sre` y `p-finops`, mover HTML de healthchecks/12-factor/runbooks/TCO/pricing de p3 a nuevas páginas |
| `app.js` | Modificar | Extender `sw()` para nuevos page IDs, agregar `_renderCostOptimization()`, agregar `loadFinOps()`, redirigir renders de SRE y Business/FinOps a nuevas páginas |

---

## Task 1: Agregar tabla `pricing_cache` a init_db()

**Files:**
- Modify: `server/main.py:358-407`

- [ ] **Step 1: Agregar CREATE TABLE dentro de `init_db()`**

En `server/main.py`, dentro de `init_db()` después de la creación de `analysis_jobs` (línea ~389), agregar:

```python
    c.execute("""
        CREATE TABLE IF NOT EXISTS pricing_cache (
            cloud        TEXT NOT NULL,
            service      TEXT NOT NULL,
            region       TEXT NOT NULL,
            price_usd_hr REAL NOT NULL,
            fetched_at   TEXT NOT NULL,
            PRIMARY KEY (cloud, service, region)
        )
    """)
```

- [ ] **Step 2: Verificar que el backend arranca sin errores**

```bash
cd server && python -c "from main import init_db; init_db(); print('DB OK')"
```

Expected output: `DB OK` (o `DB inicializada (SQLite)` en logs)

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat: agregar tabla pricing_cache a init_db"
```

---

## Task 2: Agregar prompt `_AGENT_COST_OPT_PROMPT`

**Files:**
- Modify: `server/main.py` — agregar constante después de `_AGENT_BUSINESS_PROMPT` (~línea 1057)

- [ ] **Step 1: Agregar la constante del prompt**

Después de la línea que cierra `_AGENT_BUSINESS_PROMPT` (la línea con `"""`), agregar:

```python
_AGENT_COST_OPT_PROMPT = """
Eres un Cloud FinOps Architect Senior especializado en optimización de costos multi-cloud.
Recibirás el inventario técnico del sistema Y el análisis TCO/ROI del BusinessAgent como contexto.

INSTRUCCIÓN CRÍTICA: Personaliza TODOS los valores usando el stack real detectado en el inventario.
- Usa los servicios equivalentes reales según el stack: si hay DB detectada → incluir DB managed.
- Right-sizing: basa las recomendaciones en señales concretas del bytecode (EJBs, session state, SQL).
- Sprint cost: analiza el plan de migración real para identificar paralelizaciones.

Retorna ÚNICAMENTE JSON válido:
{{
  "multicloud": {{
    "aws": {{
      "monthly_usd": 420,
      "breakdown": [
        {{"service": "ECS Fargate", "cost_usd": 180, "detail": "2 tasks × 0.5vCPU/1GB"}},
        {{"service": "RDS Aurora Serverless", "cost_usd": 95, "detail": "0.5-4 ACU"}},
        {{"service": "ALB", "cost_usd": 22, "detail": "1 ALB"}},
        {{"service": "NAT Gateway", "cost_usd": 35, "detail": "1 AZ"}}
      ],
      "pros": ["Mayor madurez de servicios managed para Java EE", "Bedrock IA nativo disponible", "ECS Fargate elimina gestión de nodos"]
    }},
    "azure": {{
      "monthly_usd": 390,
      "breakdown": [
        {{"service": "Azure Container Apps", "cost_usd": 155, "detail": "0.5 vCPU / 1 GB"}},
        {{"service": "Azure Database", "cost_usd": 80, "detail": "Flexible Server B1ms"}},
        {{"service": "Azure Load Balancer", "cost_usd": 18, "detail": "Standard"}},
        {{"service": "NAT Gateway", "cost_usd": 30, "detail": "1 zona"}}
      ],
      "pros": ["Integración nativa con Active Directory", "Azure DevOps pipelines CI/CD", "Precios competitivos para compute"]
    }},
    "gcp": {{
      "monthly_usd": 355,
      "breakdown": [
        {{"service": "Cloud Run", "cost_usd": 140, "detail": "0.5 vCPU / 512 MB pay-per-use"}},
        {{"service": "Cloud SQL", "cost_usd": 75, "detail": "db-f1-micro HA"}},
        {{"service": "Cloud Load Balancing", "cost_usd": 18, "detail": "HTTP(S) LB"}},
        {{"service": "Cloud NAT", "cost_usd": 25, "detail": "1 región"}}
      ],
      "pros": ["Cloud Run escala a cero — ideal si tráfico es bajo", "BigQuery para analytics posterior", "Precios más bajos en compute y egress Asia-Pacific"]
    }},
    "recommendation": "aws",
    "recommendation_rationale": "Justificación técnica basada en stack REAL detectado: qué servicios del inventario determinan la elección, qué ventajas específicas de cada cloud aplican a este workload concreto"
  }},
  "aws_optimization": {{
    "savings_plans_coverage": 0.72,
    "estimated_savings_pct": 34,
    "recommendations": [
      {{
        "service": "ECS Fargate",
        "current": "on-demand",
        "recommended": "Compute Savings Plan 1yr no-upfront",
        "savings_usd_monthly": 62,
        "rationale": "Carga de trabajo predecible — señal: no hay variación de concurrencia en bytecode"
      }},
      {{
        "service": "RDS Aurora",
        "current": "on-demand",
        "recommended": "Reserved Instance 1yr no-upfront",
        "savings_usd_monthly": 35,
        "rationale": "Incluir solo si hay BD detectada en inventario"
      }}
    ],
    "spot_candidates": []
  }},
  "rightsizing": {{
    "signals_used": ["señales reales del bytecode: cantidad de EJBs, session state, SQL queries, tamaño del artefacto"],
    "recommendations": [
      {{
        "service": "ECS Task",
        "current_default": "2 vCPU / 4 GB",
        "recommended": "0.5 vCPU / 1 GB",
        "monthly_savings_usd": 95,
        "reason": "Justificación basada en señales concretas del inventario"
      }}
    ]
  }},
  "sprint_cost": {{
    "total_one_time_usd": 85000,
    "optimized_usd": 65000,
    "savings_usd": 20000,
    "optimizations": [
      {{
        "action": "Paralelizar Sprint 2 (refactor código) y Sprint 3 (IaC setup)",
        "saving_usd": 12000,
        "reason": "No hay dependencias de datos entre ambas pistas — IaC puede prepararse mientras el equipo refactoriza"
      }},
      {{
        "action": "Reusar artefactos IaC generados por la Factory para Sprint 0",
        "saving_usd": 8000,
        "reason": "Dockerfile, K8s y Terraform ya generados — elimina trabajo manual de setup DevOps"
      }}
    ]
  }}
}}

REGLAS CRÍTICAS:
- recommendation en multicloud debe ser el cloud con menor costo + mejor fit para el stack detectado.
- Si NO hay BD detectada: excluir línea de DB de todos los breakdowns.
- rightsizing.signals_used debe listar señales REALES del inventario recibido, no genéricas.
- spot_candidates: listar servicios aptos para Spot solo si el workload es stateless y batch; si no aplica, dejar lista vacía.
- sprint_cost: analiza el plan real de MigrationAgent (si está disponible en el contexto) para identificar qué sprints son paralelizables.
- Todos los valores USD deben ser coherentes con el TCO del BusinessAgent que se provee como contexto.
"""
```

- [ ] **Step 2: Verificar que el archivo parsea sin errores de sintaxis**

```bash
cd server && python -c "import main; print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat: agregar prompt CostOptimizationAgent"
```

---

## Task 3: Agregar función `run_cost_optimization()` al pipeline

**Files:**
- Modify: `server/main.py:1174-1215` (dentro de `_run_bedrock_job`)

- [ ] **Step 1: Agregar variable `cost_opt_result` junto a las demás (~línea 1111)**

Después de `biz_result  = {}   # Business/FinOps agent`, agregar:

```python
    cost_opt_result = {}   # CostOptimization agent
```

- [ ] **Step 2: Agregar función `run_cost_optimization()` junto a las demás (~línea 1174)**

Después de `def run_business():`, agregar:

```python
        def run_cost_optimization():
            # Necesita biz_result — se llama en Stage 2 cuando biz_result ya está disponible
            ctx = inv_msg
            if biz_result:
                ctx += f"\n\n[BUSINESS_AGENT_TCO — usar como contexto base para los cálculos]\n{json.dumps(biz_result, ensure_ascii=False)[:3000]}"
            return _call_agent(bedrock, mid, 3072,
                               _common_ctx + _AGENT_COST_OPT_PROMPT, ctx)
```

- [ ] **Step 3: Wirear `run_cost_optimization()` en Stage 2, junto a MigrationAgent (~línea 1209)**

Reemplazar el bloque "Etapa 1b: Migration" actual:

```python
        # Etapa 1b: Migration (usa sec_result si está disponible)
        _update_job_status(job_id, "running", "Agente Migration planificando sprints...")
        try:
            mig_result = run_migration()
        except Exception as e:
            logger.warning("[Job %s] MigrationAgent falló: %s", job_id[:8], e)
```

Por este bloque que corre Migration y CostOptimization en paralelo:

```python
        # Etapa 1b: Migration + CostOptimization en paralelo (ambos usan Stage 1 ya completo)
        n_stage2 = 2
        _update_job_status(job_id, "running", f"Stage 2 — Migration + CostOptimization ({n_stage2} agentes)...")
        with ThreadPoolExecutor(max_workers=2) as ex2:
            f_mig  = ex2.submit(run_migration)
            f_cost = ex2.submit(run_cost_optimization)
            for fut in as_completed({f_mig: "migration", f_cost: "cost_opt"}):
                lbl = {f_mig: "migration", f_cost: "cost_opt"}[fut]
                try:
                    res = fut.result()
                    if lbl == "migration":
                        mig_result.update(res)
                    else:
                        cost_opt_result.update(res)
                except Exception as e:
                    logger.warning("[Job %s] Agente '%s' falló: %s", job_id[:8], lbl, e)
```

- [ ] **Step 4: Agregar `cost_optimization` a la fusión de resultados (~línea 1282)**

En el bloque `ai_response = { ... }`, después de `"business": { ... },`, agregar:

```python
            # CostOptimization agent
            "cost_optimization": {
                "multicloud":       cost_opt_result.get("multicloud", {}),
                "aws_optimization": cost_opt_result.get("aws_optimization", {}),
                "rightsizing":      cost_opt_result.get("rightsizing", {}),
                "sprint_cost":      cost_opt_result.get("sprint_cost", {}),
            },
```

- [ ] **Step 5: Verificar sintaxis**

```bash
cd server && python -c "import main; print('Pipeline OK')"
```

Expected: `Pipeline OK`

- [ ] **Step 6: Commit**

```bash
git add server/main.py
git commit -m "feat: CostOptimizationAgent wired into Stage 2 pipeline"
```

---

## Task 4: Helpers para precios Azure/GCP + endpoint `/finops/{scan_id}`

**Files:**
- Modify: `server/main.py` — agregar después del endpoint `/pricing/{scan_id}` (~línea 2664)

- [ ] **Step 1: Agregar helpers de precios Azure y GCP**

Después del cierre del endpoint `get_aws_pricing` (después de `return { ... }`), agregar:

```python
# ─── FinOps — Fetchers de precios públicos ────────────────────────────────────

def _fetch_azure_prices(region: str = "eastus") -> dict:
    """
    Llama Azure Retail Prices API (sin auth).
    Retorna dict de service→precio por hora en USD.
    """
    import requests as req
    baseline = {
        "container": 0.0160,   # Container Apps 0.5 vCPU/1GB baseline
        "database":  0.0340,   # Azure Database Flexible Server B1ms
        "cache":     0.0340,   # Azure Cache for Redis C1
        "lb":        0.0250,   # Standard Load Balancer
    }
    try:
        # Contenedor: Azure Container Apps vCPU
        url = (
            "https://prices.azure.com/api/retail/prices"
            "?$filter=priceType eq 'Consumption' and armRegionName eq '"
            + region + "' and contains(skuName,'D2s') and serviceName eq 'Container Instances'"
        )
        r = req.get(url, timeout=8)
        if r.ok:
            items = r.json().get("Items", [])
            for item in items:
                if "Linux" in item.get("skuName", "") and item.get("unitPrice", 0) > 0:
                    # Container Instances D2s = 2 vCPU / 8GB — escalar a 0.5 vCPU
                    baseline["container"] = round(item["unitPrice"] / 4, 6)
                    break
    except Exception as e:
        logger.warning("Azure Pricing API error: %s", e)
    return baseline


def _fetch_gcp_prices(region: str = "us-east1") -> dict:
    """
    Retorna precios GCP baseline (2025). Si GCP_API_KEY está configurado,
    intenta obtener precios reales de Cloud Billing Catalog API.
    """
    import requests as req
    baseline = {
        "container": 0.0000240,  # Cloud Run vCPU-second × 3600 = $/hr
        "database":  0.0250,     # Cloud SQL f1-micro
        "cache":     0.0490,     # Memorystore Redis M1 basic
        "lb":        0.0080,     # Cloud Load Balancing rule/hr
    }
    api_key = os.getenv("GCP_API_KEY", "")
    if not api_key:
        return baseline
    try:
        # Cloud Run CPU pricing
        svc_id = "9662-B51E-5089"  # Cloud Run service ID
        url = f"https://cloudbilling.googleapis.com/v1/services/{svc_id}/skus?key={api_key}"
        r = req.get(url, timeout=8)
        if r.ok:
            for sku in r.json().get("skus", []):
                if "CPU" in sku.get("description", "") and region in str(sku.get("serviceRegions", [])):
                    tiers = sku.get("pricingInfo", [{}])[0].get("pricingExpression", {}).get("tieredRates", [])
                    if tiers:
                        nano = tiers[-1].get("unitPrice", {}).get("nanos", 0)
                        baseline["container"] = round(float(nano) / 1e9 * 3600, 6)
                    break
    except Exception as e:
        logger.warning("GCP Pricing API error: %s", e)
    return baseline


def _get_cached_prices(cloud: str, region: str) -> dict | None:
    """Retorna precios cacheados si existen y son < 24h. None si expired o inexistentes."""
    try:
        conn, _ = _get_conn()
        rows = conn.execute(
            "SELECT service, price_usd_hr, fetched_at FROM pricing_cache WHERE cloud=? AND region=?",
            (cloud, region)
        ).fetchall()
        conn.close()
        if not rows:
            return None
        now = datetime.utcnow()
        prices = {}
        for row in rows:
            fetched = datetime.fromisoformat(row[2])
            if (now - fetched).total_seconds() > 86400:  # 24h TTL
                return None  # Cualquier entrada expirada invalida el cache
            prices[row[0]] = row[1]
        return prices if prices else None
    except Exception:
        return None


def _save_prices_to_cache(cloud: str, region: str, prices: dict):
    """Guarda precios en pricing_cache. Upsert por (cloud, service, region)."""
    try:
        conn, _ = _get_conn()
        now = datetime.utcnow().isoformat()
        for service, price in prices.items():
            conn.execute(
                """INSERT OR REPLACE INTO pricing_cache (cloud, service, region, price_usd_hr, fetched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (cloud, service, region, price, now)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Error guardando pricing_cache: %s", e)


@app.get("/finops/{scan_id}")
async def get_finops(scan_id: str, region: str = "us-east-1", _user: str = Depends(verify_auth)):
    """
    Retorna análisis FinOps completo:
    - ai_analysis: output de CostOptimizationAgent (guardado en bedrock_blueprint)
    - price_comparison: precios reales AWS/Azure/GCP normalizados
    - cache_hit: si los precios vinieron del caché
    """
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(
        f"SELECT hostname, bedrock_blueprint FROM scan_history WHERE id = {ph}",
        (scan_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Scan no encontrado")

    rd = dict(row)
    try:
        bp = json.loads(rd.get("bedrock_blueprint") or "{}")
    except Exception:
        bp = {}

    ai_analysis = bp.get("cost_optimization", {})

    # Azure region mapping (AWS us-east-1 → Azure eastus)
    az_region_map = {
        "us-east-1": "eastus", "us-west-2": "westus2",
        "eu-west-1": "westeurope", "ap-southeast-1": "southeastasia",
    }
    az_region = az_region_map.get(region, "eastus")
    gcp_region_map = {
        "us-east-1": "us-east1", "us-west-2": "us-west2",
        "eu-west-1": "europe-west1", "ap-southeast-1": "asia-southeast1",
    }
    gcp_region = gcp_region_map.get(region, "us-east1")

    # ── Precios AWS (reutiliza lógica existente)
    HOURS_MONTH = 730
    p = _PRICING_BASELINE
    aws_prices = {
        "container": p["fargate_vcpu_hour"] * 0.5 + p["fargate_gb_hour"] * 1.0,  # 0.5vCPU/1GB
        "database":  p.get("rds_mysql_hour", 0.034),
        "cache":     p.get("elasticache_hour", 0.034),
        "lb":        p.get("alb_hour", 0.008),
    }

    # ── Azure precios (cache o API)
    cache_hit_az = False
    az_prices = _get_cached_prices("azure", az_region)
    if az_prices:
        cache_hit_az = True
    else:
        az_prices = _fetch_azure_prices(az_region)
        _save_prices_to_cache("azure", az_region, az_prices)

    # ── GCP precios (cache o API/baseline)
    cache_hit_gcp = False
    gcp_prices = _get_cached_prices("gcp", gcp_region)
    if gcp_prices:
        cache_hit_gcp = True
    else:
        gcp_prices = _fetch_gcp_prices(gcp_region)
        _save_prices_to_cache("gcp", gcp_region, gcp_prices)

    # ── Calcular totales mensuales normalizados (0.5vCPU/1GB + DB si aplica)
    def _monthly(prices: dict, has_db: bool, has_cache: bool, has_lb: bool) -> dict:
        container = round(prices["container"] * HOURS_MONTH, 2)
        db        = round(prices["database"]  * HOURS_MONTH, 2) if has_db    else 0
        cache     = round(prices["cache"]     * HOURS_MONTH, 2) if has_cache else 0
        lb        = round(prices["lb"]        * HOURS_MONTH, 2) if has_lb    else 0
        return {
            "container": container, "database": db,
            "cache": cache, "lb": lb,
            "total": round(container + db + cache + lb, 2)
        }

    # Detectar stack del blueprint para saber si hay DB/cache/LB
    has_db    = bool(bp.get("business", {}).get("tco_aws", {}).get("rds_aurora_serverless_monthly", 0))
    has_cache = "cache" in str(bp).lower() or "redis" in str(bp).lower()
    has_lb    = True  # siempre hay ALB

    aws_monthly  = _monthly(aws_prices,  has_db, has_cache, has_lb)
    az_monthly   = _monthly(az_prices,   has_db, has_cache, has_lb)
    gcp_monthly  = _monthly(gcp_prices,  has_db, has_cache, has_lb)

    return {
        "scan_id":      scan_id,
        "hostname":     rd.get("hostname"),
        "region":       region,
        "ai_analysis":  ai_analysis,
        "price_comparison": {
            "aws":   {"monthly_usd": aws_monthly["total"], "breakdown": aws_monthly},
            "azure": {"monthly_usd": az_monthly["total"],  "breakdown": az_monthly},
            "gcp":   {"monthly_usd": gcp_monthly["total"], "breakdown": gcp_monthly},
        },
        "cache_hit":    cache_hit_az and cache_hit_gcp,
        "fetched_at":   datetime.utcnow().isoformat(),
        "note": "Precios normalizados a 0.5 vCPU / 1 GB / mes. Costos reales varían por región y configuración.",
    }
```

- [ ] **Step 2: Verificar que `requests` está disponible**

```bash
cd server && python -c "import requests; print('requests OK')"
```

Si falla: `pip install requests`

- [ ] **Step 3: Verificar sintaxis del módulo completo**

```bash
cd server && python -c "import main; print('Module OK')"
```

Expected: `Module OK`

- [ ] **Step 4: Smoke test del endpoint (con servidor corriendo)**

```bash
# En una terminal: uvicorn main:app --reload --port 8000
# En otra terminal (con un scan_id real del historial):
curl -s "http://localhost:8000/finops/TEST_ID" -H "X-API-KEY: mf-api-key-2026" | python -m json.tool | head -30
```

Expected: JSON con `price_comparison.aws`, `price_comparison.azure`, `price_comparison.gcp`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py
git commit -m "feat: endpoint /finops/{scan_id} con precios multi-cloud y cache"
```

---

## Task 5: Renombrar nav y agregar páginas SRE + FinOps en HTML

**Files:**
- Modify: `index.html:209-215` (nav items)
- Modify: `index.html:482-664` (p3 — mover contenido SRE y FinOps)

- [ ] **Step 1: Renombrar los nav items n0–n3 y agregar n-sre y n-finops**

En `index.html`, reemplazar el bloque del `<ul>` del sidebar (líneas 208–216):

```html
  <ul style="padding:0">
    <li class="navli on" id="n0" onclick="sw(0)">🧬 Analisis de Codigo</li>
    <li class="navli" id="n1" onclick="sw(1)">🖥 Infraestructura</li>
    <li class="navli" id="n2" onclick="sw(2)">🗺 Plan de Migracion</li>
    <li class="navli" id="n3" onclick="sw(3)">📦 IaC Generator</li>
    <li class="navli" id="n4" onclick="sw(4)">⏳ Historial de Escaneos</li>
    <li class="navli" id="n5" onclick="sw(5)">📊 Dashboard Ejecutivo</li>
    <li class="navli" id="n-lab" onclick="sw('lab')">🧪 Laboratorio Local</li>
  </ul>
```

Por:

```html
  <ul style="padding:0">
    <li class="navli on" id="n0" onclick="sw(0)">📋 Resumen</li>
    <li class="navli" id="n1" onclick="sw(1)">🏛 Arquitectura</li>
    <li class="navli" id="n2" onclick="sw(2)">💻 Código</li>
    <li class="navli" id="n3" onclick="sw(3)">📦 IaC</li>
    <li class="navli" id="n-sre" onclick="sw('sre')">🔧 SRE</li>
    <li class="navli" id="n-finops" onclick="sw('finops')">💰 FinOps</li>
    <li class="navli" id="n4" onclick="sw(4)">⏳ Historial</li>
    <li class="navli" id="n5" onclick="sw(5)">📊 Dashboard</li>
    <li class="navli" id="n-lab" onclick="sw('lab')">🧪 Laboratorio</li>
  </ul>
```

- [ ] **Step 2: Agregar página `p-sre` después del cierre de `p-lab` (~línea 740)**

Después del cierre de `</div>` de `p-lab` y antes de `<div class="page" id="p4">`, insertar:

```html
  <!-- ── Pilar SRE ─────────────────────────────────────────────────────────── -->
  <div class="page" id="p-sre" style="display:none">
    <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:1rem;flex-wrap:wrap">
      <h3 style="font-size:1rem;margin:0">🔧 SRE — Site Reliability Engineering</h3>
      <span style="font-size:.65rem;background:rgba(0,176,155,.15);color:var(--green);padding:.2rem .6rem;border-radius:10px;border:1px solid rgba(0,176,155,.3)">Generado por CloudNativeAgent</span>
    </div>

    <!-- Healthchecks -->
    <div class="card" id="sre-health-box" style="display:none">
      <h4 style="font-size:.85rem;margin-bottom:.6rem">❤ Healthchecks Kubernetes</h4>
      <div id="sre-health-content"></div>
    </div>

    <!-- 12-Factor -->
    <div class="card" id="sre-12factor-box" style="display:none;margin-top:1rem">
      <h4 style="font-size:.85rem;color:var(--yellow);margin-bottom:.6rem">12-Factor App — Violaciones Detectadas</h4>
      <div id="sre-12factor-list"></div>
    </div>

    <!-- SRE Runbooks -->
    <div class="card" id="sre-runbook-box" style="display:none;margin-top:1rem">
      <h4 style="font-size:.85rem;margin-bottom:.6rem">📋 Runbooks SRE — Post-Deploy</h4>
      <div id="sre-runbook-list" style="display:flex;flex-direction:column;gap:.6rem"></div>
    </div>

    <!-- Empty state -->
    <div id="sre-empty" style="text-align:center;padding:3rem;color:var(--t2);font-size:.8rem">
      Analiza un artefacto Java para generar el contenido SRE
    </div>
  </div>
```

- [ ] **Step 3: Agregar página `p-finops` después de `p-sre`**

Después del cierre de `</div>` de `p-sre`, insertar:

```html
  <!-- ── Pilar FinOps ───────────────────────────────────────────────────────── -->
  <div class="page" id="p-finops" style="display:none">
    <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:1rem;flex-wrap:wrap">
      <h3 style="font-size:1rem;margin:0">💰 FinOps Pro</h3>
      <span style="font-size:.65rem;background:rgba(249,212,35,.12);color:var(--yellow);padding:.2rem .6rem;border-radius:10px;border:1px solid rgba(249,212,35,.3)">CostOptimizationAgent + Precios Reales</span>
      <button class="bsm" id="finops-load-btn" onclick="loadFinOps()" style="background:rgba(0,163,255,.15);border-color:var(--blue);color:var(--blue)" title="Obtener precios actuales multi-cloud">🔄 Actualizar Precios</button>
      <span id="finops-cache-badge" style="font-size:.62rem;display:none"></span>
    </div>

    <!-- TCO / ROI del BusinessAgent — movido desde p3 -->
    <div id="finops-business-box" style="display:none;margin-bottom:1.2rem">
      <h4 style="font-size:.9rem;margin-bottom:.7rem;color:var(--blue)">💼 Análisis Financiero — TCO Legacy vs AWS</h4>
      <div id="finops-csuite" style="font-size:.8rem;color:#e0e0e0;background:rgba(0,163,255,.05);border:1px solid rgba(0,163,255,.2);border-radius:8px;padding:.7rem 1rem;margin-bottom:.8rem;line-height:1.7"></div>
      <div class="g2" style="margin-bottom:.7rem">
        <div class="card" style="padding:.8rem">
          <div style="font-size:.65rem;color:var(--t2);font-weight:700;margin-bottom:.5rem">COSTO LEGACY (anual)</div>
          <div id="finops-tco-legacy"></div>
        </div>
        <div class="card" style="padding:.8rem">
          <div style="font-size:.65rem;color:var(--green);font-weight:700;margin-bottom:.5rem">COSTO AWS (anual)</div>
          <div id="finops-tco-aws"></div>
        </div>
      </div>
      <div class="card" style="padding:.8rem">
        <div style="font-size:.65rem;color:var(--t2);font-weight:700;margin-bottom:.5rem">ROI PROYECTADO</div>
        <div id="finops-roi-content" style="display:flex;gap:2rem;flex-wrap:wrap"></div>
      </div>
    </div>

    <!-- Tabs: Multi-Cloud / AWS Optimizer / Right-Sizing / Sprint Cost -->
    <div id="finops-tabs-box" style="display:none;margin-top:1.2rem">
      <div style="display:flex;gap:.4rem;margin-bottom:1rem;border-bottom:1px solid var(--bdr);padding-bottom:.6rem;flex-wrap:wrap">
        <button class="bsm" id="finops-tab-mc"   onclick="showFinOpsTab('mc')"   style="opacity:1">☁ Multi-Cloud</button>
        <button class="bsm" id="finops-tab-opt"  onclick="showFinOpsTab('opt')"  style="opacity:.5">⚡ AWS Optimizer</button>
        <button class="bsm" id="finops-tab-rs"   onclick="showFinOpsTab('rs')"   style="opacity:.5">📐 Right-Sizing</button>
        <button class="bsm" id="finops-tab-sc"   onclick="showFinOpsTab('sc')"   style="opacity:.5">🗓 Sprint Cost</button>
      </div>

      <!-- Tab Multi-Cloud -->
      <div id="finops-tab-mc-content">
        <div id="finops-mc-recommendation" style="display:none;margin-bottom:1rem;padding:.8rem 1rem;border-radius:10px;background:rgba(0,176,155,.08);border:1px solid rgba(0,176,155,.3)"></div>
        <table style="width:100%;border-collapse:collapse;font-size:.78rem;margin-bottom:1rem">
          <thead>
            <tr style="border-bottom:1px solid var(--bdr)">
              <th style="text-align:left;padding:.4rem;color:var(--t2)">Cloud</th>
              <th style="text-align:right;padding:.4rem;color:var(--t2)">Contenedor</th>
              <th style="text-align:right;padding:.4rem;color:var(--t2)">DB</th>
              <th style="text-align:right;padding:.4rem;color:var(--t2)">Cache</th>
              <th style="text-align:right;padding:.4rem;color:var(--t2)">LB</th>
              <th style="text-align:right;padding:.4rem;color:var(--t2);font-weight:700">Total/mes</th>
            </tr>
          </thead>
          <tbody id="finops-mc-table-body"></tbody>
        </table>
        <div id="finops-mc-pros" style="display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin-top:.5rem"></div>
      </div>

      <!-- Tab AWS Optimizer -->
      <div id="finops-tab-opt-content" style="display:none">
        <div id="finops-opt-summary" style="margin-bottom:.8rem;padding:.6rem .8rem;background:rgba(0,163,255,.06);border-radius:8px;font-size:.78rem"></div>
        <div id="finops-opt-list" style="display:flex;flex-direction:column;gap:.6rem"></div>
      </div>

      <!-- Tab Right-Sizing -->
      <div id="finops-tab-rs-content" style="display:none">
        <div id="finops-rs-signals" style="margin-bottom:.8rem;padding:.6rem .8rem;background:rgba(157,80,187,.06);border-radius:8px;font-size:.75rem"></div>
        <table style="width:100%;border-collapse:collapse;font-size:.78rem">
          <thead>
            <tr style="border-bottom:1px solid var(--bdr)">
              <th style="text-align:left;padding:.4rem;color:var(--t2)">Servicio</th>
              <th style="text-align:center;padding:.4rem;color:var(--t2)">Default Factory</th>
              <th style="text-align:center;padding:.4rem;color:var(--t2)">Recomendado</th>
              <th style="text-align:right;padding:.4rem;color:var(--t2)">Ahorro/mes</th>
              <th style="text-align:left;padding:.4rem;color:var(--t2)">Razón</th>
            </tr>
          </thead>
          <tbody id="finops-rs-table-body"></tbody>
        </table>
      </div>

      <!-- Tab Sprint Cost -->
      <div id="finops-tab-sc-content" style="display:none">
        <div id="finops-sc-summary" style="display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin-bottom:1rem"></div>
        <div id="finops-sc-list" style="display:flex;flex-direction:column;gap:.6rem"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div id="finops-empty" style="text-align:center;padding:3rem;color:var(--t2);font-size:.8rem">
      Analiza un artefacto Java para generar el análisis FinOps
    </div>
  </div>
```

- [ ] **Step 4: Verificar que el HTML parsea correctamente**

Abrir `index.html` en el browser y verificar que la app carga sin errores en consola.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat: agregar páginas SRE y FinOps al HTML, renombrar nav"
```

---

## Task 6: Extender `sw()` y agregar `showFinOpsTab()` en app.js

**Files:**
- Modify: `app.js:956-990` (función `sw`)

- [ ] **Step 1: Reemplazar la función `sw()` para manejar 'sre' y 'finops'**

Reemplazar el bloque completo de `window.sw = function(i) { ... }` (líneas 956–990 aprox.) por:

```javascript
window.sw = function(i) {
  // Ocultar todas las páginas numéricas p0-p5
  for(let j=0; j<6; j++) {
      let pg = document.getElementById('p'+j);
      let t = document.getElementById('n'+j);
      if(pg) pg.style.display='none';
      if(t) t.classList.remove('on');
  }
  // Ocultar páginas especiales
  ['p-lab','p-sre','p-finops'].forEach(id => {
      const el = document.getElementById(id);
      if(el) el.style.display='none';
  });
  ['n-lab','n-sre','n-finops'].forEach(id => {
      const el = document.getElementById(id);
      if(el) el.classList.remove('on');
  });

  const specialMap = { lab: 'p-lab', sre: 'p-sre', finops: 'p-finops' };
  const pageId = specialMap[i] ?? 'p'+i;
  const navId  = specialMap[i] ? 'n-'+i : 'n'+i;

  let p = document.getElementById(pageId);
  let n = document.getElementById(navId);
  if(p) p.style.display='block';
  if(n) n.classList.add('on');

  if(i === 4 && window.fetchHistory) window.fetchHistory();
  if(i === 5 && window.loadDashboard) { window.loadDashboard(); window.loadPortfolio(); }
  if(i === 'finops' && lastScanId) loadFinOps();

  if (i === 0 || i === 1 || i === 2) {
      setTimeout(() => window.triggerMermaid(), 50);
  }
  if (i === 3) {
      _renderIaC(lastDetectedTechs, lastHost);
      setTimeout(() => {
          const el = document.getElementById('cn-tobe-diagram');
          if (el && el.textContent.trim()) window.triggerMermaid();
      }, 100);
  }
};
```

- [ ] **Step 2: Agregar `showFinOpsTab()` después de `sw()`**

```javascript
window.showFinOpsTab = function(tab) {
    ['mc','opt','rs','sc'].forEach(t => {
        const content = document.getElementById('finops-tab-' + t + '-content');
        const btn = document.getElementById('finops-tab-' + t);
        if(content) content.style.display = t === tab ? 'block' : 'none';
        if(btn) btn.style.opacity = t === tab ? '1' : '0.5';
    });
};
```

- [ ] **Step 3: Verificar en browser que los 8 nav items funcionan sin errores de consola**

Abrir la app, hacer click en cada ítem del nav. Verificar que las páginas se alternan sin errores en consola.

- [ ] **Step 4: Commit**

```bash
git add app.js
git commit -m "feat: extender sw() para páginas SRE/FinOps, agregar showFinOpsTab()"
```

---

## Task 7: Agregar `_renderSre()` y redirigir contenido SRE a p-sre

**Files:**
- Modify: `app.js` — agregar función después de `_renderBusiness` (~línea 2127)

- [ ] **Step 1: Agregar `_renderSre()` que puebla p-sre con healthchecks, 12-factor y runbooks**

Después del cierre de `_renderBusiness` (línea ~2127), agregar:

```javascript
// ─── SRE Pilar Renderer ───────────────────────────────────────────────────────
function _renderSre(cn) {
    if (!cn) return;
    let hasContent = false;
    const emptyEl = document.getElementById('sre-empty');

    // Healthchecks
    const healthBox  = document.getElementById('sre-health-box');
    const healthCont = document.getElementById('sre-health-content');
    const hc = cn.healthcheck_config || {};
    if (healthBox && healthCont && (hc.liveness || hc.readiness || hc.startup)) {
        const render = (label, cfg) => cfg ? `
            <div style="margin-bottom:.6rem">
                <div style="font-size:.68rem;font-weight:700;color:var(--blue);margin-bottom:.2rem">${label}</div>
                <pre style="font-size:.65rem;background:rgba(0,0,0,.4);border:1px solid rgba(0,163,255,.15);border-radius:6px;padding:.5rem;overflow:auto;max-height:160px">${
                    typeof cfg === 'string' ? cfg : JSON.stringify(cfg, null, 2)
                }</pre>
            </div>` : '';
        healthCont.innerHTML = render('Liveness Probe', hc.liveness) + render('Readiness Probe', hc.readiness) + render('Startup Probe', hc.startup);
        healthBox.style.display = 'block';
        hasContent = true;
    }

    // 12-Factor violations
    const f12Box  = document.getElementById('sre-12factor-box');
    const f12List = document.getElementById('sre-12factor-list');
    if (f12Box && f12List && cn.twelve_factor_violations?.length) {
        f12List.innerHTML = cn.twelve_factor_violations.map(v => `
            <div style="padding:.5rem .8rem;background:rgba(249,212,35,.06);border:1px solid rgba(249,212,35,.2);border-radius:8px;margin-bottom:.4rem">
                <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.2rem">
                    <span style="font-weight:700;font-size:.78rem">${v.factor || v.title || ''}</span>
                    <span style="font-size:.62rem;color:var(--yellow);background:rgba(249,212,35,.1);padding:.1rem .4rem;border-radius:5px">${v.severity || 'MEDIUM'}</span>
                </div>
                <div style="font-size:.73rem;color:var(--t2)">${v.issue || v.description || ''}</div>
                ${v.fix ? `<div style="font-size:.7rem;color:var(--green);margin-top:.25rem">✓ Fix: ${v.fix}</div>` : ''}
            </div>`).join('');
        f12Box.style.display = 'block';
        hasContent = true;
    }

    // SRE Runbooks
    const rbBox  = document.getElementById('sre-runbook-box');
    const rbList = document.getElementById('sre-runbook-list');
    if (rbBox && rbList && cn.sre_runbook?.length) {
        rbList.innerHTML = cn.sre_runbook.map(r => `
            <div style="background:rgba(0,0,0,.3);border:1px solid var(--bdr);border-radius:8px;padding:.7rem 1rem">
                <div style="font-weight:700;font-size:.8rem;color:var(--blue);margin-bottom:.15rem">${r.title || ''}</div>
                ${r.trigger ? `<div style="font-size:.7rem;color:var(--yellow);margin-bottom:.4rem">⚡ ${r.trigger}</div>` : ''}
                ${r.steps?.length ? `<ol style="margin:0;padding-left:1.1rem">${r.steps.map(s => `<li style="font-size:.7rem;color:#ddd;padding:.1rem 0">${s}</li>`).join('')}</ol>` : ''}
            </div>`).join('');
        rbBox.style.display = 'block';
        hasContent = true;
    }

    if (hasContent && emptyEl) emptyEl.style.display = 'none';
}
```

- [ ] **Step 2: Llamar `_renderSre()` desde `updateAiFields` junto a `_renderCloudNative`**

En `updateAiFields` (~línea 2384), después de la línea `_renderCloudNative(aiData?.cloudnative);`, agregar:

```javascript
    // ── SRE Pilar — Healthchecks, 12-Factor, Runbooks
    _renderSre(aiData?.cloudnative);
```

- [ ] **Step 3: Verificar que al analizar un artefacto Java el pilar SRE muestra contenido**

1. Abrir la app en el browser
2. Analizar `prueba-facturacion.war`
3. Navegar al pilar SRE
4. Verificar que aparecen healthchecks y/o runbooks (si el agente los genera)

- [ ] **Step 4: Commit**

```bash
git add app.js
git commit -m "feat: _renderSre() popula pilar SRE con healthchecks, 12-factor y runbooks"
```

---

## Task 8: Agregar `_renderFinOpsAi()`, `loadFinOps()` y renderizar pilar FinOps

**Files:**
- Modify: `app.js` — agregar después de `_renderSre()`

- [ ] **Step 1: Agregar `_renderFinOpsAi()` que puebla p-finops con el resultado del CostOptimizationAgent**

```javascript
// ─── FinOps Pilar Renderer ────────────────────────────────────────────────────
function _renderFinOpsAi(biz, costOpt) {
    const emptyEl = document.getElementById('finops-empty');
    let hasContent = false;
    const fmt = n => n != null ? '$' + Number(n).toLocaleString() : '—';

    // ── TCO / ROI del BusinessAgent (reutiliza lógica existente)
    const bizBox = document.getElementById('finops-business-box');
    if (bizBox && biz?.risk_score) {
        const csEl = document.getElementById('finops-csuite');
        if (csEl && biz.c_suite_summary)
            csEl.innerHTML = `<b style="color:var(--blue)">Para el C-Suite:</b> ${biz.c_suite_summary}`;

        const legEl = document.getElementById('finops-tco-legacy');
        if (legEl && biz.tco_legacy) {
            const l = biz.tco_legacy;
            const rows = [
                ['Licenciamiento', l.annual_licensing, l.annual_licensing_detail],
                ['Labor/Mant.', l.annual_labor_maintenance, l.annual_labor_detail],
                ['Riesgo Seg.', l.annual_security_incidents_risk, l.annual_security_detail],
                ['Downtime', l.annual_downtime_cost, l.annual_downtime_detail],
                ['Compliance', l.annual_compliance_risk, l.annual_compliance_detail],
            ].filter(([, v]) => v != null && v !== 0);
            legEl.innerHTML = rows.map(([k, v, d]) =>
                `<div style="display:flex;justify-content:space-between;font-size:.73rem;padding:.2rem 0;border-bottom:1px solid rgba(255,255,255,.04)">
                    <span style="color:var(--t2)">${k}</span><span style="color:var(--red)">${fmt(v)}</span>
                </div>${d ? `<div style="font-size:.62rem;opacity:.5;line-height:1.3;margin-bottom:.1rem">${d}</div>` : ''}`
            ).join('') +
            `<div style="display:flex;justify-content:space-between;font-size:.8rem;font-weight:700;padding:.3rem 0">
                <span>Total Anual</span><span style="color:var(--red)">${fmt(l.total_annual)}</span>
            </div>`;
        }

        const awsEl = document.getElementById('finops-tco-aws');
        if (awsEl && biz.tco_aws) {
            const a = biz.tco_aws;
            const rows = [
                ['ECS Fargate/mes', a.ecs_fargate_monthly, a.ecs_fargate_detail],
                ['RDS Aurora/mes', a.rds_aurora_serverless_monthly, a.rds_detail],
                ['ALB/mes', a.alb_monthly, null],
                ['CloudWatch/mes', a.cloudwatch_monthly, null],
            ].filter(([, v]) => v != null && v !== 0);
            awsEl.innerHTML = rows.map(([k, v, d]) =>
                `<div style="display:flex;justify-content:space-between;font-size:.73rem;padding:.2rem 0;border-bottom:1px solid rgba(255,255,255,.04)">
                    <span style="color:var(--t2)">${k}</span><span style="color:var(--green)">${fmt(v)}</span>
                </div>${d ? `<div style="font-size:.62rem;opacity:.5;line-height:1.3;margin-bottom:.1rem">${d}</div>` : ''}`
            ).join('') +
            `<div style="display:flex;justify-content:space-between;font-size:.8rem;font-weight:700;padding:.3rem 0">
                <span>Total Anual</span><span style="color:var(--green)">${fmt(a.total_annual)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:.72rem;padding:.15rem 0">
                <span style="color:var(--t2)">Migración (único)</span><span style="color:var(--yellow)">${fmt(a.migration_one_time_cost)}</span>
            </div>`;
        }

        const roiEl = document.getElementById('finops-roi-content');
        if (roiEl && biz.roi) {
            const r = biz.roi;
            roiEl.innerHTML = [
                { label: 'Ahorro Anual', val: fmt(r.annual_saving), color: 'var(--green)' },
                { label: 'Ahorro 5 años', val: fmt(r.five_year_saving), color: 'var(--green)' },
                { label: 'Payback', val: r.payback_months ? r.payback_months + ' meses' : '—', color: 'var(--blue)' },
                { label: 'ROI', val: r.roi_pct ? r.roi_pct + '%' : '—', color: 'var(--yellow)' },
            ].map(({ label, val, color }) =>
                `<div style="text-align:center"><div style="font-size:1.1rem;font-weight:700;color:${color}">${val}</div><div style="font-size:.6rem;color:var(--t2)">${label}</div></div>`
            ).join('');
        }

        bizBox.style.display = 'block';
        hasContent = true;
    }

    // ── CostOptimizationAgent — Tabs IA
    const tabsBox = document.getElementById('finops-tabs-box');
    if (tabsBox && costOpt && Object.keys(costOpt).length > 0) {
        // Tab Multi-Cloud (IA)
        const mc = costOpt.multicloud || {};
        if (mc.recommendation) {
            const recEl = document.getElementById('finops-mc-recommendation');
            if (recEl) {
                const cloudLabel = { aws: 'AWS', azure: 'Azure', gcp: 'GCP' }[mc.recommendation] || mc.recommendation;
                recEl.innerHTML = `<span style="font-weight:700;color:var(--green)">✓ Recomendación IA: <span style="color:var(--yellow)">${cloudLabel}</span></span>
                    ${mc.recommendation_rationale ? `<div style="font-size:.75rem;color:var(--t2);margin-top:.3rem;line-height:1.5">${mc.recommendation_rationale}</div>` : ''}`;
                recEl.style.display = 'block';
            }
        }

        // Tab AWS Optimizer (IA)
        const opt = costOpt.aws_optimization || {};
        const optSumEl = document.getElementById('finops-opt-summary');
        if (optSumEl && opt.estimated_savings_pct) {
            optSumEl.innerHTML = `Cobertura Savings Plans recomendada: <b style="color:var(--yellow)">${Math.round((opt.savings_plans_coverage||0)*100)}%</b> &nbsp;|&nbsp; Ahorro estimado: <b style="color:var(--green)">${opt.estimated_savings_pct}%</b> sobre costos on-demand`;
        }
        const optListEl = document.getElementById('finops-opt-list');
        if (optListEl && opt.recommendations?.length) {
            optListEl.innerHTML = opt.recommendations.map(r => `
                <div style="background:rgba(0,163,255,.05);border:1px solid rgba(0,163,255,.2);border-radius:8px;padding:.6rem .8rem">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.4rem">
                        <span style="font-weight:700;font-size:.8rem">${r.service}</span>
                        <span style="font-size:.65rem;color:var(--green);font-weight:700">-$${r.savings_usd_monthly}/mes</span>
                    </div>
                    <div style="font-size:.72rem;color:var(--t2);margin:.2rem 0">${r.current} → <span style="color:var(--blue)">${r.recommended}</span></div>
                    ${r.rationale ? `<div style="font-size:.68rem;opacity:.6;line-height:1.3">${r.rationale}</div>` : ''}
                </div>`).join('');
        }

        // Tab Right-Sizing (IA)
        const rs = costOpt.rightsizing || {};
        const rsSignals = document.getElementById('finops-rs-signals');
        if (rsSignals && rs.signals_used?.length) {
            rsSignals.innerHTML = `<b style="color:var(--purple)">Señales del inventario usadas:</b> ${rs.signals_used.join(' · ')}`;
        }
        const rsTbody = document.getElementById('finops-rs-table-body');
        if (rsTbody && rs.recommendations?.length) {
            rsTbody.innerHTML = rs.recommendations.map(r => `
                <tr>
                    <td style="padding:.4rem">${r.service}</td>
                    <td style="text-align:center;padding:.4rem;color:var(--t2)">${r.current_default}</td>
                    <td style="text-align:center;padding:.4rem;color:var(--green)">${r.recommended}</td>
                    <td style="text-align:right;padding:.4rem;color:var(--yellow)">-$${r.monthly_savings_usd}/mes</td>
                    <td style="padding:.4rem;font-size:.72rem;color:var(--t2)">${r.reason}</td>
                </tr>`).join('');
        }

        // Tab Sprint Cost (IA)
        const sc = costOpt.sprint_cost || {};
        const scSumEl = document.getElementById('finops-sc-summary');
        if (scSumEl && sc.total_one_time_usd) {
            scSumEl.innerHTML = [
                { label: 'Costo original', val: '$' + Number(sc.total_one_time_usd).toLocaleString(), color: 'var(--red)' },
                { label: 'Costo optimizado', val: '$' + Number(sc.optimized_usd).toLocaleString(), color: 'var(--green)' },
                { label: 'Ahorro potencial', val: '$' + Number(sc.savings_usd).toLocaleString(), color: 'var(--yellow)' },
            ].map(({ label, val, color }) =>
                `<div class="card" style="padding:.7rem;text-align:center"><div style="font-size:1.1rem;font-weight:700;color:${color}">${val}</div><div style="font-size:.62rem;color:var(--t2)">${label}</div></div>`
            ).join('');
        }
        const scListEl = document.getElementById('finops-sc-list');
        if (scListEl && sc.optimizations?.length) {
            scListEl.innerHTML = sc.optimizations.map(o => `
                <div style="background:rgba(0,176,155,.05);border:1px solid rgba(0,176,155,.2);border-radius:8px;padding:.6rem .8rem">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.4rem">
                        <span style="font-weight:700;font-size:.78rem">${o.action}</span>
                        <span style="font-size:.7rem;color:var(--green);font-weight:700">-$${Number(o.saving_usd).toLocaleString()}</span>
                    </div>
                    ${o.reason ? `<div style="font-size:.72rem;color:var(--t2);margin-top:.2rem">${o.reason}</div>` : ''}
                </div>`).join('');
        }

        tabsBox.style.display = 'block';
        hasContent = true;
    }

    if (hasContent && emptyEl) emptyEl.style.display = 'none';
}
```

- [ ] **Step 2: Agregar `loadFinOps()` que llama `/finops/{scan_id}` y actualiza los precios reales**

```javascript
window.loadFinOps = async function() {
    if (!lastScanId) return;
    const btn = document.getElementById('finops-load-btn');
    const badge = document.getElementById('finops-cache-badge');
    if (btn) { btn.disabled = true; btn.innerText = '⏳ Cargando...'; }

    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        const r = await apiFetch(`${apiUrl}/finops/${lastScanId}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();

        // Actualizar tabla multi-cloud con precios reales del endpoint
        const tbody = document.getElementById('finops-mc-table-body');
        const pc = d.price_comparison || {};
        const clouds = [
            { id: 'aws',   label: 'AWS',   color: 'var(--yellow)' },
            { id: 'azure', label: 'Azure', color: '#0078d4' },
            { id: 'gcp',   label: 'GCP',   color: 'var(--green)' },
        ];
        if (tbody && pc.aws) {
            tbody.innerHTML = clouds.map(({ id, label, color }) => {
                const cloud = pc[id] || {};
                const bd = cloud.breakdown || {};
                const fmt = v => v ? `$${v}` : '—';
                return `<tr>
                    <td style="padding:.4rem;font-weight:700;color:${color}">${label}</td>
                    <td style="text-align:right;padding:.4rem">${fmt(bd.container)}</td>
                    <td style="text-align:right;padding:.4rem">${fmt(bd.database)}</td>
                    <td style="text-align:right;padding:.4rem">${fmt(bd.cache)}</td>
                    <td style="text-align:right;padding:.4rem">${fmt(bd.lb)}</td>
                    <td style="text-align:right;padding:.4rem;font-weight:700;color:${color}">$${cloud.monthly_usd || '—'}</td>
                </tr>`;
            }).join('');
        }

        if (badge) {
            badge.style.display = 'inline';
            badge.style.cssText = 'font-size:.62rem;padding:.15rem .5rem;border-radius:10px;' +
                (d.cache_hit
                    ? 'background:rgba(0,176,155,.15);color:var(--green);border:1px solid rgba(0,176,155,.4)'
                    : 'background:rgba(0,163,255,.15);color:var(--blue);border:1px solid rgba(0,163,255,.4)');
            badge.textContent = d.cache_hit ? '🟢 Precios cacheados' : '🔵 Precios actualizados';
        }
    } catch(e) {
        console.warn('FinOps load error:', e);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = '🔄 Actualizar Precios'; }
    }
};
```

- [ ] **Step 3: Llamar `_renderFinOpsAi()` desde `updateAiFields`**

En `updateAiFields` (~línea 2388), después de la línea `_renderBusiness(aiData?.business);`, agregar:

```javascript
    // ── FinOps Pilar — TCO + CostOptimizationAgent
    _renderFinOpsAi(aiData?.business, aiData?.cost_optimization);
```

- [ ] **Step 4: Verificar funcionamiento end-to-end**

1. Iniciar backend: `cd server && uvicorn main:app --reload --port 8000`
2. Abrir app en browser
3. Analizar `prueba-facturacion.war`
4. Navegar al pilar FinOps
5. Verificar:
   - TCO legacy y AWS se muestran (datos del BusinessAgent)
   - Si CostOptimizationAgent retornó datos: tabs muestran contenido
   - Botón "Actualizar Precios" llama `/finops/{scan_id}` y puebla la tabla multi-cloud
   - Badge muestra 🔵 en primera carga, 🟢 en segunda (caché)
6. Navegar al pilar SRE → verificar healthchecks y runbooks

- [ ] **Step 5: Commit final**

```bash
git add app.js
git commit -m "feat: _renderFinOpsAi() y loadFinOps() — pilar FinOps completo"
```

---

## Task 9: Verificación de no-regresión

**Files:** Ninguno (solo verificación)

- [ ] **Step 1: Verificar que análisis SSH/Manual sigue funcionando**

1. Cambiar a modo "Pegar Datos Manual"
2. Pegar un inventario básico (salida del `collector.sh`)
3. Click "Analizar Datos"
4. Verificar que p0–p3 se poblan correctamente
5. Verificar que el pilar FinOps muestra TCO (desde BusinessAgent) aunque CostOptimizationAgent no corra para SSH/Manual

- [ ] **Step 2: Verificar que análisis de artefacto Java sigue produciendo Bundle descargable**

1. Analizar `prueba-facturacion.war`
2. Esperar resultado completo
3. Click "📦 Bundle" — verificar que se descarga el ZIP correctamente

- [ ] **Step 3: Verificar que Historial y Dashboard ejecutivo siguen funcionando**

Navegar a ⏳ Historial y 📊 Dashboard. Verificar que se cargan sin errores.

- [ ] **Step 4: Verificar que la caché de pricing funciona**

```bash
# Con backend corriendo y un scan_id real:
curl -s "http://localhost:8000/finops/SCAN_ID" -H "X-API-KEY: mf-api-key-2026" | python -m json.tool | grep cache_hit
# Primera llamada: "cache_hit": false
curl -s "http://localhost:8000/finops/SCAN_ID" -H "X-API-KEY: mf-api-key-2026" | python -m json.tool | grep cache_hit
# Segunda llamada: "cache_hit": true
```

- [ ] **Step 5: Commit de cierre**

```bash
git add .
git commit -m "feat: FinOps Pro + reorganización pilares — implementación completa"
```

---

## Self-Review

### Spec Coverage

| Requisito del spec | Tarea |
|--------------------|-------|
| `pricing_cache` table SQLite con TTL 24h | Task 1 |
| Prompt `CostOptimizationAgent` (multicloud, ri, rightsizing, sprint_cost) | Task 2 |
| Agente wired al pipeline Stage 2 paralelo con MigrationAgent | Task 3 |
| Fusión en `ai_response["cost_optimization"]` | Task 3 |
| `/finops/{scan_id}` endpoint | Task 4 |
| Fetchers Azure (prices.azure.com) y GCP (cloudbilling) | Task 4 |
| Normalización a $/hora por servicio equivalente | Task 4 |
| Nav renombrado (6 pilares) | Task 5 |
| Página p-sre con healthchecks/12-factor/runbooks | Task 5 + Task 7 |
| Página p-finops con 4 tabs | Task 5 + Task 8 |
| `sw()` maneja 'sre' y 'finops' | Task 6 |
| `showFinOpsTab()` para switching de tabs | Task 6 |
| `_renderSre()` popula p-sre | Task 7 |
| `_renderFinOpsAi()` popula p-finops con IA + precios reales | Task 8 |
| `loadFinOps()` llama endpoint y actualiza tabla multi-cloud | Task 8 |
| Sin regresiones en SSH/Manual/Java artifact | Task 9 |

### Notas de implementación

- **GCP_API_KEY** es opcional: si no está en `.env`, se usan precios GCP baseline 2025 (ver `_fetch_gcp_prices`).
- **requests** debe estar instalado: `pip install requests`. Si ya está en `requirements.txt`, no se necesita acción.
- El agente `CostOptimizationAgent` solo corre en **artefactos Java** (donde `is_java_artifact=True`). Para SSH/Manual, `cost_opt_result` queda vacío y el pilar FinOps muestra solo el TCO del BusinessAgent.
- La tabla multi-cloud en el frontend se actualiza **lazy** (al click de "Actualizar Precios" o al navegar al pilar), no durante el análisis inicial, para no bloquear la UX.
