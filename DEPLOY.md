# 🚀 Deploy Instructions

## Для Claude Code / OpenClaw на VPS

Эта инструкция предназначена для выполнения **Claude Code** или **вручную** на VPS где уже установлены Claude Code и OpenClaw.

---

## Шаг 0: Подготовка файлов

Перенести архив `jora.tar.gz` на VPS:

```bash
# С локальной машины:
scp jora.tar.gz oc@YOUR_VPS_IP:~/

# На VPS:
cd ~
tar -xzf jora.tar.gz
cd jora
```

Или через git (после создания репо):
```bash
cd ~
git clone https://github.com/YOUR_USER/jora.git
cd jora
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
cd ~/jora/infrastructure
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
cd ~/jora/scanner/config

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
cd ~/jora

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
cd ~/jora

# Определить путь к skills
SKILLS_DIR=$(openclaw config get skillsDir 2>/dev/null || echo "${HOME}/.openclaw/workspace/skills")
mkdir -p "$SKILLS_DIR"

# Копировать
cp -r skills/* "$SKILLS_DIR/"

# Проверить
ls "$SKILLS_DIR"
# → doc-generator  google-workspace  job-coordinator  keyword-expander
# → sheet-importer  source-discovery  source-validator
```

---

## Шаг 6: Запустить Docker-стек

```bash
cd ~/jora/infrastructure

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

Проект использует **systemd-сервис** (`/etc/systemd/system/openclaw.service`).

Важно: в файле сервиса должен быть указан реальный пользователь системы (не группа):
```ini
[Service]
User=oc          # замени на своё имя пользователя (не группу)
WorkingDirectory=/home/oc
ExecStart=/home/oc/.npm-global/bin/openclaw gateway run
```

```bash
# Запустить через systemd (рекомендуется):
sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw
sudo systemctl status openclaw

# Если systemd недоступен (контейнер, нет linger):
HOME=/home/oc /home/oc/.npm-global/bin/openclaw gateway run &

# Или через screen/tmux:
screen -S openclaw
HOME=/home/oc openclaw gateway run
# Ctrl+A, D чтобы отсоединиться
```

Проверить что модель применилась (в логах должна быть строка):
```
[gateway] agent model: anthropic/claude-haiku-4-5-20251001
```

---

## Шаг 8: Проверить

```bash
cd ~/jora/infrastructure
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
cd ~/jora/infrastructure

make status            # Статус
make logs              # Логи
make backup            # Бэкап
make restart-scanner   # Перезапустить сканер (после смены конфигов)
make update            # Обновить из git + перезапустить
```

## Мониторинг API

Скрипт `jora-api-stats` показывает сколько вызовов к Anthropic API тратится на каждое сообщение в боте:

```bash
jora-api-stats             # сегодня
jora-api-stats --yesterday # вчера
jora-api-stats --watch     # реальное время — видно каждый вызов
```

Установка (один раз, если скрипта нет в PATH):
```bash
ln -sf /home/oc/.local/bin/jora-api-stats /usr/local/bin/jora-api-stats
```

Пример вывода:
```
  Время  Модель    LLM  Tools  Статус
  22:51  haiku       2     12  ✅
  23:01  haiku       3     41  ✅
─────────────────────────────────────
  LLM вызовов (API)   : 5   ← считаются в rate limit
  Tool вызовов        : 53  ← не считаются
  Среднее LLM/сообщ. : 2.5
  Пик LLM (1 мин)    : 3
```

Файл скрипта: `/home/oc/.local/bin/jora-api-stats`
Логи OpenClaw: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
