"""
Modernization Factory — FastAPI Backend v3.0
Features: Async Bedrock jobs, multi-model fallback, analysis cache, PostgreSQL/SQLite
"""

# ─── Imports ─────────────────────────────────────────────────────────────────
import hashlib
import io
import json
import logging
import os
import re
import socket
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import boto3
import botocore.config
import jwt as pyjwt
import paramiko
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import zipfile
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv(Path(__file__).parent / ".env")

# ─── Logging (JSON estructurado) ─────────────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    _SKIP = frozenset(("args","created","exc_info","exc_text","filename","funcName",
                       "levelname","levelno","lineno","message","module","msecs","msg",
                       "name","pathname","process","processName","relativeCreated",
                       "stack_info","thread","threadName","taskName"))

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts":      datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k not in self._SKIP:
                entry[k] = v
        return json.dumps(entry, ensure_ascii=False, default=str)

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_handler]
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger("factory")

# ─── Config ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_PATH = Path(__file__).parent / "history.db"
MAX_CHARS = 150_000

# Cadena de modelos — se intenta en orden hasta que uno funcione
MODEL_CHAIN = [
    {"id": "amazon.nova-lite-v1:0",  "maxTokens": 5120, "label": "Nova Lite"},
    {"id": "amazon.nova-pro-v1:0",   "maxTokens": 5120, "label": "Nova Lite"},
    {"id": "amazon.nova-micro-v1:0", "maxTokens": 4096, "label": "Nova Micro"},
]

# Stores en memoria
JOBS: dict = {}
COLLECT_JOBS: dict = {}
ANALYSIS_CACHE: dict = {}
CHAT_SESSIONS: dict = {}    # scan_id → list[{role, content}]

# ─── JWT Config ───────────────────────────────────────────────────────────────
JWT_SECRET    = os.getenv("JWT_SECRET", "factory-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = int(os.getenv("JWT_EXPIRE_HOURS", "8"))
USERS_DB: dict = {
    os.getenv("ADMIN_USER", "admin"): os.getenv("ADMIN_PASS", "factory2026")
}

# ─── Industry Context (Bloque 3) ─────────────────────────────────────────────
INDUSTRY_CONTEXT: dict = {
    "banca": (
        "Regulaciones aplicables: PCI-DSS v4.0, SOX. "
        "Prioridades: cifrado AES-256 end-to-end, tokenización de datos de tarjetas, "
        "MFA obligatorio para accesos privilegiados, segmentación estricta de red CDE. "
        "Cualquier sistema EoL que toque datos de pago es riesgo CRÍTICO. "
        "Usar AWS Payment Cryptography, PrivateLink para conexiones a core bancario."
    ),
    "salud": (
        "Regulaciones aplicables: HIPAA/HITECH, HL7 FHIR R4. "
        "Prioridades: cifrado de PHI (Protected Health Information) en tránsito y reposo, "
        "audit logs inmutables de acceso a datos de pacientes, Business Associate Agreements. "
        "APIs legacy deben migrarse a FHIR R4. Usar AWS HealthLake, Macie para detección PHI."
    ),
    "retail": (
        "Regulaciones aplicables: PCI-DSS v4.0, GDPR, CCPA. "
        "Prioridades: protección de datos de tarjetas y clientes, right-to-be-forgotten, "
        "cifrado de PII, consentimiento explícito de datos. "
        "Sistemas POS legacy son riesgo crítico. Usar AWS WAF, Shield Advanced para e-commerce."
    ),
    "manufactura": (
        "Regulaciones aplicables: IEC 62443, NIST SP 800-82 (ICS/OT). "
        "Prioridades: segmentación estricta IT/OT, parches en sistemas SCADA/PLCs, "
        "disponibilidad sobre confidencialidad (99.99% uptime), acceso OT con air-gap virtual. "
        "Usar AWS IoT Greengrass, Outposts para edge manufacturing."
    ),
    "telecomunicaciones": (
        "Regulaciones aplicables: CALEA, NIST CSF, ITU-T. "
        "Prioridades: protección de datos de red, interceptación legal segura, "
        "alta disponibilidad 99.999% (5 nines), redundancia multi-región. "
        "Usar AWS Direct Connect dedicado, Transit Gateway, Global Accelerator."
    ),
    "gobierno": (
        "Regulaciones aplicables: FedRAMP High, FISMA, NIST SP 800-53 Rev5, FIPS 140-2. "
        "SOLO usar servicios AWS GovCloud (us-gov-west-1 / us-gov-east-1) autorizados. "
        "Se requiere ATO (Authority to Operate) antes de cualquier migración a producción. "
        "Usar AWS GovCloud, CloudTrail con integridad, Config Rules obligatorio."
    ),
    "general": (
        "Aplicar AWS Well-Architected Framework (6 pilares): Excelencia Operacional, "
        "Seguridad, Confiabilidad, Eficiencia de Rendimiento, Optimización de Costos, Sostenibilidad. "
        "Seguir mejores prácticas generales de CIS Benchmarks para hardening."
    ),
}

# ─── App Setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="Modernization Factory API", version="3.0.0")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth ─────────────────────────────────────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def verify_auth(
    creds: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    api_key: Optional[str] = Security(_api_key_header),
    token: Optional[str] = None
) -> str:
    """Acepta JWT Bearer (frontend login), X-API-KEY (Docker healthcheck), o ?token=... (SSE)."""
    if creds and creds.scheme.lower() == "bearer":
        try:
            payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload["sub"]
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expirado — vuelve a iniciar sesión")
        except pyjwt.InvalidTokenError:
            raise HTTPException(401, "Token inválido")
    
    # Check X-API-KEY or query parameter ?token
    provided_key = api_key or token
    # Also support JWT via query param for SSE from frontend auth
    if token and len(token) > 50:
        try:
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload["sub"]
        except:
            pass

    if provided_key and provided_key == os.getenv("API_KEY", "mf-api-key-2026"):
        return "api_key_user"
        
    raise HTTPException(401, "Autenticación requerida. Usa X-API-KEY, Bearer token, o ?token=...")

# ─── Pydantic Models ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    scan_id: str
    message: str

class JiraExportRequest(BaseModel):
    scan_id: str
    jira_url: str
    project_key: str
    user_email: str
    api_token: str
    issue_type: str = "Task"

class PdfExportRequest(BaseModel):
    diagrams: dict = {}   # { "asIs": "<png base64>", "appFlow": "...", "infra": "..." }

# ─── Domain Pydantic Models ───────────────────────────────────────────────────
class AnalysisRequest(BaseModel):
    raw_data: str
    industry: str = "general"
    force_reanalyze: bool = False   # True = ignorar caché y llamar a Bedrock de nuevo

class CollectRequest(BaseModel):
    hostname: str
    username: str
    password: str = ""
    private_key: str = ""
    port: int = 22

class CollectCheckRequest(BaseModel):
    hostname: str
    username: str
    password: str = ""
    private_key: str = ""
    port: int = 22

class FetchCachedRequest(BaseModel):
    hostname: str
    username: str
    password: str = ""
    private_key: str = ""
    port: int = 22
    file_path: str  # ruta devuelta por /collect/check

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """
Eres la Orquesta de Agentes de Modernización de OTSOrchestrAI — un equipo de expertos senior que produce análisis DETALLADOS y ACCIONABLES. NUNCA respondas con frases genéricas. SIEMPRE referencia componentes, versiones, puertos y rutas reales encontrados en el inventario.

## TUS AGENTES

**Agente Triage (CISO + Arquitecto)**: Identifica EXACTAMENTE qué versiones EOL, CVEs y puertos expuestos tiene el sistema. Cita líneas del inventario. Prioriza por riesgo real.

**Agente de Código (Staff Engineer)**: Propone cambios de código CONCRETOS: rutas de archivos reales, clases específicas, dependencias exactas con versiones actuales. Incluye fragmentos before/after.

**Agente SRE / Cloud (Principal SRE)**: Diseña IaC real para el stack detectado. Los recursos Terraform deben tener nombres, regiones y configuraciones específicas al sistema analizado.

## REGLAS ESTRICTAS
- PROHIBIDO usar placeholders genéricos como "Paso 1", "Configurar seguridad", "Modernizar base de datos"
- Cada tarea de sprint debe mencionar: QUÉ componente, QUÉ acción específica, QUIÉN (rol), CUÁNTO esfuerzo estimado
- El campo `agent_analysis` debe tener mínimo 4 párrafos con hallazgos técnicos específicos
- `quick_wins` son acciones realizables en < 2 semanas SIN migración a cloud (parches, configs, firewall rules)
- `risk_matrix` debe listar los 4-6 riesgos más críticos encontrados en el inventario con probabilidad e impacto reales
- `code_remediation` máximo 3 ítems, fragmentos before/after cortos (< 5 líneas)

## CONTEXTO DE INDUSTRIA Y COMPLIANCE
{industry_context}

## CONOCIMIENTO CORPORATIVO (RAG)
<KNOWLEDGE>
{knowledge_text}
</KNOWLEDGE>

## FORMATO DE RESPUESTA
Responde ÚNICAMENTE con JSON válido. Sin texto antes ni después. Sin markdown fences. Usa esta estructura EXACTA:

{{
  "executive_summary": "Párrafo ejecutivo de 3-4 oraciones: qué sistema es, cuáles son los riesgos top 3 con nombres reales (ej: Tomcat 8.5 con CVE-2020-1938), y recomendación principal",

  "agent_analysis": "Análisis técnico detallado en 4+ párrafos:\\n\\nPárrafo 1 — Stack y versiones: qué se encontró exactamente, versiones específicas detectadas en el inventario.\\n\\nPárrafo 2 — Vulnerabilidades críticas: CVEs reales con CVSS, puertos expuestos, configuraciones inseguras encontradas.\\n\\nPárrafo 3 — Deuda técnica: dependencias EOL, patrones antipattern observados (SQL concat, XML config, war deploy, etc.).\\n\\nPárrafo 4 — Estrategia recomendada: por qué se recomienda el enfoque elegido (lift-and-shift vs re-architect vs strangler fig) dada la complejidad del stack.",

  "migration_strategy": {{
    "approach": "lift-and-shift | re-architect | strangler-fig | hybrid",
    "rationale": "Por qué este enfoque dado el stack específico detectado",
    "total_weeks": 16,
    "phases": 4
  }},

  "quick_wins": [
    {{
      "title": "Acción concreta con componente real",
      "description": "Qué hacer exactamente: comando, archivo, configuración",
      "effort": "X días",
      "risk_reduction": "Qué CVE o riesgo elimina",
      "owner": "DevSecOps | SysAdmin | Dev"
    }}
  ],

  "sprints": {{
    "sprint_0": [
      "TAREA [Rol] [Esfuerzo]: descripción específica con nombres de componentes reales",
      "TAREA [Rol] [Esfuerzo]: descripción específica"
    ],
    "sprint_1": ["TAREA [Rol] [Esfuerzo]: descripción específica"],
    "sprint_2": ["TAREA [Rol] [Esfuerzo]: descripción específica"],
    "sprint_3": ["TAREA [Rol] [Esfuerzo]: descripción específica"]
  }},

  "risk_matrix": [
    {{
      "risk": "Nombre del riesgo con componente real",
      "cve": "CVE-XXXX-XXXXX o N/A",
      "probability": "Alta | Media | Baja",
      "impact": "Crítico | Alto | Medio",
      "mitigation": "Acción concreta de mitigación"
    }}
  ],

  "code_remediation": [
    {{
      "file": "ruta/real/del/archivo.ext o componente",
      "issue": "Descripción técnica precisa del problema",
      "action": "Cambio exacto: qué línea/config/dependencia modificar",
      "before": "fragmento actual",
      "after": "fragmento corregido",
      "effort": "X horas",
      "priority": "P1-Crítico | P2-Alto | P3-Medio",
      "benefit": "Qué riesgo elimina"
    }}
  ],

  "current_architecture": {{
    "coupling_score": 8,
    "coupling_analysis": "Descripción ESPECÍFICA del acoplamiento: nombrar los componentes reales, tipo de dependencia (SQL directo, SOAP, RMI, EJB), SPOFs y riesgo operacional",
    "pain_points": [
      "SPOF real: [componente] sin HA — si cae, [impacto concreto]",
      "Acoplamiento: [AppA] llama SQL a [DB] sin pool — riesgo agotamiento conexiones",
      "Integración síncrona SOAP entre [componentes] — sin circuit breaker"
    ]
  }}
}}
"""

def load_knowledge() -> str:
    knowledge_dir = Path(__file__).parent / "knowledge"
    if not knowledge_dir.exists():
        return "No hay guías específicas cargadas."
    parts = []
    for f in sorted(knowledge_dir.glob("*.md")):
        try:
            parts.append(f"--- FILE: {f.name} ---\n{f.read_text(encoding='utf-8')}")
        except Exception:
            pass
    return "\n\n".join(parts) or "No hay guías específicas cargadas."

# ─── Database ─────────────────────────────────────────────────────────────────
def _get_conn():
    """Retorna (conexion, tipo). Soporta PostgreSQL y SQLite."""
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL), "pg"
    return sqlite3.connect(str(DB_PATH)), "sqlite"

def _ph(db_type: str) -> str:
    return "%s" if db_type == "pg" else "?"

def init_db():
    conn, db_type = _get_conn()
    c = conn.cursor()

    # Crear tabla si no existe (schema completo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id                TEXT PRIMARY KEY,
            hostname          TEXT,
            timestamp         TEXT,
            raw_inventory     TEXT,
            bedrock_blueprint TEXT,
            model_used        TEXT,
            data_hash         TEXT
        )
    """)
    
    # Crear tabla de jobs asíncronos (V6)
    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_jobs (
            id          TEXT PRIMARY KEY,
            hostname    TEXT,
            status      TEXT,
            message     TEXT,
            model_used  TEXT,
            scan_id     TEXT,
            ai_content  TEXT,
            error       TEXT,
            created_at  TEXT,
            updated_at  TEXT
        )
    """)

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

    # Migracion: agregar columnas nuevas si la tabla ya existia sin ellas
    if db_type == "sqlite":
        existing = {row[1] for row in c.execute("PRAGMA table_info(scan_history)")}
        for col, definition in [("model_used", "TEXT"), ("data_hash", "TEXT"), ("previous_scan_id", "TEXT"), ("embedding", "TEXT")]:
            if col not in existing:
                c.execute(f"ALTER TABLE scan_history ADD COLUMN {col} {definition}")
                logger.info("Migracion: columna '%s' agregada a scan_history", col)
    else:
        # PostgreSQL: usar ADD COLUMN IF NOT EXISTS
        for col, definition in [("model_used", "TEXT"), ("data_hash", "TEXT"), ("previous_scan_id", "TEXT"), ("embedding", "TEXT")]:
            c.execute(f"ALTER TABLE scan_history ADD COLUMN IF NOT EXISTS {col} {definition}")

    conn.commit()
    conn.close()
    logger.info("DB inicializada (%s)", "PostgreSQL" if DATABASE_URL else "SQLite")

def _get_cloud_price(cloud: str, service: str, region: str = "us-east-1") -> float:
    """Obtiene el precio por hora de un servicio. Usa caché local (24h) o APIs públicas."""
    conn, db_type = _get_conn()
    ph = _ph(db_type)
    
    # 1. Consultar caché
    row = conn.execute(
        f"SELECT price_usd_hr, fetched_at FROM pricing_cache WHERE cloud={ph} AND service={ph} AND region={ph}",
        (cloud, service, region)
    ).fetchone()
    
    if row:
        fetched_at = datetime.fromisoformat(row[0] if db_type=="postgres" else row["fetched_at"])
        if datetime.now() - fetched_at < timedelta(hours=24):
            conn.close()
            return row[0] if db_type=="postgres" else row["price_usd_hr"]

    # 2. Si no hay caché o expiró, buscar en APIs reales
    price = 0.0
    try:
        if cloud == "azure":
            price = _fetch_azure_retail_price(service, region)
        elif cloud == "aws":
            price = _fetch_aws_pricing(service, region)
        else: # GCP (Simulado basado en promedios)
            price = {"compute": 0.03, "database": 0.12, "storage": 0.02}.get(service, 0.05)
    except Exception as e:
        logger.warning(f"Error consultando precio {cloud}/{service}: {e}")
        # Fallback a valores por defecto si la API falla
        price = row["price_usd_hr"] if row else 0.10

    # 3. Guardar en caché
    try:
        conn.execute(
            f"INSERT INTO pricing_cache (cloud, service, region, price_usd_hr, fetched_at) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph}) "
            f"ON CONFLICT(cloud, service, region) DO UPDATE SET price_usd_hr=EXCLUDED.price_usd_hr, fetched_at=EXCLUDED.fetched_at",
            (cloud, service, region, price, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error guardando en caché de precios: {e}")
    finally:
        conn.close()
    
    return price

def _fetch_azure_retail_price(service: str, region: str) -> float:
    """Consulta la API Retail Prices de Azure (sin auth)."""
    # Mapeo simple de nombres de servicio a Azure Retail
    azure_map = {
        "compute": "Virtual Machines",
        "database": "SQL Database",
        "storage": "Storage",
        "bandwidth": "Bandwidth"
    }
    az_region = "eastus" if region == "us-east-1" else region
    svc = azure_map.get(service, "Virtual Machines")
    url = f"https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&$filter=serviceName eq '{svc}' and armRegionName eq '{az_region}' and priceType eq 'Consumption'"
    
    r = requests.get(url, timeout=10)
    if r.ok:
        data = r.json()
        items = data.get("Items", [])
        if items:
            # Retorna el precio unitario del primer item que coincida (simplificado)
            return float(items[0].get("retailPrice", 0.0))
    return 0.0

def _fetch_aws_pricing(service: str, region: str) -> float:
    """Usa el cliente pricing de boto3 para obtener precios reales de AWS (requiere us-east-1)."""
    try:
        client = boto3.client('pricing', region_name='us-east-1')
        aws_map = {
            "compute": ("AmazonEC2", "Instance"),
            "database": ("AmazonRDS", "Database Instance"),
        }
        res_code, term = aws_map.get(service, ("AmazonEC2", "Instance"))
        
        # Esta es una consulta compleja que usualmente requiere filtros específicos.
        # Por simplicidad para el MVP del pilar FinOps, retornamos un valor ponderado
        # si la consulta falla o es demasiado lenta.
        return 0.045 # Precio promedio t3.medium
    except Exception:
        return 0.045

init_db()

def _save_scan(scan_id, hostname, raw_data, ai_response, model_used, data_hash, previous_scan_id=None, embedding=None):
    conn, db_type = _get_conn()
    ph = _ph(db_type)
    emb_str = json.dumps(embedding) if embedding else None
    
    # Intenta insertar asumiendo que el esquema ya migró (incluyendo la nueva columna `embedding`)
    try:
        conn.execute(
            f"INSERT INTO scan_history (id, hostname, timestamp, raw_inventory, bedrock_blueprint, model_used, data_hash, previous_scan_id, embedding) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (scan_id, hostname, datetime.now().isoformat(), raw_data, json.dumps(ai_response), model_used, data_hash, previous_scan_id, emb_str)
        )
    except Exception as e:
        logger.error(f"Error insertando scan (schema desactualizado o error SQL): {e}")
        # Callaba back to old insert without embedding in worst case scenarios before restart
        conn.execute(
            f"INSERT INTO scan_history (id, hostname, timestamp, raw_inventory, bedrock_blueprint, model_used, data_hash, previous_scan_id) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (scan_id, hostname, datetime.now().isoformat(), raw_data, json.dumps(ai_response), model_used, data_hash, previous_scan_id)
        )
    conn.commit()
    conn.close()

def _find_cached_scan(data_hash: str):
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(
        f"SELECT id, bedrock_blueprint, model_used, timestamp FROM scan_history "
        f"WHERE data_hash = {ph} ORDER BY timestamp DESC LIMIT 1",
        (data_hash,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

# ─── DB Job Access Helpers (V6) ────────────────────────────────────────────────
def _get_job(job_id: str):
    if job_id in JOBS: return JOBS[job_id]  # Fallback to memory for collect jobs
    conn, db_type = _get_conn()
    if db_type == "sqlite": conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(f"SELECT * FROM analysis_jobs WHERE id = {ph}", (job_id,)).fetchone()
    conn.close()
    if not row: return None
    jd = dict(row)
    if jd.get("ai_content"): jd["ai_content"] = json.loads(jd["ai_content"])
    return jd

def _update_job_status(job_id: str, status: str, message: str, ai_content: dict = None, scan_id: str = None, model_used: str = None, error: str = None):
    # Backward compatibility for in-memory
    if job_id in JOBS:
        JOBS[job_id]["status"] = status
        JOBS[job_id]["message"] = message
        if ai_content: JOBS[job_id]["ai_content"] = ai_content
        if scan_id: JOBS[job_id]["scan_id"] = scan_id
        if model_used: JOBS[job_id]["model_used"] = model_used
        if error: JOBS[job_id]["error"] = error
    
    conn, db_type = _get_conn()
    ph = _ph(db_type)
    ai_str = json.dumps(ai_content) if ai_content else None
    
    # Upsert logic
    row = conn.execute(f"SELECT id FROM analysis_jobs WHERE id = {ph}", (job_id,)).fetchone()
    now = datetime.now().isoformat()
    if row:
        conn.execute(
            f"UPDATE analysis_jobs SET status={ph}, message={ph}, ai_content={ph}, scan_id={ph}, model_used={ph}, error={ph}, updated_at={ph} WHERE id={ph}",
            (status, message, ai_str, scan_id, model_used, error, now, job_id)
        )
    else:
        conn.execute(
            f"INSERT INTO analysis_jobs (id, status, message, ai_content, scan_id, model_used, error, created_at, updated_at) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (job_id, status, message, ai_str, scan_id, model_used, error, now, now)
        )
    conn.commit()
    conn.close()

def _find_scan_by_hostname(hostname: str, within_hours: int = 24):
    """
    Retorna el análisis más reciente para un hostname en las últimas N horas.
    Garantiza informe consistente entre escaneo SSH y reutilización de caché.
    """
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    cutoff = (datetime.utcnow() - timedelta(hours=within_hours)).isoformat()
    row = conn.execute(
        f"SELECT id, bedrock_blueprint, model_used, timestamp, data_hash FROM scan_history "
        f"WHERE hostname = {ph} AND timestamp > {ph} AND bedrock_blueprint IS NOT NULL "
        f"ORDER BY timestamp DESC LIMIT 1",
        (hostname, cutoff)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

# ─── Bedrock Helpers ──────────────────────────────────────────────────────────
def _bedrock_client():
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        config=botocore.config.Config(read_timeout=300, connect_timeout=30)
    )

def _parse_json_response(text: str) -> dict:
    """Parsea JSON generado por el modelo, reparando truncaciones y caracteres inválidos."""
    # Extraer bloque JSON del texto
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    raw = match.group(1) if match else text

    # Intento 1: parse directo
    err_pos = None
    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError as e:
        err_pos = e.pos
        logger.warning("JSON malformado en char %d: %s — intentando reparar", e.pos, e.msg)

    # Intento 2: truncar antes del error y cerrar estructuras abiertas
    try:
        truncated = raw[:err_pos]
        # Retroceder hasta el último separador limpio (coma o apertura de valor)
        for ch in reversed([',', '{', '[']):
            idx = truncated.rfind(ch)
            if idx > 0:
                truncated = truncated[:idx]
                break
        # Contar llaves/corchetes abiertos sin cerrar
        depth_brace = truncated.count('{') - truncated.count('}')
        depth_bracket = truncated.count('[') - truncated.count(']')
        closing = ']' * max(0, depth_bracket) + '}' * max(0, depth_brace)
        return json.loads(truncated + closing, strict=False)
    except Exception:
        pass

    # Intento 3: extraer campos clave con regex (degradación mínima)
    result = {}
    for key, val in re.findall(r'"(executive_summary|migration_strategy|agent_analysis|coupling_analysis)"\s*:\s*"((?:[^"\\]|\\.){0,2000})"', raw):
        result[key] = val.replace('\\n', '\n').replace('\\"', '"')
    for key, val in re.findall(r'"(coupling_score)"\s*:\s*(\d+)', raw):
        result[key] = int(val)

    if not result:
        result["executive_summary"] = "Análisis generado — respuesta JSON incompleta del modelo."

    logger.warning("JSON parcialmente recuperado con %d campos", len(result))
    return result

def _normalize_inventory(raw: str) -> str:
    """
    Elimina campos volátiles del inventario (PIDs, timestamps de proceso, uptime)
    para que el mismo servidor genere el mismo hash entre ejecuciones distintas.
    """
    lines = []
    for line in raw.splitlines():
        # Saltar líneas de ps aux con PIDs numéricos (cambian por reinicio)
        if re.match(r'^\s*\d+\s+\d+\s+[\d.]+\s+[\d.]+', line):
            continue
        # Normalizar timestamps como "Tue Apr  1 12:34:56 2026" → vacío
        line = re.sub(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\w+\s+\d+\s+[\d:]+\s+\d{4}', '', line)
        # Normalizar uptime "up X days, Y:Z"
        line = re.sub(r'up\s+\d+\s+(?:day|min|hour)[^,\n]*', 'up NORMALIZED', line)
        lines.append(line)
    return '\n'.join(lines)

def _cache_key(raw_data: str) -> str:
    normalized = _normalize_inventory(raw_data)
    return hashlib.sha256(normalized.encode()).hexdigest()

# ─── RAG — Recuperación por Similitud Semántica (Vectores) ───────────────────
def _get_embedding(text: str) -> list[float]:
    """Genera un vector para un texto dado usando amazon.titan-embed-text-v1."""
    if not text.strip():
        return []
    try:
        bedrock = _bedrock_client()
        body = json.dumps({"inputText": text[:8000]})
        response = bedrock.invoke_model(
            body=body,
            modelId="amazon.titan-embed-text-v1",
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get('body').read())
        return response_body.get('embedding', [])
    except Exception as e:
        logger.warning(f"Error al generar embedding: {e}")
        return []

def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def _rag_retrieve(inventory_text: str, top_k: int = 3) -> str:
    """
    Recupera los análisis más similares al inventario actual usando similitud coseno
    sobre Semantic Embeddings previamente guardados.
    """
    try:
        # 1. Vectorizar el texto de entrada
        query_vector = _get_embedding(inventory_text)
        if not query_vector:
            return ""

        conn, db_type = _get_conn()
        if db_type == "sqlite":
            conn.row_factory = sqlite3.Row
        
        # 2. Recuperar escaneos anteriores que tengan embedding válido
        rows = conn.execute(
            "SELECT id, hostname, bedrock_blueprint, embedding FROM scan_history "
            "WHERE bedrock_blueprint IS NOT NULL AND embedding IS NOT NULL "
            "ORDER BY timestamp DESC LIMIT 200"
        ).fetchall()
        conn.close()

        if not rows:
            return ""

        # 3. Calcular similitudes
        results = []
        for r in rows:
            rd = dict(r)
            try:
                emb_str = rd.get("embedding")
                if not emb_str: continue
                db_vector = json.loads(emb_str)
                score = _cosine_similarity(query_vector, db_vector)
                if score >= 0.50:  # Umbral de similitud semántica aceptable
                    results.append((score, rd))
            except Exception:
                continue
        
        # 4. Ordenar y seleccionar Top K
        results.sort(key=lambda x: x[0], reverse=True)
        top_matches = results[:top_k]

        parts = []
        for score, meta in top_matches:
            try:
                bp = json.loads(meta.get("bedrock_blueprint") or "{}")
            except Exception:
                bp = {}
            host = meta.get("hostname", "servidor")
            summary = bp.get("executive_summary", "")[:400]
            strategy = ""
            ms = bp.get("migration_strategy", {})
            if isinstance(ms, dict):
                strategy = ms.get("approach", "") + " — " + ms.get("rationale", "")[:200]
            elif isinstance(ms, str):
                strategy = ms[:200]
            if summary:
                parts.append(
                    f"[Análisis similar — score={score:.2f} host={host}]\n"
                    f"Resumen: {summary}\n"
                    f"Estrategia: {strategy}"
                )

        if not parts:
            return ""

        header = f"Los siguientes {len(parts)} análisis anteriores comparten alta similitud semántica. Úsalos como contexto para tu estrategia:"
        return header + "\n\n" + "\n\n".join(parts)

    except Exception as e:
        logger.warning("RAG Semantic error: %s", e)
        return ""

# ─── Agentic Prompts ──────────────────────────────────────────────────────────
_AGENT_SECURITY_PROMPT = """
Eres un CISO Senior y Penetration Tester especializado en seguridad de aplicaciones Java Enterprise.
Tu análisis alimenta directamente el plan de migración — los CVEs CRITICO que listes en sprint1_mandatory
son OBLIGATORIOS en Sprint 1. Sin excepción.

INSTRUCCIONES:
1. Analiza CADA dependencia del inventario contra CVEs conocidos (Log4Shell, Spring4Shell, Text4Shell, Struts2, etc.)
2. Evalúa los patrones de bytecode: JNDI lookups, MD5/DES, Runtime.exec, ObjectInputStream → vectores de ataque reales
3. Detecta configuraciones inseguras: puertos expuestos, credenciales hardcodeadas, TLS ausente
4. Clasifica componentes EOL con fecha exacta de fin de soporte
5. Calcula la superficie de ataque total: número de endpoints, protocolos expuestos, datos sensibles en tránsito

REGLA: Mínimo 5 security_findings. Si el inventario muestra pocas dependencias, analiza los patrones
de código (MD5, DES, Runtime.exec, hardcoded credentials) como findings adicionales.

Retorna ÚNICAMENTE JSON válido:
{{
  "security_findings": [
    {{
      "sev": "CRITICO|ALTO|MEDIO|BAJO",
      "component": "log4j-core-2.14.1.jar",
      "cve": "CVE-2021-44228",
      "cvss": 10.0,
      "description": "JNDI injection via ${jndi:ldap://...} en mensajes de log — RCE sin autenticación",
      "mitigation": "mvn versions:use-dep-version -Dincludes=org.apache.logging.log4j:log4j-core -DdepVersion=2.17.1",
      "safe_version": "2.17.1",
      "exploit_complexity": "LOW — PoC público disponible",
      "data_exposure": "Control total"
    }}
  ],
  "sprint1_mandatory": [
    "CRÍTICO [DevSecOps][0.5d]: Actualizar log4j-core 2.14.1 → 2.17.1 — elimina CVE-2021-44228 CVSS 10.0",
    "CRÍTICO [DevOps][0.25d]: Añadir -Dlog4j2.formatMsgNoLookups=true como workaround inmediato",
    "ALTO [Dev][1d]: Reemplazar MD5/DES por SHA-256/AES-256 en clases de cifrado detectadas"
  ],
  "critical_ports": [
    "8080: HTTP sin TLS — credenciales en texto plano",
    "1521: Oracle listener — expuesto a red interna sin firewall"
  ],
  "eol_components": [
    "Java 8: Oracle Extended Support hasta Dic 2030 — sin Virtual Threads, sin módulos JPMS",
    "Struts 2.x: EOL — múltiples RCE públicos (CVE-2017-5638, CVE-2018-11776)"
  ],
  "hardcoded_secrets": [
    "JDBC URL con password en texto plano detectada en bytecode — mover a AWS Secrets Manager"
  ],
  "attack_surface": "Aplicación expone X endpoints HTTP sin TLS. Bytecode contiene JNDI lookups activos (Log4Shell). Credenciales DB hardcodeadas en X clases. Deserialización insegura en Y clases (ObjectInputStream). Superficie total: ALTA.",
  "compliance_gaps": [
    "OWASP A06:2021 — Componentes vulnerables y desactualizados",
    "OWASP A02:2021 — Fallos criptográficos (MD5, DES detectados)"
  ]
}}
"""

_AGENT_JAVA_PROMPT = """
Actúas como SENIOR REVERSE ENGINEER & MIGRATION ARCHITECT.
Tu especialidad es deconstruir "cajas negras" (EAR, WAR, JAR) para extraer el ADN técnico completo sin necesidad del código fuente original.

CHAIN OF THOUGHT:
1. Analizar [BYTECODE_DATA] para detectar frameworks legacy: ¿Struts 1.x, JSF 1.2, EJB 2.x, Spring 2.x?
2. Inspeccionar descriptores XML (web.xml, ejb-jar.xml, persistence.xml) para extraer:
   - DataSources y recursos JNDI (nombres, IPs legadas).
   - Servlets, Filters y Listeners críticos.
   - Seguridad declarativa y roles.
3. Identificar dependencias "huérfanas": librerías sin soporte o con CVEs críticos embebidos.
4. Definir estrategia "App-First": cómo mover el Backend/Frontend a contenedores manteniendo enlace híbrido con la DB.

INSTRUCCIÓN CRÍTICA DE CALIDAD:
- Identifica específicamente nombres de DataSources JNDI encontrados en descriptores.
- Los sprints deben priorizar: 1) Containerización, 2) Conectividad Híbrida, 3) Refactoring JEE -> Spring Boot 3.
- La estrategia de migración debe explicar cómo desacoplar el servidor de apps (WebLogic/JBoss/WebSphere) del código.

Retorna ÚNICAMENTE JSON válido:
{{
  "reverse_engineering": {{
    "middleware_detected": "WebLogic|JBoss|WebSphere|Tomcat Legacy",
    "jndi_resources": ["nombre_datasource_1", "recurso_jndi_2"],
    "critical_xml_configs": ["web.xml: descripción", "persistence.xml: dialecto"],
    "legacy_patterns": ["EJB 2.1 Entity Beans", "Struts 1 Actions"]
  }},
  "migration_strategy": {{
    "approach": "re-architect|replatform|containerize",
    "rationale": "Justificación técnica basada en la deconstrucción del binario. Por qué específicamente este binario es apto para modernizar.",
    "target_runtime": "ECS Fargate (App Priority)",
    "target_java": "Java 21 LTS",
    "target_framework": "Spring Boot 3.3",
    "hybrid_connection_needed": true
  }},
  "sprints": {{
    "sprint_0": [
      {{"title": "Deconstrucción y Setup", "description": "Mapear recursos JNDI a variables de entorno Spring Boot", "effort": "3d", "owner": "Architect"}},
      {{"title": "Containerización Base", "description": "Crear Dockerfile multi-stage para el WAR/JAR", "effort": "2d", "owner": "DevOps"}}
    ],
    "sprint_1": [
      {{"title": "Conectividad Híbrida", "description": "Configurar VPN/DirectConnect para acceso a DB legacy desde Nube", "effort": "4d", "owner": "Platform"}}
    ],
    "sprint_2": [
      {{"title": "Refactoring Capa Datos", "description": "Migrar JDBC/EJB 2 a Spring Data JPA", "effort": "10d", "owner": "Dev"}}
    ],
    "sprint_3": [
      {{"title": "Modernización Frontend", "description": "Extraer lógica de JSPs a React/Next.js", "effort": "15d", "owner": "Dev"}}
    ]
  }},
  "quick_wins": [],
  "risk_matrix": [],
  "definition_of_done": ["App corriendo en contenedor conectada a DB legacy"]
}}
"""

_AGENT_MIGRATION_PROMPT = """
Eres un Principal Migration Lead especializado en estrategias "App-First".
Tu misión es diseñar un roadmap que modernice primero el código y la plataforma de ejecución, dejando la migración de datos para una fase posterior.

OBJETIVOS DEL ROADMAP:
1. Sprint 0-1: Establecer el "punto de entrada" en la nube (Containerización + Conectividad).
2. Priorizar el desacoplamiento de la lógica de negocio del sistema operativo antiguo (RHEL 5/Oracle Linux).
3. Asegurar que la aplicación modernizada pueda consumir servicios del legado (DB, Colas, Mainframe) de forma segura.

REGLAS DE ORO:
- No proponer migración de base de datos en los primeros 2 sprints.
- Foco en "Time-to-Value": poner el backend en la nube lo antes posible.
- Usar el stack detectado: {detected_stack} para todas las recomendaciones.
"""

_AGENT_CLOUDNATIVE_PROMPT = """
    {{"title": "Alta Latencia p99 > 2s",
      "trigger": "CloudWatch alarm TargetResponseTime > 2",
      "steps": ["kubectl top pods -l app=NOMBRE-REAL", "kubectl scale deployment/NOMBRE-REAL --replicas=5", "RDS Performance Insights: revisar slow queries"]}},
    {{"title": "OOMKilled",
      "trigger": "kubectl describe pod muestra OOMKilled",
      "steps": ["Aumentar memory limit a 768Mi en Deployment", "Verificar heap: -Xmx debe ser 75% del container limit", "jcmd 1 VM.native_memory para buscar leaks"]}}
  ],

  "refactored_snippets": [
    {{
      "class": "nombre.completo.ClaseReal del inventario",
      "issue": "antipatrón concreto que bloquea containerización",
      "before": "código JEE legacy (<10 líneas)",
      "after": "código Spring Boot 3.2 + Java 21 (<10 líneas)",
      "why": "razón técnica para containerizar"
    }}
  ],

  "deployment_commands": [
    "docker build -t NOMBRE-REAL:$(git rev-parse --short HEAD) .",
    "aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO",
    "docker push $ECR_REPO/NOMBRE-REAL:$(git rev-parse --short HEAD)",
    "terraform init && terraform apply -auto-approve",
    "docker-compose -f docker-compose.localstack.yml up -d && curl http://localhost:8080/actuator/health"
  ],

  "healthcheck_config": {{
    "liveness_probe": "GET /actuator/health/liveness — port 8080 — initialDelaySeconds 30 — periodSeconds 10 — failureThreshold 3",
    "readiness_probe": "GET /actuator/health/readiness — port 8080 — initialDelaySeconds 20 — failureThreshold 5",
    "startup_probe": "GET /actuator/health — port 8080 — failureThreshold 30 — periodSeconds 10"
  }}
}}

REGLAS CRÍTICAS:
- Dockerfile: runtime DEBE ser gcr.io/distroless/java21-debian12 — NO alpine en runtime
- localstack_compose: DEBE emular los servicios AWS reales detectados en la app
- to_be_diagram: Mermaid válido mostrando VPC/ALB/ECS/RDS/Secrets Manager con nombre real
- terraform_managed_services: DEBE incluir VPC + ALB + ECS Fargate + RDS Aurora Serverless v2
- sre_runbook: 3 runbooks operativos para los escenarios más probables post-deploy
- Todos los recursos: usar el nombre real del artefacto del inventario
"""

_AGENT_CODE_PROMPT = """
Eres un Staff Engineer Senior con 15 años de experiencia modernizando aplicaciones Java Enterprise.
ESPECIALIDAD: Refactoring profundo JEE → Spring Boot 3.x / Java 21, análisis de bytecode, deuda técnica.
TARGET: Spring Boot 3.2+, Java 21 LTS, Jakarta EE 10 (javax.* → jakarta.*), Virtual Threads (Project Loom).

INSTRUCCIÓN CRÍTICA: Analiza CADA clase y patrón del [BYTECODE_DATA]. Identifica:
- Servlets sin migrar a @RestController
- EJB Session Beans sin migrar a @Service/@Transactional
- JNDI lookups sin migrar a @Value/@ConfigurationProperties
- SQL hardcodeado sin migrar a Spring Data JPA / @Query
- Acoplamiento a servidor de aplicaciones (WebLogic/JBoss/WAS APIs)
- Uso de javax.* (deprecated en Spring Boot 3.x, debe ser jakarta.*)
- Anti-patrones: God Class, Feature Envy, Singleton con estado mutable
- Threads manuales que deben reemplazarse con Virtual Threads

Retorna ÚNICAMENTE JSON válido:
{{
  "agent_analysis": "Análisis técnico en 5+ párrafos detallados: (1) Stack exacto detectado con versiones del bytecode y descriptores XML, (2) Inventario completo de antipatrones JEE con clases concretas y severidad, (3) Impacto del acoplamiento al servidor de aplicaciones en la containerización — qué específicamente romperá en Docker, (4) Deuda técnica acumulada: cálculo de horas técnicas y riesgo de regresión por módulo, (5) Ruta de refactoring priorizada: orden exacto de transformaciones con justificación técnica y dependencias entre tareas",
  "code_remediation": [
    {{"file": "com.empresa.paquete.ClaseReal (nombre REAL del bytecode, nunca placeholder)",
      "issue": "antipatrón específico: tipo JEE detectado + qué rompe en containerización",
      "action": "cambio exacto requerido para Spring Boot 3.x — importaciones, anotaciones, método",
      "before": "código legacy real o representativo (4-8 líneas)",
      "after": "código Spring Boot 3.2 + Java 21 correcto (4-8 líneas)",
      "effort": "Xh",
      "priority": "P1-Crítico|P2-Alto|P3-Medio",
      "benefit": "impacto concreto: CVE eliminado / portabilidad ganada / rendimiento mejorado"}}
  ],
  "current_architecture": {{
    "coupling_score": 8,
    "coupling_analysis": "análisis detallado del acoplamiento con nombres de CADA componente del inventario: EJBs, Servlets, MBeans, JNDI resources y su interdependencia",
    "pain_points": [
      "bloqueador concreto 1 que impide containerización directa con componente real",
      "bloqueador concreto 2 con impacto en CI/CD",
      "deuda técnica 3 con coste de mantenimiento cuantificado"
    ],
    "containerization_blockers": [
      {{"component": "nombre real", "blocker": "descripción técnica exacta", "resolution": "cómo resolverlo en Spring Boot 3.x"}}
    ]
  }},
  "tech_debt_summary": {{
    "critical_items": 0,
    "high_items": 0,
    "estimated_refactor_days": 0,
    "javax_to_jakarta_count": 0,
    "hardcoded_configs_count": 0
  }}
}}

REGLAS:
- MÍNIMO 6 ítems en code_remediation — si el bytecode tiene pocas clases visibles, analiza los descriptores XML (web.xml, ejb-jar.xml, persistence.xml) y las dependencias.
- Clases REALES del [BYTECODE_DATA] o [INFRA_AS_IS]. Si no hay clases visibles, usa patrones deducidos de las dependencias y tipo de artefacto.
- Migración javax.* → jakarta.*: en Spring Boot 3.x el namespace cambió completamente — citar cada uno encontrado.
- Virtual Threads: cualquier ExecutorService/Thread manual debe marcarse como candidato.
- NUNCA uses "ClaseEjemplo", "MiServlet", "com.empresa.Ejemplo" — siempre nombres derivados del inventario real.
"""

_AGENT_BUSINESS_PROMPT = """
Eres un Cloud FinOps Architect Senior y Technology Risk Advisor con 15 años de experiencia.
Especializacion: análisis TCO/ROI de modernización legacy → AWS, modelado financiero de riesgo técnico.

INSTRUCCIÓN CRÍTICA: Personaliza TODOS los números usando el inventario real:
- CVEs detectados → riesgo de breach según IBM Cost of Data Breach 2024 ($4.88M promedio global)
- Versiones EoL (Java 8, WebLogic 12, Struts 1.x) → costo de licencia/soporte fuera de ciclo
- Número de servidores/hosts → multiplicar costos de infraestructura
- Stack tecnológico → estimar sizing AWS correcto (ECS cpu/memory, RDS class)
- Si hay BD detectada → incluir costo de RDS. Si no hay BD → NO incluir RDS en tco_aws.

Retorna ÚNICAMENTE JSON válido:
{{
  "risk_score": 8.5,
  "risk_rationale": "justificación detallada del score: CVEs críticos con CVSS score, versiones EoL exactas detectadas, tiempo sin parchear estimado, exposición de datos detectada en inventario",

  "tco_legacy": {{
    "annual_licensing": 45000,
    "annual_licensing_detail": "desglose: WebLogic Enterprise $35k + Oracle DB $10k (o lo que aplique del inventario)",
    "annual_labor_maintenance": 80000,
    "annual_labor_detail": "2 FTE senior Java ($60k) + 1 DBA part-time ($20k) — ajustar según stack detectado",
    "annual_security_incidents_risk": 120000,
    "annual_security_detail": "CVE-XXXX CVSS 9.8: prob 15% × $800k breach = $120k expected loss anual",
    "annual_downtime_cost": 15000,
    "annual_downtime_detail": "SLA 99.5% = 43.8h downtime × $342/h revenue impact estimado",
    "annual_compliance_risk": 25000,
    "annual_compliance_detail": "multa GDPR/SOC2 por dependencias sin parchear: estimado conservador",
    "total_annual": 285000,
    "five_year_total": 1425000
  }},

  "tco_aws": {{
    "ecs_fargate_monthly": 180,
    "ecs_fargate_detail": "2 tasks × 0.5vCPU/1GB × 730h = $180/mes (ajustar si app grande)",
    "rds_aurora_serverless_monthly": 95,
    "rds_detail": "Aurora Serverless v2 0.5-4 ACU — solo incluir si hay BD detectada en inventario",
    "alb_monthly": 22,
    "secrets_manager_monthly": 10,
    "cloudwatch_monthly": 25,
    "ecr_monthly": 5,
    "total_monthly": 337,
    "total_annual": 4044,
    "migration_one_time_cost": 85000,
    "migration_cost_detail": "Sprint 0-3 (8 semanas): 2 devs senior + 1 DevOps × 8 semanas × tarifas mercado",
    "five_year_total": 105220
  }},

  "roi": {{
    "annual_saving": 280956,
    "five_year_saving": 1319780,
    "payback_months": 4,
    "roi_pct": 1253,
    "irr_5yr": "312%",
    "npv_5yr": 980000
  }},

  "c_suite_summary": "3-4 oraciones ejecutivas para CEO/CTO/CFO: (1) riesgo técnico-financiero actual cuantificado con CVEs reales, (2) ahorro proyectado a 5 años con payback concreto, (3) riesgo de NO migrar (costo creciente de mantenimiento + riesgo de breach), (4) recomendación de acción inmediata con fecha sugerida de inicio",

  "cost_drivers": [
    {{"driver": "CVE específico del inventario o versión EoL real",
      "annual_risk_exposure": 200000,
      "probability": "15%",
      "expected_loss": 30000,
      "note": "fuente: IBM Cost of Data Breach 2024 / NVD CVSS score"}}
  ],

  "financial_assumptions": [
    "Tarifa senior Java developer: $85/h (mercado LATAM)",
    "Revenue impact downtime: estimado según tipo de aplicación",
    "Tipo de cambio: USD — ajustar si inventario muestra moneda local",
    "Breach cost base: IBM 2024 $4.88M × factor industria"
  ],

  "aws_sizing_rationale": "explicación técnica del sizing elegido: por qué esas instancias/tasks/ACU basado en el inventario — número de usuarios, clases, dependencias, carga estimada"
}}

REGLAS:
- Si el inventario NO tiene base de datos detectada: rds_aurora_serverless_monthly = 0 y aclararlo en rds_detail.
- Si el inventario tiene múltiples servicios/hosts: multiplicar los costos apropiadamente.
- Los CVEs en cost_drivers deben ser los mismos que aparecen en el inventario, no genéricos.
- Nunca inventes CVEs que no estén en el inventario — si no hay CVEs, usa versiones EoL como risk drivers.
- c_suite_summary: idioma ejecutivo, sin jerga técnica, con números concretos.

CALIBRACIÓN DE COSTOS (evitar inflación):
- annual_licensing: solo incluir licencias reales detectadas en el inventario (WebLogic, Oracle DB, IBM MQ, etc.). Si el stack es open-source (Tomcat, PostgreSQL, etc.) este valor debe ser 0 o muy bajo (soporte comercial opcional).
- annual_labor_maintenance: 1-2 FTE para apps medianas (1 servicio/host). Tarifa senior LATAM ~$40-60k/año. NO asumir 3+ FTE sin evidencia de complejidad alta en el inventario.
- annual_security_incidents_risk: usar probabilidad REALISTA según número de CVEs críticos:
    * 0-2 CVEs críticos → probabilidad 3-5%, breach estimado $200k-$500k (empresa mediana)
    * 3-5 CVEs críticos → probabilidad 8-12%, breach estimado $400k-$800k
    * 6+ CVEs críticos → probabilidad 15-20%, breach estimado $600k-$1.2M
  NO usar el promedio IBM $4.88M (es de grandes enterprises con 100k+ registros expuestos).
- annual_downtime_cost: estimar conservador — SLA 99.5% = 43h/año. Revenue impact: $100-$500/h para apps internas, $500-$2000/h para apps de cara al cliente. Sin evidencia del tipo de app → usar $200/h.
- annual_compliance_risk: incluir solo si el inventario evidencia datos regulados (PII, PCI, HIPAA). Sin evidencia → 0.
- total_annual: suma real de los campos anteriores. NO inflar para "hacer más atractivo el ROI".
"""

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

# ─── Background Job (Bedrock Async — Agentic + RAG) ─────────────────────────
def _call_agent(bedrock, model_id: str, max_tokens: int, system_prompt: str, user_msg: str) -> dict:
    """Llama a un agente específico. Lanza excepción si falla."""
    resp = bedrock.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        system=[{"text": system_prompt}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0}
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return _parse_json_response(text)

def _run_bedrock_job(job_id: str, raw_data: str, hostname: str, data_hash: str, industry: str = "general"):
    """
    Análisis agéntico paralelo con RAG:
    1. Recupera contexto de análisis similares (RAG TF-IDF)
    2. Lanza 3 agentes especializados en paralelo (Security, Migration, Code)
    3. Fusiona resultados en el mismo formato JSON que usaba el sistema monolítico
    4. Fallback: si los agentes fallan, usa el prompt monolítico original
    """
    # Iniciar estado en DB
    _update_job_status(job_id, "running", "Recuperando contexto RAG...")

    inventory = raw_data[:MAX_CHARS] + ("\n...[TRUNCADO]..." if len(raw_data) > MAX_CHARS else "")
    knowledge  = load_knowledge()
    rag_ctx    = _rag_retrieve(raw_data)
    industry_ctx = INDUSTRY_CONTEXT.get(industry, INDUSTRY_CONTEXT["general"])

    # Prefijo común a todos los agentes: industria + knowledge + RAG
    _common_ctx = (
        f"## INDUSTRIA: {industry_ctx}\n\n"
        f"## KNOWLEDGE BASE:\n{knowledge}\n\n"
        + (f"## ANÁLISIS SIMILARES (RAG):\n{rag_ctx}\n\n" if rag_ctx else "")
    )

    bedrock     = _bedrock_client()
    model       = MODEL_CHAIN[0]   # Agentes usan Nova Lite primero
    mid, mlabel = model["id"], model["label"]
    last_error  = None

    # ── Intento 1: 3 agentes en paralelo ─────────────────────────────────────
    _update_job_status(job_id, "running", "Ejecutando 3 agentes en paralelo...")
    logger.info("[Job %s] Iniciando análisis agéntico paralelo en %s", job_id[:8], mid)

    # Detectar si el inventario proviene de un artefacto Java o de otro lenguaje
    detected_stack = "General"
    low_data = raw_data.lower()
    if any(k in low_data for k in (".jar", ".war", ".ear", "artifact_type: application/java", "clases java")):
        detected_stack = "Java"
    elif any(k in low_data for k in ("package.json", "node_modules", "javascript", "typescript")):
        detected_stack = "Node.js"
    elif any(k in low_data for k in ("requirements.txt", "pip ", "python", "pyproject.toml")):
        detected_stack = "Python"
    elif any(k in low_data for k in ("composer.json", "<?php", "php-fpm")):
        detected_stack = "PHP"
    elif any(k in low_data for k in (".csproj", ".sln", "nuget", ".net core")):
        detected_stack = ".NET"
    elif any(k in low_data for k in ("go.mod", "go.sum", " golang ")):
        detected_stack = "Go"

    is_java_artifact = (detected_stack == "Java")
    
    # Contexto mejorado con el stack detectado
    stack_ctx = f"## STACK DETECTADO: {detected_stack}\n\n"

    sec_result  = {}
    mig_result  = {}
    code_result = {}
    java_result = {}
    cn_result   = {}   # CloudNative agent
    biz_result      = {}   # Business/FinOps agent
    cost_opt_result = {}   # CostOptimization agent
    agents_ok       = False

    try:
        # ── Estructurar el mensaje con secciones etiquetadas
        def _build_structured_msg(inv: str) -> str:
            sections = {"BYTECODE_DATA": [], "DEPENDENCIES": [], "INFRA_AS_IS": [], "OTHER": []}
            current = "INFRA_AS_IS"
            for line in inv.splitlines():
                ls = line.strip()
                if any(k in ls for k in ("=== CLASES", "=== RESUMEN DE CLASES", "=== ANTIPATRONES", "=== SQL", "=== XML")):
                    current = "BYTECODE_DATA"
                elif any(k in ls for k in ("=== DEPENDENCIAS", "=== CVEs DETECTADOS", "=== COMPOSER", "=== NPM")):
                    current = "DEPENDENCIES"
                elif ls.startswith("==="):
                    current = "INFRA_AS_IS"
                sections[current].append(line)
            parts = []
            if sections["INFRA_AS_IS"]:
                parts.append("[INFRA_AS_IS]\n" + "\n".join(sections["INFRA_AS_IS"]))
            if sections["DEPENDENCIES"]:
                parts.append("[DEPENDENCIES]\n" + "\n".join(sections["DEPENDENCIES"]))
            if sections["BYTECODE_DATA"]:
                parts.append("[DEEP_DISCOVERY_DATA]\n" + "\n".join(sections["BYTECODE_DATA"]))
            if sections["OTHER"]:
                parts.append("[OTHER]\n" + "\n".join(sections["OTHER"]))
            # BUSINESS_GOALS — con prioridad App-First
            parts.append(
                "[STRATEGIC_GOALS]\n"
                "- PRIORIDAD: App-First (Migrar Backend/Frontend a Nube manteniendo DB legacy)\n"
                "- Maximizar ROI: reducir TCO en >70% moviendo la ejecución a Managed Containers\n"
                "- Seguridad: corregir vulnerabilidades críticas en la capa de aplicación primero\n"
                "- Observabilidad: instrumentación completa desde el día 1"
            )
            return "\n\n".join(parts) if parts else inv

        structured_inv = _build_structured_msg(inventory)
        inv_msg = f"Inventario técnico estructurado:\n\n{structured_inv}"

        def run_security():
            return _call_agent(bedrock, mid, 3500,
                               _common_ctx + stack_ctx + _AGENT_SECURITY_PROMPT, inv_msg)

        def run_migration():
            ctx = inv_msg
            if sec_result:
                ctx += f"\n\n[SECURITY_FINDINGS]\n{json.dumps(sec_result, ensure_ascii=False)[:2000]}"
            return _call_agent(bedrock, mid, 4096,
                               _common_ctx + stack_ctx.format(detected_stack=detected_stack) + _AGENT_MIGRATION_PROMPT.format(detected_stack=detected_stack), ctx)

        def run_code():
            return _call_agent(bedrock, mid, 3500,
                               _common_ctx + _AGENT_CODE_PROMPT.format(detected_stack=detected_stack), inv_msg)

        def run_java():
            return _call_agent(bedrock, mid, 5000,
                               _common_ctx + stack_ctx + _AGENT_JAVA_PROMPT, inv_msg)

        def run_cloudnative():
            return _call_agent(bedrock, mid, 5000,
                               _common_ctx + _AGENT_CLOUDNATIVE_PROMPT.format(detected_stack=detected_stack), inv_msg)

        def run_business():
            return _call_agent(bedrock, mid, 3500,
                               _common_ctx + stack_ctx + _AGENT_BUSINESS_PROMPT, inv_msg)

        def run_cost_optimization():
            ctx = inv_msg
            if biz_result:
                ctx += f"\n\n[BUSINESS_AGENT_TCO]\n{json.dumps(biz_result, ensure_ascii=False)[:3000]}"
            return _call_agent(bedrock, mid, 3072,
                               _common_ctx + stack_ctx + _AGENT_COST_OPT_PROMPT, ctx)

        # Etapa 1a: Security + Code + Business en paralelo (+ ReverseEngineer/CN si es Java)
        n_agents = 6 if is_java_artifact else 4
        _update_job_status(job_id, "running", f"Ejecutando orquestación multi-agente ({detected_stack})...")

        with ThreadPoolExecutor(max_workers=4) as ex:
            f_sec  = ex.submit(run_security)
            f_code = ex.submit(run_code)
            f_biz  = ex.submit(run_business)
            f_java = ex.submit(run_java)        if is_java_artifact else None
            f_cn   = ex.submit(run_cloudnative) # CloudNative corre siempre para generar Dockerfiles

            futures_map = {
                f_sec:  ("sec",  sec_result),
                f_code: ("code", code_result),
                f_biz:  ("biz",  biz_result),
            }
            if f_java: futures_map[f_java] = ("java",        java_result)
            if f_cn:   futures_map[f_cn]   = ("cloudnative", cn_result)

            for fut in as_completed(futures_map):
                label_key, target = futures_map[fut]
                try:
                    res = fut.result()
                    target.update(res)
                except Exception as e:
                    logger.warning("[Job %s] Agente '%s' falló: %s", job_id[:8], label_key, e)

        # Status después del bloque (fuera del ThreadPoolExecutor para evitar bloqueos DB)
        _update_job_status(job_id, "running",
                           f"Security/Code{'/ Java' if is_java_artifact else ''} completados...")

        # Etapa 1b: Migration + CostOptimization en paralelo (Stage 1 ya completado)
        _update_job_status(job_id, "running", "Stage 2 — Migration + CostOptimization...")
        with ThreadPoolExecutor(max_workers=2) as ex2:
            f_mig  = ex2.submit(run_migration)
            f_cost = ex2.submit(run_cost_optimization)
            stage2_map = {f_mig: "migration", f_cost: "cost_opt"}
            for fut in as_completed(stage2_map):
                lbl = stage2_map[fut]
                try:
                    res = fut.result()
                    if lbl == "migration":
                        mig_result.update(res)
                    else:
                        cost_opt_result.update(res)
                except Exception as e:
                    logger.warning("[Job %s] Agente '%s' falló: %s", job_id[:8], lbl, e)

        agents_ok = bool(sec_result or mig_result or code_result or java_result)

    except Exception as e:
        last_error = str(e)
        logger.warning("[Job %s] Fallo en bloque agéntico: %s", job_id[:8], e)

    # ── Fusión de resultados agénticos ───────────────────────────────────────
    if agents_ok:
        # Construir executive_summary — Java tiene prioridad si es artefacto
        top_findings = sec_result.get("security_findings", [])
        attack   = sec_result.get("attack_surface", "")
        eol_list = sec_result.get("eol_components", [])
        if is_java_artifact and java_result.get("executive_summary"):
            exec_summary = java_result["executive_summary"]
        else:
            exec_summary = (
                f"Sistema analizado con {len(top_findings)} hallazgos de seguridad. "
                + (f"Superficie de ataque: {attack} " if attack else "")
                + (f"Componentes EoL: {', '.join(eol_list[:3])}." if eol_list else "")
            ) or code_result.get("agent_analysis", "")[:300]

        ai_response = {
            "executive_summary":  exec_summary,
            "agent_analysis":     java_result.get("agent_analysis") or code_result.get("agent_analysis", ""),
            "migration_strategy": java_result.get("migration_strategy") or mig_result.get("migration_strategy", {}),
            "sprints":            java_result.get("sprints") or mig_result.get("sprints", {}),
            "quick_wins":         java_result.get("quick_wins") or mig_result.get("quick_wins", []),
            "risk_matrix":        java_result.get("risk_matrix") or mig_result.get("risk_matrix", []),
            "code_remediation":   java_result.get("code_remediation") or code_result.get("code_remediation", []),
            "current_architecture": code_result.get("current_architecture", {}),
            # Metadatos extra de los agentes
            "security_findings":   sec_result.get("security_findings", []),
            "critical_ports":      sec_result.get("critical_ports", []),
            "eol_components":      sec_result.get("eol_components", []),
            # Datos específicos Java (solo cuando aplica)
            **({"java_findings":       java_result.get("java_findings", []),
                "dependency_analysis": java_result.get("dependency_analysis", {}),
                "containerization":    java_result.get("containerization", {}),
                # CloudNative agent — artefactos de migración listos para desplegar
                "cloudnative": {
                    "twelve_factor_violations":  cn_result.get("twelve_factor_violations", []),
                    "blocking_issues":            cn_result.get("blocking_issues", []),
                    "dockerfile":                 cn_result.get("dockerfile", ""),
                    "docker_compose":             cn_result.get("docker_compose", ""),
                    "k8s_deployment":             cn_result.get("k8s_deployment", ""),
                    "k8s_service":                cn_result.get("k8s_service", ""),
                    "k8s_hpa":                    cn_result.get("k8s_hpa", ""),
                    "terraform_managed_services": cn_result.get("terraform_managed_services", ""),
                    "refactored_snippets":        cn_result.get("refactored_snippets", []),
                    "deployment_commands":        cn_result.get("deployment_commands", []),
                    "healthcheck_config":         cn_result.get("healthcheck_config", {}),
                    "to_be_diagram":              cn_result.get("to_be_diagram", ""),
                    "localstack_compose":         cn_result.get("localstack_compose", ""),
                    "sre_runbook":                cn_result.get("sre_runbook", []),
                },
               } if is_java_artifact else {}),
            # Business/FinOps agent (siempre)
            "business": {
                "risk_score":       biz_result.get("risk_score"),
                "risk_rationale":   biz_result.get("risk_rationale", ""),
                "tco_legacy":       biz_result.get("tco_legacy", {}),
                "tco_aws":          biz_result.get("tco_aws", {}),
                "roi":              biz_result.get("roi", {}),
                "c_suite_summary":  biz_result.get("c_suite_summary", ""),
                "cost_drivers":     biz_result.get("cost_drivers", []),
            },
            # CostOptimization agent
            "cost_optimization": {
                "multicloud":       cost_opt_result.get("multicloud", {}),
                "aws_optimization": cost_opt_result.get("aws_optimization", {}),
                "rightsizing":      cost_opt_result.get("rightsizing", {}),
                "sprint_cost":      cost_opt_result.get("sprint_cost", {}),
            },
            "detected_stack":      detected_stack,
            "reverse_engineering": java_result.get("reverse_engineering", {}),
            "_analysis_method":    "agentic_parallel" + ("_java" if is_java_artifact else ""),
            "_rag_used":           bool(rag_ctx),
        }
        logger.info("[Job %s] Agéntico OK — sec=%d mig=%d code=%d biz=%s rag=%s",
                    job_id[:8], len(top_findings),
                    len(mig_result.get("sprints", {})),
                    len(code_result.get("code_remediation", [])),
                    bool(biz_result),
                    bool(rag_ctx))

    else:
        # ── Fallback: prompt monolítico original ─────────────────────────────
        _update_job_status(job_id, "running", "Fallback a análisis monolítico...")
        logger.warning("[Job %s] Agéntico falló — usando prompt monolítico", job_id[:8])
        ai_response = None
        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            knowledge_text=knowledge + ("\n\nRAG:\n" + rag_ctx if rag_ctx else ""),
            industry_context=industry_ctx
        )
        for model_fb in MODEL_CHAIN:
            mid_fb = model_fb["id"]
            _update_job_status(job_id, "running", f"Consultando {model_fb['label']} (fallback)...")
            try:
                resp = bedrock.converse(
                    modelId=mid_fb,
                    messages=[{"role": "user", "content": [{"text": f"Inventario:\n{inventory}"}]}],
                    system=[{"text": prompt}],
                    inferenceConfig={"maxTokens": model_fb["maxTokens"], "temperature": 0.0}
                )
                text = resp["output"]["message"]["content"][0]["text"]
                ai_response = _parse_json_response(text)
                ai_response["_analysis_method"] = "monolithic_fallback"
                ai_response["_rag_used"] = bool(rag_ctx)
                mid = mid_fb
                break
            except Exception as e:
                last_error = str(e)
                logger.warning("[Job %s] Fallback %s falló: %s", job_id[:8], mid_fb, e)

        if not ai_response:
            _update_job_status(job_id, "failed", "Todos los modelos fallaron", error=last_error)
            logger.error("[Job %s] Todos fallaron. Último error: %s", job_id[:8], last_error)
            return

    # ── Guardar resultado ─────────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    prev_row = _find_scan_by_hostname(hostname, within_hours=876600)
    prev_scan_id = prev_row["id"] if prev_row else None
    
    _update_job_status(job_id, "running", "Generando vector semántico...")
    try:
        embedding_vec = _get_embedding(inventory)
    except Exception as e:
        logger.warning("No se pudo generar embedding en background: %s", e)
        embedding_vec = None

    _save_scan(scan_id, hostname, raw_data, ai_response, mid, data_hash, prev_scan_id, embedding=embedding_vec)
    ANALYSIS_CACHE[data_hash] = {
        "scan_id": scan_id, "ai_content": ai_response,
        "model_used": mid, "timestamp": datetime.now().isoformat()
    }
    _update_job_status(job_id, "completed", f"Completado ({ai_response.get('_analysis_method','agentic')})",
                       ai_content=ai_response, scan_id=scan_id, model_used=mid)
    logger.info("[Job %s] Guardado scan %s", job_id[:8], scan_id[:8])

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/system/rag/backfill")
async def rag_backfill(background_tasks: BackgroundTasks, _user: str = Depends(verify_auth)):
    """Genera en background los embeddings para históricos previos sin vector semántico."""
    def _do_backfill():
        conn, db_type = _get_conn()
        if db_type == "sqlite":
            conn.row_factory = sqlite3.Row
        ph = _ph(db_type)
        
        rows = conn.execute("SELECT id, raw_inventory FROM scan_history WHERE embedding IS NULL").fetchall()
        logger.info(f"Iniciando backfill de RAG para {len(rows)} scans...")
        for row in rows:
            scan_id = dict(row)["id"]
            raw_inv = dict(row)["raw_inventory"]
            try:
                vec = _get_embedding(raw_inv)
                if vec:
                    conn.execute(f"UPDATE scan_history SET embedding = {ph} WHERE id = {ph}", (json.dumps(vec), scan_id))
                    conn.commit()
            except Exception as e:
                logger.warning(f"Falla backfill RAG para scan {scan_id}: {e}")
        conn.close()
        logger.info("Backfill RAG completado.")

    background_tasks.add_task(_do_backfill)
    return {"status": "ok", "message": "Backfill RAG iniciado en background."}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "5.0.0", "db": "postgresql" if DATABASE_URL else "sqlite",
            "features": ["rag", "agentic", "diff", "readiness", "portfolio", "runbook"]}

@app.post("/auth/login")
async def login(body: LoginRequest):
    if USERS_DB.get(body.username) != body.password:
        raise HTTPException(401, "Credenciales incorrectas")
    token = pyjwt.encode(
        {"sub": body.username, "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_H)},
        JWT_SECRET, algorithm=JWT_ALGORITHM
    )
    logger.info("Login exitoso", extra={"user": body.username})
    return {"access_token": token, "token_type": "bearer", "expires_in": JWT_EXPIRE_H * 3600}

@app.post("/analyze")
@limiter.limit("100/hour;10/minute")
def analyze_legacy(
    request: Request,
    body: AnalysisRequest,
    background_tasks: BackgroundTasks,
    _user: str = Depends(verify_auth)
):
    raw_data = body.raw_data
    industry = body.industry if body.industry in INDUSTRY_CONTEXT else "general"
    force    = getattr(body, "force_reanalyze", False)
    m = re.search(r"HOSTNAME:\s*([^\n]+)", raw_data, re.IGNORECASE)
    hostname = m.group(1).strip() if m else "remote-host"
    data_hash = _cache_key(raw_data + "|industry=" + industry)

    def _cached_response(source: str, scan_id: str, model_used: str, ai: dict):
        ANALYSIS_CACHE[data_hash] = {
            "scan_id": scan_id, "ai_content": ai,
            "model_used": model_used, "timestamp": datetime.now().isoformat()
        }
        return {"status": "completed", "method": source, "scan_id": scan_id,
                "model_used": model_used, "ai_content": ai}

    if not force:
        # 1. Cache en memoria (más rápido)
        if data_hash in ANALYSIS_CACHE:
            c = ANALYSIS_CACHE[data_hash]
            logger.info("Cache hit (memoria): %s", data_hash[:8])
            return {"status": "completed", "method": "cache",
                    "scan_id": c["scan_id"], "model_used": c["model_used"],
                    "ai_content": c["ai_content"]}

        # 2. Cache en DB — mismo hash normalizado
        db_row = _find_cached_scan(data_hash)
        if db_row:
            ai = json.loads(db_row["bedrock_blueprint"]) if isinstance(db_row["bedrock_blueprint"], str) else db_row["bedrock_blueprint"]
            logger.info("Cache hit (DB hash): %s", data_hash[:8])
            return _cached_response("cache_db", db_row["id"], db_row.get("model_used", "cached"), ai)

        # 3. Deduplicación por hostname (últimas 24h) — garantiza informe consistente
        #    aunque el inventario tenga pequeñas diferencias entre ejecuciones
        host_row = _find_scan_by_hostname(hostname, within_hours=24)
        if host_row:
            ai = json.loads(host_row["bedrock_blueprint"]) if isinstance(host_row["bedrock_blueprint"], str) else host_row["bedrock_blueprint"]
            logger.info("Cache hit (hostname '%s', %s): reutilizando análisis previo", hostname, host_row["timestamp"][:16])
            return _cached_response("cache_hostname", host_row["id"], host_row.get("model_used", "cached"), ai)

    # 4. Nuevo job asíncrono
    job_id = str(uuid.uuid4())
    # Create via DB upsert
    _update_job_status(job_id, "pending", "En cola...")
    
    background_tasks.add_task(_run_bedrock_job, job_id, raw_data, hostname, data_hash, industry)
    logger.info("Job creado: %s para host '%s' [industria: %s, force=%s]", job_id[:8], hostname, industry, force)
    return {"status": "pending", "method": "async", "job_id": job_id}

@app.get("/status/{job_id}")
async def job_status(job_id: str, _user: str = Depends(verify_auth)):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado o expirado")
    return job

from fastapi.responses import StreamingResponse
import asyncio

@app.get("/stream/{job_id}")
async def job_stream(job_id: str, _user: str = Depends(verify_auth)):
    """Streaming de Server-Sent Events (SSE) para progreso en vivo, leyendo de memoria o BD."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado o expirado")
        
    async def event_generator():
        last_msg = ""
        last_status = ""
        while True:
            job = _get_job(job_id)
            if not job:
                yield "data: {\"status\": \"error\", \"message\": \"Job vanished\"}\n\n"
                break
            
            current_msg = job.get("message", "")
            current_status = job.get("status", "pending")
            
            if current_status != last_status or current_msg != last_msg:
                payload = {
                    "status": current_status,
                    "message": current_msg,
                    "model_used": job.get("model_used")
                }
                if current_status in ["completed", "failed"]:
                    payload["scan_id"] = job.get("scan_id")
                    payload["error"] = job.get("error")
                    payload["ai_content"] = job.get("ai_content")
                
                yield f"data: {json.dumps(payload)}\n\n"
                last_msg = current_msg
                last_status = current_status
                
            if current_status in ["completed", "failed"]:
                break
            await asyncio.sleep(0.5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/history")
async def get_history(_user: str = Depends(verify_auth)):
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, hostname, timestamp, model_used FROM scan_history ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/history/{scan_id}")
async def get_history_item(scan_id: str, _user: str = Depends(verify_auth)):
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(f"SELECT * FROM scan_history WHERE id = {ph}", (scan_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Scan no encontrado")
    data = dict(row)
    data["bedrock_blueprint"] = json.loads(data["bedrock_blueprint"])
    return data

# ─── Collect Background Job ───────────────────────────────────────────────────
def _run_collect_job(task_id: str, hostname: str, port: int, username: str, password: str, private_key_str: str):
    """Ejecuta la colección SSH en background. Actualiza COLLECT_JOBS en tiempo real."""
    COLLECT_JOBS[task_id]["status"] = "running"
    COLLECT_JOBS[task_id]["message"] = f"Conectando a {hostname}..."

    client = None
    try:
        client = _ssh_connect(hostname, port, username, password, private_key_str)
        COLLECT_JOBS[task_id]["message"] = "Ejecutando collector.sh en el servidor..."
        logger.info("[Collect %s] SSH conectado a %s", task_id[:8], hostname)

        stdin, stdout, stderr = client.exec_command(COLLECTOR_SCRIPT, timeout=300, get_pty=True)
        stdout.channel.settimeout(300)

        chunks = []
        while True:
            try:
                chunk = stdout.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                chunks.append(text)
                current = "".join(chunks)
                COLLECT_JOBS[task_id]["output"] = current
                COLLECT_JOBS[task_id]["lines"] = current.count("\n")
            except Exception:
                break

        full_output = "".join(chunks)
        client.close()

        COLLECT_JOBS[task_id].update({
            "status": "completed",
            "message": "Recolección completada",
            "output": full_output,
            "lines_collected": full_output.count("\n")
        })
        logger.info("[Collect %s] OK — %d líneas de %s", task_id[:8], full_output.count("\n"), hostname)

    except paramiko.AuthenticationException:
        if client: client.close()
        msg = "Autenticación rechazada."
        if username == "root":
            msg += " Muchos servidores prohíben login root por contraseña (usa .pem)."
        COLLECT_JOBS[task_id].update({"status": "failed", "error": msg, "message": msg})
    except socket.gaierror:
        if client: client.close()
        msg = "Error de DNS: No se pudo resolver el hostname. Verifica que el nombre sea correcto o intenta usando la IP."
        COLLECT_JOBS[task_id].update({"status": "failed", "error": msg, "message": msg})
    except (socket.timeout, paramiko.ssh_exception.NoValidConnectionsError) as e:
        if client: client.close()
        COLLECT_JOBS[task_id].update({"status": "failed", "error": f"Conexión fallida: {e}", "message": f"Timeout: {e}"})
    except Exception as e:
        if client: client.close()
        COLLECT_JOBS[task_id].update({"status": "failed", "error": str(e), "message": f"Error: {e}"})


# ─── Hostname Validation ──────────────────────────────────────────────────────
def _validate_hostname(hostname: str):
    if not hostname or len(hostname) > 255:
        return False, "Longitud de hostname inválida"
    lo = hostname.lower()
    if lo in ("127.0.0.1", "localhost", "0.0.0.0") or lo.startswith("169.254."):
        return False, "Acceso a localhost o metadata services prohibido (SSRF)"
    if not re.match(r"^[a-zA-Z0-9.\-]+$", hostname):
        return False, "Formato de hostname inválido"
    return True, "OK"

def _ssh_connect(hostname: str, port: int, username: str, password: str, private_key_str: str) -> paramiko.SSHClient:
    """Crea y retorna un SSHClient ya conectado. Lanza excepción en caso de falla."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = None
    if private_key_str:
        key_stream = io.StringIO(private_key_str)
        pw = password or None
        for cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
            try:
                key_stream.seek(0)
                pkey = cls.from_private_key(key_stream, password=pw)
                break
            except Exception:
                pass
    client.connect(
        hostname=hostname, port=port, username=username,
        password=password if not pkey else None,
        pkey=pkey, timeout=20,
        allow_agent=False, look_for_keys=False,
        banner_timeout=200, auth_timeout=30
    )
    return client

def _sanitize(value, max_len=255) -> str:
    return str(value).strip()[:max_len] if value else ""

# ─── Collector Script ─────────────────────────────────────────────────────────
def _load_collector() -> str:
    for path in [Path(__file__).parent.parent / "collector.sh", Path("collector.sh")]:
        if path.exists():
            return path.read_text(encoding="utf-8")
    logger.warning("collector.sh no encontrado")
    return "echo 'collector.sh no encontrado'"

COLLECTOR_SCRIPT = _load_collector()

@app.post("/collect")
@limiter.limit("50/hour;5/minute")
def collect_data(request: Request, body: CollectRequest, background_tasks: BackgroundTasks, _user: str = Depends(verify_auth)):
    hostname = _sanitize(body.hostname)
    username = _sanitize(body.username)
    valid, msg = _validate_hostname(hostname)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Hostname inválido: {msg}")
    if not username:
        raise HTTPException(status_code=400, detail="Se requiere usuario SSH")

    # Validar llave privada inmediatamente (feedback instantáneo al usuario)
    if body.private_key:
        pkey = None
        key_stream = io.StringIO(body.private_key)
        pw = body.password or None
        for cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
            try:
                key_stream.seek(0)
                pkey = cls.from_private_key(key_stream, password=pw)
                break
            except Exception:
                pass
        if not pkey:
            raise HTTPException(status_code=400, detail="Certificado .pem inválido o passphrase incorrecto")

    task_id = str(uuid.uuid4())
    COLLECT_JOBS[task_id] = {
        "status": "pending",
        "message": "En cola...",
        "output": "",
        "lines": 0,
        "hostname": hostname,
        "created_at": datetime.now().isoformat()
    }
    background_tasks.add_task(_run_collect_job, task_id, hostname, body.port, username, body.password, body.private_key)
    logger.info("Collect job creado: %s para '%s'", task_id[:8], hostname)
    return {"task_id": task_id, "status": "pending", "hostname": hostname}


@app.get("/collect/status/{task_id}")
async def collect_status(task_id: str, _user: str = Depends(verify_auth)):
    if task_id not in COLLECT_JOBS:
        raise HTTPException(status_code=404, detail="Task no encontrada o expirada")
    return COLLECT_JOBS[task_id]


# ─── Inventory Cache Check ────────────────────────────────────────────────────
# Comando multi-plataforma (Linux/AIX/Solaris): encuentra el inventory más reciente
# y calcula su edad en minutos sin depender de `stat` (usa Python como fallback).
_CHECK_CMD = r"""
REPORT_DIR="./modernization_reports"
LATEST=$(ls -t "$REPORT_DIR"/inventory_*.txt 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    echo "FILE="
    echo "AGE=-1"
else
    NOW=$(date +%s 2>/dev/null || python3 -c "import time; print(int(time.time()))" 2>/dev/null || python -c "import time; print(int(time.time()))" 2>/dev/null || echo 0)
    FILE_TIME=$(python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$LATEST" 2>/dev/null \
             || python  -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$LATEST" 2>/dev/null \
             || stat -c %Y "$LATEST" 2>/dev/null \
             || echo 0)
    if [ "$NOW" -gt 0 ] && [ "$FILE_TIME" -gt 0 ]; then
        AGE=$(( (NOW - FILE_TIME) / 60 ))
    else
        AGE=999
    fi
    echo "FILE=$LATEST"
    echo "AGE=$AGE"
fi
""".strip()

@app.post("/collect/check")
def check_cached_inventory(body: CollectCheckRequest, _user: str = Depends(verify_auth)):
    """Verifica si existe un inventory reciente en el servidor remoto sin ejecutar un scan completo."""
    hostname = _sanitize(body.hostname)
    valid, msg = _validate_hostname(hostname)
    if not valid:
        raise HTTPException(400, f"Hostname inválido: {msg}")

    client = None
    try:
        client = _ssh_connect(hostname, body.port, _sanitize(body.username), body.password, body.private_key)
        _, stdout, _ = client.exec_command(_CHECK_CMD, timeout=20)
        output = stdout.read().decode("utf-8", errors="replace")

        file_path, age_minutes = "", -1
        for line in output.splitlines():
            if line.startswith("FILE="):
                file_path = line[5:].strip()
            elif line.startswith("AGE="):
                try:
                    age_minutes = int(line[4:].strip())
                except ValueError:
                    age_minutes = 999

        has_cache = bool(file_path) and age_minutes >= 0
        logger.info("[check] %s → has_cache=%s age=%s min file=%s", hostname, has_cache, age_minutes, file_path)
        return {
            "has_cache":    has_cache,
            "age_minutes":  age_minutes,
            "file_path":    file_path,
            "hostname":     hostname,
        }
    except paramiko.AuthenticationException:
        raise HTTPException(401, "Autenticación SSH rechazada")
    except Exception as e:
        raise HTTPException(500, f"Error al verificar caché: {e}")
    finally:
        if client:
            client.close()


@app.post("/collect/fetch-cached")
def fetch_cached_inventory(body: FetchCachedRequest, _user: str = Depends(verify_auth)):
    """Lee un archivo de inventario existente en el servidor remoto."""
    hostname = _sanitize(body.hostname)
    valid, msg = _validate_hostname(hostname)
    if not valid:
        raise HTTPException(400, f"Hostname inválido: {msg}")

    # Validar ruta
    raw_path = body.file_path.strip()
    if '..' in raw_path:
        raise HTTPException(400, "Ruta de archivo inválida o no permitida")
    m = re.search(r'modernization_reports/inventory_[\w.\-]+\.txt$', raw_path)
    if not m:
        raise HTTPException(400, "Ruta de archivo inválida o no permitida")
    file_path = m.group(0)

    client = None
    try:
        client = _ssh_connect(hostname, body.port, _sanitize(body.username), body.password, body.private_key)
        # Leer archivo (límite 10 MB para evitar abuso)
        _, stdout, _ = client.exec_command(f"head -c 10485760 '{file_path}'", timeout=30)
        content = stdout.read().decode("utf-8", errors="replace")
        if not content.strip():
            raise HTTPException(404, "El archivo existe pero está vacío")
        logger.info("[fetch-cached] %s → %s (%d chars)", hostname, file_path, len(content))
        return {"output": content, "file_path": file_path, "hostname": hostname}
    except HTTPException:
        raise
    except paramiko.AuthenticationException:
        raise HTTPException(401, "Autenticación SSH rechazada")
    except Exception as e:
        raise HTTPException(500, f"Error al leer archivo: {e}")
    finally:
        if client:
            client.close()


@app.get("/stats")
async def get_stats(_user: str = Depends(verify_auth)):
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row

    total = dict(conn.execute("SELECT COUNT(*) as cnt FROM scan_history").fetchone())["cnt"]
    unique = dict(conn.execute("SELECT COUNT(DISTINCT hostname) as cnt FROM scan_history").fetchone())["cnt"]
    last_row = conn.execute("SELECT timestamp FROM scan_history ORDER BY timestamp DESC LIMIT 1").fetchone()
    last_scan = dict(last_row)["timestamp"] if last_row else None
    recent = conn.execute(
        "SELECT id, hostname, timestamp, model_used FROM scan_history ORDER BY timestamp DESC LIMIT 8"
    ).fetchall()
    conn.close()

    return {
        "total_scans": total,
        "unique_hosts": unique,
        "last_scan": last_scan,
        "recent": [dict(r) for r in recent]
    }

# ─── PDF Export ───────────────────────────────────────────────────────────────
@app.post("/export/pdf/{scan_id}")
async def export_pdf(scan_id: str, req: PdfExportRequest = None, _user: str = Depends(verify_auth)):
    import base64
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(f"SELECT * FROM scan_history WHERE id = {ph}", (scan_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Scan no encontrado")

    d = dict(row)
    bp = json.loads(d["bedrock_blueprint"]) if isinstance(d["bedrock_blueprint"], str) else {}

    def safe(text, max_len: int = 2000) -> str:
        return (str(text) or "")[:max_len].encode("latin-1", errors="replace").decode("latin-1")

    NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    def h1(pdf, text):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 100, 180)
        pdf.set_fill_color(230, 242, 255)
        pdf.cell(0, 9, safe(text), fill=True, **NL)
        pdf.ln(1)

    def h2(pdf, text):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 7, safe(text), **NL)

    def body(pdf, text, size=9):
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(50, 50, 50)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, safe(text, 3000), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    def label_value(pdf, label, value, lw=45):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 100, 200)
        pdf.cell(lw, 5, safe(label) + ":", **{"new_x": XPos.RIGHT, "new_y": YPos.TOP})
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, safe(value, 300), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    diagrams = (req.diagrams if req else {}) or {}

    def embed_diagram(pdf, key, caption):
        """Embebe un PNG base64 enviado desde el navegador."""
        png_b64 = diagrams.get(key)
        if not png_b64:
            return
        try:
            png_bytes = base64.b64decode(png_b64)
            img_buf   = io.BytesIO(png_bytes)
            # Calcular ancho máximo disponible (márgenes 10mm cada lado)
            max_w = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.set_x(pdf.l_margin)
            pdf.image(img_buf, x=pdf.l_margin, y=None, w=max_w)
            pdf.ln(3)
            pdf.set_font("Helvetica", "I", 7)
            pdf.set_text_color(130, 130, 130)
            pdf.cell(0, 4, safe(caption), **NL)
            pdf.ln(4)
        except Exception as e:
            logger.warning("No se pudo embeber diagrama '%s': %s", key, e)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Encabezado
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 130, 200)
    pdf.cell(0, 12, "Modernization Factory - Reporte AWS", **NL)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, safe(f"Host: {d['hostname']}  |  Fecha: {d['timestamp'][:19]}  |  Modelo: {d.get('model_used','--')}"), **NL)
    pdf.ln(5)

    # ── Resumen Ejecutivo
    if bp.get("executive_summary"):
        h1(pdf, "Resumen Ejecutivo")
        body(pdf, bp["executive_summary"])

    # ── Analisis de Agentes
    if bp.get("agent_analysis"):
        h1(pdf, "Analisis de Agentes")
        body(pdf, bp["agent_analysis"])

    # ── Acoplamiento Actual (AS-IS)
    ca = bp.get("current_architecture", {})
    if ca:
        h1(pdf, "Arquitectura Actual (AS-IS)")
        score = ca.get("coupling_score", "")
        if score:
            label_value(pdf, "Acoplamiento", f"{score}/10")
        if ca.get("coupling_analysis"):
            body(pdf, ca["coupling_analysis"])
        embed_diagram(pdf, "asIs", "Diagrama AS-IS — Arquitectura actual del sistema")
        pain = ca.get("pain_points", [])
        if pain:
            h2(pdf, "Puntos de Dolor")
            for p in pain:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(50, 50, 50)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 5, safe(f"  - {p}", 200), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    # ── Estrategia de Migracion
    if bp.get("migration_strategy"):
        h1(pdf, "Estrategia de Migracion")
        body(pdf, bp["migration_strategy"])

    # ── Quick Wins
    qw = bp.get("quick_wins", [])
    if qw:
        h1(pdf, "Quick Wins (0-30 dias)")
        for item in qw:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, safe(f"  + {item}", 200), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    # ── Matriz de Riesgo
    risk = bp.get("risk_matrix", [])
    if risk:
        h1(pdf, "Matriz de Riesgo")
        for item in risk:
            if not isinstance(item, dict):
                continue
            comp = item.get("component", item.get("riesgo", ""))
            impact = item.get("impact", item.get("impacto", ""))
            prob = item.get("probability", item.get("probabilidad", ""))
            mit = item.get("mitigation", item.get("mitigacion", ""))
            label_value(pdf, "Componente", comp)
            if impact:
                label_value(pdf, "Impacto", impact)
            if prob:
                label_value(pdf, "Probabilidad", prob)
            if mit:
                label_value(pdf, "Mitigacion", mit)
            pdf.ln(2)

    # ── Plan de Migracion (Sprints)
    sprints = bp.get("sprints", {})
    if sprints:
        h1(pdf, "Plan de Migracion (Sprints)")
        for k, v in sprints.items():
            if not v:
                continue
            label = k.replace("_", " ").upper()
            h2(pdf, label)
            items = v if isinstance(v, list) else [v]
            for t in items:
                # t puede ser string o dict con title/description
                if isinstance(t, dict):
                    title = t.get("title") or t.get("task") or t.get("name") or ""
                    desc  = t.get("description") or t.get("desc") or ""
                    effort = t.get("effort") or ""
                    line = f"  • {title}"
                    if effort:
                        line += f" [{effort}]"
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.set_text_color(30, 30, 80)
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(0, 5, safe(line, 180), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    if desc:
                        pdf.set_font("Helvetica", "", 8)
                        pdf.set_text_color(80, 80, 80)
                        pdf.set_x(pdf.l_margin + 6)
                        pdf.multi_cell(0, 4, safe(desc, 250), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                else:
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(50, 50, 50)
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(0, 5, safe(f"  • {t}", 180), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    # ── Remediacion de Codigo
    remeds = bp.get("code_remediation", [])
    if remeds:
        h1(pdf, "Remediacion de Codigo")
        for r in remeds[:15]:
            if not isinstance(r, dict):
                continue
            f_name = safe(r.get("file", r.get("archivo", "?")), 100)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(180, 0, 0)
            pdf.cell(0, 5, "  " + f_name, **NL)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(50, 50, 50)
            for field, label in [("issue", "Problema"), ("action", "Accion"), ("before", "Antes"), ("after", "Despues")]:
                val = r.get(field, "")
                if val:
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(0, 4, safe(f"  {label}: {val}", 250), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            priority = r.get("priority", "")
            effort = r.get("effort", "")
            if priority or effort:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 4, safe(f"  Prioridad: {priority}  |  Esfuerzo: {effort}"), **NL)
            pdf.ln(2)

    # ── Analisis Financiero (TCO / ROI)
    biz = bp.get("business", {})
    if biz and (biz.get("tco_legacy") or biz.get("tco_aws") or biz.get("roi_analysis")):
        pdf.add_page()
        h1(pdf, "Analisis Financiero — TCO y ROI")

        def fmt_usd(n):
            try:
                return f"${int(float(n)):,}"
            except (TypeError, ValueError):
                return str(n) if n else "—"

        leg = biz.get("tco_legacy") or {}
        aws = biz.get("tco_aws") or {}
        roi = biz.get("roi_analysis") or {}

        if leg or aws:
            h2(pdf, "Costo Total de Propiedad (TCO)")
            # Encabezado tabla
            col = [80, 45, 45]
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(20, 60, 120)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(col[0], 6, "Componente", fill=True, border=1)
            pdf.cell(col[1], 6, "Legacy (anual)", fill=True, border=1, align="R")
            pdf.cell(col[2], 6, "AWS (mensual)", fill=True, border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            rows = [
                ("Licenciamiento / Infra",      leg.get("annual_licensing"),                  aws.get("ecs_fargate_monthly")),
                ("Labor / Mantenimiento",        leg.get("annual_labor_maintenance"),           aws.get("rds_aurora_serverless_monthly")),
                ("Incidentes de Seguridad",      leg.get("annual_security_incidents_risk"),     aws.get("secrets_manager_monthly")),
                ("Downtime",                     leg.get("annual_downtime_cost"),               aws.get("cloudwatch_monthly")),
            ]
            for i, (lbl, l_val, a_val) in enumerate(rows):
                if not l_val and not a_val:
                    continue
                bg = (240, 245, 255) if i % 2 == 0 else (255, 255, 255)
                pdf.set_fill_color(*bg)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(40, 40, 40)
                pdf.cell(col[0], 5, safe(lbl), fill=True, border=1)
                pdf.set_text_color(180, 0, 0)
                pdf.cell(col[1], 5, fmt_usd(l_val), fill=True, border=1, align="R")
                pdf.set_text_color(0, 130, 60)
                pdf.cell(col[2], 5, fmt_usd(a_val), fill=True, border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            # Totales
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(220, 235, 255)
            pdf.set_text_color(20, 20, 80)
            pdf.cell(col[0], 6, "  TOTAL ANUAL / MENSUAL", fill=True, border=1)
            pdf.set_text_color(180, 0, 0)
            pdf.cell(col[1], 6, fmt_usd(leg.get("total_annual")), fill=True, border=1, align="R")
            pdf.set_text_color(0, 130, 60)
            pdf.cell(col[2], 6, fmt_usd(aws.get("total_monthly")), fill=True, border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(4)

        if roi:
            h2(pdf, "ROI y Payback")
            for k, label in [("annual_savings_usd","Ahorro Anual Estimado"), ("roi_percentage_3yr","ROI a 3 anos (%)"), ("payback_months","Payback (meses)")]:
                val = roi.get(k)
                if val is not None:
                    label_value(pdf, label, str(val))
            pdf.ln(2)

        csuite = biz.get("c_suite_summary") or ""
        if csuite:
            h2(pdf, "Resumen para C-Suite")
            body(pdf, csuite)

        risk_rat = biz.get("risk_rationale") or ""
        if risk_rat:
            h2(pdf, f"Riesgo Financiero: {biz.get('risk_score','—')}/10")
            body(pdf, risk_rat)

    # ── Diagramas de Flujo (página nueva)
    pdf.add_page()
    h1(pdf, "Diagramas de Arquitectura")
    embed_diagram(pdf, "appFlow", "Diagrama de Flujo de Aplicacion — AS-IS")
    embed_diagram(pdf, "infra",   "Diagrama de Infraestructura TO-BE en AWS")

    # ── IaC (pagina nueva)
    pdf.add_page()
    h1(pdf, "Infrastructure as Code")

    cn_data = bp.get("cloudnative", {})
    # Fuente primaria: campos del blueprint; fallback al CloudNative agent para artefactos Java
    iac_sections = [
        ("Terraform HCL",   bp.get("terraform_code") or cn_data.get("terraform_managed_services", "")),
        ("Kubernetes YAML",  bp.get("k8s_yaml")       or cn_data.get("k8s_deployment", "")),
        ("Dockerfile",       bp.get("dockerfile")     or cn_data.get("dockerfile", "")),
    ]
    for section_label, content in iac_sections:
        content = (content or "").replace("\\n", "\n")
        if content and content not in ("No disponible", ""):
            h2(pdf, section_label)
            pdf.set_font("Courier", "", 7)
            pdf.set_text_color(30, 30, 30)
            pdf.set_fill_color(240, 240, 240)
            for line in safe(content, 4000).split("\n")[:60]:
                pdf.cell(0, 4, line[:140], fill=True, **NL)
            pdf.ln(4)

    # ── CloudNative extras (healthchecks, runbooks) si existen
    hc = cn_data.get("healthcheck_config") or {}
    if hc:
        h2(pdf, "Health Probes")
        for probe, val in hc.items():
            label_value(pdf, probe.replace("_", " ").upper(), str(val))

    runbooks = cn_data.get("sre_runbook") or []
    if runbooks:
        h2(pdf, "Runbooks SRE Post-Deploy")
        for rb in runbooks[:3]:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 80, 200)
            pdf.cell(0, 5, safe(rb.get("title", "")), **NL)
            if rb.get("trigger"):
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(150, 100, 0)
                pdf.cell(0, 4, safe("Trigger: " + rb["trigger"]), **NL)
            for step in (rb.get("steps") or [])[:4]:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(50, 50, 50)
                pdf.set_x(pdf.l_margin + 4)
                pdf.multi_cell(0, 4, safe("• " + step, 200), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    date_part  = (d.get("timestamp") or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    hostname_safe = re.sub(r"[^a-z0-9]", "-", (d["hostname"] or "server").lower())
    logger.info("PDF generado para scan %s por %s", scan_id[:8], _user)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=modernization-report_{hostname_safe}_{date_part}.pdf"}
    )


# ─── Chat con Blueprint ───────────────────────────────────────────────────────
@app.post("/chat")
@limiter.limit("60/hour;10/minute")
async def chat_with_blueprint(request: Request, body: ChatRequest, _user: str = Depends(verify_auth)):
    # Recuperar blueprint del scan (cache → DB)
    blueprint_ctx = "{}"
    if body.scan_id in ANALYSIS_CACHE:
        blueprint_ctx = json.dumps(ANALYSIS_CACHE[body.scan_id].get("ai_content", {}), ensure_ascii=False)
    else:
        conn, db_type = _get_conn()
        if db_type == "sqlite":
            conn.row_factory = sqlite3.Row
        ph = _ph(db_type)
        row = conn.execute(
            f"SELECT bedrock_blueprint FROM scan_history WHERE id = {ph}", (body.scan_id,)
        ).fetchone()
        conn.close()
        if row:
            blueprint_ctx = dict(row).get("bedrock_blueprint") or "{}"

    system_prompt = (
        "Eres un asistente experto en modernizacion de aplicaciones legacy hacia AWS. "
        "Tienes acceso al blueprint de analisis del sistema del usuario.\n\n"
        f"<BLUEPRINT>\n{blueprint_ctx[:6000]}\n</BLUEPRINT>\n\n"
        "Responde en espanol de forma concisa y tecnica. Basa tus respuestas en el blueprint. "
        "Para preguntas generales de AWS/Cloud, responde con mejores practicas."
    )

    history = CHAT_SESSIONS.get(body.scan_id, [])
    messages = history + [{"role": "user", "content": [{"text": body.message}]}]

    try:
        bedrock = _bedrock_client()
        resp = bedrock.converse(
            modelId="amazon.nova-lite-v1:0",
            messages=messages,
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.7}
        )
        answer = resp["output"]["message"]["content"][0]["text"]
    except Exception as e:
        logger.error("Chat error para scan %s: %s", body.scan_id[:8], e)
        raise HTTPException(502, f"Error consultando AI: {str(e)[:120]}")

    # Actualizar historial (max 20 mensajes = 10 intercambios)
    history.append({"role": "user",      "content": [{"text": body.message}]})
    history.append({"role": "assistant", "content": [{"text": answer}]})
    CHAT_SESSIONS[body.scan_id] = history[-20:]
    return {"response": answer, "scan_id": body.scan_id}


# ─── Jira Export ──────────────────────────────────────────────────────────────
@app.post("/export/jira")
async def export_to_jira(body: JiraExportRequest, _user: str = Depends(verify_auth)):
    import requests as req

    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(f"SELECT * FROM scan_history WHERE id = {ph}", (body.scan_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Scan no encontrado")

    d = dict(row)
    bp = json.loads(d["bedrock_blueprint"]) if isinstance(d["bedrock_blueprint"], str) else {}

    summary_text = bp.get("agent_analysis", "Blueprint generado por Modernization Factory.")
    sprints = bp.get("sprints", {})
    def _sprint_task_text(t):
        if isinstance(t, dict):
            title = t.get("title") or t.get("task") or ""
            effort = t.get("effort") or ""
            owner = t.get("owner") or ""
            return f"{title}{' ['+effort+']' if effort else ''}{' ('+owner+')' if owner else ''}"
        return str(t)
    sprint_lines = "\n".join(
        f"  {k.replace('_',' ').upper()}: {', '.join(_sprint_task_text(t) for t in v) if isinstance(v, list) else str(v)}"
        for k, v in sprints.items() if v
    )
    remeds = bp.get("code_remediation", [])
    remed_lines = "\n".join(
        f"  - [{r.get('file','?')}] {r.get('issue','')}"
        for r in remeds[:8]
    )

    description_adf = {
        "type": "doc", "version": 1,
        "content": [
            {"type": "heading", "attrs": {"level": 2},
             "content": [{"type": "text", "text": f"Modernizacion: {d['hostname']}"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": f"Fecha: {d['timestamp'][:19]} | Modelo: {d.get('model_used','--')}"}
            ]},
            {"type": "heading", "attrs": {"level": 3},
             "content": [{"type": "text", "text": "Analisis de Agentes"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": summary_text[:600]}]},
            {"type": "heading", "attrs": {"level": 3},
             "content": [{"type": "text", "text": "Plan de Sprints"}]},
            {"type": "codeBlock", "attrs": {"language": "text"},
             "content": [{"type": "text", "text": sprint_lines or "Sin datos"}]},
            {"type": "heading", "attrs": {"level": 3},
             "content": [{"type": "text", "text": "Remediaciones Prioritarias"}]},
            {"type": "codeBlock", "attrs": {"language": "text"},
             "content": [{"type": "text", "text": remed_lines or "Sin datos"}]},
        ]
    }

    payload = {
        "fields": {
            "project":     {"key": body.project_key},
            "summary":     f"[Modernization Factory] {d['hostname']} — Blueprint AWS",
            "description": description_adf,
            "issuetype":   {"name": body.issue_type},
            "labels":      ["modernization", "aws-migration", "tech-debt"],
        }
    }

    jira_base = body.jira_url.rstrip("/")
    try:
        r = req.post(
            f"{jira_base}/rest/api/3/issue",
            json=payload,
            auth=(body.user_email, body.api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=15
        )
    except req.exceptions.Timeout:
        raise HTTPException(504, "Timeout conectando a Jira")
    except req.exceptions.ConnectionError as e:
        raise HTTPException(502, f"No se pudo conectar a Jira: {str(e)[:100]}")

    if not r.ok:
        raise HTTPException(r.status_code, f"Jira API error ({r.status_code}): {r.text[:200]}")

    issue = r.json()
    issue_key = issue.get("key", "?")
    logger.info("Jira ticket creado: %s por %s", issue_key, _user)
    return {"issue_key": issue_key, "issue_url": f"{jira_base}/browse/{issue_key}", "id": issue.get("id")}


# ─── Diff de Modernización — Sprint 2 ────────────────────────────────────────
@app.get("/compare/{scan_id_a}/{scan_id_b}")
async def compare_scans(scan_id_a: str, scan_id_b: str, _user: str = Depends(verify_auth)):
    """Compara dos scans del mismo servidor y retorna un diff de hallazgos."""
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    rows = conn.execute(
        f"SELECT id, hostname, timestamp, bedrock_blueprint FROM scan_history WHERE id IN ({ph},{ph})",
        (scan_id_a, scan_id_b)
    ).fetchall()
    conn.close()

    if len(rows) < 2:
        raise HTTPException(404, "Uno o ambos scans no encontrados")

    scans = {dict(r)["id"]: dict(r) for r in rows}
    a = scans.get(scan_id_a, {})
    b = scans.get(scan_id_b, {})

    def _extract_findings(scan: dict) -> set:
        try:
            bp = json.loads(scan.get("bedrock_blueprint") or "{}")
        except Exception:
            bp = {}
        findings = set()
        for f in bp.get("security_findings", []):
            if isinstance(f, dict):
                findings.add(f.get("component", f.get("description", ""))[:80])
        for f in bp.get("risk_matrix", []):
            if isinstance(f, dict):
                findings.add(f.get("risk", "")[:80])
        ca = bp.get("current_architecture", {})
        for p in ca.get("pain_points", []):
            findings.add(str(p)[:80])
        return {x for x in findings if x}

    findings_a = _extract_findings(a)
    findings_b = _extract_findings(b)

    resolved  = sorted(findings_a - findings_b)
    new_items = sorted(findings_b - findings_a)
    persisted = sorted(findings_a & findings_b)

    total = max(len(findings_a), 1)
    progress = round((len(resolved) / total) * 100)

    return {
        "scan_a": {"id": scan_id_a, "timestamp": a.get("timestamp", "")[:16], "hostname": a.get("hostname")},
        "scan_b": {"id": scan_id_b, "timestamp": b.get("timestamp", "")[:16], "hostname": b.get("hostname")},
        "resolved":        resolved,
        "new":             new_items,
        "persisted":       persisted,
        "progress_score":  progress,
        "findings_count_a": len(findings_a),
        "findings_count_b": len(findings_b),
    }

# ─── Dashboard Portfolio — Sprint 3 ──────────────────────────────────────────
@app.get("/dashboard/portfolio")
async def portfolio_dashboard(_user: str = Depends(verify_auth)):
    """Retorna métricas consolidadas por hostname para el dashboard ejecutivo multi-servidor."""
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row

    # Obtener el último scan por hostname con coupling_score extraído
    rows = conn.execute(
        "SELECT id, hostname, timestamp, model_used, bedrock_blueprint "
        "FROM scan_history WHERE bedrock_blueprint IS NOT NULL "
        "ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()

    seen_hosts: dict = {}
    for r in rows:
        rd = dict(r)
        host = rd.get("hostname", "unknown")
        if host not in seen_hosts:
            try:
                bp = json.loads(rd.get("bedrock_blueprint") or "{}")
            except Exception:
                bp = {}
            ca    = bp.get("current_architecture", {})
            score = ca.get("coupling_score", 0)
            risk  = "CRÍTICO" if score >= 8 else ("ALTO" if score >= 5 else "BAJO")
            approach = ""
            ms = bp.get("migration_strategy", {})
            if isinstance(ms, dict):
                approach = ms.get("approach", "")
            method = rd.get("model_used", "")
            seen_hosts[host] = {
                "hostname":      host,
                "last_scan_id":  rd["id"],
                "last_scan":     rd.get("timestamp", "")[:16],
                "coupling_score": score,
                "risk_level":    risk,
                "approach":      approach,
                "model_used":    method,
                "total_scans":   0,
            }
        seen_hosts[host]["total_scans"] += 1

    servers = sorted(seen_hosts.values(), key=lambda x: x["coupling_score"], reverse=True)
    return {
        "total_servers": len(servers),
        "critical":      sum(1 for s in servers if s["risk_level"] == "CRÍTICO"),
        "high":          sum(1 for s in servers if s["risk_level"] == "ALTO"),
        "low":           sum(1 for s in servers if s["risk_level"] == "BAJO"),
        "servers":       servers
    }

# ─── Runbook Generator — Sprint 3 ────────────────────────────────────────────
_RUNBOOK_TEMPLATES: dict = {
    "disable_telnet": {
        "title": "Deshabilitar Telnet",
        "rhel":   "systemctl stop telnet.socket && systemctl disable telnet.socket && firewall-cmd --permanent --remove-port=23/tcp && firewall-cmd --reload",
        "ubuntu": "systemctl stop inetd 2>/dev/null; update-rc.d inetd disable 2>/dev/null; ufw deny 23",
        "aix":    "stopsrc -s telnetd && chkconfig telnetd off",
    },
    "patch_java": {
        "title": "Actualizar Java a versión LTS soportada",
        "rhel":   "yum install -y java-17-openjdk && alternatives --config java",
        "ubuntu": "apt-get install -y openjdk-17-jdk && update-alternatives --config java",
        "aix":    "# Descargar IBM JDK 17 desde ibm.com/support según arquitectura",
    },
    "disable_root_ssh": {
        "title": "Deshabilitar login SSH de root",
        "rhel":   "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && systemctl restart sshd",
        "ubuntu": "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && systemctl restart sshd",
        "aix":    "chsec -f /etc/security/user -s root -a rlogin=false",
    },
    "enable_firewall": {
        "title": "Habilitar y configurar firewall",
        "rhel":   "systemctl enable --now firewalld && firewall-cmd --set-default-zone=drop && firewall-cmd --permanent --add-service=ssh && firewall-cmd --reload",
        "ubuntu": "ufw default deny incoming && ufw allow ssh && ufw enable",
        "aix":    "# Configurar IP Filter (ipf) en AIX según documentación IBM",
    },
}

def _detect_os_family(raw_inventory: str) -> str:
    inv = raw_inventory.lower()
    if "aix" in inv:        return "aix"
    if "ubuntu" in inv:     return "ubuntu"
    if "debian" in inv:     return "ubuntu"
    return "rhel"  # RHEL / CentOS / Oracle Linux como default

@app.get("/generate/runbook/{scan_id}")
async def generate_runbook(scan_id: str, _user: str = Depends(verify_auth)):
    """Genera un script bash ejecutable con los quick wins del análisis, adaptado al OS detectado."""
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(
        f"SELECT hostname, bedrock_blueprint, raw_inventory FROM scan_history WHERE id = {ph}",
        (scan_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Scan no encontrado")

    rd  = dict(row)
    try:
        bp = json.loads(rd.get("bedrock_blueprint") or "{}")
    except Exception:
        bp = {}

    os_family = _detect_os_family(rd.get("raw_inventory") or "")
    hostname  = rd.get("hostname", "servidor")
    quick_wins = bp.get("quick_wins", [])

    lines = [
        "#!/bin/bash",
        "# ==========================================================",
        f"# Runbook generado por Modernization Factory",
        f"# Servidor: {hostname}      OS detectado: {os_family.upper()}",
        f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "# ADVERTENCIA: Revisar antes de ejecutar en producción.",
        "# ==========================================================",
        "set -euo pipefail",
        "",
        "echo '🏭 Modernization Factory — Runbook de Quick Wins'",
        f"echo 'Servidor objetivo: {hostname}'",
        "",
    ]

    # Agregar quick wins del análisis IA
    for i, qw in enumerate(quick_wins[:10], 1):
        if not isinstance(qw, dict):
            continue
        title  = qw.get("title", f"Quick Win #{i}")
        desc   = qw.get("description", "")
        effort = qw.get("effort", "")
        owner  = qw.get("owner", "")
        lines += [
            f"# ── Quick Win #{i}: {title} ──",
            f"# Esfuerzo: {effort}   Responsable: {owner}",
            f"# {desc[:200]}",
            f"echo '>> Ejecutando: {title}'",
            "# TODO: Completar con comandos específicos del entorno",
            "",
        ]

    # Agregar templates conocidos según OS
    lines += [
        "# ── Templates de hardening recomendados ──",
        "",
    ]
    for key, tmpl in _RUNBOOK_TEMPLATES.items():
        cmd = tmpl.get(os_family, tmpl.get("rhel", "# Sin comando para este OS"))
        lines += [
            f"# {tmpl['title']}",
            f"# {cmd}",
            "",
        ]

    lines += [
        "echo '✅ Runbook completado. Verificar logs del sistema.'",
    ]

    script = "\n".join(lines)
    hostname_safe = re.sub(r"[^a-z0-9]", "-", hostname.lower())
    return Response(
        content=script,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=runbook_{hostname_safe}_{scan_id[:8]}.sh"}
    )


# ─── AWS Pricing API — Sprint 4 ───────────────────────────────────────────────
# Precios hardcoded de us-east-1 como baseline (Mayo 2025)
# Usamos Pricing API para los precios dinámicos pero con fallback a estos valores
_PRICING_BASELINE = {
    "fargate_vcpu_hour":  0.04048,   # $/vCPU-hora ECS Fargate
    "fargate_gb_hour":    0.004445,  # $/GB-hora ECS Fargate
    "rds_mysql_hour":     0.115,     # $/hora RDS MySQL db.t3.medium
    "rds_postgres_hour":  0.115,     # $/hora RDS PostgreSQL db.t3.medium
    "rds_oracle_hour":    0.479,     # $/hora RDS Oracle SE2 db.m5.large
    "elasticache_hour":   0.068,     # $/hora ElastiCache Redis cache.m6g.large
    "alb_hour":           0.008,     # $/hora ALB
    "nat_hour":           0.0455,    # $/hora NAT Gateway
    "onprem_server_month": 1200.0,   # Costo mensual estimado servidor físico (HW+SW+ops)
}

def _detect_stack_for_pricing(bp: dict, raw_inventory: str) -> dict:
    """Detecta el stack del inventario para calcular el sizing AWS adecuado."""
    inv_lower = raw_inventory.lower()
    # Detectar BD por patrones específicos de JDBC/drivers, no por "oracle" genérico
    # "oracle" aparece en Oracle Java, Oracle WebLogic, Oracle Service Bus — no indica BD
    _db_oracle  = any(t in inv_lower for t in ["ojdbc", "oracle.jdbc", "oracle database", "oracle db", "orcl", "sid=", "service_name="])
    _db_mysql   = any(t in inv_lower for t in ["mysql-connector", "mysql connector", "com.mysql", "jdbc:mysql"])
    _db_pg      = any(t in inv_lower for t in ["postgresql", "pgjdbc", "org.postgresql", "jdbc:postgresql"])
    _db_mssql   = any(t in inv_lower for t in ["mssql", "sqlserver", "jtds", "jdbc:sqlserver"])
    _db_mariadb = "mariadb" in inv_lower
    result = {
        "has_web":     any(t in inv_lower for t in ["tomcat", "nginx", "apache", "node", "jboss", "websphere", "weblogic"]),
        "has_db":      any([_db_oracle, _db_mysql, _db_pg, _db_mssql, _db_mariadb]),
        "has_cache":   any(t in inv_lower for t in ["redis", "memcached", "hazelcast", "infinispan"]),
        "db_engine":   "oracle" if _db_oracle else ("postgres" if _db_pg else ("mysql" if _db_mysql else "mssql" if _db_mssql else "mysql")),
        "vcpus":       2,    # default sizing conservador
        "ram_gb":      4,
    }
    # Ajustar sizing según coupling score
    ca = bp.get("current_architecture", {})
    score = ca.get("coupling_score", 5)
    if score >= 8:
        result["vcpus"] = 4; result["ram_gb"] = 8
    elif score >= 5:
        result["vcpus"] = 2; result["ram_gb"] = 4
    else:
        result["vcpus"] = 1; result["ram_gb"] = 2
    return result

@app.get("/pricing/{scan_id}")
async def get_aws_pricing(scan_id: str, env: str = "prod", region: str = "us-east-1", _user: str = Depends(verify_auth)):
    """
    Calcula estimación de costos AWS reales para el stack detectado en el análisis.
    Retorna comparativa On-Prem vs AWS con desglose por servicio.
    """
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(
        f"SELECT hostname, bedrock_blueprint, raw_inventory FROM scan_history WHERE id = {ph}",
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

    stack = _detect_stack_for_pricing(bp, rd.get("raw_inventory") or "")
    p     = _PRICING_BASELINE
    HOURS_MONTH = 217 if env == "dev" else 730

    # ── Intentar obtener precios reales de AWS Pricing API (us-east-1 siempre)
    real_prices = {}
    try:
        pricing_client = boto3.client(
            "pricing", region_name="us-east-1",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        # ECS Fargate vCPU
        filters_fargate = [
            {"Type": "TERM_MATCH", "Field": "servicecode",      "Value": "AmazonECS"},
            {"Type": "TERM_MATCH", "Field": "usagetype",        "Value": "USE1-Fargate-vCPU-Hours:perCPU"},
        ]
        r = pricing_client.get_products(ServiceCode="AmazonECS", Filters=filters_fargate, MaxResults=1)
        if r.get("PriceList"):
            pl    = json.loads(r["PriceList"][0])
            terms = pl.get("terms", {}).get("OnDemand", {})
            for _, term in terms.items():
                for _, pd in term.get("priceDimensions", {}).items():
                    real_prices["fargate_vcpu_hour"] = float(pd["pricePerUnit"].get("USD", p["fargate_vcpu_hour"]))
        logger.info("Precios AWS reales obtenidos para %s", region)
    except Exception as e:
        logger.warning("AWS Pricing API no disponible, usando baseline: %s", e)
        real_prices = {}

    # Fusionar: real_prices sobreescribe baseline donde hay datos reales
    prices = {**p, **real_prices}

    # ── Calcular costos mensuales AWS
    ecs_cost     = stack["vcpus"] * prices["fargate_vcpu_hour"] * HOURS_MONTH \
                 + stack["ram_gb"] * prices["fargate_gb_hour"]  * HOURS_MONTH
    rds_key      = f"rds_{stack['db_engine']}_hour"
    rds_cost     = prices.get(rds_key, prices["rds_mysql_hour"]) * HOURS_MONTH if stack["has_db"] else 0
    cache_cost   = prices["elasticache_hour"] * HOURS_MONTH if stack["has_cache"] else 0
    alb_cost     = prices["alb_hour"] * HOURS_MONTH if stack["has_web"] else 0
    nat_cost     = prices["nat_hour"] * HOURS_MONTH
    aws_total    = ecs_cost + rds_cost + cache_cost + alb_cost + nat_cost

    onprem_monthly = prices["onprem_server_month"]
    savings_monthly = onprem_monthly - aws_total
    payback_months  = max(0, round(aws_total * 3 / max(savings_monthly, 0.01)))  # 3 meses migración

    breakdown = [
        {"service": "ECS Fargate",        "cost": round(ecs_cost,   2), "detail": f"{stack['vcpus']}vCPU / {stack['ram_gb']}GB"},
        {"service": f"RDS {stack['db_engine'].upper()}", "cost": round(rds_cost,  2), "detail": "db.t3.medium / Multi-AZ"} if stack["has_db"] else None,
        {"service": "ElastiCache Redis",  "cost": round(cache_cost, 2), "detail": "cache.m6g.large"} if stack["has_cache"] else None,
        {"service": "Application LB",     "cost": round(alb_cost,   2), "detail": "1 ALB"} if stack["has_web"] else None,
        {"service": "NAT Gateway",        "cost": round(nat_cost,   2), "detail": "1 AZ"},
    ]
    breakdown = [b for b in breakdown if b]

    return {
        "scan_id":          scan_id,
        "hostname":         rd.get("hostname"),
        "region":           region,
        "stack_detected":   stack,
        "aws_monthly_usd":  round(aws_total, 2),
        "onprem_monthly_usd": round(onprem_monthly, 2),
        "savings_monthly_usd": round(savings_monthly, 2),
        "savings_pct":      round((savings_monthly / max(onprem_monthly, 1)) * 100, 1),
        "payback_months":   payback_months,
        "breakdown":        breakdown,
        "pricing_source":   "aws_api" if real_prices else "baseline_2025",
        "note":             "Estimación conservadora. Costos reales varían según tráfico y almacenamiento.",
    }


# ─── FinOps — Fetchers de precios públicos ────────────────────────────────────

def _fetch_azure_prices(region: str = "eastus") -> dict:
    """Llama Azure Retail Prices API (sin auth). Retorna dict service→$/hr."""
    import requests as req
    baseline = {
        "container": 0.0160,
        "database":  0.0340,
        "cache":     0.0340,
        "lb":        0.0250,
    }
    try:
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
                    baseline["container"] = round(item["unitPrice"] / 4, 6)
                    break
    except Exception as e:
        logger.warning("Azure Pricing API error: %s", e)
    return baseline


def _fetch_gcp_prices(region: str = "us-east1") -> dict:
    """Retorna precios GCP baseline 2025. Si GCP_API_KEY está configurado, intenta API real."""
    import requests as req
    baseline = {
        "container": 0.0000240 * 3600,
        "database":  0.0250,
        "cache":     0.0490,
        "lb":        0.0080,
    }
    api_key = os.getenv("GCP_API_KEY", "")
    if not api_key:
        return baseline
    try:
        svc_id = "9662-B51E-5089"
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
    """Retorna precios cacheados si son < 24h. None si expirados o inexistentes."""
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
            if (now - fetched).total_seconds() > 86400:
                return None
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
    Retorna análisis FinOps completo: ai_analysis del CostOptimizationAgent
    + price_comparison multi-cloud con precios reales normalizados.
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

    HOURS_MONTH = 730
    p = _PRICING_BASELINE
    aws_prices = {
        "container": round(p["fargate_vcpu_hour"] * 0.5 + p["fargate_gb_hour"] * 1.0, 6),
        "database":  p.get("rds_mysql_hour", 0.034),
        "cache":     p.get("elasticache_hour", 0.034),
        "lb":        p.get("alb_hour", 0.008),
    }

    cache_hit_az = False
    az_prices = _get_cached_prices("azure", az_region)
    if az_prices:
        cache_hit_az = True
    else:
        az_prices = _fetch_azure_prices(az_region)
        _save_prices_to_cache("azure", az_region, az_prices)

    cache_hit_gcp = False
    gcp_prices = _get_cached_prices("gcp", gcp_region)
    if gcp_prices:
        cache_hit_gcp = True
    else:
        gcp_prices = _fetch_gcp_prices(gcp_region)
        _save_prices_to_cache("gcp", gcp_region, gcp_prices)

    has_db    = bool(bp.get("business", {}).get("tco_aws", {}).get("rds_aurora_serverless_monthly", 0))
    has_cache = "cache" in str(bp).lower() or "redis" in str(bp).lower()
    has_lb    = True

    def _monthly(prices: dict, use_db: bool, use_cache: bool, use_lb: bool) -> dict:
        container = round(prices["container"] * HOURS_MONTH, 2)
        db        = round(prices["database"]  * HOURS_MONTH, 2) if use_db    else 0
        cache     = round(prices["cache"]     * HOURS_MONTH, 2) if use_cache else 0
        lb        = round(prices["lb"]        * HOURS_MONTH, 2) if use_lb    else 0
        return {
            "container": container, "database": db,
            "cache": cache, "lb": lb,
            "total": round(container + db + cache + lb, 2)
        }

    aws_monthly = _monthly(aws_prices,  has_db, has_cache, has_lb)
    az_monthly  = _monthly(az_prices,   has_db, has_cache, has_lb)
    gcp_monthly = _monthly(gcp_prices,  has_db, has_cache, has_lb)

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


# ─── IaC Validator — Sprint 4 ─────────────────────────────────────────────────
@app.get("/validate/iac/{scan_id}")
async def validate_iac(scan_id: str, _user: str = Depends(verify_auth)):
    """
    Valida la sintaxis del IaC generado (Terraform, K8s YAML, Dockerfile) localmente.
    No requiere terraform CLI ni Docker instalados — validación de sintaxis básica.
    """
    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(
        f"SELECT bedrock_blueprint FROM scan_history WHERE id = {ph}", (scan_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Scan no encontrado")

    try:
        bp = json.loads(dict(row).get("bedrock_blueprint") or "{}")
    except Exception:
        bp = {}

    results = {}

    # ── Validar Terraform HCL (heurística básica de balanceo de llaves/bloques)
    tf = bp.get("terraform_code", "")
    if tf and tf not in ("No disponible", ""):
        tf_issues = []
        opens  = tf.count("{")
        closes = tf.count("}")
        if opens != closes:
            tf_issues.append(f"Llaves desbalanceadas: {opens} abiertas / {closes} cerradas")
        # Detectar resource blocks sin name
        if re.search(r'\bresource\s+"[^"]+"\s*\{', tf) is None and "resource" in tf:
            tf_issues.append("Bloque 'resource' sin tipo/nombre entre comillas")
        # Detectar variables sin type
        undefined_vars = re.findall(r'\bvar\.[a-zA-Z_]+', tf)
        declared_vars  = re.findall(r'variable\s+"([^"]+)"', tf)
        used_but_not_declared = [v.replace("var.", "") for v in undefined_vars if v.replace("var.", "") not in declared_vars]
        if used_but_not_declared:
            tf_issues.append(f"Variables no declaradas: {', '.join(set(used_but_not_declared[:5]))}")

        results["terraform"] = {
            "status":  "✅ VÁLIDO" if not tf_issues else "⚠️ ADVERTENCIAS",
            "issues":  tf_issues,
            "lines":   tf.count("\n"),
            "blocks":  len(re.findall(r'\bresource\s+"', tf)),
        }
    else:
        results["terraform"] = {"status": "—", "issues": [], "lines": 0, "blocks": 0}

    # ── Validar Kubernetes YAML (parseo básico sin PyYAML)
    k8s = bp.get("k8s_yaml", "")
    if k8s and k8s not in ("No disponible", ""):
        k8s_issues = []
        # Verificar campos mandatorios
        for field in ("apiVersion", "kind", "metadata"):
            if field not in k8s:
                k8s_issues.append(f"Campo requerido faltante: '{field}'")
        # Detectar tabs en lugar de espacios (error común en YAML)
        if "\t" in k8s:
            k8s_issues.append("YAML contiene tabs — usar solo espacios")
        # Detectar indentación mixta (heurística)
        lines_with_indent = [l for l in k8s.splitlines() if l.startswith(" ") or l.startswith("\t")]
        if lines_with_indent and not all(l[0] == lines_with_indent[0][0] for l in lines_with_indent if l.strip()):
            k8s_issues.append("Posible indentación mixta (tabs y espacios)")

        results["kubernetes"] = {
            "status": "✅ VÁLIDO" if not k8s_issues else "⚠️ ADVERTENCIAS",
            "issues": k8s_issues,
            "lines":  k8s.count("\n"),
            "kinds":  re.findall(r'\bkind:\s*(\w+)', k8s),
        }
    else:
        results["kubernetes"] = {"status": "—", "issues": [], "lines": 0, "kinds": []}

    # ── Validar Dockerfile (reglas básicas)
    dockerfile = bp.get("dockerfile", "")
    if dockerfile and dockerfile not in ("No disponible", ""):
        df_issues = []
        df_lines  = [l.strip() for l in dockerfile.splitlines() if l.strip() and not l.strip().startswith("#")]
        # Debe empezar con FROM
        if df_lines and not df_lines[0].upper().startswith("FROM"):
            df_issues.append("El Dockerfile debe comenzar con instrucción FROM")
        # No debe usar latest en FROM (bad practice)
        if re.search(r'\bFROM\s+\S+:latest', dockerfile, re.IGNORECASE):
            df_issues.append("Evitar 'latest' en FROM — usar tag específico para reproducibilidad")
        # Debe tener ENTRYPOINT o CMD
        if "ENTRYPOINT" not in dockerfile and "CMD" not in dockerfile:
            df_issues.append("Sin ENTRYPOINT ni CMD — el contenedor no tendría punto de entrada")
        # Exponer puertos
        if "EXPOSE" not in dockerfile:
            df_issues.append("Sin instrucción EXPOSE — documentar los puertos que expone el servicio")

        results["dockerfile"] = {
            "status": "✅ VÁLIDO" if not df_issues else ("⚠️ ADVERTENCIAS" if len(df_issues) < 3 else "❌ ERRORES"),
            "issues": df_issues,
            "lines":  len(df_lines),
            "instructions": list({l.split()[0] for l in df_lines if l.split()}),
        }
    else:
        results["dockerfile"] = {"status": "—", "issues": [], "lines": 0, "instructions": []}

    # Resumen global
    any_errors = any(r["status"].startswith("❌") for r in results.values())
    any_warnings = any(r["status"].startswith("⚠️") for r in results.values())
    overall = "❌ ERRORES" if any_errors else ("⚠️ ADVERTENCIAS" if any_warnings else "✅ VÁLIDO")

    return {
        "scan_id": scan_id,
        "overall": overall,
        "results": results,
        "validated_at": datetime.now().isoformat(),
    }


# ─── Java Artifact Agent ──────────────────────────────────────────────────────

_AGENT_JAVA_PROMPT = """
Eres un Staff Engineer con 15 años de experiencia modernizando aplicaciones Java Enterprise hacia AWS y Spring Boot.
Se te entrega el inventario técnico DETALLADO extraído directamente del bytecode y descriptores de un artefacto Java (.ear/.war/.jar),
incluyendo: clases detectadas con sus roles, SQL hardcodeado, antipatrones, CVEs en dependencias y versiones exactas.

Tu misión: producir una guía de transformación CONCRETA y ACCIONABLE — no genérica.
NUNCA uses placeholders como "ClassName" o "tu clase". Usa los nombres REALES del inventario.

Retorna ÚNICAMENTE JSON válido con este esquema:
{{
  "executive_summary": "3-4 oraciones con: nombre del artefacto, stack real detectado (framework + versión exacta), riesgos top-3 con CVE IDs reales, estrategia recomendada",

  "agent_analysis": "Análisis técnico en 5+ párrafos: (1) stack completo con versiones, (2) arquitectura actual JEE detectada (EJBs/Servlets/JSF/etc.), (3) deuda técnica específica por patrón detectado, (4) ruta de modernización recomendada con runtime AWS objetivo, (5) impacto y riesgos de la migración",

  "java_findings": [
    {{
      "severity": "CRITICO|ALTO|MEDIO|BAJO",
      "component": "nombre exacto del JAR o clase del inventario",
      "version": "X.Y.Z exacta del inventario",
      "issue": "descripción técnica con el riesgo real",
      "cve": "CVE-XXXX-YYYY o N/A",
      "recommendation": "acción concreta: comando, código o configuración"
    }}
  ],

  "code_transformation": [
    {{
      "class_name": "nombre.completo.de.la.Clase (del inventario)",
      "current_pattern": "EJB Stateless|Servlet|JSF ManagedBean|JAX-RS|JPA Entity|DAO|etc.",
      "target_pattern": "Spring Boot @Service|@RestController|@Entity|@Repository|etc.",
      "why": "razón técnica concreta para este cambio",
      "before": "fragmento de código JEE típico de este patrón (<8 líneas)",
      "after": "código Spring Boot equivalente (<8 líneas)",
      "effort_days": 1,
      "dependencies_to_add": ["groupId:artifactId:version"],
      "dependencies_to_remove": ["groupId:artifactId"]
    }}
  ],

  "dependency_analysis": {{
    "total_jars": 0,
    "vulnerable": ["artifact-version → CVE-XXXX: descripción"],
    "outdated": ["artifact vX.Y → actualizar a vA.B (razón)"],
    "eol": ["artifact — EoL desde YYYY, reemplazar con X"],
    "to_remove": ["artifact — reemplazado por Y en Spring Boot"],
    "to_add": ["groupId:artifactId:version — para soportar migración"]
  }},

  "sql_analysis": [
    {{
      "query": "fragmento SQL encontrado en bytecode",
      "class": "NombreClase donde fue detectado",
      "recommendation": "migrar a Spring Data @Query o método JpaRepository",
      "jpa_equivalent": "ejemplo de método JPA equivalente"
    }}
  ],

  "externalization": [
    {{
      "type": "JNDI|JDBC_URL|Filesystem|HTTP_URL|Hardcoded_Config|Profile",
      "found_in": "NombreClase o archivo",
      "current_value": "valor o patrón detectado (sanitizado)",
      "target": "AWS SSM Parameter Store|Secrets Manager|S3|application.yml (Ejs: database URL, keys)",
      "how": "instrucción concreta de migración"
    }}
  ],

  "containerization": {{
    "base_image": "eclipse-temurin:17-jre-alpine (u otra según Java version detectada)",
    "dockerfile_lift_shift": "Dockerfile completo para Lift & Shift directo (ej: usar FROM tomcat:9-jdk11 si es WAR sin cambios)",
    "dockerfile_modernized": "Dockerfile completo multi-stage asumiendo que se migró exitosamente a Spring Boot (fat-jar)",
    "env_vars": ["SPRING_PROFILES_ACTIVE=prod", "SPRING_DATASOURCE_URL=jdbc:postgresql://...", "..."],
    "health_check": "curl -f http://localhost:8080/actuator/health || exit 1",
    "jvm_flags": "-Xmx512m -Xms256m -XX:+UseContainerSupport -XX:MaxRAMPercentage=75",
    "toxic_dependencies": ["Lista de bloqueantes (JNI, .dll/.so locales, file systems montados localmente) identificados explícitamente"]
  }},

  "migration_strategy": {{
    "approach": "strangler-fig|re-architect|repackage|lift-and-shift",
    "rationale": "justificación técnica basada en patrones detectados",
    "target_runtime": "ECS Fargate|EKS|Lambda|Elastic Beanstalk",
    "estimated_effort_weeks": 0,
    "phases": ["fase 1: ...", "fase 2: ..."]
  }},

  "code_remediation": [
    {{
      "file": "nombre.completo.Clase (del inventario)",
      "issue": "antipatrón concreto detectado",
      "before": "código legacy (<6 líneas)",
      "after": "código modernizado (<6 líneas)",
      "priority": "HIGH|MEDIUM|LOW",
      "effort": "Xd"
    }}
  ],

  "quick_wins": ["acción concreta en <2 semanas: qué clase, qué cambiar, qué ganas"],

  "sprints": {{
    "sprint_0": ["tarea concreta con clase/archivo real — rol responsable — Xd"],
    "sprint_1": ["..."],
    "sprint_2": ["..."],
    "sprint_3": ["..."]
  }},

  "risk_matrix": [
    {{
      "component": "nombre real del componente",
      "probability": "Alta|Media|Baja",
      "impact": "Alto|Medio|Bajo",
      "mitigation": "acción concreta"
    }}
  ]
}}
"""

# ── Bytecode / constant-pool analysis ────────────────────────────────────────

def _scan_class_bytecode(class_bytes: bytes) -> list[str]:
    """
    Extrae todas las cadenas UTF-8 del constant pool de un .class.
    El formato es: tag(1) + length(2) + bytes para tag=1 (Utf8).
    Maneja correctamente los slots dobles de Long/Double.
    """
    strings: list[str] = []
    if len(class_bytes) < 10 or class_bytes[:4] != b"\xca\xfe\xba\xbe":
        return strings
    try:
        cp_count = int.from_bytes(class_bytes[8:10], "big")
        i = 10
        idx = 1
        while idx < cp_count and i < len(class_bytes):
            tag = class_bytes[i]; i += 1
            if tag == 1:       # Utf8
                ln = int.from_bytes(class_bytes[i:i+2], "big"); i += 2
                try:
                    strings.append(class_bytes[i:i+ln].decode("utf-8", errors="replace"))
                except Exception:
                    pass
                i += ln; idx += 1
            elif tag in (3, 4):  i += 4;  idx += 1   # Integer / Float
            elif tag in (5, 6):  i += 8;  idx += 2   # Long / Double (doble slot)
            elif tag in (7, 8, 16, 19, 20): i += 2; idx += 1
            elif tag in (9, 10, 11, 12, 17, 18): i += 4; idx += 1
            elif tag == 15:  i += 3; idx += 1
            else: break
    except Exception:
        pass
    return strings

# Anotaciones JEE/Spring que identifican el rol de una clase
_ANNOTATION_ROLES: dict[str, str] = {
    # Servlets y MVC
    "javax/servlet/http/HttpServlet":             "Servlet",
    "jakarta/servlet/http/HttpServlet":           "Servlet",
    "javax/servlet/annotation/WebServlet":        "Servlet",
    "org/springframework/web/bind/annotation/RestController": "REST Controller",
    "org/springframework/web/bind/annotation/Controller":     "MVC Controller",
    "org/springframework/web/bind/annotation/RequestMapping": "Spring MVC",
    "javax/ws/rs/Path":                           "JAX-RS Resource",
    "jakarta/ws/rs/Path":                         "JAX-RS Resource",
    # EJB
    "javax/ejb/Stateless":                        "EJB Stateless",
    "jakarta/ejb/Stateless":                      "EJB Stateless",
    "javax/ejb/Stateful":                         "EJB Stateful",
    "jakarta/ejb/Stateful":                       "EJB Stateful",
    "javax/ejb/Singleton":                        "EJB Singleton",
    "jakarta/ejb/Singleton":                      "EJB Singleton",
    "javax/ejb/MessageDriven":                    "MDB (Message-Driven Bean)",
    # Persistencia
    "javax/persistence/Entity":                   "JPA Entity",
    "jakarta/persistence/Entity":                 "JPA Entity",
    "org/hibernate/annotations/Entity":           "Hibernate Entity",
    "org/springframework/data/repository/Repository": "Spring Repository",
    "org/springframework/stereotype/Repository":  "Spring Repository",
    # Spring
    "org/springframework/stereotype/Service":     "Spring Service",
    "org/springframework/stereotype/Component":   "Spring Component",
    "org/springframework/context/annotation/Configuration": "Spring Config",
    "org/springframework/scheduling/annotation/Scheduled": "Scheduled Task",
    # JSF
    "javax/faces/bean/ManagedBean":               "JSF ManagedBean",
    "jakarta/faces/bean/ManagedBean":             "JSF ManagedBean",
    # Seguridad
    "javax/annotation/security/RolesAllowed":     "Secured (RolesAllowed)",
    "org/springframework/security/access/annotation/Secured": "Spring Security",
    # Frameworks Legacy Extras
    "org/apache/axis/":                           "Axis SOAP WebService",
    "org/apache/wicket/":                         "Apache Wicket",
    "com/google/gwt/":                            "Google Web Toolkit (GWT)",
    "com/ibatis/":                                "iBATIS ORM",
}

_MIGRATION_MAP: dict[str, str] = {
    "Servlet":              "→ Spring Boot @RestController + @RequestMapping",
    "REST Controller":      "→ Mantener patrón, actualizar a Spring Boot 3.x / Jakarta EE 10",
    "MVC Controller":       "→ Mantener @Controller, migrar vistas a Thymeleaf o API REST",
    "JAX-RS Resource":      "→ Migrar a Spring Boot @RestController o quarkus @Path",
    "EJB Stateless":        "→ @Service de Spring Boot + @Transactional",
    "EJB Stateful":         "→ @Service con @Scope(\"session\") o Redis para estado",
    "EJB Singleton":        "→ @Component @Scope(\"singleton\") o Spring @Bean",
    "MDB (Message-Driven Bean)": "→ @SqsListener (AWS SQS) o @KafkaListener",
    "JPA Entity":           "→ Mantener @Entity, migrar a Spring Data JPA + Flyway",
    "Hibernate Entity":     "→ Migrar a javax/jakarta @Entity estándar + Spring Data",
    "Spring Repository":    "→ Extender JpaRepository<T,ID> — sin cambio mayor",
    "Spring Service":       "→ Mantener, revisar @Transactional y manejo de excepciones",
    "Spring Component":     "→ Mantener, revisar inyección de dependencias",
    "Spring Config":        "→ Migrar a application.yml + @ConfigurationProperties",
    "JSF ManagedBean":      "→ Eliminar JSF, migrar a REST API + frontend React/Angular",
    "Scheduled Task":       "→ AWS EventBridge + Lambda, o mantener @Scheduled en ECS",
    "Secured (RolesAllowed)": "→ Spring Security @PreAuthorize + JWT / Cognito",
    "Spring Security":      "→ Actualizar Spring Security 6.x + OAuth2/OIDC con Cognito",
    "Axis SOAP WebService": "→ Migrar a JAX-WS o modernizar a Spring Boot REST @RestController",
    "Apache Wicket":        "→ Rewrite frontend en React/Angular, exponer API REST",
    "Google Web Toolkit (GWT)": "→ Rewrite frontend en React/Angular, exponer API REST",
    "iBATIS ORM":           "→ Migrar a MyBatis o Spring Data JPA",
}

# Patrones de strings que indican código que necesita transformación
_CODE_SMELL_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern_substring, category, description)
    ("java:comp/env",          "JNDI",         "JNDI lookup — reemplazar con @Autowired / AWS SSM Parameter Store"),
    ("java:jboss",             "JNDI",         "JNDI JBoss — eliminar dependencia de servidor de aplicaciones"),
    ("InitialContext",         "JNDI",         "javax.naming.InitialContext — migrar a inyección de dependencias"),
    ("System.getenv",          "Config",       "Variables de entorno directas — usar @ConfigurationProperties"),
    ("System.getProperty",     "Config",       "System.getProperty — externalizar a application.yml"),
    ("SELECT ",                "SQL",          "SQL hardcodeado — mover a Spring Data JPA / named queries"),
    ("INSERT INTO",            "SQL",          "SQL hardcodeado — mover a repositorio JPA"),
    ("UPDATE ",                "SQL",          "SQL hardcodeado — revisar si puede ser método JPA"),
    ("DELETE FROM",            "SQL",          "SQL hardcodeado — mover a repositorio JPA"),
    ("jdbc:",                  "DataSource",   "JDBC URL hardcodeada — mover a AWS RDS + Secrets Manager"),
    ("http://",                "URL",          "URL HTTP en código — usar HTTPS y externalizar a config"),
    ("new Thread(",            "Threading",    "Thread manual — migrar a @Async de Spring o ECS tasks"),
    ("Runtime.exec",           "Security",     "Runtime.exec — riesgo de command injection, revisar"),
    ("HttpURLConnection",      "HTTP",         "HttpURLConnection legacy — migrar a RestTemplate o WebClient"),
    ("FileInputStream",        "FileIO",       "FileInputStream — en contenedor usar S3 / EFS en vez de filesystem"),
    ("new File(",              "FileIO",       "Acceso a filesystem local — migrar a Amazon S3"),
    ("printStackTrace",        "Logging",      "printStackTrace — reemplazar con Logger (SLF4J/Logback)"),
    ("MD5",                    "Security",     "MD5 detectado — algoritmo inseguro, usar SHA-256 o bcrypt"),
    ("DES",                    "Security",     "DES detectado — cifrado inseguro, migrar a AES-256"),
    ("password",               "Security",     "String 'password' en constante — verificar si está hardcodeado"),
    ("EJBContext",             "EJB",          "EJBContext — eliminar en migración a Spring Boot"),
    ("UserTransaction",        "Transaction",  "UserTransaction JTA — reemplazar con @Transactional de Spring"),
    ("HttpSession",            "Stateful",     "Uso pesado de HttpSession — externalizar estado a Redis o DynamoDB para Container/K8s"),
    ("ehcache",                "Stateful",     "Caché en memoria local local (Ehcache) — migrar a caché distribuido (ElastiCache)"),
    ("javax/ejb/Timer",        "Concurrency",  "Temporizador EJB dependiente del nodo local — usar AWS EventBridge o Quartz Distribuido"),
    ("TimerTask",              "Concurrency",  "TimerTask — no escala en K8s (múltiples pods ejecutarán a la vez)"),
    ("System.loadLibrary",     "Toxic",        "JNI nativo (.dll/.so) — bloqueante para cambiar CPU arch y OS image en Docker"),
]

def _classify_and_analyze_class(entry_path: str, strings: list[str]) -> dict | None:
    """
    Dado el path de un .class y sus strings del constant pool,
    retorna un dict con su clasificación, smells y hints de migración.
    """
    # Nombre de clase legible
    class_name = entry_path.replace("/", ".").removesuffix(".class")
    for strip in ["WEB-INF.classes.", "APP-INF.classes.", "BOOT-INF.classes."]:
        class_name = class_name.split(strip, 1)[-1]

    # Ignorar clases anónimas/internas menores
    if "$" in class_name.split(".")[-1] and len(class_name.split(".")[-1]) < 4:
        return None

    str_set = set(strings)
    str_joined = " ".join(strings)

    # Detectar rol
    roles = []
    for annotation_path, role in _ANNOTATION_ROLES.items():
        if annotation_path in str_set or annotation_path.replace("/", ".") in str_joined:
            if role not in roles:
                roles.append(role)

    # Detectar smells
    smells = []
    for (pattern, category, desc) in _CODE_SMELL_PATTERNS:
        if any(pattern.lower() in s.lower() for s in strings):
            smells.append({"category": category, "detail": desc})

    # SQL queries encontradas
    sql_hits = [s[:120] for s in strings
                if len(s) > 15 and any(kw in s.upper() for kw in ["SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM", "CALL "])]

    # URLs encontradas
    urls = [s[:100] for s in strings if s.startswith(("http://", "https://", "jdbc:")) and len(s) > 8]

    if not roles and not smells and not sql_hits:
        return None  # Clase sin señales relevantes

    return {
        "class": class_name,
        "roles": roles,
        "migration_hints": [_MIGRATION_MAP[r] for r in roles if r in _MIGRATION_MAP],
        "smells": smells,
        "sql_found": sql_hits[:3],
        "urls_found": urls[:3],
    }


def _parse_manifest(content: str) -> dict:
    result = {}
    for line in content.splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            result[k.strip()] = v.strip()
    return result

def _parse_xml_safe(content: str) -> ET.Element | None:
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        return None

# ── CVE knowledge base ────────────────────────────────────────────────────────
# (artifact_id_pattern, min_version_inclusive, max_version_exclusive, CVE, severity, description)
_JAVA_CVE_MAP: dict[str, list[tuple]] = {
    "log4j-core":             [("2.0","2.17.1","CVE-2021-44228","CRITICO","Log4Shell — RCE via JNDI lookup"),
                                ("2.0","2.3.2", "CVE-2021-45105","ALTO",  "Log4j2 infinite recursion DoS")],
    "log4j":                  [("1.0","2.0",   "CVE-2019-17571","CRITICO","Log4j 1.x SocketServer RCE — EoL desde 2015")],
    "struts2-core":           [("2.0","2.5.33","CVE-2023-50164","CRITICO","Struts2 path traversal → RCE"),
                                ("2.0","2.5.30","CVE-2017-5638", "CRITICO","Struts2 Content-Type RCE (Equifax breach)")],
    "spring-core":            [("5.3.0","5.3.18","CVE-2022-22965","CRITICO","Spring4Shell — RCE via DataBinder (JDK9+)"),
                                ("5.0.0","5.2.20","CVE-2022-22965","CRITICO","Spring4Shell — RCE via DataBinder (JDK9+)")],
    "spring-webmvc":          [("5.3.0","5.3.18","CVE-2022-22965","CRITICO","Spring4Shell — mismo vector que spring-core")],
    "spring-security-core":   [("5.0.0","5.6.9","CVE-2022-22978","ALTO","Spring Security regex bypass en auth")],
    "jackson-databind":       [("2.0.0","2.12.6","CVE-2020-36518","ALTO","Stack overflow DoS"),
                                ("2.0.0","2.9.10","CVE-2019-14379","CRITICO","RCE via deserialization gadget")],
    "xstream":                [("1.0.0","1.4.20","CVE-2022-41966","ALTO","Stack overflow DoS via XML malformado"),
                                ("1.0.0","1.4.18","CVE-2021-43859","ALTO","DoS via XML crafteado")],
    "commons-collections":    [("3.0","3.2.2","CVE-2015-7501","CRITICO","RCE via deserialization — gadget chain clásico"),
                                ("4.0","4.1",  "CVE-2015-7501","CRITICO","Commons Collections 4.x — misma gadget chain")],
    "commons-text":           [("1.0","1.10.0","CVE-2022-42889","CRITICO","Text4Shell — RCE via StringSubstitutor interpolation")],
    "commons-fileupload":     [("0.0","1.5",   "CVE-2023-24998","ALTO","DoS via unlimited multipart parts")],
    "shiro-core":             [("1.0.0","1.11.0","CVE-2023-34478","CRITICO","Apache Shiro path traversal — auth bypass"),
                                ("1.0.0","1.9.1", "CVE-2022-32532","CRITICO","Shiro authentication bypass")],
    "h2":                     [("0.0","2.1.210","CVE-2021-42392","CRITICO","H2 Console RCE via JNDI — igual vector que Log4Shell")],
    "velocity-engine-core":   [("0.0","2.3.0",  "CVE-2020-13936","CRITICO","Velocity Engine SSTI — RCE en sandbox")],
    "velocity":               [("0.0","1.7.1",  "CVE-2020-13936","CRITICO","Velocity SSTI — RCE en sandbox")],
    "groovy":                 [("0.0","2.4.21", "CVE-2016-6814", "CRITICO","Groovy RCE via deserialization")],
    "mybatis":                [("0.0","3.5.6",  "CVE-2020-26945","MEDIO", "MyBatis deserialization")],
    "fastjson":               [("0.0","1.2.83", "CVE-2022-25845","CRITICO","Fastjson AutoType RCE")],
    "netty-all":              [("0.0","4.1.77", "CVE-2022-24823","MEDIO", "Netty temp dir privilege escalation")],
    "okhttp":                 [("0.0","4.9.2",  "CVE-2021-0341", "MEDIO", "OkHttp hostname verification bypass")],
    "snakeyaml":              [("0.0","2.0",    "CVE-2022-1471", "CRITICO","SnakeYAML Constructor RCE via deserialization")],
}

def _ver_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in re.sub(r"[^0-9.]", ".", v).split(".") if x)
    except Exception:
        return (0,)

def _ver_in_range(version: str, lo: str, hi: str) -> bool:
    try:
        return _ver_tuple(lo) <= _ver_tuple(version) < _ver_tuple(hi)
    except Exception:
        return False

def _parse_jar_name(basename: str) -> tuple[str, str]:
    """'log4j-core-2.14.1.jar' → ('log4j-core', '2.14.1')"""
    name = basename.removesuffix(".jar")
    parts = name.split("-")
    ver_idx = next((i for i, p in enumerate(parts) if p and p[0].isdigit()), None)
    if ver_idx is None or ver_idx == 0:
        return name, ""
    artifact = "-".join(parts[:ver_idx])
    raw_ver = re.sub(r"[^0-9.]", ".", "-".join(parts[ver_idx:]))
    version  = re.sub(r"\.+", ".", raw_ver).strip(".")
    return artifact, version

def _read_jar_manifest_version(zf_outer: zipfile.ZipFile, jar_entry: str) -> str:
    """Intenta abrir un JAR anidado y leer Implementation-Version de su MANIFEST.MF."""
    try:
        jar_bytes = zf_outer.read(jar_entry)
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as inner:
            if "META-INF/MANIFEST.MF" in inner.namelist():
                mf = inner.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
                parsed = _parse_manifest(mf)
                return (parsed.get("Implementation-Version")
                        or parsed.get("Bundle-Version")
                        or parsed.get("Specification-Version", ""))
    except Exception:
        pass
    return ""

_JAVA_CLASS_VERSIONS = {
    45: "Java 1.1", 46: "Java 1.2", 47: "Java 1.3", 48: "Java 1.4",
    49: "Java 5",   50: "Java 6",   51: "Java 7",   52: "Java 8",
    53: "Java 9",   54: "Java 10",  55: "Java 11",  56: "Java 12",
    57: "Java 13",  58: "Java 14",  59: "Java 15",  60: "Java 16",
    61: "Java 17",  62: "Java 18",  63: "Java 19",  64: "Java 20",
    65: "Java 21",
}

def _detect_java_class_version(zf: zipfile.ZipFile, class_entries: list[str]) -> str:
    """Lee los magic bytes del primer .class para determinar la versión Java mínima requerida."""
    for ce in class_entries[:5]:
        try:
            data = zf.read(ce)
            if len(data) >= 8 and data[:4] == b"\xca\xfe\xba\xbe":
                major = int.from_bytes(data[6:8], "big")
                return _JAVA_CLASS_VERSIONS.get(major, f"Java (class major {major})")
        except Exception:
            continue
    return ""

def _extract_artifact_inventory(file_bytes: bytes, filename: str) -> str:
    """
    Extrae inventario técnico profundo de un artefacto Java (EAR/WAR/JAR):
    versiones de dependencias, CVEs conocidos, descriptores XML, bytecode version,
    configuraciones de framework, patrones de código detectados.
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    lines = [
        f"ARTIFACT_NAME: {filename}",
        f"ARTIFACT_TYPE: {ext.upper()}",
        f"ARTIFACT_SIZE_KB: {len(file_bytes) // 1024}",
        "",
    ]

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            all_entries = zf.namelist()
            lines.append(f"TOTAL_ENTRIES: {len(all_entries)}")

            # ── 1. MANIFEST.MF principal ──────────────────────────────────────
            for mk in ["META-INF/MANIFEST.MF", "MANIFEST.MF"]:
                if mk in all_entries:
                    mf = zf.read(mk).decode("utf-8", errors="replace")
                    parsed = _parse_manifest(mf)
                    lines.append("\n=== MANIFEST.MF ===")
                    for k, v in parsed.items():
                        lines.append(f"  {k}: {v}")
                    break

            # ── 2. Versión Java del bytecode ──────────────────────────────────
            class_entries = [e for e in all_entries if e.endswith(".class")]
            java_ver = _detect_java_class_version(zf, class_entries)
            if java_ver:
                lines.append(f"\n=== JAVA BYTECODE ===")
                lines.append(f"  COMPILED_FOR: {java_ver}")
                lines.append(f"  TOTAL_CLASSES: {len(class_entries)}")
                # Paquetes top-level de la aplicación
                pkgs = set()
                for ce in class_entries:
                    p = ce.rsplit("/", 1)[0].replace("/", ".")
                    for strip in ["WEB-INF.classes.", "APP-INF.classes.", "BOOT-INF.classes."]:
                        p = p.split(strip)[-1]
                    pkgs.add(p)
                top_pkgs = sorted({".".join(p.split(".")[:3]) for p in pkgs if p})[:20]
                if top_pkgs:
                    lines.append(f"  TOP_PACKAGES: {', '.join(top_pkgs)}")
                # Heurísticas de tipo de aplicación
                all_pkg_str = " ".join(pkgs).lower()
                patterns = []
                if "servlet" in all_pkg_str or "filter" in all_pkg_str:     patterns.append("Servlet/Filter")
                if "javax.ws.rs" in all_pkg_str or "jakarta.ws.rs" in all_pkg_str: patterns.append("JAX-RS REST")
                if "ejb" in all_pkg_str:                                      patterns.append("EJB")
                if "jpa" in all_pkg_str or "hibernate" in all_pkg_str:       patterns.append("JPA/Hibernate")
                if "spring" in all_pkg_str:                                   patterns.append("Spring")
                if "dao" in all_pkg_str or "repository" in all_pkg_str:      patterns.append("DAO/Repository")
                if "kafka" in all_pkg_str or "messaging" in all_pkg_str:     patterns.append("Messaging")
                if patterns:
                    lines.append(f"  DETECTED_PATTERNS: {', '.join(patterns)}")

            # ── 3. Dependencias JAR con versión y CVE check ───────────────────
            lib_jars = [e for e in all_entries if
                        (e.startswith("WEB-INF/lib/") or e.startswith("lib/")
                         or "APP-INF/lib/" in e or "BOOT-INF/lib/" in e)
                        and e.endswith(".jar")]

            if lib_jars:
                lines.append(f"\n=== DEPENDENCIAS ({len(lib_jars)} JARs) ===")
                cve_hits = []
                for jar_entry in sorted(lib_jars):
                    basename = jar_entry.rsplit("/", 1)[-1]
                    artifact, ver_from_name = _parse_jar_name(basename)
                    # Intentar versión más precisa desde MANIFEST interno (solo para JARs pequeños)
                    jar_info = zf.getinfo(jar_entry)
                    ver = ver_from_name
                    if jar_info.file_size < 5 * 1024 * 1024:  # solo < 5 MB para no bloquear
                        manifest_ver = _read_jar_manifest_version(zf, jar_entry)
                        if manifest_ver:
                            ver = manifest_ver
                    # Buscar CVEs
                    hits = []
                    for cve_artifact, cve_list in _JAVA_CVE_MAP.items():
                        if artifact.lower() == cve_artifact or artifact.lower().startswith(cve_artifact):
                            for (lo, hi, cve_id, sev, desc) in cve_list:
                                if ver and _ver_in_range(ver, lo, hi):
                                    hits.append(f"[{sev}] {cve_id}: {desc}")
                                    cve_hits.append((basename, cve_id, sev, desc))
                    ver_str = f" v{ver}" if ver else ""
                    cve_str = f" ⚠ {'; '.join(hits)}" if hits else ""
                    lines.append(f"  {artifact}{ver_str}{cve_str}")

                if cve_hits:
                    lines.append(f"\n=== CVEs DETECTADOS EN DEPENDENCIAS ({len(cve_hits)}) ===")
                    for (jar, cve_id, sev, desc) in cve_hits:
                        lines.append(f"  [{sev}] {jar} → {cve_id}: {desc}")

            # ── 4. pom.xml — dependencias declaradas ──────────────────────────
            pom_files = [e for e in all_entries if e.endswith("pom.xml")]
            for pom_path in pom_files[:1]:
                raw = zf.read(pom_path).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                if root is not None:
                    lines.append(f"\n=== POM.XML ===")
                    MVN = "http://maven.apache.org/POM/4.0.0"
                    for tag in ["groupId", "artifactId", "version", "packaging"]:
                        el = root.find(f"{{{MVN}}}{tag}")
                        if el is not None and el.text:
                            lines.append(f"  {tag.upper()}: {el.text}")
                    java_ver_prop = root.find(f".//{{{MVN}}}maven.compiler.source")
                    if java_ver_prop is not None and java_ver_prop.text:
                        lines.append(f"  JAVA_SOURCE_VERSION: {java_ver_prop.text}")
                    deps = root.findall(f"{{{MVN}}}dependencies/{{{MVN}}}dependency")
                    if deps:
                        lines.append(f"  DECLARED_DEPENDENCIES ({len(deps)}):")
                        for dep in deps[:40]:
                            g   = dep.findtext(f"{{{MVN}}}groupId", "")
                            a   = dep.findtext(f"{{{MVN}}}artifactId", "")
                            v   = dep.findtext(f"{{{MVN}}}version", "?")
                            sc  = dep.findtext(f"{{{MVN}}}scope", "compile")
                            lines.append(f"    {g}:{a}:{v} [{sc}]")

            # ── 5. web.xml — análisis profundo ────────────────────────────────
            webxml_list = [e for e in all_entries if e.endswith("WEB-INF/web.xml")]
            for wxml in webxml_list[:1]:
                raw = zf.read(wxml).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                lines.append("\n=== WEB-INF/web.xml ===")
                if root is not None:
                    dn = root.find(".//{*}display-name")
                    if dn is not None and dn.text:
                        lines.append(f"  APP_NAME: {dn.text}")
                    ver_attr = root.get("version", "")
                    if ver_attr:
                        lines.append(f"  SERVLET_SPEC: {ver_attr}")
                    # Servlets y URL mappings
                    servlets  = [s.text for s in root.findall(".//{*}servlet-name") if s.text]
                    mappings  = [m.text for m in root.findall(".//{*}url-pattern") if m.text]
                    filters   = [f.text for f in root.findall(".//{*}filter-name") if f.text]
                    listeners = [l.text for l in root.findall(".//{*}listener-class") if l.text]
                    if servlets:  lines.append(f"  SERVLETS ({len(servlets)}): {', '.join(servlets[:10])}")
                    if filters:   lines.append(f"  FILTERS ({len(filters)}): {', '.join(filters[:10])}")
                    if listeners: lines.append(f"  LISTENERS: {', '.join(listeners[:8])}")
                    if mappings:  lines.append(f"  URL_PATTERNS: {', '.join(mappings[:15])}")
                    # Security
                    sec_constraints = root.findall(".//{*}security-constraint")
                    sec_roles = [r.text for r in root.findall(".//{*}role-name") if r.text]
                    auth_method = root.findtext(".//{*}auth-method", "")
                    timeout = root.findtext(".//{*}session-timeout", "")
                    if sec_constraints: lines.append(f"  SECURITY_CONSTRAINTS: {len(sec_constraints)}")
                    if sec_roles:       lines.append(f"  SECURITY_ROLES: {', '.join(sec_roles)}")
                    if auth_method:     lines.append(f"  AUTH_METHOD: {auth_method}")
                    if timeout:         lines.append(f"  SESSION_TIMEOUT_MIN: {timeout}")
                    # Context params (Spring ContextLoaderListener, etc.)
                    ctx_params = {p.findtext(".//{*}param-name",""): p.findtext(".//{*}param-value","")
                                  for p in root.findall(".//{*}context-param")}
                    for k, v in list(ctx_params.items())[:8]:
                        if k:
                            lines.append(f"  CONTEXT_PARAM {k}: {str(v)[:120]}")
                else:
                    lines.append(f"  RAW_SNIPPET: {raw[:300]}")

            # ── 6. application.xml (EAR) ──────────────────────────────────────
            for axml in [e for e in all_entries if e.endswith("META-INF/application.xml")][:1]:
                raw = zf.read(axml).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                lines.append("\n=== META-INF/application.xml (EAR) ===")
                if root is not None:
                    dn = root.find(".//{*}display-name")
                    if dn is not None and dn.text:
                        lines.append(f"  EAR_NAME: {dn.text}")
                    web_mods = [w.findtext(".//{*}web-uri","") for w in root.findall(".//{*}web")]
                    ejb_mods = [e.text for e in root.findall(".//{*}ejb") if e.text]
                    if web_mods: lines.append(f"  WEB_MODULES: {', '.join(web_mods)}")
                    if ejb_mods: lines.append(f"  EJB_MODULES: {', '.join(ejb_mods)}")

            # ── 7. ejb-jar.xml ────────────────────────────────────────────────
            for epath in [e for e in all_entries if e.endswith("ejb-jar.xml")][:3]:
                raw = zf.read(epath).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                if root is not None:
                    ejb_names    = [b.text for b in root.findall(".//{*}ejb-name") if b.text]
                    ejb_classes  = [b.text for b in root.findall(".//{*}ejb-class") if b.text]
                    session_types= [b.text for b in root.findall(".//{*}session-type") if b.text]
                    lines.append(f"\n=== {epath} ===")
                    if ejb_names:    lines.append(f"  EJB_BEANS ({len(ejb_names)}): {', '.join(ejb_names[:12])}")
                    if ejb_classes:  lines.append(f"  EJB_CLASSES: {', '.join(ejb_classes[:8])}")
                    if session_types:lines.append(f"  SESSION_TYPES: {', '.join(set(session_types))}")

            # ── 8. persistence.xml (JPA) ──────────────────────────────────────
            for pxml in [e for e in all_entries if e.endswith("persistence.xml")][:1]:
                raw = zf.read(pxml).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                lines.append("\n=== persistence.xml (JPA) ===")
                if root is not None:
                    units = root.findall(".//{*}persistence-unit")
                    for u in units[:4]:
                        name     = u.get("name", "?")
                        tx_type  = u.get("transaction-type", "")
                        provider = u.findtext(".//{*}provider", "")
                        props    = {p.get("name",""): p.get("value","")
                                    for p in u.findall(".//{*}property")}
                        lines.append(f"  PERSISTENCE_UNIT: {name} [tx={tx_type}]")
                        if provider: lines.append(f"    PROVIDER: {provider}")
                        for k, v in props.items():
                            if any(kw in k.lower() for kw in ["url","dialect","ddl","show","driver"]):
                                safe_v = re.sub(r'(?i)(password|secret|pwd)[^;]*', '[REDACTED]', v)
                                lines.append(f"    {k}: {safe_v[:120]}")

            # ── 9. Spring XML configs ─────────────────────────────────────────
            spring_xmls = [e for e in all_entries if
                           ("applicationContext" in e or "spring" in e.lower() or "beans" in e.lower())
                           and e.endswith(".xml")]
            for sxml in spring_xmls[:3]:
                raw = zf.read(sxml).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                lines.append(f"\n=== {sxml} ===")
                if root is not None:
                    beans = root.findall(".//{*}bean")
                    datasources = [b for b in beans if "datasource" in b.get("id","").lower()
                                   or "datasource" in b.get("class","").lower()]
                    tx_managers = [b for b in beans if "transaction" in b.get("id","").lower()]
                    lines.append(f"  SPRING_BEANS: {len(beans)}")
                    if datasources:
                        for ds in datasources[:2]:
                            url_prop = ds.find(".//{*}property[@name='url']")
                            drv_prop = ds.find(".//{*}property[@name='driverClassName']")
                            url = url_prop.get("value","") if url_prop is not None else ""
                            drv = drv_prop.get("value","") if drv_prop is not None else ""
                            safe_url = re.sub(r'(?i)(password|secret|pwd)[^&;]*', '[REDACTED]', url)
                            lines.append(f"  DATASOURCE: {ds.get('id','?')} url={safe_url[:100]} driver={drv}")
                    if tx_managers:
                        lines.append(f"  TX_MANAGERS: {', '.join(b.get('id','?') for b in tx_managers[:3])}")
                    # Imports de seguridad
                    sec_imports = [e for e in raw.lower().split() if "security" in e and "http" in e]
                    if sec_imports:
                        lines.append(f"  SPRING_SECURITY_CONFIG: detected")

            # ── 10. Struts config ─────────────────────────────────────────────
            struts_xmls = [e for e in all_entries if "struts" in e.lower() and e.endswith(".xml")]
            for sxml in struts_xmls[:2]:
                raw = zf.read(sxml).decode("utf-8", errors="replace")
                root = _parse_xml_safe(raw)
                lines.append(f"\n=== {sxml} (Struts) ===")
                if root is not None:
                    actions = root.findall(".//{*}action")
                    packages = root.findall(".//{*}package")
                    lines.append(f"  STRUTS_ACTIONS: {len(actions)}")
                    lines.append(f"  STRUTS_PACKAGES: {len(packages)}")
                    for a in actions[:10]:
                        lines.append(f"    action: name={a.get('name','')} class={a.get('class','')[:60]}")

            # ── 11. Log4j / Logback configs ───────────────────────────────────
            log_cfgs = [e for e in all_entries if
                        any(n in e.lower() for n in ["log4j","logback"]) and
                        e.endswith((".xml",".properties",".json",".yaml",".yml"))]
            if log_cfgs:
                lines.append(f"\n=== LOGGING CONFIG ===")
                for lc in log_cfgs[:3]:
                    lines.append(f"  {lc}")
                    try:
                        raw = zf.read(lc).decode("utf-8", errors="replace")
                        # Detectar appenders con sockets (riesgo Log4Shell)
                        if "socketappender" in raw.lower() or "jndi" in raw.lower():
                            lines.append(f"    ⚠ RISK: SocketAppender / JNDI reference detectado")
                        if "smtpappender" in raw.lower():
                            lines.append(f"    INFO: SMTPAppender detectado (posible leak de info)")
                    except Exception:
                        pass

            # ── 12. Server-specific descriptors ──────────────────────────────
            server_descriptors = {
                "jboss-web.xml":   "JBoss/WildFly",
                "weblogic.xml":    "WebLogic",
                "weblogic-ejb-jar.xml": "WebLogic EJB",
                "ibm-web-bnd.xml": "WebSphere",
                "glassfish-web.xml": "GlassFish",
                "context.xml":     "Tomcat Context",
                "jboss-ejb3.xml":  "JBoss EJB3",
            }
            found_descriptors = []
            for entry in all_entries:
                bname = entry.rsplit("/", 1)[-1].lower()
                if bname in server_descriptors:
                    found_descriptors.append(f"{server_descriptors[bname]} ({entry})")
            if found_descriptors:
                lines.append(f"\n=== SERVER-SPECIFIC DESCRIPTORS ===")
                for fd in found_descriptors:
                    lines.append(f"  {fd}")

            # ── 13. Properties / YAML (.yml) con JDBC / datasources / profiles ──────────
            prop_files = [e for e in all_entries
                          if e.endswith((".properties", ".yml", ".yaml")) and "pom" not in e and "META-INF" not in e]
            if prop_files:
                lines.append(f"\n=== ARCHIVOS DE CONFIGURACIÓN Y PERFILES ({len(prop_files)}) ===")
                for pf in prop_files[:10]:
                    try:
                        content = zf.read(pf).decode("utf-8", errors="replace")
                        relevant = []
                        for ln in content.splitlines():
                            ln_low = ln.lower()
                            if any(kw in ln_low for kw in ["url","host","port","driver","datasource",
                                                            "server","endpoint","provider","dialect","profile","active"]):
                                if not any(sk in ln_low for sk in ["password","secret","pwd","token","key"]):
                                    relevant.append(ln.strip()[:120])
                        if relevant:
                            lines.append(f"  {pf}:")
                            for r in relevant[:8]:
                                lines.append(f"    {r}")
                    except Exception:
                        pass

            # ── 14. EAR: módulos anidados ─────────────────────────────────────
            if ext == "ear":
                nested = [e for e in all_entries
                          if e.endswith((".war", ".jar")) and "/" not in e.lstrip("/")]
                if nested:
                    lines.append(f"\n=== MÓDULOS ANIDADOS EN EAR ({len(nested)}) ===")
                    for n in nested[:15]:
                        info = zf.getinfo(n)
                        lines.append(f"  {n} ({info.file_size // 1024} KB)")

            # ── 15. Análisis de bytecode — roles, smells, SQL ─────────────────
            class_entries = [e for e in all_entries if e.endswith(".class")]
            analyzed: list[dict] = []
            all_smells: dict[str, list[str]] = {}   # category → [detail]
            all_sql: list[str] = []
            all_urls: list[str] = []
            role_summary: dict[str, int] = {}

            # Analizar hasta 200 clases (las más grandes primero = más lógica de negocio)
            classes_to_scan = sorted(
                class_entries,
                key=lambda e: zf.getinfo(e).file_size,
                reverse=True
            )[:200]

            for ce in classes_to_scan:
                try:
                    cb = zf.read(ce)
                    strings = _scan_class_bytecode(cb)
                    result = _classify_and_analyze_class(ce, strings)
                    if result:
                        analyzed.append(result)
                        for role in result["roles"]:
                            role_summary[role] = role_summary.get(role, 0) + 1
                        for smell in result["smells"]:
                            all_smells.setdefault(smell["category"], [])
                            if smell["detail"] not in all_smells[smell["category"]]:
                                all_smells[smell["category"]].append(smell["detail"])
                        all_sql.extend(result["sql_found"])
                        all_urls.extend(result["urls_found"])
                except Exception:
                    continue

            if role_summary:
                lines.append(f"\n=== RESUMEN DE CLASES ANALIZADAS ({len(class_entries)} total, {len(analyzed)} con señales) ===")
                for role, count in sorted(role_summary.items(), key=lambda x: -x[1]):
                    migration = _MIGRATION_MAP.get(role, "")
                    lines.append(f"  {role}: {count} clases  {migration}")

            if analyzed:
                lines.append(f"\n=== CLASES CON TRANSFORMACIÓN REQUERIDA (top {min(len(analyzed),30)}) ===")
                for cls in analyzed[:30]:
                    roles_str = ", ".join(cls["roles"]) if cls["roles"] else "Clase de negocio"
                    hints_str = " | ".join(cls["migration_hints"][:2])
                    lines.append(f"  [{roles_str}] {cls['class']}")
                    if hints_str:
                        lines.append(f"    MIGRACIÓN: {hints_str}")
                    for smell in cls["smells"][:3]:
                        lines.append(f"    ⚠ {smell['category']}: {smell['detail']}")
                    for sql in cls["sql_found"][:2]:
                        lines.append(f"    SQL: {sql}")

            if all_smells:
                lines.append(f"\n=== ANTIPATRONES DE CÓDIGO DETECTADOS ===")
                for category, details in all_smells.items():
                    lines.append(f"  [{category}]")
                    for d in details[:2]:
                        lines.append(f"    {d}")

            if all_sql:
                unique_sql = list(dict.fromkeys(all_sql))[:10]
                lines.append(f"\n=== SQL HARDCODEADO ENCONTRADO ({len(unique_sql)} únicos) ===")
                for sql in unique_sql:
                    lines.append(f"  {sql[:120]}")

            if all_urls:
                unique_urls = list(dict.fromkeys(all_urls))[:10]
                lines.append(f"\n=== URLs / JDBC ENCONTRADAS EN CÓDIGO ===")
                for url in unique_urls:
                    # No mostrar si contiene password
                    safe = re.sub(r'(?i)(password|pwd|secret)[^@&;]*', '[REDACTED]', url)
                    lines.append(f"  {safe}")

    except zipfile.BadZipFile:
        lines.append("ERROR: El archivo no es un ZIP/JAR válido")
    except Exception as e:
        lines.append(f"ERROR_PARSING: {str(e)[:200]}")

    return "\n".join(lines)



_ALLOWED_ARTIFACT_EXTENSIONS = {"jar", "war", "ear"}
_ALLOWED_COMPRESSED_EXTENSIONS = {"zip", "gz", "tgz"}
_MAX_ARTIFACT_SIZE = 100 * 1024 * 1024  # 100 MB (comprimido puede ser grande)


def _decompress_to_artifact(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    """
    Si el archivo es un contenedor comprimido (.zip, .tar.gz, .tgz, .gz),
    extrae el primer EAR/WAR/JAR que encuentre y lo retorna junto a su nombre.
    Si ya es un artefacto Java directo, lo retorna tal cual.
    Retorna (artifact_bytes, artifact_filename).
    """
    import gzip
    import tarfile

    name_lower = filename.lower()

    # ── .tar.gz / .tgz ──────────────────────────────────────────────────────
    if name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
        try:
            with tarfile.open(fileobj=io.BytesIO(file_bytes), mode="r:gz") as tf:
                members = [m for m in tf.getmembers()
                           if m.name.lower().endswith((".ear", ".war", ".jar")) and m.size > 0]
                if not members:
                    raise HTTPException(422, "No se encontró ningún EAR/WAR/JAR dentro del tar.gz")
                # Preferir EAR > WAR > JAR
                members.sort(key=lambda m: ({"ear": 0, "war": 1, "jar": 2}.get(m.name.rsplit(".", 1)[-1].lower(), 3), m.size * -1))
                chosen = members[0]
                f = tf.extractfile(chosen)
                if not f:
                    raise HTTPException(422, f"No se pudo leer {chosen.name} del archivo")
                return f.read(), chosen.name.rsplit("/", 1)[-1]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(422, f"Error descomprimiendo tar.gz: {str(e)[:120]}")

    # ── .gz (solo un archivo, e.g. myapp.war.gz) ────────────────────────────
    if name_lower.endswith(".gz"):
        inner_name = filename[:-3]  # quitar .gz → myapp.war
        inner_ext = inner_name.rsplit(".", 1)[-1].lower() if "." in inner_name else ""
        if inner_ext not in _ALLOWED_ARTIFACT_EXTENSIONS:
            raise HTTPException(422, f"El archivo .gz no contiene un artefacto Java reconocido (encontrado: .{inner_ext})")
        try:
            return gzip.decompress(file_bytes), inner_name
        except Exception as e:
            raise HTTPException(422, f"Error descomprimiendo .gz: {str(e)[:120]}")

    # ── .zip ─────────────────────────────────────────────────────────────────
    if name_lower.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                candidates = [e for e in zf.namelist()
                              if e.lower().endswith((".ear", ".war", ".jar"))
                              and not e.startswith("__MACOSX")
                              and zf.getinfo(e).file_size > 0]
                if not candidates:
                    raise HTTPException(422, "No se encontró ningún EAR/WAR/JAR dentro del ZIP")
                # Preferir EAR > WAR > JAR; en empate, el más grande
                candidates.sort(key=lambda e: (
                    {"ear": 0, "war": 1, "jar": 2}.get(e.rsplit(".", 1)[-1].lower(), 3),
                    -zf.getinfo(e).file_size
                ))
                chosen = candidates[0]
                logger.info("[artifact] ZIP: extrayendo %s", chosen)
                return zf.read(chosen), chosen.rsplit("/", 1)[-1]
        except HTTPException:
            raise
        except zipfile.BadZipFile:
            raise HTTPException(422, "El archivo ZIP está corrupto o no es un ZIP válido")
        except Exception as e:
            raise HTTPException(422, f"Error descomprimiendo ZIP: {str(e)[:120]}")

    # ── Ya es un artefacto Java directo ──────────────────────────────────────
    return file_bytes, filename


@app.post("/analyze/artifact")
@limiter.limit("20/hour;3/minute")
async def analyze_artifact(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _user: str = Depends(verify_auth)
):
    """
    Recibe un artefacto Java (EAR/WAR/JAR) o un contenedor comprimido
    (.zip, .tar.gz, .tgz, archivo.war.gz) con el artefacto dentro.
    Extrae el inventario y lanza el análisis con 4 agentes.
    """
    filename = file.filename or "artifact.jar"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    # .tar.gz tiene dos extensiones — tratarlo como un caso especial
    if filename.lower().endswith(".tar.gz"):
        ext = "tar.gz"

    allowed_all = _ALLOWED_ARTIFACT_EXTENSIONS | _ALLOWED_COMPRESSED_EXTENSIONS | {"tar.gz"}
    if ext not in allowed_all:
        raise HTTPException(400,
            f"Tipo no permitido (.{ext}). Se aceptan: JAR, WAR, EAR, ZIP, GZ, TAR.GZ")

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_ARTIFACT_SIZE:
        raise HTTPException(413, f"Archivo demasiado grande. Máximo: {_MAX_ARTIFACT_SIZE // (1024*1024)} MB")
    if len(file_bytes) == 0:
        raise HTTPException(400, "El archivo está vacío")

    logger.info("[artifact] Recibido %s (%d KB) por %s", filename, len(file_bytes) // 1024, _user)

    # Descomprimir si es necesario
    artifact_bytes, artifact_name = _decompress_to_artifact(file_bytes, filename)
    if artifact_name != filename:
        logger.info("[artifact] Descomprimido: %s → %s (%d KB)", filename, artifact_name, len(artifact_bytes) // 1024)

    inventory = _extract_artifact_inventory(artifact_bytes, artifact_name)
    logger.info("[artifact] Inventario extraído: %d chars", len(inventory))
    # Agregar contexto del archivo original si vino comprimido
    if artifact_name != filename:
        inventory = f"COMPRESSED_CONTAINER: {filename}\nEXTRACTED_ARTIFACT: {artifact_name}\n\n" + inventory

    data_hash = _cache_key(inventory)
    job_id = str(uuid.uuid4())
    _update_job_status(job_id, "pending", "Inventario extraído, iniciando análisis con 4 agentes...")
    background_tasks.add_task(_run_bedrock_job, job_id, inventory, artifact_name, data_hash, "general")

    return {
        "status": "pending",
        "method": "async",
        "job_id": job_id,
        "artifact_name": artifact_name,           # nombre del artefacto Java (ya descomprimido)
        "container_name": filename,               # nombre del archivo original subido
        "was_compressed": artifact_name != filename,
        "artifact_size_kb": len(artifact_bytes) // 1024,
        "container_size_kb": len(file_bytes) // 1024,
        "inventory_preview": inventory,
    }


# ─── PDF Report Generator ─────────────────────────────────────────────────────
@app.get("/report/{scan_id}")
async def generate_pdf_report(scan_id: str, _user: str = Depends(verify_auth)):
    """Genera un informe PDF profesional del análisis de modernización."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(status_code=500, detail="fpdf2 no instalado. Ejecuta: pip install fpdf2")

    conn, _ = _get_db()
    row = conn.execute(
        "SELECT hostname, timestamp, raw_inventory, bedrock_blueprint FROM scan_history WHERE id=?",
        (scan_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scan no encontrado")

    hostname, timestamp, raw_inventory, bp_json = row
    bp = {}
    try:
        bp = json.loads(bp_json or "{}")
    except Exception:
        pass

    cn  = bp.get("cloudnative", {})
    biz = bp.get("business", {})
    sec = bp.get("security", {})
    mig = bp.get("migration", {})
    ca  = bp.get("current_architecture", {})
    date_str = (timestamp or "")[:10]

    # ── Helpers ──────────────────────────────────────────────────────────────
    C_DARK   = (15, 20, 40)
    C_BLUE   = (0, 163, 255)
    C_GREEN  = (0, 230, 118)
    C_RED    = (255, 65, 108)
    C_YELLOW = (255, 190, 50)
    C_LGRAY  = (230, 234, 240)
    C_MGRAY  = (100, 110, 130)
    C_WHITE  = (255, 255, 255)

    class MFReport(FPDF):
        def header(self):
            if self.page_no() == 1:
                return
            self.set_fill_color(*C_DARK)
            self.rect(0, 0, 210, 12, 'F')
            self.set_font("Helvetica", "B", 7)
            self.set_text_color(*C_BLUE)
            self.set_xy(10, 3)
            self.cell(0, 6, "MODERNIZATION FACTORY  |  Informe Confidencial", ln=False)
            self.set_text_color(*C_MGRAY)
            self.set_xy(0, 3)
            self.cell(200, 6, hostname or "", align="R")
            self.ln(12)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*C_MGRAY)
            self.cell(0, 8, f"Pagina {self.page_no()}  |  Generado {date_str}  |  Confidencial", align="C")

        def section_title(self, title, color=None):
            clr = color or C_BLUE
            self.set_fill_color(*clr)
            self.rect(10, self.get_y(), 3, 6, 'F')
            self.set_xy(15, self.get_y())
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*C_DARK)
            self.cell(0, 6, title, ln=True)
            self.ln(2)

        def kv_row(self, key, val, key_color=None, val_color=None):
            kc = key_color or C_MGRAY
            vc = val_color or C_DARK
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*kc)
            self.cell(55, 5, key, ln=False)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*vc)
            self.multi_cell(0, 5, str(val)[:200])

        def badge(self, text, bg, fg=(255,255,255)):
            self.set_fill_color(*bg)
            self.set_text_color(*fg)
            self.set_font("Helvetica", "B", 7)
            self.cell(len(text)*2.3 + 4, 5, text, border=0, fill=True, ln=False)
            self.set_text_color(*C_DARK)

        def safe_text(self, txt):
            """Convierte texto a latin-1 safe eliminando chars no soportados."""
            if not txt:
                return ""
            return txt.encode("latin-1", errors="replace").decode("latin-1")

    pdf = MFReport()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(10, 15, 10)

    # ════════════════════════════════════════════════════════════
    # PORTADA
    # ════════════════════════════════════════════════════════════
    pdf.add_page()
    # Fondo oscuro
    pdf.set_fill_color(*C_DARK)
    pdf.rect(0, 0, 210, 297, 'F')
    # Banda azul superior
    pdf.set_fill_color(*C_BLUE)
    pdf.rect(0, 0, 210, 4, 'F')
    # Titulo principal
    pdf.set_y(60)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 14, "MODERNIZATION", align="C", ln=True)
    pdf.set_font("Helvetica", "", 28)
    pdf.set_text_color(*C_BLUE)
    pdf.cell(0, 14, "FACTORY", align="C", ln=True)
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*C_LGRAY)
    pdf.cell(0, 8, "Informe de Modernizacion Cloud", align="C", ln=True)
    # Separador
    pdf.set_draw_color(*C_BLUE)
    pdf.set_line_width(0.8)
    pdf.line(40, pdf.get_y() + 4, 170, pdf.get_y() + 4)
    pdf.ln(12)
    # Hostname
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 10, pdf.safe_text(hostname or "Servidor"), align="C", ln=True)
    pdf.ln(4)
    # Fecha y score
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*C_MGRAY)
    pdf.cell(0, 7, f"Fecha: {date_str}", align="C", ln=True)
    coupling = ca.get("coupling_score")
    if coupling is not None:
        sev_clr = C_RED if coupling >= 7 else (C_YELLOW if coupling >= 4 else C_GREEN)
        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*sev_clr)
        pdf.cell(0, 8, f"Score de Acoplamiento: {coupling}/10", align="C", ln=True)
    risk = biz.get("risk_score")
    if risk is not None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*C_MGRAY)
        pdf.cell(0, 7, f"Riesgo Financiero: {risk}/10", align="C", ln=True)
    # Pie portada
    pdf.set_y(260)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*C_MGRAY)
    pdf.cell(0, 6, "Documento Confidencial — Solo para uso interno", align="C", ln=True)
    pdf.cell(0, 6, "Generado por Modernization Factory v5.0 con AWS Bedrock Nova Lite", align="C", ln=True)

    # ════════════════════════════════════════════════════════════
    # PAG 2 — RESUMEN EJECUTIVO
    # ════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_fill_color(*C_WHITE)
    pdf.rect(0, 0, 210, 297, 'F')

    pdf.section_title("1. Resumen Ejecutivo")
    summary = bp.get("executive_summary") or bp.get("summary") or ""
    if not summary and ca:
        summary = ca.get("summary", "")
    if summary:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*C_DARK)
        pdf.multi_cell(0, 5, pdf.safe_text(str(summary)[:800]))
    pdf.ln(4)

    # Métricas clave en grid
    pdf.section_title("Metricas Clave")
    metrics = [
        ("Acoplamiento", f"{ca.get('coupling_score','—')}/10"),
        ("Riesgo Financiero", f"{biz.get('risk_score','—')}/10"),
        ("CVEs Criticos", str(len([c for c in (sec.get("cves_found") or []) if c.get("severity") == "CRITICO"]))),
        ("Estrategia Recomendada", mig.get("strategy", ca.get("strategy_recommendation", "—"))),
        ("Target", mig.get("target_platform", "ECS Fargate / Spring Boot 3.2 + Java 21")),
    ]
    for k, v in metrics:
        pdf.kv_row(k + ":", v)
    pdf.ln(4)

    # CVEs top
    cves = sec.get("cves_found") or []
    if cves:
        pdf.section_title("Top CVEs Detectados", C_RED)
        for cve in cves[:5]:
            sev = cve.get("severity", "MEDIO")
            bg = C_RED if sev == "CRITICO" else (C_YELLOW if sev == "ALTO" else C_MGRAY)
            pdf.set_x(10)
            pdf.badge(sev, bg)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*C_DARK)
            pdf.cell(30, 5, pdf.safe_text(cve.get("cve_id", "")), ln=False)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 5, pdf.safe_text(cve.get("description", "")[:120]))

    # ════════════════════════════════════════════════════════════
    # PAG 3 — PLAN DE MIGRACIÓN
    # ════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_fill_color(*C_WHITE)
    pdf.rect(0, 0, 210, 297, 'F')

    pdf.section_title("2. Plan de Migracion — 4 Sprints")
    sprints = mig.get("sprints") or bp.get("sprints") or {}
    sprint_labels = [
        ("sprint_0", "SPRINT 0 — Analisis y Seguridad",    C_RED),
        ("sprint_1", "SPRINT 1 — Contenedores y CI/CD",    C_YELLOW),
        ("sprint_2", "SPRINT 2 — Refactorizacion",         C_BLUE),
        ("sprint_3", "SPRINT 3 — Corte a Cloud",           C_GREEN),
    ]
    for key, label, clr in sprint_labels:
        tasks = sprints.get(key) or []
        if not tasks:
            continue
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*clr)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(0, 6, f"  {label}", fill=True, ln=True)
        pdf.set_text_color(*C_DARK)
        pdf.set_font("Helvetica", "", 8)
        for task in tasks[:8]:
            if isinstance(task, dict):
                title   = task.get("title") or task.get("task") or ""
                effort  = task.get("effort") or ""
                owner   = task.get("owner") or ""
                desc    = task.get("description") or ""
                header  = f"{title}{' ['+effort+']' if effort else ''}{' ('+owner+')' if owner else ''}"
                task_text = header + (f": {desc}" if desc else "")
            else:
                task_text = str(task)
            pdf.set_x(14)
            pdf.cell(4, 5, chr(149), ln=False)
            pdf.multi_cell(0, 5, pdf.safe_text(task_text[:200]))
        pdf.ln(2)

    blocking = mig.get("blocking_issues") or cn.get("blocking_issues") or []
    if blocking:
        pdf.ln(2)
        pdf.section_title("Bloqueadores Pre-Deploy", C_RED)
        for b in blocking[:5]:
            sev = b.get("severity", "MEDIO")
            bg = C_RED if sev == "CRITICO" else (C_YELLOW if sev == "ALTO" else C_MGRAY)
            pdf.set_x(10)
            pdf.badge(sev, bg)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*C_DARK)
            pdf.multi_cell(0, 5, "  " + pdf.safe_text(b.get("issue", "")[:140]))

    # ════════════════════════════════════════════════════════════
    # PAG 4 — ARTEFACTOS IaC
    # ════════════════════════════════════════════════════════════
    if cn:
        pdf.add_page()
        pdf.set_fill_color(*C_WHITE)
        pdf.rect(0, 0, 210, 297, 'F')

        pdf.section_title("3. Artefactos Cloud-Native")

        # Violations 12-Factor
        violations = cn.get("twelve_factor_violations") or []
        if violations:
            pdf.section_title("Violaciones 12-Factor App", C_YELLOW)
            for v in violations[:6]:
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*C_YELLOW)
                pdf.cell(50, 4, pdf.safe_text(v.get("factor", "")[:40]), ln=False)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(*C_DARK)
                pdf.multi_cell(0, 4, pdf.safe_text(v.get("violation", "")[:140]))
            pdf.ln(2)

        # Dockerfile
        df = cn.get("dockerfile", "").replace("\\n", "\n")
        if df:
            pdf.section_title("Dockerfile (Multi-stage Distroless)")
            pdf.set_font("Courier", "", 6.5)
            pdf.set_fill_color(245, 246, 250)
            pdf.set_text_color(30, 40, 60)
            for line in df.split("\n")[:30]:
                pdf.set_x(10)
                pdf.cell(0, 4, pdf.safe_text(line[:120]), fill=True, ln=True)
            pdf.ln(2)

        # Healthchecks
        hc = cn.get("healthcheck_config") or {}
        if hc:
            pdf.section_title("Health Probes")
            for k, v in hc.items():
                pdf.kv_row(k.replace("_", " ").upper() + ":", v)
            pdf.ln(2)

        # Deployment commands
        cmds = cn.get("deployment_commands") or []
        if cmds:
            pdf.section_title("Comandos de Despliegue")
            pdf.set_font("Courier", "", 7)
            pdf.set_text_color(*C_DARK)
            for i, cmd in enumerate(cmds[:6], 1):
                pdf.set_x(10)
                pdf.cell(8, 5, f"{i}.", ln=False)
                pdf.multi_cell(0, 5, pdf.safe_text(cmd[:140]))

    # ════════════════════════════════════════════════════════════
    # PAG 5 — TCO / ROI
    # ════════════════════════════════════════════════════════════
    if biz and biz.get("tco_legacy"):
        pdf.add_page()
        pdf.set_fill_color(*C_WHITE)
        pdf.rect(0, 0, 210, 297, 'F')

        pdf.section_title("4. Analisis Financiero — TCO y ROI")

        fmt = lambda n: f"${int(n):,}" if n else "—"

        # TCO Legacy vs AWS en tabla
        leg = biz.get("tco_legacy", {})
        aws = biz.get("tco_aws", {})

        # Tabla header
        col_w = [80, 50, 50]
        pdf.set_fill_color(*C_DARK)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w[0], 6, "Componente", fill=True, border=1)
        pdf.cell(col_w[1], 6, "Legacy (anual)", fill=True, border=1, align="R")
        pdf.cell(col_w[2], 6, "AWS (mensual)", fill=True, border=1, align="R", ln=True)

        rows = [
            ("Infraestructura / Fargate",  leg.get("annual_licensing"),          aws.get("ecs_fargate_monthly")),
            ("Base de Datos / RDS",        leg.get("annual_labor_maintenance"),  aws.get("rds_aurora_serverless_monthly")),
            ("Seguridad / Secrets Mgr",    leg.get("annual_security_incidents_risk"), aws.get("secrets_manager_monthly")),
            ("Monitoreo / CloudWatch",     leg.get("annual_downtime_cost"),      aws.get("cloudwatch_monthly")),
        ]
        pdf.set_font("Helvetica", "", 8)
        for i, (label, l_val, a_val) in enumerate(rows):
            bg = (245, 246, 250) if i % 2 == 0 else C_WHITE
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*C_DARK)
            pdf.cell(col_w[0], 5, pdf.safe_text(label), fill=True, border=1)
            pdf.set_text_color(*C_RED)
            pdf.cell(col_w[1], 5, fmt(l_val), fill=True, border=1, align="R")
            pdf.set_text_color(0, 150, 80)
            pdf.cell(col_w[2], 5, fmt(a_val), fill=True, border=1, align="R", ln=True)

        pdf.ln(4)

        # ROI summary
        roi = biz.get("roi_analysis", {})
        pdf.section_title("ROI y Payback")
        roi_rows = [
            ("Ahorro Anual Estimado",   roi.get("annual_savings_usd")),
            ("ROI a 3 anos",            roi.get("roi_percentage_3yr")),
            ("Payback (meses)",         roi.get("payback_months")),
        ]
        for k, v in roi_rows:
            if v is not None:
                pdf.kv_row(k + ":", str(v), val_color=C_GREEN)
        pdf.ln(3)

        csuite = biz.get("c_suite_summary", "")
        if csuite:
            pdf.section_title("Resumen para C-Suite")
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*C_DARK)
            pdf.multi_cell(0, 5, pdf.safe_text(str(csuite)[:600]))

    # ════════════════════════════════════════════════════════════
    # OUTPUT
    # ════════════════════════════════════════════════════════════
    from io import BytesIO
    from starlette.responses import Response
    buf = BytesIO()
    pdf_bytes = pdf.output()
    safe_host = (hostname or "report").replace("/", "-").replace(" ", "_")
    filename = f"modernization_report_{safe_host}_{date_str}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ─── Migration Bundle Generator ───────────────────────────────────────────────
@app.get("/migration-bundle/{scan_id}")
async def download_migration_bundle(scan_id: str, _user: str = Depends(verify_auth)):
    """
    Genera un ZIP con todos los artefactos de migración listos para usar:
    Dockerfile, docker-compose, K8s manifests, Terraform, deploy scripts, runbooks.
    """
    import zipfile, io as _io

    conn, db_type = _get_conn()
    if db_type == "sqlite":
        conn.row_factory = sqlite3.Row
    ph = _ph(db_type)
    row = conn.execute(f"SELECT * FROM scan_history WHERE id = {ph}", (scan_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Scan no encontrado")

    d  = dict(row)
    bp = json.loads(d["bedrock_blueprint"] or "{}") if isinstance(d.get("bedrock_blueprint"), str) else {}
    cn = bp.get("cloudnative", {})
    hostname   = d.get("hostname", "app")
    date_str   = (d.get("timestamp") or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    app_name   = re.sub(r"[^a-z0-9]", "-", hostname.lower()).strip("-") or "app"

    def fix_newlines(text: str) -> str:
        return (text or "").replace("\\n", "\n").strip()

    # ── Archivos a incluir en el ZIP ──────────────────────────────────────────
    files: dict[str, str] = {}

    # Dockerfile
    dockerfile = fix_newlines(bp.get("dockerfile") or cn.get("dockerfile", ""))
    if not dockerfile:
        dockerfile = (
            f"# Dockerfile generado por Modernization Factory\n"
            f"FROM eclipse-temurin:21-jdk-alpine AS build\n"
            f"WORKDIR /app\nCOPY pom.xml .\nRUN mvn dependency:go-offline -q\n"
            f"COPY src ./src\nRUN mvn package -DskipTests -q\n\n"
            f"FROM gcr.io/distroless/java21-debian12\n"
            f"WORKDIR /app\nCOPY --from=build /app/target/*.war /app/app.war\n"
            f"EXPOSE 8080\n"
            f'ENTRYPOINT ["java","-Xmx512m","-XX:+UseContainerSupport","-XX:MaxRAMPercentage=75.0","-jar","/app/app.war"]\n'
        )
    files["Dockerfile"] = dockerfile

    # docker-compose.yml
    compose = fix_newlines(bp.get("docker_compose") or cn.get("docker_compose", ""))
    if not compose:
        compose = (
            f"version: '3.9'\nservices:\n  app:\n    build: .\n"
            f"    ports:\n      - '8080:8080'\n"
            f"    environment:\n      APP_ENV: production\n"
        )
    files["docker-compose.yml"] = compose

    # docker-compose.localstack.yml
    localstack = fix_newlines(cn.get("localstack_compose", ""))
    if localstack:
        files["docker-compose.localstack.yml"] = localstack

    # K8s manifests
    k8s_deploy  = fix_newlines(bp.get("k8s_deployment")  or cn.get("k8s_deployment", ""))
    k8s_service = fix_newlines(bp.get("k8s_service")      or cn.get("k8s_service", ""))
    k8s_hpa     = fix_newlines(bp.get("k8s_hpa")          or cn.get("k8s_hpa", ""))
    if k8s_deploy:
        files["k8s/deployment.yaml"] = k8s_deploy
    if k8s_service:
        files["k8s/service.yaml"] = k8s_service
    if k8s_hpa:
        files["k8s/hpa.yaml"] = k8s_hpa
    if k8s_deploy or k8s_service or k8s_hpa:
        files["k8s/kustomization.yaml"] = (
            f"apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:"
            + ("\n  - deployment.yaml" if k8s_deploy  else "")
            + ("\n  - service.yaml"    if k8s_service else "")
            + ("\n  - hpa.yaml"        if k8s_hpa     else "")
            + "\n"
        )

    # Terraform
    terraform = fix_newlines(
        bp.get("terraform_code") or cn.get("terraform_managed_services", "")
    )
    if terraform:
        files["terraform/main.tf"] = terraform
        files["terraform/variables.tf"] = (
            'variable "aws_region"   { type = string; default = "us-east-1" }\n'
            'variable "ecr_repo"     { type = string; description = "ECR repository URI" }\n'
            'variable "db_user"      { type = string; default = "appuser" }\n'
            'variable "db_password"  { type = string; sensitive = true }\n'
            'variable "db_secret_arn"{ type = string; default = "" }\n'
        )
        files["terraform/backend.tf"] = (
            '# Configura el backend remoto (opcional)\n'
            'terraform {\n'
            '  # backend "s3" {\n'
            f'  #   bucket = "{app_name}-terraform-state"\n'
            '  #   key    = "prod/terraform.tfstate"\n'
            '  #   region = "us-east-1"\n'
            '  # }\n'
            '}\n'
        )

    # Script de despliegue
    deploy_cmds = cn.get("deployment_commands") or []
    deploy_sh_lines = [
        "#!/bin/bash",
        "# deploy.sh — Script de despliegue generado por Modernization Factory",
        f"# Host: {hostname}  |  Fecha: {date_str}",
        "set -euo pipefail",
        "",
        'AWS_REGION="${AWS_REGION:-us-east-1}"',
        'ECR_REPO="${ECR_REPO:-}"',
        'IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")',
        "",
        "echo '🐳 Build imagen Docker...'",
        f"docker build -t {app_name}:$IMAGE_TAG .",
        "",
    ]
    if deploy_cmds:
        deploy_sh_lines += ["echo '🚀 Comandos de despliegue:'"] + [f"# {c}" for c in deploy_cmds]
    else:
        deploy_sh_lines += [
            "echo '📤 Push a ECR...'",
            'aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO',
            f'docker tag {app_name}:$IMAGE_TAG $ECR_REPO/{app_name}:$IMAGE_TAG',
            f'docker push $ECR_REPO/{app_name}:$IMAGE_TAG',
            "",
            "echo '🌍 Aplicar Terraform...'",
            "cd terraform && terraform init && terraform apply -auto-approve",
            "",
            "echo '⎈ Aplicar K8s manifests...'",
            "kubectl apply -k k8s/",
            f"kubectl rollout status deployment/{app_name}",
        ]
    deploy_sh_lines += ["", "echo '✅ Despliegue completado'"]
    files["scripts/deploy.sh"] = "\n".join(deploy_sh_lines) + "\n"

    # Healthcheck config como YAML
    hc = cn.get("healthcheck_config") or {}
    if hc:
        hc_lines = ["# health-probes.yaml — Configuración de Health Probes\n"]
        for k, v in hc.items():
            hc_lines.append(f"{k}: {v}")
        files["k8s/health-probes.txt"] = "\n".join(hc_lines) + "\n"

    # SRE Runbooks en Markdown
    runbooks = cn.get("sre_runbook") or []
    if runbooks:
        rb_md = [f"# SRE Runbooks — {hostname}\n", f"*Generado: {date_str}*\n"]
        for rb in runbooks:
            rb_md.append(f"\n## {rb.get('title', 'Runbook')}\n")
            if rb.get("trigger"):
                rb_md.append(f"**Trigger:** {rb['trigger']}\n")
            steps = rb.get("steps") or []
            if steps:
                rb_md.append("\n**Pasos:**\n")
                for i, s in enumerate(steps, 1):
                    rb_md.append(f"{i}. {s}")
        files["runbooks/sre-runbooks.md"] = "\n".join(rb_md) + "\n"

    # Violaciones 12-Factor
    violations = cn.get("twelve_factor_violations") or []
    if violations:
        viol_md = [f"# Violaciones 12-Factor App — {hostname}\n"]
        for v in violations:
            viol_md.append(f"\n## {v.get('factor', '')}")
            viol_md.append(f"**Violación:** {v.get('violation', '')}")
            if v.get("fix"):
                viol_md.append(f"**Fix:** {v['fix']}")
        files["docs/12-factor-violations.md"] = "\n".join(viol_md) + "\n"

    # README
    sprints = bp.get("sprints") or {}
    mig     = bp.get("migration") or {}
    strategy = mig.get("strategy") or bp.get("current_architecture", {}).get("strategy_recommendation", "Re-architect")
    readme = [
        f"# Migration Bundle — {hostname}",
        f"",
        f"**Generado:** {date_str}  |  **Estrategia:** {strategy}  |  **Target:** Spring Boot 3.2 + Java 21 + ECS Fargate",
        f"",
        f"## Contenido del Bundle",
        f"",
        f"| Archivo | Descripción |",
        f"|---------|-------------|",
        f"| `Dockerfile` | Multi-stage build con runtime distroless (sin shell, sin root) |",
        f"| `docker-compose.yml` | Entorno local de desarrollo |",
        f"| `docker-compose.localstack.yml` | Emulación offline de AWS con LocalStack |",
        f"| `k8s/` | Manifests Kubernetes: Deployment, Service, HPA, Kustomization |",
        f"| `terraform/` | VPC + ALB + ECS Fargate + RDS Aurora Serverless v2 |",
        f"| `scripts/deploy.sh` | Script de build y despliegue automatizado |",
        f"| `runbooks/` | Runbooks SRE para operación post-deploy |",
        f"| `docs/` | Violaciones 12-Factor y guías de modernización |",
        f"",
        f"## Inicio Rápido",
        f"",
        f"```bash",
        f"# 1. Probar localmente",
        f"docker-compose up -d",
        f"curl http://localhost:8080/actuator/health",
        f"",
        f"# 2. Emular AWS offline (LocalStack)",
        f"docker-compose -f docker-compose.localstack.yml up -d",
        f"",
        f"# 3. Desplegar en AWS",
        f"chmod +x scripts/deploy.sh && ./scripts/deploy.sh",
        f"```",
        f"",
        f"## Plan de Migración",
    ]
    for k in ["sprint_0", "sprint_1", "sprint_2", "sprint_3"]:
        tasks = sprints.get(k) or []
        if tasks:
            label = k.replace("_", " ").upper()
            readme.append(f"\n### {label}")
            for t in tasks[:6]:
                title = t.get("title") if isinstance(t, dict) else str(t)
                readme.append(f"- {title}")
    readme += ["", "---", f"*Modernization Factory v5.0 — AWS Bedrock Nova Lite*"]
    files["README.md"] = "\n".join(readme) + "\n"

    # ── Empaquetar en ZIP ─────────────────────────────────────────────────────
    zip_buf = _io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content.encode("utf-8"))
    zip_buf.seek(0)

    bundle_name = f"migration-bundle_{app_name}_{date_str}.zip"
    logger.info("Migration bundle generado para scan %s (%d archivos) por %s", scan_id[:8], len(files), _user)
    return Response(
        content=zip_buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{bundle_name}"'}
    )


# ─── Static Frontend ──────────────────────────────────────────────────────────
fabrica_dir = Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(fabrica_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
