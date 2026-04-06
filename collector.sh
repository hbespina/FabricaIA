#!/bin/bash
# ==============================================================================
# Modernization Factory - Agent Collector V2.0 ENHANCED
# Detects: Infrastructure + Code + Integrations + Patterns
# Usage: chmod +x collector.sh && ./collector.sh
# Output: Generates inventory_HOSTNAME_TIMESTAMP.json + .txt
# Supports: RHEL, Solaris, AIX, Debian/Ubuntu
# ==============================================================================

# Generate output files
HOSTNAME_CLEAN=$(hostname | tr '[:upper:]' '[:lower:]' | tr -d '.')
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="inventory_${HOSTNAME_CLEAN}_${TIMESTAMP}.txt"

# Create output directory if needed
OUTPUT_DIR="./modernization_reports"
mkdir -p "$OUTPUT_DIR" 2>/dev/null
OUTPUT_FILE="$OUTPUT_DIR/$OUTPUT_FILE"

# === DISK SPACE VERIFICATION ===
MIN_DISK_MB=500  # Minimum 500MB required
CURRENT_DIR=$(pwd)

# Get available disk space (in MB) - Handle different df output formats
AVAILABLE_MB=$(df -m "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $(NF-2)}' | tr -d 'M%')
TOTAL_MB=$(df -m "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $2}' | tr -d 'M%')
USED_MB=$(df -m "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $3}' | tr -d 'M%')
USE_PERCENT=$(df "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $(NF-1)}' | tr -d '%')
# Ensure values are numeric
AVAILABLE_MB=${AVAILABLE_MB//[^0-9]/}
TOTAL_MB=${TOTAL_MB//[^0-9]/}
USED_MB=${USED_MB//[^0-9]/}
USE_PERCENT=${USE_PERCENT//[^0-9]/}

# Check disk space (ensure values are set)
if [ -z "$AVAILABLE_MB" ] || [ -z "$USE_PERCENT" ]; then
    AVAILABLE_MB="0"
    USE_PERCENT="0"
fi
if [ "$AVAILABLE_MB" -lt "$MIN_DISK_MB" ]; then
    echo "ERROR: Insufficient disk space!"
    echo "  Available: ${AVAILABLE_MB}MB (Required: ${MIN_DISK_MB}MB)"
    echo "  Usage: ${USE_PERCENT}% (Total: ${TOTAL_MB}MB, Used: ${USED_MB}MB)"
    echo "  Please free up at least $((MIN_DISK_MB - AVAILABLE_MB))MB before running collector."
    exit 1
fi

# Redirect all output to file AND stdout (tee)
# For sh compatibility: use tee without process substitution
exec > >(tee "$OUTPUT_FILE") 2>&1

echo "--- START CLOUD MODERNIZATION INVENTORY ---"
echo "REPORT_FILE: $OUTPUT_FILE"
echo "TIMESTAMP: $(date)"
echo "HOSTNAME: $(hostname)"
echo "COLLECTOR_VERSION: 2.0"
echo ""

echo "--- DISK SPACE STATUS ---"
echo "Available Disk Space: ${AVAILABLE_MB}MB"
echo "Total Disk Space: ${TOTAL_MB}MB"
echo "Used Space: ${USED_MB}MB"
echo "Usage Percentage: ${USE_PERCENT}%"
echo "Minimum Required: ${MIN_DISK_MB}MB"
if [ "$USE_PERCENT" -gt 85 ]; then
    echo "WARNING: Disk usage is high (${USE_PERCENT}%). Consider cleaning up old reports."
fi
echo ""

echo "--- OS RELEASE ---"
if [ -f /etc/redhat-release ]; then
    cat /etc/redhat-release
elif [ -f /etc/debian_version ]; then
    echo "Debian $(cat /etc/debian_version)"
else
    uname -a
fi

echo "--- PROCESSES & RUNTIMES ---"
ps -ef | grep -E "java|python|node|php|tomcat|websphere|jboss|nifi|kafka|airflow|mysql|postgres|oracle|mongodb" | grep -v grep

echo "--- LISTENING PORTS & SERVICES ---"
if command -v netstat >/dev/null 2>&1; then
    netstat -tulpn 2>/dev/null | grep LISTEN
elif command -v ss >/dev/null 2>&1; then
    ss -tlpn 2>/dev/null
else
    lsof -i -P -n 2>/dev/null | grep LISTEN
fi

echo "--- JAVA/APPLICATION STACK ---"
echo "JAVA_HOME: $JAVA_HOME"
java -version 2>&1
which javac >/dev/null && javac -version 2>&1 || echo "javac: not found"
echo "TOMCAT_HOME: $CATALINA_HOME"
echo "JBOSS_HOME: $JBOSS_HOME"

echo "--- NODE/PYTHON/PHP RUNTIME ---"
node --version 2>/dev/null || echo "Node: not installed"
python --version 2>/dev/null || python3 --version 2>/dev/null || echo "Python: not installed"
php --version 2>&1 | head -n 1

echo "--- MAVEN DEPENDENCIES (pom.xml) ---"
timeout 5 find /opt /home /var/www -maxdepth 4 -name "pom.xml" -type f 2>/dev/null | head -n 5 | while read pom; do
    echo "MAVEN_PROJECT: $pom"
    grep -E "<artifactId>|<version>" "$pom" 2>/dev/null | head -n 10
    grep -E "axis|struts|wicket|spring|hibernate|websphere|oracle|nifi|kafka|airflow" "$pom" 2>/dev/null | head -n 5
done

echo "--- PACKAGE DEPENDENCIES (npm/pip/gem) ---"
timeout 5 find /opt /home /var/www -maxdepth 4 -name "package.json" -type f 2>/dev/null | head -n 3 | while read pkg; do
    echo "NPM_PROJECT: $pkg"
    head -n 20 "$pkg" 2>/dev/null
done

timeout 5 find /opt /home /var/www -maxdepth 4 -name "requirements.txt" -type f 2>/dev/null | head -n 3 | while read req; do
    echo "PYTHON_DEPS: $req"
    cat "$req" 2>/dev/null | head -n 15
done

echo "--- WEBSERVICES & INTEGRATION (WSDL/Swagger/OpenAPI) ---"
echo ""
echo "WSDL_FILES_FOUND: $(timeout 5 find /opt /home /var/www -maxdepth 4 -name '*.wsdl' -type f 2>/dev/null | wc -l)"
timeout 5 find /opt /home /var/www -maxdepth 4 -name "*.wsdl" -type f 2>/dev/null | while read wsdl; do
    echo "  FILE: $wsdl"
    grep -E "<portType|<message|<service" "$wsdl" 2>/dev/null | head -n 5
done

echo ""
echo "API_SPECS_FOUND (Swagger/OpenAPI): $(timeout 5 find /opt /home /var/www -maxdepth 4 -type f \( -name 'swagger*.json' -o -name 'swagger*.yml' -o -name 'swagger*.yaml' -o -name 'openapi*.json' -o -name 'openapi*.yml' -o -name 'openapi*.yaml' -o -name 'api*.json' -o -name 'api*.yml' -o -name 'api*.yaml' \) 2>/dev/null | wc -l)"
timeout 5 find /opt /home /var/www -maxdepth 4 -type f \( -name 'swagger*.json' -o -name 'swagger*.yml' -o -name 'swagger*.yaml' -o -name 'openapi*.json' -o -name 'openapi*.yml' -o -name 'openapi*.yaml' -o -name 'api*.json' -o -name 'api*.yml' -o -name 'api*.yaml' \) 2>/dev/null | while read api; do
    echo "  FILE: $api"
    head -n 10 "$api" 2>/dev/null
done

echo "--- SOAP/REST API ENDPOINTS ---"
timeout 5 grep -r "soap:address\|@RestController\|@WebService\|<servlet-mapping>\|/nifi\|/api/flow" /opt /home /var/www 2>/dev/null | grep -v ".git" || echo "  (search timeout or no results)"

echo "--- CODE PATTERNS: Integration & Framework ---"
# HIGH PRIORITY SECTION: Use extended timeouts (15-20s) to collect comprehensive framework info
echo ""
echo "NIFI_INTEGRATION:"
NIFI_FILES=$(timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'nifi\|ProcessorRelationship\|AbstractProcessor' 2>/dev/null | wc -l || echo "0")
echo "  Count: $NIFI_FILES (NiFi config/processor files)"
timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'nifi' 2>/dev/null | head -n 5 | while read file; do echo "    - $file"; done
echo ""
echo "KAFKA_INTEGRATION:"
KAFKA_FILES=$(timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'kafka' 2>/dev/null | wc -l || echo "0")
echo "  Count: $KAFKA_FILES"
timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'kafka' 2>/dev/null | head -n 5 | while read file; do echo "    - $file"; done
echo ""
echo "AXIS_FRAMEWORK:"
AXIS_FILES=$(timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'axis' 2>/dev/null | wc -l || echo "0")
echo "  Count: $AXIS_FILES"
timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'axis' 2>/dev/null | while read file; do echo "    - $file"; done

echo ""
echo "STRUTS_FRAMEWORK:"
STRUTS_FILES=$(timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'struts' 2>/dev/null | wc -l || echo "0")
echo "  Count: $STRUTS_FILES"
timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'struts' 2>/dev/null | while read file; do echo "    - $file"; done

echo ""
echo "SPRING_FRAMEWORK:"
SPRING_FILES=$(timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'spring' 2>/dev/null | wc -l || echo "0")
echo "  Count: $SPRING_FILES"
timeout 15 find /opt /home /var/www -maxdepth 4 -name "*.xml" 2>/dev/null | timeout 8 xargs grep -l 'spring' 2>/dev/null | while read file; do echo "    - $file"; done

echo ""
echo "JSP_VIEWS:"
JSP_COUNT=$(timeout 10 find /opt /home /var/www -maxdepth 4 -name "*.jsp" 2>/dev/null | wc -l || echo "0")
echo "  Count: $JSP_COUNT"

echo "--- ORACLE INTEGRATION & PLSQL ---"
echo "ORACLE_INTEGRATIONS_FOUND: $(timeout 5 find /opt /home /var/www -maxdepth 4 \( -name '*odi*' -o -name '*osb*' -o -name '*weblogic*' \) 2>/dev/null | wc -l)"
timeout 5 find /opt /home /var/www -maxdepth 4 \( -name "*odi*" -o -name "*osb*" -o -name "*weblogic*" \) 2>/dev/null | while read file; do echo "  $file"; done
echo "ORACLE_LISTENERS: $(pgrep -f 'tnslsnr' 2>/dev/null | wc -l)"
echo "SQLPLUS_FOUND: $(which sqlplus 2>/dev/null || echo 'NOT_FOUND')"

echo "--- DATABASE CONNECTIONS & SCHEMAS ---"
echo "DATABASE_CONNECTIONS_FOUND: $(timeout 5 grep -r 'jdbc:\|mysql:\|postgresql:\|mongodb://' /opt /home /var/www 2>/dev/null | grep -v '.git' | wc -l)"
timeout 5 grep -r "jdbc:\|mysql:\|postgresql:\|mongodb://" /opt /home /var/www 2>/dev/null | grep -v ".git" || echo "  (search timeout or no results)"

echo "--- DATA INTEGRATION & WORKFLOW ENGINES (NiFi/Kafka/ETL) ---"
echo "NIFI_DETECTED: $(timeout 3 find /opt /opt/nifi* -maxdepth 2 -name 'nifi' -type d 2>/dev/null | wc -l || echo "0") instances"
echo "NIFI_HOME: $NIFI_HOME"
echo "NIFI_PROCESS: $(pgrep -f 'org.apache.nifi.NiFi' 2>/dev/null | wc -l) running"
timeout 5 find /opt /opt/nifi* -maxdepth 3 -name "nifi.properties" 2>/dev/null | while read nifi_props; do
    echo "NIFI_CONFIG: $nifi_props"
    grep -E "nifi.web.http.port|nifi.cluster.is.node|nifi.security.identity.provider" "$nifi_props" 2>/dev/null | head -n 5
done
echo "NIFI_FLOWS_FOUND: $(timeout 5 find /opt /opt/nifi* -maxdepth 4 \( -name 'flow.xml*' -o -name '*.nifi' \) 2>/dev/null | wc -l || echo "0")"
timeout 5 find /opt /opt/nifi* -maxdepth 4 -name "flow.xml*" 2>/dev/null | while read flow; do
    echo "  NIFI_FLOW: $flow ($(du -h "$flow" 2>/dev/null | cut -f1))"
done
echo ""
echo "KAFKA_DETECTED: $(timeout 3 find /opt -maxdepth 2 -name '*kafka*' -type d 2>/dev/null | wc -l || echo "0") instances"
echo "KAFKA_HOME: $KAFKA_HOME"
echo "KAFKA_PROCESS: $(pgrep -f 'kafka.Kafka' 2>/dev/null | wc -l) running"
timeout 5 find /opt -maxdepth 3 -name "server.properties" 2>/dev/null | grep -i kafka | while read kafkaconf; do
    echo "KAFKA_CONFIG: $kafkaconf"
    grep -E "broker.id|zookeeper.connect|listeners=" "$kafkaconf" 2>/dev/null | head -n 3
done
echo ""
echo "APACHE_AIRFLOW_DETECTED: $(timeout 3 find /opt /home -maxdepth 2 -type d -name '*airflow*' 2>/dev/null | wc -l || echo "0") instances"
echo "AIRFLOW_HOME: $AIRFLOW_HOME"
echo "AIRFLOW_PROCESS: $(pgrep -f 'airflow' 2>/dev/null | wc -l) running"
echo ""
echo "--- ACTIVE MQ / RABBITMQ / MESSAGE BUSES ---"
echo "RABBITMQ_RUNNING: $(pgrep -f 'beam.smp' >/dev/null && echo 'YES' || echo 'NO')"
echo "ACTIVEMQ_DETECTED: $(timeout 3 find /opt -maxdepth 2 -name '*activemq*' 2>/dev/null | wc -l || echo "0") instances"
timeout 5 find /opt -maxdepth 3 -name "activemq.xml" 2>/dev/null | while read amq; do
    echo "ACTIVEMQ_CONFIG: $amq"
    grep -E "<transportConnector|<networkConnector" "$amq" 2>/dev/null | head -n 3
done

echo "--- CRITICAL ENTERPRISE MIDDLEWARE ---"
echo "WEBSPHERE_DETECTED: $(timeout 3 find /opt/IBM -maxdepth 3 -name 'server.xml' 2>/dev/null | wc -l || echo "0") servers"
echo "JBOSS_DETECTED: $(pgrep -f 'jboss|wildfly' 2>/dev/null | wc -l) instances"
echo "INFORMATICA_DETECTED: $(timeout 3 find /opt -maxdepth 2 -type d -name '*infa*' 2>/dev/null | wc -l || echo "0") installations"

echo "--- CRITICAL CONFIG FILES (CONTENT SAMPLED) ---"
echo "CONFIG_FILES_FOUND: $(timeout 5 find /opt /etc -maxdepth 3 \( -name 'web.xml' -o -name 'server.xml' -o -name '*-config.xml' \) 2>/dev/null | wc -l)"
timeout 5 find /opt /etc -maxdepth 3 \( -name "web.xml" -o -name "server.xml" -o -name "*-config.xml" \) 2>/dev/null | while read cfg; do
    echo "FILE: $cfg"
    grep -E "<servlet|<connection-factory|<datasource|<resource-ref" "$cfg" 2>/dev/null | head -n 3
done

echo "--- LEGACY TECHNOLOGIES SCAN ---"
echo "LEGACY_JAR_COUNT: $(timeout 5 find /opt /home /var/www -maxdepth 4 -name "*.jar" 2>/dev/null | wc -l || echo "0")"
timeout 5 find /opt /home /var/www -maxdepth 4 -name "*.jar" 2>/dev/null | timeout 3 xargs -I {} sh -c 'basename {} | grep -E "commons-|axis|struts-|hibernate|spring-|wicket|nifi-|kafka-clients"' 2>/dev/null | head -n 20
echo ""
echo "NIFI_LIBRARIES:"
NIFI_LIBS_COUNT=$(timeout 5 find /opt /opt/nifi* -maxdepth 4 -name "nifi-*.jar" 2>/dev/null | wc -l || echo "0")
echo "  NIFI_LIBRARY_COUNT: $NIFI_LIBS_COUNT"
timeout 5 find /opt /opt/nifi* -maxdepth 4 -name "nifi-*.jar" 2>/dev/null | head -n 15 | while read jar; do
    echo "    - $(basename $jar)"
done
echo ""
echo "NIFI_PROCESSORS_INSTALLED:"
timeout 5 find /opt /opt/nifi*/lib -maxdepth 2 \( -name "*processor*.jar" -o -name "*nar" \) 2>/dev/null | head -n 10 | while read nar; do
    echo "    - $(basename $nar)"
done

echo "--- DOCKER CONTAINERS ---"
if command -v docker >/dev/null 2>&1; then
    docker ps --format "table {{.Image}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null
else
    echo "Docker: not installed"
fi

echo "--- CONTAINER RUNTIME (Kubernetes/Podman) ---"
kubectl version 2>/dev/null | head -n 1 || echo "kubectl: not found"
podman --version 2>/dev/null || echo "podman: not installed"

echo "--- LOGGING & MONITORING ---"
ls -lh /var/log/*.log 2>/dev/null | head -n 10
echo "SPLUNK_DETECTED: $(find /opt -name '*splunk*' 2>/dev/null | wc -l)"
echo "ELK_DETECTED: $(pgrep -f 'elasticsearch' 2>/dev/null | wc -l)"

echo "--- SECURITY & COMPLIANCE ---"
echo "SSL_CERTS: $(timeout 3 find /etc /opt -maxdepth 3 \( -name '*.pem' -o -name '*.crt' \) 2>/dev/null | wc -l || echo "0")"
echo "SUDO_RULES: $(sudo -l 2>/dev/null | wc -l) permissions"

echo "--- PERFORMANCE BASELINE ---"
echo "CPU_CORES: $(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc)"
echo "MEMORY_GB: $(free -g 2>/dev/null | awk '/^Mem:/ {print $2}' || grep MemTotal /proc/meminfo | awk '{print $2/1024/1024}' | cut -d. -f1)"
echo "DISK_USAGE: $(df -h / 2>/dev/null | tail -n 1)"

echo "--- SOURCE CODE ANALYSIS ---"
# Limit search depth to avoid hanging on deep directories (max 4 levels, 5s timeout)
JAVA_FILES=$(timeout 5 find /opt /home /var/www -maxdepth 4 -name '*.java' 2>/dev/null || true)
PYTHON_FILES=$(timeout 5 find /opt /home /var/www -maxdepth 4 -name '*.py' 2>/dev/null || true)
JS_FILES=$(timeout 5 find /opt /home /var/www -maxdepth 4 -name '*.js' 2>/dev/null || true)
PHP_FILES=$(timeout 5 find /opt /home /var/www -maxdepth 4 -name '*.php' 2>/dev/null || true)

echo "JAVA_SRC_FILES: $(echo "$JAVA_FILES" | grep -c '\.java' || echo 0)"
echo "PYTHON_SRC_FILES: $(echo "$PYTHON_FILES" | grep -c '\.py' || echo 0)"
echo "JS_SRC_FILES: $(echo "$JS_FILES" | grep -c '\.js' || echo 0)"
echo "PHP_SRC_FILES: $(echo "$PHP_FILES" | grep -c '\.php' || echo 0)"

echo "--- REFACTORING ANALYSIS (CODE QUALITY) ---"

echo "CODE_DUPLICATION_CHECK:"
echo "$JAVA_FILES" | head -n 20 | while read file; do
    [ -f "$file" ] && dupes=$(grep -o 'public.*{' "$file" 2>/dev/null | sort | uniq -d | wc -l) || dupes=0
    [ "${dupes:-0}" -gt 3 ] && echo "  DUPLICATION_RISK: $file ($dupes patterns)"
done

echo "CYCLOMATIC_COMPLEXITY (methods with high if/else count):"
echo "$JAVA_FILES" | head -n 20 | while read file; do
    if [ -f "$file" ]; then
        complexity=$(grep -c '\bif\b\|\belse\b\|\bswitch\b' "$file" 2>/dev/null || echo "0")
        [ "${complexity:-0}" -gt 15 ] && echo "  HIGH_COMPLEXITY: $file ($complexity branches)"
    fi
done

echo "DEAD_CODE_INDICATORS:"
echo "$JAVA_FILES" | head -n 20 | while read file; do
    if [ -f "$file" ]; then
        unused=$(grep -E 'import.*;\s*$' "$file" 2>/dev/null | grep -v 'java.lang' | wc -l || echo "0")
        [ "${unused:-0}" -gt 5 ] && echo "  UNUSED_IMPORTS: $file ($unused imports)"
    fi
done

echo "LONG_METHOD_DETECTION (>50 lines):"
echo "$JAVA_FILES" | head -n 15 | while read file; do
    [ -f "$file" ] && awk '/public.*\(/{start=NR} /^[[:space:]]*\}/{if(start && NR-start>50) print "  LONG_METHOD: '$file' (lines "start"-"NR")"}' "$file" 2>/dev/null
done

echo "LARGE_CLASS_DETECTION (>500 lines):"
timeout 5 find /opt /home /var/www -maxdepth 4 -name '*.java' -size +500c 2>/dev/null | head -n 10 | while read file; do
    lines=$(wc -l < "$file" 2>/dev/null)
    [ "$lines" -gt 500 ] && echo "  LARGE_CLASS: $file ($lines lines)"
done

echo "TEST_COVERAGE_ANALYSIS:"
TEST_FILES=$(timeout 5 find /opt /home /var/www -maxdepth 4 \( -name '*Test*.java' -o -name '*test*.py' -o -name '*.spec.js' \) 2>/dev/null | wc -l || echo "0")
TOTAL_SRC=$(echo "$JAVA_FILES$PYTHON_FILES$JS_FILES" | grep -c . || echo 1)
TEST_RATIO=$((TEST_FILES * 100 / TOTAL_SRC))
echo "  TEST_FILES: $TEST_FILES / TOTAL: $TOTAL_SRC (Coverage Ratio: ~$TEST_RATIO%)"

echo "DEPENDENCY_ANALYSIS (Coupling):"
echo "$JAVA_FILES" | head -n 15 | while read file; do
    if [ -f "$file" ]; then
        imports=$(grep -c '^import' "$file" 2>/dev/null || echo "0")
        [ "${imports:-0}" -gt 20 ] && echo "  HIGH_COUPLING: $file ($imports imports)"
    fi
done

echo "CODE_SMELLS:"
echo "  EMPTY_CATCH_BLOCKS: $(echo "$JAVA_FILES" | timeout 3 xargs grep -l 'catch.*{}' 2>/dev/null | wc -l || echo "0") files"
echo "  HARDCODED_CREDENTIALS: $(echo "$JAVA_FILES$PHP_FILES" | timeout 3 xargs grep -l 'password.*=\|pwd.*=' 2>/dev/null | wc -l || echo "0") files"
echo "  TODO_COMMENTS: $(echo "$JAVA_FILES" | timeout 3 xargs grep -c 'TODO\|FIXME\|HACK' 2>/dev/null | tail -1 || echo "0")"

echo "--- PERFORMANCE HOTSPOTS ---"
echo "SLOW_QUERY_PATTERNS:"
echo "$JAVA_FILES$PHP_FILES" | timeout 3 xargs grep -l 'SELECT \*\|N+1\|inefficient' 2>/dev/null | head -n 10 | while read file; do
    echo "  RISK_FILE: $file"
done

echo "LOOP_NESTING (>3 levels):"
echo "$JAVA_FILES" | head -n 10 | while read file; do
    if [ -f "$file" ]; then
        nesting=$(grep -o 'for.*for.*for' "$file" 2>/dev/null | wc -l || echo "0")
        [ "${nesting:-0}" -gt 0 ] && echo "  DEEP_NESTING: $file ($nesting instances)"
    fi
done

echo "--- SECURITY ANALYSIS (Static) ---"
echo "SQL_INJECTION_RISK:"
echo "$JAVA_FILES$PHP_FILES" | timeout 3 xargs grep -l 'executeQuery.*+\|concat.*query' 2>/dev/null | head -n 5 | wc -l | xargs echo "  VULNERABLE_FILES:"

echo "HARDCODED_SECRETS:"
echo "$JAVA_FILES$PHP_FILES" | timeout 3 xargs grep -E 'password|api_key|secret|token.*=' 2>/dev/null | grep -v '//.*password' | head -n 5 | wc -l | xargs echo "  SECRETS_FOUND:"

echo "UNSAFE_DESERIALIZATION:"
echo "$JAVA_FILES" | timeout 3 xargs grep -l 'ObjectInputStream\|readObject' 2>/dev/null | wc -l | xargs echo "  RISKY_FILES:"

echo "--- GIT REPOSITORIES ---"
timeout 5 find /opt /home /var/www -maxdepth 3 -name ".git" -type d 2>/dev/null | head -n 5 | while read gitdir; do
    echo "GIT_REPO: $(dirname $gitdir)"
done

echo "--- VERSION CONTROL METRICS ---"
timeout 5 find /opt /home /var/www -maxdepth 3 -name ".git" -type d 2>/dev/null | head -n 3 | while read gitdir; do
    repo_path=$(dirname "$gitdir")
    echo "REPO_PATH: $repo_path"
    [ -d "$repo_path/.git" ] && cd "$repo_path" && echo "  COMMITS: $(timeout 2 git log --oneline 2>/dev/null | wc -l || echo "0")" || echo "  COMMITS: N/A"
    [ -d "$repo_path/.git" ] && echo "  BRANCHES: $(timeout 2 git branch -r 2>/dev/null | wc -l || echo "0")" || echo "  BRANCHES: N/A"
done

echo "--- END CLOUD MODERNIZATION INVENTORY ---"

# === POST-COLLECTION DISK MANAGEMENT ===
REPORT_SIZE=$(du -h "$OUTPUT_FILE" 2>/dev/null | cut -f1)
echo ""
echo "--- COLLECTION SUMMARY ---"
echo "Report Generated: $OUTPUT_FILE"
echo "Report Size: $REPORT_SIZE"
echo "Timestamp: $(date)"

# Check final disk status
AVAILABLE_AFTER=$(df -m "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $(NF-2)}' | tr -d 'M%')
USE_AFTER=$(df "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $(NF-1)}' | tr -d '%')
AVAILABLE_AFTER=${AVAILABLE_AFTER//[^0-9]/}
USE_AFTER=${USE_AFTER//[^0-9]/}
echo "Disk Usage After: ${USE_AFTER}%"
echo "Available Space: ${AVAILABLE_AFTER}MB"

# Auto-cleanup: Keep only last 10 recent reports
echo ""
echo "--- DISK CLEANUP (Auto-removing old reports) ---"
REPORT_COUNT=$(ls -1 "$OUTPUT_DIR"/inventory_*.txt 2>/dev/null | wc -l)
if [ "$REPORT_COUNT" -gt 10 ]; then
    echo "Found $REPORT_COUNT reports. Keeping last 10 (removing oldest)..."
    ls -1tr "$OUTPUT_DIR"/inventory_*.txt 2>/dev/null | head -n $((REPORT_COUNT - 10)) | while read old_report; do
        OLD_SIZE=$(du -h "$old_report" 2>/dev/null | cut -f1)
        rm -f "$old_report"
        echo "  Removed: $(basename $old_report) ($OLD_SIZE freed)"
    done
    FREED_SPACE=$(df -m "$CURRENT_DIR" 2>/dev/null | tail -n 1 | awk '{print $4}')
    echo "After cleanup: ${FREED_SPACE}MB available"
else
    echo "Reports in directory: $REPORT_COUNT (auto-cleanup: keep max 10)"
fi

echo ""
echo "✓ Collection completed successfully"

# === ENFORCE 20MB SIZE LIMIT ===
MAX_SIZE_MB=20
MAX_SIZE_BYTES=$((MAX_SIZE_MB * 1024 * 1024))
CURRENT_SIZE_BYTES=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || du -b "$OUTPUT_FILE" 2>/dev/null | cut -f1)

if [ "$CURRENT_SIZE_BYTES" -gt "$MAX_SIZE_BYTES" ]; then
    echo ""
    echo "WARNING: Report size (${CURRENT_SIZE_BYTES} bytes) exceeds ${MAX_SIZE_MB}MB limit!"
    echo "Truncating file to ${MAX_SIZE_MB}MB..."
    
    # Keep first 5MB (system info) and last 3MB (summary)
    TEMP_FILE="${OUTPUT_FILE}.tmp"
    HEAD_SIZE=$((5 * 1024 * 1024))
    TAIL_SIZE=$((3 * 1024 * 1024))
    
    echo "" >> "$OUTPUT_FILE"
    echo "=== FILE TRUNCATED TO ${MAX_SIZE_MB}MB ===" >> "$OUTPUT_FILE"
    echo "Original size: $(numfmt --to=iec-i --suffix=B $CURRENT_SIZE_BYTES 2>/dev/null || echo "${CURRENT_SIZE_BYTES} bytes")" >> "$OUTPUT_FILE"
    echo "Kept: First 5MB (OS/infrastructure) + Last 3MB (summary/security)" >> "$OUTPUT_FILE"
    
    # Truncate file to max size using 1MB chunks instead of 1 byte chunks (massive performance gain)
    truncate -s $MAX_SIZE_BYTES "$OUTPUT_FILE" 2>/dev/null || dd if="$OUTPUT_FILE" of="$TEMP_FILE" bs=1048576 count=$MAX_SIZE_MB status=none 2>/dev/null && mv "$TEMP_FILE" "$OUTPUT_FILE"
    
    FINAL_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || du -b "$OUTPUT_FILE" 2>/dev/null | cut -f1)
    echo "Final report size: $(numfmt --to=iec-i --suffix=B $FINAL_SIZE 2>/dev/null || echo "${FINAL_SIZE} bytes")"
else
    FINAL_SIZE=$(numfmt --to=iec-i --suffix=B $CURRENT_SIZE_BYTES 2>/dev/null || echo "${CURRENT_SIZE_BYTES} bytes")
    echo "Report size: $FINAL_SIZE (within ${MAX_SIZE_MB}MB limit)"
fi
