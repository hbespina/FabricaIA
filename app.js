import discoveryEngine from './lib/discoveryEngine.js';

let lastAiData        = null;
let lastSh            = null;
let lastScanId        = null;
let lastDetectedTechs = [];
let lastFindings      = [];
let lastHost          = '';

// ─── Auth Helpers ─────────────────────────────────────────────────────────────
function authHeaders(extra = {}) {
    const token = sessionStorage.getItem('mf_token');
    return token
        ? { 'Authorization': 'Bearer ' + token, ...extra }
        : { 'X-API-KEY': 'mf-api-key-2026', ...extra };
}

async function apiFetch(url, opts = {}) {
    opts.headers = authHeaders(opts.headers || {});
    const r = await fetch(url, opts);
    if (r.status === 401) { logout(); throw new Error('Sesión expirada'); }
    return r;
}

window.doLogin = async function() {
    const user  = document.getElementById('login-user').value.trim();
    const pass  = document.getElementById('login-pass').value;
    const errEl = document.getElementById('login-error');
    const btn   = document.getElementById('login-btn');
    if (!user || !pass) { errEl.style.display='block'; errEl.innerText='Ingresa usuario y contraseña.'; return; }
    btn.disabled = true; btn.innerText = 'Verificando...';
    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        const r = await fetch(`${apiUrl}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });
        if (!r.ok) {
            const e = await r.json().catch(() => ({}));
            errEl.style.display = 'block';
            errEl.innerText = e.detail || 'Credenciales incorrectas';
            return;
        }
        const data = await r.json();
        sessionStorage.setItem('mf_token', data.access_token);
        sessionStorage.setItem('mf_user', user);
        document.getElementById('login-overlay').style.display = 'none';
        const badge = document.getElementById('user-badge');
        if (badge) badge.innerText = user;
    } catch(e) {
        errEl.style.display = 'block';
        errEl.innerText = 'No se pudo conectar al backend.';
    } finally {
        btn.disabled = false; btn.innerText = 'Ingresar';
    }
};

window.logout = function() {
    sessionStorage.removeItem('mf_token');
    sessionStorage.removeItem('mf_user');
    const overlay = document.getElementById('login-overlay');
    if (overlay) { overlay.style.display = 'flex'; }
    document.getElementById('login-pass').value = '';
    document.getElementById('login-error').style.display = 'none';
};

// Verificar auth al cargar
(function checkAuth() {
    const token   = sessionStorage.getItem('mf_token');
    const overlay = document.getElementById('login-overlay');
    if (!token) {
        if (overlay) overlay.style.display = 'flex';
    } else {
        if (overlay) overlay.style.display = 'none';
        const badge = document.getElementById('user-badge');
        const user  = sessionStorage.getItem('mf_user');
        if (badge && user) badge.innerText = user;
    }
})();

// ─── Mermaid Sanitizer ────────────────────────────────────────────────────────
function sanitizeMermaid(raw) {
    if (!raw) return 'graph LR\n  A["Sin datos"]';
    let t = raw.trim();

    // Quitar code fences ```mermaid ... ```
    t = t.replace(/^```[\w]*\s*/im, '').replace(/\s*```\s*$/m, '').trim();

    // # comentarios → %% (Mermaid solo entiende %%)
    t = t.replace(/^(\s*)#([^\n]*)/gm, '$1%%$2');

    // Asegurar declaración de grafo
    if (!/^(graph|flowchart)/i.test(t)) {
        t = 'graph LR\n' + t;
    }

    // ── Casos específicos que genera la IA y rompen el parser ──────────────────

    // 1. ["('text'"]  →  ["text"]     (paren+single-quote dentro de double-quote)
    t = t.replace(/\["\('[^']*'([^']*)'?\s*"\]/g, (_, mid) => `["${mid.trim()}"]`);
    t = t.replace(/\["'\s*([^'"]+)\s*'"\]/g, '["$1"]');   // ["'text'"]  → ["text"]

    // 2. [("'text'")] → [("text")]    (cylinder con single-quotes extra)
    t = t.replace(/\["\('([^']+)'\)"\]/g, '[("$1")]');
    t = t.replace(/\["\('([^']+)'"\]/g,   '[("$1")]');

    // 3. ("'text'")   →  ("text")     (rounded con single-quotes extra)
    t = t.replace(/\("'([^']+)'"\)/g, '("$1")');

    // ── Normalización general ──────────────────────────────────────────────────

    // 4. Envolver labels no citados que contengan chars problemáticos
    //    Cubre: A[text], A(text), A{text}  — deja intactos A["text"] etc.
    t = t.replace(
        /\b([A-Za-z_][A-Za-z0-9_]*)\s*(\[(?!\[)|\((?!\())\s*([^"{\[\]\(\)\n][^\[\]\(\)\n]{0,80}?)\s*(\]|\))/g,
        (_m, id, open, label, close) => {
            const trimmed = label.trim();
            if (!trimmed || trimmed.startsWith('"')) return _m;
            const safe = trimmed.replace(/"/g, "'");
            return `${id}${open}"${safe}"${close}`;
        }
    );

    // 5. Eliminar comillas dobles anidadas dentro de labels ya citados
    //    A["text "foo" bar"]  →  A["text 'foo' bar"]
    t = t.replace(/\["([^"\n]+)"\]/g, (_, inner) => `["${inner.replace(/"/g, "'")}"]`);

    return t;
}

const wrapLabels = sanitizeMermaid;  // alias para compatibilidad

// ─── AI Status Bar ───────────────────────────────────────────────────────────
function setAiStatus(type, msg) {
    let el = document.getElementById('ai-status-bar');
    if (!el) {
        el = document.createElement('div');
        el.id = 'ai-status-bar';
        el.style.cssText = 'position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);'
            + 'padding:.55rem 1.4rem;border-radius:20px;font-size:.75rem;font-weight:600;'
            + 'z-index:9999;transition:opacity .4s;backdrop-filter:blur(12px);white-space:nowrap';
        document.body.appendChild(el);
    }
    const styles = {
        running: 'background:rgba(0,210,255,.12);border:1px solid rgba(0,210,255,.4);color:#00d2ff',
        done:    'background:rgba(0,255,136,.12);border:1px solid rgba(0,255,136,.4);color:#00ff88',
        error:   'background:rgba(255,65,108,.12);border:1px solid rgba(255,65,108,.4);color:#ff416c',
    };
    el.style.cssText += ';' + (styles[type] || styles.running);
    el.style.opacity = '1';
    el.innerText = msg;
    if (type === 'done' || type === 'error') {
        setTimeout(() => { if (el) el.style.opacity = '0'; }, 4000);
        setTimeout(() => { if (el) el.remove(); }, 4500);
    }
}

// ─── Job Polling ──────────────────────────────────────────────────────────────
async function pollJobStatus(job_id, sh, apiUrl) {
    let attempts = 0;
    const MAX = 90; // 3 min max (90 intentos × 2s)

    const poll = async () => {
        if (attempts++ >= MAX) {
            setAiStatus('error', '✗ Timeout — usando análisis local');
            window.updateAiFields(null, sh);
            return;
        }
        try {
            const r = await fetch(`${apiUrl}/status/${job_id}`, {
                headers: { 'X-API-KEY': 'mf-api-key-2026' }
            });
            if (!r.ok) { setTimeout(poll, 3000); return; }
            const s = await r.json();

            if (s.status === 'completed') {
                setAiStatus('done', `✓ ${s.model_used || 'AI'} — análisis listo`);
                lastScanId = s.scan_id || null;
                _activateScanActions(lastScanId, sh);
                window.updateAiFields(s.ai_content, sh);
            } else if (s.status === 'failed') {
                setAiStatus('error', `✗ ${s.error ? s.error.slice(0, 80) : 'Error IA'}`);
                window.updateAiFields(null, sh);
                _activateScanActions(lastScanId, sh);
            } else {
                setAiStatus('running', `⟳ ${s.message || 'Procesando...'}`);
                setTimeout(poll, 2000);
            }
        } catch(e) {
            setTimeout(poll, 3000);
        }
    };

    setTimeout(poll, 2000);
}

// ─── Generadores de diagramas (siempre válidos) ───────────────────────────────

// ─── Categoría → capa del diagrama ──────────────────────────────────────────
const _CAT_LAYER = {
    'Web':'web', 'UX/UI':'web',
    'AppServer':'app', 'Runtime':'app', 'Framework':'app',
    'Database':'db', 'Search':'db',
    'Cache':'cache',
    'Messaging':'msg',
    'Integration':'int', 'Protocol':'int',
    'Management':'ext', 'SCM':'ext', 'Backup':'ext',
};

// ── Clase Mermaid según categoría ────────────────────────────────────────────
function _nodeClass(cat, isVampire) {
    if (isVampire) return ':::vampire';
    const m = { 'Web':':::webnode', 'UX/UI':':::webnode',
                'AppServer':':::appserv', 'Runtime':':::appserv', 'Framework':':::appserv',
                'Database':':::dbnode',  'Search':':::dbnode',
                'Cache':':::cachnode',
                'Messaging':':::msgnode',
                'Integration':':::intnode', 'Protocol':':::intnode',
                'Management':':::extnode', 'SCM':':::extnode', 'Backup':':::extnode' };
    return m[cat] || ':::appserv';
}

// ── Encapsular label seguro para Mermaid ─────────────────────────────────────
function _mSafe(s) {
    return (s || '').replace(/["\[\]{}()]/g, '').replace(/[^\w\s\-.\/]/g, ' ').trim().slice(0, 42);
}

// ─── AS-IS Diagram — Acoplamiento y Dependencias de Runtime ──────────────────
//
// Taxonomía de nodos (containerization readiness):
//   osblock   = Rojo  — dependencia directa del OS (kernel, rutas fijas, hardware)
//   stateful  = Amarillo — software con estado que requiere rediseño cloud-native
//   cloudready= Verde  — proceso independiente, puede ir a Docker de inmediato
//   intnode   = Naranja — integrador (ESB/ETL/API gateway), siempre stateful
//
// Taxonomía de conexiones:
//   ==>              Acoplamiento CRÍTICO  (sync, IPC, IP hardcoded, .so/.dll)
//   -->|"💾 /ruta"|  PERSISTENCIA         (escribe en disco local del servidor)
//   -.->             Acoplamiento DÉBIL    (async, cola, telemetría)
//
function _buildAsisMermaid(techs, findings, host) {
    let idx = 0;
    const mkId = () => 'N' + (idx++);
    const seen      = new Set();
    const seenWords = new Set();

    const addWords = label =>
        label.toLowerCase().split(/[\s/\-_]+/)
            .filter(w => w.length > 3).forEach(w => seenWords.add(w));
    const wordsDupOf = label =>
        label.toLowerCase().split(/[\s/\-_]+/)
            .filter(w => w.length > 3).some(w => seenWords.has(w));

    // ── 1. Clasificación de containerization readiness ───────────────────────
    const _readiness = node => {
        const cat = node.cat || '';
        const sev = node.sev || '';
        // Integradores siempre tienen estado propio (ESB, ETL, ODI, NiFi)
        if (['Integration'].includes(cat)) return 'intnode';
        // OS-blocked: app servers viejos y runtimes críticos con .so/.dll nativos
        if (['AppServer'].includes(cat)) return 'osblock';
        if (cat === 'Runtime' && sev === 'CRITICO') return 'osblock';
        // Stateful: todo lo que persiste estado — BDs, caches, brokers
        if (['Database','Search','Cache','Messaging'].includes(cat)) return 'stateful';
        // Cloud-ready: agentes de monitoreo, proxies web sin estado, herramientas SCM
        if (['Monitoring','External','SCM','UX/UI'].includes(cat)) return 'cloudready';
        if (cat === 'Web') return 'cloudready';
        // Default: app sin clasificar explícita
        return 'modnode';
    };

    // ── 2. Inventario por capa ────────────────────────────────────────────────
    const byLayer = { web:[], app:[], db:[], cache:[], msg:[], int:[], ext:[] };

    (techs || []).forEach(t => {
        const key = (t.n || '').toLowerCase();
        if (seen.has(key) || !t.n) return;
        seen.add(key); addWords(t.n);
        const layer = _CAT_LAYER[t.cat] || 'app';
        if (byLayer[layer]) byLayer[layer].push({ id: mkId(), label: t.n, cat: t.cat, sev: null });
    });

    (findings || []).forEach(f => {
        if (f.id === 'none') return;
        const name = (f.title || '').split(/\s[—(]/)[0].trim();
        const key  = name.toLowerCase();
        if (seen.has(key) || !name || wordsDupOf(name)) return;
        seen.add(key); addWords(name);
        const layer = _CAT_LAYER[f.cat] || 'app';
        if (byLayer[layer]) byLayer[layer].push({ id: mkId(), label: name, cat: f.cat, sev: f.sev });
    });

    const allNodes = Object.values(byLayer).flat();
    if (allNodes.length === 0)
        return 'graph LR\n    USR(["👤 Usuarios"]) --> APP["Aplicacion Legacy"] --> DB[("Base de Datos")]';

    // ── 3. Mermaid header + classDefs ────────────────────────────────────────
    const lns = ['graph TB', ''];

    // Readiness
    lns.push('    classDef osblock   fill:#4a0000,stroke:#ff4444,color:#ffaaaa,stroke-width:2px');
    lns.push('    classDef stateful  fill:#3d2e00,stroke:#ffd700,color:#ffe066,stroke-width:2px');
    lns.push('    classDef cloudready fill:#003d1a,stroke:#4ade80,color:#9ae6b4');
    lns.push('    classDef intnode   fill:#3d2000,stroke:#fb923c,color:#fbd38d,stroke-width:2px');
    lns.push('    classDef modnode   fill:#1a2a4a,stroke:#3498db,color:#90cdf4');
    lns.push('');

    // ── 4. Nodo usuario ───────────────────────────────────────────────────────
    lns.push('    USR(["👤 Usuarios / Clientes"]):::cloudready');
    lns.push('');

    // ── 5. Subgraph servidor físico ───────────────────────────────────────────
    const srvLabel = host ? host.split('.')[0].toUpperCase() : 'SERVIDOR';
    lns.push(`    subgraph SRV["🖥️ ${_mSafe(srvLabel)} — AS-IS | Inventario Runtime"]`);
    lns.push('    direction TB');

    // Sub-subgraph de integradores si existen
    const hasInt = byLayer.int.length > 0;
    if (hasInt) {
        lns.push('');
        lns.push('        subgraph ESB["🔗 Capa Integradores — ESB / ETL / API"]');
        byLayer.int.forEach(n => {
            const lbl = _mSafe('🔗 ' + n.label);
            lns.push(`            ${n.id}["${lbl}"]:::intnode`);
        });
        lns.push('        end');
    }

    // Capas web y app
    const emitNode = (n, indent = '        ') => {
        const cls  = _readiness(n);
        const ico  = n.sev === 'CRITICO' ? '⛔ ' : (n.sev === 'ALTO' ? '⚠ ' : '');
        const lbl  = _mSafe(ico + n.label);
        if (['Database','Search','Cache'].includes(n.cat))
            lns.push(`${indent}${n.id}[("${lbl}")]:::${cls}`);
        else
            lns.push(`${indent}${n.id}["${lbl}"]:::${cls}`);
    };

    [...byLayer.web, ...byLayer.app, ...byLayer.cache, ...byLayer.msg]
        .forEach(n => emitNode(n));

    // Sub-subgraph de datos (DB + archivos locales)
    if (byLayer.db.length > 0) {
        lns.push('');
        lns.push('        subgraph DATA["🗄 Capa Datos — Stateful"]');
        byLayer.db.forEach(n => emitNode(n, '            '));
        lns.push('        end');
    }

    lns.push('    end');

    // ── 6. Subgraph externo ───────────────────────────────────────────────────
    if (byLayer.ext.length > 0) {
        lns.push('');
        lns.push('    subgraph EXT["☁️ Externos / Observabilidad"]');
        byLayer.ext.forEach(n => emitNode(n, '        '));
        lns.push('    end');
    }
    lns.push('');

    // ── 7. Conexiones por tipo de acoplamiento ────────────────────────────────
    // Orden de emisión: críticas → persistencia → débiles  (para linkStyle por índice)
    const critLinks = [];   // ==>  rojo  — acoplamiento crítico
    const persLinks = [];   // -->  amarillo — escritura en disco local
    const weakLinks = [];   // -.-> verde  — async / telemetría

    const { web: webs, app: apps, db: dbs, cache: caches, msg: msgs, int: ints, ext: exts } = byLayer;

    // USR → Web (proxy reverso — acoplamiento crítico vía IP/puerto)
    if (webs.length > 0) {
        webs.forEach(w => critLinks.push(`    USR ==>|"HTTPS"| ${w.id}`));
        webs.forEach(w => apps.forEach(a => critLinks.push(`    ${w.id} ==>|"proxy_pass IPC"| ${a.id}`)));
    } else if (apps.length > 0) {
        apps.forEach(a => critLinks.push(`    USR ==>|"TCP directo"| ${a.id}`));
    }

    // App → Integrador (sync: si el ESB cae, la app cae — acoplamiento crítico)
    apps.forEach(a => ints.forEach(i =>
        critLinks.push(`    ${a.id} ==>|"sync ESB call"| ${i.id}`)
    ));

    // Integrador → DB (sync: ESB orquesta DB — acoplamiento crítico)
    ints.forEach(i => dbs.forEach(d =>
        critLinks.push(`    ${i.id} ==>|"JDBC sync"| ${d.id}`)
    ));

    // App → DB directa (SQL síncrono — acoplamiento crítico)
    if (ints.length === 0) {
        apps.forEach(a => dbs.forEach(d =>
            critLinks.push(`    ${a.id} ==>|"SQL directo"| ${d.id}`)
        ));
    }

    // DB escribe en disco local (persistencia — bloqueo para containers)
    dbs.forEach(d =>
        persLinks.push(`    ${d.id} -->|"💾 /var/data"| ${d.id}_disk[/"📁 Datos locales"/]:::osblock`)
    );

    // App/ESB escribe logs en disco local
    if (apps.length > 0) {
        persLinks.push(`    ${apps[0].id} -->|"💾 /var/log"| LOG[/"📄 Logs locales"/]:::osblock`);
    }
    if (ints.length > 0) {
        persLinks.push(`    ${ints[0].id} -->|"💾 /opt/osb/logs"| INTLOG[/"📄 OSB Logs"/]:::osblock`);
    }

    // App → Cache (miss-safe — acoplamiento débil)
    apps.forEach(a => caches.forEach(c =>
        weakLinks.push(`    ${a.id} -.->|"cache lookup"| ${c.id}`)
    ));

    // App/Int → Messaging (async — acoplamiento débil)
    [...apps, ...ints].forEach(n => msgs.forEach(m =>
        weakLinks.push(`    ${n.id} -.->|"async event"| ${m.id}`)
    ));

    // Messaging → Integrador (consume async)
    msgs.forEach(m => ints.forEach(i =>
        weakLinks.push(`    ${m.id} -.->|"consume"| ${i.id}`)
    ));

    // Cualquier nodo → Externo (telemetría / heartbeat — acoplamiento débil)
    if (exts.length > 0) {
        const anchor = apps[0] || webs[0] || ints[0];
        if (anchor) exts.forEach(e =>
            weakLinks.push(`    ${anchor.id} -.->|"telemetría"| ${e.id}`)
        );
    }

    critLinks.forEach(l => lns.push(l));
    lns.push('');
    persLinks.forEach(l => lns.push(l));
    lns.push('');
    weakLinks.forEach(l => lns.push(l));

    // ── 8. linkStyle por tipo ─────────────────────────────────────────────────
    const nC = critLinks.length;
    const nP = persLinks.length;
    const nW = weakLinks.length;

    if (nC > 0) {
        const idxs = Array.from({ length: nC }, (_, i) => i).join(',');
        lns.push(`    linkStyle ${idxs} stroke:#ff3333,stroke-width:3px`);
    }
    if (nP > 0) {
        const idxs = Array.from({ length: nP }, (_, i) => nC + i).join(',');
        lns.push(`    linkStyle ${idxs} stroke:#ffd700,stroke-width:1.5px,stroke-dasharray:3`);
    }
    if (nW > 0) {
        const idxs = Array.from({ length: nW }, (_, i) => nC + nP + i).join(',');
        lns.push(`    linkStyle ${idxs} stroke:#4ade80,stroke-width:1px,stroke-dasharray:6`);
    }

    return lns.join('\n');
}

// ─── TO-BE AWS Diagram Builder ────────────────────────────────────────────────
function _buildTobeMermaid(techs) {
    const by = {};
    (techs || []).forEach(t => { (by[t.cat] = by[t.cat] || []).push(t); });

    const safe = s => _mSafe(s);
    const lns = [
        'graph TB',
        '',
        '    classDef edge    fill:#1a2a4a,stroke:#FF9900,color:#FF9900',
        '    classDef compute fill:#0d2b1a,stroke:#27ae60,color:#9ae6b4',
        '    classDef data    fill:#0d1a3a,stroke:#2980b9,color:#90cdf4',
        '    classDef observe fill:#2a1a4a,stroke:#8e44ad,color:#d6bcfa',
        '    classDef sec     fill:#3d1a00,stroke:#e67e22,color:#fbd38d',
        '',
        '    INT(["🌐 Internet"]):::edge',
        '',
        '    subgraph EDGE["🛡️ Edge / Seguridad"]',
        '    direction LR',
        '        CF["CloudFront CDN"]:::edge',
        '        WAF["AWS WAF + Shield"]:::sec',
        '        ALB["Application LB"]:::edge',
        '    end',
        '',
        '    subgraph COMPUTE["⚙️ Compute"]',
        '    direction TB',
    ];

    const appTarget = (by['AppServer'] || by['Runtime'] || [{}])[0]?.a || 'ECS Fargate';
    lns.push(`        ECS["${safe(appTarget)}"]:::compute`);

    (by['Integration'] || []).forEach((t, i) =>
        lns.push(`        INT${i}["${safe(t.a || 'API Gateway')}"]:::compute`)
    );
    if (!by['Integration']?.length)
        lns.push('        APIGW["API Gateway"]:::compute');

    lns.push('    end');
    lns.push('');
    lns.push('    subgraph DATA["🗄️ Data"]');
    lns.push('    direction TB');

    (by['Database'] || []).forEach((t, i) =>
        lns.push(`        RDS${i}[("${safe(t.a || 'Aurora RDS')}")]:::data`)
    );
    (by['Cache'] || []).forEach((t, i) =>
        lns.push(`        CC${i}["${safe(t.a || 'ElastiCache Redis')}"]:::data`)
    );
    (by['Messaging'] || []).forEach((t, i) =>
        lns.push(`        MQ${i}["${safe(t.a || 'Amazon MQ')}"]:::data`)
    );
    if (!by['Database']?.length)
        lns.push('        RDS0[("Aurora Serverless")]:::data');
    lns.push('        S3["Amazon S3"]:::data');
    lns.push('    end');
    lns.push('');
    lns.push('    subgraph OBSERVE["📡 Observabilidad"]');
    lns.push('    direction LR');
    lns.push('        CW["CloudWatch\nLogs + Metrics"]:::observe');
    lns.push('        XRAY["AWS X-Ray\nTracing"]:::observe');
    lns.push('        SEC["Security Hub\n+ GuardDuty"]:::sec');
    lns.push('    end');
    lns.push('');

    // Connections
    lns.push('    INT --> CF --> WAF --> ALB --> ECS');
    (by['Integration'] || []).forEach((_, i) => lns.push(`    ECS --> INT${i}`));
    if (!by['Integration']?.length) lns.push('    ECS --> APIGW');
    (by['Database']  || []).forEach((_, i) => lns.push(`    ECS --> RDS${i}`));
    (by['Cache']     || []).forEach((_, i) => lns.push(`    ECS --> CC${i}`));
    (by['Messaging'] || []).forEach((_, i) => lns.push(`    ECS --> MQ${i}`));
    if (!by['Database']?.length) lns.push('    ECS --> RDS0');
    lns.push('    ECS --> S3');
    lns.push('    ECS -.->|"logs/metrics"| CW');
    lns.push('    ECS -.->|"traces"| XRAY');
    lns.push('    ECS -.->|"events"| SEC');

    return lns.join('\n');
}

// ─── IaC Local Generators ─────────────────────────────────────────────────────
function _buildTerraform(techs, host) {
    const by = {};
    (techs || []).forEach(t => { (by[t.cat] = by[t.cat] || []).push(t); });
    const region = 'us-east-1';
    const safeName = (host || 'app').replace(/[^a-z0-9]/gi, '-').toLowerCase().slice(0, 20);
    const dbEngine = (by['Database'] || [])[0]?.a?.toLowerCase().includes('oracle') ? 'oracle-ee' :
                     (by['Database'] || [])[0]?.a?.toLowerCase().includes('mysql')  ? 'mysql'     :
                     (by['Database'] || [])[0]?.a?.toLowerCase().includes('postgre') ? 'postgres'  : 'aurora-mysql';
    const hasCache  = (by['Cache']     || []).length > 0;
    const hasQueue  = (by['Messaging'] || []).length > 0;

    return `# Terraform — ${host || 'Modernization Target'}
# Generado por Modernization Factory

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = "${region}" }

# ── VPC ──────────────────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  name    = "${safeName}-vpc"
  cidr    = "10.0.0.0/16"
  azs             = ["${region}a", "${region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  enable_nat_gateway = true
}

# ── ECS Fargate ───────────────────────────────────────────────────────
resource "aws_ecs_cluster" "${safeName}_cluster" {
  name = "${safeName}-cluster"
  setting { name = "containerInsights"; value = "enabled" }
}

resource "aws_ecs_task_definition" "${safeName}_task" {
  family                   = "${safeName}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  container_definitions = jsonencode([{
    name  = "${safeName}"
    image = "\${var.ecr_image}"
    portMappings = [{ containerPort = 8080; protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options   = {
        "awslogs-group"  = "/ecs/${safeName}"
        "awslogs-region" = "${region}"
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}
${(by['Database'] || []).length > 0 ? `
# ── RDS ──────────────────────────────────────────────────────────────
resource "aws_db_instance" "${safeName}_db" {
  identifier        = "${safeName}-db"
  engine            = "${dbEngine}"
  instance_class    = "db.t3.medium"
  allocated_storage = 100
  db_name           = "${safeName.replace(/-/g,'_')}"
  username          = "dbadmin"
  password          = var.db_password
  multi_az          = true
  skip_final_snapshot = false
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
}` : ''}
${hasCache ? `
# ── ElastiCache Redis ─────────────────────────────────────────────────
resource "aws_elasticache_cluster" "${safeName}_cache" {
  cluster_id        = "${safeName}-cache"
  engine            = "redis"
  node_type         = "cache.t3.micro"
  num_cache_nodes   = 1
  port              = 6379
  subnet_group_name = aws_elasticache_subnet_group.main.name
}` : ''}
${hasQueue ? `
# ── Amazon MQ (ActiveMQ) ─────────────────────────────────────────────
resource "aws_mq_broker" "${safeName}_mq" {
  broker_name        = "${safeName}-mq"
  engine_type        = "ActiveMQ"
  engine_version     = "5.17.6"
  host_instance_type = "mq.t3.micro"
  user { username = "mqadmin"; password = var.mq_password }
}` : ''}

variable "ecr_image"    { type = string }
variable "db_password"  { type = string; sensitive = true }
variable "mq_password"  { type = string; sensitive = true; default = "" }
`;
}

function _buildK8sYaml(techs, host) {
    const by = {};
    (techs || []).forEach(t => { (by[t.cat] = by[t.cat] || []).push(t); });
    const safeName  = (host || 'app').replace(/[^a-z0-9]/gi, '-').toLowerCase().slice(0, 20);
    const appVer    = (by['AppServer'] || by['Runtime'] || [{}])[0]?.a || 'app';
    const replicas  = 2;

    return `# Kubernetes Manifests — ${host || 'Modernization Target'}
# Generado por Modernization Factory
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${safeName}
  labels:
    app.kubernetes.io/name: ${safeName}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${safeName}
  namespace: ${safeName}
  labels:
    app: ${safeName}
spec:
  replicas: ${replicas}
  selector:
    matchLabels:
      app: ${safeName}
  template:
    metadata:
      labels:
        app: ${safeName}
    spec:
      containers:
      - name: ${safeName}
        image: \${ECR_REPO}/${safeName}:latest
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "2Gi"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 20
        env:
        - name: DB_URL
          valueFrom:
            secretKeyRef:
              name: ${safeName}-secrets
              key: db_url
---
apiVersion: v1
kind: Service
metadata:
  name: ${safeName}-svc
  namespace: ${safeName}
spec:
  selector:
    app: ${safeName}
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ${safeName}-hpa
  namespace: ${safeName}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ${safeName}
  minReplicas: ${replicas}
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
`;
}

function _buildDockerfile(techs) {
    const by = {};
    (techs || []).forEach(t => { (by[t.cat] = by[t.cat] || []).push(t); });
    const appServer = (by['AppServer'] || [])[0]?.a || '';
    const runtime   = (by['Runtime']   || [])[0]?.a || '';

    let baseImg   = 'eclipse-temurin:17-jre-alpine';
    let buildImg  = 'eclipse-temurin:17-jdk-alpine';
    let buildCmd  = 'mvn -q package -DskipTests';
    let artifact  = 'target/*.jar';
    let runCmd    = 'java -jar /app/app.jar';
    let port      = 8080;

    if (/node/i.test(runtime)) {
        baseImg  = 'node:20-alpine';
        buildImg = 'node:20-alpine';
        buildCmd = 'npm ci && npm run build';
        artifact = '.';
        runCmd   = 'node server.js';
        port     = 3000;
    } else if (/python/i.test(runtime)) {
        baseImg  = 'python:3.12-slim';
        buildImg = 'python:3.12-slim';
        buildCmd = 'pip install --no-cache-dir -r requirements.txt';
        artifact = '.';
        runCmd   = 'gunicorn -w 4 -b 0.0.0.0:8000 app:app';
        port     = 8000;
    } else if (/websphere|was/i.test(appServer)) {
        baseImg  = 'ibmcom/websphere-traditional:9.0.5';
        buildImg = 'eclipse-temurin:8-jdk-alpine';
        runCmd   = '/opt/IBM/WebSphere/AppServer/bin/startServer.sh server1';
        port     = 9080;
    } else if (/jboss|wildfly/i.test(appServer)) {
        baseImg  = 'quay.io/wildfly/wildfly:30.0';
        buildImg = 'eclipse-temurin:17-jdk-alpine';
        artifact = 'target/*.war';
        runCmd   = '/opt/jboss/wildfly/bin/standalone.sh -b 0.0.0.0';
        port     = 8080;
    } else if (/tomcat/i.test(appServer)) {
        baseImg  = 'tomcat:10.1-jre17-alpine';
        buildImg = 'eclipse-temurin:17-jdk-alpine';
        artifact = 'target/*.war';
        runCmd   = 'catalina.sh run';
        port     = 8080;
    }

    return `# Dockerfile — Modernization Factory
# Multi-stage build optimizado

# ── Stage 1: Build ────────────────────────────────────────────────────
FROM ${buildImg} AS builder
WORKDIR /build
COPY . .
RUN ${buildCmd}

# ── Stage 2: Runtime ─────────────────────────────────────────────────
FROM ${baseImg}
WORKDIR /app

# Usuario no-root (seguridad)
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

COPY --from=builder /build/${artifact} /app/

EXPOSE ${port}
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \\
  CMD wget -qO- http://localhost:${port}/health || exit 1

CMD ["${runCmd.split(' ')[0]}"${runCmd.split(' ').slice(1).map(a => `, "${a}"`).join('')}]
`;
}

function _renderIaC(techs, host) {
    const aiData = lastAiData || {};
    const tfEl   = document.getElementById('tf');
    const k8sEl  = document.getElementById('k8s');
    const dockEl = document.getElementById('dock');
    if (tfEl)   tfEl.innerText   = aiData.terraform_code || _buildTerraform(techs, host);
    if (k8sEl)  k8sEl.innerText  = aiData.k8s_yaml       || _buildK8sYaml(techs, host);
    if (dockEl) dockEl.innerText = aiData.dockerfile      || _buildDockerfile(techs);
}

window.triggerMermaid = async function() {
    if (typeof mermaid === 'undefined') return;

    // Diagramas generados desde código (garantizados válidos) como fuente primaria.
    // El diagrama de la IA se intenta primero; si falla, se usa el generado.
    const DIAGRAMS = [
        {
            id: 'im',
            primary:  () => lastAiData?.mermaid_infra,
            fallback: () => _buildTobeMermaid(lastDetectedTechs),
        },
        {
            id: 'am',
            primary:  () => lastAiData?.mermaid_app_flow,
            fallback: () => _buildAsisMermaid(lastDetectedTechs, lastFindings, lastHost),
        },
        {
            id: 'current-arch-diagram',
            primary:  () => lastAiData?.current_architecture?.mermaid,
            fallback: () => _buildAsisMermaid(lastDetectedTechs, lastFindings, lastHost),
        },
    ];

    for (const { id, primary, fallback } of DIAGRAMS) {
        const el = document.getElementById(id);
        if (!el || el.offsetParent === null) continue;
        await _renderMermaid(el, primary(), fallback());
    }
};

async function _renderMermaid(el, aiRaw, generated) {
    const toSvg = async (code) => {
        const uid = 'mgr' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        try {
            const r = await mermaid.render(uid, code);
            return r.svg || r;
        } finally {
            document.getElementById(uid)?.remove();
        }
    };

    // 1. Intentar con el diagrama de la IA (sanitizado)
    if (aiRaw) {
        try {
            el.innerHTML = await toSvg(sanitizeMermaid(aiRaw));
            return;
        } catch(e) {
            console.warn('[Mermaid] AI diagram failed, using generated:', e.message?.slice(0, 60));
        }
    }

    // 2. Usar el diagrama generado programáticamente (siempre válido)
    try {
        el.innerHTML = await toSvg(generated);
    } catch(e) {
        // No debería ocurrir nunca — los generados son código controlado
        console.error('[Mermaid] generated diagram failed:', e);
        el.innerHTML = '<p style="color:var(--t2);font-size:.75rem;padding:.5rem">Diagrama no disponible</p>';
    }
}

window.sw = function(i) {
  for(let j=0; j<6; j++) {
      let pg = document.getElementById('p'+j);
      let t = document.getElementById('n'+j);
      if(pg) pg.style.display='none';
      if(t) t.classList.remove('on');
  }
  let p=document.getElementById('p'+i);
  let n=document.getElementById('n'+i);
  if(p) p.style.display='block';
  if(n) n.classList.add('on');

  if(i === 4 && window.fetchHistory) window.fetchHistory();
  if(i === 5 && window.loadDashboard) { window.loadDashboard(); window.loadPortfolio(); }

  if (i === 0 || i === 1 || i === 2) {
      setTimeout(() => window.triggerMermaid(), 50);
  }
  if (i === 3) {
      _renderIaC(lastDetectedTechs, lastHost);
  }
};

window.exportReport = function() {
  const hostName = document.getElementById('hdrHost').innerText.split(' — ')[0].replace('📍 ','');
  const titleEl = document.createElement('div');
  titleEl.style.cssText = 'position:absolute;top:-9999px;font-size:1.5rem;font-weight:700;margin-bottom:1rem;border-bottom:2px solid #ccc;padding:1rem 0;';
  titleEl.innerHTML = 'Modernization Report: <b>' + hostName + '</b>';
  document.body.insertBefore(titleEl, document.body.firstChild);
  
  const ids = ['p0','p1','p2','p3'];
  const prev = [];
  ids.forEach(id => {
      const el = document.getElementById(id);
      prev.push(el.style.display);
      el.style.display = 'block';
  });
  
  window.print();
  
  setTimeout(() => {
      titleEl.remove();
      ids.forEach((id, i) => {
          document.getElementById(id).style.display = prev[i];
      });
  }, 500);
};

window.setMode = function(m) {
  document.getElementById('mode-ssh').style.display = m === 'ssh' ? 'block' : 'none';
  document.getElementById('mode-manual').style.display = m === 'manual' ? 'block' : 'none';
  document.getElementById('tab-ssh').classList.toggle('on', m === 'ssh');
  document.getElementById('tab-manual').classList.toggle('on', m === 'manual');
};

// ─── SSH Collect Steps ────────────────────────────────────────────────────────
const SSH_STEPS = [
    { pattern: /HOSTNAME:|OS INFO|Red Hat|Ubuntu|CentOS|Debian|AIX|Solaris/i, label: 'Sistema Operativo' },
    { pattern: /JAVA|JDK|TOMCAT|CATALINA|JBOSS|WEBSPHERE/i,                   label: 'Java Stack' },
    { pattern: /PROCESSES|LISTENING|PORTS/i,                                   label: 'Procesos y Puertos' },
    { pattern: /DATABASE|MYSQL|ORACLE|MONGO|POSTGRES/i,                        label: 'Bases de Datos' },
    { pattern: /SOURCE CODE|CODE QUALITY|PYTHON|NODE|PHP/i,                    label: 'Código y Runtimes' },
    { pattern: /SECURITY|SSL|GIT|KAFKA|NIFI/i,                                 label: 'Seguridad y Mensajería' },
    { pattern: /END.*INVENTORY|REPORT COMPLETE|MODERNIZATION.*REPORT/i,        label: 'Reporte Completo' },
];

function renderSshSteps(output) {
    const el = document.getElementById('ssh-steps');
    if (!el) return;
    el.innerHTML = SSH_STEPS.map(s => {
        const done = s.pattern.test(output);
        const icon = done ? '✓' : '○';
        const color = done ? 'var(--green)' : 'var(--t2)';
        return `<div style="font-size:.72rem;color:${color};display:flex;gap:.5rem;align-items:center">
            <span style="width:14px;text-align:center;font-weight:700">${icon}</span>
            <span>${s.label}</span>
        </div>`;
    }).join('');
    const lines = document.getElementById('ssh-lines');
    if (lines) lines.innerText = (output.match(/\n/g) || []).length;
}

async function pollCollectStatus(task_id, host, apiUrl) {
    const st = document.getElementById('ssh-status');
    const btn = document.getElementById('sshbtn');
    const prog = document.getElementById('ssh-progress');
    let attempts = 0;
    const MAX = 150; // 5 min

    const poll = async () => {
        if (attempts++ > MAX) {
            st.style.color = 'var(--red)';
            st.innerText = 'Timeout — el servidor tardó demasiado.';
            if (prog) prog.style.display = 'none';
            btn.disabled = false;
            btn.innerText = '🔍 Conectar y Analizar';
            return;
        }
        try {
            const r = await fetch(`${apiUrl}/collect/status/${task_id}`, {
                headers: { 'X-API-KEY': 'mf-api-key-2026' }
            });
            if (!r.ok) { setTimeout(poll, 3000); return; }
            const s = await r.json();

            renderSshSteps(s.output || '');
            st.innerText = s.message || 'Recolectando...';

            if (s.status === 'completed') {
                if (prog) prog.style.display = 'none';
                st.style.color = 'var(--green)';
                st.innerText = `✓ ${s.lines_collected || 0} líneas recolectadas. Analizando...`;
                document.getElementById('raw').value = s.output || '';
                btn.disabled = false;
                btn.innerText = '🔍 Conectar y Analizar';
                run();
            } else if (s.status === 'failed') {
                if (prog) prog.style.display = 'none';
                st.style.color = 'var(--red)';
                st.innerText = 'Error: ' + (s.error || 'Fallo desconocido');
                btn.disabled = false;
                btn.innerText = '🔍 Conectar y Analizar';
            } else {
                setTimeout(poll, 2000);
            }
        } catch(e) {
            setTimeout(poll, 3000);
        }
    };
    setTimeout(poll, 1500);
}

// ─── Cache Modal Promise ──────────────────────────────────────────────────────
// Muestra el modal de caché y devuelve 'use_cache' | 'new_scan'
function _showCacheModal(ageMinutes, filePath) {
    return new Promise(resolve => {
        const mo = document.getElementById('cache-modal');
        if (!mo) { resolve('new_scan'); return; }

        const ageEl    = document.getElementById('cache-age');
        const fileEl   = document.getElementById('cache-file');
        const useBtn   = document.getElementById('cache-use-btn');
        const newBtn   = document.getElementById('cache-new-btn');
        const closeBtn = document.getElementById('cache-close-btn');

        if (ageEl)  ageEl.innerText  = ageMinutes + ' minutos';
        if (fileEl) fileEl.innerText = filePath.split('/').pop();

        const done = choice => { mo.style.display = 'none'; resolve(choice); };
        if (useBtn)   useBtn.onclick   = () => done('use_cache');
        if (newBtn)   newBtn.onclick   = () => done('new_scan');
        if (closeBtn) closeBtn.onclick = () => done('use_cache');  // X = usar caché por defecto

        mo.style.display = 'flex';
    });
}

window.connectAndCollect = async function() {
    const host = document.getElementById('ssh-host').value.trim();
    const user = document.getElementById('ssh-user').value.trim();
    const pass = document.getElementById('ssh-pass').value;
    const port = parseInt(document.getElementById('ssh-port').value) || 22;
    const st   = document.getElementById('ssh-status');
    const btn  = document.getElementById('sshbtn');
    const warn = document.getElementById('ssh-warn');
    const prog = document.getElementById('ssh-progress');

    if (!host || !user) { alert('Ingresa hostname y usuario.'); return; }

    const keyInput  = document.getElementById('ssh-key-file');
    const passInput = document.getElementById('ssh-pass');
    let privateKeyStr = '';

    if (keyInput && keyInput.files.length > 0) {
        privateKeyStr = await new Promise(resolve => {
            const reader = new FileReader();
            reader.onload  = e => resolve(e.target.result);
            reader.onerror = () => { alert('No se pudo leer la llave.'); resolve(''); };
            reader.readAsText(keyInput.files[0]);
        });
    }

    const activePass = passInput.value;
    btn.disabled = true;
    btn.innerText = 'Verificando...';
    st.style.color = 'var(--blue)';
    st.innerText = 'Conectando a ' + host + '...';
    warn.style.display = 'none';
    if (prog) { prog.style.display = 'block'; renderSshSteps(''); }

    // Limpiar credenciales del DOM inmediatamente
    passInput.value = '';
    if (keyInput) keyInput.value = '';

    const apiUrl = window.API_URL || 'http://localhost:8000';
    const sshPayload = { hostname: host, username: user, password: activePass, port, private_key: privateKeyStr };

    try {
        // ── 1. Verificar si hay inventario reciente en el servidor ────────────
        st.innerText = 'Verificando inventario en servidor...';
        let cacheResult = null;
        try {
            const checkResp = await fetch(`${apiUrl}/collect/check`, {
                method: 'POST',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(sshPayload)
            });
            if (checkResp.ok) cacheResult = await checkResp.json();
        } catch(_) { /* si falla el check, continuar con scan normal */ }

        // ── 2. Decidir qué hacer según la edad del cache ──────────────────────
        if (cacheResult?.has_cache) {
            const age = cacheResult.age_minutes;

            if (age < 60) {
                // Cache fresco: preguntar al usuario
                const choice = await _showCacheModal(age, cacheResult.file_path);

                if (choice === 'use_cache') {
                    // Leer el archivo existente
                    st.innerText = 'Leyendo inventario existente...';
                    btn.innerText = 'Cargando...';
                    const fetchResp = await fetch(`${apiUrl}/collect/fetch-cached`, {
                        method: 'POST',
                        headers: authHeaders({ 'Content-Type': 'application/json' }),
                        body: JSON.stringify({ ...sshPayload, file_path: cacheResult.file_path })
                    });
                    if (!fetchResp.ok) {
                        const err = await fetchResp.json();
                        throw new Error(err.detail || 'Error al leer el archivo');
                    }
                    const cached = await fetchResp.json();
                    privateKeyStr = '';

                    // Cargar en textarea y disparar análisis automáticamente
                    document.getElementById('raw').value = cached.output;
                    if (prog) prog.style.display = 'none';
                    st.style.color = 'var(--green)';
                    st.innerText = `Inventario cargado (${age} min) — analizando...`;
                    btn.disabled = false;
                    btn.innerText = '🔍 Conectar y Analizar';
                    await window.run();
                    return;
                }
                // Si eligió 'new_scan': continuar hacia abajo con scan completo
                st.innerText = 'Ejecutando nuevo scan...';

            } else {
                // Cache expirado: informar y proceder automáticamente
                st.innerText = `Inventario de ${age} min (> 1h), ejecutando nuevo scan...`;
            }
        }

        // ── 3. Scan completo ──────────────────────────────────────────────────
        btn.innerText = 'Escaneando...';
        const resp = await fetch(`${apiUrl}/collect`, {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(sshPayload)
        });
        privateKeyStr = '';

        if (!resp.ok) {
            const err = await resp.json();
            if (prog) prog.style.display = 'none';
            st.style.color = 'var(--red)';
            st.innerText = 'Error: ' + (err.detail || resp.statusText);
            btn.disabled = false;
            btn.innerText = '🔍 Conectar y Analizar';
            return;
        }

        const data = await resp.json();
        st.innerText = `Job iniciado — ${host} — recolectando datos...`;
        pollCollectStatus(data.task_id, host, apiUrl);

    } catch(e) {
        privateKeyStr = '';
        if (prog) prog.style.display = 'none';
        // Solo mostrar "Backend no disponible" si es error de red (fetch failed), no errores del servidor
        if (e instanceof TypeError && e.message.toLowerCase().includes('fetch')) {
            warn.style.display = 'block';
        }
        st.style.color = 'var(--red)';
        st.innerText = 'Error: ' + e.message;
        btn.disabled = false;
        btn.innerText = '🔍 Conectar y Analizar';
    }
};

window.run = async function() {
    const btn = document.getElementById('analbtn');
    const sBtn = document.getElementById('sshbtn');
    try {
        if (btn) btn.disabled = true;
        if (sBtn) sBtn.disabled = true;
        if (btn) btn.innerText = 'Consultando AI...';
        await analyze();
        sw(0);
    } catch(e) {
        alert('Error: ' + e.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'Analizar Datos'; }
        if (sBtn) { sBtn.disabled = false; sBtn.innerText = '🔍 Conectar y Analizar'; }
    }
};

// ─── Rendering local (reutilizado por analyze() y loadHistory()) ───────────────
function _renderLocalUI(data) {
    lastDetectedTechs = data.detectedTechs || [];
    lastFindings      = data.findings      || [];
    lastHost          = data.host          || '';

    document.getElementById('hdrHost').innerText = '📍 ' + data.host + ' — Analisis de Modernización';
    document.getElementById('patbdg').innerHTML = '<span style="background:linear-gradient(135deg,#9d50bb,#6e48aa);padding:.35rem .9rem;border-radius:8px;font-weight:700;font-size:.73rem">' + data.pattern + '</span>';

    document.getElementById('summ').innerHTML = `
        <div style="display:flex;gap:2rem">
            <div style="text-align:center">
                <div style="font-size:1.8rem;font-weight:700;color:var(--red)">${data.criticalCount}</div>
                <div style="font-size:.62rem;color:var(--t2)">CRITICOS</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:1.8rem;font-weight:700;color:var(--yellow)">${data.highCount}</div>
                <div style="font-size:.62rem;color:var(--t2)">ALTOS</div>
            </div>
        </div>`;

    document.getElementById('flist').innerHTML = data.findings.map(f => {
        const bc = f.sev === 'CRITICO' ? 'bc' : (f.sev === 'ALTO' ? 'bh' : 'bm');
        const riskBadge = (f.risk != null)
            ? `<span class="fbdg" style="background:rgba(0,0,0,.4);border:1px solid rgba(160,160,160,.4);color:var(--t2)" title="Composite Risk Score (CVSS × exposición × datos)">⚡ ${f.risk}</span>`
            : '';
        const cveBadges = (f.cves && f.cves.length)
            ? f.cves.map(c =>
                `<a href="https://nvd.nist.gov/vuln/detail/${c}" target="_blank" rel="noopener" style="text-decoration:none">` +
                `<span class="fbdg bc" style="cursor:pointer;letter-spacing:.02em" title="Ver en NIST NVD">${c}</span></a>`
              ).join(' ')
            : '';
        return `<div class="fi ${f.sev === 'CRITICO'?'fc':(f.sev==='ALTO'?'fh':'fm')}">
            <div class="fhd">
                <div style="flex:1">
                    <div class="ftit">${f.title}</div>
                    <div class="fev">[${f.cat}] ${f.evidence}</div>
                </div>
                <div style="display:flex;align-items:center;gap:.3rem;flex-wrap:wrap;justify-content:flex-end">
                    <span class="fbdg ${bc}">${f.sev}</span>
                    ${riskBadge}
                </div>
            </div>
            ${cveBadges ? `<div style="margin-bottom:.5rem;display:flex;flex-wrap:wrap;gap:.3rem">${cveBadges}</div>` : ''}
            <div class="fbody"><b>Anti:</b> ${f.anti}</div>
            <div class="fimp">${f.impact}</div>
        </div>`;
    }).join('');

    let bizCats = {};
    data.detectedTechs.forEach(d => {
        if(!bizCats[d.cat]) bizCats[d.cat] = [];
        bizCats[d.cat].push(d);
    });

    document.getElementById('biz').innerHTML = Object.keys(bizCats).map(c => {
        let rows = bizCats[c].map(d => `<div style="padding:.3rem 0;font-size:.75rem;display:flex;justify-content:space-between"><span>${d.n}</span><span style="color:var(--green);font-size:.65rem">${d.a}</span></div>`).join('');
        return `<div style="margin-bottom:.6rem"><div style="font-size:.65rem;font-weight:700;color:var(--blue);margin-bottom:.3rem">${c}</div>${rows}</div>`;
    }).join('') || 'No detectado.';

    document.getElementById('inv').innerHTML = Object.keys(bizCats).map(c => {
        let rows = bizCats[c].map(d => `<div style="padding:.3rem 0;font-size:.72rem;display:flex;justify-content:space-between"><span>${d.n}</span><span style="color:var(--blue);font-size:.62rem">${d.a}</span></div>`).join('');
        return `<div style="background:rgba(0,0,0,.3);border:1px solid rgba(0,210,255,.2);border-radius:10px;padding:.6rem;border-top:3px solid var(--blue)">
            <div style="font-size:.65rem;font-weight:700;color:var(--blue)">${c}</div>${rows}</div>`;
    }).join('');

    const protoRows = [];
    data.detectedTechs.forEach(t => protoRows.push({ icon: t.icon || '→', legacy: t.n, modern: t.a }));
    const seenLegacy = new Set(protoRows.map(r => r.legacy.toLowerCase()));
    data.findings.forEach(f => {
        if (f.modern && f.modern !== 'OK' && !seenLegacy.has(f.title.toLowerCase())) {
            protoRows.push({ icon: '⚠', legacy: f.title, modern: f.modern });
            seenLegacy.add(f.title.toLowerCase());
        }
    });
    const protoEl = document.getElementById('proto');
    if (protoEl) {
        protoEl.innerHTML = protoRows.length === 0
            ? '<p style="font-size:.75rem;color:var(--t2);margin-top:.6rem">No se detectaron tecnologías legacy con rutas de migración definidas.</p>'
            : protoRows.map(r =>
                `<div style="display:flex;align-items:center;gap:.5rem;padding:.35rem 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.75rem">
                    <span style="font-size:.8rem;min-width:1.2rem">${r.icon}</span>
                    <span style="flex:1;color:#fff">${r.legacy}</span>
                    <span style="color:var(--t2);font-size:.68rem;padding:0 .4rem">→</span>
                    <span style="color:var(--green);font-size:.72rem;text-align:right;flex:1.2">${r.modern}</span>
                </div>`).join('');
    }

    const maxRisk  = data.findings.reduce((m, f) => Math.max(m, f.risk || 0), 0);
    const totalCves = data.findings.reduce((s, f) => s + (f.cves ? f.cves.length : 0), 0);
    document.getElementById('srisk').innerText = maxRisk > 0 ? maxRisk.toFixed(1) : (data.criticalCount >= 2 ? '9.0' : '5.0');
    document.getElementById('scve').innerText  = totalCves > 0 ? totalCves : (data.criticalCount >= 2 ? '8+' : '—');
    document.getElementById('sread').innerText = maxRisk >= 8 ? 'Baja' : (data.criticalCount >= 1 ? 'Media' : 'Lista');
    document.getElementById('ssum').innerHTML  = `<p><b>Host:</b> ${data.host}</p><p><b>OS:</b> ${data.osStr}</p>`;

    document.getElementById('fop').innerText = '$' + data.costs.totalOpEx;
    document.getElementById('fmi').innerText = '$' + data.costs.migrationCost;
    document.getElementById('fpa').innerText = typeof data.costs.paybackMonths === 'number' ? data.costs.paybackMonths + ' meses' : 'N/A';
    document.getElementById('fin').innerText = '$' + data.costs.annualCostInaction;
}

window.analyze = async function() {
    const raw = document.getElementById('raw').value.trim();
    if(!raw) {
        alert('Pega datos o conecta.');
        return;
    }

    const data = discoveryEngine.analyzeData(raw);
    _renderLocalUI(data);

    const sh = data.host.replace(/[^a-z0-9]/gi, '-').toLowerCase();

    // AI Call — async con polling + fallback entre modelos
    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        const industry = (document.getElementById('industry-select') || {}).value || 'general';
        setAiStatus('running', '⟳ Iniciando análisis IA...');

        const forceReanalyze = window._forceReanalyze || false;
        window._forceReanalyze = false;
        const aiResp = await fetch(`${apiUrl}/analyze`, {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ raw_data: raw, industry, force_reanalyze: forceReanalyze })
        });

        if (!aiResp.ok) throw new Error((await aiResp.json()).detail || 'Error AI');

        const jobData = await aiResp.json();

        if (jobData.status === 'completed') {
            // Cache hit — resultado inmediato
            setAiStatus('done', `✓ ${jobData.model_used || 'caché'} — resultado instantáneo`);
            lastScanId = jobData.scan_id || null;
            _activateScanActions(lastScanId, sh);
            updateAiFields(jobData.ai_content, sh);
        } else {
            // Nuevo job — polling en background, UI ya es visible
            setAiStatus('running', '⟳ Nova Pro procesando inventario...');
            pollJobStatus(jobData.job_id, sh, apiUrl);
        }
    } catch(err) {
        console.warn('AI Error:', err);
        setAiStatus('error', '✗ IA no disponible — mostrando análisis local');
        updateAiFields(null, sh);
        _activateScanActions(lastScanId, sh);
    }
};

window.updateAiFields = function(aiData, sh) {
    lastAiData = aiData;
    lastSh = sh;

    // ── Resumen Ejecutivo
    const execBox  = document.getElementById('exec-box');
    const execSum  = document.getElementById('exec-summary');
    if (aiData?.executive_summary && execBox && execSum) {
        execSum.innerText = aiData.executive_summary;
        execBox.style.display = 'block';
    }

    // ── Estrategia de Migración
    const strat = aiData?.migration_strategy;
    const stratBox = document.getElementById('strategy-box');
    if (strat && stratBox) {
        const badge = document.getElementById('strategy-badge');
        const rationale = document.getElementById('strategy-rationale');
        const timeline = document.getElementById('strategy-timeline');
        if (badge) badge.innerText = (strat.approach || '').toUpperCase();
        if (rationale) rationale.innerText = strat.rationale || '';
        if (timeline) timeline.innerText = strat.total_weeks ? `${strat.total_weeks} semanas · ${strat.phases || 4} fases` : '';
        stratBox.style.display = 'block';
    }

    // ── Quick Wins
    const qwBox  = document.getElementById('qw-box');
    const qwList = document.getElementById('qw-list');
    if (aiData?.quick_wins?.length && qwBox && qwList) {
        qwList.innerHTML = aiData.quick_wins.map(q => `
            <div style="background:rgba(0,176,155,.06);border:1px solid rgba(0,176,155,.25);border-radius:10px;padding:.7rem 1rem;margin-bottom:.5rem">
                <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.3rem;flex-wrap:wrap">
                    <span style="font-weight:700;font-size:.82rem">${q.title || ''}</span>
                    <span style="font-size:.65rem;color:var(--t2);background:rgba(0,0,0,.3);padding:.15rem .5rem;border-radius:10px">${q.effort || ''}</span>
                    <span style="font-size:.65rem;color:var(--blue);margin-left:auto">${q.owner || ''}</span>
                </div>
                <div style="font-size:.75rem;color:var(--t2);margin-bottom:.2rem">${q.description || ''}</div>
                ${q.risk_reduction ? `<div style="font-size:.7rem;color:var(--green)">▸ ${q.risk_reduction}</div>` : ''}
            </div>`).join('');
        qwBox.style.display = 'block';
    }

    // ── Sprints
    let sp0 = (aiData?.sprints) ? aiData.sprints.sprint_0 : ['Inventario EOL', 'Mapeo APIs', 'Seguridad'];
    let sp1 = (aiData?.sprints) ? aiData.sprints.sprint_1 : ['Containerización', 'CI/CD'];
    let sp2 = (aiData?.sprints) ? aiData.sprints.sprint_2 : ['Refactorización', 'Migración'];
    let sp3 = (aiData?.sprints) ? aiData.sprints.sprint_3 : ['Corte Cloud', 'Optimización'];

    document.getElementById('plan').innerHTML = spB('SPRINT 0 — Análisis y Seguridad', sp0) + spB('SPRINT 1 — Contenedores y CI/CD', sp1) + spB('SPRINT 2 — Refactorización', sp2) + spB('SPRINT 3 — Corte a Cloud', sp3);

    // SRE Steps in p1
    const sreList = document.getElementById('sre');
    if (sreList) {
        sreList.innerHTML = sp0.map(s => `<li style="padding:.25rem 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:.78rem">${s}</li>`).join('');
    }

    // ── Análisis Detallado de Agentes
    const agentBox     = document.getElementById('agent-box');
    const agentSummary = document.getElementById('agent-summary');
    if (aiData?.agent_analysis && agentBox && agentSummary) {
        agentSummary.innerText = aiData.agent_analysis;
        agentBox.style.display = 'block';
    }

    // ── Arquitectura Actual AS-IS — siempre visible (fallback local si IA no retorna campo)
    const currBox  = document.getElementById('current-arch-box');
    if (currBox) {
        const currArch   = aiData?.current_architecture;
        const scoreEl    = document.getElementById('coupling-score');
        const analysisEl = document.getElementById('coupling-analysis');
        const painEl     = document.getElementById('pain-points');

        // Score: usar el de la IA o estimar localmente con criticCount
        const score = currArch?.coupling_score
            ?? Math.min(10, 3 + (lastFindings.filter(f => f.sev === 'CRITICO').length) * 2);
        const scoreColor = score >= 7 ? 'var(--red)' : score >= 4 ? 'var(--yellow)' : 'var(--green)';
        if (scoreEl) { scoreEl.innerText = score; scoreEl.style.color = scoreColor; }
        if (analysisEl && currArch?.coupling_analysis) analysisEl.innerText = currArch.coupling_analysis;
        if (painEl && currArch?.pain_points?.length) {
            painEl.innerHTML = currArch.pain_points.map(p =>
                `<div style="font-size:.75rem;color:var(--red);padding:.2rem 0">▸ ${p}</div>`
            ).join('');
        }
        // El diagrama AS-IS se renderiza en triggerMermaid() — visible siempre
        currBox.style.display = 'block';
    }

    // ── Matriz de Riesgos
    const riskBox  = document.getElementById('risk-box');
    const riskBody = document.getElementById('risk-body');
    if (aiData?.risk_matrix?.length && riskBox && riskBody) {
        const probColor = p => p === 'Alta' ? 'var(--red)' : p === 'Media' ? 'var(--yellow)' : 'var(--green)';
        const impColor  = i => i === 'Crítico' ? 'var(--red)' : i === 'Alto' ? 'var(--yellow)' : 'var(--blue)';
        riskBody.innerHTML = aiData.risk_matrix.map(r => `
            <tr style="border-bottom:1px solid rgba(255,255,255,.04)">
                <td style="padding:.45rem .4rem;font-size:.75rem;font-weight:600">${r.risk || ''}</td>
                <td style="padding:.45rem .4rem;text-align:center">
                    ${r.cve && r.cve !== 'N/A'
                        ? `<a href="https://nvd.nist.gov/vuln/detail/${r.cve}" target="_blank" rel="noopener" style="font-size:.65rem;color:var(--red);text-decoration:none;background:rgba(255,65,108,.15);padding:.1rem .35rem;border-radius:4px">${r.cve}</a>`
                        : `<span style="font-size:.65rem;color:var(--t2)">—</span>`}
                </td>
                <td style="padding:.45rem .4rem;text-align:center;font-size:.72rem;font-weight:700;color:${probColor(r.probability)}">${r.probability || ''}</td>
                <td style="padding:.45rem .4rem;text-align:center;font-size:.72rem;font-weight:700;color:${impColor(r.impact)}">${r.impact || ''}</td>
                <td style="padding:.45rem .4rem;font-size:.72rem;color:var(--t2)">${r.mitigation || ''}</td>
            </tr>`).join('');
        riskBox.style.display = 'block';
    }

    // ── Remediación de Código (expandida)
    const remedBox  = document.getElementById('remed-box');
    const remedList = document.getElementById('remed-list');
    if (aiData?.code_remediation?.length && remedBox && remedList) {
        const priColor = p => p?.startsWith('P1') ? 'var(--red)' : p?.startsWith('P2') ? 'var(--yellow)' : 'var(--blue)';
        remedList.innerHTML = aiData.code_remediation.map(r => `
            <div style="background:rgba(0,0,0,.3);border:1px solid var(--bdr);border-radius:10px;padding:.8rem 1rem">
                <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.4rem">
                    <span style="font-weight:700;font-size:.82rem;color:var(--blue)">${r.file || ''}</span>
                    ${r.priority ? `<span style="font-size:.62rem;font-weight:700;padding:.15rem .5rem;border-radius:10px;background:rgba(0,0,0,.4);color:${priColor(r.priority)};border:1px solid ${priColor(r.priority)}">${r.priority}</span>` : ''}
                    ${r.effort ? `<span style="font-size:.62rem;color:var(--t2);margin-left:auto">${r.effort}</span>` : ''}
                </div>
                <div style="font-size:.78rem;color:#e0e0e0;margin-bottom:.3rem"><b>Problema:</b> ${r.issue || ''}</div>
                <div style="font-size:.78rem;color:var(--green);margin-bottom:.3rem"><b>Acción:</b> ${r.action || ''}</div>
                ${r.before ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin-top:.4rem">
                    <div><div style="font-size:.6rem;color:var(--red);margin-bottom:.2rem">ANTES</div><pre style="font-size:.65rem;max-height:80px;overflow:auto">${r.before}</pre></div>
                    <div><div style="font-size:.6rem;color:var(--green);margin-bottom:.2rem">DESPUÉS</div><pre style="font-size:.65rem;max-height:80px;overflow:auto">${r.after || ''}</pre></div>
                </div>` : ''}
                ${r.benefit ? `<div style="font-size:.72rem;color:var(--t2);margin-top:.3rem;border-top:1px solid var(--bdr);padding-top:.3rem">${r.benefit}</div>` : ''}
            </div>`).join('');
        remedBox.style.display = 'block';
    }

    // Code blocks — generar localmente si IA no los retornó
    _renderIaC(lastDetectedTechs, lastHost);

    // Trigger diagrams if current page needs it
    window.triggerMermaid();
};

window.spB = function(t, i) {
    if (!i) i = [];
    return `<div style="margin-bottom:1rem">
        <div style="font-weight:700;color:var(--blue);margin-bottom:.4rem">${t}</div>
        <ul style="list-style:none;font-size:.78rem">
            ${i.map(x => `<li style="padding:.25rem 0">${x}</li>`).join('')}
        </ul>
    </div>`;
};

window.tog = function(elId, rk) {
    const el = document.getElementById(elId);
    if(!el) return;
    el.style.display = el.style.display === 'block' ? 'none' : 'block';
};

// ─── Dashboard Ejecutivo ──────────────────────────────────────────────────────
window.loadDashboard = async function() {
    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        const r = await fetch(`${apiUrl}/stats`, { headers: authHeaders() });
        if (!r.ok) return;
        const d = await r.json();

        const el = id => document.getElementById(id);
        if (el('dash-total')) el('dash-total').innerText = d.total_scans ?? '—';
        if (el('dash-hosts')) el('dash-hosts').innerText = d.unique_hosts ?? '—';
        if (el('dash-last'))  el('dash-last').innerText  = d.last_scan
            ? new Date(d.last_scan).toLocaleString()
            : 'Sin datos';

        // Modelos usados en scans recientes
        if (el('dash-models') && d.recent) {
            const models = [...new Set(d.recent.map(r => r.model_used).filter(Boolean))]
                .map(m => m.replace('amazon.','').replace('-v1:0',''));
            el('dash-models').innerText = models.length ? models.join(', ') : '—';
        }

        // Tabla de actividad reciente
        const tbody = el('dash-recent');
        if (tbody && d.recent) {
            tbody.innerHTML = d.recent.map(s => `<tr>
                <td style="font-weight:700">${s.hostname}</td>
                <td style="color:var(--t2);font-size:.72rem">${new Date(s.timestamp).toLocaleString()}</td>
                <td style="color:var(--blue);font-size:.7rem">${s.model_used ? s.model_used.replace('amazon.','').replace('-v1:0','') : '—'}</td>
                <td><button class="bsm" style="margin-top:0" onclick="loadHistory('${s.id}');sw(0)">Cargar</button></td>
            </tr>`).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--t2)">Sin datos</td></tr>';
        }
    } catch(e) {
        console.warn('Dashboard error:', e);
    }
};

// ─── Comparación de Scans ─────────────────────────────────────────────────────
let _selectedScans = [];

window.toggleScanCheck = function(id, checked) {
    if (checked) {
        if (_selectedScans.length >= 2) {
            // Deselect oldest
            const old = _selectedScans.shift();
            const cb = document.getElementById('chk-' + old);
            if (cb) cb.checked = false;
        }
        _selectedScans.push(id);
    } else {
        _selectedScans = _selectedScans.filter(s => s !== id);
    }
    const bar = document.getElementById('compare-bar');
    const btn = document.getElementById('compare-btn');
    if (bar) bar.style.display = _selectedScans.length > 0 ? 'flex' : 'none';
    if (btn) btn.style.display = _selectedScans.length === 2 ? 'inline-block' : 'none';

    const hint = bar && bar.querySelector('span');
    if (hint) hint.innerText = _selectedScans.length === 2
        ? '2 escaneos seleccionados — listo para comparar'
        : `${_selectedScans.length}/2 seleccionado${_selectedScans.length !== 1 ? 's' : ''}`;
};

window.toggleAllChecks = function(master) {
    document.querySelectorAll('.scan-chk').forEach(cb => {
        cb.checked = master.checked;
        toggleScanCheck(cb.dataset.id, master.checked);
    });
};

window.compareSelected = async function() {
    if (_selectedScans.length !== 2) return;
    const apiUrl = window.API_URL || 'http://localhost:8000';
    const box = document.getElementById('compare-result');
    if (box) { box.style.display = 'block'; box.innerHTML = '<p style="color:var(--t2);font-size:.8rem">Cargando comparación...</p>'; }

    try {
        const [r1, r2] = await Promise.all(_selectedScans.map(id =>
            fetch(`${apiUrl}/history/${id}`, { headers: authHeaders() }).then(r => r.json())
        ));

        const a1 = window._discoveryFn ? window._discoveryFn(r1.raw_inventory) : null;
        const a2 = window._discoveryFn ? window._discoveryFn(r2.raw_inventory) : null;

        const ids1 = new Set((a1?.findings || []).map(f => f.id));
        const ids2 = new Set((a2?.findings || []).map(f => f.id));
        const resolved = (a1?.findings || []).filter(f => !ids2.has(f.id));
        const newIssues = (a2?.findings || []).filter(f => !ids1.has(f.id));
        const common   = (a1?.findings || []).filter(f => ids2.has(f.id));

        const mkList = (items, color) => items.length
            ? items.map(f => `<li style="padding:.2rem 0;color:${color};font-size:.75rem">${f.title}</li>`).join('')
            : `<li style="color:var(--t2);font-size:.72rem">Ninguno</li>`;

        if (box) box.innerHTML = `
            <div class="card" style="border-top:3px solid var(--purple)">
                <h3 style="font-size:.9rem;margin-bottom:1rem">Comparación de Escaneos</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
                    <div style="background:rgba(0,0,0,.3);padding:.8rem;border-radius:8px">
                        <div style="font-size:.7rem;color:var(--t2)">ESCANEO A</div>
                        <div style="font-weight:700">${r1.hostname}</div>
                        <div style="font-size:.68rem;color:var(--t2)">${new Date(r1.timestamp).toLocaleString()}</div>
                        <div style="margin-top:.4rem;font-size:.75rem">Riesgo: <span style="color:var(--red);font-weight:700">${a1?.criticalCount ?? '?'} críticos</span></div>
                    </div>
                    <div style="background:rgba(0,0,0,.3);padding:.8rem;border-radius:8px">
                        <div style="font-size:.7rem;color:var(--t2)">ESCANEO B</div>
                        <div style="font-weight:700">${r2.hostname}</div>
                        <div style="font-size:.68rem;color:var(--t2)">${new Date(r2.timestamp).toLocaleString()}</div>
                        <div style="margin-top:.4rem;font-size:.75rem">Riesgo: <span style="color:var(--red);font-weight:700">${a2?.criticalCount ?? '?'} críticos</span></div>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
                    <div>
                        <div style="font-size:.65rem;font-weight:700;color:var(--green);margin-bottom:.4rem">✓ RESUELTOS (${resolved.length})</div>
                        <ul style="list-style:none">${mkList(resolved, 'var(--green)')}</ul>
                    </div>
                    <div>
                        <div style="font-size:.65rem;font-weight:700;color:var(--yellow);margin-bottom:.4rem">⚠ EN COMÚN (${common.length})</div>
                        <ul style="list-style:none">${mkList(common, 'var(--yellow)')}</ul>
                    </div>
                    <div>
                        <div style="font-size:.65rem;font-weight:700;color:var(--red);margin-bottom:.4rem">✗ NUEVOS (${newIssues.length})</div>
                        <ul style="list-style:none">${mkList(newIssues, 'var(--red)')}</ul>
                    </div>
                </div>
            </div>`;
    } catch(e) {
        if (box) box.innerHTML = `<p style="color:var(--red);font-size:.8rem">Error al cargar comparación: ${e.message}</p>`;
    }
};

window.fetchHistory = async function() {
    const b = document.getElementById('hist-body');
    if(!b) return;
    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        let r = await fetch(`${apiUrl}/history`, { headers: authHeaders() });
        let data = await r.json();
        _selectedScans = [];
        const bar = document.getElementById('compare-bar');
        if (bar) bar.style.display = 'none';
        const cmpResult = document.getElementById('compare-result');
        if (cmpResult) cmpResult.style.display = 'none';

        b.innerHTML = data.map(i => `<tr>
            <td><input type="checkbox" class="scan-chk" id="chk-${i.id}" data-id="${i.id}" onchange="toggleCompareCheck('${i.id}', this)"></td>
            <td style="font-weight:700">${i.hostname}</td>
            <td style="color:var(--t2);font-size:.72rem">${new Date(i.timestamp).toLocaleString()}</td>
            <td style="color:var(--blue);font-size:.7rem">${i.model_used ? i.model_used.replace('amazon.','').replace('-v1:0','') : '—'}</td>
            <td style="display:flex;gap:.3rem;flex-wrap:wrap">
              <button class="bsm" style="margin-top:0" onclick="loadHistory('${i.id}')">Cargar</button>
              <button class="bsm" style="margin-top:0;background:rgba(157,80,187,.2);border-color:var(--purple);color:var(--purple)" onclick="downloadRunbook('${i.id}')">📜</button>
            </td>
        </tr>`).join('') || '<tr><td colspan="5" style="text-align:center">No hay registros</td></tr>';

    } catch(e) { b.innerHTML = '<tr><td colspan="4" style="color:var(--red);text-align:center">Error</td></tr>'; }
};

window.loadHistory = async function(id) {
    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        let r = await fetch(`${apiUrl}/history/${id}`, { headers: authHeaders() });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        let s = await r.json();

        lastScanId = id;
        document.getElementById('raw').value = s.raw_inventory || '';

        if (s.raw_inventory) {
            const histData = discoveryEngine.analyzeData(s.raw_inventory);
            _renderLocalUI(histData);
            lastHost = histData.host || s.hostname || '';
        }

        _activateScanActions(id, s.hostname);
        updateAiFields(s.bedrock_blueprint, s.hostname);
        sw(0);
    } catch(e) { alert('Error cargando historial: ' + e.message); }
};

// ─── Scan Actions (PDF / Chat / Jira) ────────────────────────────────────────
function _activateScanActions(scanId, hostname) {
    lastScanId = scanId;
    const pdfBtn       = document.getElementById('pdf-btn');
    const jiraBtn      = document.getElementById('jira-btn');
    const reanalyzeBtn = document.getElementById('reanalyze-btn');
    const fab          = document.getElementById('chat-fab');
    const label        = document.getElementById('chat-scan-label');
    if (pdfBtn)       pdfBtn.style.display       = scanId ? 'inline-block' : 'none';
    if (jiraBtn)      jiraBtn.style.display      = scanId ? 'inline-block' : 'none';
    if (reanalyzeBtn) reanalyzeBtn.style.display = 'inline-block';  // siempre visible tras análisis
    if (fab)          fab.style.display          = scanId ? 'flex' : 'none';
    if (label)        label.innerText            = scanId ? hostname || scanId.slice(0,8) : 'Sin analisis activo';
}

window.forceReanalyze = async function() {
    const raw = (document.getElementById('raw') || {}).value || '';
    if (!raw.trim()) { alert('No hay inventario en memoria. Realice un escaneo primero.'); return; }
    if (!confirm('¿Generar un análisis nuevo ignorando el caché?\nEsto llamará a la IA y puede tardar 1-2 minutos.')) return;
    window._forceReanalyze = true;
    await window.run();
};

// ─── PDF — Captura de diagrama SVG → PNG base64 ──────────────────────────────
async function _captureDiagramPng(elementId) {
    const container = document.getElementById(elementId);
    if (!container) return null;
    const svg = container.querySelector('svg');
    if (!svg) return null;
    try {
        const bbox = svg.getBoundingClientRect();
        const w    = Math.max(Math.round(bbox.width)  || 900, 400);
        const h    = Math.max(Math.round(bbox.height) || 400, 200);

        const clone = svg.cloneNode(true);
        clone.setAttribute('width',  w);
        clone.setAttribute('height', h);
        clone.setAttribute('xmlns',  'http://www.w3.org/2000/svg');

        // Fondo oscuro igual que en la UI
        const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bg.setAttribute('width', '100%'); bg.setAttribute('height', '100%');
        bg.setAttribute('fill', '#0d1117');
        clone.insertBefore(bg, clone.firstChild);

        const svgStr  = new XMLSerializer().serializeToString(clone);
        const svgB64  = btoa(unescape(encodeURIComponent(svgStr)));
        const dataUrl = 'data:image/svg+xml;base64,' + svgB64;

        return await new Promise(resolve => {
            const img    = new Image();
            img.onload   = () => {
                const canvas  = document.createElement('canvas');
                canvas.width  = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#0d1117';
                ctx.fillRect(0, 0, w, h);
                ctx.drawImage(img, 0, 0, w, h);
                resolve(canvas.toDataURL('image/png').split(',')[1]);
            };
            img.onerror = () => resolve(null);
            img.src = dataUrl;
        });
    } catch(e) {
        console.warn('[PDF] capture failed for', elementId, e.message);
        return null;
    }
}

// ─── PDF Download ─────────────────────────────────────────────────────────────
window.downloadPdf = async function() {
    const apiUrl = window.API_URL || 'http://localhost:8000';

    // Si no hay scanId local, intentar obtener el más reciente del historial
    let scanId = lastScanId;
    if (!scanId) {
        try {
            const hResp = await fetch(`${apiUrl}/history`, { headers: authHeaders() });
            if (hResp.ok) {
                const list = await hResp.json();
                if (list && list.length > 0) scanId = list[0].id;
            }
        } catch(_) {}
        if (!scanId) {
            alert('El PDF completo requiere análisis IA activo.\n\nConecta el backend y ejecuta un análisis para poder exportar el informe.');
            return;
        }
    }

    try {
        setAiStatus('running', '⟳ Capturando diagramas...');

        const [asIs, appFlow, infra] = await Promise.all([
            _captureDiagramPng('current-arch-diagram'),
            _captureDiagramPng('am'),
            _captureDiagramPng('im'),
        ]);

        setAiStatus('running', '⟳ Generando PDF...');
        const diagrams = {};
        if (asIs)    diagrams.asIs    = asIs;
        if (appFlow) diagrams.appFlow = appFlow;
        if (infra)   diagrams.infra   = infra;

        const r = await fetch(`${apiUrl}/export/pdf/${scanId}`, {
            method:  'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body:    JSON.stringify({ diagrams })
        });
        if (!r.ok) {
            // Si el scanId local no existe, intentar con el más reciente del historial
            if (r.status === 404 && scanId !== lastScanId) throw new Error('Scan no encontrado');
            if (r.status === 404) {
                const hResp = await fetch(`${apiUrl}/history`, { headers: authHeaders() });
                if (hResp.ok) {
                    const list = await hResp.json();
                    if (list && list.length > 0) {
                        const fallbackId = list[0].id;
                        const r2 = await fetch(`${apiUrl}/export/pdf/${fallbackId}`, {
                            method: 'POST',
                            headers: authHeaders({ 'Content-Type': 'application/json' }),
                            body: JSON.stringify({ diagrams })
                        });
                        if (r2.ok) {
                            const blob2 = await r2.blob();
                            const url2 = URL.createObjectURL(blob2);
                            const a2 = document.createElement('a');
                            a2.href = url2; a2.download = `modernization-report-${fallbackId.slice(0,8)}.pdf`;
                            a2.click(); URL.revokeObjectURL(url2);
                            lastScanId = fallbackId;
                            setAiStatus('done', '✓ PDF descargado (scan más reciente)');
                            return;
                        }
                    }
                }
            }
            const e = await r.json().catch(() => ({}));
            throw new Error(e.detail || r.statusText);
        }
        const blob = await r.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = `modernization-report-${lastScanId.slice(0,8)}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        setAiStatus('done', '✓ PDF descargado con diagramas');
    } catch(e) {
        setAiStatus('error', '✗ Error generando PDF: ' + e.message.slice(0, 60));
    }
};

// ─── Chat ─────────────────────────────────────────────────────────────────────
window.toggleChat = function() {
    const panel = document.getElementById('chat-panel');
    if (!panel) return;
    const visible = panel.style.display === 'flex';
    panel.style.display = visible ? 'none' : 'flex';
    if (!visible) document.getElementById('chat-input').focus();
};

window.sendChat = async function() {
    if (!lastScanId) { alert('Ejecuta un análisis primero para usar el chat.'); return; }
    const input   = document.getElementById('chat-input');
    const msgBox  = document.getElementById('chat-messages');
    const message = input.value.trim();
    if (!message) return;

    // Mostrar mensaje del usuario
    msgBox.innerHTML += `<div style="align-self:flex-end;background:rgba(0,210,255,.12);border:1px solid rgba(0,210,255,.25);border-radius:12px 12px 2px 12px;padding:.5rem .8rem;font-size:.78rem;max-width:85%">${message}</div>`;
    input.value = '';
    msgBox.scrollTop = msgBox.scrollHeight;

    // Spinner
    const spinnerId = 'chat-spin-' + Date.now();
    msgBox.innerHTML += `<div id="${spinnerId}" style="align-self:flex-start;color:var(--t2);font-size:.72rem;padding:.3rem">⟳ Consultando AI...</div>`;
    msgBox.scrollTop = msgBox.scrollHeight;

    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        const r = await fetch(`${apiUrl}/chat`, {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ scan_id: lastScanId, message })
        });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Error AI'); }
        const data = await r.json();

        document.getElementById(spinnerId)?.remove();
        const escaped = (data.response || '').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
        msgBox.innerHTML += `<div style="align-self:flex-start;background:var(--glass);border:1px solid var(--bdr);border-radius:12px 12px 12px 2px;padding:.5rem .8rem;font-size:.78rem;max-width:90%;line-height:1.5">${escaped}</div>`;
        msgBox.scrollTop = msgBox.scrollHeight;
    } catch(e) {
        document.getElementById(spinnerId)?.remove();
        msgBox.innerHTML += `<div style="color:var(--red);font-size:.72rem;padding:.3rem">✗ ${e.message}</div>`;
    }
};

// ─── Jira Export ──────────────────────────────────────────────────────────────
window.openJiraModal = function() {
    if (!lastScanId) { alert('Ejecuta un análisis primero.'); return; }
    const modal = document.getElementById('jira-modal');
    if (modal) { modal.style.display = 'flex'; }
    document.getElementById('jira-status').style.display = 'none';
};

window.submitJira = async function() {
    const jiraUrl = document.getElementById('jira-url').value.trim();
    const project = document.getElementById('jira-project').value.trim();
    const email   = document.getElementById('jira-email').value.trim();
    const token   = document.getElementById('jira-token').value.trim();
    const statusEl = document.getElementById('jira-status');

    if (!jiraUrl || !project || !email || !token) {
        statusEl.style.display = 'block';
        statusEl.style.cssText += ';color:var(--yellow);background:rgba(249,212,35,.08);border:1px solid var(--yellow);border-radius:6px;padding:.4rem .6rem';
        statusEl.innerText = 'Completa todos los campos.';
        return;
    }

    statusEl.style.display = 'block';
    statusEl.style.color = 'var(--t2)';
    statusEl.innerText = '⟳ Creando ticket en Jira...';

    try {
        const apiUrl = window.API_URL || 'http://localhost:8000';
        const r = await fetch(`${apiUrl}/export/jira`, {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ scan_id: lastScanId, jira_url: jiraUrl, project_key: project, user_email: email, api_token: token })
        });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText); }
        const data = await r.json();
        statusEl.style.color = 'var(--green)';
        statusEl.innerHTML = `✓ Ticket creado: <a href="${data.issue_url}" target="_blank" style="color:var(--blue)">${data.issue_key}</a>`;
        document.getElementById('jira-token').value = '';
    } catch(e) {
        statusEl.style.color = 'var(--red)';
        statusEl.innerText = '✗ ' + e.message.slice(0, 100);
    }
};

// ─── Sprint 2: Diff de Modernización ─────────────────────────────────────────
let _selectedForCompare = [];

window.toggleCompareCheck = function(scanId, cb) {
    if (cb.checked) {
        _selectedForCompare.push(scanId);
    } else {
        _selectedForCompare = _selectedForCompare.filter(id => id !== scanId);
    }
    const bar = document.getElementById('compare-bar');
    const btn = document.getElementById('compare-btn');
    if (bar) bar.style.display = _selectedForCompare.length > 0 ? 'flex' : 'none';
    if (btn) btn.style.display = _selectedForCompare.length === 2 ? 'inline-block' : 'none';
};

window.compareSelected = async function() {
    if (_selectedForCompare.length !== 2) {
        alert('Selecciona exactamente 2 escaneos para comparar.');
        return;
    }
    const [a, b] = _selectedForCompare;
    const apiUrl = window.API_URL || 'http://localhost:8000';
    const resultEl = document.getElementById('compare-result');
    if (resultEl) { resultEl.style.display = 'block'; resultEl.innerHTML = '<span style="color:var(--t2)">Comparando...</span>'; }
    try {
        const r = await fetch(`${apiUrl}/compare/${a}/${b}`, { headers: authHeaders() });
        if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
        const d = await r.json();
        if (!resultEl) return;
        const scoreColor = d.progress_score >= 50 ? 'var(--green)' : d.progress_score >= 20 ? 'var(--yellow)' : 'var(--red)';
        resultEl.innerHTML = `
        <div style="padding:.8rem;background:rgba(0,0,0,.3);border:1px solid var(--purple);border-radius:10px">
          <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:.8rem;flex-wrap:wrap">
            <h4 style="font-size:.9rem;color:var(--purple)">⚡ Diff de Modernización</h4>
            <span style="font-size:.7rem;color:var(--t2)">${d.scan_a.hostname} @ ${d.scan_a.timestamp} → ${d.scan_b.timestamp}</span>
            <span style="margin-left:auto;font-size:1.1rem;font-weight:700;color:${scoreColor}">${d.progress_score}% progreso</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;font-size:.75rem">
            <div>
              <div style="color:var(--green);font-weight:700;margin-bottom:.4rem">✅ Resueltos (${d.resolved.length})</div>
              ${d.resolved.length ? d.resolved.map(x => `<div style="padding:.2rem 0;color:#a0d0a0">▸ ${x}</div>`).join('') : '<div style="color:var(--t2)">—</div>'}
            </div>
            <div>
              <div style="color:var(--yellow);font-weight:700;margin-bottom:.4rem">⚠ Persisten (${d.persisted.length})</div>
              ${d.persisted.length ? d.persisted.map(x => `<div style="padding:.2rem 0;color:#d0c080">▸ ${x}</div>`).join('') : '<div style="color:var(--t2)">—</div>'}
            </div>
            <div>
              <div style="color:var(--red);font-weight:700;margin-bottom:.4rem">⚡ Nuevos (${d.new.length})</div>
              ${d.new.length ? d.new.map(x => `<div style="padding:.2rem 0;color:#d09090">▸ ${x}</div>`).join('') : '<div style="color:var(--t2)">—</div>'}
            </div>
          </div>
        </div>`;
    } catch(e) {
        if (resultEl) resultEl.innerHTML = `<span style="color:var(--red)">Error: ${e.message}</span>`;
    }
};

// ─── Sprint 3: Portfolio Multi-Servidor ──────────────────────────────────────
window.loadPortfolio = async function() {
    const apiUrl = window.API_URL || 'http://localhost:8000';
    const tbody  = document.getElementById('portfolio-body');
    const summEl = document.getElementById('portfolio-summary');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:1rem;color:var(--t2)">Cargando...</td></tr>';
    try {
        const r = await fetch(`${apiUrl}/dashboard/portfolio`, { headers: authHeaders() });
        if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
        const d = await r.json();

        // Summary pills
        if (summEl) {
            summEl.innerHTML = [
                `<div style="padding:.3rem .8rem;background:rgba(0,163,255,.15);border:1px solid var(--blue);border-radius:20px;font-size:.72rem">🖥️ <b>${d.total_servers}</b> servidores</div>`,
                `<div style="padding:.3rem .8rem;background:rgba(255,50,50,.15);border:1px solid var(--red);border-radius:20px;font-size:.72rem">🔴 <b>${d.critical}</b> críticos</div>`,
                `<div style="padding:.3rem .8rem;background:rgba(249,212,35,.15);border:1px solid var(--yellow);border-radius:20px;font-size:.72rem">⚠️ <b>${d.high}</b> altos</div>`,
                `<div style="padding:.3rem .8rem;background:rgba(0,255,150,.15);border:1px solid var(--green);border-radius:20px;font-size:.72rem">✅ <b>${d.low}</b> bajos</div>`,
            ].join('');
        }

        if (!d.servers || !d.servers.length) {
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:1rem;color:var(--t2)">Sin datos aún. Ejecuta al menos un análisis.</td></tr>';
            return;
        }

        const _riskColor = r => r === 'CRÍTICO' ? 'var(--red)' : r === 'ALTO' ? 'var(--yellow)' : 'var(--green)';
        if (tbody) tbody.innerHTML = d.servers.map(s => `
        <tr style="border-bottom:1px solid var(--bdr);transition:background .2s" onmouseover="this.style.background='rgba(255,255,255,.04)'" onmouseout="this.style.background=''"  >
          <td style="padding:.5rem .4rem;font-weight:600;color:var(--blue)">${s.hostname}</td>
          <td style="text-align:center;padding:.5rem .4rem">
            <span style="font-size:1.1rem;font-weight:700;color:${_riskColor(s.risk_level)}">${s.coupling_score}</span>
            <span style="font-size:.65rem;color:var(--t2)">/10</span>
          </td>
          <td style="text-align:center;padding:.5rem .4rem">
            <span style="padding:.15rem .5rem;border-radius:12px;font-size:.65rem;font-weight:700;background:${_riskColor(s.risk_level)}22;color:${_riskColor(s.risk_level)};border:1px solid ${_riskColor(s.risk_level)}">${s.risk_level}</span>
          </td>
          <td style="padding:.5rem .4rem;font-size:.72rem;color:var(--t2)">${s.approach || '—'}</td>
          <td style="text-align:center;padding:.5rem .4rem;color:var(--t2);font-size:.72rem">${s.total_scans}</td>
          <td style="text-align:center;padding:.5rem .4rem;font-size:.68rem;color:var(--t2)">${s.last_scan}</td>
          <td style="text-align:center;padding:.5rem .4rem">
            <button class="bsm" onclick="downloadRunbook('${s.last_scan_id}')" title="Descargar runbook bash">📜 Runbook</button>
          </td>
        </tr>`).join('');
    } catch(e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="color:var(--red);text-align:center;padding:1rem">Error: ${e.message}</td></tr>`;
    }
};

// ─── Sprint 3: Descargar Runbook ──────────────────────────────────────────────
window.downloadRunbook = async function(scanId) {
    if (!scanId) scanId = lastScanId;
    if (!scanId) { alert('No hay scan activo. Realiza un análisis primero.'); return; }
    const apiUrl = window.API_URL || 'http://localhost:8000';
    try {
        const r = await fetch(`${apiUrl}/generate/runbook/${scanId}`, { headers: authHeaders() });
        if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
        const blob = await r.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href = url;
        const cd = r.headers.get('Content-Disposition') || '';
        a.download = cd.match(/filename=([^\s;]+)/)?.[1] || `runbook_${scanId.slice(0,8)}.sh`;
        a.click();
        URL.revokeObjectURL(url);
    } catch(e) {
        alert('Error descargando runbook: ' + e.message);
    }
};
