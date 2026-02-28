---
name: source-validator
description: "Manages the lifecycle of job vacancy sources: processes user approvals/rejections, maintains blacklist and grey list, runs periodic health checks on sources. Use when the user approves or rejects a source, asks about source status, or when scheduled validation runs. Triggers on: 'approve source', 'blacklist', 'source status', 'grey list', or during weekly source health checks."
---

# Source Validator Skill

## Purpose

Manages the complete lifecycle of vacancy sources:
- Process user approvals and rejections
- Maintain blacklist (permanent exclusion)
- Maintain grey list (temporary exclusion with re-checks) [Architecture only in POC]
- Run health checks on existing sources

## Source States

```
                 ┌─────────────┐
    Discovered → │   pending    │
                 └──────┬──────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │  active   │ │ rejected │ │  blacklisted  │
        └────┬─────┘ └──────────┘ └──────────────┘
             │
             │ 180d no relevant (aggregator)
             │ 0 ever (vendor)
             ▼
        ┌──────────┐
        │   grey    │ ← [Full version]
        │           │   re-check weekly
        └────┬─────┘
             │
        ┌────┼────────┐
        ▼              ▼
   ┌──────────┐  ┌──────────┐
   │ restored  │  │ excluded  │
   │ (→active) │  │           │
   └──────────┘  └──────────┘
```

## Commands

### User Approval Commands (via TG)

| Command | Action |
|---------|--------|
| `Approve all` | Move all pending sources to active, update scanner config |
| `Approve 1,2,3` | Approve specific sources by number |
| `Reject 4` | Reject source (not added, forgotten) |
| `Blacklist 5` | Add to permanent blacklist |
| `Restore {source}` | Move from grey/excluded back to active |

### Manual Source Management Commands (via TG)

| Command | Action |
|---------|--------|
| `/add_source {url}` | Add a web source (career page or job board). Agent auto-detects type, CSS selector, enriches metadata, asks for confirmation |
| `/add_source @{channel}` | Add a public TG channel. Agent checks accessibility, scans recent posts for relevance, asks for confirmation |
| `/remove_source {id\|name\|number}` | Show source details, ask confirmation, remove from scanner config |
| `/sources` | List all sources grouped by status: active web, active TG, grey list, blacklisted |
| `/source {id\|number}` | Show detailed info: URL, type, status, stats (vacancies found, last scan, last new vacancy) |

### Processing /add_source

When user sends `/add_source {url_or_channel}`:

1. **Detect type**:
   - Starts with `@` or `t.me/` → Telegram public channel
   - Starts with `http` → Web source
   - Otherwise → ask user to clarify

2. **For Web sources**:
   a. Fetch the page
   b. Auto-detect CSS selector for job titles (see source-discovery skill for selector strategy)
   c. Test selector — count how many job listings found
   d. Classify: vendor (single company) or aggregator (multiple companies)
   e. Enrich with metadata (Layer 1)
   f. Present to user for confirmation

3. **For TG channels**:
   a. Check channel is public and accessible
   b. Scan last 50 posts for keyword matches
   c. Count subscribers (if available)
   d. Classify as aggregator
   e. Enrich with metadata
   f. Present to user for confirmation

4. **After user confirms "Approve"**:
   a. Add to `sources.json` with status `active`
   b. Add to `scanner-config/jobSites.json` (web) or `tg_sources.json` (TG)
   c. Restart scanner: `docker compose restart job-scanner`
   d. Confirm: "✅ Источник добавлен в сканирование"

5. **"Approve + scan now"** (web only):
   a. Steps a-c above
   b. Additionally trigger an immediate scan cycle

### Processing /remove_source

When user sends `/remove_source {identifier}`:

1. **Find source** by id, name (fuzzy match), or list number from last `/sources` output
2. **Show details**: name, URL, type, when added, how many vacancies found, last scan time
3. **Ask for confirmation** with options:
   - "Confirm" → remove from active, remove from scanner config, set status `removed`
   - "Blacklist" → remove + add to blacklist (won't be re-suggested by source-discovery)
   - "Cancel" → do nothing
4. **After confirmation**:
   a. Update `sources.json` → status `removed` or `blacklisted`
   b. Regenerate `scanner-config/jobSites.json` (without this source)
   c. Restart scanner
   d. Confirm: "✅ Источник удалён"

### Processing /sources

When user sends `/sources`:

1. Read `sources.json`
2. Group by status and type:
   - Active Web (with vacancy count)
   - Active Telegram (with vacancy count)
   - Grey list [if any, with reason]
   - Blacklisted [count only]
3. Show numbered list for easy reference
4. Include action hints: `/source N`, `/add_source`, `/remove_source N`

### Processing /source {id}

When user sends `/source {id_or_number}`:

1. Find source by id or list number
2. Show full details:
   - URL, type, status
   - Added date, approved date
   - CSS selector (web) or channel name (TG)
   - Total vacancies found
   - Last scan time
   - Last new vacancy date
   - Health status
3. Include actions: `/remove_source {id}`

### Processing Approval

When user approves sources:

1. Update source status in `sources.json` → `"status": "active"`
2. For web sources: add entry to `scanner-config/jobSites.json`
3. For TG sources: add to `scanner-config/tg_sources.json`
4. Confirm in TG: "✅ Добавлено {N} источников в сканирование"

### Processing Rejection

When user rejects:
1. Update status → `"status": "rejected"`
2. Do NOT add to blacklist (user may reconsider)
3. Source won't appear in future recommendations

### Processing Blacklist

When user blacklists:
1. Add to `blacklist.json` with reason and date
2. Update status → `"status": "blacklisted"`
3. Remove from scanner config if present
4. Future source-discovery will skip this source

## Health Check (POC)

Run weekly on all active sources:

### Web Sources
1. Attempt to fetch the URL
2. Check if `jobTitleSelector` still returns results
3. If fails 3 consecutive weeks → flag for user attention

### Telegram Sources
1. Check if channel is still accessible
2. Check if there are recent posts (< 30 days)
3. If no posts → flag for user attention

### Health Check Report (TG)

```
🔍 Source Health Check — {date}

✅ Healthy: 22 sources
⚠️ Issues: 3 sources

1. 🌐 Startup.jobs — CSS selector returns 0 results
   → "Fix" / "Remove"
2. 📱 @old_qa_channel — no posts for 45 days
   → "Keep" / "Grey list"
3. 🌐 TechCareers.io — HTTP 503 (3rd week)
   → "Keep" / "Remove"
```

## Grey List Logic [Architecture — Full Version]

### Entry Criteria

| Source Type | Condition | Threshold |
|-------------|-----------|-----------|
| Aggregator | No relevant vacancies found | > 180 days |
| Vendor | Zero relevant vacancies ever | Since addition |
| Any | Source returns errors consistently | > 3 weeks |

### Re-check Process (Weekly)

1. Fetch/scan grey-listed sources
2. If relevant vacancy found → restore to active, notify user
3. If source has no updates at all > `EXCLUDE_NO_UPDATE_DAYS` (60) → exclude
4. Log all actions to `grey_list_log`

### Notifications

```
⚠️ Source → Grey List
📱 @qa_remote_jobs
Причина: 180+ дней без релевантных вакансий
Будет проверяться еженедельно.
→ /restore — вернуть в активные

🔄 Grey List Re-check
Проверено: 3 источника
Восстановлен: @qa_remote_jobs (нашлась вакансия QA Director)
Без изменений: 2

❌ Source Excluded
🌐 old-board.com — нет обновлений 60+ дней
→ /restore — вернуть принудительно
```

## File Schema

### sources.json
```json
[
  {
    "id": "web_revolut_careers",
    "type": "web",
    "name": "Revolut Careers",
    "url": "https://revolut.com/careers/?query=quality",
    "status": "active",
    "added_date": "2026-02-27",
    "approved_date": "2026-02-27",
    "last_health_check": "2026-02-27",
    "health_status": "ok",
    "consecutive_failures": 0,
    "last_relevant_vacancy": null,
    "total_relevant_vacancies": 0,
    "config": {
      "jobTitleSelector": ".job-title",
      "antiBotCheck": false
    },
    "enrichment": {
      "source_type": "vendor",
      "company": "Revolut",
      "estimated_relevance": 5
    }
  }
]
```

### blacklist.json
```json
[
  {
    "id": "web_jobrocket",
    "url": "https://jobrocket.ru/en",
    "reason": "User blacklisted — irrelevant content",
    "blacklisted_date": "2026-02-27"
  }
]
```

### grey_list_log.json [Full Version]
```json
[
  {
    "source_id": "tg_qa_remote",
    "action": "grey_listed",
    "reason": "180+ days without relevant vacancies (aggregator)",
    "date": "2026-02-27"
  },
  {
    "source_id": "tg_qa_remote",
    "action": "re_checked",
    "result": "no_change",
    "date": "2026-03-06"
  }
]
```

## Sync with Scanner Config

After any status change, regenerate scanner configs:

1. `jobSites.json` — only active web sources
2. `tg_sources.json` — only active TG sources
3. Restart scanner if config changed: `docker compose restart job-scanner`
