// Modernization Factory - Engine App JS V1.0

async function analyzeData() {
    const rawData = document.getElementById('raw-input').value;
    if (!rawData) return alert('Por favor, pega los datos del colector.');

    const resultsDiv = document.getElementById('results');
    resultsDiv.style.display = 'block';

    // Intento de Análisis Real via Amazon Bedrock (Fase J)
    try {
        console.log("Intentando análisis vía Amazon Bedrock...");
        const response = await fetch('http://localhost:8000/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_data: rawData })
        });

        if (response.ok) {
            const bedrockAnalysis = await response.json();
            // Si el backend devuelve un string JSON, lo parseamos
            const result = typeof bedrockAnalysis === 'string' ? JSON.parse(bedrockAnalysis) : bedrockAnalysis;
            return renderResults(result);
        }
    } catch (err) {
        console.warn("Backend Bedrock no disponible. Usando Motor Heurístico Local V2.3.");
    }

    // --- FALLBACK: Motor de Parsing Estructural V2.3 (Local) ---
    const sections = rawData.split('---');
    let hostname = "Unknown-Host";
    let osInfo = "Unknown OS";
    let processes = "";

    const hostLine = rawData.match(/HOSTNAME:\s+([^\n\r]+)/i);
    if (hostLine) hostname = hostLine[1].trim();

    sections.forEach(s => {
        if (s.includes('OS RELEASE')) osInfo = s.replace('OS RELEASE ---', '').trim();
        if (s.includes('PROCESSES')) processes = s;
    });

    const isLegacy = osInfo.toLowerCase().includes('release 4') || osInfo.toLowerCase().includes('release 5');
    const hasOracle = rawData.toLowerCase().includes('oracle') || processes.toLowerCase().includes('tnslsnr');
    const hasJava = rawData.toLowerCase().includes('java') || processes.toLowerCase().includes('java');
    const hasTomcat = processes.toLowerCase().includes('tomcat') || processes.toLowerCase().includes('catalina');

    const analysis = {
        sre_analysis: {
            risk_score: isLegacy ? 9 : 3,
            complexity_score: isLegacy ? 8 : 2,
            readiness_level: isLegacy ? "Crítica" : "Excelente",
            critical_vulnerabilities: isLegacy ? ["Kernel Gap 2.6", "Glibc Desactualizado"] : ["Upgrade via App Runner"]
        },
        financial_impact: {
            migration_effort_hours: isLegacy ? 480 : 40,
            estimated_migration_cost_usd: isLegacy ? 15000 : 2000,
            projected_cloud_monthly_usd: 1200,
            savings_vs_onprem_pct: isLegacy ? 35 : 15,
            payback_months: isLegacy ? 12 : 4,
            cost_of_inaction_annual: isLegacy ? 85000 : 5000
        },
        target_architecture: {
            provider: "AWS (Heuristic)",
            compute: isLegacy ? "Amazon EKS" : "AWS App Runner",
            database_path: hasOracle ? ["Oracle Legacy", "RDS Custom"] : ["N/A"],
            mermaid_graph: `graph TD\n    A[Internet] --> B[NGINX]\n    B --> C[Pod: ${hostname}]`
        },
        inventory_analytics: hasJava ? [{ item: "Java Runtime", version: "Legacy", action: "Refactor", modern_alternative: "Corretto 17" }] : [],
        deployment_artifacts: {
            terraform_snippet: `resource "aws_eks_cluster" "factory" {\n  name = "modernization-${hostname.toLowerCase()}"\n}`,
            nginx_config: `server {\n    listen 80;\n    server_name ${hostname};\n}`,
            k8s_manifest: `apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: ${hostname.toLowerCase().split('.')[0]}`
        },
        system: {
            hostname: hostname,
            os: osInfo.split('\n')[0],
            stack: hasJava ? ["Java"] : ["Generic"]
        }
    };

    renderResults(analysis);
}

function renderResults(data) {
    // SRE Scores V2.1
    document.getElementById('risk-score').innerText = data.sre_analysis.risk_score;
    document.getElementById('complexity-score').innerText = data.sre_analysis.complexity_score;
    document.getElementById('readiness-score').innerText = data.sre_analysis.readiness_level;
    document.getElementById('compliance-gap').innerText = "HIGH";
    
    // Financial Impact V2.1
    document.getElementById('cloud-opex').innerText = `$${data.financial_impact.projected_cloud_monthly_usd}`;
    document.getElementById('migration-cost').innerText = `$${data.financial_impact.estimated_migration_cost_usd}`;
    document.getElementById('payback-period').innerText = `${data.financial_impact.payback_months} meses`;
    document.getElementById('inaction-cost').innerText = `$${data.financial_impact.cost_of_inaction_annual}`;

    // System Summary
    const summaryDiv = document.getElementById('system-summary');
    summaryDiv.innerHTML = `
        <p><strong>Host:</strong> ${data.system.hostname}</p>
        <p><strong>OS:</strong> ${data.system.os}</p>
        <div style="margin-top:0.5rem;">
            ${data.system.stack.map(s => `<span class="status-badge" style="margin-right:5px;">${s}</span>`).join('')}
        </div>
    `;

    // Inventory Analytics V2.1
    const invDiv = document.getElementById('inventory-table');
    invDiv.innerHTML = data.inventory_analytics.map(i => `
        <div style="display:flex; justify-content:space-between; padding:0.8rem; border-bottom:1px solid var(--glass-border);">
            <span>${i.item} <small style="color:var(--text-secondary);">(${i.version})</small></span>
            <span style="font-weight:bold; color:var(--accent-blue);">${i.action}</span>
            <span style="color:var(--text-secondary);">${i.modern_alternative}</span>
        </div>
    `).join('');

    // SRE Recommendations V2.1 (Vulnerabilidades)
    const stepsUl = document.getElementById('migration-steps');
    stepsUl.innerHTML = data.sre_analysis.critical_vulnerabilities.map(v => `
        <li style="margin-bottom:0.8rem; display:flex; gap:10px;">
            <div style="width:10px; height:10px; border-radius:50%; background:var(--risk-high); flex-shrink:0; margin-top:5px;"></div>
            <span>${v}</span>
        </li>
    `).join('');

    // IaC & Config Section V2.1
    document.getElementById('iac-code').innerText = data.deployment_artifacts.terraform_snippet + "\n\n" + data.deployment_artifacts.k8s_manifest;
    document.getElementById('nginx-code').innerText = data.deployment_artifacts.nginx_config;

    // Mermaid Diagram V2.1 (Dynamic from JSON)
    const mermaidContainer = document.getElementById('mermaid-container');
    mermaidContainer.removeAttribute('data-processed');
    mermaidContainer.innerHTML = data.target_architecture.mermaid_graph;
    mermaid.init(undefined, mermaidContainer);

    // Persistir análisis
    saveAnalysis(data);
}

// Persistencia Local [NEW G]
function saveAnalysis(data) {
    localStorage.setItem('latest_analysis', JSON.stringify(data));
}

// Chat Assistant Logic [NEW G]
function toggleChat() {
    const win = document.getElementById('chat-window');
    win.style.display = win.style.display === 'flex' ? 'none' : 'flex';
}

function sendMessage() {
    const input = document.getElementById('user-msg');
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    input.value = '';

    // Respuestas SRE simuladas
    setTimeout(() => {
        let reply = "Como experto SRE, te sugiero revisar las dependencias de red en el puerto 8101 antes del cut-over.";
        if (text.toLowerCase().includes('costo')) reply = "El costo OPEX estimado es conservador; considera un 10% adicional por transferencia de datos (Egress).";
        if (text.toLowerCase().includes('riesgo')) reply = "El mayor riesgo es el Kernel gap (2.6 vs 6.x). Recomiendo usar contenedores con syscall interception.";
        addMessage(reply, 'bot');
    }, 1000);
}

function addMessage(text, side) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `msg ${side}`;
    msgDiv.innerText = text;
    document.getElementById('chat-messages').appendChild(msgDiv);
    msgDiv.scrollIntoView();
}

// Cargar último análisis si existe
window.onload = () => {
    const saved = localStorage.getItem('latest_analysis');
    if (saved) {
        console.log("Cargando análisis previo...");
        // Podríamos auto-renderizar aquí si quisiéramos
    }
}
