// Modernization Factory - Engine App JS V1.0

async function analyzeData() {
    const rawData = document.getElementById('raw-input').value;
    if (!rawData) return alert('Por favor, pega los datos del colector.');

    const resultsDiv = document.getElementById('results');
    resultsDiv.style.display = 'block';

    // Motor de Detección Heurística V2.2
    const hasOracle = rawData.toLowerCase().includes('oracle');
    const hasJava = rawData.toLowerCase().includes('java');
    const hasTomcat = rawData.toLowerCase().includes('tomcat');
    const isRHEL4 = rawData.includes('release 4');
    
    // Extracción de Hostname (ejemplo básico)
    const hostnameMatch = rawData.match(/hostname[=\s]+([^\s\n]+)/i) || ["", "Unknown-Host"];
    const hostname = hostnameMatch[1];

    const analysis = {
        sre_analysis: {
            risk_score: isRHEL4 ? 9 : 5,
            complexity_score: hasJava && isRHEL4 ? 8 : 4,
            readiness_level: isRHEL4 ? "Crítica" : "Media",
            critical_vulnerabilities: []
        },
        financial_impact: {
            migration_effort_hours: isRHEL4 ? 480 : 120,
            estimated_migration_cost_usd: isRHEL4 ? 15000 : 5000,
            projected_cloud_monthly_usd: 1200,
            savings_vs_onprem_pct: 35,
            payback_months: isRHEL4 ? 12 : 6,
            cost_of_inaction_annual: isRHEL4 ? 85000 : 25000
        },
        target_architecture: {
            provider: "AWS",
            compute: "Amazon EKS",
            database_path: hasOracle ? ["Oracle 8 (Legacy)", "RDS Custom (Oracle 19c)"] : ["N/A (Capa de Aplicación Pura)"],
            mermaid_graph: ""
        },
        inventory_analytics: [],
        deployment_artifacts: {
            terraform_snippet: `resource "aws_eks_cluster" "factory" {\n  name = "modernization-${hostname}"\n}`,
            nginx_config: `server {\n    listen 80;\n    # Sticky sessions para ${hostname}\n    proxy_cookie_path / "/; HTTPOnly; Secure";\n}`,
            k8s_manifest: `apiVersion: v1\nkind: Deployment\nmetadata:\n  name: ${hostname.toLowerCase()}`
        },
        system: {
            hostname: hostname,
            os: isRHEL4 ? "RHEL 4 (Legacy)" : "Modern OS",
            stack: []
        }
    };

    // Construcción dinámica basada en detecciones
    if (isRHEL4) {
        analysis.sre_analysis.critical_vulnerabilities.push("Kernel 2.6 es incompatible con kernels modernos (6.x)");
        analysis.sre_analysis.critical_vulnerabilities.push("Falta de parches de seguridad (End of Life)");
    }
    if (hasJava) {
        analysis.system.stack.push("Java Detected");
        analysis.inventory_analytics.push({ item: "JDK Runtime", version: "Legacy", action: "Refactor", modern_alternative: "OpenJDK 17" });
    }
    if (hasTomcat) {
        analysis.system.stack.push("Tomcat");
        analysis.inventory_analytics.push({ item: "Tomcat Instance", version: "EOL", action: "Rehost/Refactor", modern_alternative: "Tomcat 10+" });
    }
    if (hasOracle) {
        analysis.system.stack.push("Oracle DB");
        analysis.inventory_analytics.push({ item: "Oracle Database", version: "Legacy", action: "Rehost", modern_alternative: "RDS Custom" });
    }

    // Generar Diagrama Mermaid Dinámico
    let mGraph = `graph TD\n    A[Internet] --> B[NGINX Ingress]\n    B --> C[Pod: ${hostname}]`;
    if (hasOracle) mGraph += `\n    C --> D[(RDS Custom: Oracle 19c)]`;
    analysis.target_architecture.mermaid_graph = mGraph;

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
