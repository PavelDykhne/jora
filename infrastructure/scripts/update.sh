#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "📦 Pulling latest code..."
cd "$PROJECT_DIR"
git pull origin main

echo "🔧 Updating skills..."
skills_dir="$(openclaw config get skillsDir 2>/dev/null || echo "${HOME}/.openclaw/workspace/skills")"
cp -r skills/* "$skills_dir/"

echo "🐳 Rebuilding & restarting..."
cd infrastructure
docker compose up -d --build

echo "⏳ Waiting..."
sleep 10

echo "🏥 Health check..."
bash scripts/healthcheck.sh

echo "✅ Update complete"
