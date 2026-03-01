---
name: source-validator
description: >
  Manages job vacancy sources. Handle these commands:
  /sources — show all sources grouped by status with stats, sorted by priority
  /source N — detailed info on source N from the last /sources list
  /add_source {url|@channel} — add a new web source or Telegram channel (auto-evaluates priority)
  /remove_source {N|name} — remove a source with confirmation
  /set_priority {N} {1-10} — manually override priority for source N
  Also triggers on: "approve source", "approve all", "blacklist", "reject source",
  "source status", "приоритет источника", "список источников", "добавить источник",
  "удалить источник", "источники", "покажи источники", "сколько источников".
---

# Source Validator Skill

## Config Paths

```
SOURCES_FILE   = /home/oc/jora/scanner/config/sources.json
JOBSITES_FILE  = /home/oc/jora/scanner/config/jobSites.json
TG_SOURCES     = /home/oc/jora/scanner/config/tg_sources.json
BLACKLIST_FILE = /home/oc/jora/scanner/config/blacklist.json
```

## Source Statuses

| Status      | Meaning                                      |
|-------------|----------------------------------------------|
| `active`    | In scanner, being scanned every 30 min       |
| `pending`   | Discovered but not yet approved              |
| `rejected`  | User rejected (won't be re-suggested)        |
| `blacklisted` | Permanently excluded                       |
| `grey`      | Temporarily inactive (Full version)         |

---

## Command: /sources

Read `sources.json` and display grouped list. Format:

```
📡 Источники (23 total)

🌐 Web — активные (18), сортировка по приоритету:
 1. Greenhouse — QA Director ✅  aggregator  ⭐9
 2. Lever — Head of QA ✅  aggregator  ⭐9
 3. Revolut Careers ✅  vendor  ⭐8
 4. Stripe Jobs ✅  vendor  ⭐8
 5. EPAM Careers ✅  vendor  ⭐8
 6. JetBrains Jobs ✅  vendor  ⭐7
 ...

📱 Telegram — ожидают подтверждения (5):
19. @remote_qa_jobs ⏳  ⭐5
20. @qa_vacancies ⏳  ⭐5
21. @devjobs ⏳  ⭐4
22. @djinnijobs ⏳  ⭐5
23. @workintech ⏳  ⭐4

🚫 Чёрный список: 0

→ /source N — подробности
→ /add_source {url} — добавить
→ /remove_source N — удалить
→ Approve 19,20 — активировать TG каналы
```

Notes:
- Number sources sequentially for easy reference; show web active sorted by `priority` descending
- Store the last numbering in memory for /source N and /remove_source N lookups
- If `stats.total_vacancies_found > 0`, show it: `✅ 12 вак.`
- If `stats.consecutive_failures >= 3`, show `⚠️` warning
- Always show `⭐{priority}` next to each source name

---

## Command: /source N

Find source by number from last /sources output. Show full details:

```
📡 Revolut Careers (#3)

🌐 https://revolut.com/careers/?query=quality
Тип: vendor | Статус: ✅ active
Добавлен: 2026-02-27
Приоритет: ⭐ 8/10

📊 Статистика:
   Вакансий найдено: 0
   Последнее сканирование: —
   Последняя новая вакансия: —
   Ошибок подряд: 0

→ /remove_source 3 — удалить
→ /set_priority 3 {1-10} — изменить приоритет
```

---

## Command: /add_source {url_or_channel}

### Step 1 — Detect type
- Starts with `@` or `t.me/` → Telegram channel
- Starts with `http` → Web source
- Otherwise → ask user to clarify

### Step 2a — Web source: Initial Probe

Perform a full probe to determine the scan method before asking user to approve.

**Probe script:**
```python
import urllib.request, json, sys

CANDIDATE_SELECTORS = [
    ".job-title", ".vacancy-title", ".opening a", "h2[itemprop='title']",
    ".position-title", ".posting-title h5", ".search-result__item-name",
    "[data-id='job-title']", ".profile", ".vacancy-card__title",
    "h3 a", ".job-card-title", ".job-position-title", ".sc-jMGMwj",
]

SPA_MARKERS = [
    "__NEXT_DATA__", "_next/static", "data-reactroot",  # React/Next
    "__nuxt", "__vue",                                    # Vue/Nuxt
    "ng-version", "ng-app",                              # Angular
    "window.__INITIAL_STATE__", "window.__APP_STATE__",  # Generic SPA
]

url = "<user_provided_url>"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

try:
    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
    http_status = 200
except urllib.error.HTTPError as e:
    http_status = e.code
    html = ""
except Exception as e:
    http_status = 0
    html = ""
```

**Determine `scan_method` and `selector`:**

```
A. http_status == 404 or http_status == 0:
   → scan_method = "unknown"
   → Ошибка — сообщи пользователю, НЕ добавляй источник
   → "❌ URL недоступен (HTTP {status}). Проверьте адрес."

B. http_status in [403, 429, 503] (bot protection):
   → scan_method = "fakebrowser"
   → antiBotCheck = True
   → selector = первый из CANDIDATE_SELECTORS (.job-title) как fallback
   → Предупредить: "Сайт блокирует HTTP-запросы — будет использован FakeBrowser"

C. http_status == 200:
   → Проверить SPA_MARKERS в html
   → Попробовать каждый CANDIDATE_SELECTORS через BeautifulSoup (or simple regex/count)
   → best_selector = selector с максимальным количеством matches (> 0)

   C1. best_selector найден (matches > 0):
       → scan_method = "axios"
       → antiBotCheck = False
       → selector = best_selector

   C2. best_selector не найден (все 0) ИЛИ найдены SPA_MARKERS:
       → scan_method = "fakebrowser"
       → antiBotCheck = True
       → selector = лучший candidate из простого анализа структуры страницы,
                   или ".job-title" как fallback
```

Classify as **vendor** (single company career page) or **aggregator** (multiple companies).

### Priority Evaluation

After probe, evaluate the source relevance on a scale **1–10** for "Head of QA / QA Director" roles:

| Score | Criteria |
|-------|----------|
| 9–10  | ATS aggregator (Greenhouse/Lever) with exact "head of qa" / "qa director" query |
| 8     | Top-tier tech vendor (well-known company, >5k employees) with QA-targeted URL |
| 7     | Solid job board / aggregator covering QA leadership roles |
| 6     | Mid-tier vendor career page; UA/RU market boards with senior filter |
| 5     | Niche board, remote-only with limited senior coverage; TG channel pending validation |
| 3–4   | Broad aggregator, low signal-to-noise for leadership roles |
| 1–2   | Unlikely to post Head of QA / QA Director roles |

Scoring factors:
- URL search params contain `head+of+qa` or `qa+director` → +2
- `source_type: aggregator` with cross-company coverage → +1
- Well-known company (Stripe, Google, Revolut etc.) → +1
- Niche domain (gaming, crypto-only) → -1
- TG channel, not yet validated → score = 5

**Present to user** (адаптируй под результат probe):

```
# Если axios работает:
📡 Новый источник обнаружен

🌐 Habr Career
   URL: career.habr.com/vacancies?q=head+of+qa
   Тип: Aggregator
   Метод: axios ✅  (найдено 25 вакансий)
   Селектор: .vacancy-card__title
   Приоритет: ⭐ 7/10 — агрегатор RU-рынка, точный запрос "head of qa"

→ Approve — добавить
→ Cancel — отменить

# Если FakeBrowser (JS-rendered):
📡 Новый источник обнаружен

🌐 Miro Careers
   URL: miro.com/careers/open-positions/
   Тип: Vendor (Miro)
   Метод: FakeBrowser ⚙️  (JS-rendered сайт)
   Селектор: .position-title (ожидаемый — проверится при сканировании)
   Приоритет: ⭐ 6/10 — вендор, известная компания

→ Approve — добавить
→ Cancel — отменить

# Если заблокирован (403):
📡 Новый источник обнаружен

🌐 Revolut Careers
   URL: revolut.com/careers/
   Тип: Vendor (Revolut)
   Метод: FakeBrowser ⚙️  (сайт блокирует HTTP-запросы)
   Селектор: .job-title (fallback — проверится при сканировании)
   Приоритет: ⭐ 8/10 — крупный fintech-вендор

→ Approve — добавить
→ Cancel — отменить
```

### Step 2b — Telegram channel
Check accessibility via public t.me URL. Note subscriber count if visible.

Priority for TG channels: default **5**. Increase to 6 if channel has >5k subscribers and posts QA leadership roles regularly; decrease to 4 if broad/generic.

Present to user:
```
📡 TG-канал

📱 QA Jobs Remote (@qa_jobs_remote)
   Тип: Aggregator
   Язык: предположительно EN
   Приоритет: ⭐ 5/10 — ожидает валидации

→ Approve — добавить в мониторинг
→ Cancel — отменить
```

### Step 3 — After user approves

**Generate id** from url/channel name: `web_{company}_{slug}` or `tg_{channel}`.

**Update sources.json** — add entry with status `active`:
```python
import json, datetime

sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
sources.append({
    "id": new_id,
    "type": "web",  # or "telegram"
    "name": name,
    "url": url,
    "status": "active",
    "added_date": datetime.date.today().isoformat(),
    "priority": priority,  # 1-10, evaluated during probe
    "config": {
        "jobTitleSelector": selector,
        "antiBotCheck": scan_method == "fakebrowser",
        "scan_method": scan_method,  # "axios" | "fakebrowser" | "unknown"
    },
    "enrichment": {"source_type": source_type, "company": company},
    "stats": {"total_vacancies_found": 0, "last_scan": None, "last_new_vacancy": None, "consecutive_failures": 0}
})
open('/home/oc/jora/scanner/config/sources.json', 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
```

**Regenerate jobSites.json** (web only, active only, sorted by priority desc) and tg_sources.json (TG only, active only):
```python
import json

sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))

web_active = sorted(
    [{"name": s["name"], "url": s["url"],
      "jobTitleSelector": s["config"]["jobTitleSelector"],
      "antiBotCheck": s["config"].get("antiBotCheck", False),
      "scan_method": s["config"].get("scan_method", "axios"),
      "priority": s.get("priority", 5)}
     for s in sources if s["type"] == "web" and s["status"] == "active"],
    key=lambda x: x["priority"], reverse=True
)
open('/home/oc/jora/scanner/config/jobSites.json', 'w').write(json.dumps(web_active, indent=2, ensure_ascii=False))

tg_active = [
    {"id": s["id"], "type": "telegram_public", "name": s["name"],
     "channel": s["channel"], "url": s["url"], "status": "active",
     "priority": s.get("priority", 5)}
    for s in sources if s["type"] == "telegram" and s["status"] == "active"
]
open('/home/oc/jora/scanner/config/tg_sources.json', 'w').write(json.dumps(tg_active, indent=2, ensure_ascii=False))
```

**Confirm to user** and show restart hint:
```
✅ Bolt Careers добавлен в сканирование

Конфиг обновлён. Изменения применятся автоматически на следующем цикле сканирования (~30 мин).

Для немедленного применения:
  cd /home/oc/jora/infrastructure && sudo make restart-scanner
```

---

## Command: /remove_source {N|name}

1. Find source by number (from last /sources list) or fuzzy name match
2. Show details and ask confirmation:

```
🗑 Удалить источник?

🌐 Bolt Careers
   URL: bolt.eu/en/careers/positions/
   Добавлен: 2026-02-27
   Найдено вакансий: 5

→ Confirm — удалить
→ Blacklist — удалить + занести в чёрный список
→ Cancel — отменить
```

3. After confirmation:

**Update sources.json** — set status to `removed` or `blacklisted`:
```python
import json, datetime

sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
for s in sources:
    if s["id"] == target_id:
        s["status"] = "removed"  # or "blacklisted"
        break
open('/home/oc/jora/scanner/config/sources.json', 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
```

If blacklisted, also update blacklist.json:
```python
import json, datetime

bl = json.load(open('/home/oc/jora/scanner/config/blacklist.json'))
bl.append({"id": target_id, "url": url, "reason": "User blacklisted", "date": datetime.date.today().isoformat()})
open('/home/oc/jora/scanner/config/blacklist.json', 'w').write(json.dumps(bl, indent=2, ensure_ascii=False))
```

**Regenerate jobSites.json / tg_sources.json** (same as in /add_source).

**Confirm**:
```
✅ Bolt Careers удалён из сканирования

Конфиг обновлён. Изменения применятся на следующем цикле сканирования (~30 мин).
```

---

## Command: /set_priority {N} {1-10}

Override the priority score for a source.

1. Find source by number from last /sources list
2. Validate value is integer 1–10
3. Update `sources.json`:

```python
import json

sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
for s in sources:
    if s["id"] == target_id:
        s["priority"] = new_priority
        break
open('/home/oc/jora/scanner/config/sources.json', 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
```

4. Regenerate jobSites.json with new priority order (use standard regeneration snippet).
5. Confirm:

```
✅ Приоритет Revolut Careers обновлён: ⭐ 8/10 → ⭐ 9/10

Порядок сканирования обновится на следующем цикле (~30 мин).
```

---

## Approval Workflow (from source-discovery)

When user sends "Approve all" or "Approve 1,2,3":

1. Find pending sources by number
2. Set status → `active` in sources.json
3. Regenerate jobSites.json / tg_sources.json
4. Confirm: "✅ Добавлено N источников в сканирование"

When user sends "Blacklist 5":
1. Set status → `blacklisted`
2. Add to blacklist.json
3. Confirm: "🚫 Источник добавлен в чёрный список"

---

## Regenerate Scanner Configs

Always regenerate **both** files after any status change. jobSites.json is sorted by `priority` descending so the scanner processes high-priority sources first.

```python
import json

sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))

web = sorted(
    [{"name": s["name"], "url": s["url"],
      "jobTitleSelector": s["config"]["jobTitleSelector"],
      "antiBotCheck": s["config"].get("antiBotCheck", False),
      "scan_method": s["config"].get("scan_method", "axios"),
      "priority": s.get("priority", 5)}
     for s in sources if s["type"] == "web" and s["status"] == "active"],
    key=lambda x: x["priority"], reverse=True
)

tg = [{"id": s["id"], "type": "telegram_public", "name": s["name"],
       "channel": s.get("channel", ""), "url": s["url"], "status": "active",
       "priority": s.get("priority", 5)}
      for s in sources if s["type"] == "telegram" and s["status"] == "active"]

open('/home/oc/jora/scanner/config/jobSites.json', 'w').write(json.dumps(web, indent=2, ensure_ascii=False))
open('/home/oc/jora/scanner/config/tg_sources.json', 'w').write(json.dumps(tg, indent=2, ensure_ascii=False))
print(f"Regenerated: {len(web)} web + {len(tg)} TG sources")
```

---

## Stats Update

When a new vacancy notification arrives mentioning a source, update its stats:

```python
import json, datetime

sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
for s in sources:
    if s["name"] == source_name or s["url"] in vacancy_url:
        s["stats"]["total_vacancies_found"] += 1
        s["stats"]["last_new_vacancy"] = datetime.date.today().isoformat()
        s["stats"]["consecutive_failures"] = 0
        break
open('/home/oc/jora/scanner/config/sources.json', 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
```

---

## Evening Health Check (cron: daily 18:00)

Triggered automatically by cron. Checks `sources.json` stats written by the scanner.
Do NOT make HTTP requests — use stats already recorded by the scanner.

### Grey list criteria (move source from `active` → `grey`)

| Condition | Threshold | Reason |
|-----------|-----------|--------|
| `last_new_vacancy` is null AND `last_scan` older than 30 days | — | Scanned but never found anything |
| `last_new_vacancy` older than 30 days | 30 days | No relevant vacancies lately |
| `consecutive_failures` | >= 3 | Technical failures |

Note: if `last_scan` is null — source not yet scanned, skip it (scanner will do deep scan on next cycle).

### Health check script

```python
import json, datetime

SOURCES = '/home/oc/jora/scanner/config/sources.json'
sources = json.load(open(SOURCES))
today = datetime.date.today()
cutoff_30d = today - datetime.timedelta(days=30)

to_grey = []
ok = []

for s in sources:
    if s['status'] != 'active':
        continue
    stats = s.get('stats', {})
    last_scan = stats.get('last_scan')
    last_new = stats.get('last_new_vacancy')
    failures = stats.get('consecutive_failures', 0)

    # Not yet scanned — skip, scanner will do deep scan
    if not last_scan:
        continue

    last_scan_date = datetime.date.fromisoformat(last_scan[:10])
    last_new_date = datetime.date.fromisoformat(last_new[:10]) if last_new else None

    reason = None
    if failures >= 3:
        reason = f'технические ошибки подряд: {failures}'
    elif last_new_date is None and last_scan_date < cutoff_30d:
        reason = 'сканируется >30 дней, релевантных вакансий не найдено'
    elif last_new_date and last_new_date < cutoff_30d:
        reason = f'последняя вакансия {(today - last_new_date).days} дней назад'

    if reason:
        to_grey.append((s, reason))
    else:
        ok.append(s)

# Move to grey list
if to_grey:
    for s, reason in to_grey:
        s['status'] = 'grey'
        s['grey_since'] = today.isoformat()
        s['grey_reason'] = reason

    # Regenerate scanner configs (exclude grey sources), sorted by priority desc
    web = sorted(
        [{"name": s["name"], "url": s["url"],
          "jobTitleSelector": s["config"]["jobTitleSelector"],
          "antiBotCheck": s["config"].get("antiBotCheck", False),
          "scan_method": s["config"].get("scan_method", "axios"),
          "priority": s.get("priority", 5)}
         for s in sources if s["type"] == "web" and s["status"] == "active"],
        key=lambda x: x["priority"], reverse=True
    )
    tg = [{"id": s["id"], "type": "telegram_public", "name": s["name"],
           "channel": s.get("channel", ""), "url": s["url"], "status": "active",
           "priority": s.get("priority", 5)}
          for s in sources if s["type"] == "telegram" and s["status"] == "active"]

    open(SOURCES, 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
    open('/home/oc/jora/scanner/config/jobSites.json', 'w').write(json.dumps(web, indent=2, ensure_ascii=False))
    open('/home/oc/jora/scanner/config/tg_sources.json', 'w').write(json.dumps(tg, indent=2, ensure_ascii=False))

print(json.dumps({
    "ok": len(ok),
    "moved_to_grey": [{"name": s["name"], "reason": r} for s, r in to_grey]
}))
```

### Report to send in Telegram

```
🔍 Вечерняя проверка источников — {date}

✅ Активных и здоровых: {ok_count}
⏸ Переведено в серый список: {grey_count}

1. 🌐 InGameJob
   Причина: сканируется >30 дней, релевантных вакансий не найдено
2. 🌐 old-board.com
   Причина: технические ошибки подряд: 4

Серый список перепроверяется еженедельно.
После 180 дней — чёрный список.
```

If nothing moved to grey — send brief confirmation:
```
✅ Проверка источников — {date}: все {N} активных источников в норме.
```

---

## Weekly Grey List Recheck (cron: every Sunday 10:00)

Triggered automatically by cron. For each grey source:
1. Check if 180+ days since `grey_since` → move to **blacklist**
2. For the rest: do a quick HTTP fetch to see if site is alive and has listings
3. If listings found with keyword match → **restore to active**

### Recheck script

```python
import json, datetime, urllib.request

SOURCES = '/home/oc/jora/scanner/config/sources.json'
BLACKLIST = '/home/oc/jora/scanner/config/blacklist.json'

sources = json.load(open(SOURCES))
blacklist = json.load(open(BLACKLIST))
today = datetime.date.today()
cutoff_180d = today - datetime.timedelta(days=180)

keywords_raw = json.load(open('/home/oc/jora/scanner/config/default.json')).get('JOB_KEYWORDS', [])
keywords = [k.lower() for k in keywords_raw]

restored = []
blacklisted = []
still_grey = []

for s in sources:
    if s['status'] != 'grey':
        continue

    grey_since = datetime.date.fromisoformat(s.get('grey_since', today.isoformat()))

    # 180 days elapsed → blacklist
    if grey_since <= cutoff_180d:
        s['status'] = 'blacklisted'
        blacklist.append({
            "id": s["id"], "url": s["url"],
            "reason": f"Grey list 180+ days (since {s['grey_since']}): {s.get('grey_reason','')}",
            "date": today.isoformat()
        })
        blacklisted.append(s["name"])
        continue

    # Try to fetch and find relevant vacancies
    found_vacancy = False
    if s['type'] == 'web':
        try:
            req = urllib.request.Request(s['url'], headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore').lower()
            if any(kw in html for kw in keywords):
                found_vacancy = True
        except Exception:
            pass

    if found_vacancy:
        s['status'] = 'active'
        s.pop('grey_since', None)
        s.pop('grey_reason', None)
        s['stats']['consecutive_failures'] = 0
        restored.append(s["name"])
    else:
        still_grey.append(s["name"])

# Save
open(SOURCES, 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
open(BLACKLIST, 'w').write(json.dumps(blacklist, indent=2, ensure_ascii=False))

# Regenerate scanner configs, sorted by priority desc
web = sorted(
    [{"name": s["name"], "url": s["url"],
      "jobTitleSelector": s["config"]["jobTitleSelector"],
      "antiBotCheck": s["config"].get("antiBotCheck", False),
      "priority": s.get("priority", 5)}
     for s in sources if s["type"] == "web" and s["status"] == "active"],
    key=lambda x: x["priority"], reverse=True
)
tg = [{"id": s["id"], "type": "telegram_public", "name": s["name"],
       "channel": s.get("channel", ""), "url": s["url"], "status": "active",
       "priority": s.get("priority", 5)}
      for s in sources if s["type"] == "telegram" and s["status"] == "active"]
open('/home/oc/jora/scanner/config/jobSites.json', 'w').write(json.dumps(web, indent=2, ensure_ascii=False))
open('/home/oc/jora/scanner/config/tg_sources.json', 'w').write(json.dumps(tg, indent=2, ensure_ascii=False))

print(json.dumps({
    "restored": restored,
    "blacklisted": blacklisted,
    "still_grey": still_grey
}))
```

### Report to send in Telegram

```
🔄 Еженедельная перепроверка серого списка — {date}

✅ Восстановлены в активные (нашлись вакансии):
   - Habr Career

🚫 Переведены в чёрный список (180+ дней):
   - old-board.com (с 2025-09-03)

⏸ Остаются в сером списке: 2
   - InGameJob (28 дней, из 180)
   - WeWorkRemotely (15 дней, из 180)
```

If grey list is empty:
```
🔄 Серый список — {date}: пуст, проверять нечего.
```
