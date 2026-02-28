# 🚀 Deploy Instructions

## Для Claude Code / OpenClaw на VPS

Эта инструкция предназначена для выполнения **Claude Code** или **вручную** на VPS где уже установлены Claude Code и OpenClaw.

---

## Шаг 0: Подготовка файлов

Перенести архив `job-hunter-agent.tar.gz` на VPS:

```bash
# С локальной машины:
scp job-hunter-agent.tar.gz oc@YOUR_VPS_IP:~/

# На VPS:
cd ~
tar -xzf job-hunter-agent.tar.gz
cd job-hunter-agent
```

Или через git (после создания репо):
```bash
cd ~
git clone https://github.com/YOUR_USER/job-hunter-agent.git
cd job-hunter-agent
```

---

## Шаг 1: Проверить зависимости

```bash
# Docker
docker --version          # нужна 24+
docker compose version    # нужна v2+

# Node.js
node -v                   # нужна 22+

# OpenClaw
openclaw --version
```

Если чего-то нет — install.sh установит:
```bash
cd infrastructure
bash scripts/install.sh
```

---

## Шаг 2: Создать .env

```bash
cd ~/job-hunter-agent/infrastructure
cp .env.template .env
nano .env
```

Заполнить:
- `TG_BOT_TOKEN` — от @BotFather
- `TG_CHAT_ID` — от @userinfobot (ваш ID)
- `ANTHROPIC_API_KEY` — из console.anthropic.com

---

## Шаг 3: Настроить сканер

```bash
cd ~/job-hunter-agent/scanner/config

# Создать default.json из шаблона
cp default.json.template default.json
nano default.json
```

Подставить `TG_BOT_TOKEN` и `TG_CHAT_ID` в поля `TELEGRAM.TOKEN` и `TELEGRAM.CHAT_ID`.

Ключевые слова (`JOB_KEYWORDS`) уже заполнены 25 вариациями для Head of QA.
Сайты (`jobSites.json`) — 18 seed-источников.

---

## Шаг 4: Исходники сканера

Сканер — это внешний проект. Нужно скопировать его исходники в `scanner/`:

```bash
cd ~/job-hunter-agent

# Клонировать во временную папку и скопировать исходники
git clone https://github.com/EgorBodnar/job-scanner-tg-notification.git /tmp/job-scanner
cp /tmp/job-scanner/index.js scanner/
cp /tmp/job-scanner/jobTitleParser.js scanner/
cp /tmp/job-scanner/package.json scanner/package-upstream.json

# Мержим package.json (берём upstream, наш Dockerfile совместим)
cp /tmp/job-scanner/package.json scanner/package.json
cp /tmp/job-scanner/package-lock.json scanner/package-lock.json 2>/dev/null || true

rm -rf /tmp/job-scanner
```

> **Почему не git submodule?** Для простоты POC. В продакшене — форк или submodule.

---

## Шаг 5: Установить OpenClaw skills

```bash
cd ~/job-hunter-agent

# Определить путь к skills
SKILLS_DIR=$(openclaw config get skillsDir 2>/dev/null || echo "${HOME}/.openclaw/workspace/skills")
mkdir -p "$SKILLS_DIR"

# Копировать
cp -r skills/* "$SKILLS_DIR/"

# Проверить
ls "$SKILLS_DIR"
# → doc-generator  job-coordinator  keyword-expander  source-discovery  source-validator
```

---

## Шаг 6: Запустить Docker-стек

```bash
cd ~/job-hunter-agent/infrastructure

# Собрать и запустить
docker compose up -d --build

# Проверить
docker compose ps

# Логи
docker compose logs -f
```

Ожидаемый результат:
```
scanner     running
enrichment  running
mongo       running (healthy)
```

---

## Шаг 7: Запустить OpenClaw gateway

```bash
# Если systemd доступен:
openclaw service install
openclaw gateway start

# Если systemd НЕ доступен (контейнер, нет linger):
openclaw gateway start --no-service

# Или через screen/tmux:
screen -S openclaw
openclaw gateway start --foreground
# Ctrl+A, D чтобы отсоединиться
```

---

## Шаг 8: Проверить

```bash
cd ~/job-hunter-agent/infrastructure
bash scripts/healthcheck.sh
```

Ожидаемый результат:
```
🏥 Health Check
  ✅ Docker
  ✅ MongoDB
  ✅ Scanner
  ✅ Enrichment
  ✅ OpenClaw
Result: 5 OK, 0 FAIL
```

---

## Шаг 9: Первый запуск

Открой Telegram → твой бот → напиши:

> Ищи вакансии "Head of QA"

Агент должен:
1. Подтвердить ключевые слова (25 штук)
2. Предложить источники
3. После одобрения — сканер начнёт работу

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `ECONNREFUSED` при `openclaw gateway start` | `loginctl enable-linger $USER` (от root) или `--no-service` |
| Scanner exit code 1 | `docker compose logs scanner` — обычно неверный CSS-селектор |
| Enrichment не шлёт в TG | Проверь `TG_BOT_TOKEN` и `TG_CHAT_ID` в `.env` |
| MongoDB unhealthy | `docker compose logs mongo` — возможно мало RAM |
| Skills не триггерятся | `openclaw skills list` — проверь что установились |

---

## Ежедневные команды

```bash
cd ~/job-hunter-agent/infrastructure

make status            # Статус
make logs              # Логи
make backup            # Бэкап
make restart-scanner   # Перезапустить сканер (после смены конфигов)
make update            # Обновить из git + перезапустить
```
