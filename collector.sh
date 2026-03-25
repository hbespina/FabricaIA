#!/bin/bash
# ==============================================================================
# Modernization Factory - Agente Colector V1.0
# Uso: chmod +x collector.sh && ./collector.sh > inventory.txt
# Diseñado para: RHEL 4+, Solaris, AIX, Debian/Ubuntu
# ==============================================================================

echo "--- START CLOUD MODERNIZATION INVENTORY ---"
echo "TIMESTAMP: $(date)"
echo "HOSTNAME: $(hostname)"

echo "--- OS RELEASE ---"
if [ -f /etc/redhat-release ]; then
    cat /etc/redhat-release
elif [ -f /etc/debian_version ]; then
    echo "Debian $(cat /etc/debian_version)"
else
    uname -a
fi

echo "--- PROCESSES ---"
ps -ef | grep -v "\[" | head -n 100

echo "--- NETSTAT/LISTENING PORTS ---"
if command -v netstat >/dev/null 2>&1; then
    netstat -tulpn | grep LISTEN
elif command -v ss >/dev/null 2>&1; then
    ss -tlpn
else
    lsof -i -P -n | grep LISTEN
fi

echo "--- CRITICAL DIRECTORIES ---"
for dir in /opt /usr/local /home; do
    echo "Checking $dir..."
    ls -F $dir | head -n 20
done

echo "--- ENV VARIABLES ---"
env | grep -E "JAVA|TOMCAT|ORACLE|PATH|HOME"

echo "--- DOCKER/CONTAINER INFO ---"
if command -v docker >/dev/null 2>&1; then
    docker ps --format "table {{.Image}}\t{{.Status}}\t{{.Ports}}"
fi

echo "--- END CLOUD MODERNIZATION INVENTORY ---"
