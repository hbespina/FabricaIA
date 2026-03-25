// Modernization Factory - Engine App JS V1.0

async function analyzeData() {
    const rawData = document.getElementById('raw-input').value;
    if (!rawData) return alert('Por favor, pega los datos del colector.');

    // Simulación de procesamiento de motor IA
    // En una implementación real, esto iría a una API de LLM
    const resultsDiv = document.getElementById('results');
    resultsDiv.style.display = 'block';

    // Mock Data basado en el análisis previo de RHEL 4
    const analysis = {
        sre_analysis: {
            risk_score: 9,
            complexity_score: 8,
            readiness_level: "Baja",
            critical_vulnerabilities: ["SSL/TLS v1.0", "Glibc Stack Overflow (Legacy)", "Unsupported Kernel 2.6"]
        },
        financial_impact: {
            migration_effort_hours: 480,
            estimated_migration_cost_usd: 15000,
            projected_cloud_monthly_usd: 1250,
            savings_vs_onprem_pct: 35,
            payback_months: 12,
            cost_of_inaction_annual: 85000
        },
        target_architecture: {
            provider: "AWS",
            compute: "Amazon EKS",
            database_path: ["Oracle 8 (Legacy)", "RDS Custom (Oracle 19c)", "Aurora PostgreSQL"],
            mermaid_graph: `graph TD
    A[NGINX Ingress] --> B[EKS Pods: Tomcat 1.4]
    B --> C[(RDS Custom: Oracle 19c)]
    style B fill:#3a7bd5,stroke:#fff,color:#fff
    style C fill:#9d50bb,stroke:#fff,color:#fff`
        },
        inventory_analytics: [
            { item: "JDK", version: "1.4.2_06", action: "Refactor", modern_alternative: "OpenJDK 17" },
            { item: "Apache Axis", version: "1.3", action: "Replace", modern_alternative: "Spring Web Services" },
            { item: "Oracle DB", version: "8.1.7", action: "Rehost", modern_alternative: "RDS Custom 19c" }
        ],
        deployment_artifacts: {
            terraform_snippet: `resource "aws_eks_cluster" "v2_1" {\n  name = "modernization-v2-1"\n}`,
            nginx_config: `server {\n    listen 80;\n    # Sticky session for Legacy\n    proxy_cookie_path / "/; HTTPOnly; Secure";\n}`,
            k8s_manifest: `apiVersion: v1\nkind: Pod\nmetadata:\n  name: legacy-app`
        },
        system: { // Legacy fallback
            hostname: "g100603sv446.cencosud.corp",
            os: "RHEL 4 (Update 6)",
            stack: ["Java 1.4", "Tomcat", "Axis"]
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
