#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKUP_DIR="${HOME}/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Backing up MongoDB..."
docker compose -f "${PROJECT_DIR}/infrastructure/docker-compose.yml" \
    exec -T mongo mongodump --db job_hunter_db --archive > "${BACKUP_DIR}/mongo.archive"

echo "📦 Backing up configs..."
cp "${PROJECT_DIR}/infrastructure/.env" "${BACKUP_DIR}/.env" 2>/dev/null || true
cp -r "${PROJECT_DIR}/workspace/jobs/" "${BACKUP_DIR}/workspace_jobs/" 2>/dev/null || true
cp -r "${PROJECT_DIR}/scanner/config/" "${BACKUP_DIR}/scanner_config/" 2>/dev/null || true

echo "📦 Compressing..."
tar -czf "${BACKUP_DIR}.tar.gz" -C "$(dirname "$BACKUP_DIR")" "$(basename "$BACKUP_DIR")"
rm -rf "$BACKUP_DIR"

# Keep 4 weeks
find "${HOME}/backups" -name "*.tar.gz" -mtime +28 -delete 2>/dev/null || true

echo "✅ Backup: ${BACKUP_DIR}.tar.gz ($(du -h "${BACKUP_DIR}.tar.gz" | cut -f1))"
