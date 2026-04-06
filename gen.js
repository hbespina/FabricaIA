const fs = require('fs');
const html = String.raw`<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Modernization Factory | Architect V3</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
:root{--bg:#0a0e14;--glass:rgba(255,255,255,0.05);--bdr:rgba(255,255,255,0.1);--blue:#00d2ff;--purple:#9d50bb;--red:#ff416c;--yellow:#f9d423;--green:#00b09b;--t2:#a0a0a0;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:#fff;}
.app{display:flex;min-height:100vh;}
aside{width:250px;background:linear-gradient(180deg,#111827,#0a0e14);border-right:2px solid var(--purple);padding:1.5rem;display:flex;flex-direction:column;}
.logo{font-size:.95rem;font-weight:700;background:linear-gradient(135deg,#00d2ff,#9d50bb);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:1.5rem;}
.navli{list-style:none;padding:.7rem 1rem;border-radius:8px;cursor:pointer;color:var(--t2);transition:.3s;margin-bottom:.3rem;}
.navli:hover,.navli.on{background:var(--glass);color:#fff;border-left:3px solid var(--blue);}
.ver{margin-top:auto;font-size:.6rem;color:var(--t2);}
main{flex:1;padding:1.5rem;overflow-y:auto;}
.hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;}
.badge{background:rgba(0,210,255,.1);border:1px solid var(--blue);padding:.3rem .8rem;border-radius:20px;font-size:.7rem;color:var(--blue);}
.card{background:var(--glass);border:1px solid var(--bdr);border-radius:18px;padding:1.2rem;margin-bottom:1.2rem;}
.pt{border-top:3px solid var(--purple);}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem;margin-bottom:1.2rem;}
textarea{width:100%;height:120px;background:rgba(0,0,0,.4);border:1px solid var(--bdr);border-radius:10px;padding:.8rem;color:#fff;font-family:monospace;resize:vertical;font-size:.78rem;}
input[type=text],input[type=password],input[type=number]{background:rgba(0,0,0,.4);border:1px solid var(--bdr);border-radius:8px;padding:.55rem .8rem;color:#fff;font-size:.82rem;}
.btn{background:linear-gradient(135deg,#00d2ff,#3a7bd5);border:none;padding:.7rem 1.8rem;border-radius:8px;color:#fff;font-weight:700;cursor:pointer;font-size:.88rem;margin-top:.8rem;}
.btn:disabled{opacity:.5;cursor:default;}
.bsm{background:var(--purple);border:none;color:#fff;padding:.25rem .7rem;border-radius:5px;font-size:.68rem;cursor:pointer;}
.bsm:hover{background:var(--blue);}
.modetab{background:transparent;border:1px solid var(--bdr);color:var(--t2);padding:.4rem 1rem;border-radius:8px;font-size:.78rem;cursor:pointer;transition:.3s;}
.modetab.on{background:var(--purple);border-color:var(--purple);color:#fff;}
.expbtn{background:rgba(255,255,255,.08);border:1px solid var(--bdr);padding:.4rem 1rem;border-radius:8px;color:#fff;font-size:.78rem;cursor:pointer;}
.expbtn:hover{border-color:var(--blue);color:var(--blue);}
pre{background:#03050a;padding:.8rem;border-radius:8px;font-size:.68rem;font-family:monospace;overflow:auto;border:1px solid var(--bdr);max-height:190px;}
table{width:100%;border-collapse:collapse;font-size:.78rem;margin-top:.8rem;}
th{text-align:left;padding:.4rem;color:var(--t2);border-bottom:1px solid var(--bdr);}
td{padding:.4rem;border-bottom:1px solid rgba(255,255,255,.04);}
td code{background:rgba(0,0,0,.3);padding:.1rem .35rem;border-radius:3px;font-size:.68rem;}
.svc{display:flex;align-items:center;gap:.8rem;padding:.7rem;border-radius:10px;border:1px solid var(--bdr);background:rgba(0,0,0,.2);margin-top:.7rem;}
.page{display:none;}
.fi{border-radius:12px;padding:1rem;margin-bottom:.8rem;background:rgba(0,0,0,.2);}
.fi.fc{border-left:4px solid var(--red);}
.fi.fh{border-left:4px solid var(--yellow);}
.fi.fm{border-left:4px solid var(--blue);}
.fhd{display:flex;align-items:flex-start;gap:.6rem;margin-bottom:.6rem;}
.ftit{font-weight:700;font-size:.88rem;flex:1;}
.fev{font-size:.7rem;color:var(--t2);margin-top:.2rem;}
.fev code{background:rgba(0,0,0,.4);padding:.1rem .3rem;border-radius:3px;color:var(--blue);font-size:.68rem;}
.fbody{font-size:.78rem;color:var(--t2);margin-bottom:.4rem;}
.fimp{font-size:.75rem;color:var(--yellow);}
.fmod{font-size:.72rem;color:var(--green);margin-top:.3rem;}
.iref{display:none;margin-top:.8rem;border-top:1px solid var(--bdr);padding-top:.8rem;}
.sp2{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-top:.5rem;}
.fbdg{padding:.15rem .5rem;border-radius:5px;font-size:.62rem;font-weight:700;white-space:nowrap;}
.bc{background:rgba(255,65,108,.2);color:var(--red);border:1px solid var(--red);}
.bh{background:rgba(249,212,35,.15);color:var(--yellow);border:1px solid var(--yellow);}
.bm{background:rgba(0,210,255,.1);color:var(--blue);border:1px solid var(--blue);}
@media print{
  aside,.expbtn,.modetab,#analbtn,#sshbtn{display:none!important;}
  .page{display:block!important;}
  .card,.fi{break-inside:avoid;border:1px solid #ccc;background:white!important;color:black!important;}
  body{background:white;color:black;}
  pre{background:#f5f5f5!important;color:black!important;border:1px solid #ccc;}
}
</style>
</head>
<body>
<div class="app">
<aside>
  <div class="logo">MODERNIZATION FACTORY</div>
  <ul style="padding:0">
    <li class="navli on" id="n0" onclick="sw(0)">&#x1F9EC; Analisis de Codigo</li>
    <li class="navli" id="n1" onclick="sw(1)">&#x1F5A5; Infraestructura</li>
    <li class="navli" id="n2" onclick="sw(2)">&#x1F5FA; Plan de Migracion</li>
    <li class="navli" id="n3" onclick="sw(3)">&#x1F4E6; IaC Generator</li>
  </ul>
  <div class="ver">ENGINE V3 UNIVERSAL</div>
</aside>
<main>
  <div class="hdr">
    <div><h2 style="font-size:1.4rem">Modernization Engine <span style="color:var(--purple)">ARCHITECT V3</span></h2>
    <p style="color:var(--t2);font-size:.8rem">Analisis universal: Java, Node, Python, PHP, .NET, cualquier stack</p></div>
    <div style="display:flex;gap:.6rem;align-items:center">
      <button class="expbtn" onclick="exportReport()">&#x1F4C4; Exportar PDF</button>
      <div class="badge">Universal V3</div>
    </div>
  </div>

  <div class="card" style="margin-bottom:1.2rem">
    <div style="display:flex;gap:.5rem;margin-bottom:1rem;border-bottom:1px solid var(--bdr);padding-bottom:.8rem">
      <button class="modetab on" id="tab-ssh" onclick="setMode('ssh')">&#x1F50C; Conexion SSH Directa</button>
      <button class="modetab" id="tab-manual" onclick="setMode('manual')">&#x1F4CB; Pegar Datos Manual</button>
    </div>
    <div id="mode-ssh">
      <p style="color:var(--t2);font-size:.78rem;margin-bottom:.8rem">Conecta directamente al servidor — el backend ejecuta el colector via SSH</p>
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr 80px;gap:.6rem;align-items:end">
        <div>
          <label style="font-size:.7rem;color:var(--t2);display:block;margin-bottom:.3rem">Hostname / IP</label>
          <input id="ssh-host" type="text" placeholder="servidor.corp" style="width:100%">
        </div>
        <div>
          <label style="font-size:.7rem;color:var(--t2);display:block;margin-bottom:.3rem">Usuario</label>
          <input id="ssh-user" type="text" placeholder="root" style="width:100%">
        </div>
        <div>
          <label style="font-size:.7rem;color:var(--t2);display:block;margin-bottom:.3rem">Clave</label>
          <input id="ssh-pass" type="password" placeholder="..." style="width:100%">
        </div>
        <div>
          <label style="font-size:.7rem;color:var(--t2);display:block;margin-bottom:.3rem">Puerto</label>
          <input id="ssh-port" type="number" value="22" style="width:100%">
        </div>
      </div>
      <div style="margin-top:.8rem;display:flex;gap:.8rem;align-items:center;flex-wrap:wrap">
        <button class="btn" id="sshbtn" onclick="connectAndCollect()">&#x1F50D; Conectar y Analizar</button>
        <span id="ssh-status" style="font-size:.78rem;color:var(--t2)"></span>
      </div>
      <div id="ssh-warn" style="display:none;margin-top:.6rem;background:rgba(249,212,35,.07);border:1px solid var(--yellow);border-radius:8px;padding:.6rem;font-size:.75rem;color:var(--yellow)">
        Backend no disponible. Ejecuta <b>start-backend.bat</b> y recarga la pagina.
      </div>
    </div>
    <div id="mode-manual" style="display:none">
      <p style="color:var(--t2);font-size:.78rem;margin-bottom:.6rem">Pega la salida completa de collector.sh</p>
      <textarea id="raw" placeholder="--- START CLOUD MODERNIZATION INVENTORY ---"></textarea>
      <button class="btn" id="analbtn" onclick="run()">&#x1F50D; Analizar Datos</button>
    </div>
  </div>

  <div class="page" id="p0">
    <div class="card pt">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:.5rem;align-items:flex-start">
        <div><h3 style="font-size:1rem">Hallazgos de Codigo Detectados</h3>
          <p style="color:var(--t2);font-size:.72rem;margin-top:.2rem">Anti-patrones detectados automaticamente segun el stack</p></div>
        <div id="patbdg"></div>
      </div>
      <div id="summ" style="margin-top:.8rem"></div>
    </div>
    <div id="flist"></div>
    <div class="g2">
      <div class="card pt"><h3 style="font-size:.9rem">Stack Detectado</h3><div id="biz"></div></div>
      <div class="card pt"><h3 style="font-size:.9rem">Protocolos: Legacy -> Modern</h3><div id="proto"></div></div>
    </div>
    <div class="card pt"><h3 style="font-size:.9rem">Application Data Flow</h3><div class="mermaid" id="am"></div></div>
  </div>

  <div class="page" id="p1">
    <div class="g2">
      <div class="card" style="text-align:center">
        <h3 style="font-size:.9rem">Scores</h3>
        <div style="display:flex;justify-content:space-around;margin-top:.8rem">
          <div><div id="srisk" style="font-size:1.8rem;font-weight:700;color:var(--red)">-</div><div style="font-size:.6rem;color:var(--t2)">RIESGO</div></div>
          <div><div id="scve" style="font-size:1.8rem;font-weight:700;color:#00ffca">-</div><div style="font-size:.6rem;color:var(--t2)">CVE</div></div>
          <div><div id="sread" style="font-size:1.8rem;font-weight:700;color:var(--green)">-</div><div style="font-size:.6rem;color:var(--t2)">READINESS</div></div>
        </div>
      </div>
      <div class="card"><h3 style="font-size:.9rem">Servidor</h3><div id="ssum" style="margin-top:.8rem;font-size:.82rem"></div></div>
    </div>
    <div class="card"><h3 style="font-size:.9rem">Stack Detectado</h3><div id="inv"></div></div>
    <div class="g2">
      <div class="card"><h3 style="font-size:.9rem">Cloud Target</h3><div class="mermaid" id="im"></div></div>
      <div class="card"><h3 style="font-size:.9rem">SRE Steps</h3><ul id="sre" style="list-style:none;font-size:.82rem;margin-top:.8rem"></ul></div>
    </div>
    <div class="card"><h3 style="font-size:.9rem">TCO &amp; ROI</h3>
      <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:.8rem">
        <div><div style="font-size:.7rem;color:var(--t2)">OPEX/mes</div><div id="fop" style="font-size:1.2rem;font-weight:700;color:var(--blue)">-</div></div>
        <div><div style="font-size:.7rem;color:var(--t2)">Migracion</div><div id="fmi" style="font-size:1.2rem;font-weight:700;color:var(--yellow)">-</div></div>
        <div><div style="font-size:.7rem;color:var(--t2)">Payback</div><div id="fpa" style="font-size:1.2rem;font-weight:700;color:var(--green)">-</div></div>
        <div><div style="font-size:.7rem;color:var(--t2)">Costo inaccion</div><div id="fin" style="font-size:1.2rem;font-weight:700;color:var(--red)">-</div></div>
      </div>
    </div>
  </div>

  <div class="page" id="p2">
    <div class="card pt"><h3 style="font-size:.9rem">Plan de Migracion por Sprints</h3><div id="plan" style="margin-top:1rem"></div></div>
  </div>

  <div class="page" id="p3">
    <div class="g2">
      <div class="card"><h3 style="font-size:.9rem">Terraform</h3><pre id="tf"></pre></div>
      <div class="card"><h3 style="font-size:.9rem">Kubernetes</h3><pre id="k8s"></pre></div>
    </div>
    <div class="card"><h3 style="font-size:.9rem">Dockerfile</h3><pre id="dock"></pre></div>
  </div>
</main>
</div>

<script>
// NAV
function sw(i){
  for(var j=0;j<4;j++){
    document.getElementById('p'+j).style.display='none';
    document.getElementById('n'+j).classList.remove('on');
  }
  document.getElementById('p'+i).style.display='block';
  document.getElementById('n'+i).classList.add('on');
}

function exportReport(){
  var ids=['p0','p1','p2','p3'], prev=[];
  ids.forEach(function(id){var el=document.getElementById(id);prev.push(el.style.display);el.style.display='block';});
  window.print();
  setTimeout(function(){ids.forEach(function(id,i){document.getElementById(id).style.display=prev[i];});},500);
}

function setMode(m){
  document.getElementById('mode-ssh').style.display=m==='ssh'?'block':'none';
  document.getElementById('mode-manual').style.display=m==='manual'?'block':'none';
  document.getElementById('tab-ssh').classList.toggle('on',m==='ssh');
  document.getElementById('tab-manual').classList.toggle('on',m==='manual');
}

async function connectAndCollect(){
  var host=document.getElementById('ssh-host').value.trim();
  var user=document.getElementById('ssh-user').value.trim();
  var pass=document.getElementById('ssh-pass').value;
  var port=parseInt(document.getElementById('ssh-port').value)||22;
  var st=document.getElementById('ssh-status');
  var btn=document.getElementById('sshbtn');
  var warn=document.getElementById('ssh-warn');
  if(!host||!user){alert('Ingresa hostname y usuario.');return;}
  btn.disabled=true;btn.innerText='Conectando...';
  st.style.color='var(--blue)';st.innerText='Conectando a '+host+'...';
  warn.style.display='none';
  try{
    var resp=await fetch('http://localhost:5055/collect',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({hostname:host,username:user,password:pass,port:port})});
    if(!resp.ok){var err=await resp.json();st.style.color='var(--red)';st.innerText='Error: '+(err.error||resp.statusText);return;}
    var data=await resp.json();
    st.style.color='var(--green)';
    st.innerText='OK — '+data.output.split('\\n').length+' lineas recibidas. Analizando...';
    document.getElementById('raw').value=data.output;
    run();
  }catch(e){
    warn.style.display='block';
    st.style.color='var(--red)';st.innerText='No se pudo conectar al backend.';
  }finally{btn.disabled=false;btn.innerText='Conectar y Analizar';}
}

// UNIVERSAL SIGNATURES
var SIGS=[
  {id:'jdk14',cat:'Runtime',sev:'CRITICO',
   title:'Java 1.4 / 1.5 — EOL sin parche',
   detect:function(r){return /jdk1\.[45]/i.test(r);},
   evidence:function(r){var m=r.match(/jdk(1\.[45][^\s/]*)/i);return m?'JDK '+m[1]:'jdk1.4 detectado';},
   anti:'Sin generics ni try-with-resources. SQL concatenado = SQL Injection. Connection leaks.',
   impact:'Toda CVE en la JVM sin parche. Imposible usar librerias modernas.',
   modern:'Amazon Corretto 17 + Spring Boot 3',rk:'jdk'},
  {id:'jdk6',cat:'Runtime',sev:'CRITICO',
   title:'Java 6 / 7 — EOL',
   detect:function(r){return /jdk1\.[67]/i.test(r)||/java version "1\.[67]/i.test(r);},
   evidence:function(r){var m=r.match(/jdk(1\.[67][^\s/]*)/i)||r.match(/java version "(1\.[67][^"]*)/i);return m?'Java '+m[1]:'java 1.6/1.7';},
   anti:'EOL sin patches. Sin lambdas. Sin modulos.',
   impact:'Vulnerabilidades conocidas sin parche. Dependencias modernas incompatibles.',
   modern:'Amazon Corretto 17 LTS',rk:'jdk'},
  {id:'jdk8',cat:'Runtime',sev:'ALTO',
   title:'Java 8 — Solo mantenimiento de seguridad',
   detect:function(r){return /jdk1\.8/i.test(r)||/java version "1\.8/i.test(r);},
   evidence:function(r){return 'Java 8 detectado';},
   anti:'Solo recibe parches de seguridad. Sin Records, sin Virtual Threads.',
   impact:'Deuda tecnica. Frameworks modernos requieren Java 11+.',
   modern:'Amazon Corretto 21 LTS (Virtual Threads)',rk:'jdk'},
  {id:'tomcat45',cat:'AppServer',sev:'CRITICO',
   title:'Tomcat 4.x / 5.x — EOL',
   detect:function(r){return /tomcat[/-][45]\./i.test(r);},
   evidence:function(r){var m=r.match(/tomcat[/-]([45]\.[^\s,]+)/i);return m?'Tomcat '+m[1]:'Tomcat 4/5 detectado';},
   anti:'Servlet 2.3/2.4. Sin async. Sin HTTP/2.',
   impact:'Todas las apps en el mismo JVM caen juntas.',
   modern:'ECS Fargate + Corretto 17 (contenedor por app)',rk:'jsp'},
  {id:'jboss',cat:'AppServer',sev:'CRITICO',
   title:'JBoss / WildFly legacy',
   detect:function(r){return /jboss|wildfly/i.test(r);},
   evidence:function(r){var m=r.match(/jboss[^\s]*/i)||r.match(/wildfly[^\s]*/i);return m?m[0]:'JBoss/WildFly detectado';},
   anti:'App server monolitico pesado. EJBs. Despliegue lento.',
   impact:'Alta complejidad ops. Sin escalado horizontal simple.',
   modern:'Quarkus + ECS / App Runner',rk:'soap'},
  {id:'weblogic',cat:'AppServer',sev:'CRITICO',
   title:'Oracle WebLogic — Licencia cara',
   detect:function(r){return /weblogic/i.test(r);},
   evidence:function(r){return 'WebLogic detectado';},
   anti:'Licencia Oracle a miles de dolares/CPU.',
   impact:'Costo escala con el hardware. Imposible containerizar facilmente.',
   modern:'Spring Boot en ECS (sin licencia)',rk:'soap'},
  {id:'axis',cat:'Integration',sev:'CRITICO',
   title:'Apache Axis SOAP — Protocolo EOL',
   detect:function(r){return /axis[-_]\d/i.test(r)||(/axis/i.test(r)&&/axis\.jar|\/axis/i.test(r));},
   evidence:function(r){var m=r.match(/axis[-_][\d_.]+/gi)||['axis detectado'];return m.slice(0,3).join(', ');},
   anti:'SOAP sin OAuth2/JWT. Sin rate limiting. WSDL publicamente expuesto.',
   impact:'Cada integracion B2B requiere stubs Java. Imposible consumir desde mobile.',
   modern:'REST/OpenAPI 3.0 en API Gateway + Lambda',rk:'soap'},
  {id:'struts',cat:'Framework',sev:'ALTO',
   title:'Apache Struts 1.x — CVEs criticos (hack Equifax)',
   detect:function(r){return /struts[-_]1|struts\.jar/i.test(r);},
   evidence:function(r){var m=r.match(/struts[^\s,]*/gi);return m?m.slice(0,3).join(', '):'struts 1.x detectado';},
   anti:'CVE-2017-5638 y familia. EOL desde 2013. Exploits publicos.',
   impact:'Superficie de ataque conocida y documentada.',
   modern:'Spring Boot MVC + Thymeleaf',rk:'jsp'},
  {id:'dbcp',cat:'DataAccess',sev:'ALTO',
   title:'Commons DBCP 1.x — Connection pool sin administrar',
   detect:function(r){return /commons-dbcp/i.test(r);},
   evidence:function(r){var m=r.match(/commons-dbcp[-\d.]+/gi)||['commons-dbcp'];return m.slice(0,3).join(', ');},
   anti:'maxWait=-1 bloquea hilos indefinidamente. Credenciales en XML en texto plano.',
   impact:'Connection leak bajo carga. Servidor sin hilos disponibles.',
   modern:'HikariCP + RDS Proxy + Secrets Manager',rk:'dbcp'},
  {id:'log4j1',cat:'Security',sev:'ALTO',
   title:'Log4j 1.x — CVE critica / RCE',
   detect:function(r){return /log4j-1|log4j\.jar/i.test(r);},
   evidence:function(r){var m=r.match(/log4j[^\s]*/gi);return m?m.slice(0,3).join(', '):'log4j 1.x detectado';},
   anti:'EOL. RCE via JNDI en configuraciones especificas.',
   impact:'Remote Code Execution si el servicio es accesible desde red.',
   modern:'SLF4J + Logback o Log4j 2.x',rk:null},
  {id:'python2',cat:'Runtime',sev:'CRITICO',
   title:'Python 2.x — EOL enero 2020',
   detect:function(r){return /Python 2\.\d/i.test(r);},
   evidence:function(r){var m=r.match(/Python (2\.\d[^\s]*)/i);return m?'Python '+m[1]:'Python 2.x';},
   anti:'Sin parches de seguridad. Sin f-strings. Unicode fragil.',
   impact:'Toda CVE en CPython 2.x sin parche. pip ya no soporta Python 2.',
   modern:'Python 3.12 + FastAPI en Lambda o ECS',rk:null},
  {id:'php5',cat:'Runtime',sev:'CRITICO',
   title:'PHP 5.x / 7.0-7.1 — EOL con CVEs',
   detect:function(r){return /PHP [57]\.[01]\./i.test(r)||/php-5/i.test(r);},
   evidence:function(r){var m=r.match(/PHP ([57]\.\d\.[^\s]*)/i);return m?'PHP '+m[1]:'PHP EOL detectado';},
   anti:'EOL. mysql_ functions deprecadas = SQL Injection. Sin tipos estrictos.',
   impact:'Multiples CVEs sin parche.',
   modern:'PHP 8.3 + Laravel 11',rk:null},
  {id:'dotnet-fw',cat:'Runtime',sev:'ALTO',
   title:'.NET Framework / Mono — Solo Windows',
   detect:function(r){return /mono [\d]|\.net framework|\.csproj/i.test(r);},
   evidence:function(r){var m=r.match(/mono [\d.]+/i)||r.match(/\.net framework [\d.]+/i);return m?m[0]:'.NET Framework detectado';},
   anti:'Solo corre en Windows. Sin rendimiento de .NET 8.',
   impact:'No se puede containerizar en Linux. Costo de licencias Windows.',
   modern:'.NET 8 LTS (cross-platform, Linux containers)',rk:null},
  {id:'oracle-db',cat:'Database',sev:'CRITICO',
   title:'Oracle Database — Licencia Enterprise cara',
   detect:function(r){return /tnslsnr|ora_/i.test(r);},
   evidence:function(r){return 'tnslsnr / ora_ detectado (Oracle Listener)';},
   anti:'$47,500/CPU licencia Enterprise. JDBC propietario.',
   impact:'Vendor lock-in total. Costo escala con CPUs.',
   modern:'Amazon Aurora PostgreSQL (1/10 del costo)',rk:'dbcp'},
  {id:'mysql5',cat:'Database',sev:'MEDIO',
   title:'MySQL 5.x — EOL',
   detect:function(r){return /mysql.*5\.[0-7]|mysql-5/i.test(r);},
   evidence:function(r){var m=r.match(/mysql[\s-](5\.[^\s,]+)/i);return m?'MySQL '+m[1]:'MySQL 5.x';},
   anti:'EOL. Sin JSON nativo completo.',
   impact:'Sin parches de seguridad.',
   modern:'Amazon Aurora MySQL 8.0 Serverless v2',rk:null},
  {id:'activemq',cat:'Messaging',sev:'ALTO',
   title:'ActiveMQ Classic — Broker legacy',
   detect:function(r){return /activemq/i.test(r);},
   evidence:function(r){var m=r.match(/activemq[^\s]*/i);return m?m[0]:'ActiveMQ detectado';},
   anti:'JMS sincrono y fragil. Sin particionamiento. Sin replay.',
   impact:'Broker monolitico: si cae, todas las colas caen.',
   modern:'Amazon SQS + SNS o Amazon MQ',rk:null},
  {id:'cron-http',cat:'Batch',sev:'ALTO',
   title:'Batch via HTTP-Cron (wget/curl) — Anti-patron',
   detect:function(r){return /(wget|curl)/i.test(r)&&/cron/i.test(r);},
   evidence:function(r){var m=r.match(/wget[^\n]*/i)||r.match(/curl[^\n]*/i);return m?m[0].substring(0,80):'wget/curl en crontab';},
   anti:'Si el servidor web cae, el batch falla silenciosamente. Sin retry.',
   impact:'Procesos batch sin observabilidad ni alertas.',
   modern:'EventBridge Scheduler + Lambda',rk:'batch'},
  {id:'ldap',cat:'Security',sev:'MEDIO',
   title:'Autenticacion LDAP directa sin SSO moderno',
   detect:function(r){return /ldap/i.test(r);},
   evidence:function(r){var m=r.match(/ldap[^\s]*/i);return m?m[0]:'ldap detectado';},
   anti:'Sin MFA, sin JWT, sin RBAC moderno.',
   impact:'Si el LDAP falla, toda la app queda inaccesible.',
   modern:'Cognito + SAML 2.0 + MFA',rk:'ldap'},
  {id:'ant',cat:'DevOps',sev:'MEDIO',
   title:'Apache Ant — Build sin gestion de dependencias',
   detect:function(r){return /apache-ant|ant\.jar/i.test(r);},
   evidence:function(r){var m=r.match(/apache-ant-[\d.]+/gi);return m?m.join(', '):'Apache Ant detectado';},
   anti:'JARs copiados manualmente. Builds no reproducibles. Deploy via SCP.',
   impact:'Imposible CI/CD moderno.',
   modern:'Maven 3 / Gradle 8 + GitHub Actions',rk:'ant'},
  {id:'no-container',cat:'DevOps',sev:'MEDIO',
   title:'Sin containerizacion detectada',
   detect:function(r){return !/docker|podman|containerd/i.test(r);},
   evidence:function(r){return 'Docker/Podman no detectados';},
   anti:'Apps corriendo en OS host sin aislamiento.',
   impact:'Memory leak de una app puede derribar todo el servidor.',
   modern:'Docker + ECS Fargate',rk:null,lic:0,mgr:1},
  {id:'jsp',cat:'UX/UI',sev:'ALTO',
   title:'JSP Server-Side Render (Monolito)',
   detect:function(r){return /\.jsp/i.test(r);},
   evidence:function(r){var m=r.match(/\w+\.jsp/gi)||[];return m.slice(0,4).join(', ');},
   anti:'SQL + Java + HTML en el mismo archivo. No testeable.',
   impact:'Cada cambio de UI requiere redespliegue del WAR completo.',
   modern:'React/Next.js + API Gateway + Lambda',rk:'jsp',lic:0,mgr:4},
  {id:'odi',cat:'Integration',sev:'CRITICO',
   title:'Oracle Data Integrator (ODI) — ETL propietario on-premise',
   detect:function(r){return /\bodi\b|oracle.odi|odiparams|agentcmd|odiagent|ODI_HOME|oracle_di/i.test(r);},
   evidence:function(r){var m=r.match(/odi[^\s]*/i)||r.match(/ODI[^\s]*/);;return m?m[0]:'ODI detectado en procesos o instalacion';},
   anti:'ETL on-premise con repositorio Oracle. Pipelines acoplados a la BD de ODI. Sin paralelismo elastico. Deployment manual de escenarios.',
   impact:'Si el servidor ODI cae, todos los flujos de datos se detienen. Licencia Oracle incluida. Sin observabilidad moderna.',
   modern:'AWS Glue (Spark serverless) + Step Functions (orquestacion) + CloudWatch',rk:'odi',lic:25000,mgr:8},
  {id:'osb',cat:'Integration',sev:'CRITICO',
   title:'Oracle Service Bus (OSB) — ESB propietario sobre WebLogic',
   detect:function(r){return /servicebus|oracle.*osb|osb[_-]|sb.kernel|wli.jar|osb.console|SB_HOME|ALSBConfigMBean|oracle\.service\.bus/i.test(r);},
   evidence:function(r){var m=r.match(/(?:sb.kernel|osb[_-][^\s]*|oracle.*service.bus)[^\s]*/i);return m?m[0]:'OSB detectado en /opt o procesos WebLogic';},
   anti:'ESB on-premise sobre WebLogic. Routing y transformaciones en XML/XSLT propietario. WS-Security fragil. Escalado manual de servidores.',
   impact:'Punto unico de falla para todas las integraciones. Licencia Oracle WebLogic + OSB. Operacion 24x7 especializada requerida.',
   modern:'AWS API Gateway + Lambda (REST/ESB serverless) + Amazon MQ para mensajes',rk:'osb',lic:35000,mgr:10},
  {id:'nifi',cat:'Integration',sev:'MEDIO',
   title:'Apache NiFi on-premise — Data flow sin escalado elastico',
   detect:function(r){return /nifi[\.\-_]|apache.nifi|nifi\.sh|nifi\.properties|nifi-app|org\.apache\.nifi/i.test(r);},
   evidence:function(r){var m=r.match(/nifi[^\s]*/i)||r.match(/apache.nifi[^\s]*/i);return m?m[0]:'Apache NiFi detectado en procesos o /opt';},
   anti:'NiFi on-premise requiere JVM dedicada y administracion manual. Sin escalado automatico. Recursos fijos aunque no haya flujo de datos.',
   impact:'Capacidad maxima de procesamiento limitada al hardware del servidor. Sin HA automatica. Actualizaciones manuales y disruptivas.',
   modern:'Containerizar NiFi en EKS (escalado horizontal) o migrar a Amazon Managed MWAA / AWS Glue DataBrew',rk:'nifi',lic:0,mgr:6}
];

// REFACTORS
var RF={
  jdk:{t:'Java 1.4 a Corretto 17',
    o:'// Java 1.4 - SQL Injection + connection leak\\nStatement st = conn.createStatement();\\nResultSet rs = st.executeQuery(\\n  "SELECT * FROM t WHERE id=" + id); // INJECTION!\\n// conn nunca se cierra = LEAK',
    n:'// Java 17 - Seguro + try-with-resources\\ntry (var ps = conn.prepareStatement(\\n     "SELECT * FROM t WHERE id=?")) {\\n  ps.setObject(1, id);\\n  return ps.executeQuery();\\n} // cierre automatico garantizado',
    note:'try-with-resources (Java 7+) garantiza cierre. PreparedStatement elimina SQL Injection.'},
  soap:{t:'SOAP Axis a REST + OpenAPI 3.0',
    o:'<!-- WSDL Axis 1.x - sin auth, verboso -->\\n<wsdl:operation name="getCliente">\\n  <!-- Sin OAuth, sin versionado -->\\n  <wsdl:input message="tns:req"/>\\n</wsdl:operation>',
    n:'# openapi.yaml\\npaths:\\n  /clientes/{id}:\\n    get:\\n      security: [{BearerAuth: []}]\\n      responses: {"200": {content: {application/json: {}}}}\\n# Lambda: async(ev) => db.findById(ev.pathParameters.id)',
    note:'REST+OpenAPI consumible desde cualquier lenguaje. API Gateway agrega auth y rate limiting.'},
  batch:{t:'HTTP-Cron wget a EventBridge + Lambda',
    o:'# crontab - batch dispara HTTP al servidor web\\n0 12 * * * wget -O/tmp/out.html http://app/rep.jsp\\n# Si httpd cae: falla SIN alertas, SIN retry',
    n:'// EventBridge Scheduler - retry automatico\\nresource "aws_scheduler_schedule" "daily" {\\n  schedule_expression = "cron(0 12 * * ? *)"\\n  target { retry_policy { maximum_retry_attempts = 3 } }\\n}\\n// Cada ejecucion logeada en CloudWatch automaticamente',
    note:'EventBridge tiene retry automatico y dead-letter queue. CloudWatch Logs captura cada ejecucion.'},
  dbcp:{t:'DBCP 1.0 a RDS Proxy + Secrets Manager',
    o:'<!-- context.xml - credenciales en texto plano! -->\\n<Resource username="app" password="P@ss123"\\n  maxWait="-1"  <!-- bloquea indefinidamente -->\\n  factory="org.apache.commons.dbcp.BasicDataSourceFactory"/>',
    n:'// Credentials rotadas cada 30 dias automaticamente\\nconst {SecretString} = await sm.send(\\n  new GetSecretValueCommand({SecretId:"prod/db"}));\\nconst creds = JSON.parse(SecretString);\\n// RDS Proxy gestiona pool + failover Multi-AZ',
    note:'DBCP maxWait=-1 bloquea todos los hilos. Secrets Manager rota credenciales sin downtime.'},
  jsp:{t:'JSP 1.2 a React + API REST',
    o:'<%-- JSP legacy: SQL + Java + HTML mezclados --%>\\n<% String p = request.getParameter("pais");\\n   ResultSet rs = st.executeQuery(\\n     "SELECT * FROM rep WHERE pais="+p); // INJECTION! %>\\n<% while(rs.next()) { %><p><%= rs.getString("n") %></p><% } %>',
    n:'// React 18 - UI desacoplada\\nexport const Reportes = ({pais}) => {\\n  const {data} = useQuery({queryKey:["rep",pais],\\n    queryFn:()=>fetch("/api/v1/reportes?pais="+pais).then(r=>r.json())});\\n  return <DataTable rows={data?.items??[]}/>;\\n};',
    note:'React renderiza, API Gateway autentica, Lambda ejecuta. Cada capa testeable independientemente.'},
  ldap:{t:'LDAP directo a Cognito + SAML SSO',
    o:'// AuthFilter.java - LDAP sin TLS, sin MFA\\nDirContext ctx = new InitialDirContext(\\n  env("ldap://corp-ldap:389", user, pass));\\n// Sin JWT, sin RBAC, sin auditoria',
    n:'// Lambda Authorizer - Cognito JWT\\nconst payload = await verifier.verify(token);\\n// RBAC desde grupos Cognito (federados via SAML con AD)\\n// MFA obligatorio. Logs de auditoria en CloudTrail.',
    note:'Cognito federa con AD via SAML 2.0. Agrega MFA, JWT, RBAC y auditoria sin tocar el AD.'},
  ant:{t:'Apache Ant a Maven + GitHub Actions CI/CD',
    o:'<!-- build.xml Ant - JARs manuales, deploy por SCP -->\\n<javac classpath="lib/axis.jar:lib/dbcp.jar" source="1.4"/>\\n<exec executable="scp">\\n  <arg value="app.war"/>\\n  <arg value="root@server:/opt/"/>\\n</exec>',
    n:'<!-- pom.xml Maven - reproducible y versionado -->\\n<parent>spring-boot-starter-parent 3.2.0</parent>\\n\\n# GitHub Actions CI/CD\\nsteps:\\n  - run: mvn test   # Tests automaticos\\n  - run: mvn package # Build reproducible\\n  - uses: aws-actions/amazon-ecs-deploy-task-definition@v1',
    note:'Maven descarga dependencias del repo central. GitHub Actions ejecuta tests en cada commit antes de deployar.'},
  odi:{t:'Oracle ODI a AWS Glue + Step Functions',
    o:'-- ODI: Escenario ejecutado en agente on-premise\n-- Pipeline acoplado al repositorio Oracle\nAGENTCMD -PORT=20910 startscen CARGA_DWH 001\n-- Si el servidor cae: todos los jobs se detienen\n-- Sin retry automatico, sin alertas, sin logs centralizados\n-- Licencia Oracle por CPU del servidor ODI',
    n:'# AWS Glue Job (PySpark serverless)\nimport sys\nfrom awsglue.context import GlueContext\nglueContext = GlueContext(SparkContext.getOrCreate())\n\n# Leer desde fuente (JDBC, S3, DynamoDB)\ndf = glueContext.create_dynamic_frame.from_catalog(\n  database="staging", table_name="ventas")\n\n# Transformar\ndf_clean = df.filter(lambda x: x["monto"] > 0)\n\n# Escribir en Data Warehouse\nglueContext.write_dynamic_frame.from_options(df_clean,\n  connection_type="s3",\n  connection_options={"path": "s3://dw/ventas/"})\n\n# Step Functions orquesta el pipeline con retry automatico',
    note:'AWS Glue es serverless: no hay servidor ODI que mantener. Step Functions reemplaza el scheduler ODI con retry, timeouts y alarmas CloudWatch incluidos. Sin licencia Oracle.'},
  osb:{t:'Oracle Service Bus a API Gateway + Lambda',
    o:'-- OSB Pipeline: routing XML/XSLT propietario\n<pipeline>\n  <stage name="ValidarEntrada">\n    <condition>$body/ns:orden/ns:monto &gt; 0</condition>\n    <route>\n      <service ref="svc:BackendOracle"/>\n    </route>\n  </stage>\n</pipeline>\n-- Corre sobre WebLogic administrado manualmente\n-- Sin versionado de APIs. Sin JWT. Sin rate limiting.',
    n:'# API Gateway + Lambda: ESB cloud-native\nresource "aws_api_gateway_rest_api" "esb" {\n  name = "enterprise-bus"\n}\n\n# Lambda como proxy de integracion\nexport const handler = async (event) => {\n  const payload = JSON.parse(event.body);\n  if (!payload.orden?.monto || payload.orden.monto <= 0)\n    return {statusCode:400, body: "Monto invalido"};\n  const result = await backendService.procesar(payload);\n  return {statusCode:200, body: JSON.stringify(result)};\n};\n# API GW: OAuth2, rate limiting, logging automatico',
    note:'OSB requiere WebLogic + licencia Oracle + equipo especializado. API Gateway es serverless, escala automaticamente, incluye auth, rate limiting y logs sin configuracion adicional.'},
  nifi:{t:'Apache NiFi on-premise a NiFi en EKS / MWAA',
    o:'# NiFi on-premise (un solo servidor)\n# nifi.properties:\nnifi.web.http.port=8080\nnifi.cluster.is.node=false  # sin cluster!\nnifi.content.repository.directory.default=/data/nifi/content\n# Problemas:\n# - Si el servidor cae, todos los flujos se detienen\n# - Escalado manual: agregar RAM/CPU al servidor\n# - Backpressure sin alertas en CloudWatch\n# - Actualizacion requiere downtime',
    n:'# NiFi en EKS con autoescalado horizontal\napiVersion: apps/v1\nkind: StatefulSet\nmetadata:\n  name: nifi\nspec:\n  replicas: 3  # cluster HA\n  template:\n    spec:\n      containers:\n      - name: nifi\n        image: apache/nifi:latest\n        resources:\n          requests: {memory: 2Gi, cpu: 1}\n          limits: {memory: 4Gi, cpu: 2}\n---\n# Alternativa serverless: Amazon MWAA (Airflow)\n# o AWS Glue DataBrew para transformaciones visuales',
    note:'NiFi en EKS con StatefulSet permite cluster HA de 3+ nodos. MWAA (Managed Airflow) elimina la administracion del servidor. Glue DataBrew para ETL visual sin codigo.'}
};

// TECH MAP - universal detection con categorias
var TECHS=[
  // --- Runtime ---
  {cat:'Runtime',icon:'\u26A1',pat:/java\s|java\//i, n:'Java Runtime', a:'Amazon Corretto 17/21'},
  {cat:'Runtime',icon:'\u26A1',pat:/node\s*v\d|nodejs/i, n:'Node.js', a:'Node.js 20 LTS en Lambda/ECS'},
  {cat:'Runtime',icon:'\u26A1',pat:/Python\s*\d/i, n:'Python', a:'Python 3.12 en Lambda/ECS'},
  {cat:'Runtime',icon:'\u26A1',pat:/PHP\s*\d/i, n:'PHP', a:'PHP 8.3 + Laravel 11'},
  {cat:'Runtime',icon:'\u26A1',pat:/ruby|rails/i, n:'Ruby/Rails', a:'Ruby 3.3 en ECS Fargate'},
  {cat:'Runtime',icon:'\u26A1',pat:/dotnet|mono |aspnet|asp\.net/i, n:'.NET / Mono', a:'.NET 8 LTS en contenedor Linux'},
  {cat:'Runtime',icon:'\u26A1',pat:/go \d|golang/i, n:'Go (Golang)', a:'Mantener; containerizar en ECS'},
  // --- App Server ---
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/catalina|tomcat/i, n:'Apache Tomcat', a:'ECS Fargate + Corretto 17'},
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/jboss|wildfly/i, n:'JBoss / WildFly', a:'Quarkus + ECS Fargate'},
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/weblogic/i, n:'Oracle WebLogic', a:'Spring Boot + ECS (sin licencia)'},
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/websphere/i, n:'IBM WebSphere', a:'Open Liberty + ECS'},
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/glassfish/i, n:'GlassFish', a:'Payara + ECS o Spring Boot'},
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/unicorn|gunicorn|uwsgi/i, n:'WSGI Server (Python)', a:'uvicorn + FastAPI en Lambda'},
  {cat:'AppServer',icon:'\uD83D\uDDA5',pat:/pm2|forever\.js/i, n:'PM2 / Node process mgr', a:'ECS Fargate (sin PM2)'},
  // --- Web / Proxy ---
  {cat:'Web',icon:'\uD83C\uDF10',pat:/httpd|apache2/i, n:'Apache HTTPD', a:'ALB + CloudFront'},
  {cat:'Web',icon:'\uD83C\uDF10',pat:/nginx/i, n:'NGINX', a:'Mantener como Ingress en EKS'},
  {cat:'Web',icon:'\uD83C\uDF10',pat:/haproxy/i, n:'HAProxy', a:'AWS ALB (managed)'},
  {cat:'Web',icon:'\uD83C\uDF10',pat:/varnish/i, n:'Varnish Cache', a:'CloudFront + ElastiCache'},
  {cat:'Web',icon:'\uD83C\uDF10',pat:/squid/i, n:'Squid Proxy', a:'AWS PrivateLink + NAT Gateway'},
  {cat:'Web',icon:'\uD83C\uDF10',pat:/iis|w3wp/i, n:'IIS (Windows)', a:'ECS Windows Containers'},
  // --- Database ---
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/mysqld/i, n:'MySQL', a:'Amazon Aurora MySQL Serverless v2'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/postgres/i, n:'PostgreSQL', a:'Amazon Aurora PostgreSQL Serverless'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/tnslsnr|ora_\w/i, n:'Oracle Database', a:'Aurora PostgreSQL via AWS DMS'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/mariadbd|mariadb/i, n:'MariaDB', a:'Amazon Aurora MySQL'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/mongod/i, n:'MongoDB', a:'Amazon DocumentDB'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/cassandra/i, n:'Apache Cassandra', a:'Amazon Keyspaces (serverless)'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/couchdb/i, n:'CouchDB', a:'Amazon DynamoDB'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/influxdb/i, n:'InfluxDB (TimeSeries)', a:'Amazon Timestream'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/elasticsearch|opensearch/i, n:'Elasticsearch / OpenSearch', a:'Amazon OpenSearch Service'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/db2/i, n:'IBM DB2', a:'Aurora PostgreSQL via DMS'},
  {cat:'Database',icon:'\uD83D\uDDC4',pat:/sqlserver|mssql/i, n:'SQL Server', a:'Amazon RDS for SQL Server'},
  // --- Cache ---
  {cat:'Cache',icon:'\u26A1',pat:/redis-server|redis\s/i, n:'Redis', a:'Amazon ElastiCache for Redis'},
  {cat:'Cache',icon:'\u26A1',pat:/memcached/i, n:'Memcached', a:'Amazon ElastiCache for Memcached'},
  // --- Message Broker ---
  {cat:'Messaging',icon:'\uD83D\uDCE8',pat:/kafka/i, n:'Apache Kafka', a:'Amazon MSK (managed Kafka)'},
  {cat:'Messaging',icon:'\uD83D\uDCE8',pat:/rabbitmq/i, n:'RabbitMQ', a:'Amazon MQ for RabbitMQ'},
  {cat:'Messaging',icon:'\uD83D\uDCE8',pat:/activemq/i, n:'ActiveMQ', a:'Amazon MQ / SQS + SNS'},
  {cat:'Messaging',icon:'\uD83D\uDCE8',pat:/pulsar/i, n:'Apache Pulsar', a:'Amazon MSK / EventBridge'},
  {cat:'Messaging',icon:'\uD83D\uDCE8',pat:/nats/i, n:'NATS', a:'Amazon EventBridge Pipes'},
  {cat:'Messaging',icon:'\uD83D\uDCE8',pat:/sendmail|postfix|dovecot/i, n:'Mail Server (SMTP)', a:'Amazon SES'},
  // --- Integration / ETL ---
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/\bodi\b|odiagent|ODI_HOME/i, n:'Oracle ODI (ETL)', a:'AWS Glue + Step Functions'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/servicebus|sb\.kernel|SB_HOME|osb\.console/i, n:'Oracle Service Bus (OSB)', a:'API Gateway + Lambda + Amazon MQ'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/nifi[\._\-]|apache\.nifi|nifi\.sh/i, n:'Apache NiFi', a:'NiFi en EKS (HA) o Amazon MWAA'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/mulesoft|mule\.bat|mule\.sh/i, n:'MuleSoft ESB', a:'AWS API Gateway + EventBridge'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/tibco|tibrv/i, n:'TIBCO (ESB)', a:'Amazon EventBridge + Lambda'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/informatica/i, n:'Informatica PowerCenter', a:'AWS Glue DataBrew'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/pentaho/i, n:'Pentaho (ETL)', a:'AWS Glue + Step Functions'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/talend/i, n:'Talend', a:'AWS Glue (Spark serverless)'},
  {cat:'Integration',icon:'\uD83D\uDD17',pat:/camel/i, n:'Apache Camel', a:'AWS Step Functions + EventBridge'},
  // --- Container / Orchestration ---
  {cat:'Container',icon:'\uD83D\uDCE6',pat:/dockerd|docker\/|docker ps/i, n:'Docker', a:'Amazon ECS Fargate'},
  {cat:'Container',icon:'\uD83D\uDCE6',pat:/kubectl|kube-apiserver|kubelet/i, n:'Kubernetes', a:'Amazon EKS (managed)'},
  {cat:'Container',icon:'\uD83D\uDCE6',pat:/podman/i, n:'Podman', a:'ECS Fargate (OCI compatible)'},
  {cat:'Container',icon:'\uD83D\uDCE6',pat:/containerd/i, n:'containerd', a:'EKS con containerd runtime'},
  {cat:'Container',icon:'\uD83D\uDCE6',pat:/openshift/i, n:'OpenShift', a:'Amazon EKS + ECS Fargate'},
  // --- Security ---
  {cat:'Security',icon:'\uD83D\uDD12',pat:/vault/i, n:'HashiCorp Vault', a:'AWS Secrets Manager + KMS'},
  {cat:'Security',icon:'\uD83D\uDD12',pat:/keycloak/i, n:'Keycloak IAM', a:'Amazon Cognito + SAML'},
  {cat:'Security',icon:'\uD83D\uDD12',pat:/ldap|slapd/i, n:'LDAP / OpenLDAP', a:'Cognito + SAML federation'},
  {cat:'Security',icon:'\uD83D\uDD12',pat:/selinux/i, n:'SELinux', a:'AWS Security Groups + IAM'},
  {cat:'Security',icon:'\uD83D\uDD12',pat:/fail2ban|iptables/i, n:'Firewall (iptables/fail2ban)', a:'AWS WAF + Security Groups'},
  // --- DevOps / CI-CD ---
  {cat:'DevOps',icon:'\u2699',pat:/jenkins/i, n:'Jenkins CI', a:'AWS CodePipeline + CodeBuild'},
  {cat:'DevOps',icon:'\u2699',pat:/gitlab/i, n:'GitLab', a:'GitLab en EKS o GitHub Actions'},
  {cat:'DevOps',icon:'\u2699',pat:/sonarqube/i, n:'SonarQube', a:'CodeGuru Reviewer'},
  {cat:'DevOps',icon:'\u2699',pat:/nexus|artifactory/i, n:'Nexus / Artifactory', a:'AWS CodeArtifact'},
  {cat:'DevOps',icon:'\u2699',pat:/apache-ant|ant\.jar/i, n:'Apache Ant', a:'Maven 3 / Gradle + CodeBuild'},
  {cat:'DevOps',icon:'\u2699',pat:/ansible/i, n:'Ansible', a:'AWS Systems Manager (SSM)'},
  {cat:'DevOps',icon:'\u2699',pat:/terraform/i, n:'Terraform (IaC)', a:'Mantener o migrar a CDK'},
  {cat:'DevOps',icon:'\u2699',pat:/svn|subversion/i, n:'SVN (Version Control)', a:'AWS CodeCommit / GitHub'},
  // --- Monitoring ---
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/prometheus/i, n:'Prometheus', a:'Amazon Managed Prometheus (AMP)'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/grafana/i, n:'Grafana', a:'Amazon Managed Grafana (AMG)'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/nagios/i, n:'Nagios', a:'CloudWatch + AWS Health'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/zabbix/i, n:'Zabbix', a:'CloudWatch + EventBridge'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/datadog/i, n:'Datadog Agent', a:'Mantener (Datadog soporte AWS) o CloudWatch'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/splunk/i, n:'Splunk', a:'Amazon OpenSearch + CloudWatch Logs'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/kibana/i, n:'Kibana', a:'Amazon OpenSearch Dashboards'},
  {cat:'Monitoring',icon:'\uD83D\uDCCA',pat:/newrelic/i, n:'New Relic Agent', a:'Mantener o migrar a CloudWatch'},
];

function run(){
  var btn=document.getElementById('analbtn');
  try{btn.disabled=true;btn.innerText='Analizando...';analyze();sw(0);}
  catch(e){alert('Error: '+e.message);console.error(e);}
  finally{btn.disabled=false;btn.innerText='Analizar Datos';}
}

function analyze(){
  var raw=document.getElementById('raw').value.trim();
  if(!raw){alert('Pega los datos del colector o conecta via SSH.');return;}
  var rl=raw.toLowerCase();

  // METADATA
  var hn=raw.match(/HOSTNAME:\s*([^\n]+)/i);
  var host=hn?hn[1].trim():'Unknown';
  var osM=raw.match(/Red Hat[^\n]*/i)||raw.match(/Ubuntu[^\n]*/i)||raw.match(/Debian[^\n]*/i)||raw.match(/SUSE[^\n]*/i)||['Unix/Linux'];
  var osStr=osM[0];

  // DETECT TECH
  var det=[];
  TECHS.forEach(function(t){if(t.pat.test(raw))det.push(t);});

  // RUN SIGS
  var fi=[], cr=0, hi=0;
  var totalLicense=0, totalComplex=0;

  SIGS.forEach(function(s){
    if(s.detect(raw)){
      var e=s.evidence(raw);
      fi.push({id:s.id,t:s.title,cat:s.cat,sev:s.sev,e:e,a:s.anti,i:s.impact,mod:s.modern,rk:s.rk,cls:s.id});
      if(s.sev==='CRITICO')cr++;
      if(s.sev==='ALTO')hi++;
      totalLicense += (s.lic || 0);
      totalComplex += (s.mgr || 1);
    }
  });

  if(fi.length===0)fi.push({id:'none',t:'No se encontraron riesgos criticos',cat:'SRE',sev:'BAJO',e:'N/A',a:'Arquitectura madura o motor sin firmas',i:'N/A',mod:'Contactar equipo SRE para analisis manual',rk:null,lic:0,mgr:1});

  // ARCH PATTERN
  var hasJava=/java|tomcat|catalina/i.test(raw);
  var hasSoap=/axis|wsdl|soap/i.test(raw);
  var hasNode=/package\.json|node_modules/i.test(raw)&&/node/i.test(raw);
  var hasPython=/requirements\.txt|django|flask|fastapi/i.test(raw);
  var hasPhp=/\.php|composer\.json/i.test(raw);
  var pat=hasSoap&&hasJava?'SOA LEGACY (SOAP + Multi-Monolito)':
           hasJava?'JVM MONOLITO (Tomcat/JBoss)':
           hasNode?'NODE.JS (Express/API)':
           hasPython?'PYTHON (Django/Flask/FastAPI)':
           hasPhp?'PHP (LAMP Stack)':'MIXTO / SCRIPT-BASED';

  // PROTOCOLS
  var pr=[];
  if(hasSoap)pr.push(['SOAP/WSDL (Axis/CXF)','REST/OpenAPI 3.0 + API Gateway','Alto','Muy Alto']);
  if(/\.jsp/i.test(raw))pr.push(['JSP Server-Side Render','React/Next.js + API REST','Alto','Muy Alto']);
  if(/cron/i.test(raw)&&/(wget|curl)/i.test(raw))pr.push(['HTTP-Cron (wget/curl)','EventBridge + Lambda','Medio','Alto']);
  if(/dbcp|jdbc/i.test(raw))pr.push(['JDBC + DBCP','RDS Proxy + Aurora Serverless','Medio','Alto']);
  if(/ldap/i.test(raw))pr.push(['LDAP directo','Cognito + SAML/SSO + MFA','Bajo','Alto']);
  if(/activemq/i.test(raw))pr.push(['JMS / ActiveMQ','Amazon SQS + SNS','Medio','Alto']);
  if(/sendmail|postfix/i.test(raw))pr.push(['SMTP (sendmail)','Amazon SES','Bajo','Medio']);
  if(/\bodi\b|odiagent/i.test(raw))pr.push(['Oracle ODI (ETL on-premise)','AWS Glue + Step Functions','Alto','Muy Alto']);
  if(/servicebus|sb.kernel|SB_HOME/i.test(raw))pr.push(['Oracle Service Bus (OSB/ESB)','API Gateway + Lambda + Amazon MQ','Alto','Muy Alto']);
  if(/nifi[\.\-]|apache.nifi/i.test(raw))pr.push(['Apache NiFi on-premise','NiFi en EKS / Amazon MWAA','Medio','Alto']);
  if(pr.length===0)pr.push(['Stack actual','Cloud-native (ECS + Aurora + Lambda)','Medio','Alto']);

  // MIGRATION PLAN
  var sp0=['Inventario de dependencias y versiones EOL','Mapeo de APIs expuestas (SOAP, REST, scripts)','Identificar dependencias entre componentes'];
  var sp1=['Containerizar sin cambiar codigo (lift-and-shift)','ALB + NGINX como terminador TLS','Activar CloudWatch Logs para todas las apps'];
  var sp2=[];
  if(hasSoap)sp2.push('Migrar endpoints SOAP a REST (Strangler Fig)');
  if(/dbcp|jdbc/i.test(raw))sp2.push('Migrar a RDS Proxy + Secrets Manager');
  if(/cron/i.test(raw))sp2.push('Reemplazar cron jobs por EventBridge + Lambda');
  if(/ldap/i.test(raw))sp2.push('Implementar Cognito + SAML federation');
  if(/\bodi\b|odiagent/i.test(raw))sp2.push('Migrar pipelines ODI a AWS Glue + Step Functions');
  if(/servicebus|sb.kernel|SB_HOME/i.test(raw))sp2.push('Migrar OSB pipelines a API Gateway + Lambda (Strangler Fig)');
  if(/nifi[\.\-]|apache.nifi/i.test(raw))sp2.push('Containerizar NiFi en EKS o migrar a Amazon MWAA');
  if(sp2.length===0)sp2.push('Migrar protocolos legacy a cloud-native');
  var sp3=['Modernizar UI: separar presentacion de logica','CI/CD: GitHub Actions + ECS Blue/Green','Desconexion controlada del servidor legacy'];

  // RENDER
  var cr=fi.filter(function(f){return f.sev==='CRITICO';}).length;
  var hi=fi.filter(function(f){return f.sev==='ALTO';}).length;
  var cats=fi.reduce(function(acc,f){if(acc.indexOf(f.cat)<0)acc.push(f.cat);return acc;},[]);

  document.getElementById('patbdg').innerHTML='<span style="background:linear-gradient(135deg,#9d50bb,#6e48aa);padding:.35rem .9rem;border-radius:8px;font-weight:700;font-size:.73rem">'+pat+'</span>';
  document.getElementById('summ').innerHTML=
    '<div style="display:flex;gap:2rem;flex-wrap:wrap">'+
    '<div style="text-align:center"><div style="font-size:1.8rem;font-weight:700;color:var(--red)">'+cr+'</div><div style="font-size:.62rem;color:var(--t2)">CRITICOS</div></div>'+
    '<div style="text-align:center"><div style="font-size:1.8rem;font-weight:700;color:var(--yellow)">'+hi+'</div><div style="font-size:.62rem;color:var(--t2)">ALTOS</div></div>'+
    '<div style="text-align:center"><div style="font-size:1.8rem;font-weight:700;color:var(--blue)">'+fi.length+'</div><div style="font-size:.62rem;color:var(--t2)">HALLAZGOS</div></div>'+
    '<div style="text-align:center"><div style="font-size:1.8rem;font-weight:700;color:var(--green)">'+cats.length+'</div><div style="font-size:.62rem;color:var(--t2)">CATEGORIAS</div></div>'+
    '</div>';

  var fhtml='';
  fi.forEach(function(f){
    var bc=f.sev==='CRITICO'?'bc':f.sev==='ALTO'?'bh':'bm';
    fhtml+='<div class="fi '+f.cls+'">'+
      '<div class="fhd"><div style="flex:1"><div class="ftit">'+f.t+'</div>'+
      '<div class="fev">[<b>'+f.cat+'</b>] Evidencia: <code>'+f.e+'</code></div></div>'+
      '<span class="fbdg '+bc+'">'+f.sev+'</span></div>'+
      '<div class="fbody"><b>Anti-patron:</b> '+f.a+'</div>'+
      '<div class="fimp">Impacto: '+f.i+'</div>'+
      '<div class="fmod">Recomendacion: '+f.mod+'</div>';
    if(f.rk&&RF[f.rk])fhtml+='<button class="bsm" style="margin-top:.7rem" onclick="tog(\'ir'+f.id+'\',\''+f.rk+'\')">Ver codigo: '+RF[f.rk].t+'</button><div class="iref" id="ir'+f.id+'"></div>';
    fhtml+='</div>';
  });
  document.getElementById('flist').innerHTML=fhtml;

  // BIZ - grouped inventory (page 0)
  var bizCats={};
  det.forEach(function(d){
    var c=d.cat||'Otro';
    if(!bizCats[c])bizCats[c]=[];
    bizCats[c].push(d);
  });
  var catColors={Runtime:'#00d2ff',AppServer:'#9d50bb',Web:'#00b09b',Database:'#f9d423',Cache:'#ff9f43',Messaging:'#ff416c',Integration:'#a29bfe',Container:'#00cec9',Security:'#fd79a8',DevOps:'#fdcb6e',Monitoring:'#74b9ff',Otro:'#b2bec3'};
  var bhtml=Object.keys(bizCats).map(function(cat){
    var color=catColors[cat]||'#aaa';
    var items=bizCats[cat].map(function(d){
      return '<div style="display:flex;justify-content:space-between;align-items:center;padding:.45rem .6rem;border-bottom:1px solid rgba(255,255,255,.04);font-size:.78rem"><span>'+d.n+'</span><span style="color:var(--green);font-size:.68rem">'+d.a+'</span></div>';
    }).join('');
    return '<div style="margin-bottom:.8rem"><div style="font-size:.7rem;font-weight:700;color:'+color+';padding:.3rem 0;border-bottom:1px solid '+color+'40;margin-bottom:.3rem">'+cat.toUpperCase()+' ('+bizCats[cat].length+')</div>'+items+'</div>';
  }).join('');
  document.getElementById('biz').innerHTML=bhtml||'<p style="color:var(--t2);font-size:.78rem;margin-top:.8rem">Ejecutar collector con root para detectar el stack completo.</p>';

  // PROTOCOLS TABLE
  var ptH='<table><tr><th>Legacy</th><th>Moderno</th><th>Effort</th><th>Beneficio</th></tr>';
  pr.forEach(function(p){ptH+='<tr><td><code>'+p[0]+'</code></td><td><code style="color:var(--green)">'+p[1]+'</code></td><td>'+p[2]+'</td><td style="color:var(--green)">'+p[3]+'</td></tr>';});
  document.getElementById('proto').innerHTML=ptH+'</table>';

  var ag='graph LR\n  U((Usuario)) --> GW[API GW]\n  GW --> A[App]\n  A --> DB[(Aurora)]\n  A --> C[Cache]\n  A --> Q[SQS/EB]';

  // INFRA
  document.getElementById('srisk').innerText=cr>=3?9:cr>=1?7:5;
  document.getElementById('scve').innerText=cr>=3?'1200+':cr>=1?'500+':'50';
  document.getElementById('sread').innerText=cr>=2?'Critica':hi>=2?'Media':'Lista';
  document.getElementById('ssum').innerHTML='<p><b>Host:</b> '+host+'</p><p><b>OS:</b> '+osStr+'</p><p><b>Patron:</b> '+pat+'</p><p style="margin-top:.4rem"><b>Tecnologias:</b> '+det.map(function(d){return d.n;}).join(', ')+'</p>';
  // FINANCIAL CALCULATION
  // fop: opex mensual (soporte + infra básica)
  // fmi: inversión CapEx (consultoría/modernización)
  // fpa: payback (meses)
  // fin: ahorro anual (por license avoidance)
  var infraBase = 500; // VM costs
  var currentOpEx = (totalLicense / 12) + infraBase;
  var modernOpEx = (infraBase * 0.4); // Serverless is cheaper
  var monthlySaving = currentOpEx - modernOpEx;
  
  var capEx = (totalComplex * 3500) + (cr * 2000); // More difficulty = more cost
  var payback = monthlySaving > 0 ? Math.round(capEx / monthlySaving) : 24;
  var annualSaving = monthlySaving * 12;

  document.getElementById('fop').innerText='$' + Math.round(currentOpEx).toLocaleString();
  document.getElementById('fmi').innerText='$' + Math.round(capEx).toLocaleString();
  document.getElementById('fpa').innerText=payback + ' meses';
  document.getElementById('fin').innerText='$' + Math.round(annualSaving).toLocaleString();
  // INV - grouped inventory (page 1)
  var invCats={};
  det.forEach(function(d){
    var c=d.cat||'Otro';
    if(!invCats[c])invCats[c]=[];
    invCats[c].push(d);
  });
  var catColorsInv={Runtime:'#00d2ff',AppServer:'#9d50bb',Web:'#00b09b',Database:'#f9d423',Cache:'#ff9f43',Messaging:'#ff416c',Integration:'#a29bfe',Container:'#00cec9',Security:'#fd79a8',DevOps:'#fdcb6e',Monitoring:'#74b9ff',Otro:'#b2bec3'};
  var ih='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.8rem;margin-top:.5rem">';
  Object.keys(invCats).forEach(function(cat){
    var color=catColorsInv[cat]||'#aaa';
    var rows=invCats[cat].map(function(d){
      return '<div style="display:flex;justify-content:space-between;align-items:center;padding:.4rem 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:.75rem"><span style="color:#fff">'+d.n+'</span><span style="color:'+color+';font-size:.62rem;text-align:right;max-width:55%">'+d.a+'</span></div>';
    }).join('');
    ih+='<div style="background:rgba(0,0,0,.3);border:1px solid '+color+'30;border-radius:12px;padding:.8rem;border-top:3px solid '+color+'">';
    ih+='<div style="font-size:.7rem;font-weight:700;color:'+color+';margin-bottom:.5rem">'+cat.toUpperCase()+' <span style="color:var(--t2)">x'+invCats[cat].length+'</span></div>';
    ih+=rows+'</div>';
  });
  ih+='</div>';
  document.getElementById('inv').innerHTML=invCats&&Object.keys(invCats).length>0?ih:'<p style="color:var(--t2);font-size:.8rem">Stack no identificado. Ejecutar con permisos root.</p>';
  document.getElementById('sre').innerHTML=
    '<li style="margin-bottom:.7rem"><b>WAF + TLS delante de '+host+'</b><br><small style="color:var(--red)">Rollback: reapuntar DNS</small></li>'+
    '<li style="margin-bottom:.7rem"><b>Containerizar sin cambiar codigo</b><br><small style="color:var(--red)">Rollback: stop docker</small></li>'+
    '<li><b>Strangler Fig: API Gateway delante del stack</b><br><small style="color:var(--red)">Rollback: quitar reglas</small></li>';
  var ig='graph TD\n  U[Internet] --> ALB[AWS ALB+WAF]\n  ALB --> NG[NGINX]\n  NG --> A[Container: App]\n  A --> GW[API GW]\n  GW --> L[Lambda]\n  L --> DB[(Aurora)]';

  // PLAN
  document.getElementById('plan').innerHTML=
    spB('SPRINT 0 (Sem 1-2) - Discovery','var(--purple)',sp0)+
    spB('SPRINT 1 (Sem 3-6) - Containerizacion','var(--blue)',sp1)+
    spB('SPRINT 2 (Sem 7-12) - Migracion Protocolos','var(--green)',sp2)+
    spB('SPRINT 3 (Sem 13+) - Modernizacion Final','var(--yellow)',sp3);

  // IAC
  var sh=host.toLowerCase().replace(/[^a-z0-9]/g,'-');
  document.getElementById('tf').innerText='resource "aws_ecs_cluster" "factory" {\n  name = "factory-'+sh+'"\n}\nresource "aws_ecs_task_definition" "app" {\n  family = "'+sh+'-task"\n  container_definitions = jsonencode([{\n    name  = "app"\n    image = "'+sh+':latest"\n    portMappings = [{ containerPort = 8080 }]\n  }])\n}\nresource "aws_rds_cluster" "aurora" {\n  cluster_identifier = "'+sh+'-db"\n  engine = "aurora-mysql"\n  engine_mode = "serverless"\n}';
  document.getElementById('k8s').innerText='apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: '+sh+'\nspec:\n  replicas: 2\n  selector:\n    matchLabels: {app: '+sh+'}\n  template:\n    spec:\n      containers:\n      - name: app\n        image: '+sh+':latest\n        ports:\n        - containerPort: 8080\n        env:\n        - name: DB_URL\n          valueFrom:\n            secretKeyRef: {name: db-secret, key: url}';
  document.getElementById('dock').innerText='# Dockerfile universal\nFROM amazoncorretto:17-al2 AS build\nWORKDIR /app\nCOPY . .\nRUN mvn package -DskipTests\n\nFROM amazoncorretto:17-al2-jre\nCOPY --from=build /app/target/*.jar app.jar\nHEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1\nEXPOSE 8080\nENTRYPOINT ["java","-jar","app.jar"]';

  setTimeout(function(){
    try{var e=document.getElementById('am');e.removeAttribute('data-processed');e.innerHTML=ag;mermaid.init(undefined,e);}catch(ex){console.warn(ex);}
    try{var e2=document.getElementById('im');e2.removeAttribute('data-processed');e2.innerHTML=ig;mermaid.init(undefined,e2);}catch(ex){console.warn(ex);}
  },300);
}

function spB(title,color,items){
  return '<div style="margin-bottom:1.2rem"><div style="font-weight:700;color:'+color+';margin-bottom:.5rem">'+title+'</div>'+
    '<ul style="list-style:none;font-size:.8rem">'+items.map(function(i){return '<li style="padding:.35rem 0;border-bottom:1px solid var(--bdr)">'+i+'</li>';}).join('')+'</ul></div>';
}

function tog(elId,rk){
  var el=document.getElementById(elId);
  if(!el)return;
  if(el.style.display==='block'){el.style.display='none';return;}
  var r=RF[rk];
  if(!r){el.innerHTML='<p style="color:var(--t2);font-size:.78rem">Preview no disponible.</p>';el.style.display='block';return;}
  el.innerHTML='<div style="font-weight:700;color:var(--purple);font-size:.8rem;margin-bottom:.7rem">'+r.t+'</div>'+
    '<div class="sp2">'+
      '<div><div style="font-size:.62rem;color:var(--red);margin-bottom:.3rem;font-weight:700">LEGACY</div><pre style="max-height:160px">'+esc(r.o)+'</pre></div>'+
      '<div><div style="font-size:.62rem;color:var(--green);margin-bottom:.3rem;font-weight:700">MODERNO</div><pre style="max-height:160px">'+esc(r.n)+'</pre></div>'+
    '</div>'+
    '<div style="font-size:.73rem;color:var(--t2);margin-top:.7rem;border-top:1px solid var(--bdr);padding-top:.7rem">'+r.note+'</div>';
  el.style.display='block';
  el.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
</script>
</body>
</html>`;

fs.writeFileSync('modern-architect-v2.html', html, 'utf8');
console.log('HTML written:', fs.statSync('modern-architect-v2.html').size, 'bytes');

// Validate JS
var s = html.lastIndexOf('<script>');
var e = html.lastIndexOf('</script>');
var js = html.substring(s+8, e);
try { new Function(js); console.log('JS syntax: OK'); }
catch(err) { console.log('JS syntax ERROR:', err.message); }
