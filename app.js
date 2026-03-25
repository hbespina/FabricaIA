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
        system: {
            hostname: "g100603sv446.cencosud.corp",
            os: "Red Hat Enterprise Linux ES release 4 (Update 6)",
            risk: 9,
            stack: ["Java 1.4", "Tomcat", "Axis SOAP", "Apache 2.0"]
        },
        inventory: [
            { comp: "JDK", ver: "1.4.2_06", status: "Critical", icon: "🔴" },
            { comp: "Apache Axis", ver: "1.1/1.2/1.3", status: "EOL", icon: "⚠️" },
            { comp: "Tomcat", ver: "Multiple Instances", status: "High Risk", icon: "🔴" },
            { comp: "Altiris", ver: "Legacy Agent", status: "Shadow", icon: "🔍" }
        ],
        steps: [
            "Crear contenedor base en Amazon ECR con librerías compat-lib (glibc 2.3).",
            "Configurar RDS Custom para soporte de Oracle 8 -> 19c.",
            "Implementar NGINX Ingress con Sticky Sessions (Session Affinity).",
            "Terminar SSL en Ingress para mitigar obsolescencia de TLS en Axis 1.x."
        ],
        financial: {
            opex: "$1,250",
            migCost: "$15,000",
            payback: "12 meses",
            hours: "480"
        },
        scores: { risk: 9, complexity: 8, readiness: 4 },
        terraform: `resource "aws_eks_cluster" "modern_factory" {
  name     = "modernization-eks"
  role_arn = aws_iam_role.eks.arn
}`,
        nginx: `server {
    listen 80;
    server_name intratest.cencosud.corp;
    location / {
        proxy_pass http://tomcat-service;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Sticky session support
        proxy_cookie_path / "/; HTTPOnly; Secure";
    }
}`,
        mermaid: `graph TD
    A[NGINX Ingress] --> B[EKS: Tomcat Pods]
    B --> C[(RDS Custom: Oracle 19c)]
    style B fill:#3a7bd5,stroke:#fff,color:#fff
    style C fill:#9d50bb,stroke:#fff,color:#fff`
    };

    renderResults(analysis);
}

function renderResults(data) {
    // Scores
    document.getElementById('risk-score').innerText = data.scores.risk;
    document.getElementById('complexity-score').innerText = data.scores.complexity;
    document.getElementById('readiness-score').innerText = data.scores.readiness;
    
    // Financials
    document.getElementById('cloud-opex').innerText = data.financial.opex;
    document.getElementById('migration-cost').innerText = data.financial.migCost;
    document.getElementById('payback-period').innerText = data.financial.payback;
    document.getElementById('man-hours').innerText = data.financial.hours;

    // System Summary
    const summaryDiv = document.getElementById('system-summary');
    summaryDiv.innerHTML = `
        <p><strong>Host:</strong> ${data.system.hostname}</p>
        <p><strong>OS:</strong> ${data.system.os}</p>
        <div style="margin-top:0.5rem;">
            ${data.system.stack.map(s => `<span class="status-badge" style="margin-right:5px;">${s}</span>`).join('')}
        </div>
    `;

    // Inventory Table
    const invDiv = document.getElementById('inventory-table');
    invDiv.innerHTML = data.inventory.map(i => `
        <div style="display:flex; justify-content:space-between; padding:0.8rem; border-bottom:1px solid var(--glass-border);">
            <span>${i.icon} ${i.comp}</span>
            <span style="color:var(--text-secondary);">${i.ver}</span>
            <span style="color:var(--risk-high);">${i.status}</span>
        </div>
    `).join('');

    // Migration Steps
    const stepsUl = document.getElementById('migration-steps');
    stepsUl.innerHTML = data.steps.map(s => `
        <li style="margin-bottom:0.8rem; display:flex; gap:10px;">
            <div style="width:20px; height:20px; border-radius:50%; background:var(--accent-blue); flex-shrink:0;"></div>
            <span>${s}</span>
        </li>
    `).join('');

    // IaC & Config Section
    document.getElementById('iac-code').innerText = data.terraform;
    document.getElementById('nginx-code').innerText = data.nginx;

    // Mermaid Diagram
    const mermaidContainer = document.getElementById('mermaid-container');
    mermaidContainer.removeAttribute('data-processed');
    mermaidContainer.innerHTML = data.mermaid;
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
