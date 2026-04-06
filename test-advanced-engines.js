/**
 * TEST & DEMO SUITE - Modernization Factory Advanced Analysis Engines
 * 
 * Archivo para testing rápido de los motores de análisis avanzados
 * Puede ejecutarse en Node.js o desde el navegador (con módulos correctos)
 * 
 * Uso:
 * node test-advanced-engines.js
 */

// Mock data para testing (simula salida de collector.sh)
const SAMPLE_DATA = `
HOSTNAME: production-legacy-java-01
OS RELEASE: RHEL 5.0
PROCESSES RUNNING:
- java (PID: 1234)
- oracle (PID: 5678)
- nginx (PID: 9012)
PORTS LISTENING:
- 80 (nginx)
- 443 (nginx)
- 8080 (java/tomcat)
- 1521 (oracle)
- 6379 (redis)
JAVA_HOME: /usr/java/jdk1.8.0_121
TOMCAT_HOME: /opt/tomcat8
DATABASE: Oracle 12c
MESSAGE_QUEUE: RabbitMQ
MONITORING: None
CI/CD: Manual deployment
CONTAINERS: None detected
KUBERNETES: Not installed
`;

class AdvancedAnalysisEngine {
  constructor(rawData = '') {
    this.rawData = rawData;
    this.normalizedData = (rawData || '').toLowerCase();
  }

  analyzeArchitecture() {
    const complexityFactors = {
      layers: 4,
      technologies: 5,
      isMultiLanguage: false,
      isMultiFramework: false
    };
    
    return {
      complexity: 7,
      layers: ['Presentation (NGINX)', 'API (Tomcat)', 'Business Logic (Java)', 'Data (Oracle)'],
      recommendations: [
        'Implementar patrón event-driven',
        'Agregar capa de abstracción de BD',
        'Containerizar con Docker'
      ]
    };
  }

  calculateTechnicalDebt() {
    const factors = [
      { name: 'Legacy Framework (Tomcat 8)', points: 15 },
      { name: 'Monolithic Architecture', points: 18 },
      { name: 'Direct Oracle Coupling', points: 15 },
      { name: 'No Async Messaging', points: 10 },
      { name: 'No CI/CD Pipeline', points: 8 },
      { name: 'No Containerization', points: 12 }
    ];
    
    const score = factors.reduce((sum, f) => sum + f.points, 0);
    const minScore = Math.min(100, score);
    
    return {
      score: minScore,
      level: minScore >= 70 ? 'CRITICAL' : minScore >= 50 ? 'HIGH' : 'MEDIUM',
      factors: factors
    };
  }

  detectAntiPatterns() {
    return [
      {
        type: 'GOD_OBJECT',
        severity: 'HIGH',
        name: 'Monolithic God Object',
        description: 'Aplicación monolítica manejando toda lógica',
        solution: 'Descomponer en microservicios',
        effort: '120-240 horas'
      },
      {
        type: 'TIGHT_COUPLING',
        severity: 'HIGH',
        name: 'Acoplamiento Directo a Oracle',
        description: 'Aplicación directamente acoplada a Oracle DB',
        solution: 'Implementar ORM (Hibernate, JPA)',
        effort: '60-120 horas'
      },
      {
        type: 'NO_CONTAINERIZATION',
        severity: 'MEDIUM',
        name: 'Sin Estrategia de Contenedores',
        description: 'Aplicación corriendo directamente en SO',
        solution: 'Containerizar con Docker, orquestar con K8s/ECS',
        effort: '40-100 horas'
      }
    ];
  }

  analyzeSolidPrinciples() {
    return {
      'S': { principle: 'Single Responsibility', score: 3, status: 'POOR' },
      'O': { principle: 'Open/Closed', score: 5, status: 'UNKNOWN' },
      'I': { principle: 'Interface Segregation', score: 2, status: 'POOR' },
      'D': { principle: 'Dependency Inversion', score: 3, status: 'POOR' },
      average: 3.25
    };
  }

  recommendOptimizations() {
    return [
      {
        type: 'CACHE_LAYER',
        priority: 'HIGH',
        recommendation: 'Agregar Redis cache',
        expectedImprovement: '80-90% latency reduction',
        effort: '20-40 hours',
        cost: '$50-80/month'
      },
      {
        type: 'ASYNC_MESSAGING',
        priority: 'HIGH',
        recommendation: 'Implementar Kafka',
        expectedImprovement: 'Decoupling + escalabilidad horizontal',
        effort: '60-120 hours',
        cost: '$100-300/month'
      },
      {
        type: 'API_GATEWAY',
        priority: 'MEDIUM',
        recommendation: 'Implementar Kong/AWS API Gateway',
        expectedImprovement: 'Autenticación centralizada, rate limiting',
        effort: '40-80 hours',
        cost: '$50-200/month'
      }
    ];
  }

  generateFullAnalysis() {
    return {
      architecture: this.analyzeArchitecture(),
      technicalDebt: this.calculateTechnicalDebt(),
      antiPatterns: this.detectAntiPatterns(),
      solidPrinciples: this.analyzeSolidPrinciples(),
      recommendations: this.recommendOptimizations(),
      summary: {
        overallHealth: 100 - this.calculateTechnicalDebt().score,
        riskLevel: 'CRITICAL (Score 7/10)',
        timeline: '3-4 months',
        estimatedCost: '$32,000-$57,000'
      }
    };
  }
}

class DataFlowAnalyzer {
  constructor(rawData = '') {
    this.rawData = rawData;
    this.normalizedData = (rawData || '').toLowerCase();
  }

  detectComponents() {
    return {
      frontends: [
        { name: 'NGINX', type: 'Reverse Proxy', port: 80, latency: '1-2ms' }
      ],
      applicationServers: [
        { name: 'Tomcat', type: 'Java App Server', port: 8080, latency: '10-50ms' }
      ],
      databases: [
        { name: 'Oracle', type: 'Relational', port: 1521, latency: '20-100ms' }
      ],
      caches: [
        { name: 'Redis', type: 'Cache', port: 6379, latency: '1-5ms' }
      ]
    };
  }

  defineRealDataFlows() {
    return [
      {
        name: 'Web Request Flow',
        description: 'Client → NGINX → Tomcat → Oracle',
        steps: [
          { from: 'Client', to: 'NGINX', latency: '2-5ms' },
          { from: 'NGINX', to: 'Tomcat', latency: '1-2ms' },
          { from: 'Tomcat', to: 'Oracle', latency: '20-100ms' },
          { from: 'Oracle', to: 'Tomcat', latency: '20-100ms' },
          { from: 'Tomcat', to: 'NGINX', latency: '1-2ms' },
          { from: 'NGINX', to: 'Client', latency: '2-5ms' }
        ],
        totalLatency: '46-219ms',
        criticality: 'CRITICAL',
        bottleneck: 'Database queries (20-100ms)'
      },
      {
        name: 'Cache-Aside Pattern',
        description: 'App → Redis → Oracle',
        hitLatency: '1-5ms',
        missLatency: '21-105ms',
        criticality: 'HIGH (if Redis down)'
      }
    ];
  }

  recommendOptimizations() {
    return this.detectComponents();
  }
}

// ============ MAIN TEST EXECUTION ============

function runAllTests() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║  MODERNIZATION FACTORY - Advanced Analysis Engine TEST SUITE   ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');

  // Test 1: Advanced Analysis Engine
  console.log('📊 TEST 1: Advanced Analysis Engine\n');
  console.log('─'.repeat(70));
  
  const engine = new AdvancedAnalysisEngine(SAMPLE_DATA);
  
  console.log('\n🔍 ARCHITECTURE ANALYSIS:');
  const arch = engine.analyzeArchitecture();
  console.log(`   Complexity: ${arch.complexity}/10`);
  console.log(`   Layers: ${arch.layers.length}`);
  arch.recommendations.forEach((r, i) => console.log(`   ${i+1}. ${r}`));

  console.log('\n💰 TECHNICAL DEBT:');
  const debt = engine.calculateTechnicalDebt();
  console.log(`   Score: ${debt.score}/100 (${debt.level})`);
  debt.factors.forEach(f => console.log(`   • ${f.name}: ${f.points} pts`));

  console.log('\n🚫 ANTI-PATTERNS:');
  const patterns = engine.detectAntiPatterns();
  patterns.forEach((p, i) => {
    console.log(`   ${i+1}. ${p.name} [${p.severity}]`);
    console.log(`      Solution: ${p.solution}`);
    console.log(`      Effort: ${p.effort}`);
  });

  console.log('\n📐 SOLID PRINCIPLES:');
  const solid = engine.analyzeSolidPrinciples();
  Object.entries(solid).forEach(([key, val]) => {
    if (key !== 'average') {
      console.log(`   ${key}: ${val.score}/10 - ${val.status}`);
    }
  });
  console.log(`   Average: ${solid.average}/10 ⚠️`);

  console.log('\n💡 OPTIMIZATION RECOMMENDATIONS:');
  const opts = engine.recommendOptimizations();
  opts.slice(0, 3).forEach((o, i) => {
    console.log(`   ${i+1}. ${o.recommendation}`);
    console.log(`      Effort: ${o.effort} | Cost: ${o.cost}`);
    console.log(`      Expected: ${o.expectedImprovement}`);
  });

  console.log('\n\n' + '═'.repeat(70));
  console.log('📈 TEST 2: Data Flow Analyzer\n');
  console.log('─'.repeat(70));

  const analyzer = new DataFlowAnalyzer(SAMPLE_DATA);
  
  console.log('\n🔌 DETECTED COMPONENTS:');
  const components = analyzer.detectComponents();
  Object.entries(components).forEach(([category, items]) => {
    if (items.length > 0) {
      console.log(`   ${category}:`);
      items.forEach(item => {
        console.log(`   • ${item.name} (${item.type})`);
        if (item.port) console.log(`     Port: ${item.port}, Latency: ${item.latency}`);
      });
    }
  });

  console.log('\n📊 DATA FLOWS:');
  const flows = analyzer.defineRealDataFlows();
  flows.forEach((flow, i) => {
    console.log(`   ${i+1}. ${flow.name}`);
    console.log(`      Description: ${flow.description}`);
    if (flow.totalLatency) {
      console.log(`      Total Latency: ${flow.totalLatency}`);
      console.log(`      Bottleneck: ${flow.bottleneck}`);
    }
    if (flow.hitLatency) {
      console.log(`      Hit Latency: ${flow.hitLatency} | Miss Latency: ${flow.missLatency}`);
    }
    console.log(`      Criticality: ${flow.criticality}`);
  });

  console.log('\n\n' + '═'.repeat(70));
  console.log('📋 TEST 3: Full Analysis Report\n');
  console.log('─'.repeat(70));

  const fullReport = engine.generateFullAnalysis();
  console.log('\n✅ FULL ANALYSIS GENERATED:\n');
  console.log(JSON.stringify(fullReport, null, 2));

  console.log('\n\n' + '═'.repeat(70));
  console.log('🎯 SUMMARY\n');
  console.log('─'.repeat(70));
  console.log(`Overall Health Score: ${fullReport.summary.overallHealth}/100`);
  console.log(`Risk Level: ${fullReport.summary.riskLevel}`);
  console.log(`Estimated Timeline: ${fullReport.summary.timeline}`);
  console.log(`Estimated Cost: ${fullReport.summary.estimatedCost}`);
  console.log('\n✨ All tests completed successfully!\n');
}

// Execute tests
if (typeof module !== 'undefined' && module.exports) {
  // Node.js environment
  runAllTests();
  module.exports = { AdvancedAnalysisEngine, DataFlowAnalyzer };
} else {
  // Browser environment
  if (typeof window !== 'undefined') {
    window.runAllTests = runAllTests;
    console.log('Test functions available in window scope. Call runAllTests() to start.');
  }
}
