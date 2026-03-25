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
            "Desplegar en EKS con Pod Security Policies endurecidas."
        ],
        terraform: `resource "aws_eks_cluster" "modern_factory" {
  name     = "modernization-eks"
  role_arn = aws_iam_role.eks.arn
  vpc_config {
    subnet_ids = [aws_subnet.private.id]
  }
}

resource "aws_db_instance" "oracle_target" {
  engine = "custom-oracle-ee"
  engine_version = "19"
  instance_class = "db.m5.large"
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
    // Risk Score
    document.getElementById('risk-score').innerText = data.system.risk;
    
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

    // IaC Section
    document.getElementById('iac-code').innerText = data.terraform;

    // Mermaid Diagram
    const mermaidContainer = document.getElementById('mermaid-container');
    mermaidContainer.removeAttribute('data-processed');
    mermaidContainer.innerHTML = data.mermaid;
    mermaid.init(undefined, mermaidContainer);
}
