# 🏗 OpenClaw Job Offer Radar Agent — Infrastructure & DevOps

## Production-Grade Deployment Architecture

---

## 1. Система версионирования

### Выбор: GitHub

**Почему GitHub, а не GitLab:**
- OpenClaw и job-scanner-tg-notification уже на GitHub — единая экосистема
- GitHub Actions — проще для CI/CD одного проекта
- GitHub Container Registry (ghcr.io) — бесплатный для публичных образов
- Для приватного проекта одного человека — free tier хватает

### Структура репозитория: Monorepo

```
jora/
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # Lint + test на каждый push/PR
│   │   ├── build-push.yml            # Build Docker images → GHCR
│   │   └── deploy.yml                # Deploy на VPS по тегу/ручному триггеру
│   └── dependabot.yml                # Автоапдейт зависимостей
│
├── infrastructure/
│   ├── docker-compose.yml            # Продакшен compose
│   ├── docker-compose.dev.yml        # Dev/локальный override
│   ├── Makefile                      # Shortcut-команды
│   ├── .env.template                 # Шаблон переменных (без секретов)
│   └── scripts/
│       ├── install.sh                # Полный инсталлятор VPS
│       ├── backup.sh                 # Бэкап MongoDB + конфигов
│       ├── restore.sh                # Восстановление из бэкапа
│       ├── healthcheck.sh            # Проверка здоровья всех сервисов
│       └── update.sh                 # Обновление до последней версии
│
├── scanner/                          # Fork/submodule job-scanner-tg-notification
│   ├── config/
│   │   ├── default.json.template     # Шаблон (keywords + TG)
│   │   └── jobSites.json             # Seed sources (версионируется)
│   ├── index.js
│   ├── jobTitleParser.js
│   ├── Dockerfile
│   └── package.json
│
├── enrichment/                       # Enrichment service
│   ├── config/
│   │   └── default.json.template
│   ├── src/
│   │   ├── index.js                  # Entry point
│   │   ├── dedup.js                  # Fuzzy dedup logic
│   │   ├── enricher.js               # Company enrichment
│   │   ├── scorer.js                 # Relevance scoring
│   │   └── notifier.js               # Enhanced TG notifications
│   ├── Dockerfile
│   └── package.json
│
├── skills/                           # OpenClaw skills
│   ├── keyword-expander/
│   │   └── SKILL.md
│   ├── source-discovery/
│   │   └── SKILL.md
│   ├── source-validator/
│   │   └── SKILL.md
│   ├── doc-generator/
│   │   └── SKILL.md
│   └── job-coordinator/
│       └── SKILL.md
│
├── monitoring/
│   ├── docker-compose.monitoring.yml # Prometheus + Grafana + Loki
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── dashboards/
│   │   │   │   └── jora-dashboard.json   # Дашборд: вакансии, источники, API cost
│   │   │   └── datasources/
│   │   │       └── datasources.yml
│   │   └── dashboards/
│   │       └── jora-dashboard.json
│   ├── loki/
│   │   └── loki-config.yml
│   ├── promtail/
│   │   └── promtail-config.yml
│   └── alertmanager/
│       └── alertmanager.yml          # Алерты → Telegram
│
├── templates/                        # Данные пользователя (gitignore'd, но шаблоны — нет)
│   ├── keywords.json.example
│   ├── sources.json.example
│   ├── blacklist.json.example
│   ├── master_resume.json.example
│   └── candidate_profile.json.example
│
├── docs/
│   ├── SETUP_GUIDE.md                # Полный гайд (текущий v3)
│   ├── ARCHITECTURE.md               # Архитектурная документация
│   ├── RUNBOOK.md                    # Инструкции на случай инцидентов
│   └── CHANGELOG.md
│
├── .gitignore
├── .dockerignore
├── LICENSE
└── README.md
```

### .gitignore

```gitignore
# Секреты
.env
*.env.local
infrastructure/secrets/

# Пользовательские данные
workspace/jobs/
data/mongo/

# Runtime
node_modules/
*.log
__pycache__/

# OS
.DS_Store
Thumbs.db
```

### Branching Strategy

Простая модель для проекта одного человека:

```
main          ← стабильная версия, деплоится по тегу
  └── dev     ← текущая разработка, автотесты
       └── feature/xxx  ← фичи (если нужно)
```

| Событие | Действие |
|---------|---------|
| Push в `dev` | CI: lint + test |
| PR `dev → main` | CI: lint + test + build images |
| Тег `v*` на `main` | CD: build + push images → deploy на VPS |
| Ручной trigger | Deploy конкретной версии |

---

## 2. Infrastructure as Code

### Docker images: Multi-stage builds

#### scanner/Dockerfile
```dockerfile
FROM node:22-slim

# Chromium for puppeteer (anti-bot scraping)
RUN apt-get update && apt-get install -y chromium --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY . .

USER node
CMD ["node", "index.js"]
```

> **Note:** `fakebrowser` was replaced with `puppeteer-extra` + `puppeteer-extra-plugin-stealth` (fakebrowser incompatible with puppeteer v19+). `npm install --omit=dev` instead of `npm ci` to avoid lock-file conflicts when updating dependencies.

#### enrichment/Dockerfile
```dockerfile
FROM node:22-slim AS base
WORKDIR /app

FROM base AS deps
COPY package*.json ./
RUN npm ci --production

FROM base AS runtime
COPY --from=deps /app/node_modules ./node_modules
COPY src/ ./src/
USER node
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD node -e "process.exit(0)"
CMD ["node", "src/index.js"]
```

### Docker Compose: Production

```yaml
# infrastructure/docker-compose.yml

services:
  # === Scanner ===
  scanner:
    image: ghcr.io/${GITHUB_USER}/jora-scanner:${VERSION:-latest}
    build:
      context: ../scanner
    volumes:
      - scanner_config:/app/config
    environment:
      - MONGO_URI=mongodb://mongo:27017/${DB_NAME:-job_hunter_db}
    depends_on:
      mongo:
        condition: service_healthy
    restart: unless-stopped
    logging: &logging
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
        tag: "{{.Name}}"
    networks:
      - backend

  # === Enrichment ===
  enrichment:
    image: ghcr.io/${GITHUB_USER}/jora-enrichment:${VERSION:-latest}
    build:
      context: ../enrichment
    environment:
      - MONGO_URI=mongodb://mongo:27017/${DB_NAME:-job_hunter_db}
      - TG_TOKEN=${TG_BOT_TOKEN}
      - TG_CHAT_ID=${TG_CHAT_ID}
      - DUPLICATE_THRESHOLD=${DUPLICATE_THRESHOLD:-0.85}
      - RELEVANCE_SCORE_MIN=${RELEVANCE_SCORE_MIN:-0}
    depends_on:
      mongo:
        condition: service_healthy
    restart: unless-stopped
    logging: *logging
    networks:
      - backend

  # === MongoDB ===
  mongo:
    image: mongo:7
    volumes:
      - mongo_data:/data/db
      - mongo_config:/data/configdb
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    logging: *logging
    networks:
      - backend

  # === MongoDB Backup (cron) ===
  mongo-backup:
    image: mongo:7
    volumes:
      - mongo_backups:/backups
      - mongo_data:/data/db:ro
    entrypoint: >
      sh -c 'while true; do
        mongodump --uri="mongodb://mongo:27017/${DB_NAME:-job_hunter_db}" \
          --out=/backups/$$(date +%Y%m%d_%H%M%S) &&
        find /backups -maxdepth 1 -mtime +7 -exec rm -rf {} \; ;
        sleep 86400;
      done'
    depends_on:
      mongo:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - backend

volumes:
  mongo_data:
  mongo_config:
  mongo_backups:
  scanner_config:

networks:
  backend:
    driver: bridge
```

### Makefile

```makefile
# infrastructure/Makefile

.PHONY: help install up down restart logs status backup restore update health

COMPOSE = docker compose -f docker-compose.yml
COMPOSE_MON = docker compose -f docker-compose.monitoring.yml

help: ## Показать справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Полная установка с нуля
	bash scripts/install.sh

up: ## Запустить все сервисы
	$(COMPOSE) up -d

up-mon: ## Запустить мониторинг
	$(COMPOSE_MON) up -d

down: ## Остановить все сервисы
	$(COMPOSE) down

restart: ## Перезапустить все
	$(COMPOSE) restart

restart-scanner: ## Перезапустить только сканер
	$(COMPOSE) restart scanner

logs: ## Логи всех сервисов (follow)
	$(COMPOSE) logs -f

logs-scanner: ## Логи сканера
	$(COMPOSE) logs -f scanner

logs-enrichment: ## Логи enrichment
	$(COMPOSE) logs -f enrichment

status: ## Статус сервисов
	$(COMPOSE) ps
	@echo "---"
	@bash scripts/healthcheck.sh

backup: ## Бэкап MongoDB + конфигов
	bash scripts/backup.sh

restore: ## Восстановление (BACKUP_DIR=path)
	bash scripts/restore.sh $(BACKUP_DIR)

update: ## Обновление до последней версии
	bash scripts/update.sh

health: ## Проверка здоровья
	bash scripts/healthcheck.sh

mongo-shell: ## Войти в MongoDB shell
	docker exec -it $$($(COMPOSE) ps -q mongo) mongosh job_hunter_db

clean: ## Удалить все данные (ОСТОРОЖНО!)
	@read -p "Удалить ВСЕ данные? [y/N] " confirm && [ "$$confirm" = "y" ] && \
		$(COMPOSE) down -v || echo "Отменено"
```

---

## 3. Артефакты

### Docker Images → GitHub Container Registry (ghcr.io)

```
ghcr.io/{user}/jora-scanner:{tag}
ghcr.io/{user}/jora-enrichment:{tag}
```

### CI/CD Pipeline

#### .github/workflows/ci.yml
```yaml
name: CI

on:
  push:
    branches: [dev, main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm

      - name: Lint & test scanner
        working-directory: scanner
        run: |
          npm ci
          npm run lint --if-present
          npm test --if-present

      - name: Lint & test enrichment
        working-directory: enrichment
        run: |
          npm ci
          npm run lint --if-present
          npm test --if-present
```

#### .github/workflows/build-push.yml
```yaml
name: Build & Push Images

on:
  push:
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  SCANNER_IMAGE: ${{ github.repository_owner }}/jora-scanner
  ENRICHMENT_IMAGE: ${{ github.repository_owner }}/jora-enrichment

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract version
        id: meta
        run: echo "version=${GITHUB_REF_NAME#v}" >> $GITHUB_OUTPUT

      - name: Build & push scanner
        uses: docker/build-push-action@v5
        with:
          context: scanner
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.SCANNER_IMAGE }}:${{ steps.meta.outputs.version }}
            ${{ env.REGISTRY }}/${{ env.SCANNER_IMAGE }}:latest

      - name: Build & push enrichment
        uses: docker/build-push-action@v5
        with:
          context: enrichment
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.ENRICHMENT_IMAGE }}:${{ steps.meta.outputs.version }}
            ${{ env.REGISTRY }}/${{ env.ENRICHMENT_IMAGE }}:latest
```

#### .github/workflows/deploy.yml
```yaml
name: Deploy

on:
  workflow_run:
    workflows: [Build & Push Images]
    types: [completed]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to deploy (e.g., 1.0.0)'
        required: false
        default: 'latest'

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd ~/jora
            git pull origin main
            cd infrastructure
            VERSION=${{ inputs.version || 'latest' }} docker compose pull
            VERSION=${{ inputs.version || 'latest' }} docker compose up -d
            sleep 10
            bash scripts/healthcheck.sh
```

### Версионирование артефактов

| Артефакт | Хранение | Тегирование |
|----------|---------|------------|
| Docker images | ghcr.io | `v1.0.0` + `latest` |
| Skills (SKILL.md) | Git | По коммитам |
| Scanner config | Git (шаблоны) + VPS (runtime) | По коммитам |
| MongoDB dumps | VPS `/backups/` + [опц.] S3 | `YYYYMMDD_HHMMSS` |
| User data (resume, profile) | VPS only (не в git) | Ручные бэкапы |

---

## 4. Мониторинг и алерты

### Стек: Prometheus + Grafana + Loki + Alertmanager → Telegram

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ scanner  │────▶│  Prometheus   │────▶│   Grafana     │
│ enrichm. │     │  (метрики)    │     │  (дашборды)   │
│ mongo    │     └──────┬───────┘     └──────────────┘
│ openclaw │            │
└──────────┘            ▼
                 ┌──────────────┐     ┌──────────────┐
     Логи ──────▶│    Loki       │     │ Alertmanager  │──▶ 🔔 Telegram
     (promtail)  │  (логи)       │     │  (алерты)     │
                 └──────────────┘     └──────────────┘
```

### Метрики (custom endpoints в сервисах)

Каждый сервис экспортирует `/metrics` (Prometheus format):

**Scanner:**
```
job_scanner_scans_total{status="success|error"}       # Количество сканирований
job_scanner_vacancies_found_total{source="..."}        # Найдено вакансий
job_scanner_scan_duration_seconds{source="..."}        # Время сканирования
job_scanner_sources_active                              # Активных источников
```

**Enrichment:**
```
enrichment_processed_total{status="success|error"}     # Обработано вакансий
enrichment_duplicates_found_total                       # Найдено дубликатов
enrichment_notifications_sent_total                     # Отправлено уведомлений
enrichment_company_cache_hits_total                     # Кэш попадания
enrichment_processing_duration_seconds                  # Время обработки
```

**MongoDB (через mongodb-exporter):**
```
mongodb_connections_current
mongodb_op_counters_total{type="query|insert|update"}
mongodb_dbstats_collections{database="job_hunter_db"}
mongodb_dbstats_data_size{database="job_hunter_db"}
```

### Дашборд Grafana: Job Hunter Overview

| Панель | Метрика | Тип |
|--------|---------|-----|
| Вакансий найдено (24ч) | `increase(job_scanner_vacancies_found_total[24h])` | Stat |
| Вакансий за неделю | `increase(job_scanner_vacancies_found_total[7d])` | Graph |
| Источники: active / grey / error | `job_scanner_sources_active` | Gauge |
| Дубликаты | `increase(enrichment_duplicates_found_total[24h])` | Stat |
| TG уведомления | `increase(enrichment_notifications_sent_total[24h])` | Stat |
| Scan errors | `rate(job_scanner_scans_total{status="error"}[1h])` | Graph |
| MongoDB size | `mongodb_dbstats_data_size` | Gauge |
| API cost estimate | Custom (tokens × price) | Stat |

### Алерты → Telegram

#### Alertmanager config
```yaml
# monitoring/alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: telegram
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: telegram
    telegram_configs:
      - bot_token: '${TG_ALERT_BOT_TOKEN}'
        chat_id: ${TG_ALERT_CHAT_ID}
        parse_mode: HTML
        message: |
          {{ if eq .Status "firing" }}🔥{{ else }}✅{{ end }}
          <b>{{ .CommonLabels.alertname }}</b>
          {{ .CommonAnnotations.summary }}
          {{ range .Alerts }}
          {{ .Annotations.description }}
          {{ end }}
```

#### Alert rules
```yaml
# monitoring/prometheus/alerts.yml
groups:
  - name: jora
    rules:
      # Сканер не работает
      - alert: ScannerDown
        expr: up{job="scanner"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Scanner service is down"
          description: "Job scanner has been down for 5 minutes"

      # Сканер не находит вакансии (возможно сломались селекторы)
      - alert: NoVacanciesFound
        expr: increase(job_scanner_vacancies_found_total[24h]) == 0
        for: 24h
        labels:
          severity: warning
        annotations:
          summary: "No vacancies found in 24h"
          description: "Scanner found 0 vacancies. Check CSS selectors."

      # Enrichment отстаёт
      - alert: EnrichmentBacklog
        expr: (job_scanner_vacancies_found_total - enrichment_processed_total) > 20
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Enrichment backlog growing"
          description: "{{ $value }} vacancies waiting for enrichment"

      # MongoDB диск
      - alert: MongoDBDiskHigh
        expr: mongodb_dbstats_data_size > 1e9
        labels:
          severity: warning
        annotations:
          summary: "MongoDB data > 1GB"
          description: "Consider cleanup of old vacancies"

      # Docker контейнер рестартит
      - alert: ContainerRestarting
        expr: increase(container_restart_count[1h]) > 3
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.name }} restarting"
          description: "{{ $value }} restarts in the last hour"

      # VPS диск
      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.15
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Disk space < 15%"
          description: "VPS root partition running low"
```

### monitoring/docker-compose.monitoring.yml

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "127.0.0.1:9090:9090"
    restart: unless-stopped
    networks:
      - monitoring
      - backend

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_SERVER_ROOT_URL=http://localhost:3000
    ports:
      - "127.0.0.1:3000:3000"
    restart: unless-stopped
    networks:
      - monitoring

  loki:
    image: grafana/loki:latest
    volumes:
      - ./loki:/etc/loki
      - loki_data:/loki
    ports:
      - "127.0.0.1:3100:3100"
    restart: unless-stopped
    networks:
      - monitoring

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./promtail:/etc/promtail
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    restart: unless-stopped
    networks:
      - monitoring

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./alertmanager:/etc/alertmanager
    ports:
      - "127.0.0.1:9093:9093"
    restart: unless-stopped
    networks:
      - monitoring

  node-exporter:
    image: prom/node-exporter:latest
    pid: host
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
    restart: unless-stopped
    networks:
      - monitoring

  mongodb-exporter:
    image: percona/mongodb_exporter:0.40
    environment:
      - MONGODB_URI=mongodb://mongo:27017
    depends_on:
      - mongo
    restart: unless-stopped
    networks:
      - monitoring
      - backend

volumes:
  prometheus_data:
  grafana_data:
  loki_data:

networks:
  monitoring:
    driver: bridge
  backend:
    external: true
    name: infrastructure_backend
```

### Доступ к дашбордам — только через SSH-туннель

```bash
ssh -L 3000:localhost:3000 -L 9090:localhost:9090 user@VPS_IP
# Grafana:    http://localhost:3000
# Prometheus: http://localhost:9090
```

---

## 5. Инсталлятор: максимальная автоматизация

### Философия

Один скрипт `install.sh` + OpenClaw-агент для финальной настройки:

```
install.sh (bash)           → системные зависимости, Docker, структура
     │
     ▼
openclaw setup skill        → интерактивная настройка через TG:
                               ключевые слова, источники, одобрения
```

### install.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# OpenClaw Job Offer Radar Agent — Full Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/{user}/jora/main/infrastructure/scripts/install.sh | bash
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

PROJECT_DIR="${HOME}/jora"
REPO_URL="https://github.com/{USER}/jora.git"

# --- Pre-flight checks ---
preflight() {
    info "Running pre-flight checks..."

    if [ "$(id -u)" -eq 0 ]; then
        error "Do NOT run as root. Create a dedicated user first:"
        echo "  sudo adduser jobhunter && sudo usermod -aG sudo jobhunter && su - jobhunter"
        exit 1
    fi

    if [ "$(uname)" != "Linux" ]; then
        error "This installer requires Linux (Ubuntu 22.04+)"
        exit 1
    fi

    info "Pre-flight OK: user=$(whoami), os=$(uname -s)"
}

# --- System dependencies ---
install_deps() {
    info "Installing system dependencies..."
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y curl wget git build-essential jq
}

# --- Docker ---
install_docker() {
    if command -v docker &> /dev/null; then
        info "Docker already installed: $(docker --version)"
    else
        info "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker "$USER"
        info "Docker installed. You may need to re-login for group changes."
    fi

    if ! docker compose version &> /dev/null; then
        error "Docker Compose not found. Please install Docker Compose v2."
        exit 1
    fi
}

# --- Node.js ---
install_node() {
    if command -v node &> /dev/null && [[ "$(node -v)" == v22* ]]; then
        info "Node.js already installed: $(node -v)"
    else
        info "Installing Node.js 22..."
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
}

# --- OpenClaw ---
install_openclaw() {
    if command -v openclaw &> /dev/null; then
        info "OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'installed')"
    else
        info "Installing OpenClaw..."
        curl -fsSL https://get.openclaw.ai | bash
        info "OpenClaw installed. Run 'openclaw setup' for initial configuration."
    fi
}

# --- Clone project ---
setup_project() {
    if [ -d "$PROJECT_DIR" ]; then
        warn "Project directory exists. Pulling latest..."
        cd "$PROJECT_DIR" && git pull origin main
    else
        info "Cloning project..."
        git clone "$REPO_URL" "$PROJECT_DIR"
    fi

    cd "$PROJECT_DIR"

    # Create workspace
    mkdir -p workspace/jobs/applications

    # Copy templates if not exist
    for f in templates/*.example; do
        target="workspace/jobs/$(basename "$f" .example)"
        [ -f "$target" ] || cp "$f" "$target"
    done
}

# --- Environment ---
setup_env() {
    cd "$PROJECT_DIR/infrastructure"

    if [ -f .env ]; then
        warn ".env already exists. Skipping."
        return
    fi

    cp .env.template .env

    echo ""
    info "Configure your .env file:"
    echo ""

    read -rp "Telegram Bot Token (from @BotFather): " tg_token
    read -rp "Telegram Chat ID (from @userinfobot): " tg_chat_id
    read -rp "Anthropic API Key: " anthropic_key

    sed -i "s|TG_BOT_TOKEN=.*|TG_BOT_TOKEN=${tg_token}|" .env
    sed -i "s|TG_CHAT_ID=.*|TG_CHAT_ID=${tg_chat_id}|" .env
    sed -i "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${anthropic_key}|" .env

    chmod 600 .env
    info ".env configured"
}

# --- Install OpenClaw skills ---
install_skills() {
    info "Installing OpenClaw skills..."
    local skills_dir="${HOME}/.openclaw/workspace/skills"
    mkdir -p "$skills_dir"
    cp -r "${PROJECT_DIR}/skills/"* "$skills_dir/"
    info "Skills installed: $(ls "$skills_dir" | tr '\n' ' ')"
}

# --- Firewall ---
setup_firewall() {
    info "Configuring firewall..."
    sudo ufw allow OpenSSH
    sudo ufw --force enable
    info "Firewall enabled: only SSH allowed"
}

# --- Start services ---
start_services() {
    cd "$PROJECT_DIR/infrastructure"
    info "Starting Docker services..."
    docker compose up -d
    sleep 10

    info "Checking health..."
    bash scripts/healthcheck.sh || warn "Some services may still be starting"
}

# --- Systemd for OpenClaw ---
setup_openclaw_service() {
    info "Enabling OpenClaw systemd service..."
    sudo systemctl enable openclaw 2>/dev/null || warn "OpenClaw service not found. Run 'openclaw setup' first."
}

# --- Summary ---
summary() {
    echo ""
    echo "============================================================"
    info "✅ Installation complete!"
    echo "============================================================"
    echo ""
    echo "  Project:    ${PROJECT_DIR}"
    echo "  Docker:     $(docker compose -f ${PROJECT_DIR}/infrastructure/docker-compose.yml ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null || echo 'check manually')"
    echo "  OpenClaw:   $(openclaw status 2>/dev/null || echo 'run openclaw setup')"
    echo ""
    echo "  Next steps:"
    echo "  1. cd ${PROJECT_DIR}/infrastructure"
    echo "  2. make status"
    echo "  3. Send your TG bot: 'Ищи вакансии Head of QA'"
    echo ""
    echo "  Monitoring (optional):"
    echo "  make up-mon"
    echo "  ssh -L 3000:localhost:3000 $(whoami)@YOUR_VPS_IP"
    echo "  → http://localhost:3000 (Grafana)"
    echo ""
    echo "============================================================"
}

# --- Main ---
main() {
    echo ""
    echo "🦞 OpenClaw Job Offer Radar Agent — Installer"
    echo "============================================================"
    echo ""

    preflight
    install_deps
    install_docker
    install_node
    install_openclaw
    setup_project
    setup_env
    install_skills
    setup_firewall
    start_services
    setup_openclaw_service
    summary
}

main "$@"
```

### Скрипты обслуживания

#### healthcheck.sh
```bash
#!/usr/bin/env bash
# Проверяет что все сервисы работают

OK=0
FAIL=0

check() {
    local name=$1 cmd=$2
    if eval "$cmd" &>/dev/null; then
        echo "  ✅ $name"
        ((OK++))
    else
        echo "  ❌ $name"
        ((FAIL++))
    fi
}

echo "Health Check:"
check "Docker"     "docker info"
check "MongoDB"    "docker exec \$(docker compose ps -q mongo) mongosh --eval 'db.runCommand({ping:1})' --quiet"
check "Scanner"    "docker compose ps scanner | grep -q running"
check "Enrichment" "docker compose ps enrichment | grep -q running"
check "OpenClaw"   "systemctl is-active openclaw"

echo ""
echo "Result: ${OK} OK, ${FAIL} FAIL"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
```

#### update.sh
```bash
#!/usr/bin/env bash
set -euo pipefail

cd ~/jora

echo "📦 Pulling latest code..."
git pull origin main

echo "🔧 Updating skills..."
cp -r skills/* ~/.openclaw/workspace/skills/

echo "🐳 Pulling latest images..."
cd infrastructure
docker compose pull

echo "🔄 Restarting services..."
docker compose up -d

echo "⏳ Waiting for startup..."
sleep 10

echo "🏥 Health check..."
bash scripts/healthcheck.sh

echo "✅ Update complete"
```

#### backup.sh
```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${HOME}/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Backing up MongoDB..."
docker exec $(docker compose -f ~/jora/infrastructure/docker-compose.yml ps -q mongo) \
    mongodump --db job_hunter_db --out /tmp/dump
docker cp $(docker compose -f ~/jora/infrastructure/docker-compose.yml ps -q mongo):/tmp/dump "$BACKUP_DIR/mongo"

echo "📦 Backing up configs..."
cp -r ~/jora/infrastructure/.env "$BACKUP_DIR/"
cp -r ~/jora/workspace/jobs/ "$BACKUP_DIR/workspace_jobs/"
cp -r ~/.openclaw/openclaw.json "$BACKUP_DIR/" 2>/dev/null || true

echo "📦 Compressing..."
tar -czf "${BACKUP_DIR}.tar.gz" -C "$(dirname "$BACKUP_DIR")" "$(basename "$BACKUP_DIR")"
rm -rf "$BACKUP_DIR"

echo "✅ Backup: ${BACKUP_DIR}.tar.gz ($(du -h "${BACKUP_DIR}.tar.gz" | cut -f1))"

# Cleanup old backups (keep 4 weeks)
find ~/backups -name "*.tar.gz" -mtime +28 -delete
```

---

## Сводка: от POC к Production

| Аспект | POC (сейчас) | Production (цель) |
|--------|-------------|-------------------|
| Код | Файлы на VPS | GitHub monorepo |
| Docker images | `docker compose build` на VPS | GHCR → `docker compose pull` |
| Деплой | Ручной `scp` + `restart` | `git tag v1.0.0` → auto deploy |
| Секреты | `.env` на диске | `.env` + GitHub Secrets для CD |
| Бэкапы | Ручной `tar` | Ежедневный cron + retention |
| Мониторинг | `docker compose logs` | Prometheus + Grafana + алерты в TG |
| Логи | `journalctl` | Loki + Promtail + Grafana |
| Алерты | Нет | Scanner down, no vacancies, disk, restarts |
| Установка | 10+ ручных шагов | `curl ... \| bash` — один скрипт |
| Обновление | Ручное | `make update` или auto по тегу |
| Healthcheck | `docker compose ps` | `make health` + Prometheus |

---

## Стоимость Production

| Компонент | Стоимость |
|-----------|-----------|
| VPS Ubuntu (Hetzner CX32, 8GB — для мониторинга) | €8.45/мес |
| Anthropic API (Claude Sonnet) | $20-35/мес |
| GitHub (free tier, private repo) | $0 |
| GHCR (free tier) | $0 |
| Domain (опционально) | ~$10/год |
| **Итого** | **~€29-44/мес** |
