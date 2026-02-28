# 🎯 OpenClaw Job Hunter Agent v3 — POC

## Самообучающийся агент поиска работы: Global Head of QA
## Деплой на Ubuntu VPS

---

## Концепция

Этот агент работает как **персональный рекрутер**, который:

1. **Расширяет ключевые слова** — вы говорите "Head of QA", агент подбирает 25+ вариаций: "QA Director", "VP Quality Engineering", "Head of Quality Assurance" и т.д.
2. **Сам находит источники вакансий** — career-страницы, агрегаторы, TG-каналы — и валидирует их
3. **Присылает источники на согласование** — вы контролируете, где агент ищет
4. **Каждые 30 минут сканирует одобренные сайты** через job-scanner-tg-notification
5. **Обогащает каждую вакансию** данными о компании и выявляет дубликаты
6. **Готовит пакет документов** — досье, резюме, cover letter — по команде
7. **[Архитектурно]** Управляет серым списком мёртвых источников, автоматически откликается

**Ключевой принцип: агент НИЧЕГО не делает без вашего одобрения.**

---

## Архитектура

### Разделение ответственности

| Что | Кто делает | Технология |
|-----|-----------|-----------|
| Расширение ключевых слов | **keyword-expander** (OpenClaw skill) | Claude AI |
| Поиск источников | **source-discovery** (OpenClaw skill) | Claude AI + web search |
| Одобрение источников | **source-validator** (OpenClaw skill) | JSON configs + TG |
| Сканирование сайтов | **job-scanner-tg** (Docker) | Node.js + Cheerio + Puppeteer |
| Обогащение + дедупликация | **enrichment-svc** (Docker) | Node.js + MongoDB |
| Генерация документов | **doc-generator** (OpenClaw skill) | Claude AI + PDF |
| Трекинг и отчёты | **job-coordinator** (OpenClaw skill) | Claude AI + MongoDB |
| Хранение данных | **MongoDB** (Docker) | MongoDB 7 |

### Потоки данных

```
ПОТОК 1: Настройка (один раз + обновления)
──────────────────────────────────────────

  "Head of QA" ──▶ keyword-expander ──▶ 25 keywords ──▶ config/default.json
                                              │                    │
                                              ▼                    ▼
                                    source-discovery ──▶ jobSites.json
                                              │          tg_sources.json
                                              ▼
                                    source-validator ──▶ Одобрение → конфиг сканера


ПОТОК 2: Сканирование (каждые 30 мин, автоматически)
─────────────────────────────────────────────────────

  jobSites.json ──▶ job-scanner-tg ──▶ MongoDB: new vacancy
                                              │
                                     enrichment-svc (poll 60s)
                                              │
                                     ┌────────┴────────┐
                                     │ Fuzzy dedup      │
                                     │ Company lookup   │
                                     │ Relevance score  │
                                     └────────┬────────┘
                                              │
                                              ▼
                                     TG: 🏢 Вакансия + справка + score


ПОТОК 3: Документы (по команде)
───────────────────────────────

  /docs 3 ──▶ doc-generator ──▶ Deep research (Layer 3)
                                       │
                                ┌──────┴──────┐
                                │ Resume.pdf   │
                                │ CoverLetter  │
                                │ Dossier.md   │
                                └──────┬──────┘
                                       ▼
                                TG: 📎 файлы на согласование
```

### Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose на VPS                        │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  job-scanner-tg   │  │   MongoDB     │  │  enrichment-svc  │   │
│  │  (Node.js)        │  │              │  │  (Node.js)       │   │
│  │                    │  │  vacancies   │  │                  │   │
│  │  Сканирует сайты   │─▶│  sources     │◀─│  Fuzzy dedup     │   │
│  │  Фильтрует keywords│  │  cache       │  │  Company lookup  │   │
│  │  Шлёт в TG         │  │  config      │  │  Scoring         │   │
│  │  Anti-bot bypass   │  │              │  │  Enhanced TG     │   │
│  └──────────────────┘  └──────────────┘  └──────────────────┘   │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  [Full] Userbot   │  │ [Full] Applier   │                     │
│  │  Закрытые TG      │  │ Headless apply   │                     │
│  └──────────────────┘  └──────────────────┘                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Telegram Bot API
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OpenClaw Agent                              │
│                                                                   │
│  keyword-expander  → "Head of QA" → 25 вариаций                 │
│  source-discovery  → находит сайты + TG каналы                   │
│  source-validator  → одобрение / blacklist / grey list           │
│  doc-generator     → резюме + CL + досье (по команде)           │
│  job-coordinator   → трекинг + follow-up + отчёты               │
│  [Full] auto-applier → автоматический отклик                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Use Cases

### UC-0: Расширение ключевых слов ✅ POC
| | |
|---|---|
| **Описание** | Вы даёте seed-роль, агент генерирует полный список вариаций |
| **Вход** | "Head of QA" |
| **Выход** | 25+ ключевых слов, категоризированных по точности |
| **Действие** | После одобрения → обновляет `JOB_KEYWORDS` в конфиге сканера |

### UC-1: Мульти-источники ✅ POC (web + public TG)
| | |
|---|---|
| **POC** | Web career pages + aggregators + public TG каналы |
| **Full** | + закрытые TG группы, Facebook, LinkedIn |

### UC-2: Жизненный цикл источника (Grey List) — архитектурно
| | |
|---|---|
| **Агрегатор → серый** | 180 дней без релевантных вакансий |
| **Вендор → серый** | 0 вакансий за всё время |
| **Серый → переприверка** | Раз в неделю |
| **Серый → исключён** | Нет обновлений > N дней совсем |

### UC-3: Обнаружение дубликатов ✅ POC
| | |
|---|---|
| **Логика** | Fuzzy-matching: company + title, порог ≥ 0.85 |
| **Действие** | TG уведомление: "Возможный дубликат" |

### UC-4: Обогащение вакансии ✅ POC (Layer 2)
| | |
|---|---|
| **Слой 1** | Мета-данные источника (при добавлении) |
| **Слой 2** | Краткая справка о компании (автоматически) ✅ |
| **Слой 3** | Глубокий ресёрч (по команде, при генерации docs) ✅ |

### UC-5: Генерация документов ✅ POC
| | |
|---|---|
| **Вход** | `/docs {id}` в TG |
| **Выход** | Resume PDF + Cover Letter PDF + Dossier |

### UC-6: Автоматический отклик — архитектурно
| | |
|---|---|
| **POC** | Нет |
| **Full** | Greenhouse, Lever, Workday, BambooHR |

### UC-7: Управление источниками через TG-бот ✅ POC
| | |
|---|---|
| **Описание** | Пользователь добавляет и удаляет источники прямо через Telegram-бот, без правки конфигов вручную |
| **Добавление** | `/add_source https://company.com/careers` — агент сам определяет тип, CSS-селектор, обогащает мета-данными, просит подтверждение |
| **Добавление TG** | `/add_source @channel_name` — агент проверяет канал, оценивает релевантность |
| **Удаление** | `/remove_source {id или имя}` — агент показывает источник, просит подтверждение, удаляет из конфига сканера |
| **Список** | `/sources` — показать все активные источники с их статусом |
| **Детали** | `/source {id}` — подробная информация: статус, последнее сканирование, найденные вакансии |
| **Принцип** | Любое изменение → подтверждение пользователем → обновление конфига → рестарт сканера |

#### Подробный flow: добавление источника

```
Вы: /add_source https://revolut.com/careers

Агент:
1. Определяет тип → web (vendor career page)
2. Сканирует страницу → находит CSS-селектор для job titles
3. Тестирует — находит N job listings
4. Обогащает: company = Revolut, type = vendor

Ответ:
📡 Новый источник обнаружен

🌐 Revolut Careers
   URL: https://revolut.com/careers
   Тип: Vendor (career page)
   Селектор: .sc-jMGMwj (найдено 47 вакансий)
   Компания: Revolut

→ "Approve" — добавить в сканирование
→ "Approve + scan now" — добавить и сразу просканировать
→ "Cancel" — отменить
```

```
Вы: /add_source @qa_jobs_remote

Агент:
1. Проверяет канал → публичный, 8.4k подписчиков
2. Сканирует последние 50 постов → 3 релевантных
3. Оценивает: aggregator, relevance 3/5

Ответ:
📡 TG-канал обнаружен

📱 QA Jobs Remote (@qa_jobs_remote)
   Подписчиков: 8,400
   Тип: Aggregator
   Релевантных постов (30 дн): 3
   Язык: EN

→ "Approve" — добавить в мониторинг
→ "Cancel" — отменить
```

#### Подробный flow: удаление источника

```
Вы: /remove_source Revolut

Агент:
🗑 Удалить источник?

🌐 Revolut Careers
   Активен с: 2026-02-27
   Найдено вакансий: 12
   Последнее сканирование: 2 часа назад

→ "Confirm" — удалить из сканирования
→ "Blacklist" — удалить + добавить в чёрный список
→ "Cancel" — отменить
```

#### Подробный flow: список источников

```
Вы: /sources

📡 Активные источники (23)

🌐 Web (15):
 1. Revolut Careers ✅ 12 вакансий
 2. Stripe Jobs ✅ 8 вакансий
 3. RemoteOK QA ✅ 34 вакансии
 ...

📱 Telegram (5):
 16. @qa_jobs_remote ✅ 3 вакансии
 17. @djinnijobs ✅ 7 вакансий
 ...

⏸ Grey list (2):
 21. old-board.com — 180д без релевантных
 22. @dead_channel — нет постов 45д

🚫 Blacklisted (1):
 23. jobrocket.ru

→ /source {номер} — подробности
→ /add_source {url} — добавить
→ /remove_source {номер} — удалить
```

### UC-8: Поиск рефералов и рекрутеров ✅ POC
| | |
|---|---|
| **Описание** | При подготовке отклика агент находит людей, которые могут занести резюме рекрутеру (рефералы), и наиболее подходящих рекрутеров в компании |
| **Рефералы** | Поиск 3-5 специалистов своего грейда (Head/Director/VP of QA/Engineering) в целевой компании, которые могут передать резюме через внутренний реферальный процесс |
| **Рекрутеры** | Поиск 3 наиболее релевантных рекрутеров: Technical Recruiter, Engineering Recruiter, Talent Acquisition — кто нанимает на QA/Engineering leadership позиции |
| **Триггер** | Автоматически при `/docs {id}` или отдельно по `/referrals {id}` |
| **Выход** | Список с именами, должностями, LinkedIn URL, рекомендацией кому писать первому и шаблоном сообщения |

#### Логика поиска рефералов

```
Вход: компания = Revolut, роль = Global Head of QA

1. Поиск в LinkedIn (через web search):
   "Revolut" + ("Head of QA" OR "QA Director" OR "VP Engineering"
   OR "Director of Engineering" OR "Head of Testing")

2. Фильтрация:
   - Текущий сотрудник компании (не бывший)
   - Грейд: Director / Head / VP / Senior Director
   - Функция: QA, Engineering, Testing, Platform
   - Не прямой конкурент на ту же роль

3. Ранжирование:
   - Ближайший по функции (QA > Eng > Platform)
   - Ближайший по грейду (тот же > на 1 выше)
   - Наличие общих контактов / сообществ
```

#### Логика поиска рекрутеров

```
Вход: компания = Revolut

1. Поиск в LinkedIn:
   "Revolut" + ("Technical Recruiter" OR "Engineering Recruiter"
   OR "Talent Acquisition" OR "Recruiting Lead")

2. Фильтрация:
   - Текущий сотрудник
   - Нанимает на Engineering / QA / Tech Leadership

3. Ранжирование:
   - Специализация (Engineering > General)
   - Уровень (Senior Recruiter > Junior)
   - Активность (недавние посты о найме)
```

#### Выход в TG

```
Вы: /docs 3  (или /referrals 3)

👥 Referrals & Recruiters: Revolut

🤝 Рефералы (могут занести резюме):
1. ⭐ Anna Schmidt — Director of Engineering
   🔗 linkedin.com/in/anna-schmidt
   💡 Ближайший по функции, тот же грейд
   📝 Рекомендация: написать первой

2. Ivan Petrov — Head of Platform QA
   🔗 linkedin.com/in/ivan-petrov
   💡 QA функция, может знать нанимающего менеджера

3. Sarah Chen — VP Engineering, Payments
   🔗 linkedin.com/in/sarah-chen
   💡 Грейд выше, может дать сильную рекомендацию

🎯 Рекрутеры:
1. ⭐ James Wilson — Senior Technical Recruiter
   🔗 linkedin.com/in/james-wilson
   💡 Нанимает Engineering Leadership, свежие посты
   📝 Рекомендация: основной контакт

2. Maria López — Engineering Talent Partner
   🔗 linkedin.com/in/maria-lopez
   💡 Специализация: QA & Testing

3. Tom Baker — Talent Acquisition Lead
   🔗 linkedin.com/in/tom-baker
   💡 Менеджер TA команды, для эскалации

→ /outreach 3 — сгенерировать сообщения для каждого
```

#### Генерация outreach-сообщений (по команде)

```
Вы: /outreach 3

✉️ Outreach: Revolut — Global Head of QA

📨 Для реферала (Anna Schmidt):
───────────────────────
Hi Anna,

I noticed you're leading engineering at Revolut —
impressive work on the payments expansion.

I'm exploring the Global Head of QA role and
believe my experience scaling QA orgs in fintech
(most recently at B2Broker) could be a strong fit.

Would you be open to a brief chat or passing
along my profile internally?

Best, Pavel
───────────────────────

📨 Для рекрутера (James Wilson):
───────────────────────
Hi James,

I saw you're hiring for engineering leadership
at Revolut. I'm a QA leader with 23 years'
experience including scaling QA at fintech orgs
and leading AI-driven quality transformation.

I'd love to discuss the Global Head of QA role.
Happy to share my CV — would that work?

Best, Pavel
───────────────────────

→ "Approve" / "Edit referral msg: ..." / "Edit recruiter msg: ..."
```

---

## Структура файлов POC

```
~/job-hunter/                              # Корневая директория проекта
│
├── docker-compose.yml                     # Объединённый compose
├── .env                                   # Секреты (из .env.template)
├── .env.template                          # Шаблон переменных
│
├── job-scanner-tg-notification/           # git clone — сканер
│   ├── config/
│   │   ├── default.json                   # ← keywords + TG config
│   │   └── jobSites.json                  # ← web sources
│   ├── index.js
│   ├── jobTitleParser.js
│   ├── Dockerfile
│   └── docker-compose.yml                 # НЕ используется, берём корневой
│
├── enrichment-svc/                        # Сервис обогащения
│   ├── config/
│   │   └── default.json
│   ├── index.js
│   ├── package.json
│   └── Dockerfile
│
├── scanner-config/                        # Конфиги для сканера (управляются OpenClaw)
│   ├── default.json                       # Keywords + TG settings
│   ├── jobSites.json                      # Web sources
│   └── tg_sources.json                    # TG channel sources
│
└── workspace/                             # Рабочие данные OpenClaw skills
    └── jobs/
        ├── keywords.json                  # Output keyword-expander
        ├── sources.json                   # All sources with metadata
        ├── blacklist.json                 # Blacklisted sources
        ├── grey_list_log.json             # [Full] Grey list history
        ├── master_resume.json             # Master resume template
        ├── candidate_profile.json         # Candidate preferences
        └── applications/                  # Generated docs per vacancy
            └── {vacancy_id}/
                ├── dossier.md
                ├── resume.pdf
                └── cover_letter.pdf

~/.openclaw/workspace/skills/              # OpenClaw skills
├── keyword-expander/
│   └── SKILL.md
├── source-discovery/
│   └── SKILL.md
├── source-validator/
│   └── SKILL.md
├── doc-generator/
│   └── SKILL.md
└── job-coordinator/
    └── SKILL.md
```

---

## Деплой POC: пошагово

### Требования

- **ОС**: Ubuntu 22.04 / 24.04 LTS
- **RAM**: 4 GB (Puppeteer + MongoDB)
- **Диск**: 30 GB+
- **Docker + Docker Compose**
- **Node.js 22**

### Шаг 1: Подготовка

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git build-essential python3 python3-pip

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Node.js 22
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

### Шаг 2: OpenClaw

```bash
curl -fsSL https://get.openclaw.ai | bash
# Визард: Anthropic → API key → Claude Sonnet → Telegram → daemon
```

### Шаг 3: Проект

```bash
mkdir -p ~/job-hunter && cd ~/job-hunter

# Клонируем сканер
git clone https://github.com/EgorBodnar/job-scanner-tg-notification.git

# Создаём enrichment-svc (из файлов POC)
mkdir -p enrichment-svc/config
# Скопируйте файлы из poc/enrichment-svc/

# Конфиги
mkdir -p scanner-config
# Скопируйте файлы из poc/scanner-config/

# Рабочее пространство
mkdir -p workspace/jobs/applications
# Скопируйте templates из poc/templates/

# Переменные окружения
cp .env.template .env
nano .env  # Заполните TG_BOT_TOKEN, TG_CHAT_ID, ANTHROPIC_API_KEY
```

### Шаг 4: Конфигурация сканера

```bash
# Подставляем keywords и TG настройки
cp scanner-config/default.json job-scanner-tg-notification/config/default.json
cp scanner-config/jobSites.json job-scanner-tg-notification/config/jobSites.json

# Отредактируйте TG токен и chat_id
nano job-scanner-tg-notification/config/default.json
```

### Шаг 5: Установка OpenClaw skills

```bash
# Скопируйте skills
cp -r poc/skills/* ~/.openclaw/workspace/skills/

# Включите в конфиге
nano ~/.openclaw/openclaw.json
```

```json
{
  "skills": {
    "entries": {
      "keyword-expander": { "enabled": true },
      "source-discovery": { "enabled": true },
      "source-validator": { "enabled": true },
      "doc-generator": { "enabled": true },
      "job-coordinator": { "enabled": true }
    }
  }
}
```

### Шаг 6: Запуск Docker-стека

```bash
cd ~/job-hunter
docker compose up -d

# Проверка
docker compose ps
docker compose logs -f
```

### Шаг 7: Запуск OpenClaw

```bash
openclaw gateway restart
openclaw skills list
openclaw doctor
```

### Шаг 8: Первый запуск

В Telegram боту:

> Ищи вакансии "Head of QA"

Агент:
1. **keyword-expander** → генерирует 25 вариаций → на одобрение
2. После одобрения → обновляет `config/default.json`
3. **source-discovery** → находит source → на одобрение
4. После одобрения → обновляет `jobSites.json`
5. `docker compose restart job-scanner`
6. Сканер начинает работу, вакансии → enrichment → TG

---

## Как это выглядит в Telegram

### 1. Расширение ключевых слов

```
🔑 Keyword Expansion: "Head of QA"

🎯 Точное совпадение (3):
   Head of QA
   Head of Quality Assurance
   Head of Quality Engineering

🔄 Близкие вариации (14):
   QA Director, Director of QA,
   Director of Quality Assurance,
   VP of QA, VP Quality Engineering,
   Head of Testing, Head of Quality, ...

🔭 Расширенные (8):
   Senior Director of QA, Global Head of QA,
   Chief Quality Officer, ...

❌ Исключены (уровень ниже):
   QA Manager, QA Lead, Senior QA Engineer

📊 Всего: 25 ключевых слов

→ "Approve" — сохранить
→ "Add: VP Test Engineering" — добавить
→ "Remove: Chief Quality Officer" — убрать
```

### 2. Обнаружение источников

```
📡 Source Discovery — Feb 27, 2026

✅ Рекомендую (5):
1. 🌐 Revolut Careers (5/5) — vendor
2. 🌐 RemoteOK QA (4/5) — агрегатор
3. 🌐 Greenhouse boards (4/5) — агрегатор
4. 📱 @qa_vacancies (3/5) — TG канал, RU
5. 📱 @remote_qa_jobs (3/5) — TG канал, EN

❌ Отклонены:
6. 📱 @qa_trainee — 0 senior ролей

→ "Approve all" / "Approve 1,2,3" / "Blacklist 6"
```

### 3. Сканер нашёл вакансию

```
🔍 New: Global Head of QA — Revolut
🔗 https://revolut.com/careers/...
Source: Revolut Careers
```

### 4. Обогащение (через 1 мин)

```
🏢 Revolut: Global Head of QA

📊 Relevance: 85/100
👥 8,000+ employees | Fintech
📍 HQ: London, UK
⭐ Glassdoor: 3.8/5
🔗 revolut.com/careers

→ /docs_rev_001 — подготовить документы
```

### 5. Дубликат

```
⚠️ Possible duplicate

"Head of Quality Assurance" — Revolut
📍 Source: LinkedIn Jobs
Похоже на: "Global Head of QA — Revolut" (89%)

→ /ignore — пропустить
→ /track — отслеживать отдельно
```

### 6. Управление источниками через бота

```
Вы: /add_source https://bolt.eu/en/careers/positions/

📡 Новый источник

🌐 Bolt Careers
   URL: bolt.eu/en/careers/positions/
   Тип: Vendor (career page)
   Селектор: .job-position-title (найдено 83 вакансии)
   Компания: Bolt

→ "Approve" — добавить в сканирование
→ "Approve + scan now" — добавить и просканировать
→ "Cancel" — отменить
```

```
Вы: /add_source @qa_remote_europe

📡 TG-канал

📱 QA Remote Europe (@qa_remote_europe)
   Подписчиков: 5,200
   Тип: Aggregator
   Релевантных постов (30 дн): 4
   Язык: EN

→ "Approve" / "Cancel"
```

```
Вы: /sources

📡 Активные источники (23)

🌐 Web (15):
 1. Revolut Careers ✅ 12 вакансий
 2. Stripe Jobs ✅ 8 вакансий
 3. Bolt Careers ✅ 5 вакансий
 ...

📱 Telegram (5):
 16. @qa_jobs_remote ✅ 3 вакансии
 17. @qa_remote_europe ✅ 4 вакансии
 ...

⏸ Grey list (2):  [архитектурно]
🚫 Blacklist (1): jobrocket.ru

→ /source {номер} — подробности
→ /add_source {url} — добавить
→ /remove_source {номер} — удалить
```

```
Вы: /remove_source 3

🗑 Удалить источник?

🌐 Bolt Careers
   Активен с: 2026-02-27
   Найдено вакансий: 5
   Последнее сканирование: 1 час назад

→ "Confirm" — удалить
→ "Blacklist" — удалить + чёрный список
→ "Cancel" — отменить
```

```
Вы: /source 1

📡 Revolut Careers (#1)

🌐 https://revolut.com/careers/?query=quality
Тип: Vendor | Статус: ✅ active
Добавлен: 2026-02-27
Селектор: .sc-jMGMwj

📊 Статистика:
   Вакансий найдено: 12
   Последнее сканирование: 35 мин назад
   Последняя новая вакансия: вчера

→ /remove_source 1 — удалить
```

### 7. Рефералы и рекрутеры

```
Вы: /docs 3

📦 Revolut: Global Head of QA

📋 Досье: 8,000+ сотр, $33B, экспансия на 40 рынков
📄 Резюме: акцент на масштабировании QA в финтехе
✉️ CL: угол — экспансия + качество на масштабе

👥 Рефералы (могут занести резюме):
1. ⭐ Anna Schmidt — Director of Engineering
   🔗 linkedin.com/in/anna-schmidt
   💡 Ближайший по функции, написать первой
2. Ivan Petrov — Head of Platform QA
   🔗 linkedin.com/in/ivan-petrov
3. Sarah Chen — VP Engineering, Payments
   🔗 linkedin.com/in/sarah-chen

🎯 Рекрутеры:
1. ⭐ James Wilson — Senior Technical Recruiter
   🔗 linkedin.com/in/james-wilson
   💡 Нанимает Eng Leadership
2. Maria López — Engineering Talent Partner
3. Tom Baker — Talent Acquisition Lead

📎 файлы прикреплены

→ "Approve" / "Edit resume: ..." / "Edit CL: ..."
→ /outreach 3 — сгенерировать сообщения
```

```
Вы: /outreach 3

✉️ Outreach: Revolut — Global Head of QA

📨 Реферал #1 (Anna Schmidt):
───────────────────────
Hi Anna, I noticed you're leading engineering
at Revolut — impressive growth to 40 markets.
I'm exploring the Global Head of QA role and
my experience scaling QA orgs in fintech could
be a strong fit. Would you be open to a brief
chat or passing along my profile internally?
Best, Pavel
───────────────────────

📨 Рекрутер #1 (James Wilson):
───────────────────────
Hi James, I saw you're hiring engineering
leadership at Revolut. I'm a QA leader with
23 years' experience including AI-driven
quality transformation in fintech. Happy to
share my CV for the Head of QA role — would
that work? Best, Pavel
───────────────────────

→ "Approve" / "Edit referral 1: ..."
→ "Edit recruiter 1: ..."
```

---

## Стоимость POC

| Компонент | Стоимость |
|-----------|-----------|
| VPS Ubuntu (Hetzner CX22, 4GB) | €5.85/мес |
| Anthropic API (Claude Sonnet) | $20-35/мес |
| MongoDB (self-hosted) | $0 |
| job-scanner-tg (open source) | $0 |
| **Итого** | **~€26-41/мес** |

---

## Roadmap

### ✅ POC v3.0
- [x] keyword-expander: seed role → 25+ keywords
- [x] source-discovery: web + public TG channels
- [x] source-validator: approve / blacklist
- [x] source management via TG: /add_source, /remove_source, /sources
- [x] job-scanner-tg: web scanning + TG notify
- [x] enrichment-svc: company brief + fuzzy dedup + scoring
- [x] doc-generator: resume + CL + dossier
- [x] referral & recruiter search: /referrals, /outreach
- [x] job-coordinator: tracking + reports

### 🔜 Full v4.0
- [ ] TG Userbot (Pyrogram) для закрытых групп
- [ ] Grey list + еженедельная переприверка
- [ ] Автоматическое исключение мёртвых источников
- [ ] Auto-applier (Greenhouse, Lever, Workday)
- [ ] Facebook / LinkedIn источники
- [ ] Платные API (Crunchbase Pro, LinkedIn Sales Nav)
- [ ] A/B тестирование Cover Letters
