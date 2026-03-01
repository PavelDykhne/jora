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

Конфигурация источников (все файлы уже есть в репо):
- `sources.json` — единый реестр источников со статусами и статистикой
- `jobSites.json` — auto-generated из sources.json (active web only), не редактировать вручную
- `tg_sources.json` — auto-generated из sources.json (active TG only), не редактировать вручную
- `blacklist.json` — перманентно исключённые источники

---

## Шаг 4: Исходники сканера

Исходники сканера хранятся прямо в репо (`scanner/`). Внешних зависимостей нет.

Если нужно обновить `jobTitleParser.js` из upstream:
```bash
curl -o scanner/jobTitleParser.js \
  https://raw.githubusercontent.com/EgorBodnar/job-scanner-tg-notification/main/jobTitleParser.js
```

> `scanner/index.js` — форк с добавленной записью статистики и deep scan для новых источников. Не заменять upstream-версией.

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
# → sheet-importer  sheet-scanner  source-discovery  source-validator
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

> **Bind mount:** сканер монтирует `../scanner/config` напрямую — изменения в `sources.json` подхватываются на следующем цикле без перезапуска контейнера.
> **MongoDB:** порт 27017 проброшен на `127.0.0.1` — доступен с хоста для OpenClaw skills.

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

## Шаг 8.5: Настроить OpenClaw cron

После запуска gateway добавить автоматические задачи:

```bash
# Вечерняя проверка источников (ежедневно 18:00)
openclaw cron add \
  --name "source-health-check" \
  --cron "0 18 * * *" \
  --announce \
  --message "Выполни вечернюю проверку здоровья источников. Запусти health check: прочитай /home/oc/jora/scanner/config/sources.json, проверь для каждого активного источника поля stats (last_scan, last_new_vacancy, consecutive_failures), переведи в серый список источники без релевантных вакансий более 30 дней или с 3+ ошибками подряд. Обнови sources.json, jobSites.json, tg_sources.json. Отправь отчёт." \
  --description "Вечерняя проверка актуальности источников → серый список"

# Еженедельная перепроверка серого списка (воскресенье 10:00)
openclaw cron add \
  --name "grey-list-recheck" \
  --cron "0 10 * * 0" \
  --announce \
  --message "Выполни еженедельную перепроверку серого списка источников. Прочитай /home/oc/jora/scanner/config/sources.json, найди источники со статусом grey: если grey_since 180+ дней назад — переведи в blacklist и обнови blacklist.json; для остальных попробуй HTTP-запрос к URL и найди keyword-совпадения из default.json — если нашлись релевантные вакансии, верни в active. Обнови sources.json, jobSites.json, tg_sources.json. Отправь отчёт." \
  --description "Еженедельная перепроверка серого списка → чёрный список после 180 дней"

# Проверить
openclaw cron list
```

## Шаг 9: Первый запуск

Открой Telegram → твой бот → напиши:

> Ищи вакансии "Head of QA"

Агент должен:
1. Подтвердить ключевые слова (25 штук)
2. Предложить источники
3. После одобрения — сканер начнёт работу
4. Новые источники автоматически получат deep scan (180-дневный lookback)

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `ECONNREFUSED` при `openclaw gateway start` | `loginctl enable-linger $USER` (от root) или `--no-service` |
| Scanner exit code 1 | `docker compose logs scanner` — обычно неверный CSS-селектор |
| Enrichment не шлёт в TG | Проверь `TG_BOT_TOKEN` и `TG_CHAT_ID` в `.env` |
| MongoDB unhealthy | `docker compose logs mongo` — возможно мало RAM |
| Skills не триггерятся | `openclaw skills list` — проверь что установились |
| `/sources` не работает | `make sync-skills` — пересинхронизировать skills в OpenClaw |
| `sources.json` не обновляется | Сканер пишет stats только через bind mount — проверь `docker compose ps scanner` |
| Cron не запускается | `openclaw cron list` и `openclaw cron status` |

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
