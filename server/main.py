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
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security
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
    {"id": "amazon.nova-pro-v1:0",   "maxTokens": 5120, "label": "Nova Pro"},
    {"id": "amazon.nova-lite-v1:0",  "maxTokens": 5120, "label": "Nova Lite"},
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
) -> str:
    """Acepta JWT Bearer (frontend login) o X-API-KEY (Docker healthcheck / CLI)."""
    if creds and creds.scheme.lower() == "bearer":
        try:
            payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload["sub"]
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expirado — vuelve a iniciar sesión")
        except pyjwt.InvalidTokenError:
            raise HTTPException(401, "Token inválido")
    if api_key and api_key == os.getenv("API_KEY", "mf-api-key-2026"):
        return "api_key_user"
    raise HTTPException(401, "Autenticación requerida. Usa X-API-KEY o Bearer token.")

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

    # Migracion: agregar columnas nuevas si la tabla ya existia sin ellas
    if db_type == "sqlite":
        existing = {row[1] for row in c.execute("PRAGMA table_info(scan_history)")}
        for col, definition in [("model_used", "TEXT"), ("data_hash", "TEXT"), ("previous_scan_id", "TEXT")]:
            if col not in existing:
                c.execute(f"ALTER TABLE scan_history ADD COLUMN {col} {definition}")
                logger.info("Migracion: columna '%s' agregada a scan_history", col)
    else:
        # PostgreSQL: usar ADD COLUMN IF NOT EXISTS
        for col, definition in [("model_used", "TEXT"), ("data_hash", "TEXT"), ("previous_scan_id", "TEXT")]:
            c.execute(f"ALTER TABLE scan_history ADD COLUMN IF NOT EXISTS {col} {definition}")

    conn.commit()
    conn.close()
    logger.info("DB inicializada (%s)", "PostgreSQL" if DATABASE_URL else "SQLite")

init_db()

def _save_scan(scan_id, hostname, raw_data, ai_response, model_used, data_hash, previous_scan_id=None):
    conn, db_type = _get_conn()
    ph = _ph(db_type)
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

# ─── RAG — Recuperación por Similitud TF-IDF ─────────────────────────────────
def _rag_retrieve(inventory_text: str, top_k: int = 3) -> str:
    """
    Recupera los análisis más similares al inventario actual usando TF-IDF coseno.
    Retorna un string listo para inyectar en el prompt como <RAG_CONTEXT>.
    Sin dependencias externas pesadas: usa scikit-learn (TF-IDF + coseno).
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        conn, db_type = _get_conn()
        if db_type == "sqlite":
            conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, hostname, bedrock_blueprint, raw_inventory FROM scan_history "
            "WHERE bedrock_blueprint IS NOT NULL ORDER BY timestamp DESC LIMIT 80"
        ).fetchall()
        conn.close()

        if not rows or len(rows) < 2:
            return ""

        docs = []
        metas = []
        for r in rows:
            rd = dict(r)
            inv = (rd.get("raw_inventory") or "")[:8000]
            if inv.strip():
                docs.append(inv)
                metas.append(rd)

        if len(docs) < 2:
            return ""

        corpus = [inventory_text[:8000]] + docs
        vec = TfidfVectorizer(
            max_features=3000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1
        )
        tfidf = vec.fit_transform(corpus)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

        top_idx = np.argsort(sims)[::-1][:top_k]
        parts = []
        for i in top_idx:
            score = float(sims[i])
            if score < 0.08:   # umbral mínimo de relevancia
                continue
            meta = metas[i]
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

        header = f"Los siguientes {len(parts)} análisis anteriores son técnicamente similares. Úsalos como contexto para ser más específico:"
        return header + "\n\n" + "\n\n".join(parts)

    except ImportError:
        logger.warning("scikit-learn no instalado — RAG deshabilitado")
        return ""
    except Exception as e:
        logger.warning("RAG error: %s", e)
        return ""

# ─── Agentic Prompts ──────────────────────────────────────────────────────────
_AGENT_SECURITY_PROMPT = """
Eres un CISO senior y experto en seguridad cloud. Analiza el inventario dado y retorna ÚNICAMENTE JSON válido:
{{
  "security_findings": [
    {{"sev": "CRITICO|ALTO|MEDIO", "component": "nombre real", "cve": "CVE-XXXX o N/A",
      "description": "descripción técnica con versión exacta",
      "mitigation": "comando o config exacta para remediarlo"}}
  ],
  "critical_ports": ["puerto:servicio expuesto"],
  "eol_components": ["componente vX.Y — EoL desde YYYY"],
  "attack_surface": "descripción de superficie de ataque en 2 oraciones"
}}
"""

_AGENT_MIGRATION_PROMPT = """
Eres un Principal Cloud Architect de AWS. Recibes un inventario de servidor legacy junto con hallazgos de seguridad previos.
Retorna ÚNICAMENTE JSON válido con la estrategia de migración:
{{
  "migration_strategy": {{"approach": "lift-and-shift|re-architect|strangler-fig|hybrid",
    "rationale": "por qué este enfoque dado el stack",
    "total_weeks": 16, "phases": 4}},
  "sprints": {{
    "sprint_0": ["TAREA [Rol] [Esfuerzo]: descripción concreta"],
    "sprint_1": ["TAREA [Rol] [Esfuerzo]: descripción concreta"],
    "sprint_2": ["TAREA [Rol] [Esfuerzo]: descripción concreta"],
    "sprint_3": ["TAREA [Rol] [Esfuerzo]: descripción concreta"]
  }},
  "quick_wins": [
    {{"title": "acción concreta", "description": "qué hacer exactamente",
      "effort": "X días", "risk_reduction": "CVE o riesgo eliminado", "owner": "DevSecOps|SysAdmin|Dev"}}
  ],
  "risk_matrix": [
    {{"risk": "nombre con componente real", "cve": "CVE o N/A",
      "probability": "Alta|Media|Baja", "impact": "Crítico|Alto|Medio",
      "mitigation": "acción concreta"}}
  ]
}}
"""

_AGENT_CODE_PROMPT = """
Eres un Staff Engineer experto en refactoring de aplicaciones legacy hacia contenedores.
Retorna ÚNICAMENTE JSON válido:
{{
  "agent_analysis": "Análisis técnico en 4+ párrafos: stack detectado, vulnerabilidades, deuda técnica, estrategia de containerización recomendada",
  "code_remediation": [
    {{"file": "ruta/real/archivo.ext", "issue": "problema técnico preciso",
      "action": "cambio exacto requerido",
      "before": "fragmento actual (< 5 líneas)",
      "after": "fragmento corregido (< 5 líneas)",
      "effort": "X horas", "priority": "P1-Crítico|P2-Alto|P3-Medio",
      "benefit": "riesgo que elimina"}}
  ],
  "current_architecture": {{
    "coupling_score": 8,
    "coupling_analysis": "descripción del acoplamiento con componentes reales",
    "pain_points": ["SPOF real con impacto concreto"]
  }}
}}
Máximo 3 ítems en code_remediation. Usa fragmentos before/after cortos.
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
    JOBS[job_id]["status"] = "running"
    JOBS[job_id]["message"] = "Recuperando contexto RAG..."

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
    model       = MODEL_CHAIN[0]   # Agentes usan Nova Pro primero
    mid, mlabel = model["id"], model["label"]
    last_error  = None

    # ── Intento 1: 3 agentes en paralelo ─────────────────────────────────────
    JOBS[job_id]["message"] = f"Ejecutando 3 agentes en paralelo ({mlabel})..."
    logger.info("[Job %s] Iniciando análisis agéntico paralelo en %s", job_id[:8], mid)

    sec_result  = {}
    mig_result  = {}
    code_result = {}
    agents_ok   = False

    try:
        inv_msg = f"Inventario del servidor a analizar:\n{inventory}"

        def run_security():
            return _call_agent(bedrock, mid, 2048,
                               _common_ctx + _AGENT_SECURITY_PROMPT, inv_msg)

        def run_migration():
            # Migration agent recibe hallazgos de seguridad si están disponibles
            ctx = inv_msg
            if sec_result:
                ctx += f"\n\nHallazgos de seguridad detectados:\n{json.dumps(sec_result, ensure_ascii=False)[:2000]}"
            return _call_agent(bedrock, mid, 3072,
                               _common_ctx + _AGENT_MIGRATION_PROMPT, ctx)

        def run_code():
            return _call_agent(bedrock, mid, 2048,
                               _common_ctx + _AGENT_CODE_PROMPT, inv_msg)

        # Etapa 1a: Security + Code en paralelo (no dependen entre sí)
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_sec  = ex.submit(run_security)
            f_code = ex.submit(run_code)
            for fut in as_completed([f_sec, f_code]):
                try:
                    res = fut.result()
                    if fut is f_sec:
                        sec_result.update(res)
                    else:
                        code_result.update(res)
                except Exception as e:
                    logger.warning("[Job %s] Agente falló: %s", job_id[:8], e)

        # Etapa 1b: Migration (usa sec_result si está disponible)
        JOBS[job_id]["message"] = "Agente Migration planificando sprints..."
        try:
            mig_result = run_migration()
        except Exception as e:
            logger.warning("[Job %s] MigrationAgent falló: %s", job_id[:8], e)

        agents_ok = bool(sec_result or mig_result or code_result)

    except Exception as e:
        last_error = str(e)
        logger.warning("[Job %s] Fallo en bloque agéntico: %s", job_id[:8], e)

    # ── Fusión de resultados agénticos ───────────────────────────────────────
    if agents_ok:
        # Construir executive_summary desde los hallazgos de seguridad
        top_findings = sec_result.get("security_findings", [])
        attack  = sec_result.get("attack_surface", "")
        eol_list = sec_result.get("eol_components", [])
        exec_summary = (
            f"Sistema analizado con {len(top_findings)} hallazgos de seguridad. "
            + (f"Superficie de ataque: {attack} " if attack else "")
            + (f"Componentes EoL: {', '.join(eol_list[:3])}." if eol_list else "")
        ) or code_result.get("agent_analysis", "")[:300]

        ai_response = {
            "executive_summary":  exec_summary,
            "agent_analysis":     code_result.get("agent_analysis", ""),
            "migration_strategy": mig_result.get("migration_strategy", {}),
            "sprints":            mig_result.get("sprints", {}),
            "quick_wins":         mig_result.get("quick_wins", []),
            "risk_matrix":        mig_result.get("risk_matrix", []),
            "code_remediation":   code_result.get("code_remediation", []),
            "current_architecture": code_result.get("current_architecture", {}),
            # Metadatos extra de los agentes
            "security_findings":   sec_result.get("security_findings", []),
            "critical_ports":      sec_result.get("critical_ports", []),
            "eol_components":      sec_result.get("eol_components", []),
            "_analysis_method":    "agentic_parallel",
            "_rag_used":           bool(rag_ctx),
        }
        logger.info("[Job %s] Agéntico OK — sec=%d mig=%d code=%d rag=%s",
                    job_id[:8], len(top_findings),
                    len(mig_result.get("sprints", {})),
                    len(code_result.get("code_remediation", [])),
                    bool(rag_ctx))

    else:
        # ── Fallback: prompt monolítico original ─────────────────────────────
        JOBS[job_id]["message"] = "Fallback a análisis monolítico..."
        logger.warning("[Job %s] Agéntico falló — usando prompt monolítico", job_id[:8])
        ai_response = None
        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            knowledge_text=knowledge + ("\n\nRAG:\n" + rag_ctx if rag_ctx else ""),
            industry_context=industry_ctx
        )
        for model_fb in MODEL_CHAIN:
            mid_fb = model_fb["id"]
            JOBS[job_id]["message"] = f"Consultando {model_fb['label']} (fallback)..."
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
            JOBS[job_id].update({"status": "failed", "message": "Todos los modelos fallaron", "error": last_error})
            logger.error("[Job %s] Todos fallaron. Último error: %s", job_id[:8], last_error)
            return

    # ── Guardar resultado ─────────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    # Buscar el scan anterior del mismo hostname para el diff de modernización
    prev_row = _find_scan_by_hostname(hostname, within_hours=876600)  # cualquier scan previo
    prev_scan_id = prev_row["id"] if prev_row else None
    _save_scan(scan_id, hostname, raw_data, ai_response, mid, data_hash, prev_scan_id)
    ANALYSIS_CACHE[data_hash] = {
        "scan_id": scan_id, "ai_content": ai_response,
        "model_used": mid, "timestamp": datetime.now().isoformat()
    }
    JOBS[job_id].update({
        "status":     "completed",
        "message":    f"Completado ({ai_response.get('_analysis_method','agentic')})",
        "model_used": mid,
        "scan_id":    scan_id,
        "ai_content": ai_response
    })
    logger.info("[Job %s] Guardado scan %s", job_id[:8], scan_id[:8])

# ─── Endpoints ────────────────────────────────────────────────────────────────
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
    JOBS[job_id] = {
        "status": "pending",
        "message": "En cola...",
        "model_used": None,
        "created_at": datetime.now().isoformat()
    }
    background_tasks.add_task(_run_bedrock_job, job_id, raw_data, hostname, data_hash, industry)
    logger.info("Job creado: %s para host '%s' [industria: %s, force=%s]", job_id[:8], hostname, industry, force)
    return {"status": "pending", "method": "async", "job_id": job_id}

@app.get("/status/{job_id}")
async def job_status(job_id: str, _user: str = Depends(verify_auth)):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job no encontrado o expirado")
    return JOBS[job_id]

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
            if v:
                label = k.replace("_", " ").upper()
                tasks = "\n".join(f"  - {t}" for t in v) if isinstance(v, list) else str(v)
                h2(pdf, label)
                body(pdf, tasks)

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

    # ── Diagramas de Flujo (página nueva)
    pdf.add_page()
    h1(pdf, "Diagramas de Arquitectura")
    embed_diagram(pdf, "appFlow", "Diagrama de Flujo de Aplicacion — AS-IS")
    embed_diagram(pdf, "infra",   "Diagrama de Infraestructura TO-BE en AWS")

    # ── IaC (pagina nueva)
    pdf.add_page()
    h1(pdf, "Infrastructure as Code")

    for section_label, bp_key in [("Terraform HCL", "terraform_code"), ("Kubernetes YAML", "k8s_yaml"), ("Dockerfile", "dockerfile")]:
        content = bp.get(bp_key, "")
        if content and content not in ("No disponible", ""):
            h2(pdf, section_label)
            pdf.set_font("Courier", "", 7)
            pdf.set_text_color(30, 30, 30)
            pdf.set_fill_color(240, 240, 240)
            for line in safe(content, 4000).split("\n")[:60]:
                pdf.cell(0, 4, line[:140], fill=True, **NL)
            pdf.ln(4)

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    hostname_safe = re.sub(r"[^a-z0-9]", "-", d["hostname"].lower())
    logger.info("PDF generado para scan %s por %s", scan_id[:8], _user)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{hostname_safe}_{scan_id[:8]}.pdf"}
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
    sprint_lines = "\n".join(
        f"  {k.replace('_',' ').upper()}: {', '.join(v) if isinstance(v, list) else v}"
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
    result = {
        "has_web":         any(t in inv_lower for t in ["tomcat", "nginx", "apache", "node", "jboss", "websphere", "weblogic"]),
        "has_db":          any(t in inv_lower for t in ["oracle", "mysql", "postgres", "mssql", "mariadb"]),
        "has_cache":       any(t in inv_lower for t in ["redis", "memcached", "hazelcast", "infinispan"]),
        "db_engine":       "oracle" if "oracle" in inv_lower else ("postgres" if "postgres" in inv_lower else "mysql"),
        "vcpus":           2,    # default sizing conservador
        "ram_gb":          4,
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
async def get_aws_pricing(scan_id: str, region: str = "us-east-1", _user: str = Depends(verify_auth)):
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
    HOURS_MONTH = 730

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


# ─── Static Frontend ──────────────────────────────────────────────────────────
fabrica_dir = Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(fabrica_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
