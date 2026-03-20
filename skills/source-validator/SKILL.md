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
REGENERATE     = python3 /home/oc/jora/scanner/regenerate.py
```

## Source Statuses

| Status | Meaning |
|--------|---------|
| `active` | In scanner, scanned every 30 min |
| `pending` | Discovered, not yet approved |
| `rejected` | User rejected |
| `blacklisted` | Permanently excluded |
| `grey` | Temporarily inactive |

---

## Regenerate Scanner Configs

After ANY change to sources.json, always run:
```bash
python3 /home/oc/jora/scanner/regenerate.py
```
This rebuilds jobSites.json (web active, sorted by priority desc) and tg_sources.json (TG active).

---

## Command: /sources

Read sources.json, display grouped list:

```
📡 Источники (23 total)

🌐 Web — активные (18), по приоритету:
 1. Greenhouse — QA Director ✅  aggregator  ⭐9
 2. Lever — Head of QA ✅  aggregator  ⭐9
 ...

📱 Telegram — ожидают (5):
19. @remote_qa_jobs ⏳  ⭐5

🚫 Чёрный список: 0

→ /source N — подробности | /add_source {url} — добавить
```

Notes: number sequentially, store for /source N lookups, show `✅ N вак.` if found, `⚠️` if failures≥3.

---

## Command: /source N

```
📡 Revolut Careers (#3)
🌐 https://revolut.com/careers/?query=quality
Тип: vendor | Статус: ✅ active | Приоритет: ⭐ 8/10
📊 Вакансий: 0 | Ошибок подряд: 0

→ /remove_source 3 | /set_priority 3 {1-10}
```

---

## Command: /add_source {url_or_channel}

**Type detection:** `@` or `t.me/` → Telegram; `http` → Web.

### Web source probe

Run in bash:
```python
import urllib.request, json

CANDIDATE_SELECTORS = ['.job-title', '.vacancy-title', '.opening a', 'h2[itemprop="title"]',
    '.position-title', '.posting-title h5', '.search-result__item-name',
    '[data-id="job-title"]', '.profile', '.vacancy-card__title', 'h3 a',
    '.job-card-title', '.job-position-title', '.sc-jMGMwj']

SPA_MARKERS = ['__NEXT_DATA__', '_next/static', 'data-reactroot', '__nuxt', '__vue',
    'ng-version', 'ng-app', 'window.__INITIAL_STATE__']

url = "<user_provided_url>"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
    http_status = 200
except urllib.error.HTTPError as e:
    http_status = e.code; html = ""
except:
    http_status = 0; html = ""
```

**Decision:**
- 404/0 → error, don't add
- 403/429/503 → `scan_method=fakebrowser`, `antiBotCheck=True`
- 200 + SPA markers or no selector matches → `scan_method=fakebrowser`
- 200 + selector found → `scan_method=axios`, `antiBotCheck=False`

**Priority 1–10:** ATS aggregator with exact query=9–10; top-tier vendor=8; solid job board=7; mid-tier=6; TG pending=5; broad/low signal=3–4.

**Present to user:**
```
📡 Новый источник: {Name}
🌐 {url} | Тип: {vendor|aggregator}
Метод: {axios ✅ / FakeBrowser ⚙️} | Селектор: {selector} | Приоритет: ⭐{N}/10

→ Approve — добавить | Cancel — отменить
```

### After approval — add to sources.json:
```python
import json, datetime
sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
sources.append({"id": new_id, "type": "web", "name": name, "url": url,
    "status": "active", "added_date": datetime.date.today().isoformat(),
    "priority": priority,
    "config": {"jobTitleSelector": selector, "antiBotCheck": anti_bot, "scan_method": scan_method},
    "enrichment": {"source_type": source_type, "company": company},
    "stats": {"total_vacancies_found": 0, "last_scan": None, "last_new_vacancy": None, "consecutive_failures": 0}})
open('/home/oc/jora/scanner/config/sources.json', 'w').write(json.dumps(sources, indent=2, ensure_ascii=False))
```
Then run `python3 /home/oc/jora/scanner/regenerate.py`.

### Telegram channel
Default priority 5. Present similarly, then add to sources.json with type=telegram.

**Confirm:** `✅ {Name} добавлен. Изменения применятся на следующем цикле (~30 мин).`

---

## Command: /remove_source {N|name}

1. Find by number or fuzzy name, show confirmation:
```
🗑 Удалить? {Name} | {url} | Найдено вакансий: {N}
→ Confirm | Blacklist | Cancel
```

2. Set `status=removed` or `blacklisted` in sources.json. If blacklisted, append to blacklist.json.
3. Run `python3 /home/oc/jora/scanner/regenerate.py`.

---

## Command: /set_priority {N} {1-10}

Update `priority` in sources.json for target source, run regenerate.py.
Confirm: `✅ {Name}: ⭐{old} → ⭐{new}`

---

## Approval Workflow (from source-discovery)

- "Approve all" / "Approve 1,2,3" → set `status=active`, run regenerate.py
- "Blacklist 5" → set `status=blacklisted`, add to blacklist.json, run regenerate.py

---

## Evening Health Check (cron: daily 18:00)

Use stats in sources.json (written by scanner). Do NOT make HTTP requests.

**Grey list criteria (active → grey):**
- `consecutive_failures >= 3` → technical failures
- `last_scan` older than 30 days AND `last_new_vacancy` is null → never found anything
- `last_new_vacancy` older than 30 days → no relevant vacancies lately

Skip sources where `last_scan` is null (not yet scanned).

After moving to grey: run `python3 /home/oc/jora/scanner/regenerate.py`.

**Report:**
```
🔍 Вечерняя проверка — {date}
✅ Активных: {N} | ⏸ В серый: {N}
1. {name} — {reason}
```
If nothing moved: `✅ Проверка {date}: все {N} источников в норме.`

---

## Weekly Grey List Recheck (cron: Sunday 10:00)

For each grey source:
1. If `grey_since` ≥ 180 days → move to blacklist, add to blacklist.json
2. Else: HTTP fetch, check for keyword matches from default.json → if found, restore to active

After changes: run `python3 /home/oc/jora/scanner/regenerate.py`.

**Report:**
```
🔄 Перепроверка серого списка — {date}
✅ Восстановлены: {list}
🚫 В чёрный список (180+ дней): {list}
⏸ Остаются в сером: {N}
```
