
const API_BASE = 'http://127.0.0.1:8000';

const MOCK_INVENTORY = `
HOSTNAME: srv-legacy-prod-01
OS: RHEL 5.11 (Tikanga)
DATABASE: Oracle Database 8i Release 8.1.7.0.0 - Production
DB_PROCESS: ora_pmon_PROD1
DB_PORT: 1521

APP_STACK:
- WebLogic Server 8.1 SP6
- Java(TM) 2 Runtime Environment, Standard Edition (build 1.4.2_19-b04)

ARTEFACTOS DETECTADOS:
- facturacion-central.ear
- reportes-ventas.war

CONEXIONES SQL DETECTADAS EN BYTECODE:
- SELECT * FROM TBL_FACTURAS WHERE ESTADO = 'PENDIENTE'
- CALL SP_LIQUIDACION_MENSUAL(?, ?, ?)
- INSERT INTO LOG_TRANSACCIONES (ID, MSG) VALUES (SEQ_LOG.NEXTVAL, ?)

DEPENDENCIAS:
- ojdbc14.jar (Oracle JDBC Driver)
- log4j-1.2.8.jar
`;

async function runTest() {
    console.log('🚀 Iniciando Escaneo de Prueba v5.2 (Real Squad Execution)...');
    
    try {
        // 0. Login para obtener JWT
        console.log('🔑 Autenticando...');
        const loginResp = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: 'admin',
                password: 'factory2026'
            })
        });
        if (!loginResp.ok) throw new Error(`Login failed! status: ${loginResp.status}`);
        const loginData = await loginResp.json();
        const token = loginData.access_token;
        const headers = { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        };

        // 1. Iniciar Análisis
        const startResp = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                raw_data: MOCK_INVENTORY,
                industry: 'banca',
                force_reanalyze: true
            })
        });
        
        if (!startResp.ok) throw new Error(`Analyze error! status: ${startResp.status}`);
        const startData = await startResp.json();
        const jobId = startData.job_id;
        console.log(`✅ Trabajo iniciado. JobID: ${jobId}`);
        
        // 2. Polling de Status
        let status = 'queued';
        let result = null;
        
        console.log('⏳ Esperando procesamiento de los 8 agentes (3 etapas)...');
        
        while (status === 'queued' || status === 'running') {
            const statusResp = await fetch(`${API_BASE}/status/${jobId}`, { headers });
            if (!statusResp.ok) throw new Error(`Status error! status: ${statusResp.status}`);
            const statusData = await statusResp.json();
            
            status = statusData.status;
            process.stdout.write(`\r[STATUS]: ${status} - ${statusData.message || ''}   `);
            
            if (status === 'completed') {
                result = statusData.ai_content;
                break;
            }
            if (status === 'failed') {
                throw new Error(statusData.error || 'Desconocido');
            }
            
            await new Promise(r => setTimeout(r, 4000));
        }
        
        console.log('\n\n' + '='.repeat(60));
        console.log('🏁 RESULTADOS DEL SQUAD DE MODERNIZACIÓN v5.2');
        console.log('='.repeat(60));
        
        console.log('\n🧠 [PM] RESUMEN EJECUTIVO (Síntesis):');
        console.log(`> ${result.pm?.executive_summary || 'N/A'}`);
        
        console.log('\n🎖 [PM] PRIORIDADES MAESTRO:');
        (result.pm?.master_priorities || []).forEach(p => {
            console.log(`- [SPRINT ${p.sprint}] ${p.task}: ${p.rationale}`);
        });

        console.log('\n🗄 [DBA] ESTRATEGIA DE BASE DE DATOS:');
        console.log(`- Motor Destino: ${result.database || 'N/A'}`); // Adjusted to match backend key
        
        console.log('\n💡 [DBA] OBJETOS CRÍTICOS (PL/SQL):');
        (result.dba_findings?.plsql_refactor_candidates || []).forEach(o => {
            console.log(`- ${o.name} (${o.complexity}): ${o.recommendation}`);
        });

        console.log('\n💰 [FINOPS] ROI ESTIMADO:');
        console.log(`- Ahorro Anual: ${result.business?.roi?.annual_saving || 'N/A'}`);
        console.log(`- Payback: ${result.business?.roi?.payback_months || 'N/A'} meses`);

        console.log('\n' + '='.repeat(60));
        console.log('✅ TEST EXITOSO');
        
    } catch (err) {
        console.error('\n❌ ERROR EN EL TEST:', err.message);
    }
}

runTest();
