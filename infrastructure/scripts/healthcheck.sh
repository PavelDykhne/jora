#!/usr/bin/env bash
set -uo pipefail

OK=0; FAIL=0

check() {
    local name=$1; shift
    if "$@" &>/dev/null; then
        echo "  ✅ $name"; ((OK++))
    else
        echo "  ❌ $name"; ((FAIL++))
    fi
}

echo "🏥 Health Check"
check "Docker"       docker info
check "MongoDB"      docker compose exec -T mongo mongosh --eval 'db.runCommand({ping:1})' --quiet
check "Scanner"      docker compose ps scanner --format '{{.State}}' | grep -q running
check "Enrichment"   docker compose ps enrichment --format '{{.State}}' | grep -q running

# OpenClaw — optional, may not be systemd
if command -v openclaw &>/dev/null; then
    check "OpenClaw" openclaw gateway probe
fi

echo ""
echo "Result: ${OK} OK, ${FAIL} FAIL"
[ "$FAIL" -eq 0 ]
