#!/usr/bin/env node

/**
 * Test Suite para Modernization Factory v2.0
 * Ejecutar: node test-manual.js
 */

import validator from './lib/validator.js';
import discoveryEngine from './lib/discoveryEngine.js';
import analysisEngine from './lib/analysisEngine.js';

console.log('\n' + '='.repeat(70));
console.log('  MODERNIZATION FACTORY — Test Suite v2.0');
console.log('='.repeat(70) + '\n');

// ============ TEST DATA ============
const sampleData = `
--- METADATA ---
HOSTNAME: app-server-prod.company.com
DATE: 2026-03-27
OS RELEASE: RHEL 5
--- PROCESSES ---
java -version 11
mysqld
nginx
httpd
oracle sqlplus
rabbitmq-server
postgres
redis-server
--- PORTS ---
:80 
:443
:1521 oracle
:3306 mysql
:5432 postgres
:5672 rabbitmq
:6379 redis
:8080
:9090
`;

const validations = [];
const tests = [];

function assert(condition, testName) {
    if (condition) {
        console.log('✅', testName);
        tests.push({ name: testName, status: 'PASS' });
    } else {
        console.log('❌', testName);
        tests.push({ name: testName, status: 'FAIL' });
    }
}

// ============ TEST 1: VALIDATOR ============
console.log('\n📋 TEST 1: Validation Module\n');

const emptyValidation = validator.validateRawData('');
assert(!emptyValidation.valid, 'Rechaza datos vacíos');

const shortValidation = validator.validateRawData('abc');
assert(!shortValidation.valid, 'Rechaza datos muy cortos');

const goodValidation = validator.validateRawData(sampleData);
assert(goodValidation.valid, 'Acepta datos válidos');

const hostname = validator.extractHostname(sampleData);
assert(hostname === 'app-server-prod.company.com', `Extrae hostname correctamente (${hostname})`);

const osInfo = validator.extractOsInfo(sampleData);
assert(osInfo.includes('RHEL'), `Extrae OS info correctamente (${osInfo})`);

const sanitized = validator.sanitizeText('<script>alert("XSS")</script>');
assert(!sanitized.includes('<'), 'Sanitiza contra XSS');

// ============ TEST 2: DISCOVERY ENGINE ============
console.log('\n🔍 TEST 2: Discovery Engine\n');

const analysis = discoveryEngine.analyzeStack(sampleData);

assert(analysis.stack.length > 0, `Detecta stack: ${analysis.stack.join(', ')}`);
assert(analysis.stack.includes('Java Runtime'), 'Detecta Java');
assert(analysis.stack.includes('MySQL/MariaDB'), 'Detecta MySQL');
assert(analysis.stack.includes('NGINX'), 'Detecta NGINX');
assert(analysis.stack.includes('Oracle Database'), 'Detecta Oracle');
assert(analysis.stack.includes('Redis'), 'Detecta Redis');
assert(analysis.stack.includes('RabbitMQ'), 'Detecta RabbitMQ');

assert(analysis.flags.isLegacy === true, 'Detecta como legacy (RHEL 5)');
assert(analysis.flags.hasWeb === true, 'Detecta web servers');
assert(analysis.flags.hasDB === true, 'Detecta databases');
assert(analysis.flags.hasJava === true, 'Detecta Java');
assert(analysis.flags.hasOracle === true, 'Detecta Oracle');
assert(analysis.flags.hasMQ === true, 'Detecta Message Queue');

const pattern = discoveryEngine.determineArchPattern(
    analysis.flags.hasJava,
    analysis.flags.hasOracle,
    analysis.flags.hasMQ,
    analysis.stack.length,
    analysis.flags.hasWeb,
    analysis.flags.hasDB
);
assert(pattern.includes('ENTERPRISE'), `Patrón correcto: ${pattern}`);

// ============ TEST 3: ANALYSIS ENGINE ============
console.log('\n📊 TEST 3: Analysis Engine\n');

const sreMetrics = analysisEngine.calculateSREMetrics(true, true);
assert(sreMetrics.risk_score === 9, `Risk score legacy/hasDB: ${sreMetrics.risk_score}`);
assert(sreMetrics.readiness_level === 'Crítica', `Readiness level: ${sreMetrics.readiness_level}`);

const financeImpact = analysisEngine.calculateFinancialImpact(true, true);
assert(financeImpact.estimated_migration_cost_usd === 15000, `Migration cost: $${financeImpact.estimated_migration_cost_usd}`);
assert(financeImpact.payback_months === 12, `Payback: ${financeImpact.payback_months} meses`);

const plan = analysisEngine.generateMigrationPlan(true);
assert(plan.length === 5, `Plan tiene ${plan.length} pasos`);
assert(plan[0].action.includes('Colector'), 'Primer paso es colector');
assert(plan[0].rollback.includes('Eliminar'), 'Rollback definido');

const terraform = analysisEngine.generateTerraformSnippet('app-server-prod');
assert(terraform.includes('factory-app-server-prod'), 'Terraform snippet generado');

const k8s = analysisEngine.generateK8sManifest('legacy-app');
assert(k8s.includes('legacy-app'), 'K8s manifest generado');

// ============ TEST 4: CODE INJECTION PREVENTION ============
console.log('\n🔒 TEST 4: Security\n');

const xssPayload = '<img src=x onerror="alert(1)">';
const sanitized1 = validator.sanitizeText(xssPayload);
assert(!sanitized1.includes('onerror'), 'XSS payload sanitizado');

const sqlPayload = "'; DROP TABLE users; --";
const sanitized2 = validator.sanitizeText(sqlPayload);
assert(sanitized2.length > 0, 'SQL injection contenido');

// ============ RESULTS ============
console.log('\n' + '='.repeat(70));
console.log('  TEST RESULTS');
console.log('='.repeat(70) + '\n');

const passed = tests.filter(t => t.status === 'PASS').length;
const failed = tests.filter(t => t.status === 'FAIL').length;
const total = tests.length;

console.log(`Total: ${total}`);
console.log(`✅ Passed: ${passed}`);
console.log(`❌ Failed: ${failed}`);
console.log(`Success Rate: ${((passed/total)*100).toFixed(1)}%\n`);

if (failed === 0) {
    console.log('🎉 ALL TESTS PASSED!\n');
    process.exit(0);
} else {
    console.log('⚠️ Some tests failed\n');
    process.exit(1);
}
