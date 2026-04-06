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
    {"id": "amazon.nova-pro-v1:0",   "maxTokens": 4096, "label": "Nova Pro"},
    {"id": "amazon.nova-lite-v1:0",  "maxTokens": 4096, "label": "Nova Lite"},
    {"id": "amazon.nova-micro-v1:0", "maxTokens": 2048, "label": "Nova Micro"},
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
- Los bloques IaC deben ser funcionales y específicos al stack detectado

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
      "before": "fragmento de código o config actual problemático",
      "after": "fragmento de código o config correcto",
      "effort": "X horas",
      "priority": "P1-Crítico | P2-Alto | P3-Medio",
      "benefit": "Qué riesgo elimina y qué mejora operacional trae"
    }}
  ],

  "terraform_code": "# Terraform HCL completo y funcional para el stack detectado\\n# Incluir: VPC, ECS/EKS cluster, RDS/Aurora, ALB, IAM roles, Security Groups\\n# Variables con valores reales del entorno analizado\\n\\nterraform {{\\n  required_version = \\">=1.6\\"\\n  ...\\n}}",

  "k8s_yaml": "# Kubernetes manifests para el stack detectado\\n# Incluir: Namespace, Deployment con imagen correcta, Service, HPA\\n---\\napiVersion: apps/v1\\n...",

  "dockerfile": "# Dockerfile multi-stage optimizado para el runtime detectado\\n# Usar imagen base correcta para la versión encontrada\\nFROM ...",

  "current_architecture": {{
    "mermaid": "graph TB\\n    classDef appserv fill:#1a2a4a,stroke:#3498db,color:#90cdf4\\n    classDef dbnode fill:#0d2b4a,stroke:#2980b9,color:#90cdf4\\n    classDef intnode fill:#3d2000,stroke:#e67e22,color:#fbd38d\\n    classDef webnode fill:#1a1a3d,stroke:#6c63ff,color:#c3b1e1\\n    classDef vampire fill:#8B0000,stroke:#FF0000,color:#fff,stroke-width:3px\\n    USR([\\\"Usuarios\\\"])\\n    subgraph SRV[\\\"Servidor AS-IS\\\"]\\n    direction TB\\n        WEB[\\\"Web Server real detectado\\\"]:::webnode\\n        APP[\\\"App Server real detectado\\\"]:::appserv\\n        DB[(\\\"Base Datos real detectada\\\")]:::vampire\\n        INT[\\\"Bus Integración real\\\"]:::vampire\\n    end\\n    USR ==> WEB\\n    WEB ==>|\\\"proxy\\\"| APP\\n    APP ==>|\\\"SQL directo\\\"| DB\\n    APP ==>|\\\"integración\\\"| INT\\n    INT ==>|\\\"write DB\\\"| DB\\n    linkStyle 0,1,2,3,4 stroke:#ff3333,stroke-width:2.5px",
    "coupling_score": 8,
    "coupling_analysis": "Descripción ESPECÍFICA del acoplamiento: nombrar los componentes reales detectados, tipo de dependencia (SQL directo, SOAP, RMI, EJB), SPOFs identificados y por qué representan riesgo operacional",
    "pain_points": [
      "SPOF real: [componente] sin HA ni failover — si cae, [impacto concreto]",
      "Acoplamiento directo: [AppA] llama SQL a [DB] sin connection pool — riesgo de agotamiento de conexiones",
      "Integración síncrona SOAP/RMI entre [componentes] — sin circuit breaker ni timeout"
    ]
  }},

  "mermaid_app_flow": "graph TB\\n    classDef appserv fill:#1a2a4a,stroke:#3498db,color:#90cdf4\\n    classDef dbnode fill:#0d2b4a,stroke:#2980b9,color:#90cdf4\\n    classDef intnode fill:#3d2000,stroke:#e67e22,color:#fbd38d\\n    classDef vampire fill:#8B0000,stroke:#FF0000,color:#fff,stroke-width:3px\\n    USR([\\\"Usuario\\\"])\\n    subgraph COMPUTE[\\\"Compute — AS-IS\\\"]\\n        APP[\\\"App detectada\\\"]:::appserv\\n        INT[\\\"Integración detectada\\\"]:::vampire\\n    end\\n    subgraph DATA[\\\"Data — AS-IS\\\"]\\n        DB[(\\\"DB detectada\\\")]:::vampire\\n    end\\n    USR ==> APP\\n    APP ==>|\\\"SQL\\\"| DB\\n    APP ==>|\\\"SOAP/RMI\\\"| INT\\n    INT ==>|\\\"write\\\"| DB\\n    linkStyle 0,1,2,3 stroke:#ff3333,stroke-width:2.5px",

  "mermaid_infra": "graph TB\\n    classDef edge fill:#1a2a4a,stroke:#FF9900,color:#FF9900\\n    classDef compute fill:#0d2b1a,stroke:#27ae60,color:#9ae6b4\\n    classDef data fill:#0d1a3a,stroke:#2980b9,color:#90cdf4\\n    classDef observe fill:#2a1a4a,stroke:#8e44ad,color:#d6bcfa\\n    INT([\\\"Internet\\\"]):::edge\\n    subgraph EDGE[\\\"Edge / Seguridad\\\"]\\n        CF[\\\"CloudFront CDN\\\"]:::edge\\n        WAF[\\\"AWS WAF\\\"]:::edge\\n        ALB[\\\"Application LB\\\"]:::edge\\n    end\\n    subgraph COMPUTE[\\\"Compute\\\"]\\n        ECS[\\\"ECS Fargate - app migrada\\\"]:::compute\\n        APIGW[\\\"API Gateway\\\"]:::compute\\n    end\\n    subgraph DATA[\\\"Data\\\"]\\n        RDS[(\\\"Aurora RDS - motor real\\\")]:::data\\n        S3[\\\"Amazon S3\\\"]:::data\\n    end\\n    subgraph OBS[\\\"Observabilidad\\\"]\\n        CW[\\\"CloudWatch\\\"]:::observe\\n        XRAY[\\\"X-Ray\\\"]:::observe\\n    end\\n    INT --> CF --> WAF --> ALB --> ECS\\n    ECS --> APIGW\\n    ECS --> RDS\\n    ECS --> S3\\n    ECS -.-> CW\\n    ECS -.-> XRAY"
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
        for col, definition in [("model_used", "TEXT"), ("data_hash", "TEXT")]:
            if col not in existing:
                c.execute(f"ALTER TABLE scan_history ADD COLUMN {col} {definition}")
                logger.info("Migracion: columna '%s' agregada a scan_history", col)
    else:
        # PostgreSQL: usar ADD COLUMN IF NOT EXISTS
        for col, definition in [("model_used", "TEXT"), ("data_hash", "TEXT")]:
            c.execute(f"ALTER TABLE scan_history ADD COLUMN IF NOT EXISTS {col} {definition}")

    conn.commit()
    conn.close()
    logger.info("DB inicializada (%s)", "PostgreSQL" if DATABASE_URL else "SQLite")

init_db()

def _save_scan(scan_id, hostname, raw_data, ai_response, model_used, data_hash):
    conn, db_type = _get_conn()
    ph = _ph(db_type)
    conn.execute(
        f"INSERT INTO scan_history (id, hostname, timestamp, raw_inventory, bedrock_blueprint, model_used, data_hash) "
        f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
        (scan_id, hostname, datetime.now().isoformat(), raw_data, json.dumps(ai_response), model_used, data_hash)
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
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    raw = match.group(1) if match else text
    return json.loads(raw, strict=False)

def _cache_key(raw_data: str) -> str:
    return hashlib.sha256(raw_data.encode()).hexdigest()

# ─── Background Job (Bedrock Async) ──────────────────────────────────────────
def _run_bedrock_job(job_id: str, raw_data: str, hostname: str, data_hash: str, industry: str = "general"):
    """
    Se ejecuta en un thread separado via BackgroundTasks.
    Intenta cada modelo en MODEL_CHAIN hasta que uno responda.
    """
    JOBS[job_id]["status"] = "running"

    inventory = raw_data[:MAX_CHARS] + ("\n...[TRUNCADO]..." if len(raw_data) > MAX_CHARS else "")
    knowledge = load_knowledge()
    industry_ctx = INDUSTRY_CONTEXT.get(industry, INDUSTRY_CONTEXT["general"])
    prompt = SYSTEM_PROMPT_TEMPLATE.format(knowledge_text=knowledge, industry_context=industry_ctx)
    bedrock = _bedrock_client()
    last_error = None

    for model in MODEL_CHAIN:
        mid, mlabel = model["id"], model["label"]
        JOBS[job_id]["message"] = f"Consultando {mlabel}..."
        logger.info("[Job %s] Intentando modelo %s", job_id[:8], mid)

        try:
            resp = bedrock.converse(
                modelId=mid,
                messages=[{"role": "user", "content": [{"text": f"Inventario:\n{inventory}"}]}],
                system=[{"text": prompt}],
                inferenceConfig={"maxTokens": model["maxTokens"], "temperature": 0.3}
            )
            parsed_text = resp["output"]["message"]["content"][0]["text"]
            ai_response = _parse_json_response(parsed_text)

            scan_id = str(uuid.uuid4())
            _save_scan(scan_id, hostname, raw_data, ai_response, mid, data_hash)

            # Guardar en cache de memoria
            ANALYSIS_CACHE[data_hash] = {
                "scan_id": scan_id,
                "ai_content": ai_response,
                "model_used": mid,
                "timestamp": datetime.now().isoformat()
            }

            JOBS[job_id].update({
                "status": "completed",
                "message": f"Completado con {mlabel}",
                "model_used": mid,
                "scan_id": scan_id,
                "ai_content": ai_response
            })
            logger.info("[Job %s] Exitoso con %s", job_id[:8], mid)
            return

        except Exception as e:
            last_error = str(e)
            logger.warning("[Job %s] %s falló: %s", job_id[:8], mid, e)
            continue

    # Todos los modelos fallaron
    JOBS[job_id].update({
        "status": "failed",
        "message": "Todos los modelos fallaron",
        "error": last_error
    })
    logger.error("[Job %s] Todos fallaron. Último error: %s", job_id[:8], last_error)

# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0.0", "db": "postgresql" if DATABASE_URL else "sqlite"}

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
    m = re.search(r"HOSTNAME:\s*([^\n]+)", raw_data, re.IGNORECASE)
    hostname = m.group(1).strip() if m else "remote-host"
    # Include industry in cache key so different industries get different analyses
    data_hash = _cache_key(raw_data + "|industry=" + industry)

    # 1. Cache en memoria (más rápido)
    if data_hash in ANALYSIS_CACHE:
        c = ANALYSIS_CACHE[data_hash]
        logger.info("Cache hit (memoria): %s", data_hash[:8])
        return {
            "status": "completed", "method": "cache",
            "scan_id": c["scan_id"], "model_used": c["model_used"],
            "ai_content": c["ai_content"]
        }

    # 2. Cache en DB
    db_row = _find_cached_scan(data_hash)
    if db_row:
        ai = json.loads(db_row["bedrock_blueprint"]) if isinstance(db_row["bedrock_blueprint"], str) else db_row["bedrock_blueprint"]
        ANALYSIS_CACHE[data_hash] = {
            "scan_id": db_row["id"], "ai_content": ai,
            "model_used": db_row.get("model_used", "cached"),
            "timestamp": db_row["timestamp"]
        }
        logger.info("Cache hit (DB): %s", data_hash[:8])
        return {
            "status": "completed", "method": "cache_db",
            "scan_id": db_row["id"], "model_used": db_row.get("model_used", "cached"),
            "ai_content": ai
        }

    # 3. Nuevo job asíncrono
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "pending",
        "message": "En cola...",
        "model_used": None,
        "created_at": datetime.now().isoformat()
    }
    background_tasks.add_task(_run_bedrock_job, job_id, raw_data, hostname, data_hash, industry)
    logger.info("Job creado: %s para host '%s' [industria: %s]", job_id[:8], hostname, industry)
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
    logger.warning("[fetch-cached] raw file_path recibido: %r", raw_path)
    if '..' in raw_path:
        raise HTTPException(400, "Ruta de archivo inválida o no permitida")
    m = re.search(r'modernization_reports/inventory_[\w.\-]+\.txt$', raw_path)
    logger.warning("[fetch-cached] regex match: %s", m)
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


# ─── Static Frontend ──────────────────────────────────────────────────────────
fabrica_dir = Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(fabrica_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
