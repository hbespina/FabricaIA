/**
 * Test: UnifiedAnalysisOrchestrator en Acción
 * Muestra cómo las 3 capas de análisis mejoran los resultados
 */

// Importar el Orchestrator (en Node.js)
// const UnifiedAnalysisOrchestrator = require('./lib/unifiedAnalysisOrchestrator');

// Simulación de datos del collector.sh (entrada típica)
const SAMPLE_RAW_DATA = `
HOSTNAME: legacy-system-01
DATE: 2024-03-30

--- METADATA ---
Linux legacy-system-01 4.19.0-8-generic #8-Ubuntu x86_64 GNU/Linux
NAME="Ubuntu"
VERSION="18.04.3 LTS (Bionic Beaver)"

--- HARDWARE ---
8
             total       used       free     shared    buffers     cached
Mem:         15.6G      12.3G      3.3G     120.0M       0.0B      5.2G

--- RUNNING PROCESSES ---
oracle    1234   0.8  4.2   4567890  675432 ?   Sl   09:15   0:48 ora_pmon_TESTDB
oracle    2345   0.6  2.1   2345678  342567 ?   Sl   09:15   0:32 ora_dbw0_TESTDB
java      3456  15.2 28.5 3456789000 4567890 ?   Sl   09:22   2:15 /opt/websphere/java/bin/java -Xmx2048m ...
java      4567   2.1  8.3   234567890  1234567 ?   Sl   09:25   0:45 /opt/tomcat/bin/catalina.sh run
root      5678   0.0  0.0    12345     6789 ?   Ss   09:30   0:01 /usr/sbin/sshd -D

--- NETWORK PORTS ---
tcp        0      0 127.0.0.1:22           0.0.0.0:*               LISTEN      5678/sshd
tcp        0      0 0.0.0.0:8080           0.0.0.0:*               LISTEN      4567/java
tcp        0      0 0.0.0.0:8443           0.0.0.0:*               LISTEN      4567/java
tcp        0      0 0.0.0.0:1521           0.0.0.0:*               LISTEN      1234/oracle
tcp        0      0 0.0.0.0:80             0.0.0.0:*               LISTEN      6789/apache2
tcp        0      0 0.0.0.0:443            0.0.0.0:*               LISTEN      6789/apache2

--- JAVA LIBS ---
/opt/tomcat/lib/axis.jar
/opt/tomcat/lib/commons-dbcp-1.4.jar
/opt/tomcat/lib/struts-1.3.8.jar
/opt/tomcat/lib/log4j-1.2.15.jar

--- ENVIRONMENT ---
JAVA_HOME=/usr/lib/jvm/java-8-openjdk
CATALINA_HOME=/opt/tomcat

=== END INVENTORY ===
`;

/**
 * Clase de prueba que simula el Orchestrator
 * (En producción, importarías desde lib/unifiedAnalysisOrchestrator.js)
 */
class TestUnifiedAnalysis {
  constructor() {
    this.timestamp = new Date().toISOString();
  }

  // Simula Stage 1
  stage1_Discovery(rawData) {
    console.log('\n' + '='.repeat(80));
    console.log('📍 STAGE 1: DISCOVERY ENGINE (Local Heuristic Analysis)');
    console.log('='.repeat(80));
    console.log();

    const analysis = {
      discovered_components: [
        {
          name: 'Oracle Database 12.2',
          port: 1521,
          role: 'Data Storage',
          detected_by: 'port_listening',
          action: 'Migrate to Amazon Aurora / RDS',
          risk: 'CRITICAL',
          notes: 'Direct TCP connection, no abstraction'
        },
        {
          name: 'Java 8 Runtime',
          process: 'java',
          version: '8',
          ports: [8080, 8443, 7001],
          role: 'Application Server',
          detected_by: 'process_scan',
          action: 'Upgrade to Java 17+ or Migrate app',
          risk: 'HIGH',
          notes: 'EOL version, security vulnerabilities'
        },
        {
          name: 'Apache HTTPD',
          process: 'apache2',
          ports: [80, 443],
          role: 'Web Server',
          detected_by: 'port_listening',
          action: 'Replace with NGINX or ALB',
          risk: 'MEDIUM',
          notes: 'Legacy, consider API Gateway'
        },
        {
          name: 'Tomcat',
          path: '/opt/tomcat',
          process: 'catalina.sh',
          ports: [8080],
          role: 'Application Container',
          detected_by: 'process_scan',
          action: 'Containerize with Docker',
          risk: 'MEDIUM',
          notes: 'No native docker support'
        },
        {
          name: 'IBM WebSphere (suspected)',
          path: '/opt/websphere',
          process: 'java',
          role: 'Legacy App Server',
          detected_by: 'path_scan',
          action: 'Migrate to Open Liberty or Spring Boot',
          risk: 'CRITICAL',
          notes: 'Proprietary, expensive, hard to scale'
        }
      ],
      
      infrastructure_flags: {
        is_monolithic: true,
        is_legacy: true,
        has_web_tier: true,
        has_app_tier: true,
        has_data_tier: true,
        containerized: false,
        orchestrated: false,
        has_load_balancer: false,
        has_redundancy: false
      },

      quick_recommendations: [
        '⛔ STOP using direct TCP to database (add ORM layer)',
        '⛔ STOP running on Java 8 (update to 17+)',
        '🔄 ADOPT containerization (Docker → Kubernetes)',
        '🔄 ADOPT CI/CD pipeline (Jenkins, GitLab, etc)',
        '✅ ADD caching layer (Redis)',
        '✅ ADD monitoring (Prometheus, ELK)'
      ]
    };

    console.log(`✓ Detected ${analysis.discovered_components.length} components`);
    console.log(`✓ Monolithic: ${analysis.infrastructure_flags.is_monolithic ? 'YES' : 'NO'}`);
    console.log(`✓ Legacy: ${analysis.infrastructure_flags.is_legacy ? 'YES' : 'NO'}`);
    console.log(`✓ Containerized: ${analysis.infrastructure_flags.containerized ? 'YES' : 'NO'}`);
    console.log();

    analysis.discovered_components.forEach((comp, i) => {
      console.log(`  ${i + 1}. ${comp.name} (${comp.role})`);
      console.log(`     Risk: ${comp.risk} | Action: ${comp.action}`);
    });

    return analysis;
  }

  // Simula Stage 2
  stage2_AdvancedAnalysis(stage1Results) {
    console.log('\n' + '='.repeat(80));
    console.log('🧠 STAGE 2: ADVANCED ANALYSIS (Specialized Engines)');
    console.log('='.repeat(80));
    console.log();

    const analysis = {
      technical_debt: {
        score: 82,
        level: 'CRÍTICO',
        factors_breakdown: {
          'Legacy Framework (WebSphere/Java8)': 25,
          'No Containerization': 20,
          'Direct Database Coupling': 15,
          'No CI/CD Pipeline': 15,
          'Monolithic Architecture': 15,
          'No Observability (No Prometheus/ELK)': 12
        },
        recommendation: 'Urgent refactoring needed. This system will become unmaintainable in 12 months.'
      },

      anti_patterns_detected: [
        {
          id: 1,
          type: 'MONOLITHIC_GOD_OBJECT',
          severity: 'CRÍTICA',
          description: 'Entire business logic in single Java app + direct DB coupling',
          impact: 'Impossible to scale independently. Single deployment = full risk. Cannot parallelize development.',
          solution: 'Decompose into microservices (Auth, Payment, Inventory, etc.)',
          effort_hours: 480,
          timeline_weeks: 16
        },
        {
          id: 2,
          type: 'LEGACY_FRAMEWORK',
          severity: 'CRÍTICA',
          description: 'Java 8 + WebSphere + deprecated libraries (Log4j 1.2, Struts 1.3, Commons-DBCP)',
          impact: 'Security vulnerabilities. No support. Hard to hire developers. Licensing costs.',
          solution: 'Migrate to Spring Boot 3.x + Quarkus. Upgrade Log4j, use ORM (Hibernate), modern auth.',
          effort_hours: 240,
          timeline_weeks: 12
        },
        {
          id: 3,
          type: 'CIRCULAR_DEPENDENCY',
          severity: 'MEDIA',
          description: 'Direct TCP connection from App to Oracle. No data access layer. Tight coupling.',
          impact: 'Database schema changes break code. Hard to test. Cannot mock database.',
          solution: 'Implement Data Access Layer (DAL) + ORM (JPA/Hibernate)',
          effort_hours: 160,
          timeline_weeks: 8
        },
        {
          id: 4,
          type: 'NO_CONTAINERIZATION',
          severity: 'MEDIA',
          description: 'Running on bare OS. No Docker. Infrastructure tightly coupled to OS version.',
          impact: 'Difficult to scale. Deployment errors. Environment drift (dev ≠ prod).',
          solution: 'Containerize with Docker. Deploy to ECS or Kubernetes.',
          effort_hours: 120,
          timeline_weeks: 6
        },
        {
          id: 5,
          type: 'SINGLE_POINT_OF_FAILURE',
          severity: 'CRÍTICA',
          description: 'Single app server + single database + no failover',
          impact: 'Any failure = complete outage. No redundancy. Business stops.',
          solution: 'Implement RDS Multi-AZ + load balancer + health checks',
          effort_hours: 100,
          timeline_weeks: 4
        },
        {
          id: 6,
          type: 'NO_ASYNC_ARCHITECTURE',
          severity: 'MEDIA',
          description: 'All operations blocking. No message queue (Kafka/RabbitMQ)',
          impact: 'Poor scalability. High latency. Cannot handle spikes.',
          solution: 'Add Kafka/RabbitMQ for async jobs. Implement background workers.',
          effort_hours: 120,
          timeline_weeks: 6
        },
        {
          id: 7,
          type: 'MANUAL_SCALING',
          severity: 'MEDIA',
          description: 'No auto-scaling. Must manually provision servers.',
          impact: 'Cannot handle traffic spikes. Over-provisioning = wasted $. Under-provisioning = downtime.',
          solution: 'Implement ASG (Auto Scaling Group) or Kubernetes HPA',
          effort_hours: 60,
          timeline_weeks: 3
        }
      ],

      data_flow_analysis: {
        primary_flow: {
          name: 'Web Request Flow (Synchronous)',
          steps: [
            { step: 1, component: 'Client Browser', latency_ms: 0, location: 'Internet' },
            { step: 2, component: 'Apache (Front-end)', latency_ms: 2, location: 'Port 80/443', bottleneck: false },
            { step: 3, component: 'Apache → Tomcat', latency_ms: 5, location: 'Network', bottleneck: false },
            { step: 4, component: 'Tomcat (App Logic)', latency_ms: 50, location: 'Port 8080', bottleneck: false },
            { step: 5, component: 'Tomcat → Oracle', latency_ms: 3, location: 'Network', bottleneck: false },
            { step: 6, component: 'Oracle Query', latency_ms: 80, location: 'Database (Port 1521)', bottleneck: true },
            { step: 7, component: 'Oracle → Tomcat', latency_ms: 3, location: 'Network', bottleneck: false },
            { step: 8, component: 'Response to Client', latency_ms: 5, location: 'Network', bottleneck: false }
          ],
          total_latency: { min: 148, max: 250, avg: 180 },
          bottlenecks: [
            'DATABASE QUERY (80ms) - 44% of total latency',
            'APP LOGIC (50ms) - 28% of total latency'
          ],
          optimization_opportunities: [
            '+60% faster: Cache frequently-queried data in Redis (8ms cache hit)',
            '+40% faster: Reduce DB round-trips with batching',
            '+30% faster: Add database indexes on frequently-searched columns',
            '+25% faster: Implement query result pagination (instead of full scans)'
          ]
        }
      },

      solid_principles_analysis: {
        single_responsibility: {
          score: 2,
          assessment: 'POOR - Single monolithic object handles all responsibilities',
          recommendation: 'Split into UserService, PaymentService, OrderService, etc.'
        },
        open_closed: {
          score: 3,
          assessment: 'POOR - Tightly coupled to Oracle. Adding new data sources = code changes.',
          recommendation: 'Use DAO pattern. New data source = new DAO implementation, no core changes.'
        },
        liskov_substitution: {
          score: 4,
          assessment: 'POOR - Direct database dependency. Cannot easily substitute implementations.',
          recommendation: 'Use interfaces. Implement for Oracle, MySQL, PostgreSQL independently.'
        },
        interface_segregation: {
          score: 2,
          assessment: 'POOR - Monolithic Interface. Clients depend on everything.',
          recommendation: 'Break into smaller, focused APIs: /auth, /orders, /inventory, etc.'
        },
        dependency_inversion: {
          score: 2,
          assessment: 'POOR - Depends on low-level details (Oracle, Tomcat)',
          recommendation: 'Depend on abstractions. Use Spring DI to inject dependencies.'
        },
        average_score: 2.6,
        overall_assessment: 'CRÍTICO - System violates all SOLID principles',
        action_items: [
          'Implement Dependency Injection (Spring Framework)',
          'Break monolith into bounded contexts (Domain-Driven Design)',
          'Use interfaces for all major components',
          'Implement facade pattern for external APIs'
        ]
      },

      architecture_health: {
        overall_score: 2,
        scale_readiness: 'POOR - Cannot handle >2x traffic increase',
        maintainability: 'POOR - High complexity, low cohesion',
        security_posture: 'POOR - Java 8, Log4j vulnerabilities',
        modifiability: 'POOR - Changes require full regression testing',
        time_to_market: 'POOR - 4-6 weeks per release cycle',
        recommended_target_state: 'Microservices on Kubernetes with event-driven architecture'
      }
    };

    console.log(`📊 Technical Debt Score: ${analysis.technical_debt.score}/100 (${analysis.technical_debt.level})`);
    console.log();
    console.log('   Factors:');
    Object.entries(analysis.technical_debt.factors_breakdown).forEach(([factor, points]) => {
      console.log(`     • ${factor}: +${points} points`);
    });
    console.log();

    console.log(`⚠️  Anti-patterns Detected: ${analysis.anti_patterns_detected.length}`);
    analysis.anti_patterns_detected.forEach((ap, i) => {
      console.log(`   ${i + 1}. [${ap.severity}] ${ap.type}`);
      console.log(`      Impact: ${ap.impact}`);
      console.log(`      Solution: ${ap.solution}`);
      console.log(`      Effort: ${ap.effort_hours}h (${ap.timeline_weeks} weeks)`);
      console.log();
    });

    console.log(`📈 Data Flows: ${analysis.data_flow_analysis.primary_flow.steps.length} steps`);
    console.log(`   Total Latency: ${analysis.data_flow_analysis.primary_flow.total_latency.avg}ms average`);
    console.log(`   Bottleneck: ${analysis.data_flow_analysis.primary_flow.bottlenecks[0]}`);
    console.log();

    console.log(`📋 SOLID Principles: Average ${analysis.solid_principles_analysis.average_score.toFixed(1)}/10 (${analysis.solid_principles_analysis.overall_assessment})`);
    console.log();

    return analysis;
  }

  // Simula Stage 3 (Respuesta IA)
  stage3_AIEnrichment(stage1Results, stage2Results) {
    console.log('\n' + '='.repeat(80));
    console.log('🤖 STAGE 3: AI ENRICHMENT (AWS Bedrock + Claude 3.5 Sonnet)');
    console.log('='.repeat(80));
    console.log();

    const analysis = {
      status: 'AI_ANALYSIS_COMPLETE',
      model: 'Claude 3.5 Sonnet (via AWS Bedrock)',
      confidence: 0.94,

      executive_summary: `
This system represents a classic legacy monolith with critical technical debt (82/100).
The architecture is:
- Tightly coupled (direct DB access, no abstraction layers)
- Unscalable (single point of failure, no redundancy)
- High-risk (Java 8 EOL, vulnerable librariesm no observability)
- Difficult to maintain (monolithic design, tight deployment coupling)

Recommendation: Immediate modernization required. Estimated ROI: 18-24 months.
      `,

      migration_roadmap: {
        philosophy: 'Strangler Fig Pattern - Incrementally replace components without full rewrite',
        phases: [
          {
            phase: 1,
            name: 'Assessment & Containerization',
            duration: '12-14 weeks',
            effort_hours: 480,
            cost_estimate: '$200K - $300K',
            teams_required: ['DevOps', 'SRE', 'Architects'],
            tasks: [
              '✓ Baseline current performance metrics',
              '✓ Containerize existing app with Docker',
              '✓ Set up CI/CD pipeline (GitLab/Jenkins)',
              '✓ Implement logging & monitoring (ELK stack)',
              '✓ Create Kubernetes cluster (EKS on AWS)',
              '✓ Deploy first instance to K8s'
            ],
            acceptance_criteria: [
              'App runs in Docker locally',
              'Automated tests run on every commit',
              'Metrics visible in Grafana dashboard',
              'App deployed to staging K8s cluster'
            ]
          },

          {
            phase: 2,
            name: 'Data Modernization (Oracle → Aurora)',
            duration: '16-18 weeks',
            effort_hours: 640,
            cost_estimate: '$400K - $500K',
            teams_required: ['DBA', 'Backend', 'Data Engineer'],
            tasks: [
              '✓ Audit Oracle schema & identify dependencies',
              '✓ Set up Amazon Aurora with Read Replicas',
              '✓ Implement data migration tool (AWS DMS)',
              '✓ Create fallback/rollback procedures',
              '✓ Run parallel Oracle + Aurora (shadow testing)',
              '✓ Cutover to Aurora (zero-downtime migration)'
            ],
            acceptance_criteria: [
              'All data migrated to Aurora',
              'Aurora read/write latency < 10ms',
              'Database failover tested and working',
              'Cost reduced by 40% vs Oracle license'
            ]
          },

          {
            phase: 3,
            name: 'Service Decomposition (Monolith → Microservices)',
            duration: '24-28 weeks',
            effort_hours: 960,
            cost_estimate: '$600K - $800K',
            teams_required: ['Backend', 'Frontend', 'Architects'],
            tasks: [
              '✓ Domain-Driven Design workshops',
              '✓ Identify service boundaries (Auth, Payment, Inventory, Shipping)',
              '✓ Extract Services (one per sprint)',
              '✓ Implement API Gateway (Kong/AWS Gateway)',
              '✓ Set up service discovery (Consul/K8s DNS)',
              '✓ Implement distributed tracing (Jaeger)',
              '✓ Event-driven architecture (Kafka)'
            ],
            acceptance_criteria: [
              'Minimum 5 independent services',
              'Each service can deploy independently',
              'Inter-service communication via APIs / Events',
              'Can scale each service independently'
            ]
          },

          {
            phase: 4,
            name: 'Optimization & Operations (Optional, 8-12 weeks)',
            duration: '8-12 weeks',
            effort_hours: 320,
            cost_estimate: '$150K - $200K',
            teams_required: ['DevOps', 'SRE', 'Security'],
            tasks: [
              '✓ Implement caching layer (Redis)',
              '✓ Setup auto-scaling (HPA)',
              '✓ Security hardening (network policies, RBAC)',
              '✓ Cost optimization (reserved instances, spot pricing)',
              '✓ Disaster recovery procedures'
            ]
          }
        ],

        total_duration_months: 12,
        total_cost_estimate: '$1.35M - $1.8M',
        expected_roi: {
          monthly_savings: '$95K', // Reduced licensing, better resource utilization
          payback_period_months: 14,
          three_year_savings: '$3.4M',
          non_financial: [
            'Faster time-to-market (2 weeks → 3 days)',
            'Improved uptime (90% → 99.95%)',
            'Developer satisfaction (modern stack)',
            'Easier hiring (popular tech stack)'
          ]
        }
      },

      recommendations_by_role: {
        CTO: [
          'Approve Phase 1 (Containerization) - lowest risk, immediate visibility improvements',
          'Budget $1.5M for 12-month transformation',
          'Allocate 15-20 FTE (40% from existing team, 60% contractors)',
          'Set KPIs: Deployment frequency (2/week → daily), Change failure rate (20% → 5%)'
        ],
        ENTERPRISE_ARCHITECT: [
          'Design target state: Event-driven microservices on EKS',
          'Identify service boundaries using DDD (Domain-Driven Design)',
          'Plan fallback strategies for each phase',
          'Create technology radar: Phase out Oracle, Java 8; Phase in Kubernetes, Kafka'
        ],
        DBA: [
          'Prepare Aurora migration plan in detail',
          'Set up shadow testing for data consistency',
          'Plan zero-downtime switchover',
          'Post-migration: Implement automated backups, Point-in-Time Recovery'
        ],
        DEVOPS: [
          'Build K8s cluster infrastructure',
          'Automate CI/CD with GitLab/Jenkins',
          'Set up monitoring/logging (Prometheus, ELK, Jaeger)',
          'Create disaster recovery procedures'
        ],
        DEVELOPERS: [
          'Upgrade to Java 17 (Phase 1)',
          'Implement clean code patterns (SOLID)',
          'Write tests (>80% coverage)',
          'Learn Kubernetes/Docker/Kafka ecosystem'
        ]
      },

      risk_mitigation: [
        {
          risk: 'Data loss during Oracle→Aurora migration',
          mitigation: 'Parallel run Oracle + Aurora in shadow mode for 2 weeks before cutover'
        },
        {
          risk: 'Service dependency chaos during decomposition',
          mitigation: 'Implement circuit breakers (Hystrix/Resilience4j), service mesh (Istio)'
        },
        {
          risk: 'Budget overrun',
          mitigation: 'Phase-gate approach: approve each phase after previous one succeeds'
        },
        {
          risk: 'Team resistance to change',
          mitigation: 'Training program + early wins (Phase 1 = visible improvements)'
        }
      ],

      success_metrics: {
        before: {
          deployment_frequency: 'Every 3-4 weeks',
          change_failure_rate: '18%',
          mean_time_recovery: '4 hours',
          uptime: '99.0%',
          p95_latency: '850ms',
          tech_debt: '82/100'
        },
        target_6_months: {
          deployment_frequency: '2x per week',
          change_failure_rate: '8%',
          mean_time_recovery: '15 minutes',
          uptime: '99.5%',
          p95_latency: '180ms',
          tech_debt: '40/100'
        },
        target_12_months: {
          deployment_frequency: 'Daily (10x)',
          change_failure_rate: '5%',
          mean_time_recovery: '5 minutes',
          uptime: '99.95%',
          p95_latency: '85ms',
          tech_debt: '20/100'
        }
      }
    };

    console.log(`🤖 AI Analysis Complete (Confidence: ${(analysis.confidence * 100).toFixed(0)}%)`);
    console.log();
    console.log('📋 Executive Summary:');
    console.log(analysis.executive_summary);
    console.log();

    console.log('🗺️  Migration Roadmap:');
    console.log(`   Duration: ${analysis.migration_roadmap.total_duration_months} months`);
    console.log(`   Cost: ${analysis.migration_roadmap.total_cost_estimate}`);
    console.log(`   Expected ROI: ${analysis.migration_roadmap.expected_roi.payback_period_months} months payback`);
    console.log();

    analysis.migration_roadmap.phases.forEach(phase => {
      console.log(`   Phase ${phase.phase}: ${phase.name} (${phase.duration})`);
      console.log(`     • Effort: ${phase.effort_hours} hours`);
      console.log(`     • Cost: ${phase.cost_estimate}`);
      console.log(`     • Teams: ${phase.teams_required.join(', ')}`);
    });
    console.log();

    console.log('📊 Projected Success Metrics:');
    console.log('   At 12 months:');
    const target = analysis.success_metrics.target_12_months;
    Object.entries(target).forEach(([metric, value]) => {
      console.log(`     • ${metric}: ${value}`);
    });

    return analysis;
  }

  // Generar reporte consolidado
  async runCompleteAnalysis() {
    console.log('\n' + '█'.repeat(80));
    console.log('█' + ' '.repeat(78) + '█');
    console.log('█' + '  UNIFIED ANALYSIS ORCHESTRATOR v2.0 - TEST EXECUTION'.padEnd(79) + '█');
    console.log('█' + ' '.repeat(78) + '█');
    console.log('█'.repeat(80) + '\n');

    try {
      const stage1 = this.stage1_Discovery(SAMPLE_RAW_DATA);
      const stage2 = this.stage2_AdvancedAnalysis(stage1);
      const stage3 = this.stage3_AIEnrichment(stage1, stage2);

      const finalReport = {
        timestamp: this.timestamp,
        stages: { stage1, stage2, stage3 },
        conclusion: `
✅ ANALYSIS COMPLETE

Summary:
- Detected ${stage1.discovered_components.length} critical components
- Identified ${stage2.anti_patterns_detected.length} architecture anti-patterns
- Technical Debt Score: ${stage2.technical_debt.score}/100 (${stage2.technical_debt.level})
- AI recommended ${ stage3.migration_roadmap.total_cost_estimate} modernization
- Projected 12-month ROI: ${stage3.migration_roadmap.expected_roi.three_year_savings}

Next Steps:
1. Review migration roadmap with stakeholders
2. Approve Phase 1 (Containerization + CI/CD)
3. Allocate budget and team resources
4. Execute implementation
        `
      };

      console.log('\n' + '█'.repeat(80));
      console.log('█' + finalReport.conclusion.padEnd(79) + '█');
      console.log('█'.repeat(80) + '\n');

      return finalReport;

    } catch (error) {
      console.error('❌ Analysis failed:', error.message);
      throw error;
    }
  }
}

// Ejecutar test
const test = new TestUnifiedAnalysis();
test.runCompleteAnalysis().then(report => {
  console.log('\n✅ Test completed successfully!\n');
}).catch(error => {
  console.error('\n❌ Test failed:', error);
  process.exit(1);
});
